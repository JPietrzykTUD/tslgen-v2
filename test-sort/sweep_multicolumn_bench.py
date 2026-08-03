#!/usr/bin/env python3
"""Sweep and stitch the multi-column co-sort benchmark.

`COSORT_WORKERS`, `COSORT_TASK_THRESHOLD`, and `COSORT_PARTITION_THRESHOLD` are
scalar per process, so a scaling curve over any of them needs one process per
value. This script runs that matrix and merges the per-run JSON files into one
file that `visualize_multicolumn_bench.py` can load as a single sweep.

    ./sweep_multicolumn_bench.py run --workers 1,2,4,8,16 \
        --partition-thresholds 4096,16384,65536 --columns 1,2,3
    streamlit run visualize_multicolumn_bench.py -- --json sweep/merged.json

Only the standard library is used, so this runs in environments where the
Streamlit/pandas explorer cannot.

## Why the sweep is split into three phases

Benchmark names carry only the axes that apply to them: a serial target has no
`workers=`, a `parallel_` target has `workers=`/`threshold=` but no
`partitions=`, and only a `deep_parallel_` target carries all three. Nesting one
loop over every axis would therefore re-run serial targets once per
configuration and emit many benchmarks with byte-identical names, which is both
wasted machine time and ambiguous input for the explorer. Each phase instead
runs exactly the targets whose names distinguish its axes:

    baseline  once                                -> baseline.json
    serial    once                                -> serial.json
    parallel  per (workers, threshold)            -> parallel_w*_t*.json
    deep      per (workers, threshold, partition) -> deep_w*_t*_p*.json

Run count is `2 + W*T + W*T*P`, reported before anything executes. Select a
subset with `--phases`, for example `--phases baseline` to add the scalar
reference to a sweep that already ran.

`std_lex_argsort` is its own phase because it is registered once per data type
rather than per SIMD width, so its names carry `lanes=na`. A `--narrow` that
constrains `lanes` would exclude it entirely; the baseline phase therefore
relaxes any `lanes=` term in the narrow and keeps the rest. The explorer joins
the baseline on data type, distribution, direction, columns, and size only, so
one baseline row serves every lane and worker configuration.

## Stitching

`stitch` merges any set of run files. It refuses to merge results from different
hosts or CPU counts unless `--force`, because a mixed-host sweep silently
invalidates every cross-configuration comparison. Benchmarks that still collide
on identity after merging are collapsed to the fastest observation and reported;
nothing is dropped silently.

Naming an existing merged file as an explicit input merges into it, which is how
a phase is added to a finished sweep::

    ./sweep_multicolumn_bench.py stitch build/sweep/merged.json \
        build/sweep/baseline.json -o build/sweep/merged.json

A *directory* input excludes the output file instead, so re-stitching a run
directory rebuilds from the run files and cannot resurrect a measurement whose
run file was replaced.

A run interrupted mid-write leaves truncated JSON. This script reports such a
file as skipped rather than repairing it: `visualize_multicolumn_bench.py` owns
the salvage path for truncated output and can read one such file directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Phase target selection. Each is a positive prefix pattern rather than a
# negation so that `--narrow` can be appended to every phase filter the same
# way; a negative filter cannot be intersected with another pattern.
PHASE_FILTERS = {
    "baseline": "^std_lex_argsort",
    "serial": "^(post_|incremental_)",
    "parallel": "^parallel_",
    "deep": "^deep_parallel_",
}
PHASE_ORDER = ("baseline", "serial", "parallel", "deep")

# The scalar baseline is registered once per data type, not per SIMD width, so
# its names carry `lanes=na`. Narrowing a sweep to one width must not silently
# drop it, so a lanes term is widened for that phase alone.
LANES_TERM = re.compile(r"lanes=[^/]*")

# Context fields that must agree for merged runs to be comparable. `mhz_per_cpu`
# is deliberately absent: it is an instantaneous clock sample that differs
# between consecutive runs on one host, so requiring it to match rejects every
# legitimate sweep. Its drift is reported separately as a comparability note.
CONTEXT_IDENTITY_KEYS = (
    "host_name",
    "num_cpus",
    "cpu_scaling_enabled",
    "caches",
    "library_build_type",
)

# Clock-sample spread above this fraction is reported; sustained throttling
# across a long sweep skews configurations against each other.
CLOCK_DRIFT_NOTE_THRESHOLD = 0.05


def parse_int_list(text: str) -> list[int]:
    values = [int(token) for token in text.split(",") if token.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


def parse_phase_list(text: str) -> list[str]:
    phases = [token.strip() for token in text.split(",") if token.strip()]
    unknown = [phase for phase in phases if phase not in PHASE_FILTERS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown phase(s) {', '.join(unknown)}; expected any of "
            f"{', '.join(PHASE_ORDER)}"
        )
    if not phases:
        raise argparse.ArgumentTypeError("expected at least one phase")
    return phases


def warn(message: str) -> None:
    """Diagnostics on stderr, ordered against the stdout progress log."""
    sys.stdout.flush()
    sys.stderr.write(message)
    sys.stderr.flush()


# --------------------------------------------------------------------------- #
# Planning                                                                    #
# --------------------------------------------------------------------------- #
class Run:
    """One benchmark process: its phase, axis values, filter, and output file."""

    def __init__(
        self,
        phase: str,
        out_name: str,
        workers: int,
        task_threshold: int,
        partition_threshold: int,
        narrow: str | None,
    ) -> None:
        self.phase = phase
        self.out_name = out_name
        self.workers = workers
        self.task_threshold = task_threshold
        self.partition_threshold = partition_threshold
        pattern = PHASE_FILTERS[phase]
        if narrow and phase == "baseline":
            narrow = LANES_TERM.sub("lanes=[^/]*", narrow)
        self.filter = f"{pattern}.*{narrow}" if narrow else pattern

    def label(self) -> str:
        if self.phase in ("baseline", "serial"):
            return self.phase
        if self.phase == "parallel":
            return f"parallel w={self.workers} t={self.task_threshold}"
        return (
            f"deep w={self.workers} t={self.task_threshold} "
            f"p={self.partition_threshold}"
        )


def plan_runs(args: argparse.Namespace) -> list[Run]:
    runs: list[Run] = []
    for phase in ("baseline", "serial"):
        if phase in args.phases:
            runs.append(
                Run(
                    phase,
                    f"{phase}.json",
                    args.workers[0],
                    args.task_thresholds[0],
                    args.partition_thresholds[0],
                    args.narrow,
                )
            )
    for workers in args.workers:
        for task in args.task_thresholds:
            if "parallel" in args.phases:
                runs.append(
                    Run(
                        "parallel",
                        f"parallel_w{workers}_t{task}.json",
                        workers,
                        task,
                        args.partition_thresholds[0],
                        args.narrow,
                    )
                )
            if "deep" not in args.phases:
                continue
            for partition in args.partition_thresholds:
                runs.append(
                    Run(
                        "deep",
                        f"deep_w{workers}_t{task}_p{partition}.json",
                        workers,
                        task,
                        partition,
                        args.narrow,
                    )
                )
    return runs


def run_environment(args: argparse.Namespace, run: Run) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        COSORT_COLUMNS=",".join(str(v) for v in args.columns),
        COSORT_DISTRIBUTIONS=",".join(str(v) for v in args.distributions),
        COSORT_DIRECTIONS=",".join(str(v) for v in args.directions),
        COSORT_MIN_SIZE_LEVEL=str(args.min_size_level),
        COSORT_MAX_SIZE_LEVEL=str(args.max_size_level),
        COSORT_WORKERS=str(run.workers),
        COSORT_TASK_THRESHOLD=str(run.task_threshold),
        COSORT_PARTITION_THRESHOLD=str(run.partition_threshold),
    )
    if args.memory_cap is not None:
        env["COSORT_MEMORY_CAP_BYTES"] = str(args.memory_cap)
    return env


def run_command(args: argparse.Namespace, run: Run, out_path: Path) -> list[str]:
    command = [
        str(args.exe),
        f"--benchmark_filter={run.filter}",
        f"--benchmark_out={out_path}",
        "--benchmark_out_format=json",
        f"--benchmark_min_time={args.min_time}",
    ]
    if args.repetitions > 1:
        command += [
            f"--benchmark_repetitions={args.repetitions}",
            "--benchmark_report_aggregates_only=true",
        ]
    command += args.benchmark_args
    return command


# --------------------------------------------------------------------------- #
# Running                                                                     #
# --------------------------------------------------------------------------- #
def command_run(args: argparse.Namespace) -> int:
    if not args.exe.exists():
        sys.stderr.write(
            f"benchmark executable not found: {args.exe}\n"
            "build it with:\n"
            "  cmake -S test-sort -B test-sort/build -DCMAKE_BUILD_TYPE=Release "
            "-DENABLE_GBENCH=ON\n"
            "  cmake --build test-sort/build --target benchmark_multicolumn_gbench\n"
        )
        return 2

    runs = plan_runs(args)
    if not runs:
        sys.stderr.write("every phase was skipped; nothing to run\n")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    counts = {phase: sum(1 for r in runs if r.phase == phase) for phase in PHASE_ORDER}
    print(
        f"planned {len(runs)} benchmark processes ("
        + " ".join(f"{phase}={counts[phase]}" for phase in PHASE_ORDER)
        + ")"
    )
    print(f"output directory: {args.out_dir}")

    if args.dry_run:
        for index, run in enumerate(runs, 1):
            out_path = args.out_dir / run.out_name
            print(f"\n[{index}/{len(runs)}] {run.label()}")
            print("  " + " ".join(run_command(args, run, out_path)))
        return 0

    started = time.monotonic()
    failures: list[tuple[Run, int]] = []
    skipped = 0
    for index, run in enumerate(runs, 1):
        out_path = args.out_dir / run.out_name
        if out_path.exists() and not args.overwrite:
            print(f"[{index}/{len(runs)}] {run.label()}: exists, skipping")
            skipped += 1
            continue
        print(f"[{index}/{len(runs)}] {run.label()} -> {out_path.name}", flush=True)
        command = run_command(args, run, out_path)
        completed = subprocess.run(
            command,
            env=run_environment(args, run),
            cwd=None,  # inherit; every path handed to the child is absolute
            stdout=subprocess.DEVNULL if args.quiet else None,
        )
        if completed.returncode != 0:
            failures.append((run, completed.returncode))
            warn(
                f"  failed with exit code {completed.returncode}\n"
                f"  {' '.join(command)}\n"
            )

    elapsed = time.monotonic() - started
    print(
        f"\nran {len(runs) - skipped - len(failures)} of {len(runs)} processes "
        f"in {elapsed / 60:.1f} min ({skipped} skipped, {len(failures)} failed)"
    )
    for run, code in failures:
        print(f"  failed: {run.label()} (exit {code})")

    if args.no_stitch:
        return 1 if failures else 0

    produced = sorted(
        args.out_dir / run.out_name
        for run in runs
        if (args.out_dir / run.out_name).exists()
    )
    if not produced:
        warn("no run files were produced; nothing to stitch\n")
        return 1
    merged = args.out_dir / args.merged_name
    status = stitch(produced, merged, force=args.force)
    return 1 if (failures or status != 0) else 0


# --------------------------------------------------------------------------- #
# Stitching                                                                   #
# --------------------------------------------------------------------------- #
def benchmark_identity(entry: dict) -> tuple:
    return (
        entry.get("run_name", entry.get("name", "")),
        entry.get("run_type", ""),
        entry.get("aggregate_name", ""),
        entry.get("repetition_index", -1),
        entry.get("threads", -1),
    )


def real_time_of(entry: dict) -> float:
    try:
        return float(entry["real_time"])
    except (KeyError, TypeError, ValueError):
        return float("inf")


def context_differences(first: dict, other: dict) -> list[str]:
    return [
        key
        for key in CONTEXT_IDENTITY_KEYS
        if key in first or key in other
        if first.get(key) != other.get(key)
    ]


def stitch(paths: list[Path], out_path: Path, force: bool = False) -> int:
    merged_context: dict | None = None
    reference_path: Path | None = None
    entries: dict[tuple, dict] = {}
    collapsed = 0
    unreadable: list[tuple[Path, str]] = []
    mismatched: list[tuple[Path, list[str]]] = []
    sources: list[str] = []
    clocks: list[float] = []

    for path in paths:
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            unreadable.append((path, str(error).split("\n")[0]))
            continue

        context = raw.get("context", {})
        if merged_context is None:
            merged_context = dict(context)
            reference_path = path
        else:
            differences = context_differences(merged_context, context)
            if differences:
                mismatched.append((path, differences))
                if not force:
                    continue

        # Merging an already-stitched file keeps the names of the runs it came
        # from, so provenance survives incremental accumulation.
        for name in context.get("_stitched_from", [path.name]):
            if name not in sources:
                sources.append(name)
        try:
            clocks.append(float(context["mhz_per_cpu"]))
        except (KeyError, TypeError, ValueError):
            pass
        for entry in raw.get("benchmarks", []):
            key = benchmark_identity(entry)
            previous = entries.get(key)
            if previous is None:
                entries[key] = entry
            else:
                collapsed += 1
                if real_time_of(entry) < real_time_of(previous):
                    entries[key] = entry

    if unreadable:
        warn(
            f"\nskipped {len(unreadable)} unreadable run file(s); an interrupted "
            "run leaves truncated JSON, which\n"
            "visualize_multicolumn_bench.py can still load one file at a time:\n"
            + "".join(f"  {path.name}: {reason}\n" for path, reason in unreadable)
        )

    if mismatched:
        action = "merged anyway (--force)" if force else "excluded"
        warn(
            f"\n{len(mismatched)} run file(s) disagree with {reference_path.name} "
            f"on host identity and were {action}:\n"
            + "".join(
                f"  {path.name}: {', '.join(differences)}\n"
                for path, differences in mismatched
            )
            + (
                ""
                if force
                else "  pass --force to merge across hosts; cross-configuration "
                "comparisons then mix machines\n"
            )
        )

    if len(clocks) > 1 and min(clocks) > 0:
        spread = (max(clocks) - min(clocks)) / min(clocks)
        if spread > CLOCK_DRIFT_NOTE_THRESHOLD:
            warn(
                f"\nnote: reported CPU clock varied {min(clocks):.0f}-"
                f"{max(clocks):.0f} MHz ({spread * 100:.0f}%) across runs.\n"
                "  Runs are still merged, but configurations measured at "
                "different clocks are not strictly comparable.\n"
            )

    if merged_context is None or not entries:
        warn("\nnothing to stitch\n")
        return 1

    merged_context["_stitched_from"] = sorted(sources)
    ordered = sorted(entries.values(), key=lambda e: benchmark_identity(e))
    out_path.write_text(
        json.dumps({"context": merged_context, "benchmarks": ordered}, indent=2) + "\n"
    )

    print(
        f"\nstitched {len(sources)} run file(s) into {out_path} "
        f"({len(ordered)} benchmarks"
        + (f", {collapsed} duplicate observation(s) collapsed to fastest" if collapsed else "")
        + ")"
    )
    print(f"  streamlit run visualize_multicolumn_bench.py -- --json {out_path}")
    return 1 if (unreadable or (mismatched and not force)) else 0


def command_stitch(args: argparse.Namespace) -> int:
    paths: list[Path] = []
    for target in args.inputs:
        if target.is_dir():
            # A directory rebuilds from run files: excluding the output keeps a
            # replaced run from being resurrected out of the previous merge. An
            # explicitly named merged file is kept, which is how a phase is
            # added to a finished sweep.
            paths.extend(
                path
                for path in sorted(target.glob("*.json"))
                if path.resolve() != args.out.resolve()
            )
        else:
            paths.append(target)
    if not paths:
        sys.stderr.write("no input JSON files found\n")
        return 2
    return stitch(paths, args.out, force=args.force)


# --------------------------------------------------------------------------- #
# Command line                                                                #
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="see the module docstring for the phase decomposition",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="sweep the scalar axes and stitch the result")
    run.add_argument(
        "--exe",
        type=Path,
        default=here / "build" / "benchmark_multicolumn_gbench",
        help="benchmark executable (default: %(default)s)",
    )
    run.add_argument(
        "--out-dir",
        type=Path,
        default=here / "build" / "sweep",
        help="directory for per-run and merged JSON (default: %(default)s)",
    )
    run.add_argument("--merged-name", default="merged.json", help="stitched file name")
    run.add_argument(
        "--workers",
        type=parse_int_list,
        default=[1, 2, 4, 8],
        help="comma list of worker counts (default: 1,2,4,8)",
    )
    run.add_argument(
        "--task-thresholds",
        type=parse_int_list,
        default=[4096],
        help="comma list of next-column task thresholds (default: 4096)",
    )
    run.add_argument(
        "--partition-thresholds",
        type=parse_int_list,
        default=[4096, 16384, 65536],
        help="comma list of partition thresholds (default: 4096,16384,65536)",
    )
    run.add_argument("--columns", type=parse_int_list, default=[1, 2, 3])
    run.add_argument("--distributions", type=parse_int_list, default=[0, 4, 6, 7])
    run.add_argument("--directions", type=parse_int_list, default=[0])
    run.add_argument("--min-size-level", type=int, default=1)
    run.add_argument("--max-size-level", type=int, default=3)
    run.add_argument("--memory-cap", type=int, default=None, help="COSORT_MEMORY_CAP_BYTES")
    run.add_argument(
        "--narrow",
        default=None,
        help="extra regex appended to each phase filter, e.g. 'u32/lanes=16'",
    )
    run.add_argument("--min-time", default="0.2s", help="--benchmark_min_time")
    run.add_argument("--repetitions", type=int, default=1, help="--benchmark_repetitions")
    run.add_argument(
        "--phases",
        type=parse_phase_list,
        default=list(PHASE_ORDER),
        help="comma list of %s (default: all). Use 'baseline' alone to add the "
        "scalar reference to a sweep that already ran." % ",".join(PHASE_ORDER),
    )
    run.add_argument(
        "--overwrite",
        action="store_true",
        help="rerun configurations whose JSON already exists (default: resume)",
    )
    run.add_argument("--dry-run", action="store_true", help="print commands only")
    run.add_argument("--quiet", action="store_true", help="discard benchmark stdout")
    run.add_argument("--no-stitch", action="store_true", help="skip the merge step")
    run.add_argument("--force", action="store_true", help="stitch across host mismatch")
    run.add_argument(
        "benchmark_args",
        nargs="*",
        help="extra arguments forwarded to the benchmark executable",
    )
    run.set_defaults(handler=command_run)

    stitch_parser = sub.add_parser("stitch", help="merge run JSON files into one sweep")
    stitch_parser.add_argument(
        "inputs", nargs="+", type=Path, help="JSON files, or directories of them"
    )
    stitch_parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=here / "build" / "sweep" / "merged.json",
        help="stitched output path (default: %(default)s)",
    )
    stitch_parser.add_argument(
        "--force", action="store_true", help="merge despite host mismatch"
    )
    stitch_parser.set_defaults(handler=command_stitch)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Resolve every path argument before any handler runs. The benchmark child
    # process inherits this cwd, but a relative --out-dir typed against a
    # different cwd would otherwise reach Google Benchmark unresolved, and it
    # reports a failed --benchmark_out open as "invalid file name" and exits 1
    # rather than creating the directory.
    for name in ("exe", "out_dir", "out"):
        value = getattr(args, name, None)
        if isinstance(value, Path):
            setattr(args, name, value.expanduser().resolve())
    inputs = getattr(args, "inputs", None)
    if inputs is not None:
        args.inputs = [path.expanduser().resolve() for path in inputs]
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
