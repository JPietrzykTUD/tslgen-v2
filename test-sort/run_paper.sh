#!/usr/bin/env bash
# Produces every number the paper cites, with the method fixed in
# benchmarks/paper_harness.hpp and the questions listed in docs/benchmark-plan.md.
#
#   ./run_paper.sh <build-dir> <results-dir> [--quick]
#
# One CSV per question, all sharing a schema, so a figure is a query over the
# results directory rather than a re-run. Refuses to write into a results
# directory that already holds another host's numbers: merging runs from
# different machines is the one mistake that cannot be spotted afterwards.
#
# The accelerator rows need a machine with the devices. Where they are absent the
# drivers emit the row with a reason rather than skipping it, so a run from the
# wrong host is visible in the CSV instead of looking like a backend that lost.
set -euo pipefail

build="${1:?usage: run_paper.sh <build-dir> <results-dir> [--quick]}"
results="${2:?usage: run_paper.sh <build-dir> <results-dir> [--quick]}"
# Absolute from here on. Several steps run the drivers from inside the build
# directory -- `(cd "$build" && ./bench_q2_algorithms --csv "$results/...")` -- so a
# relative results path put the CSVs in the build tree while `tee` wrote the logs
# where the caller asked, splitting a results directory in half without saying so.
mkdir -p "$results"
results="$(cd "$results" && pwd)"
quick="${3:-}"

host="$(hostname)"
mkdir -p "$results"
stamp="$results/host.txt"
if [[ -f "$stamp" ]] && [[ "$(cat "$stamp")" != "$host" ]]; then
  echo "refusing to write: $results holds numbers from $(cat "$stamp"), not $host" >&2
  echo "use a different results directory per machine" >&2
  exit 1
fi
printf '%s\n' "$host" > "$stamp"

# Recorded once here as well as per row, so the directory is self-describing.
{
  printf 'host: %s\n' "$host"
  printf 'date: %s\n' "$(date -Is)"
  printf 'kernel: %s\n' "$(uname -sr)"
  printf 'cpu: %s\n' "$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')"
  printf 'cores: %s\n' "$(nproc)"
  printf 'governor: %s\n' "$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown)"
  printf 'load: %s\n' "$(cut -d' ' -f1-3 /proc/loadavg)"
  printf 'measure-cell: %s\n' \
    "$("$build/bench_q4_scaling" --axis threads --shapes low_cardinality_d4 \
        --rows 65536 --element-bytes 4 2>/dev/null \
       | grep -m1 '^measure-cell=' | cut -d= -f2 || echo unknown)"
  printf 'devices: dsa=%s iax=%s\n' \
    "$(ls -d /dev/dsa 2>/dev/null || echo absent)" \
    "$(ls -d /dev/iax 2>/dev/null || echo absent)"
} > "$results/machine.txt"
cat "$results/machine.txt"

# Which accelerator rows this machine can contribute. No host here has both, so
# the paper's accelerator table is assembled from more than one run and each row
# records where it came from.
have_dsa=$([[ -e /dev/dsa ]] && echo yes || echo no)
have_iax=$([[ -e /dev/iax ]] && echo yes || echo no)
echo "accelerators: dsa=$have_dsa iax=$have_iax"
# Ask only for what this host has. `--paths hw` would ask for every compiled
# hardware backend and drop the absent ones as unavailable, which is honest but
# fills the accelerator table with rows from the wrong machine. Override with
# COSORT_Q3_DETECTORS to force a list.
q3_detectors="scalar"
[[ "$have_dsa" == "yes" ]] && q3_detectors="$q3_detectors,dsa_hw"
[[ "$have_iax" == "yes" ]] && q3_detectors="$q3_detectors,iaa_hw,iaa_freq_hw"
q3_detectors="${COSORT_Q3_DETECTORS:-$q3_detectors}"
echo "q3 detectors: $q3_detectors"
if [[ "$have_dsa" == "no" && "$have_iax" == "no" ]]; then
  echo "  no accelerator on this host: Q3 contributes the scalar baseline only"
fi
if ! ldconfig -p 2>/dev/null | grep -q libaccel-config; then
  echo "  !! libaccel-config is not installed; DML dlopens it to enumerate work"
  echo "     queues, and without it every hardware submission fails with an"
  echo "     internal error whatever its size"
fi

if [[ -n "$(awk '{print ($1 > 1.0)}' /proc/loadavg)" ]] \
   && [[ "$(awk '{print ($1 > 1.0)}' /proc/loadavg)" == "1" ]]; then
  echo
  echo "!! load average is above 1.0; these numbers are not publishable" >&2
