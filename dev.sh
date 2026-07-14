#!/usr/bin/env bash
set -euo pipefail

# Steerable task runner for the tslc generator and its maintenance tooling.

self="$(basename "$0")"
usage() {
  cat <<EOF
${self}: steerable task runner for the tslc generator and its maintenance tooling.

Modes:
  ./${self} generate   generate + format the C++/Rust project               (no compiler needed)
  ./${self} build      generate + build-verify both backends                [default]
  ./${self} test       generate + build + run the value tests (SDE / qemu-aarch64 / Wasmtime when present)
  ./${self} document   generate + format + build C++/Rust API docs
  ./${self} document-site
                       rebuild only the docs website from existing generated docs/data
  ./${self} explain    diagnose ONE primitive/profile/backend/ext/type slot (no compiler needed)
  ./${self} check      validate the complete TSL corpus without rendering
  ./${self} doctor     probe selected backend/profile toolchains and runners
  ./${self} list       list catalog entries
  ./${self} show       describe one catalog entry
  ./${self} audit      audit source metadata
  ./${self} ratchet    coverage regression gate vs the committed baseline   (no compiler needed)
  ./${self} benchmark-ratchet
                       require complete variant benchmark coverage/inventory (no compiler needed)
  ./${self} dump       dump one pipeline stage (catalog/segments/selection/lowered) (no compiler)

Extra flags pass through after generator modes; document-site honors --output-root
and --backends for the existing tree, e.g.:
  ./${self} document --profiles avx2 --primitives add
  ./${self} document-site
  ./${self} document-site --output-root ./tslctmp/verify --backends cpp,rust
  ./${self} test    --profiles skylake --primitives add,convert_up
  ./${self} explain --primitive add --profile avx2 --type si32 --backend cpp
  ./${self} ratchet --update
  ./${self} benchmark-ratchet --update
  ./${self} dump    --stage segments --primitive add

generate/build/test and authoring tools drive the unified \`python -m tslc\`
surface; document-site rebuilds the website from an existing output tree.

Env knobs (build/test only): TSLC_OUTPUT_ROOT TSLC_SOURCES TSLC_MACHINE_PROFILES
  TSLC_BACKENDS TSLC_SDE TSLC_QEMU_AARCH64 TSLC_WASMTIME TSLC_VERIFY_JOBS
  TSLC_SUMMARY_FILE
Env knobs (document or TSLC_DOCUMENT=1): TSLC_DOXYGEN TSLC_SPHINX_BUILD TSLC_CARGO
  TSLC_NPM
  TSLC_DOCUMENT_PROJECT

The Python unit-test suite is a separate gate: run \`pytest tslc/tests\`.
EOF
}

mode="build"
if (( $# > 0 )); then
  case "$1" in
    generate|build|test|document|document-site|explain|check|doctor|list|show|audit|ratchet|benchmark-ratchet|dump) mode="$1"; shift ;;
    -h|--help|help) usage; exit 0 ;;
    *) echo "usage: $0 [generate|build|test|document|document-site|explain|check|doctor|list|show|audit|ratchet|benchmark-ratchet|dump] [extra flags...]" >&2; exit 2 ;;
  esac
fi
extra_args=("$@")

has_cli_flag() {
  local flag="$1"
  local arg
  for arg in "${extra_args[@]}"; do
    [[ "$arg" == "$flag" ]] && return 0
  done
  return 1
}

has_cli_assignment() {
  local flag="$1"
  local arg
  for arg in "${extra_args[@]}"; do
    [[ "$arg" == "$flag" || "$arg" == "$flag"=* ]] && return 0
  done
  return 1
}

if [[ "$mode" == "generate" ]] && { has_cli_flag --test || has_cli_flag --fuzz; }; then
  echo "ERROR: dev.sh generate does not accept --test or --fuzz." >&2
  echo "Use './dev.sh test ...' so SDE/qemu-aarch64 paths are wired consistently." >&2
  echo "For manual control, call 'python -m tslc.cli' directly with explicit --runner KIND=PATH options." >&2
  exit 2
fi

effective_cli_value() {
  local flag="$1"
  local value="$2"
  local i arg
  for (( i = 0; i < ${#extra_args[@]}; i++ )); do
    arg="${extra_args[$i]}"
    case "$arg" in
      "$flag")
        if (( i + 1 < ${#extra_args[@]} )); then
          value="${extra_args[$((i + 1))]}"
        fi
        ;;
      "$flag"=*)
        value="${arg#${flag}=}"
        ;;
    esac
  done
  printf '%s\n' "$value"
}

output_root="${TSLC_OUTPUT_ROOT:-./tslctmp/verify}"
sources="${TSLC_SOURCES:-tsldata}"
machine_profiles="${TSLC_MACHINE_PROFILES:-supplementary/buildsystem/machine_profiles.json}"
backends="${TSLC_BACKENDS:-cpp,rust}"
effective_output_root="$(effective_cli_value --output-root "$output_root")"
document_backends="$(effective_cli_value --backends "$backends")"
sde="${TSLC_SDE:-/opt/intel-sde/sde64}"
qemu="${TSLC_QEMU_AARCH64:-/usr/bin/qemu-aarch64}"
wasmtime="${TSLC_WASMTIME:-/usr/local/bin/wasmtime}"
doxygen="${TSLC_DOXYGEN:-doxygen}"
sphinx_build="${TSLC_SPHINX_BUILD:-sphinx-build}"
cargo_doc="${TSLC_CARGO:-cargo}"
npm_doc="${TSLC_NPM:-npm}"
document_project="${TSLC_DOCUMENT_PROJECT:-TSL Generated API}"
summary_file="${TSLC_SUMMARY_FILE:-}"

export PYTHONPATH="tslc/src${PYTHONPATH:+:$PYTHONPATH}"

# Focused authoring/maintenance modes do not enter generated-project workflows.
case "$mode" in
  explain) exec python -m tslc explain "${extra_args[@]}" ;;
  check)   exec python -m tslc check "${extra_args[@]}" ;;
  doctor)  exec python -m tslc doctor "${extra_args[@]}" ;;
  list)    exec python -m tslc list "${extra_args[@]}" ;;
  show)    exec python -m tslc show "${extra_args[@]}" ;;
  audit)   exec python -m tslc audit metadata "${extra_args[@]}" ;;
  ratchet) exec python -m tslc coverage ratchet "${extra_args[@]}" ;;
  benchmark-ratchet) exec python -m tslc.maintenance.benchmark_coverage "${extra_args[@]}" ;;
  dump)    exec python -m tslc inspect "${extra_args[@]}" ;;
esac

mkdir -p tslctmp
export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$PWD/tslctmp/zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$PWD/tslctmp/zig-global-cache}"
mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"

# Build parallelism (only the build/test modes compile).
if [[ -z "${CMAKE_BUILD_PARALLEL_LEVEL:-}" ]]; then
  jobs="${TSLC_VERIFY_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
  [[ "$jobs" =~ ^[0-9]+$ ]] || jobs=4
  (( jobs > 8 )) && jobs=8
  export CMAKE_BUILD_PARALLEL_LEVEL="$jobs"
fi
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-$CMAKE_BUILD_PARALLEL_LEVEL}"

compiler_basename() {
  local command="${1:-}"
  command="${command%% *}"
  command="${command##*/}"
  printf '%s\n' "$command"
}

# The CI/devcontainer image exposes Zig via ambient CC/CXX for cross-target
# flows. Native host builds should use the host toolchain unless the caller
# passes --compiler cpp=COMMAND directly to tslc or opts into a different host compiler
# through TSLC_HOST_CXX/TSLC_HOST_CC.
if [[ "$(compiler_basename "${CXX:-}")" == "zig" ]]; then
  export CXX="${TSLC_HOST_CXX:-c++}"
fi
if [[ "$(compiler_basename "${CC:-}")" == "zig" ]]; then
  export CC="${TSLC_HOST_CC:-cc}"
fi

if [[ "$mode" == "document-site" ]]; then
  echo "tslc ${mode} -> ${effective_output_root}"
  python -m tslc.maintenance.documentation \
    --output-root "$effective_output_root" \
    --backends "$document_backends" \
    --project-name "$document_project" \
    --sphinx-build "$sphinx_build" \
    --npm "$npm_doc" \
    --site-only \
    --skip-npm-ci
  echo "${self} ${mode}: OK"
  exit 0
fi

# Fail fast through the verifier-owned backend/profile-aware preflight.
if [[ "$mode" == "build" || "$mode" == "test" ]]; then
  doctor=(
    python -m tslc doctor
    --sources "$sources"
    --machine-profiles "$machine_profiles"
    --backends "$(effective_cli_value --backends "$backends")"
  )
  effective_profiles="$(effective_cli_value --profiles "")"
  [[ -n "$effective_profiles" ]] && doctor+=( --profiles "$effective_profiles" )
  [[ "$mode" == "test" ]] && doctor+=( --run )
  for (( i = 0; i < ${#extra_args[@]}; i++ )); do
    arg="${extra_args[$i]}"
    case "$arg" in
      --compiler|--target|--linker|--runner)
        if (( i + 1 < ${#extra_args[@]} )); then
          doctor+=( "$arg" "${extra_args[$((i + 1))]}" )
          ((i+=1))
        fi
        ;;
      --compiler=*|--target=*|--linker=*|--runner=*) doctor+=( "$arg" ) ;;
    esac
  done
  if ! has_cli_assignment --runner; then
    [[ -e "$sde" ]] && doctor+=( --runner "sde=$sde" )
    [[ -e "$qemu" ]] && doctor+=( --runner "qemu-aarch64=$qemu" )
    [[ -e "$wasmtime" ]] && doctor+=( --runner "wasmtime=$wasmtime" )
  fi
  "${doctor[@]}"
fi

cli=(
  python -m tslc
  "$([[ "$mode" == "document" ]] && printf generate || printf '%s' "$mode")"
  --sources "$sources"
  --machine-profiles "$machine_profiles"
  --backends "$backends"
  --output-root "$output_root"
)
if [[ -n "$summary_file" ]] && ! has_cli_flag --summary-file; then
  cli+=( --summary-file "$summary_file" )
fi
case "$mode" in
  test)
    cli+=( --test --value-test-warnings )
    # Pass the runners only when present, so annotated profiles run rather than fail on a
    # missing binary; absent ones are skipped by the verify step.
    if ! has_cli_assignment --runner; then
      [[ -e "$sde" ]] && cli+=( --runner "sde=$sde" )
      [[ -e "$qemu" ]] && cli+=( --runner "qemu-aarch64=$qemu" )
      [[ -e "$wasmtime" ]] && cli+=( --runner "wasmtime=$wasmtime" )
    fi
    ;;
esac
(( ${#extra_args[@]} )) && cli+=( "${extra_args[@]}" )

echo "tslc ${mode} -> ${effective_output_root}"
"${cli[@]}"
if [[ "$mode" == "document" || "${TSLC_DOCUMENT:-0}" == "1" || "${TSLC_DOCUMENT:-}" == "true" ]]; then
  python -m tslc.maintenance.documentation \
    --output-root "$effective_output_root" \
    --backends "$document_backends" \
    --project-name "$document_project" \
    --doxygen "$doxygen" \
    --sphinx-build "$sphinx_build" \
    --cargo "$cargo_doc" \
    --npm "$npm_doc"
fi
echo "${self} ${mode}: OK"
