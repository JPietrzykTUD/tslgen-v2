#!/usr/bin/env bash
# Re-run only the corpus stages (Q5 screen, Q6 attribute).
#
# They read nothing from best_config.tsv -- the corpus enumerates its own variant
# space -- so when they are the only stages that failed there is nothing to carry
# over from Q0 and no reason to repeat Q1 through Q4.
#
# Both stages run as a single process, one after the other. Neither is split across
# cores, and the idle cores during the serial attribute stage are deliberate: the
# socket has one shared L3 and one memory controller per node, so concurrent
# processes measure each other's cache and bandwidth pressure rather than the sorter.
# Wall clock is bought by measuring fewer cases, never by measuring them at once.
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

# --- Q6: one process, sequentially ------------------------------------------------
# NOT sharded across cores, though it is single-threaded and six sit idle.
#
# One 30 MiB L3 is shared by every core on this socket, and one memory controller by
# every core on the node. Six concurrent processes each holding a ~30 MB working set
# would get a fifth of the cache each and a sixth of the bandwidth -- and the cases
# sized to the LLC are exactly the ones that would interfere, which are exactly the
# ones worth measuring. A sharded run finishes six times sooner and reports numbers
# that are six-way cache contention rather than the sorter. Benchmarks do not run
# concurrently.
#
# The time is bought back by measuring fewer cases, not by measuring them badly:
# `unique_last_*` at LLC is ~15s per iteration and dominates here as it does in
# screen, and COSORT_ELEMENT_BYTES=4 halves the stage if the 8-byte half of the style
# table is not needed.
attribute_filter="${COSORT_ATTRIBUTE_FILTER--unique_last.*size=LLC}"
began=$SECONDS
echo "=== q6_portability (attribute), one process, filter=${attribute_filter:-none}"
COSORT_STAGE=attribute numactl --physcpubind="$phys" --membind=0 \
  "${line_buffered[@]+"${line_buffered[@]}"}" "$build/cosort_bench" "${gbench[@]}" \
  --benchmark_repetitions="$attribute_reps" \
  --benchmark_min_time="$COSORT_MIN_TIME" \
  ${attribute_filter:+--benchmark_filter="$attribute_filter"} \
  --benchmark_out="$results/q6_portability.json" \
  > "$results/q6_portability.log" 2>&1
python3 "$convert" "$results/q6_portability.json" "$results/q6_portability.csv" \
  --question q6_portability
echo "--- q6_portability done in $(( (SECONDS - began) / 60 ))m"
