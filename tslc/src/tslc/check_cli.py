"""Implementation of the first-class ``tslc check`` authoring command."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys
import time
from typing import Any

from tslc.api import _expand_sources, generate_project
from tslc.authoring import check_catalog
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.diagnostics import Diagnostic, has_errors
from tslc.project_config import ProjectConfig, load_project_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc check",
        description="Validate a complete TSL corpus without rendering or writing artifacts.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="show diagnostics only for these files/directories; the complete corpus is loaded",
    )
    parser.add_argument("--config", help="path to tslc.toml (discovered by default)")
    parser.add_argument("--sources", nargs="+", help="complete corpus roots")
    parser.add_argument("--machine-profiles", help="path to machine_profiles.json")
    parser.add_argument("--primitive", action="append", default=[])
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--type", action="append", dest="type_tags", default=[])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument(
        "--watch-interval",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    try:
        config = load_project_config(args.config)
        settings = _settings(args, config)
    except ValueError as exc:
        parser.error(str(exc))
    if args.watch_interval <= 0:
        parser.error("--watch-interval must be greater than zero")

    status = _run_once(settings, args)
    if not args.watch:
        return status
    fingerprint = _fingerprint(settings.sources, settings.machine_profiles)
    try:
        while True:
            time.sleep(args.watch_interval)
            current = _fingerprint(settings.sources, settings.machine_profiles)
            if current == fingerprint:
                continue
            fingerprint = current
            if args.format == "text":
                print("\nchange detected; checking again")
            status = _run_once(settings, args)
    except KeyboardInterrupt:
        return 130


class _Settings:
    def __init__(
        self,
        sources: tuple[Path, ...],
        machine_profiles: Path | None,
        backends: tuple[str, ...],
    ) -> None:
        self.sources = sources
        self.machine_profiles = machine_profiles
        self.backends = backends


def _settings(args: argparse.Namespace, config: ProjectConfig | None) -> _Settings:
    if args.sources:
        sources = tuple(Path(value) for value in args.sources)
    elif config is not None:
        sources = config.sources
    else:
        raise ValueError("no corpus configured; pass --sources or create tslc.toml")
    backends = tuple(args.backend) or (
        config.backends if config is not None else ("cpp", "rust")
    )
    machine_profiles = (
        Path(args.machine_profiles)
        if args.machine_profiles
        else config.machine_profiles
        if config is not None
        else None
    )
    if _slot_requested(args) and machine_profiles is None:
        raise ValueError(
            "slot-aware checks require --machine-profiles or a tslc.toml setting"
        )
    return _Settings(sources, machine_profiles, backends)


def _slot_requested(args: argparse.Namespace) -> bool:
    return bool(args.primitive or args.profile or args.backend or args.type_tags)


def _run_once(settings: _Settings, args: argparse.Namespace) -> int:
    filters = tuple(Path(value).resolve() for value in args.paths)
    skipped_payload: list[dict[str, object]] = []
    if _slot_requested(args):
        assert settings.machine_profiles is not None
        generation = generate_project(
            settings.sources,
            machine_profiles_path=settings.machine_profiles,
            primitives=args.primitive or None,
            profiles=args.profile or None,
            type_tags=args.type_tags or DEFAULT_SCALAR_TYPE_TAGS,
            backends=settings.backends,
            generation_mode="strict",
            render_artifacts=False,
        )
        diagnostics = generation.diagnostics
        skipped_payload = [
            {
                "profile": item.profile,
                "backend": item.backend,
                "primitive": item.primitive,
                "extension": item.extension,
                "type": item.type_tag,
                "reason": item.reason,
            }
            for item in generation.skipped
        ]
        payload: dict[str, Any] = {
            "mode": "slots",
            "coverage": len(generation.coverage),
            "skipped": skipped_payload,
        }
        failed = has_errors(diagnostics) or bool(generation.skipped)
    else:
        catalog_check = check_catalog(settings.sources, backends=settings.backends)
        diagnostics = catalog_check.diagnostics
        payload = {"mode": "catalog", "sources": len(catalog_check.source_paths)}
        failed = has_errors(diagnostics)
    shown = tuple(item for item in diagnostics if _matches(item, filters))
    hidden = len(diagnostics) - len(shown)
    payload.update(
        {
            "status": "error" if failed else "ok",
            "diagnostics": [_diagnostic_json(item) for item in shown],
            "hidden_diagnostics": hidden,
        }
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for diagnostic in shown:
            print(_diagnostic_text(diagnostic), file=sys.stderr)
        if hidden:
            print(
                f"{hidden} diagnostic(s) outside the requested paths were hidden",
                file=sys.stderr,
            )
        if payload["mode"] == "slots":
            print(
                f"{'failed' if failed else 'ok'}: checked {payload['coverage']} lowered "
                f"slot(s), {len(skipped_payload)} unsupported"
            )
        else:
            print(
                f"{'failed' if failed else 'ok'}: checked {payload['sources']} TSL source file(s)"
            )
    return 1 if failed else 0


def _matches(diagnostic: Diagnostic, filters: tuple[Path, ...]) -> bool:
    if not filters or diagnostic.location is None:
        return True
    path = diagnostic.location.path.resolve()
    return any(path == item or item in path.parents for item in filters)


def _diagnostic_text(diagnostic: Diagnostic) -> str:
    location = diagnostic.location
    at = (
        ""
        if location is None
        else f" {location.path}:{location.line}:{location.column}"
    )
    return f"[{diagnostic.severity}] {diagnostic.code}{at}: {diagnostic.message}"


def _diagnostic_json(diagnostic: Diagnostic) -> dict[str, object]:
    location = diagnostic.location
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "location": (
            None
            if location is None
            else {
                "path": str(location.path),
                "line": location.line,
                "column": location.column,
            }
        ),
    }


def _fingerprint(
    sources: Sequence[Path], machine_profiles: Path | None
) -> tuple[tuple[str, int, int], ...]:
    paths = list(_expand_sources(sources))
    if machine_profiles is not None:
        paths.append(machine_profiles)
    values: list[tuple[str, int, int]] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            stat = path.stat()
        except OSError:
            values.append((str(path.resolve()), -1, -1))
        else:
            values.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    return tuple(values)


if __name__ == "__main__":
    raise SystemExit(main())