fi

# Elapsed per stage and since the start, printed either side of each driver. A
# full run is six to eight hours; without this the only way to tell a slow stage
# from a hung one is to watch the row count by hand.
suite_started=$SECONDS
stage_index=0
stage_total=6

elapsed_text() {  # seconds
  local s=$1
  if (( s >= 3600 )); then printf '%dh%02dm' $(( s / 3600 )) $(( (s % 3600) / 60 ))
  elif (( s >= 60 )); then printf '%dm%02ds' $(( s / 60 )) $(( s % 60 ))
  else printf '%ds' "$s"; fi
}

run() {  # binary, csv name, args...
  local binary="$1"; shift
  local name="$1"; shift
  stage_index=$(( stage_index + 1 ))
  if [[ ! -x "$build/$binary" ]]; then
    echo "skipping $name: $build/$binary is not built"
    return
  fi
  local began=$SECONDS
  echo
  echo "=== [$stage_index/$stage_total] $name  (started $(date +%H:%M:%S), \
$(elapsed_text $(( began - suite_started ))) into the run)"
  # stderr is merged in so the drivers' progress lines land in the log too: after a
  # seven-hour run the question is usually "where did the time go", and that needs
  # the timestamps, not just the final table.
  (cd "$build" && "./$binary" "$@" --csv "$results/$name.csv" 2>&1) \
    | tee "$results/$name.log"
  local took=$(( SECONDS - began ))
  echo "--- $name finished in $(elapsed_text $took); \
$(elapsed_text $(( SECONDS - suite_started ))) total so far"
}

if [[ "$quick" == "--quick" ]]; then
  # A shape and size per question: proves the pipeline, not the paper.
  narrow_q1=(--shapes low_cardinality_d4 --rows 1048576 --cols 1,4 \
             --workers "1,${COSORT_WORKERS:-$(nproc)}")
  narrow_q2=(--shapes low_cardinality_d4,skewed_zipf_s1 --rows 1048576 --cols 4 --widths 4)
  narrow_q3=(--cardinalities 1024 --cols 4 --widths 4 --workers 1 --rows 1048576)
  narrow_q4=(--axis threads --shapes skewed_zipf_s1 --widths 4 --rows 1048576)
  # The corpus stages need narrowing too: `attribute` alone is 186 registrations
  # across three styles and three widths, which is minutes even at one shape.
  export COSORT_SHAPES=low_cardinality_d4
  export COSORT_SIZE_LEVELS=1
  export COSORT_COLUMNS=3
else
  narrow_q1=()
  narrow_q2=()
  narrow_q3=()
  narrow_q4=()
fi

