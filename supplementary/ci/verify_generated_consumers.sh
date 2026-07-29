#!/usr/bin/env bash
set -euo pipefail

generated_root="${1:-./tslctmp/ci-generated}"
scratch_root="${2:-./tslctmp/consumer-checks}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

if [[ ! -d "$generated_root" ]]; then
  echo "generated output root does not exist: $generated_root" >&2
  exit 1
fi

generated_root="$(cd "$generated_root" && pwd)"
scratch_root="$(mkdir -p "$scratch_root" && cd "$scratch_root" && pwd)"
export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-$scratch_root/zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$scratch_root/zig-global-cache}"
mkdir -p "$ZIG_LOCAL_CACHE_DIR" "$ZIG_GLOBAL_CACHE_DIR"

compiler_basename() {
  local command="${1:-}"
  command="${command%% *}"
  command="${command##*/}"
  printf '%s\n' "$command"
}

if [[ "$(compiler_basename "${CXX:-}")" == "zig" ]]; then
  export CXX="${TSLC_HOST_CXX:-c++}"
fi
if [[ "$(compiler_basename "${CC:-}")" == "zig" ]]; then
  export CC="${TSLC_HOST_CC:-cc}"
fi

case "$scratch_root" in
  "$PWD"/tslctmp/*|/tmp/*) ;;
  *)
    echo "refusing to clean consumer-check scratch outside tslctmp or /tmp: $scratch_root" >&2
    exit 1
    ;;
esac

rm -rf \
  "$scratch_root/cpp-consumer" \
  "$scratch_root/cpp-build" \
  "$scratch_root/examples-build" \
  "$scratch_root/rust-examples"
mkdir -p "$scratch_root/cpp-consumer" "$scratch_root/rust-examples"

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

cat >"$scratch_root/rust-examples/Cargo.toml" <<EOF
[package]
name = "tsl_rust_examples_check"
version = "0.1.0"
edition = "2021"
publish = false

[dependencies]
tsl = { path = "$generated_root/rust", default-features = false }

[[bin]]
name = "unary_operator"
path = "$repo_root/examples/rust/src/bin/unary_operator.rs"

[[bin]]
name = "binary_operator"
path = "$repo_root/examples/rust/src/bin/binary_operator.rs"

[[bin]]
name = "chunk_operator"
path = "$repo_root/examples/rust/src/bin/chunk_operator.rs"

[[bin]]
name = "range_operator"
path = "$repo_root/examples/rust/src/bin/range_operator.rs"

[[bin]]
name = "predicate_operator"
path = "$repo_root/examples/rust/src/bin/predicate_operator.rs"

[[bin]]
name = "where_operator"
path = "$repo_root/examples/rust/src/bin/where_operator.rs"

[[bin]]
name = "masked_operator"
path = "$repo_root/examples/rust/src/bin/masked_operator.rs"

[[bin]]
name = "native_mask_operator"
path = "$repo_root/examples/rust/src/bin/native_mask_operator.rs"

[[bin]]
name = "byte_mask_operator"
path = "$repo_root/examples/rust/src/bin/byte_mask_operator.rs"

[[bin]]
name = "bit_mask_operator"
path = "$repo_root/examples/rust/src/bin/bit_mask_operator.rs"

[[bin]]
name = "consume_operator"
path = "$repo_root/examples/rust/src/bin/consume_operator.rs"

[[bin]]
name = "masked_consume_operator"
path = "$repo_root/examples/rust/src/bin/masked_consume_operator.rs"

[[bin]]
name = "aggregation_operator"
path = "$repo_root/examples/rust/src/bin/aggregation_operator.rs"

[[bin]]
name = "masked_aggregation_operator"
path = "$repo_root/examples/rust/src/bin/masked_aggregation_operator.rs"

[[bin]]
name = "count_operator"
path = "$repo_root/examples/rust/src/bin/count_operator.rs"

[[bin]]
name = "selection_operator"
path = "$repo_root/examples/rust/src/bin/selection_operator.rs"

[[bin]]
name = "masked_selection_operator"
path = "$repo_root/examples/rust/src/bin/masked_selection_operator.rs"

[[bin]]
name = "selection_vector_operator"
path = "$repo_root/examples/rust/src/bin/selection_vector_operator.rs"

[[bin]]
name = "selected_transform_operator"
path = "$repo_root/examples/rust/src/bin/selected_transform_operator.rs"

[[bin]]
name = "selected_refinement_operator"
path = "$repo_root/examples/rust/src/bin/selected_refinement_operator.rs"

[[bin]]
name = "selected_aggregate_consume_operator"
path = "$repo_root/examples/rust/src/bin/selected_aggregate_consume_operator.rs"
EOF

# Cargo probes rustc with `rustc -`. Run the Rust examples before the verbose
# C++ build/test phase so PTY-backed callers cannot leak build-log bytes into
# that probe as inherited source input.
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin unary_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin binary_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin chunk_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin range_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin predicate_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin where_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin masked_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin native_mask_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin byte_mask_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin bit_mask_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin consume_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin masked_consume_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin aggregation_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin masked_aggregation_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin count_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin selection_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin masked_selection_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin selection_vector_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin selected_transform_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin selected_refinement_operator </dev/null
cargo run --quiet --manifest-path "$scratch_root/rust-examples/Cargo.toml" --bin selected_aggregate_consume_operator </dev/null

cmake -S "$scratch_root/cpp-consumer" -B "$scratch_root/cpp-build"
cmake --build "$scratch_root/cpp-build" --target tsl_cpp_consumer

cmake \
  -S "$repo_root/examples/cpp" \
  -B "$scratch_root/examples-build" \
  -DTSL_GENERATED_ROOT_DIR="$generated_root" \
  -DTSL_PROFILE=scalar
cmake --build "$scratch_root/examples-build"
ctest --test-dir "$scratch_root/examples-build" --output-on-failure
