#!/usr/bin/env bash
# Produces every number the paper cites, with the method fixed in
# benchmarks/paper_harness.hpp and the questions listed in docs/benchmark-plan.md.
#
#   ./run_paper.sh --results DIR [--build DIR] [--cxx PATH] [--profile NAME]
#                  [--stages LIST] [--datasets DIR] [--quick] [--allow-busy]
#
# Self-contained: given only a results directory it configures a build tree from
# this checkout, builds it, measures every stage and writes the report. `--help`
# lists every flag, `--list-stages` every stage name. The older positional form
# `run_paper.sh <build-dir> <results-dir>` still works.
#
# One CSV per question, all sharing a schema, so a figure is a query over the
# results directory rather than a re-run. Refuses to write into a results
# directory that already holds another host's numbers: merging runs from
# different machines is the one mistake that cannot be spotted afterwards.
#
# The accelerator rows need a machine with the devices. Where they are absent the
# drivers emit the row with a reason rather than skipping it, so a run from the
# wrong host is visible in the CSV instead of looking like a backend that lost.
#
# What this refuses to do, each because it has silently produced wrong numbers:
#
#   * measure from a build whose fetched TSL is not the version it was configured
#     for -- FetchContent keeps whatever it downloaded first, and a stale tree can
#     be months behind the pin,
#   * measure from an instrumented build, or one that resolved the scalar profile,
#   * measure on a machine that is not idle -- load average above 1.0 or another
#     runnable task while sampling (--allow-busy overrides and says so in the
#     output), and
#   * measure before the correctness gate passes.
#
# Q3 is three stages rather than one, because its question has three parts: the
# grid (large effects, one pass), the worker ladder (how many cores the device
# replaces -- a crossing between two scaling curves) and the pressure sweep (4x
# and 16x the last level, because an offload's case is memory pressure). The two
# narrow ones repeat the whole binary several times and append: the effects there
# are a few percent, and re-running a driver moves its numbers by about a fifth,
# which no amount of resampling inside one process can see.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"

# Every stage this suite can run, in the order it runs them. `--stages` selects a
# subset by name; `--list-stages` prints them.
all_stages=(q0_tune q1_baselines q2_algorithms q3_detection q3_ladder q3_pressure
            q3_run_length q4_scaling q4_smt q5_variants q6_portability report)

usage() {
  cat <<'USAGE'
run_paper.sh -- produce every number the paper cites, from a checkout to a report.

  ./run_paper.sh --results DIR [options]
  ./run_paper.sh <build-dir> <results-dir> [--quick] [--allow-busy]    (older form)

Where the work happens:
  --results DIR      where the CSVs, logs and report go. Required.
  --build DIR        build tree to measure from. Configured and built if it does
                     not exist yet. Default: <results>/build.
  --source DIR       repository checkout to build. Default: this script's directory.

What to build with:
  --cxx PATH         C++ compiler.        Default: $CXX, else c++.
  --cc PATH          C compiler.          Default: $CC, else cc.
  --profile NAME     TSL profile.         Default: auto. A run whose profile
                     resolves to `scalar` is refused: every number would be a
                     scalar fallback whatever the style column says.
  --tsl-version TAG  Generated TSL release tag. Default: the pin in CMakeLists.txt.
  --baselines        Also build Q1's external baselines (needs network: ips4o,
                     x86-simd-sort, TBB).
  --jobs N           Build parallelism. Default: online CPUs minus two.
  --reconfigure      Delete and re-create the build tree first.

What to measure:
  --stages LIST      Comma-separated stage names, or `all`. Default: all.
                     `--list-stages` prints them.
  --scale N          TPC-DS/DSB scale factor: shorthand for
                     --datasets <source>/TMP/tpcds_keys/sfN. The keys have to be
                     extracted already -- run_all.sh --scale N does that.
  --datasets DIR     Directory of extracted TPC-DS/DSB keys (*.tsldset). Default:
                     $TPCDS_KEYS, else a search under <source>/TMP/tpcds_keys.
  --workers N        Worker count for the reporting drivers.
  --max-workers N    Upper bound on Q4's thread axis.
  --quick            Proof-of-pipeline sizes: fewer stages, smaller shapes. Not
                     publishable, and the narrow stages are skipped because a few
                     percent is not resolvable at those sizes anyway.
  --allow-busy       Measure anyway on a machine that is not idle, and say so.

  -h, --help         This text.

Everything above can also be set through the environment (COSORT_*); the flags
win. `--list-stages` and `--help` exit without touching anything.
USAGE
}

build=""
results=""
source_dir="$here"
cxx="${CXX:-}"
cc="${CC:-}"
profile="${TSL_PROFILE:-auto}"
tsl_version="${COSORT_TSL_VERSION_PIN:-}"
jobs=""
want_baselines="no"
reconfigure="no"
stages_requested="all"
datasets="${TPCDS_KEYS:-}"
scale=""
quick=""
allow_busy="no"
# Whether any build-time flag was passed *explicitly*. The defaults come from the
# environment, and a caller who has `CXX` exported has not asked for anything.
build_flags="no"
positional=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --results)      results="${2:?--results needs a directory}"; shift 2 ;;
    --build)        build="${2:?--build needs a directory}"; shift 2 ;;
    --source)       source_dir="${2:?--source needs a directory}"; shift 2 ;;
    --cxx)          cxx="${2:?--cxx needs a compiler}"; build_flags="yes"; shift 2 ;;
    --cc)           cc="${2:?--cc needs a compiler}"; build_flags="yes"; shift 2 ;;
    --profile)      profile="${2:?--profile needs a name}"; build_flags="yes"; shift 2 ;;
    --tsl-version)  tsl_version="${2:?--tsl-version needs a tag}"; build_flags="yes"; shift 2 ;;
    --jobs)         jobs="${2:?--jobs needs a count}"; shift 2 ;;
    --stages)       stages_requested="${2:?--stages needs a list}"; shift 2 ;;
    --datasets)     datasets="${2:?--datasets needs a directory}"; shift 2 ;;
    --scale)        scale="${2:?--scale needs a number}"; shift 2 ;;
    --workers)      COSORT_WORKERS="${2:?--workers needs a count}"; shift 2 ;;
    --max-workers)  COSORT_MAX_WORKERS="${2:?--max-workers needs a count}"; shift 2 ;;
    --baselines)    want_baselines="yes"; shift ;;
    --reconfigure)  reconfigure="yes"; shift ;;
    --quick)        quick="--quick"; shift ;;
    --allow-busy)   allow_busy="yes"; shift ;;
    --list-stages)  printf '%s\n' "${all_stages[@]}"; exit 0 ;;
    -h|--help)      usage; exit 0 ;;
    # Anything starting with a dash is a mistyped flag, never a path. This used
    # to test `--*`, so a single-dash `-cxx` fell through to the positional arm
    # and became the build directory -- which `--reconfigure` then handed to
    # `rm -rf`.
    -*)             echo "unknown argument: $1" >&2
                    case "$1" in
                      -[a-z]*[a-z])
                        echo "did you mean -$1?" >&2 ;;
                    esac
                    usage >&2; exit 2 ;;
    *)              positional+=("$1"); shift ;;
  esac
