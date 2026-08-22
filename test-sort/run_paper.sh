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

run() {  # binary, csv name, args...
  local binary="$1"; shift
  local name="$1"; shift
  if [[ ! -x "$build/$binary" ]]; then
    echo "skipping $name: $build/$binary is not built"
    return
  fi
  echo
  echo "=== $name"
  (cd "$build" && "./$binary" "$@" --csv "$results/$name.csv") \
    | tee "$results/$name.log"
}

if [[ "$quick" == "--quick" ]]; then
  # A shape and size per question: proves the pipeline, not the paper.
  narrow_q1=(--shapes low_cardinality_d4 --rows 1048576 --cols 1,4 --workers 1,24)
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
tpcds_dir="${TPCDS_KEYS:-$(dirname "$0")/data/tpcds}"
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
  echo "build check: instrumentation is compiled out"
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
if [[ -x "$build/bench_q0_tune" ]]; then
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
    "${narrow_q3[@]+"${narrow_q3[@]}"}"
# Q4 gets the tuned configuration and the measured keys: its thread axis is where
# the algorithm crossover is visible, and it is only visible on real keys -- the
# synthetic shapes are won by the quicksort at every thread count.
run bench_q4_scaling    q4_scaling    --tuned "$tuned" \
    "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q4[@]+"${narrow_q4[@]}"}"

# Q5 and Q6 are stages of the existing staged driver rather than new binaries.
if [[ -x "$build/cosort_bench" ]]; then
  # Q5 and Q6 are stages of the corpus rather than binaries of their own: a
  # bench_q5_*.cpp would have to re-implement its registration and drop
  # accounting to produce numbers it already produces. What the paper needs from
  # them is the shared schema, so the JSON is converted into it.
  converter="$(dirname "$0")/benchmarks/visualization/gbench_to_paper.py"
  for stage in screen:q5_variants attribute:q6_portability; do
    name="${stage#*:}"
    echo
    echo "=== $name (cosort_bench, ${stage%%:*} stage)"
    if (cd "$build" && COSORT_STAGE="${stage%%:*}" ./cosort_bench \
          --benchmark_repetitions=9 --benchmark_report_aggregates_only=true \
          --benchmark_format=json --benchmark_out="$results/$name.json") \
        > "$results/$name.log" 2>&1; then
      python3 "$converter" "$results/$name.json" "$results/$name.csv" \
        --question "$name" || echo "  conversion failed"
    else
      echo "  cosort_bench ${stage%%:*} failed, see $results/$name.log"
    fi
  done
fi

echo
echo "results in $results:"
ls -1 "$results"
