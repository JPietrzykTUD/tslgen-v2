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
# Absolute, for the same reason run_paper.sh does it: the steps below run from
# inside the build directory.
mkdir -p "$results"
results="$(cd "$results" && pwd)"

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
if [[ "$have_dsa" == "yes" ]]; then
  preset=bench-dsa
elif [[ "$have_iax" == "yes" ]]; then
  preset=bench-iaa
else
  preset=bench
fi
# Baselines are orthogonal to accelerators, and used not to be: the accelerator
# preset was chosen first and only `bench-dsa-baselines` carried the flag, with
# `bench-iaa` getting it from an extra argument further down. A host with neither
# device landed on `bench`, which has no baselines variant and matched no branch, so
# Q1's external comparisons were silently unbuildable there -- every ips4o, Arrow,
# x86-simd-sort and std::sort row came out as "not built", hours into a run, on the
# one question whose whole point is the comparison. `bench-iaa-baselines` existed
# and was never selected.
#
# Prefer the preset variant where there is one, so the build directory name records
# the choice; `bench` has no variant, so it takes the flag directly.
extra=()
if [[ "$baselines" == "yes" ]]; then
  case "$preset" in
    bench-dsa|bench-iaa) preset="$preset-baselines" ;;
    bench) extra+=(-DTSL_COSORT_ENABLE_BASELINES=ON) ;;
  esac
fi
# Where the binaries go. Overridable because a repository can be visible under two
# paths at once -- a devcontainer bind-mounts the host checkout, so
# /home/you/repo and /workspaces/repo are the same directory -- and cmake keys its
# cache on the source path *string*. Two views therefore fight over one build
# directory, each invalidating the other's cache, and the loser is whichever one
# ran second. Give each view its own:
#
#   TSL_COSORT_BUILD_DIR=~/bench-build ./run_all.sh ...
build="${TSL_COSORT_BUILD_DIR:-$root/tslctmp/test-sort-$preset}"
echo "accelerators: dsa=$have_dsa iax=$have_iax  ->  preset $preset"
echo "external baselines (ips4o, Arrow, x86-simd-sort, TBB): $baselines"
# The work queues are character devices, usually root-owned and mode 600. Without
# access the accelerator rows come out as drops naming the reason, which is honest
# but empty -- and the point of running on this host is those rows. Said here, once,
# rather than discovered in Q3's output hours later.
for _dev in /dev/dsa/wq* /dev/iax/wq*; do
  [[ -e "$_dev" ]] || continue
  if [[ ! -r "$_dev" ]]; then
    echo "  !! $_dev is not readable by $(id -un): the accelerator rows will be drops."
    echo "     Either grant access once --"
    echo "       sudo chgrp \$(id -gn) $(dirname "$_dev")/wq* && sudo chmod 660 $(dirname "$_dev")/wq*"
    echo "     (a udev rule if it should survive a reboot) -- or run this whole"
    echo "     script under sudo, which also makes every build tree, the 13 GB of"
    echo "     generated tables and the results directory root-owned."
  fi
  break
done
echo
echo "=== 1/4 configure"
# A build directory carried over from another machine keeps a CMakeCache.txt whose
# recorded source and binary paths are that machine's, and cmake refuses to reuse
# it -- correctly, but fatally, and the message is about "reediting the cache"
# rather than about deleting a directory that should never have travelled. Detect
# it and start clean.
if [[ -f "$build/CMakeCache.txt" ]]; then
  cached_home="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$build/CMakeCache.txt")"
  if [[ -n "$cached_home" && "$cached_home" != "$here" ]]; then
    # Same directory under a different path is the common case here, not a tree
    # copied from another machine: compare what the paths resolve to before
    # deciding this cache is foreign.
    same_tree=no
    if [[ -d "$cached_home" ]]; then
      cached_id="$(stat -c '%d:%i' "$cached_home" 2>/dev/null || true)"
      here_id="$(stat -c '%d:%i' "$here" 2>/dev/null || true)"
      [[ -n "$cached_id" && "$cached_id" == "$here_id" ]] && same_tree=yes
    fi
    if [[ "$same_tree" == "yes" ]]; then
      echo "  !! $build was configured as $cached_home, which is this same"
      echo "     directory under another path -- a container bind-mount, most"
      echo "     likely. cmake keys its cache on the path string, so reusing this"
      echo "     build directory means the two views keep invalidating each other."
      echo "     Reconfiguring it for $here now; set TSL_COSORT_BUILD_DIR to give"
      echo "     each view its own build directory and stop the thrashing."
    else
      echo "$build was configured for $cached_home, a different tree -- removing it"
    fi
    rm -rf "$build"
  fi
fi

