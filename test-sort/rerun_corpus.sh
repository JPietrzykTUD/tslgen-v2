#!/usr/bin/env bash
# Re-run only the corpus stages (Q5 screen, Q6 attribute).
#
# They read nothing from best_config.tsv -- the corpus enumerates its own variant
# space -- so when they are the only stages that failed there is nothing to carry
# over from Q0 and no reason to repeat Q1 through Q4.
#
# The two stages want opposite treatment:
#
#   screen     registers parallel and deep-parallel families, so each case wants the
#              whole pin. One process, all cores.
#   attribute  admits only serial variants -- 660 cases, every one single-threaded --
#              so one process uses one core and leaves five idle. It is sharded, one
#              shard per core, each pinned to its own CPU so the shards do not
#              contend and their timings stay comparable.
set -euo pipefail
build="${TSL_COSORT_BUILD_DIR:-$HOME/bench-sort-build}"
results="${1:?usage: rerun_corpus.sh <results-dir>}"
here="$(cd "$(dirname "$0")" && pwd)"
convert="$here/benchmarks/visualization/gbench_to_paper.py"
mkdir -p "$results"

# One thread per physical core of node 0, as run_all.sh does.
phys="$(lscpu -p=CPU,CORE,NODE | grep -v '^#' \
        | awk -F, '$3==0 { if (!($2 in seen)) { seen[$2]=1; printf "%s%s", sep, $1; sep="," } }')"
IFS=',' read -r -a cpus <<< "$phys"
export COSORT_WORKERS="${#cpus[@]}"
echo "node 0 physical cores: $phys (${#cpus[@]} of them)"

# Screening is a coarser question than reporting, and its grid is much larger, so it
# gets its own settings rather than the paper's:
#
#   rle=scalar      the detector axis is Q3's, and Q3 measures it against the tuned
#                   sorter with a phase split. Screen carrying dml_sw, dsa_hw and
#                   both async backends multiplied it from 552 cases to 918 on a host
#                   with DSA -- two thirds again, for a question already answered
#                   better elsewhere.
#   3 repetitions   the output is "viable / not viable". Nine is the reporting
#                   methodology, and the reporting drivers keep it; spending 3x here
#                   buys precision the answer does not use.
#
# Together these turn a nine-hour screen into under two. Override either if you want
# the full grid: COSORT_RLE= (empty for all) and COSORT_SCREEN_REPETITIONS=9.
# What actually dominates the screen stage, measured rather than guessed.
#
# One iteration, per shape, at the LLC level, every variant family:
#
#   unique_first                62 cases in 19s
#   independent_uniform_c1024   32 cases in 22s
#   skewed_zipf_s1              32 cases in 14s
#   low_cardinality_d4          32 cases in  9s
#   unique_last_g2              46 of 62 cases in 90s
#   unique_last_g64              6 of 62 cases in 90s   -- ~15s per iteration
#
# The maximal-depth shapes are the cost, across every family -- not `deep_parallel`,
# which was my first guess and wrong. At three repetitions a 15-second iteration is
# 45s of case, and 124 such cases is most of the stage.
#
# `unique_last_*` is still screened at L2, where the same 124 cases take seconds, so
# what is lost is those shapes in the out-of-cache regime rather than the shapes
# themselves. Set COSORT_SCREEN_FILTER= to measure them and expect two to three
# hours.
screen_filter="${COSORT_SCREEN_FILTER--unique_last.*size=LLC}"
screen_reps="${COSORT_SCREEN_REPETITIONS:-3}"
attribute_reps="${COSORT_ATTRIBUTE_REPETITIONS:-9}"
export COSORT_RLE="${COSORT_RLE-scalar}"
echo "screen: rle=${COSORT_RLE:-all}, $screen_reps repetitions, \
filter=${screen_filter:-none}; attribute: $attribute_reps repetitions"

# `report_aggregates_only` governs the *file*, `display_aggregates_only` the
# *console*, and they are independent. So the JSON keeps only the aggregates the
# converter reads, while the console prints every repetition -- three lines per case
# instead of one set, which is three times finer progress and, more usefully, shows
# movement *within* a case rather than only at its end. A case that takes minutes
# stops looking like a stall.
gbench=(--benchmark_report_aggregates_only=true
        --benchmark_display_aggregates_only=false
        --benchmark_format=console --benchmark_out_format=json)

