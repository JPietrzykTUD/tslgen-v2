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
mapfile -t archive_roots < <(
  tar -tzf "$archive" | awk -F/ 'NF > 0 {print $1}' | sort -u
)
if [[ "${#archive_roots[@]}" -ne 1 || -z "${archive_roots[0]}" ]]; then
  echo "generated release archive must contain exactly one root directory" >&2
  exit 1
fi
archive_root="${archive_roots[0]}"
tar -xzf "$archive" -C "$run_root/extracted" \
  "$archive_root/.tsl-release-bundles.json" \
  "$archive_root/bundles/cpp-scalar" \
  "$archive_root/bundles/rust-release"
generated_root="$run_root/extracted/$archive_root"
cpp_bundle="$generated_root/bundles/cpp-scalar"
rust_bundle="$generated_root/bundles/rust-release"
if [[ ! -f "$generated_root/.tsl-release-bundles.json" || \
      ! -f "$cpp_bundle/.tslc-manifest.json" || \
      ! -f "$cpp_bundle/cpp/CMakeLists.txt" || \
      ! -f "$rust_bundle/.tslc-manifest.json" || \
      ! -f "$rust_bundle/rust/Cargo.toml" ]]; then
  echo "generated release archive is missing its scalar C++ or Rust bundle" >&2
  exit 1
fi
jq -e '
  .schema_version == 1
  and .layout == "backend-deployment-bundles-v1"
  and any(.bundles[]; .id == "cpp-scalar" and .profiles == ["scalar"])
  and any(.bundles[]; .id == "rust-release" and (.profiles | length) > 0)
' "$generated_root/.tsl-release-bundles.json" >/dev/null

cp -R \
  "$repo_root/tslc/tests/fixtures/release/archive_cpp_consumer" \
  "$run_root/cpp-consumer"
cmake \
  -S "$run_root/cpp-consumer" \
  -B "$run_root/cpp-build" \
  -DTSL_GENERATED_ROOT="$cpp_bundle"
cmake --build "$run_root/cpp-build"
ctest --test-dir "$run_root/cpp-build" --output-on-failure

cargo new --quiet --bin --vcs none "$run_root/rust-consumer"
cp \
  "$repo_root/tslc/tests/fixtures/release/archive_rust_consumer.rs" \
  "$run_root/rust-consumer/src/main.rs"
cargo add \
  --quiet \
  --manifest-path "$run_root/rust-consumer/Cargo.toml" \
  --path "$rust_bundle/rust" \
  tsl
CARGO_TARGET_DIR="$run_root/rust-target" \
  cargo run --quiet --locked --manifest-path "$run_root/rust-consumer/Cargo.toml"
