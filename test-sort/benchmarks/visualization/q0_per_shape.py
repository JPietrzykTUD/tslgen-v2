#!/usr/bin/env python3
"""Per-shape parallel speedup from a bench_q0_tune log.

The CSV cannot answer this. A Q0 row is one *candidate*, and its ns/element is the
tuning set reduced to a single number -- `shape_params` says "4 shapes" and nothing
else survives. So a candidate that scales on three shapes and collapses on the
fourth reports one aggregate below 1.0, and which shape did it is not recoverable.

The log keeps the breakdown: every (cell, worker count) block ends with an
"algorithm choice vs configuration choice" table listing each shape's ns/element.
Pairing those tables across worker counts within a cell gives the per-shape
speedup, which is what says whether a shape parallelises at all.

    python3 q0_per_shape.py <q0_tune.log>
"""
import re
import sys
from collections import defaultdict

CELL = re.compile(r"^=+\s+(\S+)\s*/\s*(\d+)-bit\s*/\s*u(\d+).*?(\d+)\s+workers?\s*$")
SHAPE = re.compile(r"^\s{2}(\S+_u\d+_n\d+_m\d+)\s+([\d.]+)\s")


def main(path: str) -> int:
    # (style, width, key width) -> worker count -> shape -> ns/element
    cells: dict = defaultdict(lambda: defaultdict(dict))
    cell = workers = None
    for line in open(path, encoding="utf-8", errors="replace"):
        header = CELL.match(line.rstrip())
        if header:
            style, width, key_bits, workers = header.groups()
            cell, workers = (style, width, key_bits), int(workers)
            continue
        if cell is None:
            continue
        shape = SHAPE.match(line.rstrip())
        if shape:
            # The first column is fixed/fixed: one configuration, this shape.
            cells[cell][workers][shape.group(1)] = float(shape.group(2))

    per_shape = defaultdict(list)
    for cell, by_workers in cells.items():
        counts = sorted(by_workers)
        if len(counts) < 2:
            continue
        serial, parallel = counts[0], counts[-1]
        for shape, one in by_workers[serial].items():
            many = by_workers[parallel].get(shape)
            if many:
                per_shape[shape].append((one / many, cell, serial, parallel))

    if not per_shape:
        print("no paired worker blocks found -- did the run reach its parallel phase?")
        return 1
    width = max(len(s) for s in per_shape)
    print(f"{'shape':<{width}}  cells  median  worst   best")
    for shape in sorted(per_shape, key=lambda s: sorted(v[0] for v in per_shape[s])[
            len(per_shape[s]) // 2]):
        values = sorted(v[0] for v in per_shape[shape])
        median = values[len(values) // 2]
        flag = "   <-- does not parallelise" if median < 1.2 else ""
        print(f"{shape:<{width}}  {len(values):>5}  {median:5.2f}x  "
              f"{values[0]:5.2f}x  {values[-1]:5.2f}x{flag}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
