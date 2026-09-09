#!/usr/bin/env bash
set -euo pipefail

archive="${1:?usage: verify_release_archive_consumers.sh ARCHIVE [SCRATCH_PARENT]}"
scratch_parent="${2:-./tslctmp/release-archive-consumers}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

if [[ ! -f "$archive" ]]; then
  echo "generated release archive does not exist: $archive" >&2
  exit 1
fi
archive="$(cd "$(dirname "$archive")" && pwd)/$(basename "$archive")"
mkdir -p "$scratch_parent"
scratch_parent="$(cd "$scratch_parent" && pwd)"
case "$scratch_parent" in
  "$repo_root"/tslctmp/*|/tmp/*) ;;
  *)
    echo "scratch parent must be below repository tslctmp or /tmp: $scratch_parent" >&2
    exit 1
    ;;
esac

run_root="$(mktemp -d "$scratch_parent/run.XXXXXX")"
cleanup() {
  rm -rf "$run_root"
}
trap cleanup EXIT

mkdir "$run_root/extracted"
tar -xzf "$archive" -C "$run_root/extracted"
shopt -s nullglob
archive_roots=("$run_root"/extracted/*)
shopt -u nullglob
if [[ "${#archive_roots[@]}" -ne 1 || ! -d "${archive_roots[0]}" ]]; then
  echo "generated release archive must contain exactly one root directory" >&2
  exit 1
fi
generated_root="${archive_roots[0]}"
if [[ ! -f "$generated_root/.tslc-manifest.json" || \
      ! -f "$generated_root/cpp/CMakeLists.txt" || \
      ! -f "$generated_root/rust/Cargo.toml" ]]; then
  echo "generated release archive is missing its C++, Rust, or manifest product" >&2
  exit 1
fi

cp -R \
  "$repo_root/tslc/tests/fixtures/release/archive_cpp_consumer" \
  "$run_root/cpp-consumer"
cmake \
  -S "$run_root/cpp-consumer" \
  -B "$run_root/cpp-build" \
  -DTSL_GENERATED_ROOT="$generated_root"
cmake --build "$run_root/cpp-build"
ctest --test-dir "$run_root/cpp-build" --output-on-failure

cargo new --quiet --bin --vcs none "$run_root/rust-consumer"
cp \
  "$repo_root/tslc/tests/fixtures/release/archive_rust_consumer.rs" \
  "$run_root/rust-consumer/src/main.rs"
cargo add \
  --quiet \
  --manifest-path "$run_root/rust-consumer/Cargo.toml" \
  --path "$generated_root/rust" \
  tsl
CARGO_TARGET_DIR="$run_root/rust-target" \
  cargo run --quiet --locked --manifest-path "$run_root/rust-consumer/Cargo.toml"
