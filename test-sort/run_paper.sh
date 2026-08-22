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
if [[ "$have_dsa" == "no" && "$have_iax" == "no" ]]; then
  echo "  no accelerator on this host: Q3's hardware rows will all be drops"
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

run bench_q2_algorithms q2_algorithms "${tpcds_args[@]+"${tpcds_args[@]}"}" \
    "${narrow_q2[@]+"${narrow_q2[@]}"}"
# Hardware paths only: the software ones are QPL's and DML's own CPU code, kept
# for correctness rather than for figures.
run bench_q3_detection  q3_detection  --paths hw "${narrow_q3[@]+"${narrow_q3[@]}"}"
run bench_q4_scaling    q4_scaling    "${narrow_q4[@]+"${narrow_q4[@]}"}"

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
