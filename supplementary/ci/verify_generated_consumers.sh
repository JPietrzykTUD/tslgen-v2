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
  "$scratch_root/cpp-build-scalar" \
  "$scratch_root/cpp-build-avx2" \
  "$scratch_root/cpp-build-sve" \
  "$scratch_root/cpp-build-rvv" \
  "$scratch_root/cpp-build-wasm32-simd128" \
  "$scratch_root/examples-build" \
  "$scratch_root/rust-examples"
mkdir -p "$scratch_root/cpp-consumer" "$scratch_root/rust-examples"

cat >"$scratch_root/cpp-consumer/CMakeLists.txt" <<EOF
cmake_minimum_required(VERSION 3.20)
project(tsl_cpp_consumer_check LANGUAGES CXX)

include(FetchContent)
set(TSL_CONSUMER_PROFILE scalar CACHE STRING "TSL consumer profile")
set(TSL_PROFILE "\${TSL_CONSUMER_PROFILE}" CACHE STRING "TSL profile" FORCE)
set(TSL_BUILD_TESTS OFF CACHE BOOL "TSL generated tests" FORCE)
FetchContent_Declare(tsl SOURCE_DIR "$generated_root/cpp")
FetchContent_MakeAvailable(tsl)

if(TSL_CONSUMER_PROFILE STREQUAL "scalar")
  add_library(tsl_cpp_documented_checked_example OBJECT
    "$repo_root/supplementary/docs/site/checked_api_example.cpp")
  target_link_libraries(tsl_cpp_documented_checked_example PRIVATE tsl::tsl)
  if(MSVC)
    target_compile_options(tsl_cpp_documented_checked_example PRIVATE /W4 /WX)
  else()
    target_compile_options(tsl_cpp_documented_checked_example PRIVATE -Wall -Wextra -Werror)
  endif()
endif()

if(CMAKE_CROSSCOMPILING)
  add_library(tsl_cpp_consumer OBJECT main.cpp)
else()
  add_executable(tsl_cpp_consumer main.cpp)
endif()
target_link_libraries(tsl_cpp_consumer PRIVATE tsl::tsl)
if(MSVC)
  target_compile_options(tsl_cpp_consumer PRIVATE /W4 /WX)
else()
  target_compile_options(tsl_cpp_consumer PRIVATE -Wall -Wextra -Werror)
endif()
EOF

cat >"$scratch_root/cpp-consumer/main.cpp" <<'EOF'
#include <cstddef>
#include <cstdint>
#include <cstdlib>

#include <tsl.hpp>

int main() {
  using Vec =
      tsl::dataparallel::simd_for_t<tsl::dataparallel::native, std::int32_t>;
  const std::size_t lanes = Vec::lane_count();
  const std::size_t bytes = lanes * sizeof(std::int32_t);
  auto* left = static_cast<std::int32_t*>(std::malloc(bytes));
  auto* right = static_cast<std::int32_t*>(std::malloc(bytes));
  auto* output = static_cast<std::int32_t*>(std::malloc(bytes));
  if (left == nullptr || right == nullptr || output == nullptr) {
    std::free(left);
    std::free(right);
    std::free(output);
    return 4;
  }
  for (std::size_t index = 0; index < lanes; ++index) {
    left[index] = 2;
    right[index] = 3;
    output[index] = 0;
  }

  const int status = [&]() {
    const auto ordinary_left = tsl::load<Vec, false>(left);
    const auto ordinary_right = tsl::load<Vec, false>(right);
    tsl::store<Vec, false>(
        output, tsl::add<Vec>(ordinary_left, ordinary_right));

    tsl::precondition_error error = tsl::precondition_error::none;
    const auto checked_left = tsl::load_checked<Vec, false>(
        tsl::span<std::int32_t const>(left, lanes), error);
    if (error != tsl::precondition_error::none) {
      return 1;
    }
    const auto checked_right = tsl::load_checked<Vec, false>(
        tsl::span<std::int32_t const>(right, lanes), error);
    if (error != tsl::precondition_error::none) {
      return 2;
    }
    return tsl::store_checked<Vec, false>(
               tsl::span<std::int32_t>(output, lanes),
               tsl::add<Vec>(checked_left, checked_right)) ==
                   tsl::precondition_error::none
               ? 0
               : 3;
  }();
  std::free(left);
  std::free(right);
  std::free(output);
  return status;
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

# Cargo's package include policy must be independent of locally rendered docs.
# Compare the actual Cargo-owned package listing before and after adding an
# excluded documentation artifact to the generated crate.
rust_manifest="$generated_root/rust/Cargo.toml"
package_paths_before="$(
  cargo package \
    --manifest-path "$rust_manifest" \
    --allow-dirty \
    --no-verify \
    --list
)"
package_probe="$generated_root/rust/docs/tsl-v1-package-probe.txt"
cleanup_package_probe() {
  rm -f "$package_probe"
  rmdir "$(dirname "$package_probe")" 2>/dev/null || true
}
trap cleanup_package_probe EXIT
mkdir -p "$(dirname "$package_probe")"
touch "$package_probe"
package_paths_after="$(
  cargo package \
    --manifest-path "$rust_manifest" \
    --allow-dirty \
    --no-verify \
    --list
)"
cleanup_package_probe
trap - EXIT
if [[ "$package_paths_before" != "$package_paths_after" ]]; then
  echo "generated Rust package contents changed after local docs were added" >&2
  exit 1
fi

build_cpp_consumer() {
  local profile="$1"
  local compiler="$2"
  local system_name="${3:-}"
  local system_processor="${4:-}"
  local compiler_target="${5:-}"
  local build_root="$scratch_root/cpp-build-$profile"
  local configure=(
    cmake
    -S "$scratch_root/cpp-consumer"
    -B "$build_root"
    -DTSL_CONSUMER_PROFILE="$profile"
    -DCMAKE_CXX_COMPILER="$compiler"
  )
  if [[ -n "$system_name" ]]; then
    configure+=(
      -DCMAKE_SYSTEM_NAME="$system_name"
      -DCMAKE_SYSTEM_PROCESSOR="$system_processor"
      -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY
    )
  fi
  if [[ -n "$compiler_target" ]]; then
    configure+=( -DCMAKE_CXX_COMPILER_TARGET="$compiler_target" )
  fi
  command -v "$compiler" >/dev/null
  "${configure[@]}"
  cmake --build "$build_root" --target tsl_cpp_consumer
}

build_cpp_consumer scalar c++
build_cpp_consumer avx2 c++
build_cpp_consumer sve aarch64-linux-gnu-g++ Linux aarch64
build_cpp_consumer rvv riscv64-linux-gnu-g++ Linux riscv64
build_cpp_consumer \
  wasm32-simd128 \
  /opt/wasi-sdk/bin/clang++ \
  WASI \
  wasm32 \
  wasm32-wasip1

cmake \
  -S "$repo_root/examples/cpp" \
  -B "$scratch_root/examples-build" \
  -DTSL_GENERATED_ROOT_DIR="$generated_root" \
  -DTSL_PROFILE=scalar
cmake --build "$scratch_root/examples-build"
ctest --test-dir "$scratch_root/examples-build" --output-on-failure
