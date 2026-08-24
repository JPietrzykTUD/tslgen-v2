"""Which extracted key set do the results in this directory already use?

The csv records the row count of every measured case but not the scale factor behind
it, and a key file's name carries its row count: tpcds_qNNN_u32_n<rows>_m<cols>.
Matching one against the other identifies the set that produced existing rows, which
is the only one a re-run may add to.

Synthetic shapes are excluded. `tpcds_q67_sf1` is TslShape::TpcdsQ67 parameterised by
scale factor, generated rather than extracted, and its row count is derived from the
machine -- it would match nothing here and must not be mistaken for a real key.
"""
import csv, os, re, sys

keys_root, results = sys.argv[1], sys.argv[2]
sets = {}
for entry in sorted(os.listdir(keys_root)) if os.path.isdir(keys_root) else []:
    rows = set()
    directory = os.path.join(keys_root, entry)
    for name in os.listdir(directory) if os.path.isdir(directory) else []:
        found = re.search(r"_n(\d+)_m\d+\.tsldset$", name)
        if found:
            rows.add(int(found.group(1)))
    if rows:
        sets[entry] = rows

measured = set()
for csv_name in ("q2_algorithms.csv", "q1_baselines.csv", "q4_scaling.csv"):
    path = os.path.join(results, csv_name)
    if not os.path.isfile(path):
        continue
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            shape = row.get("shape", "")
            if shape.startswith("tpcds_") and "_sf" not in shape:
                try:
                    measured.add(int(row["rows"]))
                except (KeyError, ValueError):
                    pass

matched = sorted(name for name, rows in sets.items() if measured & rows)
if len(matched) == 1:
    print(matched[0])
