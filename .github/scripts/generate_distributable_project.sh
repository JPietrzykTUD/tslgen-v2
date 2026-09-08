#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )); then
  echo "usage: $0 OUTPUT_ROOT" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
output_root="$1"
machine_profiles="supplementary/buildsystem/machine_profiles.json"

cd "$repo_root"

release_contract="$(
  PYTHONPATH=tslc/src python -m tslc release contract --format json
)"
cpp_profiles="$(
  jq -er '
    [.backends[] | select(.id == "cpp") | .profiles[].name]
    | if length > 0 then join(",") else error("C++ release profiles are empty") end
  ' <<<"$release_contract"
)"
rust_profiles="$(
  jq -er '
    [.backends[] | select(.id == "rust") | .profiles[].name]
    | if length > 0 then join(",") else error("Rust release profiles are empty") end
  ' <<<"$release_contract"
)"
all_profiles="$(
  jq -er '
    [.backends[].profiles[].name] | unique
    | if length > 0 then join(",") else error("release profiles are empty") end
  ' <<<"$release_contract"
)"

./dev.sh generate \
  --machine-profiles "$machine_profiles" \
  --profiles "$all_profiles" \
  --backend-profiles "cpp=$cpp_profiles" \
  --backend-profiles "rust=$rust_profiles" \
  --backends cpp,rust \
  --output-root "$output_root"
