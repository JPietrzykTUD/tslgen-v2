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
  profile_shards("cpp"; $name; $profiles; cpp_profile_chunk_size($name)),
  profile_shards("rust"; $name; $profiles; rust_profile_chunk_size);

def rust_coexistence_shard:
  {
    backend: "rust",
    name: "rust-x86-coexistence",
    profiles: "sse,sse2,sse3,avx,avx2,knl",
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
  rust_coexistence_shard
]