configure() {
  # `-B "$build"` is not redundant. A preset carries its own `binaryDir`, so
  # `--preset` alone writes wherever the preset says -- which silently ignores
  # TSL_COSORT_BUILD_DIR and leaves configure and build looking at two different
  # directories. That surfaced as cmake's "could not load cache" at the first
  # build step, with a configure log that had just reported success. An explicit
  # -B overrides the preset, so one variable decides for both.
  cmake -S "$here" -B "$build" --preset "$preset" \
        -DCMAKE_CXX_COMPILER="$compiler" -DCMAKE_C_COMPILER="$c_compiler" \
        "${extra[@]+"${extra[@]}"}" "$@"
}
configure

# --- 2. data ------------------------------------------------------------------
# Real query keys. Large and per-scale-factor, so they live outside the repository
# and are produced once. Q1, Q2 and Q4 pick them up; without them those drivers
# run synthetic shapes only and say so.
#
# The directory is *named* for the scale factor, and carries a manifest recording
# it. The earlier version checked only whether any keys existed, so asking for
# `--scale 10` with scale-1 keys already present skipped the generation and
# measured scale 1 while the log said 10 -- the worst kind of wrong, because every
# number was real and every label was a lie. Keeping them in separate directories
# also means two scale factors can coexist rather than one overwriting the other.
gen="$here/benchmarks/datagen/tpcds"
keys="$here/TMP/tpcds_keys/sf$scale"
manifest="$keys/manifest.txt"
echo
echo "=== 2/4 data (scale factor $scale)"

# Keys from before this layout existed, flat in TMP/tpcds_keys. Their scale factor
# was never recorded, so they are reported and ignored rather than guessed at.
if compgen -G "$here/TMP/tpcds_keys/*.tsldset" > /dev/null; then
  echo "note: $here/TMP/tpcds_keys holds keys of unrecorded scale factor;"
  echo "      ignoring them. Delete them once you no longer need them."
fi

keys_ready=no
if [[ -f "$manifest" ]] && compgen -G "$keys/*.tsldset" > /dev/null; then
  recorded="$(sed -n 's/^scale_factor=//p' "$manifest")"
  if [[ "$recorded" == "$scale" ]]; then
    keys_ready=yes
    echo "keys already extracted at scale factor $scale: \
$(ls "$keys"/*.tsldset | wc -l) files in $keys"
  else
    echo "$keys records scale factor $recorded, not $scale -- regenerating"
    rm -rf "$keys"
  fi
elif compgen -G "$keys/*.tsldset" > /dev/null; then
  echo "$keys holds keys with no manifest -- regenerating so the scale factor is"
  echo "  recorded rather than assumed"
  rm -rf "$keys"
fi

