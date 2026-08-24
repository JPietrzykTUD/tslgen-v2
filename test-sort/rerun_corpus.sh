#!/usr/bin/env bash
# Re-run only the corpus stages. They read nothing from best_config.tsv -- the
# corpus enumerates its own variant space -- so Q0's output is not needed and
# Q0-Q4's CSVs are untouched.
set -euo pipefail
build="${TSL_COSORT_BUILD_DIR:-$HOME/bench-sort-build}"
results="${1:?usage: rerun_q5q6.sh <results-dir>}"
here="$(cd "$(dirname "$0")" && pwd)"

# One thread per physical core of node 0, as run_all.sh does.
phys="$(lscpu -p=CPU,CORE,NODE | grep -v '^#' \
        | awk -F, '$3==0 { if (!($2 in seen)) { seen[$2]=1; printf "%s%s", sep, $1; sep="," } }')"
pin=(numactl --physcpubind="$phys" --membind=0)
# Belt and braces: the corpus now sizes its pool from the affinity mask, but saying
# it explicitly means a run under a pin this script did not set is still right.
export COSORT_WORKERS="$(awk -F, '{print NF}' <<< "$phys")"
echo "pinned to $phys, $COSORT_WORKERS workers"

for stage in screen:q5_variants attribute:q6_portability; do
  name="${stage#*:}"
  began=$SECONDS
  echo "=== $name (${stage%%:*})"
  COSORT_STAGE="${stage%%:*}" "${pin[@]}" "$build/cosort_bench" \
    --benchmark_repetitions=9 --benchmark_report_aggregates_only=true \
    --benchmark_format=console --benchmark_out_format=json \
    --benchmark_out="$results/$name.json" > "$results/$name.log" 2>&1
  python3 "$here/benchmarks/visualization/gbench_to_paper.py" \
    "$results/$name.json" "$results/$name.csv" --question "$name"
  echo "--- $name done in $(( (SECONDS - began) / 60 ))m"
done
