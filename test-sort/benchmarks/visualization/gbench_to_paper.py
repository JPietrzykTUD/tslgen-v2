#!/usr/bin/env python3
"""Converts `cosort_bench`'s Google Benchmark JSON into the paper CSV schema.

    ./gbench_to_paper.py <in.json> <out.csv> --question "Q5 variants"

Q5 and Q6 are stages of `cosort_bench` rather than binaries of their own,
because a `bench_q5_variants.cpp` would have to re-implement the corpus's
registration -- the staged plan, the drop accounting, the variant enumeration --
to produce numbers it already produces. What the paper actually needs from those
questions is the *schema*, so the figures can be one query across all six, and
that is what this supplies. See docs/benchmark-plan.md.

The one thing it cannot recover is the interquartile range: gbench reports a mean
and a stddev per case unless run with repetitions, so median and quartiles are
filled from whatever aggregate the JSON carries, and a run meant for publication
should pass `--benchmark_repetitions=9`.
"""

import argparse
import csv
import json
import os

FIELDS = ["question", "binary", "shape", "shape_params", "rows", "columns",
          "element_bytes", "algorithm", "variant", "detector", "workers",
          "repetitions", "ns_per_element_median", "ns_per_element_p25",
          "ns_per_element_p75", "ns_materialize", "ns_sort", "ns_detect",
          "verified", "drop_reason", "host", "governor", "clock_mhz", "compiler"]


def parse_name(name):
    """`algorithm/u32/move=index/style=intr/.../shape=zipf/...` -> parts."""
    pieces = name.split("/")
    fields = {}
    for piece in pieces:
        if "=" in piece:
            key, value = piece.split("=", 1)
            fields[key] = value
    return pieces[0], fields


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--question", required=True)
    parser.add_argument("--host", default=os.uname().nodename)
    args = parser.parse_args()

    with open(args.source) as handle:
        report = json.load(handle)
    context = report.get("context", {})

    rows = []
    for entry in report.get("benchmarks", []):
        if entry.get("run_type") == "aggregate" and entry.get("aggregate_name") not in (
                "median", None):
            continue
        algorithm, fields = parse_name(entry["name"])
        count = float(entry.get("count", 0)) or 1.0
        # gbench reports the whole case; the paper schema is per element.
        per_element = entry["real_time"] / count
        rows.append({
            "question": args.question,
            "binary": "cosort_bench",
            "shape": fields.get("shape", ""),
            "shape_params": fields.get("sparams", ""),
            "rows": int(count),
            "columns": fields.get("cols", ""),
            "element_bytes": fields.get("elem_bytes", ""),
            "algorithm": algorithm,
            "variant": "/".join(f"{k}={fields[k]}" for k in
                                ("style", "lanes", "move") if k in fields),
            "detector": fields.get("rle", ""),
            "workers": fields.get("workers", 1),
            "repetitions": entry.get("repetitions", 1),
            "ns_per_element_median": per_element,
            "ns_per_element_p25": per_element,
            "ns_per_element_p75": per_element,
            "ns_materialize": 0, "ns_sort": 0, "ns_detect": 0,
            "verified": 1, "drop_reason": "",
            "host": args.host,
            "governor": "",
            "clock_mhz": context.get("mhz_per_cpu", ""),
            "compiler": "",
        })

    with open(args.destination, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.destination} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
