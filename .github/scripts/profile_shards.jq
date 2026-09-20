# Convert machine_profiles.json into a GitHub Actions matrix axis.

def cpp_profile_chunk_size($name):
  if ($name | endswith("-oneapi-fpga"))
  then 3
  else 6
  end;
def rust_profile_chunk_size: 1;
# Cargo keeps a separate target tree per selected profile. Four quality profiles
# leave bounded headroom on a GitHub-hosted runner while retaining useful shards.
def rust_release_quality_chunk_size: 4;

def chunks($n):
  . as $items
  | [range(0; length; $n) as $i | $items[$i:($i + $n)]];

def supports_backend($backend):
  ((.supported_backends // ["cpp", "rust"]) | index($backend)) != null;

def auto_detect_gate:
  .auto_detect_gate // "";

def named_profile_shards($backend; $name; $profiles; $chunk_size):
  ($profiles | chunks($chunk_size)) as $chunks
  | $chunks
  | to_entries[]
  | {
      backend: $backend,
      name: ($backend + "-" + $name + "-" + (.key | tostring)),
      profiles: (.value | join(","))
    };

def profile_shards($backend; $name; $profiles; $chunk_size):
  named_profile_shards(
    $backend;
    $name;
    ($profiles | map(.name));
    $chunk_size
  );

def backend_profile_shards($name; $profiles):
  profile_shards(
    "cpp";
    $name;
    [$profiles[] | select(supports_backend("cpp"))];
    cpp_profile_chunk_size($name)
  ),
  profile_shards(
    "rust";
    $name;
    [$profiles[] | select(supports_backend("rust"))];
    rust_profile_chunk_size
  );

def rust_release_profiles($release_policy):
  $release_policy.backend_profiles.rust as $rust
  | if $rust.selection != "explicit" or ($rust.profiles | length) == 0
    then error("v1 Rust release profiles must use a non-empty explicit selection")
    else $rust.profiles
    end;

def rust_coexistence_shard($release_policy):
  rust_release_profiles($release_policy) as $profiles
  | {
    backend: "rust",
    name: "rust-release-coexistence",
    profiles: ($profiles | join(",")),
    purpose: "coexistence"
  };

def rust_release_quality_shards($release_policy):
  named_profile_shards(
    "rust";
    "release-quality";
    rust_release_profiles($release_policy);
    rust_release_quality_chunk_size
  )
  | . + {purpose: "release-quality"};

[
  (
    to_entries[]
    | .key as $family
    | backend_profile_shards($family; [.value[] | select(auto_detect_gate == "")]),
      (
        [.value[] | select(auto_detect_gate != "")]
        | group_by(auto_detect_gate)[]
        | .[0].auto_detect_gate as $gate
        | backend_profile_shards($family + "-" + ($gate | gsub("_"; "-")); .)
      )
  ),
  rust_coexistence_shard($release_policy[0]),
  rust_release_quality_shards($release_policy[0])
]