# Real TPC-DS / DSB keys join Q2's grid when they have been extracted. See
# benchmarks/datagen/tpcds/README.md for producing them; they are large and
# per-scale-factor, so they are not in the repository.
tpcds_args=()
# run_all.sh extracts keys to TMP/tpcds_keys/sf$scale and passes the path down, so
# this default only matters when the script is invoked directly -- which is exactly
# when it used to point at `data/tpcds`, a directory nothing writes. A standalone
# verification run then measured synthetic shapes only and said so in a line nobody
# reads until afterwards. Search the scale directories instead, and when there is
# more than one, ask the results directory which the run being reproduced used.
tpcds_dir="${TPCDS_KEYS:-}"
if [[ -z "$tpcds_dir" ]]; then
  keys_root="$(dirname "$0")/TMP/tpcds_keys"
  mapfile -t key_sets < <(
    for candidate in "$keys_root"/sf*; do
      [[ -d "$candidate" ]] && compgen -G "$candidate/*.tsldset" > /dev/null \
        && basename "$candidate"
    done)
  if [[ ${#key_sets[@]} -eq 1 ]]; then
    tpcds_dir="$keys_root/${key_sets[0]}"
  elif [[ ${#key_sets[@]} -gt 1 ]]; then
    inferred="$(python3 "$(dirname "$0")/benchmarks/visualization/infer_key_scale.py" \
                "$keys_root" "$results" 2>/dev/null || true)"
    if [[ -n "$inferred" ]]; then
      tpcds_dir="$keys_root/$inferred"
      echo "TPC-DS scale factor from the results directory: $inferred"
    else
      echo "!! more than one extracted key set (${key_sets[*]}) and nothing in" >&2
      echo "   $results to infer from. Set TPCDS_KEYS to the one you want; without" >&2
      echo "   it Q1, Q2 and Q4 measure synthetic shapes only." >&2
      tpcds_dir="$keys_root/${key_sets[0]}"
      echo "   defaulting to ${key_sets[0]}" >&2
    fi
  else
    tpcds_dir="$(dirname "$0")/data/tpcds"
  fi
fi
if [[ -d "$tpcds_dir" ]] && compgen -G "$tpcds_dir/*.tsldset" > /dev/null; then
  echo "real TPC-DS keys: $tpcds_dir ($(ls "$tpcds_dir"/*.tsldset | wc -l) files)"
  tpcds_args=(--tpcds-dir "$tpcds_dir")
else
  echo "no extracted TPC-DS keys at $tpcds_dir; Q2 runs synthetic shapes only"
  echo "  produce them with benchmarks/datagen/tpcds/extract_keys.py"
fi

# A measuring build collects nothing. The drivers announce which build they are,
# and this refuses to produce a results directory from an instrumented one:
# the counters cost up to 1.17x on the parallel index-sort path, which is enough
# to move a comparison and impossible to subtract afterwards.
if [[ -x "$build/bench_q4_scaling" ]]; then
  if ! "$build/bench_q4_scaling" --axis threads --shapes low_cardinality_d4 \
        --rows 65536 --element-bytes 4 2>&1 | grep -q "instrumentation=off"; then
    echo "refusing to measure: $build has instrumentation compiled in" >&2
    echo "  configure with: cmake -S test-sort --preset bench-dsa" >&2
    echo "  (or add -DTSL_COSORT_NO_INSTRUMENTATION=ON)" >&2
    exit 1
  fi
  if "$build/bench_q4_scaling" --axis threads --shapes low_cardinality_d4 \
        --rows 65536 --element-bytes 4 2>&1 | grep -q "TSL profile is SCALAR"; then
    echo "refusing to measure: $build resolved the scalar TSL profile" >&2
    echo "  every number would be a scalar fallback. Delete $build and" >&2
    echo "  configure it again, or set -DTSL_PROFILE=<name> deliberately." >&2
    exit 1
  fi
  echo "build check: instrumentation is compiled out, profile is not scalar"
fi

# Correctness before any number: a configuration that sorts wrongly is a bug in
# the sorter, not a slow candidate, and the tuner routing around it would hide
# that. This checks every (style, width, configuration) at a small size and fails
# the run rather than reporting a narrower grid. Well under a minute.
if [[ -x "$build/bench_q0_tune" ]]; then
  echo
  echo "=== correctness gate"
  if ! (cd "$build" && ./bench_q0_tune --verify-only) | tee "$results/verify.log" \
       | tail -1; then
    echo "a configuration sorts wrongly; fix it before measuring anything" >&2
    exit 1
  fi
fi

# Q0 next: it writes the configuration the reporting drivers read. Without it
# they fall back to defaults and label every row "(default)", which is how a
# hard-coded leaf once made the quicksort look 6.6x slower than it is.
tuned="$results/best_config.tsv"
if [[ -s "$tuned" ]]; then
  # run_all.sh already ran Q0 in full -- its output chose the cell these drivers
  # were built for, so re-running it here would be a second, possibly different
  # answer for the same question. Reuse it.
  echo
  echo "=== q0_tune: reusing $tuned ($(grep -vc '^#' "$tuned") configurations)"
elif [[ -x "$build/bench_q0_tune" ]]; then
  echo
  echo "=== q0_tune"
  if [[ "$quick" == "--quick" ]]; then
    q0_args=(--styles intr --widths 512 --workers 1 --rows 262144
             --shapes tpcds_q67_sf1,skewed_zipf_s1)
  else
    q0_args=()
  fi
  (cd "$build" && ./bench_q0_tune "${q0_args[@]+"${q0_args[@]}"}" \
      --out "$tuned" --csv "$results/q0_tune.csv") | tee "$results/q0_tune.log"
else
  echo "bench_q0_tune is not built; the drivers will use their defaults"
fi

# Q1 exists only in a build configured with -DTSL_COSORT_ENABLE_BASELINES=ON, so
# it is run when present rather than required: the default build stays
# dependency-free.
if [[ -x "$build/bench_q1_baselines" ]]; then
  run bench_q1_baselines q1_baselines --tuned "$tuned" \
      ${COSORT_WORKERS:+--workers "$COSORT_WORKERS"} \
      "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q1[@]+"${narrow_q1[@]}"}"
else
  echo
  echo "=== q1_baselines: not built; configure with -DTSL_COSORT_ENABLE_BASELINES=ON"
fi

run bench_q2_algorithms q2_algorithms --tuned "$tuned" "${tpcds_args[@]+"${tpcds_args[@]}"}" \
    "${narrow_q2[@]+"${narrow_q2[@]}"}"
# Hardware only, and only this host's hardware: the software paths are QPL's and
# DML's own CPU code, kept for correctness rather than for figures.
run bench_q3_detection  q3_detection  --tuned "$tuned" --detectors "$q3_detectors" \
    ${COSORT_WORKERS:+--workers "$COSORT_WORKERS"} \
    "${narrow_q3[@]+"${narrow_q3[@]}"}"
# Q4 gets the tuned configuration and the measured keys: its thread axis is where
# the algorithm crossover is visible, and it is only visible on real keys -- the
# synthetic shapes are won by the quicksort at every thread count.
run bench_q4_scaling    q4_scaling    --tuned "$tuned" \
    ${COSORT_MAX_WORKERS:+--max-workers "$COSORT_MAX_WORKERS"} \
    "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q4[@]+"${narrow_q4[@]}"}"

# Q5 and Q6 are stages of the existing staged driver rather than new binaries.
if [[ -x "$build/cosort_bench" ]]; then
  # Q5 and Q6 are stages of the corpus rather than binaries of their own: a
  # bench_q5_*.cpp would have to re-implement its registration and drop
  # accounting to produce numbers it already produces. What the paper needs from
  # them is the shared schema, so the JSON is converted into it.
  converter="$(dirname "$0")/benchmarks/visualization/gbench_to_paper.py"
  # `--benchmark_format` is the *console* format and `--benchmark_out_format` the
  # file's. Setting the console to json made gbench emit nothing at all until the
  # entire stage finished -- it writes one document at the end -- so an eight-hour
  # stage looked identical to a hang, and the file was going to be json anyway
  # because that is the default for --benchmark_out. Console for progress, json for
  # the file.
  # No exclusions: the full size grid, every shape. These two stages once ran for
  # hours, but that was two-way partitioning being admitted onto data whose equal
  # runs it cannot partition -- a gate that read the wrong parameter, since fixed --
  # not the number of cases. Measured after the fix: screen 38 minutes, attribute 31.
  # The two variables narrow a re-run by hand; they are not needed for a full one.
  screen_filter="${COSORT_SCREEN_FILTER-}"
  attribute_filter="${COSORT_ATTRIBUTE_FILTER-}"
  export COSORT_RLE="${COSORT_RLE-scalar}"
  export COSORT_MIN_TIME="${COSORT_MIN_TIME:-0.2s}"
  for stage in "screen:q5_variants:${COSORT_SCREEN_REPETITIONS:-3}:$screen_filter" \
               "attribute:q6_portability:${COSORT_ATTRIBUTE_REPETITIONS:-9}:$attribute_filter"; do
    IFS=':' read -r stage_name name stage_reps stage_filter <<< "$stage"
    stage="$stage_name:$name"
    stage_index=$(( stage_index + 1 ))
    corpus_began=$SECONDS
    echo
    echo "=== [$stage_index/$stage_total] $name (cosort_bench, ${stage%%:*} stage) \
$(elapsed_text $(( corpus_began - suite_started ))) into the run"
    # `stdbuf -oL`: the output is redirected, and libc block-buffers a non-tty
    # stdout, so without it a live stage looks frozen until 4 KiB of results
    # accumulate.
    if (cd "$build" && COSORT_STAGE="${stage%%:*}" \
          ${TSL_COSORT_STDBUF:-stdbuf -oL -eL} ./cosort_bench \
          --benchmark_repetitions="$stage_reps" \
          --benchmark_report_aggregates_only=true \
          --benchmark_min_time="$COSORT_MIN_TIME" \
          ${stage_filter:+--benchmark_filter="$stage_filter"} \
          --benchmark_format=console --benchmark_out_format=json \
          --benchmark_out="$results/$name.json") \
        > "$results/$name.log" 2>&1; then
      python3 "$converter" "$results/$name.json" "$results/$name.csv" \
        --question "$name" || echo "  conversion failed"
      echo "--- $name finished in $(elapsed_text $(( SECONDS - corpus_began )))"
    else
      echo "  cosort_bench ${stage%%:*} failed, see $results/$name.log"
    fi
  done
fi

echo
echo "the whole run took $(elapsed_text $(( SECONDS - suite_started )))"
echo
echo "results in $results:"
ls -1 "$results"
