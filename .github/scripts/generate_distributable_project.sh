#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )); then
  echo "usage: $0 OUTPUT_ROOT" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
output_root="$1"
machine_profiles="${TSLC_MACHINE_PROFILES:-supplementary/buildsystem/machine_profiles.json}"

cd "$repo_root"

profile_shards="$(
  jq -c \
    -f .github/scripts/profile_shards.jq \
    "$machine_profiles"
)"
rust_profiles="$(
  jq -er '
    [.[] | select(.backend == "rust" and .purpose == "coexistence")]
    | if length == 1 and (.[0].profiles | length > 0)
      then .[0].profiles
      else error("expected exactly one non-empty Rust coexistence shard")
      end
  ' <<<"$profile_shards"
)"

./dev.sh generate \
  --machine-profiles "$machine_profiles" \
  --backend-profiles "rust=$rust_profiles" \
  --backends cpp,rust \
  --output-root "$output_root"
