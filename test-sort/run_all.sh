#!/usr/bin/env bash
# Everything, from a clean checkout to a results directory.
#
#   ./run_all.sh [results-dir] [--quick] [--scale N] [--no-baselines]
#
# Four steps, each skipped when it is already done, so re-running after a failure
# does not repeat the expensive parts:
#
#   1. configure   the measurement preset for this host's accelerators
#   2. data        DSB's dsdgen, then the projected key columns
#   3. build       every target run_paper.sh invokes
#   4. run         run_paper.sh
#
# The preset is chosen from what /dev actually has, and it is always a *measurement*
# preset: counters compiled out, phase timers off. run_paper.sh refuses to write a
# results directory from any other kind of build, so this cannot quietly produce
# instrumented numbers.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"

results="${1:-$root/results/$(hostname)}"
quick=""
scale=1
baselines=yes
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) quick="--quick" ;;
    --scale) scale="$2"; shift ;;
    --no-baselines) baselines=no ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- the compiler -------------------------------------------------------------
# Pinned rather than discovered: the generated TSL selects its profile and its
# compiler-capability defines from the compiler it is configured with, so a
# different one is a different library, and comparing results across them would be
# comparing two things at once.
# Deliberately not `$CXX`: that variable is often already set to something else in
# a dev container -- it was `zig c++` here, which this script happily picked up on
# its first run. The override is its own name so an unrelated environment cannot
# silently change which compiler produced a published measurement.
compiler="${TSL_COSORT_CXX:-clang++-22}"
if ! command -v "$compiler" > /dev/null 2>&1; then
  echo "$compiler is not on PATH." >&2
  echo "  Set TSL_COSORT_CXX to override. Note that the generated TSL selects its" >&2
  echo "  profile and capability defines from the compiler, so results from two" >&2
  echo "  compilers are not comparable." >&2
  exit 1
fi
echo "compiler: $compiler ($("$compiler" --version | head -1))"

# --- 1. configure -------------------------------------------------------------
have_dsa=$([[ -e /dev/dsa ]] && echo yes || echo no)
have_iax=$([[ -e /dev/iax ]] && echo yes || echo no)
if [[ "$have_dsa" == "yes" && "$baselines" == "yes" ]]; then
  preset=bench-dsa-baselines
elif [[ "$have_dsa" == "yes" ]]; then
  preset=bench-dsa
elif [[ "$have_iax" == "yes" ]]; then
  preset=bench-iaa
else
  preset=bench
fi
build="$root/tslctmp/test-sort-$preset"
echo "accelerators: dsa=$have_dsa iax=$have_iax  ->  preset $preset"
echo
echo "=== 1/4 configure"
extra=()
[[ "$preset" == "bench-iaa" && "$baselines" == "yes" ]] \
  && extra+=(-DTSL_COSORT_ENABLE_BASELINES=ON)
cmake -S "$here" --preset "$preset" -DCMAKE_CXX_COMPILER="$compiler" \
      "${extra[@]+"${extra[@]}"}"

# --- 2. data ------------------------------------------------------------------
# Real query keys. Large and per-scale-factor, so they live outside the repository
# and are produced once. Q1, Q2 and Q4 pick them up; without them those drivers
# run synthetic shapes only and say so.
keys="$here/TMP/tpcds_keys"
echo
echo "=== 2/4 data (scale factor $scale)"
if compgen -G "$keys/*.tsldset" > /dev/null; then
  echo "keys already extracted: $(ls "$keys"/*.tsldset | wc -l) files in $keys"
else
  gen="$here/benchmarks/datagen/tpcds"
  if [[ ! -x "$gen/.dsb/code/tools/dsdgen" ]]; then
    echo "building DSB's dsdgen"
    (cd "$gen" && ./build_generator.sh)
  fi
  if [[ ! -d "$gen/.data/sf$scale" ]]; then
    echo "generating tables at scale factor $scale"
    (cd "$gen" && ./generate.sh "$scale")
  fi
  echo "extracting key columns"
  mkdir -p "$keys"
  (cd "$gen" && ./extract_keys.py --data ".data/sf$scale" \
      --schema .dsb/scripts/create_tables.sql --out "$keys" \
      --queries q067,q064,q010,q050,q081)
fi

# --- 3. build, in two phases --------------------------------------------------
# The reporting drivers can only be *built* for one (style, register width) cell:
# both are template parameters of the sorters, sitting under a configuration
# dispatch that is already 36 instantiations per key width, so crossing them with
# nine cells is 324 and minutes of compile per driver. The cell is therefore a
# build parameter -- which is only honest if something chooses it from measurement
# rather than from a default nobody revisits.
#
# So: build the tuner, ask it which cell wins on this host, then build everything
# else for that cell. The probe is small on purpose (two shapes, few rows) because
# it is ranking cells rather than choosing a configuration; the full Q0 inside
# run_paper.sh re-checks the built cell against its own nine and says so if the
# choice was wrong by more than 10%.
echo
echo "=== 3/4 build (phase 1: the tuner)"
cmake --build "$build" -j "$(nproc)" --target bench_q0_tune

echo
echo "--- probing for this host's best (style, width) cell"
probe="$("$build/bench_q0_tune" --workers 1 --rows 65536 \
           --shapes low_cardinality_d4,skewed_zipf_s1 --out /dev/null 2>&1 \
         | grep '^TSL_COSORT_BEST_CELL' | tail -1 || true)"
if [[ -n "$probe" ]]; then
  cell_style="$(awk '{print $2}' <<< "$probe")"
  cell_width="$(awk '{print $3}' <<< "$probe")"
  case "$cell_style" in
    intr)       cell_style=Intrinsics ;;
    clang)      cell_style=ClangBuiltin ;;
    clang_bool) cell_style=ClangBoolMask ;;
    *) echo "unrecognised style '$cell_style' from the probe; keeping the default" >&2
       cell_style="" ;;
  esac
  if [[ -n "$cell_style" ]]; then
    echo "best cell on this host: $cell_style/$cell_width-bit"
    cmake -S "$here" --preset "$preset" -DCMAKE_CXX_COMPILER="$compiler" \
          -DTSL_COSORT_MEASURE_STYLE="$cell_style" \
          -DTSL_COSORT_MEASURE_WIDTH="$cell_width" \
          "${extra[@]+"${extra[@]}"}"
  fi
else
  echo "the probe produced no cell; building for the default" >&2
fi

echo
echo "=== 3/4 build (phase 2: everything else)"
targets=(bench_q0_tune bench_q2_algorithms bench_q3_detection bench_q4_scaling
         cosort_bench)
[[ "$baselines" == "yes" ]] && targets+=(bench_q1_baselines)
cmake --build "$build" -j "$(nproc)" --target "${targets[@]}"

# --- 4. run -------------------------------------------------------------------
echo
echo "=== 4/4 run"
TPCDS_KEYS="$keys" "$here/run_paper.sh" "$build" "$results" ${quick:+$quick}
