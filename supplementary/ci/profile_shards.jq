# Convert machine_profiles.json into a GitHub Actions matrix axis.

def profile_chunk_size: 6;

def chunks($n):
  . as $items
  | [range(0; length; $n) as $i | $items[$i:($i + $n)]];

[
  to_entries[]
  | .key as $family
  | ([.value[].name] | chunks(profile_chunk_size)) as $chunks
  | $chunks
  | to_entries[]
  | {
      name: ($family + "-" + (.key | tostring)),
      profiles: (.value | join(","))
    }
]
