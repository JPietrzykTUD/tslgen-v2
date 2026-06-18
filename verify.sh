#!/usr/bin/env bash
set -euo pipefail

mkdir -p tslctmp

export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$PWD/tslctmp/zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$PWD/tslctmp/zig-global-cache}"
mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"

host_jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '4')"
if ! [[ "$host_jobs" =~ ^[0-9]+$ ]] || (( host_jobs < 1 )); then
  host_jobs=4
fi

if [[ -n "${TSLC_VERIFY_WORKERS:-}" ]]; then
  verify_workers="$TSLC_VERIFY_WORKERS"
elif (( host_jobs >= 32 )); then
  verify_workers=24
elif (( host_jobs >= 16 )); then
  verify_workers=8
elif (( host_jobs >= 8 )); then
  verify_workers=4
elif (( host_jobs >= 4 )); then
  verify_workers=2
else
  verify_workers=1
fi
if ! [[ "$verify_workers" =~ ^[0-9]+$ ]] || (( verify_workers < 1 )); then
  verify_workers=1
elif (( verify_workers > 24 )); then
  verify_workers=24
fi

if [[ -z "${CMAKE_BUILD_PARALLEL_LEVEL:-}" ]]; then
  verify_jobs="${TSLC_VERIFY_JOBS:-$(( (host_jobs + verify_workers - 1) / verify_workers ))}"
  if [[ "$verify_jobs" =~ ^[0-9]+$ ]] && (( verify_jobs > 8 )); then
    verify_jobs=8
  elif ! [[ "$verify_jobs" =~ ^[0-9]+$ ]] || (( verify_jobs < 1 )); then
    verify_jobs=1
  fi
  export CMAKE_BUILD_PARALLEL_LEVEL="$verify_jobs"
fi
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-$CMAKE_BUILD_PARALLEL_LEVEL}"

python -m compileall -q tslc/src/tslc

if (( verify_workers == 1 )); then
  echo "Running non-build tests from tslc/tests, excluding test_build_verify.py."
  pytest --basetemp=tslctmp/pytest_verify_nonbuild \
    tslc/tests \
    --ignore=tslc/tests/test_build_verify.py \
    -q

  echo "Running generated build matrix from tslc/tests/test_build_verify.py."
  pytest --basetemp=tslctmp/pytest_build_verify \
    tslc/tests/test_build_verify.py \
    -q
else
  pids=()
  logs=()

  mapfile -t nonbuild_tests < <(
    pytest --collect-only -q tslc/tests --ignore=tslc/tests/test_build_verify.py |
      sed -n 's#^tests/#tslc/tests/#p'
  )
  echo "Collected ${#nonbuild_tests[@]} non-build tests from tslc/tests, excluding test_build_verify.py."
  for ((shard = 0; shard < verify_workers; shard++)); do
    shard_tests=()
    for ((index = shard; index < ${#nonbuild_tests[@]}; index += verify_workers)); do
      shard_tests+=("${nonbuild_tests[$index]}")
    done
    log="tslctmp/pytest_verify_nonbuild_${shard}.log"
    logs+=("$log")
    (
      echo "non-build shard $((shard + 1))/$verify_workers: ${#shard_tests[@]} tests"
      pytest --basetemp="tslctmp/pytest_verify_nonbuild_${shard}" "${shard_tests[@]}" -q
    ) >"$log" 2>&1 &
    pids+=("$!")
  done

  mapfile -t build_tests < <(
    pytest --collect-only -q tslc/tests/test_build_verify.py |
      sed -n 's#^tests/#tslc/tests/#p'
  )
  echo "Collected ${#build_tests[@]} generated-build tests from tslc/tests/test_build_verify.py."

  for ((shard = 0; shard < verify_workers; shard++)); do
    shard_tests=()
    for ((index = shard; index < ${#build_tests[@]}; index += verify_workers)); do
      shard_tests+=("${build_tests[$index]}")
    done
    log="tslctmp/pytest_build_verify_${shard}.log"
    logs+=("$log")
    (
      echo "build-verify shard $((shard + 1))/$verify_workers: ${#shard_tests[@]} tests from test_build_verify.py"
      export ZIG_LOCAL_CACHE_DIR="$PWD/tslctmp/zig-local-cache-${shard}"
      export ZIG_GLOBAL_CACHE_DIR="$PWD/tslctmp/zig-global-cache-${shard}"
      mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"
      pytest --basetemp="tslctmp/pytest_build_verify_${shard}" "${shard_tests[@]}" -q
    ) >"$log" 2>&1 &
    pids+=("$!")
  done

  failed=0
  for index in "${!pids[@]}"; do
    if ! wait "${pids[$index]}"; then
      failed=1
    fi
    cat "${logs[$index]}"
  done
  if (( failed != 0 )); then
    exit 1
  fi
fi

if grep -RIn 'BackendTranslation' tslc/src/tslc tslc/tests --include='*.py'; then
  echo "ERROR: found stale BackendTranslation references" >&2
  exit 1
fi

if grep -RInE 'backend_id ==|backend_id !=' tslc/src/tslc/lower --include='*.py'; then
  echo "ERROR: found backend behavior branches in lowering" >&2
  exit 1
fi

echo "All targeted validations passed."
