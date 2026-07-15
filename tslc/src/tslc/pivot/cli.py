"""Command-line entry for the isolated PIVOT YAML exporter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tslc.api import _expand_sources
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.output.writer import write_artifacts
from tslc.pivot.exporter import PivotExportRequest, export_pivot
from tslc.pivot.model import PivotLanguage, PivotSkip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc export pivot",
        description=(
            "Export the strict, inlineable PIVOT dataflow subset as deterministic YAML."
        ),
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="complete TSL source roots or files",
    )
    parser.add_argument(
        "--machine-profiles",
        required=True,
        help="path to machine_profiles.json",
    )
    parser.add_argument(
        "--primitives",
        default=None,
        help="comma-separated primitive names; omit for the complete corpus",
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help="comma-separated machine profiles; omit for every loaded profile",
    )
    parser.add_argument(
        "--types",
        default=",".join(DEFAULT_SCALAR_TYPE_TAGS),
        help="comma-separated scalar type tags",
    )
    parser.add_argument(
        "--language",
        required=True,
        help="comma-separated output languages: cpp,rust",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="root directory for per-language PIVOT YAML trees",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when any selected specialization is outside the PIVOT subset",
    )
    parser.add_argument(
        "--show-skips",
        action="store_true",
        help="print every skipped specialization and its reason",
    )
    args = parser.parse_args(argv)

    try:
        languages = _languages(args.language)
    except ValueError as exc:
        parser.error(str(exc))

    result = export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources(tuple(Path(path) for path in args.sources)),
            machine_profiles_path=Path(args.machine_profiles),
            languages=languages,
            primitives=_split_optional(args.primitives),
            profiles=_split_optional(args.profiles),
            type_tags=_split(args.types),
        )
    )
    for diagnostic in result.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if args.show_skips or args.strict:
        for skip in result.skipped:
            print(_format_skip(skip), file=sys.stderr)
    if has_errors(result.diagnostics) or (args.strict and result.skipped):
        return 1

    report = write_artifacts(result.artifacts, args.output_root, mode="overwrite")
    for diagnostic in report.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if has_errors(report.diagnostics):
        return 1
    file_count = sum(len(item.documents) for item in result.projections)
    definition_count = sum(
        len(document.definitions)
        for item in result.projections
        for document in item.documents
    )
    print(
        f"exported {file_count} "
        "PIVOT YAML files for "
        f"{','.join(item.language.value for item in result.projections)} with "
        f"{definition_count} definitions; "
        f"skipped {len(result.skipped)} specializations"
    )
    return 0


def _split(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _split_optional(value: str | None) -> tuple[str, ...] | None:
    return None if value is None else _split(value)


def _languages(value: str) -> tuple[PivotLanguage, ...]:
    names = _split(value)
    if not names:
        raise ValueError("--language requires at least one language")
    unknown = sorted(set(names) - {item.value for item in PivotLanguage})
    if unknown:
        raise ValueError(f"unsupported PIVOT language(s): {', '.join(unknown)}")
    return tuple(PivotLanguage(name) for name in dict.fromkeys(names))


def _format_skip(skip: PivotSkip) -> str:
    location = (
        ""
        if skip.source is None
        else f" at {skip.source.path}:{skip.source.line}:{skip.source.column}"
    )
    return (
        f"[pivot-skip] {skip.language.value}/{skip.profile}/{skip.primitive}<"
        f"{skip.extension},{skip.type_tag}>: {skip.reason}{location}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
