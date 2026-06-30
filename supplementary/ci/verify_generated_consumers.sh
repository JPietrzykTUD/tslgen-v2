#!/usr/bin/env bash
set -euo pipefail

generated_root="${1:-./tslctmp/ci-generated}"
scratch_root="${2:-./tslctmp/consumer-checks}"

if [[ ! -d "$generated_root" ]]; then
  echo "generated output root does not exist: $generated_root" >&2
  exit 1
fi

generated_root="$(cd "$generated_root" && pwd)"
scratch_root="$(mkdir -p "$scratch_root" && cd "$scratch_root" && pwd)"
export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$scratch_root/zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$scratch_root/zig-global-cache}"
mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"

case "$scratch_root" in
  "$PWD"/tslctmp/*|/tmp/*) ;;
  *)
    echo "refusing to clean consumer-check scratch outside tslctmp or /tmp: $scratch_root" >&2
    exit 1
    ;;
esac

rm -rf "$scratch_root/cpp-consumer" "$scratch_root/cpp-build" "$scratch_root/rust-consumer"
mkdir -p "$scratch_root/cpp-consumer" "$scratch_root/rust-consumer/src"

cat >"$scratch_root/cpp-consumer/CMakeLists.txt" <<EOF
cmake_minimum_required(VERSION 3.20)
project(tsl_cpp_consumer_check LANGUAGES CXX)

include(FetchContent)
set(TSL_PROFILE scalar CACHE STRING "TSL profile" FORCE)
FetchContent_Declare(tsl SOURCE_DIR "$generated_root/cpp")
FetchContent_MakeAvailable(tsl)

add_executable(tsl_cpp_consumer main.cpp)
target_link_libraries(tsl_cpp_consumer PRIVATE tsl::tsl)
EOF

cat >"$scratch_root/cpp-consumer/main.cpp" <<'EOF'
#include <cstdint>
#include <tsl.hpp>

int main() {
  using Vec = tsl::simd<std::int32_t, tsl::scalar>;
  return tsl::add<Vec>(1, 2) == 3 ? 0 : 1;
}
EOF

cmake -S "$scratch_root/cpp-consumer" -B "$scratch_root/cpp-build"
cmake --build "$scratch_root/cpp-build" --target tsl_cpp_consumer

cat >"$scratch_root/rust-consumer/Cargo.toml" <<EOF
[package]
name = "tsl_rust_consumer_check"
version = "0.1.0"
edition = "2021"

[dependencies]
tsl_generated = { path = "$generated_root/rust", default-features = false, features = ["scalar"] }
EOF

cat >"$scratch_root/rust-consumer/src/main.rs" <<'EOF'
use tsl_generated::tsl_core::{Scalar, Simd};
use tsl_generated::tsl_scalar::add;

fn main() {
    let result = add::<Simd<i32, Scalar>>(1, 2);
    assert_eq!(result, 3);
}
EOF

cargo run --quiet --manifest-path "$scratch_root/rust-consumer/Cargo.toml"