# Per-repetition time floor. gbench auto-tunes iterations to reach it, so it is the
# knob that decides what a case costs: at 0.5s a case is nine repetitions of at
# least half a second. Screening does not need that resolution.
export COSORT_MIN_TIME="${COSORT_MIN_TIME:-0.2s}"

# Line-buffered, because the output is redirected to a file. libc block-buffers a
# non-tty stdout in 4 KiB chunks, so a stage that emits one line per completed case
# appears frozen for as long as it takes ten of them to finish -- which is
# indistinguishable from the hang we were actually looking for. `stdbuf -oL` makes
# the log a live progress signal instead of a periodic dump.
line_buffered=()
if command -v stdbuf > /dev/null; then
  line_buffered=(stdbuf -oL -eL)
fi

# --- Q5: one process, the whole pin -------------------------------------------
began=$SECONDS
echo "=== q5_variants (screen)"
COSORT_STAGE=screen numactl --physcpubind="$phys" --membind=0 \
  "${line_buffered[@]+"${line_buffered[@]}"}" "$build/cosort_bench" \
  "${gbench[@]}" --benchmark_repetitions="$screen_reps" \
  --benchmark_min_time="$COSORT_MIN_TIME" \
  ${screen_filter:+--benchmark_filter="$screen_filter"} \
  --benchmark_out="$results/q5_variants.json" \
  > "$results/q5_variants.log" 2>&1
python3 "$convert" "$results/q5_variants.json" "$results/q5_variants.csv" \
  --question q5_variants
echo "--- q5_variants done in $(( (SECONDS - began) / 60 ))m"

# --- Q6: one shard per core ----------------------------------------------------
# Six filters that partition the 660 cases exactly. The last carries `style=na` --
# the scalar `std_lex_argsort` baseline, which has no SIMD style and would otherwise
# be dropped silently by a style-based split. Verified by counting: 5x108 + 120 = 660.
shards=(
  'style=intr/.*size=L2/'
  'style=intr/.*size=LLC/'
  'style=clang/.*size=L2/'
  'style=clang/.*size=LLC/'
  'style=clang_bool/.*size=L2/'
  '(style=clang_bool/.*size=LLC/|style=na/)'
)
began=$SECONDS
echo "=== q6_portability (attribute), ${#shards[@]} shards on ${#cpus[@]} cores"
pids=()
for index in "${!shards[@]}"; do
  cpu="${cpus[$(( index % ${#cpus[@]} ))]}"
  COSORT_STAGE=attribute numactl --physcpubind="$cpu" --membind=0 \
    "${line_buffered[@]+"${line_buffered[@]}"}" "$build/cosort_bench" "${gbench[@]}" \
    --benchmark_repetitions="$attribute_reps" \
    --benchmark_min_time="$COSORT_MIN_TIME" \
    --benchmark_filter="${shards[$index]}" \
    --benchmark_out="$results/q6_shard$index.json" \
    > "$results/q6_shard$index.log" 2>&1 &
  pids+=($!)
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if [[ "$failed" != 0 ]]; then
  echo "at least one shard failed; see $results/q6_shard*.log" >&2
  exit 1
fi

# One CSV from the shards: the converter emits a header per file, so all but the
# first are dropped.
: > "$results/q6_portability.csv"
for index in "${!shards[@]}"; do
  python3 "$convert" "$results/q6_shard$index.json" \
    "$results/q6_shard$index.csv" --question q6_portability
  if [[ "$index" == 0 ]]; then
    cat "$results/q6_shard$index.csv" >> "$results/q6_portability.csv"
  else
    tail -n +2 "$results/q6_shard$index.csv" >> "$results/q6_portability.csv"
  fi
done
echo "--- q6_portability done in $(( (SECONDS - began) / 60 ))m, \
$(( $(wc -l < "$results/q6_portability.csv") - 1 )) rows"
