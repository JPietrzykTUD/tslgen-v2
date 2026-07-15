"""Measure the Version 1 authoring latency contracts on a configured corpus."""

from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from tslc.lsp.features import completions, hover
from tslc.lsp.positions import span_to_range
from tslc.lsp.workspace import AuthoringWorkspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tslc.maintenance.authoring_benchmark",
        description=(
            "Measure cold authoring, cached edit, hover, completion, and preview latency."
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--edits", type=int, default=20)
    parser.add_argument("--hovers", type=int, default=200)
    parser.add_argument("--completions", type=int, default=200)
    parser.add_argument("--primitive", default="add")
    parser.add_argument("--profile", default="avx2")
    parser.add_argument("--extension", default="avx2")
    parser.add_argument("--type", dest="type_tag", default="si32")
    parser.add_argument("--backend", default="cpp")
    args = parser.parse_args(argv)
    if args.edits < 1 or args.hovers < 1 or args.completions < 1:
        parser.error("--edits, --hovers, and --completions must be positive")

    root = args.root.resolve()
    workspace = AuthoringWorkspace.from_root(root)
    started = perf_counter()
    initial = workspace.check()
    cold_seconds = perf_counter() - started
    if initial is None or initial.index is None:
        parser.error("initial corpus check did not produce an index")

    reference = next(
        span
        for spans in initial.index.primitive_references.values()
        for span in spans
    )
    path = reference.path
    original = path.read_text(encoding="utf-8")
    edit_seconds: list[float] = []
    snapshot = initial
    for iteration in range(args.edits):
        generation = workspace.open(
            path,
            original + f"\n# authoring benchmark {iteration}\n",
            iteration + 1,
        )
        started = perf_counter()
        checked = workspace.check(generation)
        edit_seconds.append(perf_counter() - started)
        if checked is None or checked.index is None:
            parser.error("benchmark edit did not produce an index")
        snapshot = checked

    text = workspace.document_text(reference.path)
    assert text is not None
    position = span_to_range(reference, text).start
    hover_seconds: list[float] = []
    for _ in range(args.hovers):
        started = perf_counter()
        hovered = hover(snapshot.index, reference.path, text, position)
        hover_seconds.append(perf_counter() - started)
        if hovered is None:
            parser.error("benchmark reference did not produce hover content")

    completion_seconds: list[float] = []
    for _ in range(args.completions):
        started = perf_counter()
        completed = completions(snapshot, reference.path, text, position)
        completion_seconds.append(perf_counter() - started)
        if not completed.items:
            parser.error("benchmark reference did not produce completion items")

    workspace.close_document(path)
    command = [
        sys.executable,
        "-m",
        "tslc",
        "preview",
        "--primitive",
        args.primitive,
        "--profile",
        args.profile,
        "--extension",
        args.extension,
        "--type",
        args.type_tag,
        "--backend",
        args.backend,
    ]
    started = perf_counter()
    preview = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    preview_seconds = perf_counter() - started
    if preview.returncode != 0:
        parser.error(f"preview failed: {preview.stderr.strip()}")

    print(
        json.dumps(
            {
                "schema_version": 1,
                "corpus_files": len(initial.source_paths),
                "cold_check_seconds": round(cold_seconds, 6),
                "edit_p95_seconds": round(_percentile(edit_seconds, 0.95), 6),
                "hover_p95_seconds": round(_percentile(hover_seconds, 0.95), 6),
                "completion_p95_seconds": round(
                    _percentile(completion_seconds, 0.95),
                    6,
                ),
                "preview_seconds": round(preview_seconds, 6),
                "samples": {
                    "edits": args.edits,
                    "hovers": args.hovers,
                    "completions": args.completions,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(ceil(len(ordered) * fraction) - 1, 0)]


if __name__ == "__main__":
    raise SystemExit(main())
