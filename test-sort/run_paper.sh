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
  narrow_q2=(--shapes low_cardinality_d4,skewed_zipf_s1 --rows 1048576 --cols 4 --widths 4)
  narrow_q3=(--cardinalities 1024 --cols 4 --widths 4 --workers 1 --rows 1048576)
  narrow_q4=(--axis threads --shapes skewed_zipf_s1 --widths 4 --rows 1048576)
  # The corpus stages need narrowing too: `attribute` alone is 186 registrations
  # across three styles and three widths, which is minutes even at one shape.
  export COSORT_SHAPES=low_cardinality_d4
  export COSORT_SIZE_LEVELS=1
  export COSORT_COLUMNS=3
else
  narrow_q2=()
  narrow_q3=()
  narrow_q4=()
fi

run bench_q2_algorithms q2_algorithms "${narrow_q2[@]+"${narrow_q2[@]}"}"
run bench_q3_detection  q3_detection  "${narrow_q3[@]+"${narrow_q3[@]}"}"
run bench_q4_scaling    q4_scaling    "${narrow_q4[@]+"${narrow_q4[@]}"}"

# Q5 and Q6 are stages of the existing staged driver rather than new binaries.
if [[ -x "$build/cosort_bench" ]]; then
  echo
  echo "=== q5_variants (cosort_bench, screen stage)"
  (cd "$build" && COSORT_STAGE=screen ./cosort_bench \
      --benchmark_format=json --benchmark_out="$results/q5_variants.json") \
    > "$results/q5_variants.log" 2>&1 || echo "  cosort_bench screen failed, see the log"
  echo
  echo "=== q6_portability (cosort_bench, attribute stage)"
  (cd "$build" && COSORT_STAGE=attribute ./cosort_bench \
      --benchmark_format=json --benchmark_out="$results/q6_portability.json") \
    > "$results/q6_portability.log" 2>&1 || echo "  cosort_bench attribute failed, see the log"
fi

echo
echo "results in $results:"
ls -1 "$results"
