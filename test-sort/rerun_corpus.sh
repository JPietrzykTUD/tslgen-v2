#!/usr/bin/env bash
# Re-run the stages that still need it, in one command:
#
#   q4  bench_q4_scaling  -- the thread/rows/columns scaling curves
#   q5  cosort_bench, screen stage    -- the variant corpus
#   q6  cosort_bench, attribute stage -- the portability corpus
#
#   ./rerun_corpus.sh <results-dir> [q4] [q5] [q6]      (no stage named = all three)
#
# Q0 through Q3 are not here. They read as complete and correct in the current
# results, and Q4 is present only because its row and column axes asked for a
# hardcoded 24 workers -- 4x oversubscription under the pin -- which is fixed but
# means its existing numbers were measured wrong. Q5 and Q6 never finished.
#
# None of the three reads best_config.tsv except Q4, so nothing here re-tunes: the
# tuned configuration is an input, and the script refuses to run Q4 without it
# rather than quietly measuring the defaults and labelling them tuned.
#
# Measured on the w5-3425 pinned to node 0's six physical cores: q4 ~40 minutes,
# q5 38, q6 31. About an hour and fifty in total.
set -uo pipefail

# --- what to run --------------------------------------------------------------
results="${1:?usage: rerun_corpus.sh <results-dir> [q4] [q5] [q6]}"
shift
stages=("$@")
if [[ ${#stages[@]} -eq 0 ]]; then
  stages=(q4 q5 q6)
fi
for stage in "${stages[@]}"; do
  case "$stage" in
    q4|q5|q6) ;;
    *) echo "unknown stage '$stage'; expected q4, q5 or q6" >&2; exit 2 ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
build="${TSL_COSORT_BUILD_DIR:-$HOME/bench-sort-build}"
convert="$here/benchmarks/visualization/gbench_to_paper.py"
mkdir -p "$results"
# Absolute from here on: the drivers run with the build directory as their working
# directory, so a relative results path would write inside the build tree.
results="$(cd "$results" && pwd)"
[[ -d "$build" ]] && build="$(cd "$build" && pwd)"

# --- the build must exist -----------------------------------------------------
# Configuring is run_all.sh's job, and it picks the compiler, the measured
# (style, width) cell and the baseline dependencies. Guessing a subset of that here
# would produce a build that measures something other than what the paper reports.
if [[ ! -f "$build/CMakeCache.txt" ]]; then
  {
    echo "no configured build at $build"
    echo
    # The preset is chosen from what /dev actually has -- bench, bench-dsa,
    # bench-iaa, or a -baselines variant -- and run_all.sh owns that choice along
    # with the compiler and the measured (style, width) cell. Reproducing a guess at
    # it here would produce a build that measures something other than what the
    # paper reports, so this points at the script that knows.
    found=()
    while IFS= read -r cache; do
      found+=("$(cd "$(dirname "$cache")" && pwd)")
    done < <(find "$here/tslctmp" "$here/../tslctmp" "$HOME" \
                  -maxdepth 2 -name CMakeCache.txt 2>/dev/null)
    # shellcheck disable=SC2207
    [[ ${#found[@]} -gt 0 ]] && found=($(printf '%s\n' "${found[@]}" | sort -u))
    if [[ ${#found[@]} -gt 0 ]]; then
      echo "configured builds found on this machine:"
      for dir in "${found[@]}"; do echo "  TSL_COSORT_BUILD_DIR=$dir"; done
      echo
    fi
    echo "To configure one: ./run_all.sh picks the preset from this host's /dev,"
    echo "along with the compiler and the measured (style, width) cell, then builds"
    echo "and runs every stage. To configure by hand, the presets are bench,"
    echo "bench-dsa, bench-iaa, bench-dsa-baselines and bench-iaa-baselines:"
    echo
    echo "  cmake -S $here -B $build --preset bench"
  } >&2
  exit 2
fi

# --- nothing else may be measuring -------------------------------------------
# One shared L3 and one memory controller per node: a second benchmark process
# invalidates both runs, and the damage is invisible afterwards unless someone
# thinks to compare start_load. This is the guard for the mistake that has actually
# happened here, which was leaving a pinned job running under someone else's sweep.
live=""
for name in cosort_bench bench_q0_tune bench_q1_baselines bench_q2_algorithms \
            bench_q3_detection bench_q4_scaling; do
  if pgrep -x "$name" > /dev/null 2>&1; then
    live="$live $name($(pgrep -x "$name" | tr '\n' ' '))"
  fi
done
if [[ -n "$live" ]]; then
  echo "refusing to start: a benchmark is already running:$live" >&2
  echo "kill it by pid and re-run, or set COSORT_ALLOW_CONCURRENT=1 to override" >&2
  [[ "${COSORT_ALLOW_CONCURRENT:-0}" == "1" ]] || exit 2
  echo "COSORT_ALLOW_CONCURRENT=1: continuing, and these numbers are contaminated" >&2
fi
load="$(awk '{print $1}' /proc/loadavg)"
if awk "BEGIN { exit !($load > 1.0) }"; then
  echo "warning: load average is $load before starting; expect noise" >&2
fi

# --- the pin ------------------------------------------------------------------
# One thread per physical core of node 0. Two NUMA nodes and two SMT threads per
# core mean the logical count is four times the width worth measuring: a
# memory-bound co-sort across all of them measures SMT pairs sharing an L1 and
# gathers crossing the interconnect. The drivers cap their own worker counts at
# min(physical cores per node, affinity mask), so this pin and that cap agree.
phys="$(lscpu -p=CPU,CORE,NODE | grep -v '^#' \
        | awk -F, '$3==0 { if (!($2 in seen)) { seen[$2]=1; printf "%s%s", sep, $1; sep="," } }')"
IFS=',' read -r -a cpus <<< "$phys"
export COSORT_WORKERS="${#cpus[@]}"
pin=(numactl --physcpubind="$phys" --membind=0)
echo "pin: node 0 physical cores $phys (${#cpus[@]} of them)"
# Echo the size grid. It is an environment variable read inside the binary, so a run
# that was meant to include 2xLLC and silently did not looks exactly like one that
# was not: the only evidence is the size= field of every case name in the log.
echo "size levels: ${COSORT_SIZE_LEVELS:-stage default (1,3 = L2 and LLC)}"
echo "stages: ${stages[*]}"
echo "build: $build"
echo "results: $results"

# --- build what we are about to run -------------------------------------------
targets=()
for stage in "${stages[@]}"; do
  case "$stage" in
    q4) targets+=(bench_q4_scaling) ;;
    q5|q6) targets+=(cosort_bench) ;;
  esac
done
# shellcheck disable=SC2207
targets=($(printf '%s\n' "${targets[@]}" | sort -u))
echo "building: ${targets[*]}"
if ! cmake --build "$build" -j "$(nproc)" --target "${targets[@]}" > /tmp/rerun-build.log 2>&1; then
  echo "build failed; see /tmp/rerun-build.log" >&2
  tail -20 /tmp/rerun-build.log >&2
  exit 2
fi

# --- shared settings ----------------------------------------------------------
# `report_aggregates_only` governs the *file*, `display_aggregates_only` the
# *console*, and they are independent. So the JSON keeps only the aggregates the
# converter reads, while the console prints every repetition -- three times finer
# progress, and movement *within* a case rather than only at its end, so a case that
# takes minutes stops looking like a stall.
gbench=(--benchmark_report_aggregates_only=true
        --benchmark_display_aggregates_only=false
        --benchmark_format=console --benchmark_out_format=json)

# Per-repetition time floor. gbench auto-tunes iterations to reach it, so it is the
# knob that decides what a case costs.
export COSORT_MIN_TIME="${COSORT_MIN_TIME:-0.2s}"

# Screening is a coarser question than reporting and its grid is much larger, so it
# gets its own settings: the detector axis is Q3's (screen carrying dml_sw, dsa_hw
# and both async backends took it from 552 cases to 918 on a DSA host, for a question
# answered better elsewhere), and three repetitions suffice for "viable / not
# viable". COSORT_RLE= and COSORT_SCREEN_REPETITIONS=9 restore both.
export COSORT_RLE="${COSORT_RLE-scalar}"
screen_reps="${COSORT_SCREEN_REPETITIONS:-3}"
attribute_reps="${COSORT_ATTRIBUTE_REPETITIONS:-9}"

# Nothing is excluded: the full size grid, every shape at every level. These stages
# did once run for hours, and the cause was a gate bug rather than the number of
# cases -- two_way_allowed read the distinct-count parameters `d`, `d1` and `c`, but
# the unique_last family carries `g`, the terminal group size, which *is* the
# equal-run length. Finding none of the three it concluded "no cardinality, treat as
# unique" and admitted every group size up to 4096 to two-way partitioning, which is
# quadratic in exactly that run. At the LLC size `unique_last_g64` cost 60s per
# iteration per two-way variant against 0.24s for three-way on the same data; with
# `g` read it is 0.65s. The two filter variables narrow a re-run by hand and default
# to empty.
screen_filter="${COSORT_SCREEN_FILTER-}"
attribute_filter="${COSORT_ATTRIBUTE_FILTER-}"

# Line-buffered, because the output is redirected to a file. libc block-buffers a
# non-tty stdout in 4 KiB chunks, so a stage emitting one line per completed case
# looks frozen until ten of them finish -- indistinguishable from the hang we were
# actually looking for.
line_buffered=()
if command -v stdbuf > /dev/null; then
  line_buffered=(stdbuf -oL -eL)
fi

elapsed_text() {
  local s=$1
  if (( s >= 3600 )); then printf '%dh%02dm' $(( s / 3600 )) $(( (s % 3600) / 60 ))
  elif (( s >= 60 )); then printf '%dm%02ds' $(( s / 60 )) $(( s % 60 ))
  else printf '%ds' "$s"; fi
}

# A result file about to be overwritten is moved aside, not replaced. Q4's existing
# csv holds 384 measured rows; they are wrong in a known way, which is not the same
# as worthless.
keep_previous() {  # path
  [[ -f "$1" ]] || return 0
  mkdir -p "$results/superseded"
  local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
  mv "$1" "$results/superseded/$(basename "${1%.*}")-$stamp.${1##*.}"
}

suite_started=$SECONDS
failed=()
ran=()

# --- q4 -----------------------------------------------------------------------
run_q4() {
  local tuned="$results/best_config.tsv"
  if [[ ! -f "$tuned" ]]; then
    echo "q4 needs $tuned, which Q0 writes. Run ./run_all.sh, or copy the tuned" >&2
    echo "configuration in; measuring the defaults would mislabel them as tuned." >&2
    return 2
  fi
  local tpcds=() dir="${TPCDS_KEYS:-$here/data/tpcds}"
  if [[ -d "$dir" ]] && compgen -G "$dir/*.tsldset" > /dev/null; then
    tpcds=(--tpcds-dir "$dir")
    echo "  real TPC-DS keys: $dir ($(ls "$dir"/*.tsldset | wc -l) files)"
  else
    echo "  no TPC-DS keys at $dir; synthetic shapes only, and the algorithm"
    echo "  crossover is only visible on measured keys"
  fi
  # Extra flags for a narrowed re-run, as COSORT_Q0_ARGS does for the tuner:
  #   COSORT_Q4_ARGS="--axis threads"                    one axis
  #   COSORT_Q4_ARGS="--shapes skewed_zipf_s1 --widths 4"  one shape, one key width
  # A full re-run needs none of them.
  read -r -a q4_extra <<< "${COSORT_Q4_ARGS:-}"
  keep_previous "$results/q4_scaling.csv"
  ( cd "$build" && "${pin[@]}" "${line_buffered[@]+"${line_buffered[@]}"}" \
      ./bench_q4_scaling --tuned "$tuned" \
      ${COSORT_MAX_WORKERS:+--max-workers "$COSORT_MAX_WORKERS"} \
      "${tpcds[@]+"${tpcds[@]}"}" "${q4_extra[@]+"${q4_extra[@]}"}" \
      --csv "$results/q4_scaling.csv" 2>&1 ) | tee "$results/q4_scaling.log"
  return "${PIPESTATUS[0]}"
}

# --- q5 / q6 ------------------------------------------------------------------
# Stages of the existing corpus driver rather than binaries of their own: a
# bench_q5_*.cpp would re-implement registration and drop accounting to produce
# numbers it already produces. What the paper needs is the shared schema, so the
# gbench json is converted into it.
#
# One process each, run one after the other. Neither is split across cores, and the
# idle cores during the serial attribute stage are deliberate: six concurrent
# processes would each get a fifth of the shared 30 MiB L3 and a sixth of the node's
# bandwidth, and the cases sized to the LLC are exactly the ones that would
# interfere -- exactly the ones worth measuring. Benchmarks do not run concurrently.
run_corpus() {  # stage, csv name, repetitions, filter
  local stage="$1" name="$2" reps="$3" filter="$4"
  echo "  ${filter:+filter=$filter, }$reps repetitions, rle=${COSORT_RLE:-all}"
  keep_previous "$results/$name.csv"
  COSORT_STAGE="$stage" "${pin[@]}" \
    "${line_buffered[@]+"${line_buffered[@]}"}" "$build/cosort_bench" \
    "${gbench[@]}" --benchmark_repetitions="$reps" \
    --benchmark_min_time="$COSORT_MIN_TIME" \
    ${filter:+--benchmark_filter="$filter"} \
    --benchmark_out="$results/$name.json" \
    > "$results/$name.log" 2>&1
  local status=$?
  if (( status != 0 )); then
    echo "  cosort_bench $stage exited $status; see $results/$name.log" >&2
    return "$status"
  fi
  python3 "$convert" "$results/$name.json" "$results/$name.csv" --question "$name"
}

for stage in "${stages[@]}"; do
  began=$SECONDS
  echo
  echo "=== $stage  (started $(date +%H:%M:%S), $(elapsed_text $(( began - suite_started ))) in)"
  case "$stage" in
    q4) run_q4 ;;
    q5) run_corpus screen    q5_variants    "$screen_reps"    "$screen_filter" ;;
    q6) run_corpus attribute q6_portability "$attribute_reps" "$attribute_filter" ;;
  esac
  status=$?
  if (( status == 0 )); then
    ran+=("$stage")
    echo "--- $stage finished in $(elapsed_text $(( SECONDS - began )))"
  else
    failed+=("$stage")
    echo "--- $stage FAILED after $(elapsed_text $(( SECONDS - began )))" >&2
  fi
done

echo
echo "=== total $(elapsed_text $(( SECONDS - suite_started )))"
for stage in "${ran[@]+"${ran[@]}"}"; do
  case "$stage" in
    q4) csv="$results/q4_scaling.csv" ;;
    q5) csv="$results/q5_variants.csv" ;;
    q6) csv="$results/q6_portability.csv" ;;
  esac
  if [[ -f "$csv" ]]; then
    echo "  $stage  $(( $(wc -l < "$csv") - 1 )) rows  $csv"
  fi
done
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "  failed: ${failed[*]}" >&2
  exit 1
fi
