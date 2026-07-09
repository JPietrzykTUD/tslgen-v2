# Convert machine_profiles.json into a GitHub Actions matrix axis.

def profile_chunk_size: 6;

def chunks($n):
  . as $items
  | [range(0; length; $n) as $i | $items[$i:($i + $n)]];

def auto_detect_gate:
  .auto_detect_gate // "";

def profile_shards($name; $profiles):
  ($profiles | map(.name) | chunks(profile_chunk_size)) as $chunks
  | $chunks
  | to_entries[]
  | {
      name: ($name + "-" + (.key | tostring)),
      profiles: (.value | join(","))
    };

[
  to_entries[]
  | .key as $family
  | profile_shards($family; [.value[] | select(auto_detect_gate == "")]),
    (
      [.value[] | select(auto_detect_gate != "")]
      | group_by(auto_detect_gate)[]
      | .[0].auto_detect_gate as $gate
      | profile_shards($family + "-" + ($gate | gsub("_"; "-")); .)
    )
]