done

# The older positional form, kept because existing scripts and notes use it.
if [[ ${#positional[@]} -gt 0 ]]; then
  [[ -z "$build" ]]   && build="${positional[0]}"
  [[ ${#positional[@]} -gt 1 && -z "$results" ]] && results="${positional[1]}"
  if [[ ${#positional[@]} -gt 2 ]]; then
    echo "too many positional arguments: ${positional[*]}" >&2
    exit 2
  fi
fi

if [[ -z "$results" ]]; then
  echo "no results directory: pass --results DIR" >&2
  usage >&2
  exit 2
fi

# A compiler that is not there should say so now, not as a CMake error twelve
# seconds into a configure. Only a named one is checked: an empty value means
# "whatever CMake picks", which is CMake's business.
for named in "cxx:$cxx" "cc:$cc"; do
  flag="${named%%:*}"
  path="${named#*:}"
  [[ -z "$path" ]] && continue
  # A value may carry arguments -- `CXX="zig c++"` is a real thing -- so only the
  # first word is the program, and a bare name is looked up on PATH.
  program="${path%% *}"
  if [[ "$program" == */* ]]; then
    [[ -x "$program" ]] && continue
  else
    command -v "$program" >/dev/null 2>&1 && continue
  fi
  echo "--$flag: no such compiler: $program" >&2
  if [[ "$program" == */* ]]; then
    similar="$(ls "$(dirname "$program")" 2>/dev/null \
               | grep -E "^$(basename "${program%%-*}")(\+\+)?(-[0-9]+)?$" \
               | sort | tr '\n' ' ')"
    [[ -n "$similar" ]] && echo "  this host has: $similar" >&2
  fi
  exit 2
done
# Absolute from here on. Several steps run the drivers from inside the build
# directory -- `(cd "$build" && ./bench_q2_algorithms --csv "$results/...")` -- so a
# relative results path put the CSVs in the build tree while `tee` wrote the logs
# where the caller asked, splitting a results directory in half without saying so.
mkdir -p "$results"
results="$(cd "$results" && pwd)"
source_dir="$(cd "$source_dir" && pwd)"
[[ -z "$build" ]] && build="$results/build"

# `--scale N` names the key set the way run_all.sh does. It selects, it does not
# generate: extraction needs the DSB generator and is run_all.sh's step 2. A scale
# that was never extracted is an error rather than a silent fall back to whichever
# one happens to be on disk -- measuring scale 1 while the log says 10 is the worst
# kind of wrong, because every row looks fine.
if [[ -n "$scale" ]]; then
  if [[ ! "$scale" =~ ^[0-9]+$ ]]; then
    echo "--scale takes a number, not '$scale'" >&2
    exit 2
  fi
  if [[ -n "$datasets" ]]; then
    echo "--scale and --datasets both given; --datasets wins" >&2
  else
    datasets="$source_dir/TMP/tpcds_keys/sf$scale"
    if [[ ! -d "$datasets" ]] || ! compgen -G "$datasets/*.tsldset" > /dev/null; then
      echo "--scale $scale: no extracted keys in $datasets" >&2
      available="$(for candidate in "$source_dir"/TMP/tpcds_keys/sf*; do
                     [[ -d "$candidate" ]] \
                       && compgen -G "$candidate/*.tsldset" > /dev/null \
                       && basename "$candidate"
                   done | tr '\n' ' ' || true)"
      if [[ -n "${available// /}" ]]; then
        echo "  extracted here: $available" >&2
      else
        echo "  none are extracted. Produce them with:" >&2
        echo "    ./run_all.sh --scale $scale" >&2
        echo "  or measure synthetic shapes only by omitting --scale." >&2
      fi
      exit 2
    fi
  fi
fi
# Absolute, for the same reason `results` is: the drivers are invoked as
# `(cd "$build" && ./bench_q2_algorithms --tpcds-dir "$dir")`, so a relative path
# resolves against the build tree instead of the caller's directory. It would not
# error -- `--tpcds-dir` that finds no *.tsldset means "measure synthetic shapes
# only", and the run says so in a line nobody reads until afterwards. So a path
# that was given and cannot be resolved is refused here instead.
if [[ -n "$datasets" ]]; then
  if [[ ! -d "$datasets" ]]; then
    echo "--datasets: no such directory: $datasets" >&2
    exit 2
  fi
  datasets="$(cd "$datasets" && pwd)"
  if ! compgen -G "$datasets/*.tsldset" > /dev/null; then
    echo "--datasets: $datasets holds no *.tsldset key columns" >&2
    echo "  extract them with ./run_all.sh --scale N, or omit --datasets to" >&2
    echo "  measure synthetic shapes only." >&2
    exit 2
  fi
  export TPCDS_KEYS="$datasets"
fi

# Which stages to run. Named rather than positional so a re-run of one question
# does not depend on counting, and validated here so a typo fails before the
# machine is tied up for six hours rather than after.
declare -A run_stage=()
if [[ "$stages_requested" == "all" ]]; then
  for stage in "${all_stages[@]}"; do run_stage[$stage]=1; done
else
  IFS=',' read -r -a wanted <<< "$stages_requested"
  for stage in "${wanted[@]}"; do
    known="no"
    for candidate in "${all_stages[@]}"; do
      [[ "$stage" == "$candidate" ]] && known="yes"
    done
    if [[ "$known" != "yes" ]]; then
      echo "unknown stage: $stage" >&2
      echo "known stages: ${all_stages[*]}" >&2
      exit 2
    fi
    run_stage[$stage]=1
  done
fi
# `report` and `q0_tune` are not optional in the way the others are: every
# reporting driver reads best_config.tsv, so asking for q2 alone still needs the
# tuner's answer -- reused from the results directory when it is already there.
want() { [[ -n "${run_stage[$1]:-}" ]]; }

# ---------------------------------------------------------------------------
# The build tree
# ---------------------------------------------------------------------------
# Configured here rather than assumed, so a fresh checkout on a new machine is one
# command. An existing tree is reused as it stands -- reconfiguring one that is
# mid-build is how a directory came out resolved to the scalar profile once, with
# no symptom but an unrelated compile error.
if [[ "$reconfigure" == "yes" ]]; then
  # `rm -rf` on a path that came from the command line, so it is checked first.
  # A mistyped flag reaching this line is not hypothetical: `-cxx` did, before
  # the parser above learned that a leading dash is always a flag.
  if [[ -e "$build" ]]; then
    if [[ ! -f "$build/CMakeCache.txt" ]]; then
      echo "refusing to remove $build: it is not a CMake build tree." >&2
      echo "  --reconfigure deletes the build directory, so it only ever deletes" >&2
      echo "  one this script could have made. Remove it by hand if you meant it." >&2
      exit 2
    fi
    if [[ "$build" -ef "$source_dir" || "$build" -ef "$results" ]]; then
      echo "refusing to remove $build: it is the source or results directory." >&2
      exit 2
    fi
    echo "removing $build to configure it again"
    rm -rf -- "$build"
  fi
fi

if [[ ! -f "$build/CMakeCache.txt" ]]; then
  echo
  echo "=== configuring $build"
  configure=(cmake -S "$source_dir" -B "$build"
             -DCMAKE_BUILD_TYPE=Release
             -DTSL_PROFILE="$profile"
             -DTSL_COSORT_ENABLE_DSA=ON
             -DTSL_COSORT_NO_INSTRUMENTATION=ON)
  [[ -n "$cxx" ]] && configure+=(-DCMAKE_CXX_COMPILER="$cxx")
  [[ -n "$cc" ]]  && configure+=(-DCMAKE_C_COMPILER="$cc")
  [[ -n "$tsl_version" ]] && configure+=(-DTSL_RELEASE_VERSION="$tsl_version")
  [[ "$want_baselines" == "yes" ]] && configure+=(-DTSL_COSORT_ENABLE_BASELINES=ON)
  if ! "${configure[@]}" 2>&1 | tee "$results/configure.log" | tail -5; then
    echo "configure failed; the whole log is in $results/configure.log" >&2
    grep -m1 -A 4 "CMake Error" "$results/configure.log" >&2 || true
    exit 1
  fi
  # `TSL_PROFILE=auto` probes the host by compiling *and running* a snippet per
  # ISA. Where that cannot run -- a container without permission to execute a
  # freshly built binary, a cross build -- every probe fails and the profile
  # silently resolves to `scalar`. Nothing downstream complains: the intrinsics
  # style still compiles, the drivers still run, and every number is a scalar
  # fallback. Caught here, where the log still says which it picked.
  if grep -q "TSL auto-detected profile = scalar" "$results/configure.log" \
     && [[ "$profile" == "auto" ]]; then
    echo "refusing to build: TSL_PROFILE=auto resolved to the scalar profile." >&2
    echo "  Every number from this tree would be a scalar fallback whatever the" >&2
    echo "  style column says. The probe compiles and *runs* a snippet per ISA, so" >&2
    echo "  it fails wholesale where running a fresh binary is not permitted." >&2
    echo "  Name the profile instead, e.g." >&2
    echo "    $0 --profile sapphire_emerald_granite_rapids --results $results" >&2
    echo "  (cmake -LH $build | grep TSL_PROFILE lists what this release carries)" >&2
    exit 1
  fi
else
  echo "=== reusing the build tree in $build"
  if [[ "$build_flags" == "yes" ]]; then
    echo "    (--cxx/--cc/--profile/--tsl-version apply at configure time only;" >&2
    echo "     pass --reconfigure to apply them to this tree)" >&2
  fi
fi

: "${jobs:=$(( $(nproc) > 2 ? $(nproc) - 2 : 1 ))}"
echo "=== building (-j $jobs)"
if ! cmake --build "$build" -j "$jobs" 2>&1 | tee "$results/build.log" | tail -3; then
  echo "build failed; the whole log is in $results/build.log" >&2
  grep -m3 -i "error:" "$results/build.log" >&2 || true
  exit 1
fi

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

# The generated TSL this build actually compiled against, checked against the
# version it was configured to want. FetchContent does not re-download into an
# existing source directory, so a build tree configured months ago keeps whatever
# release it fetched then, silently, while CMakeLists.txt says something else.
# That is not a hypothetical: a tree holding v0.2.5 against a v0.3.0 pin failed to
# compile the bitonic leaf for want of `tsl::select`, and the missing primitive
# looked like a source bug for hours.
# The pin comes from CMakeLists.txt, not from the build's own cache: a tree
# configured while the pin was older holds that older value in its cache too, so
# cache-against-fetched is consistent on exactly the tree that is wrong.
pinned_tsl="$(sed -n 's/^set(TSL_RELEASE_VERSION "\([^"]*\)".*/\1/p' "$source_dir/CMakeLists.txt" 2>/dev/null | head -1 || true)"
fetched_tsl="$(ls "$build"/_deps/tsl-subbuild/tsl-populate-prefix/src/tsl-generated-*.tar.gz                2>/dev/null | head -1 || true)"
if [[ -n "$pinned_tsl" && -n "$fetched_tsl" ]]; then
  fetched_tsl="$(basename "$fetched_tsl" .tar.gz)"
  fetched_tsl="${fetched_tsl#tsl-generated-}"
  if [[ "$fetched_tsl" != "$pinned_tsl" ]]; then
    if [[ "${COSORT_TSL_VERSION:-}" == "$fetched_tsl" ]]; then
      echo "generated TSL: $fetched_tsl (pin says $pinned_tsl; allowed by COSORT_TSL_VERSION)"
    else
      echo "refusing to measure: $build compiled against generated TSL $fetched_tsl," >&2
      echo "  but CMakeLists.txt pins $pinned_tsl. FetchContent does not replace an" >&2
      echo "  existing _deps source tree, so a build directory configured before the" >&2
      echo "  pin moved keeps the old release -- and its own cache records the old" >&2
      echo "  version too, so nothing looks inconsistent from inside it. The" >&2
      echo "  directory has to go:" >&2
      echo "    $0 --results $results --build $build --reconfigure" >&2
      echo "  To measure an older release deliberately:" >&2
      echo "    COSORT_TSL_VERSION=$fetched_tsl ./run_paper.sh ..." >&2
      exit 1
    fi
  fi
  echo "generated TSL: $fetched_tsl (matches the pin)"
fi

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
# Both forms of each device, because they answer different questions. The
# synchronous row prices an offload that a worker waits on; the asynchronous one
# prices the only form in which the device can overlap the sort, and it is the one
# a "does offloading pay" claim rests on. It became measurable when the
# samplesort's worklist took on the pending-work contract; before that every
# asynchronous row was a drop reading "this driver never polls".
q3_detectors="scalar"
[[ "$have_dsa" == "yes" ]] && q3_detectors="$q3_detectors,dsa_hw,dsa_hw_async"
[[ "$have_iax" == "yes" ]] && q3_detectors="$q3_detectors,iaa_hw,iaa_hw_async,iaa_freq_hw"
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

# A busy machine is refused rather than warned about. Every driver already prints
# "these numbers are not publishable" when it starts above 1.0, and every results
# directory in this repository carries that line -- which is to say the warning
# does not work. The differences being resolved here are a few percent and the
# inter-process spread on a contended host is twenty.
#
# What this gate can and cannot do, because it is easy to over-read:
#
#   * It is a screen at the door, not a guard for the run. A six-hour suite that
#     starts on an idle host and is joined at minute forty by a colleague's build
#     passes this check and is contended anyway.
#   * The load average is a one-minute exponential average, so it lags: a job that
#     started ten seconds ago barely shows, and one that ended a minute ago still
#     does. `procs_running` from /proc/stat is the instantaneous count of runnable
#     tasks, so both are sampled -- the average for what has been happening, the
#     runnable count for what is happening now.
#   * Neither can stop the kernel putting something on these cores mid-run.
#     Nothing in userspace can. What closes that gap is on two other levels:
#     `paper_harness.hpp` counts involuntary context switches around every timed
#     pass and marks the row (`preempted_passes`), and a cpuset makes the cores
#     exclusive so there is nothing to be preempted by. The recipe is printed
#     below when this host is not already isolated.
load_now="$(cut -d' ' -f1 /proc/loadavg)"
load_cap="${COSORT_LOAD_CAP:-1.0}"

# The runnable count, sampled rather than read once: a single read of
# `procs_running` catches this shell and whatever happened to be on a CPU that
# instant, so the useful statistic is the maximum over a couple of seconds.
runnable_max=0
for _ in 1 2 3 4 5 6; do
  running="$(awk '/^procs_running/{print $2}' /proc/stat)"
  if (( running > runnable_max )); then runnable_max=$running; fi
  sleep 0.3
done
# One runnable task is this script. Anything above that is somebody else.
runnable_others=$(( runnable_max > 0 ? runnable_max - 1 : 0 ))
runnable_cap="${COSORT_RUNNABLE_CAP:-1}"

busy_reason=""
if awk -v l="$load_now" -v c="$load_cap" 'BEGIN{exit !(l > c)}'; then
  busy_reason="load average is $load_now, above $load_cap"
fi
if (( runnable_others > runnable_cap )); then
  extra="$runnable_others other runnable task(s) while sampling, above $runnable_cap"
  busy_reason="${busy_reason:+$busy_reason; }$extra"
fi
if [[ -n "$busy_reason" ]]; then
  if [[ "$allow_busy" == "yes" ]]; then
    echo
    echo "!! $busy_reason, and --allow-busy was given:" >&2
    echo "   this directory will not be publishable" >&2
  else
    echo "refusing to measure: $busy_reason" >&2
    echo "  something else is using the cores being measured. Wait for it, or pass" >&2
    echo "  --allow-busy to produce a working (not publishable) directory, or raise" >&2
    echo "  the bar with COSORT_LOAD_CAP / COSORT_RUNNABLE_CAP." >&2
    exit 1
  fi
fi

# Whether the OS can put anything else on these cores at all. `isolcpus` or an
# exclusive cpuset is the only thing that answers "what if some process gets
# scheduled on the same CPU" with "it cannot"; without one, the harness can only
# notice afterwards.
isolated="$(cat /sys/devices/system/cpu/isolated 2>/dev/null || true)"
if [[ -z "${isolated//[[:space:]]/}" ]]; then
  echo
  echo "note: no isolated CPUs on this host, so the scheduler may place other work" >&2
  echo "  on the cores this run measures. The harness records that per row" >&2
  echo "  (preempted_passes) but cannot prevent it." >&2
  echo "" >&2
  echo "  numactl and an exclusive cpuset answer different questions, and a" >&2
  echo "  publishable run wants both:" >&2
  echo "    numactl  decides where THIS process runs and allocates -- one NUMA" >&2
  echo "             node's cores, that node's memory. It is what keeps the" >&2
  echo "             parallel numbers about the sort instead of about cross-node" >&2
  echo "             latency, and it is already how every figure here is taken." >&2
  echo "    a cpuset decides who ELSE may run there. numactl cannot do this: it" >&2
  echo "             restricts this process, not the scheduler's freedom to put" >&2
  echo "             somebody else on the same cores." >&2
  echo "" >&2
  echo "  What actually excludes other work, strongest first:" >&2
  echo "    isolcpus=<list> nohz_full=<list> rcu_nocbs=<list> at boot -- the" >&2
  echo "      kernel keeps those CPUs out of the general scheduling domains, so" >&2
  echo "      nothing lands there unless it asks by affinity. Needs a reboot." >&2
  echo "    sudo cset shield --cpu=0-5 --kthread=on -- moves every movable task," >&2
  echo "      kernel threads included, into a system cpuset off those cores. No" >&2
  echo "      reboot; needs root and the cpuset package." >&2
  echo "    cgroup v2 with cpuset.cpus.partition=isolated on the run's cgroup --" >&2
  echo "      the same idea without cset. Note that AllowedCPUs / cpuset.cpus" >&2
  echo "      ALONE does not do this: it confines this run to those CPUs the way" >&2
  echo "      taskset does, and leaves every other cgroup free to use them. The" >&2
  echo "      partition file is what makes them exclusive." >&2
  echo "" >&2
  echo "  Then run under numactl inside it, e.g." >&2
  echo "    sudo cset shield --exec -- numactl --cpunodebind=0 --membind=0 \\" >&2
  echo "      $0 --results $results" >&2
  echo "" >&2
  echo "  Without any of them, run under numactl anyway and read preempted_passes" >&2
  echo "  afterwards: counting what the kernel took away is all a userspace" >&2
  echo "  program can do about it." >&2
fi

# Elapsed per stage and since the start, printed either side of each driver. A
# full run is six to eight hours; without this the only way to tell a slow stage
# from a hung one is to watch the row count by hand.
suite_started=$SECONDS
stage_index=0
# Eight stages: q1, q2, the three q3 stages, q4, and the two corpus stages.
# --quick skips the two narrow q3 stages, whose whole point is resolving a few
# percent -- which a proof-of-pipeline run cannot do anyway.
# How many stages this invocation will actually run, so the "[3/7]" headers mean
# something after `--stages` narrows the set. `--quick` drops the three narrow Q3
# stages and the SMT stage: they resolve a few percent, which proof-of-pipeline
# sizes cannot do anyway.
stage_total=0
for stage in "${all_stages[@]}"; do
  want "$stage" || continue
  case "$stage" in
    report) continue ;;                    # not a measurement
    q0_tune) continue ;;                   # printed separately, before the count
    q3_ladder|q3_pressure|q3_run_length|q4_smt)
      [[ "$quick" == "--quick" ]] && continue ;;
  esac
  stage_total=$(( stage_total + 1 ))
done

elapsed_text() {  # seconds
  local s=$1
  if (( s >= 3600 )); then printf '%dh%02dm' $(( s / 3600 )) $(( (s % 3600) / 60 ))
  elif (( s >= 60 )); then printf '%dm%02ds' $(( s / 60 )) $(( s % 60 ))
  else printf '%ds' "$s"; fi
}

# Some questions here turn on a few percent, and the harness's own resampling
# only sees the spread *inside* one process: re-running the binary moves the same
# numbers by about a fifth. So the stages that ask fine questions are run several
# times and their rows appended into one CSV, which is exactly what the analysis
# wants -- `findings.py` medians the rows per cell, and the row count per cell is
# how many whole-process passes produced it.
run_repeated() {  # passes, binary, csv name, args...
  local passes="$1"; shift
  local binary="$1"; shift
  local name="$1"; shift
  stage_index=$(( stage_index + 1 ))
  if [[ ! -x "$build/$binary" ]]; then
    echo "skipping $name: $build/$binary is not built"
    return
  fi
  local began=$SECONDS
  echo
  echo "=== [$stage_index/$stage_total] $name  x$passes passes  (started \
$(date +%H:%M:%S), $(elapsed_text $(( began - suite_started ))) into the run)"
  rm -f "$results/$name.csv" "$results/$name.log" \
        "$results/${name}_detector_counters.csv"
  local pass
  for (( pass = 1; pass <= passes; pass++ )); do
    local scratch="$results/.$name.pass$pass.csv"
    echo "--- pass $pass of $passes" | tee -a "$results/$name.log"
    (cd "$build" && "./$binary" "$@" --csv "$scratch" 2>&1) \
      | tee -a "$results/$name.log"
    # First pass keeps the header; the rest append their rows to it. The schema is
    # identical by construction -- same binary, same flags -- so this is a longer
    # table rather than a merged one.
    for part in "$scratch" "${scratch%.csv}_detector_counters.csv"; do
      [[ -s "$part" ]] || continue
      local target="$results/$name.csv"
      [[ "$part" == *_detector_counters.csv ]] \
        && target="$results/${name}_detector_counters.csv"
      if [[ -s "$target" ]]; then
        tail -n +2 "$part" >> "$target"
      else
        cat "$part" > "$target"
      fi
      rm -f "$part"
    done
  done
  local took=$(( SECONDS - began ))
  echo "--- $name finished in $(elapsed_text $took); \
$(elapsed_text $(( SECONDS - suite_started ))) total so far"
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
  # Two worker counts rather than one, so the iso-resource pairing is actually
  # exercised: at one worker there is no core to take away and the flag is inert.
  narrow_q3=(--cardinalities 1024 --cols 4 --widths 4 --workers 1,2 --rows 1048576)
  narrow_q4=(--axis threads --shapes skewed_zipf_s1 --widths 4 --rows 1048576)
  # The corpus stages need narrowing too: `attribute` alone is 186 registrations
  # across three styles and three widths, which is minutes even at one shape.
  export COSORT_SHAPES=low_cardinality_d4
  export COSORT_SIZE_LEVELS=1
  export COSORT_COLUMNS=3
  export COSORT_SCREEN_REPETITIONS="${COSORT_SCREEN_REPETITIONS:-3}"
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
  keys_root="$source_dir/TMP/tpcds_keys"
  mapfile -t key_sets < <(
    for candidate in "$keys_root"/sf*; do
      [[ -d "$candidate" ]] && compgen -G "$candidate/*.tsldset" > /dev/null \
        && basename "$candidate"
    done)
  if [[ ${#key_sets[@]} -eq 1 ]]; then
    tpcds_dir="$keys_root/${key_sets[0]}"
  elif [[ ${#key_sets[@]} -gt 1 ]]; then
    inferred="$(python3 "$source_dir/benchmarks/visualization/infer_key_scale.py" \
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
    tpcds_dir="$source_dir/data/tpcds"
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
elif want q0_tune && [[ -x "$build/bench_q0_tune" ]]; then
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
if want q1_baselines; then
  if [[ -x "$build/bench_q1_baselines" ]]; then
    run bench_q1_baselines q1_baselines --tuned "$tuned" \
        ${COSORT_WORKERS:+--workers "$COSORT_WORKERS"} \
        "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q1[@]+"${narrow_q1[@]}"}"
  else
    echo
    echo "=== q1_baselines: not built; pass --baselines (needs network) to include it"
    stage_total=$(( stage_total - 1 ))
  fi
fi

if want q2_algorithms; then
  run bench_q2_algorithms q2_algorithms --tuned "$tuned" \
      "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q2[@]+"${narrow_q2[@]}"}"
fi
# Hardware only, and only this host's hardware: the software paths are QPL's and
# DML's own CPU code, kept for correctness rather than for figures.
#
# Three Q3 stages, because the question has three parts and they need different
# amounts of machine time.
#
# 1. `q3_detection` -- the grid. Cardinality x columns x key width x workers x
#    detector, one pass. This is where a large effect shows up: a backend that
#    regresses several-fold, or a device that cannot engage at all. Its rows now
#    carry the phase split, so detection's *share* of the sort is readable from
#    them -- it was structurally zero in every earlier directory, because the
#    switch that compiles the counters out also nulled the pointer the phase
#    timers are written through.
#    `--iso-resource` adds, for every offloading backend, a run with one worker
#    fewer than the scalar scan it is compared against: the usual argument for an
#    offload is that it frees a core, and an equal-worker comparison never charges
#    it for one.
if want q3_detection; then
  run bench_q3_detection  q3_detection  --tuned "$tuned" --iso-resource \
                                        --detectors "$q3_detectors" \
      ${COSORT_WORKERS:+--workers "$COSORT_WORKERS"} \
      "${narrow_q3[@]+"${narrow_q3[@]}"}"
fi

if [[ "$quick" != "--quick" ]]; then
 if want q3_ladder; then
  # 2. `q3_ladder` -- both scaling curves, every worker count from one to the
  #    physical cores of one node, on one cell. "How many cores does the device
  #    replace" is a crossing between the scalar curve at full width and the
  #    offloaded curve, so it needs the curves rather than two points;
  #    `findings.py::cores_freed` reads it off these rows. Narrow on purpose: the
  #    ladder multiplies the grid by the core count, and the effect it resolves is
  #    a few percent, which is what the repeated passes are for.
  run_repeated "${COSORT_Q3_LADDER_PASSES:-3}" bench_q3_detection q3_ladder \
      --tuned "$tuned" --detectors "$q3_detectors" --workers ladder \
      --cardinalities "${COSORT_Q3_LADDER_CARDINALITY:-16}" \
      --cols "${COSORT_Q3_LADDER_COLS:-8}" --element-bytes 4 \
      --sizes "${COSORT_Q3_LADDER_SIZES:-4}"
 fi

 if want q3_pressure; then
  # 3. `q3_pressure` -- the same cell at four and sixteen times the last level.
  #    An offload's case is that it moves memory without spending core cycles or
  #    polluting cache, and a working set that still half-fits cannot show it: on
  #    this class of machine the asynchronous penalty fell from 1.7x to 1.05x
  #    between those two sizes. Multiples of the probed cache, so the axis means
  #    the same thing on the next host.
  #    Two sweeps, because "bigger footprint" and "longer runs" are different
  #    claims and a fixed cardinality moves both: four times the rows at c=1024
  #    also makes every equal run four times longer, so a win cannot be attributed.
  #    The first sweep holds the cardinality and lets both move (the confounded
  #    one, kept because it is the regime the other questions report); the second
  #    holds rows/c fixed, so only the footprint changes.
  run_repeated "${COSORT_Q3_PRESSURE_PASSES:-2}" bench_q3_detection q3_pressure \
      --tuned "$tuned" --detectors "$q3_detectors" \
      --cardinalities "${COSORT_Q3_PRESSURE_CARDINALITY:-1024}" --cols 8 \
      --element-bytes 4 --sizes "${COSORT_Q3_SIZES:-4,16}"
 fi

 if want q3_run_length; then
  run_repeated "${COSORT_Q3_PRESSURE_PASSES:-2}" bench_q3_detection q3_run_length \
      --tuned "$tuned" --detectors "$q3_detectors" --cols 8 --element-bytes 4 \
      --sizes "${COSORT_Q3_SIZES:-4,16}" \
      --run-length "${COSORT_Q3_RUN_LENGTH:-8192}"
 fi
fi

# The SMT question, which nothing in this suite asked before.
#
# Every parallel figure here pins one thread per *physical* core of one NUMA node,
# for a good reason: a memory-bound co-sort run across SMT siblings has them
# evicting each other's lines, and a sweep that wandered onto siblings once
# produced a "the quicksort does not scale" finding that had to be withdrawn. But
# "avoid SMT so the thread axis is clean" is not the same claim as "SMT does not
# help", and the paper is about exploiting the hardware. So: the same physical
# cores, once with one thread each and once with both siblings, and the comparison
# is between the two ends.
#
# The masks come from the topology rather than from a literal, because which
# logical CPU is which core's sibling is a per-machine fact.
node0_cpus="$(cat /sys/devices/system/node/node0/cpulist 2>/dev/null || echo '')"
physical_mask=""
sibling_mask=""
if [[ -n "$node0_cpus" ]]; then
  declare -A seen_core=()
  first_of_core=()
  second_of_core=()
  for cpu in $(python3 -c "
import sys
spec = sys.argv[1]
out = []
for part in spec.split(','):
    if '-' in part:
        lo, hi = part.split('-')
        out += list(range(int(lo), int(hi) + 1))
    elif part:
        out.append(int(part))
print(' '.join(map(str, out)))" "$node0_cpus"); do
    siblings="$(cat "/sys/devices/system/cpu/cpu$cpu/topology/thread_siblings_list" \
                2>/dev/null || echo "$cpu")"
    if [[ -z "${seen_core[$siblings]:-}" ]]; then
      seen_core[$siblings]=$cpu
      first_of_core+=("$cpu")
    else
      second_of_core+=("$cpu")
    fi
  done
  physical_mask="$(IFS=,; echo "${first_of_core[*]}")"
  if [[ ${#second_of_core[@]} -gt 0 ]]; then
    sibling_mask="$physical_mask,$(IFS=,; echo "${second_of_core[*]}")"
  fi
fi
if [[ -n "$sibling_mask" && "$quick" != "--quick" ]]; then
  echo
  echo "SMT: ${#first_of_core[@]} physical cores on node 0 (mask $physical_mask),"
  echo "     ${#second_of_core[@]} siblings (mask $sibling_mask)"
fi

# Q4 gets the tuned configuration and the measured keys: its thread axis is where
# the algorithm crossover is visible, and it is only visible on real keys -- the
# synthetic shapes are won by the quicksort at every thread count.
if want q4_scaling; then
  run bench_q4_scaling    q4_scaling    --tuned "$tuned" \
      ${COSORT_MAX_WORKERS:+--max-workers "$COSORT_MAX_WORKERS"} \
      "${tpcds_args[@]+"${tpcds_args[@]}"}" "${narrow_q4[@]+"${narrow_q4[@]}"}"
fi

# One thread per physical core against two threads per physical core, on the same
# cores. `pinned_cpus` in the CSV records which mask each row ran under, so the
# two are distinguishable afterwards without trusting a filename.
if want q4_smt && [[ -n "$sibling_mask" && "$quick" != "--quick" \
      && -x "$build/bench_q4_scaling" ]]; then
  smt_workers=$(( ${#first_of_core[@]} + ${#second_of_core[@]} ))
  stage_index=$(( stage_index + 1 ))
  smt_began=$SECONDS
  echo
  echo "=== [$stage_index/$stage_total] q4_smt (up to $smt_workers threads on \
${#first_of_core[@]} cores)"
  (cd "$build" && taskset -c "$sibling_mask" ./bench_q4_scaling --tuned "$tuned" \
      --axis threads --max-workers "$smt_workers" \
      "${tpcds_args[@]+"${tpcds_args[@]}"}" \
      --csv "$results/q4_smt.csv" 2>&1) | tee "$results/q4_smt.log"
  echo "--- q4_smt finished in $(elapsed_text $(( SECONDS - smt_began )))"
fi

# Q5 and Q6 are stages of the existing staged driver rather than new binaries: a
# bench_q5_*.cpp would have to re-implement its registration, its variant
# enumeration and its drop accounting to produce numbers it already produces.
#
# What changed is how those cases are *measured*. `--paper-csv` runs them through
# paper_harness.hpp -- verify then time, median of at least nine with quartiles,
# resampled while the spread stays above 5%, machine state on every row, drops
# carrying their reason -- and writes the shared schema directly. Before this they
# went through Google Benchmark and a JSON conversion that could not recover the
# fields the schema wanted: `verified` was hardcoded to 1, there were no
# quartiles, and the repetition count was whatever the flag said rather than what
# the spread needed. Two of the seven questions were held to a different method
# than the other five, and the corpus's CSVs carried a `size_level` column the
# others did not.
#
# COSORT_GBENCH=1 runs the old path instead, for comparing the two on one machine.
if [[ -x "$build/cosort_bench" ]]; then
  export COSORT_RLE="${COSORT_RLE-scalar}"
  screen_filter="${COSORT_SCREEN_FILTER-}"
  attribute_filter="${COSORT_ATTRIBUTE_FILTER-}"
  for stage in "screen:q5_variants:$screen_filter" \
               "attribute:q6_portability:$attribute_filter"; do
    IFS=':' read -r stage_name name stage_filter <<< "$stage"
    want "$name" || continue
    stage_index=$(( stage_index + 1 ))
    corpus_began=$SECONDS
    echo
    echo "=== [$stage_index/$stage_total] $name (cosort_bench, $stage_name stage) \
$(elapsed_text $(( corpus_began - suite_started ))) into the run"
    if [[ "${COSORT_GBENCH:-0}" == "1" ]]; then
      export COSORT_MIN_TIME="${COSORT_MIN_TIME:-0.2s}"
      reps="${COSORT_SCREEN_REPETITIONS:-9}"
      [[ "$stage_name" == "attribute" ]] && reps="${COSORT_ATTRIBUTE_REPETITIONS:-9}"
      if (cd "$build" && COSORT_STAGE="$stage_name" \
            ${TSL_COSORT_STDBUF:-stdbuf -oL -eL} ./cosort_bench \
            --benchmark_repetitions="$reps" \
            --benchmark_report_aggregates_only=true \
            --benchmark_min_time="$COSORT_MIN_TIME" \
            ${stage_filter:+--benchmark_filter="$stage_filter"} \
            --benchmark_format=console --benchmark_out_format=json \
            --benchmark_out="$results/$name.json") \
          > "$results/$name.log" 2>&1; then
        python3 "$(dirname "$0")/benchmarks/visualization/gbench_to_paper.py" \
          "$results/$name.json" "$results/$name.csv" --question "$name" \
          || echo "  conversion failed"
      else
        echo "  cosort_bench $stage_name failed, see $results/$name.log"
      fi
    elif ! (cd "$build" && COSORT_STAGE="$stage_name" \
              ${TSL_COSORT_STDBUF:-stdbuf -oL -eL} ./cosort_bench \
              --paper-csv "$results/$name.csv" --question "$name") \
            > "$results/$name.log" 2>&1; then
      echo "  cosort_bench $stage_name failed, see $results/$name.log"
    fi
    echo "--- $name finished in $(elapsed_text $(( SECONDS - corpus_began )))"
  done
fi

# Answer the questions, not just measure them. Both steps read the directory that
# was just written and need nothing but pandas, so a run ends with its own
# findings rather than with a pile of CSVs and a note about how to read them. Not
# fatal: a missing dependency should not fail a seven-hour measurement.
analysis="$source_dir/benchmarks/visualization"
if want report && python3 -c 'import pandas' 2>/dev/null; then
  echo
  echo "=== findings"
  if python3 "$analysis/findings.py" --results "$results" \
       > "$results/findings.txt" 2>&1; then
    sed -n '1,12p' "$results/findings.txt"
    echo "  ... full text in $results/findings.txt"
  else
    echo "  findings.py failed; see $results/findings.txt"
  fi
  if python3 "$analysis/report.py" --results "$results" \
       --out "$results/report.html" >/dev/null 2>&1; then
    echo "  wrote $results/report.html (one page, opens offline)"
  else
    echo "  report.py failed"
  fi
else
  echo
  echo "no pandas: skipping the findings and the report. Produce them later with"
  echo "  python3 $analysis/findings.py --results $results"
fi

# Did anything land on these cores while the suite ran? The per-row counters can
# answer that, and a reader should not have to open a CSV to find out.
python3 - "$results" <<'CONTENTION' || true
import csv, glob, os, sys

results = sys.argv[1]
worst = []
for path in sorted(glob.glob(os.path.join(results, "*.csv"))):
    contended = total = 0
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            passes = row.get("preempted_passes") or ""
            reps = row.get("repetitions") or ""
            if not passes.strip() or not reps.strip():
                continue
            try:
                passes, reps = int(float(passes)), int(float(reps))
            except ValueError:
                continue
            total += 1
            if reps > 0 and passes * 2 > reps:
                contended += 1
    if contended:
        worst.append((os.path.basename(path), contended, total))
if worst:
    print()
    print("!! rows measured while the kernel was preempting this run:")
    for name, contended, total in worst:
        print(f"     {name}: {contended} of {total} rows")
    print("   The scheduler put other work on these cores after the start-of-run")
    print("   check passed. Re-run those stages on an isolated cpuset, or read")
    print("   them as working numbers.")
CONTENTION

echo
echo "results in $results:"
ls -1 "$results"
cat <<'MANIFEST'

what is in there, beyond one CSV per question:
  q3_detection.csv              the grid, with the phase split (ns_materialize /
                                ns_sort / ns_detect) and the iso-resource rows,
                                which name their pairing in `variant`
  q3_ladder.csv                 both scaling curves over every worker count, for
                                findings.py::cores_freed
  q3_pressure.csv               the same cell at 4x and 16x the last level, with
                                the cardinality held -- so the footprint and the
                                run length grow together
  q4_smt.csv                    the thread axis run on the same physical cores
                                with both SMT siblings, against q4_scaling's one
                                thread per core. `pinned_cpus` says which mask a
                                row ran under
  q3_run_length.csv             the same two sizes with rows/cardinality held, so
                                only the footprint changes. The pair separates
                                "the offload likes memory pressure" from "the
                                offload likes long runs"
  q3_*_detector_counters.csv    what each detector did with the ranges it was
                                given: offloaded, declined and why, descriptors,
                                spans, poll accounting, with the repetition count.
                                A runtime column cannot tell "the offload did not
                                pay" from "the offload never happened"; these can.
  best_config.tsv               what Q0 shipped, and what every reporting driver
                                read. Keyed by worker count as well as shape, so a
                                driver running six workers gets the tuner's
                                six-worker winner; the worker-agnostic entry is the
                                fallback where a cell was not tuned at that width.
                                Every row's label says which it used.

every CSV carries two columns about the machine rather than the sort:
  preempted_passes              timed passes the kernel interrupted, and
  involuntary_switches          how many times. `start_load` screens the host when
                                a driver launches; these two catch interference
                                that arrived later, which is the only kind a
                                six-hour suite is actually exposed to. A row whose
                                preempted_passes exceeds half its repetitions has a
                                contended median and should not be published.

  configure.log / build.log     how this tree was configured and built, so a
                                results directory says which compiler, which TSL
                                release and which profile produced it without
                                anyone having to remember

read it with:
  python3 benchmarks/visualization/findings.py --results <this directory>
  python3 benchmarks/visualization/report.py   --results <this directory> --out report.html

re-run one question:
  ./run_paper.sh --results <this directory> --stages q3_detection,report
MANIFEST
