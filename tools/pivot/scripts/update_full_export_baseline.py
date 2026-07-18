#!/usr/bin/env python3
"""Regenerate the reviewed full-corpus PIVOT coverage manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(_REPOSITORY_ROOT / "tools" / "pivot" / "src"),
    str(_REPOSITORY_ROOT / "tslc" / "src"),
]

from tslc.diagnostics import format_diagnostic  # noqa: E402
from tslc_pivot.baseline import (  # noqa: E402
    build_full_export_manifest,
    canonical_full_export,
    update_full_export_baseline,
)
from tslc_pivot.exporter import export_pivot  # noqa: E402


_BASELINE_PATH = (
    _REPOSITORY_ROOT
    / "tools"
    / "pivot"
    / "tests"
    / "baselines"
    / "full_export.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the guarded full-corpus PIVOT coverage baseline."
    )
    parser.add_argument(
        "--allow-reviewed-incompatible-baseline",
        action="store_true",
        help=(
            "allow removed definitions or replaced direct hashes after an explicit "
            "product or correctness review"
        ),
    )
    args = parser.parse_args(argv)

    run = canonical_full_export(_REPOSITORY_ROOT)
    result = export_pivot(run.request)
    for diagnostic in result.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if result.diagnostics:
        return 1

    manifest = build_full_export_manifest(run, result)
    try:
        update_full_export_baseline(
            _BASELINE_PATH,
            manifest,
            allow_reviewed_incompatible_baseline=(
                args.allow_reviewed_incompatible_baseline
            ),
        )
    except ValueError as exc:
        print(f"refused baseline update: {exc}", file=sys.stderr)
        return 2
    summary = manifest["summary"]
    assert isinstance(summary, dict)
    print(
        f"wrote {_BASELINE_PATH.relative_to(_REPOSITORY_ROOT)}: "
        f"{summary['documents']} documents, "
        f"{summary['definitions']} definitions, "
        f"{summary['skips']} skips"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
