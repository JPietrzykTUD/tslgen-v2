#!/usr/bin/env python3
"""Inspect coverage or maintain the canonical primitive coverage report.

The default command is read-only and reports the configured corpus, profiles,
types, and backends. ``--update`` and ``--check`` deliberately use the stable
repository-wide canonical probe so the committed report remains reproducible.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.authoring import check_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.diagnostics import Diagnostic, format_diagnostic, has_errors
from tslc.maintenance.build_verified import build_verified_primitives
from tslc.maintenance.coverage_inventory_report import (
    CoverageInventory,
    build_coverage_inventory,
    skip_category,
)
from tslc.maintenance.coverage_inventory_render import (
    render_json,
    render_markdown,
    render_text,
)
from tslc.maintenance import _repo_context
from tslc.maintenance._repo_context import RepoContext
from tslc.project_config import ProjectConfig, load_project_config


PROFILES = ("scalar", "sse2", "avx", "avx2", "skylake", "icelake_rockerlake")


def canonical_report_path(context: RepoContext) -> Path:
    """The tracked Markdown report maintained by ``--update``/``--check``."""

    return context.coverage_root / "primitive-coverage-inventory.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc coverage inventory",
        description="Inspect configured specialization coverage.",
    )
    parser.add_argument("--config", help="path to tslc.toml (discovered by default)")
    parser.add_argument("--sources", nargs="+", help="complete corpus roots")
    parser.add_argument("--machine-profiles", help="path to machine_profiles.json")
    parser.add_argument("--profiles", help="comma-separated profile names")
    parser.add_argument("--backends", help="comma-separated backend IDs")
    parser.add_argument("--types", help="comma-separated scalar type tags")
    parser.add_argument(
        "--format", choices=("text", "markdown", "json"), default="text"
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--update",
        action="store_true",
        help="rewrite the canonical tracked Markdown report",
    )
    actions.add_argument(
        "--check",
        action="store_true",
        help="fail if the canonical tracked Markdown report is stale",
    )
    parser.add_argument(
        "--output",
        help="tracked report path for --update or --check",
    )
    args = parser.parse_args(argv)

    if args.update or args.check:
        _reject_custom_canonical_scope(args, parser)
        return _run_canonical(args, parser)
    if args.output is not None:
        parser.error("--output requires --update or --check")
    return _run_report(args, parser)


def _run_canonical(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Maintain the tracked report over the stable repository-wide scope."""

    context = _repo_context.require_repo_context(parser)
    inventory, errors = collect_inventory(
        sources=(context.data_root,),
        machine_profiles=context.machine_profiles_path,
        profiles=PROFILES,
        backends=registered_backend_ids(),
        type_tags=_ARITH_TYPE_TAGS,
    )
    if inventory is None:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else canonical_report_path(context)
    rendered = render_markdown(inventory, tracked=True)
    if args.check:
        current = output.read_text(encoding="utf-8") if output.is_file() else None
        if current != rendered:
            print(f"coverage inventory is stale: {output}", file=sys.stderr)
            return 1
        print(f"coverage inventory is current: {_display_path(output, context.root)}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"wrote {_display_path(output, context.root)}")
    return 0


def _run_report(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Print a read-only inventory over the configured corpus scope."""

    sources: tuple[Path, ...]
    try:
        project = load_project_config(args.config)
        sources, machine_profiles, backends = _configured_scope(args, project, parser)
        profiles = _csv(args.profiles) if args.profiles else None
        type_tags = _csv(args.types) if args.types else _ARITH_TYPE_TAGS
    except ValueError as exc:
        parser.error(str(exc))

    inventory, errors = collect_inventory(
        sources=sources,
        machine_profiles=machine_profiles,
        profiles=profiles,
        backends=backends,
        type_tags=type_tags,
    )
    if inventory is None:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    renderer = {
        "text": render_text,
        "markdown": render_markdown,
        "json": render_json,
    }[args.format]
    print(renderer(inventory), end="")
    return 0


def collect_inventory(
    *,
    sources: tuple[Path, ...],
    machine_profiles: Path,
    profiles: tuple[str, ...] | None,
    backends: tuple[str, ...],
    type_tags: tuple[str, ...],
) -> tuple[CoverageInventory | None, tuple[str, ...]]:
    """Load configured inputs, run lowering only, and calculate the inventory.

    Build-verification evidence comes from the typed
    ``tslc.maintenance.build_verified`` constant the generated-build tests
    consume, so no checkout probing is required.
    """

    catalog_result = check_catalog(sources, backends=backends)
    if catalog_result.catalog is None or has_errors(catalog_result.diagnostics):
        return None, _diagnostic_lines(catalog_result.diagnostics)
    catalog = catalog_result.catalog
    loaded_profiles = load_machine_profiles_checked(
        machine_profiles, catalog.target_families
    )
    if has_errors(loaded_profiles.diagnostics):
        return None, _diagnostic_lines(loaded_profiles.diagnostics)
    selected_profiles = (
        profiles if profiles is not None else tuple(sorted(loaded_profiles.profiles))
    )
    unknown = tuple(name for name in selected_profiles if name not in loaded_profiles.profiles)
    if unknown:
        known = ", ".join(sorted(loaded_profiles.profiles))
        return None, (
            f"unknown profile(s): {', '.join(unknown)}; known profiles: {known}",
        )
    selected_profile_models = tuple(
        loaded_profiles.profiles[name] for name in selected_profiles
    )

    result = generate_project(
        sources,
        machine_profiles_path=machine_profiles,
        profiles=selected_profiles,
        type_tags=type_tags,
        backends=backends,
        render_artifacts=False,
    )
    if has_errors(result.diagnostics):
        return None, _diagnostic_lines(result.diagnostics)
    return (
        build_coverage_inventory(
            catalog,
            result,
            machine_profiles=selected_profile_models,
            backends=backends,
            type_tags=type_tags,
            verified_primitives=build_verified_primitives(),
        ),
        (),
    )


def _configured_scope(
    args: argparse.Namespace,
    project: ProjectConfig | None,
    parser: argparse.ArgumentParser,
) -> tuple[tuple[Path, ...], Path, tuple[str, ...]]:
    """Resolve corpus paths, requiring a checkout only as the last fallback."""

    fallback: RepoContext | None = None
    if args.sources:
        sources = tuple(Path(item) for item in args.sources)
    elif project is not None:
        sources = project.sources
    else:
        fallback = _repo_context.require_repo_context(parser)
        sources = (fallback.data_root,)
    if args.machine_profiles:
        machine_profiles = Path(args.machine_profiles)
    elif project is not None:
        machine_profiles = project.machine_profiles
    else:
        if fallback is None:
            fallback = _repo_context.require_repo_context(parser)
        machine_profiles = fallback.machine_profiles_path
    backends = (
        _csv(args.backends)
        if args.backends
        else project.backends
        if project is not None
        else registered_backend_ids()
    )
    if not sources:
        raise ValueError("no corpus configured; pass --sources or create tslc.toml")
    if not backends:
        raise ValueError("at least one backend is required")
    return sources, machine_profiles, backends


def _reject_custom_canonical_scope(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    custom = tuple(
        option
        for option, value in (
            ("--config", args.config),
            ("--sources", args.sources),
            ("--machine-profiles", args.machine_profiles),
            ("--profiles", args.profiles),
            ("--backends", args.backends),
            ("--types", args.types),
        )
        if value is not None
    )
    if custom:
        parser.error(
            f"{'/'.join(custom)} cannot be combined with --update or --check; "
            "tracked reports use the canonical repository scope"
        )
    if args.format != "text":
        parser.error("--format cannot be combined with --update or --check")


def _csv(value: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise ValueError("comma-separated option must contain at least one value")
    return items


def _diagnostic_lines(diagnostics: tuple[Diagnostic, ...]) -> tuple[str, ...]:
    return tuple(
        format_diagnostic(diagnostic)
        for diagnostic in diagnostics
        if diagnostic.severity == "error"
    )


def _display_path(path: Path, repo_root: Path) -> Path:
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path


__all__ = (
    "PROFILES",
    "canonical_report_path",
    "collect_inventory",
    "main",
    "skip_category",
)


if __name__ == "__main__":
    raise SystemExit(main())
