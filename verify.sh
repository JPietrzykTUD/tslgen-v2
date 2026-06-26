#!/usr/bin/env bash
set -euo pipefail

# Steerable end-to-end driver for the tslc generator. Drives `python -m tslc.cli` in one of:
#   ./verify.sh generate   generate + format the C++/Rust project           (no compiler needed)
#   ./verify.sh build      generate + build-verify both backends            [default]
#   ./verify.sh test       generate + build + run the value tests (SDE / qemu-aarch64 when present)
#
# Extra tslc.cli flags pass through after the mode, e.g.:
#   ./verify.sh test --profiles skylake --primitives add,convert_up
#
# Env knobs: TSLC_OUTPUT_ROOT TSLC_SOURCES TSLC_MACHINE_PROFILES TSLC_BACKENDS
#            TSLC_SDE TSLC_QEMU_AARCH64 TSLC_VERIFY_JOBS
#
# The Python unit-test suite is a separate gate: run `pytest tslc/tests`.

mode="build"
if (( $# > 0 )); then
  case "$1" in
    generate|build|test) mode="$1"; shift ;;
    -h|--help|help) sed -n '4,16p' "$0"; exit 0 ;;
    *) echo "usage: $0 [generate|build|test] [extra tslc.cli flags...]" >&2; exit 2 ;;
  esac
fi
extra_args=("$@")

output_root="${TSLC_OUTPUT_ROOT:-./tslctmp/verify}"
sources="${TSLC_SOURCES:-tsldata}"
machine_profiles="${TSLC_MACHINE_PROFILES:-supplementary/buildsystem/machine_profiles.json}"
backends="${TSLC_BACKENDS:-cpp,rust}"
sde="${TSLC_SDE:-/opt/intel-sde/sde64}"
qemu="${TSLC_QEMU_AARCH64:-/usr/bin/qemu-aarch64}"

export PYTHONPATH="tslc/src${PYTHONPATH:+:$PYTHONPATH}"

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

# Fail fast with a clear message if a compiling mode has no working toolchain.
if [[ "$mode" != "generate" ]]; then
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
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        suffix = f": {detail}" if detail else ""
        fail(f"{name} compiler preflight failed with exit code {completed.returncode}{suffix}")


preflight_root = Path("tslctmp/toolchain-preflight")
preflight_root.mkdir(parents=True, exist_ok=True)

cxx = shlex.split(os.environ.get("CXX", "c++")) or ["c++"]
if shutil.which(cxx[0]) is None:
    fail(f"C++ compiler {cxx[0]} not found")
cpp_source = preflight_root / "tslc_verify.cpp"
cpp_source.write_text("int main() { return 0; }\n", encoding="utf-8")
run_preflight(
    "C++",
    [*cxx, "-x", "c++", "-std=c++17", "-c", str(cpp_source), "-o", str(preflight_root / "tslc_verify.o")],
)

rustc = os.environ.get("RUSTC", "rustc").strip() or "rustc"
if shutil.which(rustc) is None:
    fail(f"Rust compiler {rustc} not found")
rust_source = preflight_root / "tslc_verify.rs"
rust_source.write_text("fn main() {}\n", encoding="utf-8")
run_preflight(
    "Rust",
    [rustc, "--edition=2021", str(rust_source), "-o", str(preflight_root / "tslc_verify_rust")],
)
PY
fi

cli=(
  python -m tslc.cli
  --sources "$sources"
  --machine-profiles "$machine_profiles"
  --backends "$backends"
  --output-root "$output_root"
)
case "$mode" in
  build) cli+=( --verify ) ;;
  test)
    cli+=( --test --value-test-warnings )
    # Pass the emulators only when present, so SDE/qemu-annotated profiles run rather than fail
    # on a missing binary; absent ones are skipped by the verify step.
    [[ -e "$sde" ]] && cli+=( --sde "$sde" )
    [[ -e "$qemu" ]] && cli+=( --qemu-aarch64 "$qemu" )
    ;;
esac
(( ${#extra_args[@]} )) && cli+=( "${extra_args[@]}" )

echo "tslc ${mode} -> ${output_root}"
"${cli[@]}"
echo "verify.sh ${mode}: OK"