if [[ "$keys_ready" == "no" ]]; then
  if [[ ! -x "$gen/.dsb/code/tools/dsdgen" ]]; then
    echo "building DSB's dsdgen"
    (cd "$gen" && ./build_generator.sh)
  fi
  if [[ ! -d "$gen/.data/sf$scale" ]]; then
    echo "generating tables at scale factor $scale (this is the slow step)"
    (cd "$gen" && ./generate.sh "$scale")
  fi
  echo "extracting key columns"
  mkdir -p "$keys"
  (cd "$gen" && ./extract_keys.py --data ".data/sf$scale" \
      --schema .dsb/scripts/create_tables.sql --out "$keys" \
      --queries q067,q064,q010,q050,q081)
  # Written last, so an interrupted extraction leaves no manifest and the next run
  # regenerates rather than trusting a half-populated directory.
  {
    printf 'scale_factor=%s\n' "$scale"
    printf 'generated=%s\n' "$(date -Is)"
    printf 'host=%s\n' "$(hostname)"
    printf 'generator=%s\n' "DSB dsdgen, benchmarks/datagen/tpcds"
    for f in "$keys"/*.tsldset; do
      printf 'key=%s\n' "$(basename "$f")"
    done
  } > "$manifest"
  echo "wrote $manifest"
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
# else for that cell. Q0 runs ONCE, in full, and its single result decides both
# things: which cell the drivers are built for, and which configuration they use.
#
# It used to be a small probe here and a second full Q0 inside run_paper.sh. That
# was two runs that could disagree, with the cheaper one -- two shapes at 65,536
# rows, a working set inside L2 -- deciding the register width. It picked
# ClangBuiltin/128-bit once, a four-lane cell, on a 2% gap inside its own noise.
# One full run costs more than the probe did but replaces the second run entirely.
# --- topology: one thread per physical core, inside one NUMA node ---------------
# `nproc` on this class of machine counts SMT siblings across every node: a Xeon
# w5-3425 reports 24 for twelve physical cores spread over two NUMA nodes. Running
# a memory-bound co-sort across all 24 measures SMT pairs thrashing a shared L1 and
# gathers crossing a node boundary -- contention that has nothing to do with the
# sorter, and which is what made the parallel numbers degrade past four workers.
#
# So the measured machine is one node's physical cores: the first thread of each
# core on node 0, with memory bound to the same node. Enforced with numactl rather
# than requested politely, because the executors size themselves from the worker
# count they are given and would otherwise spread wherever the scheduler allows.
phys_cpus="$(lscpu -p=CPU,CORE,NODE | grep -v '^#' \
             | awk -F, '$3==0 { if (!($2 in seen)) { seen[$2]=1; printf "%s%s", sep, $1; sep="," } }')"
phys_count="$(awk -F, '{print NF}' <<< "$phys_cpus")"
if [[ -z "$phys_cpus" || "$phys_count" -lt 1 ]]; then
  echo "could not read the CPU topology; falling back to nproc" >&2
  phys_cpus=""
  phys_count="$(nproc)"
fi
pin=()
if [[ -n "$phys_cpus" ]] && command -v numactl > /dev/null; then
  pin=(numactl --physcpubind="$phys_cpus" --membind=0)
  echo "pinning to node 0 physical cores: $phys_cpus ($phys_count workers max)"
else
  echo "!! numactl is unavailable or the topology is unreadable: the run is NOT" >&2
  echo "   pinned, and its parallel numbers include SMT and cross-NUMA effects." >&2
  echo "   Install numactl (apt-get install numactl) before publishing." >&2
fi
# Every driver that takes a worker count gets this pair: serial, and one thread per
# physical core of the local node. Never the logical count.
export COSORT_WORKERS="1,$phys_count"
export COSORT_MAX_WORKERS="$phys_count"

cmake --build "$build" -j "$(nproc)" --target bench_q0_tune

mkdir -p "$results"
tuned="$results/best_config.tsv"
echo
# Extra flags for the tuner, word-split, for the knobs whose right value is a
# judgement about how much of the design space is worth the hours:
#
#   COSORT_Q0_ARGS="--cell-prune-factor 2.5"     keep more cells in the table
#   COSORT_Q0_ARGS="--cell-prune-factor 0"       measure every cell in full
#   COSORT_Q0_ARGS="--styles clang_bool"         one style, three cells not nine
#   COSORT_Q0_ARGS="--tie-margin 6"              a wider band counts as tied
#   COSORT_Q0_ARGS="--candidate-seconds 300"     an absolute per-candidate bound
#
# Several can be combined in the one string. Everything else about the run stays
# derived from the host.
read -r -a q0_extra <<< "${COSORT_Q0_ARGS:-}"
# --quick has to narrow the tuner too. When Q0 moved here from run_paper.sh its
# quick-mode narrowing was left behind, so `--quick` -- whose whole purpose is to
# prove the pipeline in minutes -- ran the full multi-hour tune and never reached the
# stages it was meant to be checking.
if [[ "$quick" == "--quick" ]]; then
  q0_quick=(--rows 262144 --shapes low_cardinality_d4,skewed_zipf_s1
            --styles "$(tr 'A-Z' 'a-z' <<< "${TSL_COSORT_MEASURE_STYLE:-ClangBoolMask}" \
                        | sed 's/clangboolmask/clang_bool/;s/clangbuiltin/clang/;s/intrinsics/intr/')"
            --widths 512)
else
  q0_quick=()
fi
echo "=== q0_tune (full: decides the cell and every configuration)"
if [[ ${#q0_extra[@]} -gt 0 ]]; then
  echo "    extra tuner flags: ${q0_extra[*]}"
fi
"${pin[@]}" "$build/bench_q0_tune" --workers "$COSORT_WORKERS" \
  "${q0_quick[@]+"${q0_quick[@]}"}" "${q0_extra[@]+"${q0_extra[@]}"}" \
  --out "$tuned" --csv "$results/q0_tune.csv" 2>&1 \
  | tee "$results/q0_tune.log"
probe="$(grep '^TSL_COSORT_BEST_CELL' "$results/q0_tune.log" | tail -1 || true)"
if [[ -n "$probe" ]]; then
  cell_style="$(awk '{print $2}' <<< "$probe")"
  cell_width="$(awk '{print $3}' <<< "$probe")"
  case "$cell_style" in
    intr) cell_style=Intrinsics ;;
    clang) cell_style=ClangBuiltin ;;
    clang_bool) cell_style=ClangBoolMask ;;
    *) echo "unrecognised style '$cell_style' from q0; keeping the default" >&2
       cell_style=""; cell_width="" ;;
  esac
  if [[ -n "$cell_style" ]]; then
    echo "building the reporting drivers for $cell_style/$cell_width-bit"
    cmake -S "$here" -B "$build" \
      -DTSL_COSORT_MEASURE_STYLE="$cell_style" \
      -DTSL_COSORT_MEASURE_WIDTH="$cell_width" > /dev/null
  fi
else
  echo "q0 named no cell; building for the default" >&2
fi

targets=(bench_q0_tune bench_q2_algorithms bench_q3_detection bench_q4_scaling
         cosort_bench)
[[ "$baselines" == "yes" ]] && targets+=(bench_q1_baselines)
cmake --build "$build" -j "$(nproc)" --target "${targets[@]}"

# --- 4. run -------------------------------------------------------------------
echo
echo "=== 4/4 run"
TPCDS_KEYS="$keys" "${pin[@]}" "$here/run_paper.sh" "$build" "$results" ${quick:+$quick}
