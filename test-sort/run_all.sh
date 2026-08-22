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

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

results=""
quick=""
scale=1
baselines=yes
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --quick) quick="--quick" ;;
    --scale) scale="${2:?--scale needs a number}"; shift ;;
    --no-baselines) baselines=no ;;
    -*) echo "unknown option: $1" >&2; usage 2 ;;
    *)
      # A bare argument is the results directory, and only the first one is. The
      # earlier version took `$1` unconditionally, so `--help` became a directory
      # name and the run started anyway.
      if [[ -n "$results" ]]; then
        echo "more than one results directory given: $results and $1" >&2
        usage 2
      fi
      results="$1"
      ;;
  esac
  shift
done
results="${results:-$root/results/$(hostname)}"

# --- the compiler -------------------------------------------------------------
# Pinned rather than discovered: the generated TSL selects its profile and its
# compiler-capability defines from the compiler it is configured with, so a
# different one is a different library, and comparing results across them would be
# comparing two things at once.
# Clang 22 or newer, because the generated TSL's clang implementation family needs
# its elementwise builtins -- but *newer* is fine, so the version is discovered
# rather than pinned. The first version of this script required exactly
# `clang++-22` and failed on a host that had only clang++-24.
#
# Deliberately not `$CXX`: that variable is often already set to something else in
# a dev container -- it was `zig c++` here, which an earlier version of this script
# happily picked up. The override has its own name so an unrelated environment
# cannot silently change which compiler produced a published measurement.
clang_major_of() {
  "$1" --version 2>/dev/null | sed -n 's/.*clang version \([0-9]\+\).*/\1/p' | head -1
}

compiler="${TSL_COSORT_CXX:-}"
if [[ -z "$compiler" ]]; then
  for candidate in clang++-26 clang++-25 clang++-24 clang++-23 clang++-22 clang++; do
    command -v "$candidate" > /dev/null 2>&1 || continue
    major="$(clang_major_of "$candidate")"
    if [[ -n "$major" && "$major" -ge 22 ]]; then
      compiler="$candidate"
      break
    fi
  done
fi
if [[ -z "$compiler" ]] || ! command -v "$compiler" > /dev/null 2>&1; then
  echo "no clang++ 22 or newer on PATH." >&2
  echo "  The generated TSL's clang implementation family needs clang 22's" >&2
  echo "  elementwise builtins; below that the style axis measures TSL's scalar" >&2
  echo "  fallbacks instead of the styles." >&2
  echo "  Set TSL_COSORT_CXX to name one explicitly." >&2
  exit 1
fi
major="$(clang_major_of "$compiler")"
if [[ -z "$major" || "$major" -lt 22 ]]; then
  echo "$compiler reports version '${major:-unknown}', and 22 or newer is required." >&2
  exit 1
fi
# The C compiler has to match: DML's kernels are C, and the `clang` preset pins
# `clang-22`, which is wrong on a host that has only a newer one. Passing both
# explicitly is what stops the preset's value surviving into the cache.
c_compiler="${TSL_COSORT_CC:-}"
if [[ -z "$c_compiler" ]]; then
  c_compiler="${compiler%++*}${compiler#*++}"      # clang++-24 -> clang-24
  command -v "$c_compiler" > /dev/null 2>&1 || c_compiler=clang
fi
echo "compiler: $compiler (clang $major), C: $c_compiler"
echo "          $("$compiler" --version | head -1)"

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

# A build directory carried over from another machine keeps a CMakeCache.txt whose
# recorded source and binary paths are that machine's, and cmake refuses to reuse
# it -- correctly, but fatally, and the message is about "reediting the cache"
# rather than about deleting a directory that should never have travelled. Detect
# it and start clean.
if [[ -f "$build/CMakeCache.txt" ]]; then
  cached_home="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$build/CMakeCache.txt")"
  if [[ -n "$cached_home" && "$cached_home" != "$here" ]]; then
    echo "$build was configured for $cached_home, not $here -- removing it"
    rm -rf "$build"
  fi
fi

configure() {
  cmake -S "$here" --preset "$preset" \
        -DCMAKE_CXX_COMPILER="$compiler" -DCMAKE_C_COMPILER="$c_compiler" \
        "${extra[@]+"${extra[@]}"}" "$@"
}
configure

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
    configure -DTSL_COSORT_MEASURE_STYLE="$cell_style" \
              -DTSL_COSORT_MEASURE_WIDTH="$cell_width"
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
