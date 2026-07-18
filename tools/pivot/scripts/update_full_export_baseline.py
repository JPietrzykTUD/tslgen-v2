#!/usr/bin/env python3
"""Regenerate the reviewed production and typed-body manifests."""

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
    build_body_census_manifest,
    build_full_export_manifest,
    canonical_full_export,
    update_pivot_baselines,
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
_BODY_BASELINE_PATH = (
    _REPOSITORY_ROOT
    / "tools"
    / "pivot"
    / "tests"
    / "baselines"
    / "body_census.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the guarded full-corpus PIVOT baselines."
    )
    parser.add_argument(
        "--allow-reviewed-incompatible-baseline",
        action="store_true",
        help=(
            "allow removed definitions, replaced direct hashes, or changed typed-"
            "body facts after an explicit product or correctness review"
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
    body_manifest = build_body_census_manifest(
        result,
        source_root=_REPOSITORY_ROOT,
    )
    try:
        update_pivot_baselines(
            _BASELINE_PATH,
            manifest,
            _BODY_BASELINE_PATH,
            body_manifest,
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
    body_summary = body_manifest["summary"]
    assert isinstance(body_summary, dict)
    print(
        f"wrote {_BODY_BASELINE_PATH.relative_to(_REPOSITORY_ROOT)}: "
        f"{body_summary['entries']} entries, "
        f"{body_summary['failures']} failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
