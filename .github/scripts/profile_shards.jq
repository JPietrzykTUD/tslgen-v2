# Convert machine_profiles.json into a GitHub Actions matrix axis.

def cpp_profile_chunk_size($name):
  if ($name | endswith("-oneapi-fpga"))
  then 3
  else 6
  end;
def rust_profile_chunk_size: 1;

def chunks($n):
  . as $items
  | [range(0; length; $n) as $i | $items[$i:($i + $n)]];

def supports_backend($backend):
  ((.supported_backends // ["cpp", "rust"]) | index($backend)) != null;

def auto_detect_gate:
  .auto_detect_gate // "";

def profile_shards($backend; $name; $profiles; $chunk_size):
  ($profiles | map(.name) | chunks($chunk_size)) as $chunks
  | $chunks
  | to_entries[]
  | {
      backend: $backend,
      name: ($backend + "-" + $name + "-" + (.key | tostring)),
      profiles: (.value | join(","))
    };

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

def rust_coexistence_shard($release_policy):
  $release_policy.backend_profiles.rust as $rust
  | if $rust.selection != "explicit" or ($rust.profiles | length) == 0
    then error("v1 Rust release profiles must use a non-empty explicit selection")
    else $rust.profiles
    end
  | . as $profiles
  | {
    backend: "rust",
    name: "rust-x86-coexistence",
    profiles: ($profiles | join(",")),
    purpose: "coexistence"
  };

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
  rust_coexistence_shard($release_policy[0])
]
