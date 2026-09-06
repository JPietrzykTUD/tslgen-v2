#!/usr/bin/env python3
"""Freeze the typed TSL 1.x public callable-family boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tslc.backend.algorithm_contracts import (
    ALGORITHM_PUBLIC_FAMILIES,
)
from tslc.backend.cpp_algorithm_contracts import cpp_checked_algorithm_families
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.maintenance import _repo_context
from tslc.maintenance._catalog import load_repository_catalog
from tslc.maintenance._repo_context import RepoContext


def canonical_baseline_path(context: RepoContext) -> Path:
    return context.coverage_root / "tsl-v1-public-api.json"


def build_public_api_baseline(context: RepoContext) -> dict[str, object]:
    """Project public identities from typed catalog and backend manifests."""

    catalog = load_repository_catalog(context, purpose="public-API baseline")
    primitives = [
        {
            "name": primitive.name,
            "signature": primitive.signature,
            "attributes": dict(sorted(primitive.attributes.items())),
            "result_target": list(primitive.result_target or ()),
            "checked_source_contract": bool(primitive.preconditions),
            "preconditions": sorted(
                condition.kind.value for condition in primitive.preconditions
            ),
        }
        for primitive in sorted(
            catalog.primitives,
            key=lambda item: (
                item.name,
                item.signature,
                tuple(sorted(item.attributes.items())),
                tuple(item.result_target or ()),
            ),
        )
    ]
    return {
        "version": 1,
        "compatibility": {
            "cpp": (
                "names reachable through tsl.hpp, excluding detail namespaces, "
                "physical profile headers, and compiler-selection macros"
            ),
            "rust": (
                "opaque root facade plus profile primitive callables; core and "
                "algorithm substrate representations are not stable ABI"
            ),
            "identity_level": (
                "typed callable family; backend overload sets and representative "
                "rendered declarations are ratcheted by generated snapshots"
            ),
        },
        "cpp_core_identities": [
            "tsl::array_type",
            "tsl::dataparallel::fixed",
            "tsl::dataparallel::generic",
            "tsl::dataparallel::native",
            "tsl::implementation_state",
            "tsl::precondition_error",
            "tsl::reg_param",
            "tsl::simd",
            "tsl::span",
        ],
        "rust_root_identities": [
            "tsl::Mask",
            "tsl::NativeMask",
            "tsl::NativeSimd",
            "tsl::PreconditionError",
            "tsl::Simd",
            "tsl::SimdElement",
            "tsl::SupportedSimd",
            "tsl::profile",
        ],
        "primitive_callable_families": primitives,
        "algorithm_callable_families": sorted(ALGORITHM_PUBLIC_FAMILIES),
        "cpp_checked_algorithm_families": sorted(cpp_checked_algorithm_families()),
        "rust_algorithm_callables": sorted(RUST_ALGORITHM_RESERVED_NAMES),
    }


def serialize(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check or update the frozen TSL v1 public API baseline."
    )
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    context = _repo_context.require_repo_context(parser)
    path = Path(args.baseline) if args.baseline else canonical_baseline_path(context)
    try:
        baseline = build_public_api_baseline(context)
        actual = serialize(baseline)
    except (RuntimeError, ValueError) as error:
        print(f"public API baseline failed: {error}", file=sys.stderr)
        return 2
    if args.update:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        print(f"wrote {path}")
        return 0
    if not path.is_file():
        print(f"public API baseline missing: {path}", file=sys.stderr)
        return 2
    if path.read_text(encoding="utf-8") != actual:
        print(
            "public API differs from the reviewed v1 baseline; review and run "
            "with --update to accept it",
            file=sys.stderr,
        )
        return 1
    primitive_families = baseline["primitive_callable_families"]
    if not isinstance(primitive_families, list):
        raise AssertionError("public API primitive families must be a list")
    print(
        "TSL v1 public API baseline OK: "
        f"{len(primitive_families)} primitive families"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
