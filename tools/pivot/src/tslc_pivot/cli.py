"""Command-line entry for the isolated PIVOT YAML exporter."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import shlex
import sys
from pathlib import Path

from tslc.api import write_artifacts
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.project_config import (
    ProjectConfig,
    discover_config,
    load_project_config,
)
from tslc.sources import expand_source_paths
from tslc_pivot.exporter import PivotExportRequest, export_pivot
from tslc_pivot.model import PivotLanguage, PivotSkip


@dataclass(frozen=True, slots=True)
class PivotCliInvocation:
    """One resolved standalone invocation and the argv that produced it."""

    argv: tuple[str, ...]
    request: PivotExportRequest
    output_root: Path
    source_roots: tuple[Path, ...]
    project_config_path: Path | None
    strict: bool
    show_skips: bool

    @property
    def command(self) -> str:
        return render_cli_command(self.argv)


def main(argv: list[str] | None = None) -> int:
    invocation = resolve_cli_invocation(
        tuple(sys.argv[1:] if argv is None else argv),
        working_directory=Path.cwd(),
    )

    result = export_pivot(invocation.request)
    for diagnostic in result.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if invocation.show_skips or invocation.strict:
        for skip in result.skipped:
            print(_format_skip(skip), file=sys.stderr)
    if has_errors(result.diagnostics) or (
        invocation.strict and result.skipped
    ):
        return 1

    report = write_artifacts(
        result.artifacts,
        invocation.output_root,
        mode="overwrite",
    )
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


def resolve_cli_invocation(
    argv: Sequence[str],
    *,
    working_directory: Path,
) -> PivotCliInvocation:
    """Parse and resolve argv exactly as the standalone command does."""

    parser = _parser()
    normalized_argv = tuple(argv)
    args = parser.parse_args(normalized_argv)
    root = working_directory.resolve()

    try:
        config_value = (
            discover_config(root)
            if args.config is None
            else _required_argument_path(args.config, root)
        )
        project = (
            None
            if config_value is None
            else load_project_config(config_value)
        )
        source_roots, source_paths, machine_profiles_path = _compiler_inputs(
            args.sources,
            args.machine_profiles,
            project,
            root,
        )
        languages = _languages(args.language)
    except ValueError as exc:
        parser.error(str(exc))

    return PivotCliInvocation(
        argv=normalized_argv,
        request=PivotExportRequest(
            source_paths=source_paths,
            machine_profiles_path=machine_profiles_path,
            languages=languages,
            primitives=_split_optional(args.primitives),
            profiles=_split_optional(args.profiles),
            type_tags=_split(args.types),
        ),
        output_root=_required_argument_path(args.output_root, root),
        source_roots=source_roots,
        project_config_path=None if project is None else project.path,
        strict=args.strict,
        show_skips=args.show_skips,
    )


def render_cli_command(argv: Sequence[str]) -> str:
    """Render the executable name and argv without maintaining a second form."""

    return shlex.join(("tslc-pivot", *argv))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tslc-pivot",
        description=(
            "Export the strict, inlineable PIVOT dataflow subset as deterministic YAML."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="path to tslc.toml; defaults to discovery from the current directory",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="complete TSL source roots or files; defaults to tslc.toml",
    )
    parser.add_argument(
        "--machine-profiles",
        default=None,
        help="path to machine_profiles.json; defaults to tslc.toml",
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
    return parser


def _split(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _compiler_inputs(
    source_values: list[str] | None,
    machine_profiles_value: str | None,
    project: ProjectConfig | None,
    working_directory: Path,
) -> tuple[tuple[Path, ...], tuple[Path, ...], Path]:
    source_roots = (
        tuple(
            _required_argument_path(value, working_directory)
            for value in source_values
        )
        if source_values is not None
        else (() if project is None else project.sources)
    )
    if not source_roots:
        raise ValueError(
            "--sources is required when no tslc.toml supplies tslc.sources"
        )
    machine_profiles = (
        _required_argument_path(machine_profiles_value, working_directory)
        if machine_profiles_value is not None
        else (None if project is None else project.machine_profiles)
    )
    if machine_profiles is None:
        raise ValueError(
            "--machine-profiles is required when no tslc.toml supplies "
            "tslc.machine_profiles"
        )
    return source_roots, expand_source_paths(source_roots), machine_profiles


def _required_argument_path(value: str, working_directory: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (working_directory / path).resolve()


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


__all__ = (
    "PivotCliInvocation",
    "main",
    "render_cli_command",
    "resolve_cli_invocation",
)
