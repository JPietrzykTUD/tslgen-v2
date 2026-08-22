#!/usr/bin/env python3
"""Records the tree's measured state so a refactor can be checked against it.

    ./snapshot.py <build-dir> <output-file> [--dsa DIR] [--iaa DIR]

Emits one normalised `key = value` per line, sorted, so two runs diff cleanly.
A pure file move must not change anything here. Test counts are exact and must
match; timings carry roughly 5% run-to-run noise on this host, so read a
difference under ~8% as noise and anything above it as a regression to explain.

Reads the machine-readable output the benchmarks already produce (`--csv`,
`--benchmark_format=json`) rather than parsing their human tables, because the
tables are laid out for reading and change shape when a column is added.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

TIMEOUT = 900


def run(args, cwd):
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              timeout=TIMEOUT)
        return done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"


def collect_tests(out, build, extra_builds):
    binaries = [
        ("sort", build, "test_sort"),
        ("multicolumn_sort", build, "test_multicolumn_sort"),
        ("multicolumn_index_sort", build, "test_multicolumn_index_sort"),
        ("samplesort", build, "test_samplesort_cosort"),
    ]
    for label, directory in extra_builds.items():
        if label == "dsa":
            binaries.append(("dsa_run_detector", directory, "test_dsa_run_detector"))
        else:
            binaries += [
                ("iaa_frequency", directory, "test_iaa_frequency_run_detector"),
                ("iaa_run_detector", directory, "test_iaa_run_detector"),
                ("iaa_distinct_frequencies", directory,
                 "test_iaa_distinct_frequencies"),
            ]

    for name, directory, binary in binaries:
        path = os.path.join(directory, binary)
        if not os.access(path, os.X_OK):
            out[f"test.{name}"] = "MISSING"
            continue
        code, text = run([f"./{binary}"], directory)
        if code != 0:
            out[f"test.{name}"] = "FAILED"
            continue
        checks = re.findall(r"\((\d+) checks\)", text)
        out[f"test.{name}"] = f"passed checks={checks[-1]}" if checks else "passed"


def collect_samplesort(out, build, n):
    binary = os.path.join(build, "bench_samplesort_cosort")
    if not os.access(binary, os.X_OK):
        return
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        path = handle.name
    code, _ = run(["./bench_samplesort_cosort", "--n", str(n), "--csv", path], build)
    if code != 0:
        out["perf.samplesort"] = "FAILED"
        return
    with open(path) as handle:
        for row in csv.DictReader(handle):
            # `what` carries spaces and parentheses; key on its shape instead.
            what = row["what"].replace(" ", "_").replace("(", "").replace(")", "")
            key = (f"perf.samplesort.{what}.{row['type']}.k{row['k']}"
                   f".{row['policy']}.c{row['chunks']}")
            out[key] = row["ns_per_element"]
    os.unlink(path)


def collect_hybrid_leaf(out, build, rows):
    binary = os.path.join(build, "bench_hybrid_leaf")
    if not os.access(binary, os.X_OK):
        return
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        path = handle.name
    code, _ = run(["./bench_hybrid_leaf", "--shapes", "low_cardinality_d4",
                   "--cols", "4", "--rows", str(rows), "--csv", path], build)
    if code != 0:
        out["perf.hybrid_leaf"] = "FAILED"
        return
    with open(path) as handle:
        for row in csv.DictReader(handle):
            key = (f"perf.hybrid_leaf.{row['shape']}.c{row['columns']}"
                   f".{row['policy']}.f{row['fill_percent']}")
            out[key] = row["best_ms"]
    os.unlink(path)


def collect_corpus(out, build):
    binary = os.path.join(build, "cosort_bench")
    if not os.access(binary, os.X_OK):
        return
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        path = handle.name
    env = dict(os.environ,
               COSORT_STAGE="screen",
               COSORT_VARIANTS="post_3way_ins,post_3way_net,post_3way_hyb",
               COSORT_SHAPES="low_cardinality_d4",
               COSORT_COLUMNS="4", COSORT_SIZE_LEVELS="1",
               COSORT_MOVEMENTS="direct,index", COSORT_RLE="scalar")
    try:
        subprocess.run(["./cosort_bench", "--benchmark_min_time=0.20s",
                        "--benchmark_format=json", f"--benchmark_out={path}"],
                       cwd=build, env=env, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        out["perf.corpus"] = "TIMEOUT"
        return
    try:
        with open(path) as handle:
            report = json.load(handle)
    except Exception:
        out["perf.corpus"] = "UNREADABLE"
        return
    for entry in report.get("benchmarks", []):
        name = entry["name"]
        algorithm = name.split("/")[0]
        fields = dict(part.split("=", 1) for part in name.split("/") if "=" in part)
        key = f"perf.corpus.{algorithm}.{fields.get('move', 'na')}"
        out[key] = f"{entry['real_time']:.0f}"
    os.unlink(path)


def collect_tree(out, root):
    def git(*args):
        code, text = run(["git", *args], root)
        return text.strip() if code == 0 else ""

    tracked = [line for line in git("ls-files", ".").splitlines() if line]
    out["tree.files_tracked"] = str(len(tracked))
    out["tree.headers"] = str(sum(1 for f in tracked if f.endswith(".hpp")))
    out["tree.sources"] = str(sum(1 for f in tracked if f.endswith(".cpp")))
    out["tree.max_depth"] = str(max((f.count("/") for f in tracked), default=0))
    total = 0
    for name in tracked:
        if name.endswith((".hpp", ".cpp")):
            try:
                with open(os.path.join(root, name), errors="ignore") as handle:
                    total += sum(1 for _ in handle)
            except OSError:
                pass
    out["tree.code_lines"] = str(total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("build")
    parser.add_argument("output")
    parser.add_argument("--dsa")
    parser.add_argument("--iaa")
    parser.add_argument("--n", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--rows", type=int, default=262144)
    parser.add_argument("--skip-perf", action="store_true")
    parser.add_argument("--repeat", type=int, default=3,
                        help="collect the timings this many times and keep the "
                             "median per key; two consecutive single runs were "
                             "measured up to 27%% apart on this host")
    args = parser.parse_args()

    build = os.path.abspath(args.build)
    root = os.path.dirname(os.path.abspath(__file__))
    extra = {}
    if args.dsa:
        extra["dsa"] = os.path.abspath(args.dsa)
    if args.iaa:
        extra["iaa"] = os.path.abspath(args.iaa)

    out = {}
    collect_tests(out, build, extra)
    if not args.skip_perf:
        # Median over repeats, per key. A single run is far too noisy to compare:
        # the parallel rows in particular move by tens of percent between two
        # consecutive runs on an otherwise idle machine.
        rounds = []
        for _ in range(max(1, args.repeat)):
            timings = {}
            collect_samplesort(timings, build, args.n)
            collect_hybrid_leaf(timings, build, args.rows)
            collect_corpus(timings, build)
            rounds.append(timings)
        keys = set()
        for timings in rounds:
            keys |= set(timings)
        for key in keys:
            samples = []
            for timings in rounds:
                value = timings.get(key)
                if value is None:
                    continue
                try:
                    samples.append(float(value))
                except ValueError:
                    samples = []
                    out[key] = value
                    break
            if samples:
                samples.sort()
                out[key] = f"{samples[len(samples) // 2]:.6g}"
    collect_tree(out, root)

    with open(args.output, "w") as handle:
        for key in sorted(out):
            handle.write(f"{key} = {out[key]}\n")
    print(f"wrote {args.output} ({len(out)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
