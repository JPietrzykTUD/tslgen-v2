"""Focused catalog discovery for authors and completion clients."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tslc.authoring import check_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS, SCALAR_TYPE_INFOS
from tslc.diagnostics import Diagnostic, SourceSpan, format_diagnostic, has_errors
from tslc.ir.region_registry import (
    DEFAULT_TSIL_REGION_DESCRIPTORS,
    TSIL_REGION_BY_KEYWORD,
    TsilRegionDescriptor,
)
from tslc.project_config import ProjectConfig, load_project_config

_KINDS = (
    "primitives",
    "profiles",
    "extensions",
    "types",
    "type-groups",
    "backends",
    "regions",
)
_SHOW_KINDS = ("primitive", "profile", "extension", "type", "type-group", "backend", "region")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc catalog", description="List and describe typed TSL catalog entries."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    list_parser = subparsers.add_parser(
        "list", help="list catalog names", prog="tslc list"
    )
    _add_common_arguments(list_parser)
    list_parser.add_argument("kind", choices=_KINDS)
    show_parser = subparsers.add_parser(
        "show", help="describe one catalog entry", prog="tslc show"
    )
    _add_common_arguments(show_parser)
    show_parser.add_argument("kind", choices=_SHOW_KINDS)
    show_parser.add_argument("name")
    args = parser.parse_args(argv)
    try:
        config = load_project_config(args.config)
        sources, machine_profiles, backends = _settings(args, config)
    except ValueError as exc:
        parser.error(str(exc))

    result = check_catalog(sources, backends=backends)
    if result.catalog is None or has_errors(result.diagnostics):
        _print_diagnostics(result.diagnostics)
        return 1
    profiles: dict[str, MachineProfile] = {}
    if args.kind in ("profiles", "profile"):
        if machine_profiles is None:
            parser.error("profiles require --machine-profiles or tslc.toml")
        loaded = load_machine_profiles_checked(
            machine_profiles, result.catalog.target_families
        )
        if has_errors(loaded.diagnostics):
            _print_diagnostics(loaded.diagnostics)
            return 1
        profiles = dict(loaded.profiles)

    if args.action == "list":
        output = _list_payload(result.catalog, profiles, args.kind)
    else:
        shown = _show_payload(result.catalog, profiles, args.kind, args.name)
        if shown is None:
            print(f"no {args.kind} named {args.name!r}", file=sys.stderr)
            return 1
        output = shown
    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(_text(output))
    return 0


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="path to tslc.toml (discovered by default)")
    parser.add_argument("--sources", nargs="+", help="complete corpus roots")
    parser.add_argument("--machine-profiles", help="path to machine_profiles.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")


def _settings(
    args: argparse.Namespace, config: ProjectConfig | None
) -> tuple[tuple[Path, ...], Path | None, tuple[str, ...]]:
    sources = (
        tuple(Path(item) for item in args.sources)
        if args.sources
        else config.sources
        if config is not None
        else ()
    )
    if not sources:
        raise ValueError("no corpus configured; pass --sources or create tslc.toml")
    profiles = (
        Path(args.machine_profiles)
        if args.machine_profiles
        else config.machine_profiles
        if config is not None
        else None
    )
    backends = config.backends if config is not None else registered_backend_ids()
    return sources, profiles, backends


def _list_payload(
    catalog: Catalog, profiles: dict[str, MachineProfile], kind: str
) -> dict[str, object]:
    if kind == "primitives":
        values = sorted({primitive.name for primitive in catalog.primitives})
    elif kind == "profiles":
        values = sorted(profiles)
    elif kind == "extensions":
        values = sorted(catalog.extensions)
    elif kind == "types":
        values = list(DEFAULT_SCALAR_TYPE_TAGS)
    elif kind == "type-groups":
        values = sorted(catalog.type_groups)
    elif kind == "backends":
        values = list(registered_backend_ids())
    else:
        values = [item.keyword for item in DEFAULT_TSIL_REGION_DESCRIPTORS]
    return {"kind": kind, "items": values}


def _show_payload(
    catalog: Catalog,
    profiles: dict[str, MachineProfile],
    kind: str,
    name: str,
) -> dict[str, object] | None:
    if kind == "primitive":
        variants = catalog.primitives_named(name, unmasked=False)
        return None if not variants else {
            "kind": kind,
            "name": name,
            "variants": [_primitive(item) for item in variants],
        }
    if kind == "profile":
        profile = profiles.get(name)
        return None if profile is None else _profile(profile)
    if kind == "extension":
        extension = catalog.extensions.get(name)
        return None if extension is None else _extension(extension)
    if kind == "type":
        scalar_type = SCALAR_TYPE_INFOS.get(name)
        return None if scalar_type is None else {
            "kind": kind,
            "name": scalar_type.tag,
            "bit_width": scalar_type.bit_width,
            "signed": scalar_type.signed,
            "floating": scalar_type.floating,
        }
    if kind == "type-group":
        members = catalog.type_groups.get(name)
        return None if members is None else {"kind": kind, "name": name, "members": list(members)}
    if kind == "backend":
        return None if name not in registered_backend_ids() else {"kind": kind, "name": name}
    region = TSIL_REGION_BY_KEYWORD.get(name)
    return None if region is None else _region(region)


def _primitive(item: Primitive) -> dict[str, object]:
    return {
        "signature": item.signature,
        "parameters": list(item.parameters),
        "attributes": dict(item.attributes),
        "implementations": [
            {
                "extension": implementation.extension,
                "type_group": implementation.type_group,
                "to_target_group": implementation.to_target_group,
                "source": _source(implementation.selector_source or implementation.source),
            }
            for implementation in item.implementations
        ],
        "tests": len(item.tests),
        "brief": item.brief_description,
        "arithmetic": _arithmetic(item),
        "source": _source(item.source),
    }


def _arithmetic(item: Primitive) -> dict[str, object] | None:
    contract = item.arithmetic
    if contract is None:
        return None
    return {
        "operations": [operation.value for operation in contract.ordered_operations],
        "operand_roles": {
            binding.role.value: {
                "parameter": binding.parameter_name,
                "index": binding.parameter_index,
                "non_mask_ordinal": binding.non_mask_ordinal,
                "kind": binding.parameter_kind,
            }
            for binding in contract.operand_bindings
        },
        "guarantees": [
            guarantee.value for guarantee in contract.ordered_guarantees
        ],
    }


def _extension(item: Extension) -> dict[str, object]:
    return {
        "kind": "extension",
        "name": item.name,
        "isa": item.isa_name,
        "family": item.family,
        "inherits": item.inherits,
        "vector_bits": item.vector_bits,
        "vector_bits_kind": item.vector_bits_kind,
        "target_features": sorted(item.active_when.target_features),
        "compile_modes": sorted(item.active_when.compile_modes),
        "backends": sorted(
            backend for backend, supported in item.backend_supported.items() if supported
        ),
        "source": _source(item.source),
    }


def _profile(item: MachineProfile) -> dict[str, object]:
    return {
        "kind": "profile",
        "name": item.name,
        "family": item.family,
        "target_features": sorted(item.features),
        "compile_modes": sorted(item.compile_modes),
        "backend_flags": {key: list(value) for key, value in item.backend_flags.items()},
        "runner": None if item.runner is None else {
            "kind": item.runner.kind,
            "profile": item.runner.profile,
            "args": list(item.runner.args),
        },
    }


def _region(item: TsilRegionDescriptor) -> dict[str, object]:
    return {
        "kind": "region",
        "name": item.keyword,
        "purpose": item.purpose,
        "accepted_forms": list(item.accepted_forms),
        "body_shape": item.body_shape,
        "shell_validator": item.shell_validator,
    }


def _source(source: SourceSpan | None) -> dict[str, object] | None:
    return None if source is None else {
        "path": str(source.path),
        "line": source.line,
        "column": source.column,
        "end_line": source.end_line,
        "end_column": source.end_column,
    }


def _text(payload: dict[str, object]) -> str:
    items = payload.get("items")
    if isinstance(items, list):
        return "\n".join(str(item) for item in items)
    return "\n".join(_flatten(payload))


def _flatten(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten(item, name))
        return lines
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return [f"{prefix}: {', '.join(str(item) for item in value) or '-'}"]
        lines = []
        for index, item in enumerate(value):
            lines.extend(_flatten(item, f"{prefix}[{index}]"))
        return lines
    return [f"{prefix}: {value}"]


def _print_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> None:
    for item in diagnostics:
        print(format_diagnostic(item), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
