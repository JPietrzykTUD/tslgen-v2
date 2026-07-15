#!/usr/bin/env python3
"""Inspect coverage or maintain the canonical primitive coverage report.

The default command is read-only and reports the configured corpus, profiles,
types, and backends. ``--update`` and ``--check`` deliberately use the stable
repository-wide canonical probe so the committed report remains reproducible.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.authoring import check_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.diagnostics import Diagnostic, format_diagnostic, has_errors
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
from tslc.project_config import ProjectConfig, load_project_config


PROFILES = ("scalar", "sse2", "avx", "avx2", "skylake", "icelake_rockerlake")


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_DATA_ROOT = _REPO_ROOT / "tsldata"
_PROFILES_PATH = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
_BUILD_TEST = _REPO_ROOT / "tslc" / "tests" / "test_build_verify.py"
_OUT = _REPO_ROOT / "coverage" / "primitive-coverage-inventory.md"


def _has_skip_decorator(fn: ast.FunctionDef) -> bool:
    """Return whether a test function is explicitly skipped."""

    for decorator in fn.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        while isinstance(target, ast.Attribute):
            if target.attr == "skip":
                return True
            target = target.value
    return False


def _build_verified_primitives() -> frozenset[str]:
    """Primitive names covered by at least one non-skipped generated build test."""

    tree = ast.parse(_BUILD_TEST.read_text(encoding="utf-8"))
    verified: set[str] = set()
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef) or _has_skip_decorator(fn):
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "primitives"
                and isinstance(node.value, ast.List)
            ):
                verified.update(
                    element.value
                    for element in node.value.elts
                    if isinstance(element, ast.Constant)
                    and isinstance(element.value, str)
                )
    return frozenset(verified)


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

    sources: tuple[Path, ...]
    profiles: tuple[str, ...] | None
    maintenance_mode = args.update or args.check
    if maintenance_mode:
        _reject_custom_canonical_scope(args, parser)
        sources = (_DATA_ROOT,)
        machine_profiles = _PROFILES_PATH
        profiles = PROFILES
        backends = registered_backend_ids()
        type_tags = _ARITH_TYPE_TAGS
    else:
        if args.output is not None:
            parser.error("--output requires --update or --check")
        try:
            project = load_project_config(args.config)
            sources, machine_profiles, backends = _configured_scope(args, project)
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

    if args.check or args.update:
        output = Path(args.output) if args.output else _OUT
        rendered = render_markdown(inventory, tracked=True)
        if args.check:
            current = output.read_text(encoding="utf-8") if output.is_file() else None
            if current != rendered:
                print(f"coverage inventory is stale: {output}", file=sys.stderr)
                return 1
            print(f"coverage inventory is current: {_display_path(output)}")
            return 0
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {_display_path(output)}")
        return 0

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
    """Load configured inputs, run lowering only, and calculate the inventory."""

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
            verified_primitives=_build_verified_primitives(),
        ),
        (),
    )


def _configured_scope(
    args: argparse.Namespace,
    project: ProjectConfig | None,
) -> tuple[tuple[Path, ...], Path, tuple[str, ...]]:
    sources = (
        tuple(Path(item) for item in args.sources)
        if args.sources
        else project.sources
        if project is not None
        else (_DATA_ROOT,)
    )
    machine_profiles = (
        Path(args.machine_profiles)
        if args.machine_profiles
        else project.machine_profiles
        if project is not None
        else _PROFILES_PATH
    )
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


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(_REPO_ROOT)
    except ValueError:
        return path


__all__ = (
    "PROFILES",
    "collect_inventory",
    "main",
    "skip_category",
)


if __name__ == "__main__":
    raise SystemExit(main())
