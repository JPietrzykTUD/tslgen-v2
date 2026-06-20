#!/usr/bin/env bash
set -euo pipefail

mkdir -p tslctmp

export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$PWD/tslctmp/zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$PWD/tslctmp/zig-global-cache}"
mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"

python - <<'PY'
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_preflight(name: str, command: list[str]) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        suffix = f": {detail}" if detail else ""
        fail(f"{name} compiler preflight failed with exit code {completed.returncode}{suffix}")


preflight_root = Path("tslctmp/toolchain-preflight")
preflight_root.mkdir(parents=True, exist_ok=True)

cxx = shlex.split(os.environ.get("CXX", "c++"))
if not cxx:
    cxx = ["c++"]
if shutil.which(cxx[0]) is None:
    fail(f"C++ compiler {cxx[0]} not found")
cpp_source = preflight_root / "tslc_verify.cpp"
cpp_object = preflight_root / "tslc_verify.o"
cpp_source.write_text("int main() { return 0; }\n", encoding="utf-8")
run_preflight(
    "C++",
    [*cxx, "-x", "c++", "-std=c++17", "-c", str(cpp_source), "-o", str(cpp_object)],
)

rustc = os.environ.get("RUSTC", "rustc").strip() or "rustc"
if shutil.which(rustc) is None:
    fail(f"Rust compiler {rustc} not found")
rust_source = preflight_root / "tslc_verify.rs"
rust_binary = preflight_root / "tslc_verify_rust"
rust_source.write_text("fn main() {}\n", encoding="utf-8")
run_preflight(
    "Rust",
    [rustc, "--edition=2021", str(rust_source), "-o", str(rust_binary)],
)
PY

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

require_collected_test() {
  local expected="$1"
  shift
  local test_id
  for test_id in "$@"; do
    if [[ "$test_id" == "$expected" ]]; then
      return 0
    fi
  done
  echo "ERROR: required test was not collected: $expected" >&2
  exit 1
}

mapfile -t nonbuild_tests < <(
  pytest --collect-only -q tslc/tests --ignore=tslc/tests/test_build_verify.py |
    sed -n 's#^tests/#tslc/tests/#p'
)
if (( ${#nonbuild_tests[@]} == 0 )); then
  echo "ERROR: collected zero non-build tests from tslc/tests" >&2
  exit 1
fi
require_collected_test \
  "tslc/tests/test_build_verify_config.py::test_cpp_verifier_accepts_explicit_compiler" \
  "${nonbuild_tests[@]}"
require_collected_test \
  "tslc/tests/test_build_verify_config.py::test_rust_verifier_accepts_explicit_compiler" \
  "${nonbuild_tests[@]}"
echo "Collected ${#nonbuild_tests[@]} non-build tests from tslc/tests, excluding test_build_verify.py."

mapfile -t build_tests < <(
  pytest --collect-only -q tslc/tests/test_build_verify.py |
    sed -n 's#^tests/#tslc/tests/#p'
)
if (( ${#build_tests[@]} == 0 )); then
  echo "ERROR: collected zero generated-build tests from tslc/tests/test_build_verify.py" >&2
  exit 1
fi
require_collected_test \
  "tslc/tests/test_build_verify.py::test_generated_profiles_build" \
  "${build_tests[@]}"
echo "Collected ${#build_tests[@]} generated-build tests from tslc/tests/test_build_verify.py."

if (( verify_workers == 1 )); then
  echo "Running non-build tests from tslc/tests, excluding test_build_verify.py."
  pytest --basetemp=tslctmp/pytest_verify_nonbuild \
    "${nonbuild_tests[@]}" \
    -q

  echo "Running generated build matrix from tslc/tests/test_build_verify.py."
  pytest --basetemp=tslctmp/pytest_build_verify \
    "${build_tests[@]}" \
    -q
else
  pids=()
  logs=()

  for ((shard = 0; shard < verify_workers; shard++)); do
    shard_tests=()
    for ((index = shard; index < ${#nonbuild_tests[@]}; index += verify_workers)); do
      shard_tests+=("${nonbuild_tests[$index]}")
    done
    if (( ${#shard_tests[@]} == 0 )); then
      continue
    fi
    log="tslctmp/pytest_verify_nonbuild_${shard}.log"
    logs+=("$log")
    (
      echo "non-build shard $((shard + 1))/$verify_workers: ${#shard_tests[@]} tests"
      pytest --basetemp="tslctmp/pytest_verify_nonbuild_${shard}" "${shard_tests[@]}" -q
    ) >"$log" 2>&1 &
    pids+=("$!")
  done

  for ((shard = 0; shard < verify_workers; shard++)); do
    shard_tests=()
    for ((index = shard; index < ${#build_tests[@]}; index += verify_workers)); do
      shard_tests+=("${build_tests[$index]}")
    done
    if (( ${#shard_tests[@]} == 0 )); then
      continue
    fi
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
