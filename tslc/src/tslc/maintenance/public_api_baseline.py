#!/usr/bin/env python3
"""Freeze the typed TSL 1.x public callable-family boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.backend.algorithm_contracts import ALGORITHM_CONTRACTS
from tslc.backend.algorithm_surface import ALGORITHM_PUBLIC_FAMILIES
from tslc.backend.cpp_algorithm_contracts import cpp_checked_algorithm_families
from tslc.backend.cpp_public_api import (
    CPP_CORE_PUBLIC_IDENTITIES,
    cpp_public_api_manifest,
)
from tslc.backend.helper_requirements import (
    BackendHelperPlan,
    CPP_HELPER_MANIFEST,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.precondition_error_rendering import (
    cpp_precondition_error,
    rust_precondition_error,
)
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_algorithm_plan import plan_rust_algorithm
from tslc.backend.rust_api_planner import plan_rust_facade
from tslc.backend.rust_dispatch import plan_rust_dispatch
from tslc.backend.rust_public_api import (
    RUST_ROOT_PUBLIC_IDENTITIES,
    rust_public_api_manifest,
)
from tslc.backend.rust_static_selection import plan_rust_static_selection
from tslc.catalog.arithmetic import ArithmeticOperandBinding
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
)
from tslc.catalog.semantics import OperandBinding, PrimitiveProviderRequirement
from tslc.diagnostics import Diagnostic
from tslc.maintenance import _repo_context
from tslc.maintenance._catalog import load_repository_catalog
from tslc.maintenance._repo_context import RepoContext
from tslc.maintenance.release_contract import (
    canonical_policy_path,
    select_release_profiles,
)
from tslc.maintenance.release_contract_policy import load_release_policy


_EXACT_DECLARATION_BACKENDS = ("cpp", "rust")


def canonical_baseline_path(context: RepoContext) -> Path:
    return context.coverage_root / "tsl-v1-public-api.json"


def _operand_binding(
    binding: OperandBinding | ArithmeticOperandBinding,
) -> dict[str, object]:
    return {
        "domain": (
            "arithmetic"
            if isinstance(binding, ArithmeticOperandBinding)
            else "operation"
        ),
        "role": binding.role.value,
        "parameter": binding.parameter_name,
        "parameter_index": binding.parameter_index,
        "parameter_kind": binding.parameter_kind,
    }


def _primitive_family(primitive: Primitive) -> dict[str, object]:
    operation = primitive.operation
    arithmetic = primitive.arithmetic
    memory = primitive.memory
    conversion = primitive.conversion
    shift = primitive.shift
    overload = primitive.overload
    return {
        "name": primitive.name,
        "signature": primitive.signature,
        "parameters": list(primitive.parameters),
        "attributes": dict(sorted(primitive.attributes.items())),
        "result_target": list(primitive.result_target or ()),
        "immediate_parameters": [
            {
                "name": parameter.name,
                "type": parameter.type_tag,
                "value_range": (
                    [
                        parameter.value_range.lower,
                        parameter.value_range.upper.source_text,
                        parameter.value_range.inclusive,
                    ]
                    if parameter.value_range is not None
                    else None
                ),
                "valid_range": (
                    [
                        parameter.valid_range.lower,
                        parameter.valid_range.upper.source_text,
                        parameter.valid_range.inclusive,
                    ]
                    if parameter.valid_range is not None
                    else None
                ),
                "dispatch": [list(item) for item in parameter.dispatch],
            }
            for parameter in primitive.immediate_params
        ],
        "generic_parameters": [
            {
                "name": parameter.name,
                "kind": parameter.kind,
                "default": parameter.default,
                "base_types": list(parameter.base_type_constraints),
                "specialize_base": parameter.specialize_base,
                "base_width_relations": [
                    constraint.relation
                    for constraint in parameter.base_width_constraints
                ],
            }
            for parameter in primitive.generic_params
        ],
        "parameter_type_rules": [
            {
                "parameter": rule.parameter_name,
                "attribute": rule.attribute_name,
                "value": rule.attribute_value,
                "type": rule.type_expr.source_text,
            }
            for rule in primitive.param_type_rules
        ],
        "overload": (
            {
                "axis": overload.axis,
                "value": overload.value,
                "declares_primary": overload.declares_primary,
            }
            if overload is not None
            else None
        ),
        "operation": (
            {
                "kind": operation.kind.value,
                "operands": [
                    _operand_binding(binding)
                    for binding in operation.operand_bindings
                ],
            }
            if operation is not None
            else None
        ),
        "arithmetic": (
            {
                "operations": [
                    item.value for item in arithmetic.ordered_operations
                ],
                "guarantees": [
                    item.value for item in arithmetic.ordered_guarantees
                ],
                "operands": [
                    _operand_binding(binding)
                    for binding in arithmetic.operand_bindings
                ],
            }
            if arithmetic is not None
            else None
        ),
        "memory": (
            {
                "access": memory.access.value,
                "addressing": memory.addressing.value,
                "payload_extent": memory.payload_extent.value,
                "indexed_lane_extent": (
                    memory.indexed_lane_extent.value
                    if memory.indexed_lane_extent is not None
                    else None
                ),
            }
            if memory is not None
            else None
        ),
        "conversion": (
            {
                "kind": conversion.kind.value,
                "lane_count": conversion.lane_count.value,
                "numeric_mode": (
                    conversion.numeric_mode.value
                    if conversion.numeric_mode is not None
                    else None
                ),
            }
            if conversion is not None
            else None
        ),
        "shift": (
            {
                "count_rule": shift.count_rule.value,
                "lane_rule": shift.lane_rule.value,
                "scalar_count_types": list(shift.scalar_count_types),
            }
            if shift is not None
            else None
        ),
        "checked_source_contract": bool(primitive.preconditions),
        "preconditions": [
            {
                "kind": condition.kind.value,
                "operands": [
                    _operand_binding(binding)
                    for binding in condition.operand_bindings
                ],
            }
            for condition in primitive.preconditions
        ],
    }


def _checked_algorithm_contracts() -> list[dict[str, object]]:
    return [
        {
            "name": contract.name,
            "result_kind": contract.result_kind.value,
            "ranges": [
                {
                    "name": binding.name,
                    "role": binding.role.value,
                    "mask_storage": (
                        binding.mask_storage.value
                        if binding.mask_storage is not None
                        else None
                    ),
                }
                for binding in contract.ranges
            ],
            "conditions": [
                {
                    "kind": condition.kind.value,
                    "range": condition.range_name,
                    "reference": condition.reference_name,
                    "error": condition.error.value,
                }
                for condition in contract.conditions
            ],
            "alias_rules": [
                {
                    "writable": rule.writable_range_name,
                    "readable": list(rule.readable_range_names),
                    "allow_exact_alias": rule.allow_exact_alias,
                }
                for rule in contract.alias_rules
            ],
        }
        for contract in sorted(
            ALGORITHM_CONTRACTS.values(), key=lambda item: item.name
        )
    ]


def _checked_precondition_contracts(
    catalog: Catalog,
) -> list[dict[str, object]]:
    """Freeze every compiler-owned fact that defines one checked condition."""

    return [
        {
            "kind": descriptor.kind.value,
            "description": descriptor.description,
            "hazard": descriptor.hazard.value,
            "error": descriptor.error.value,
            "additional_errors": [
                error.value for error in descriptor.additional_errors
            ],
            "unchecked_consequence": descriptor.unchecked_consequence,
            "required_roles": sorted(role.value for role in descriptor.required_roles),
            "compatible_operations": sorted(
                operation.value for operation in descriptor.compatible_operations
            ),
            "required_arithmetic_roles": sorted(
                role.value for role in descriptor.required_arithmetic_roles
            ),
            "compatible_arithmetic_operations": sorted(
                operation.value
                for operation in descriptor.compatible_arithmetic_operations
            ),
            "numeric_domain": (
                descriptor.numeric_domain.value
                if descriptor.numeric_domain is not None
                else None
            ),
            "checkable_arithmetic_binding_kinds": sorted(
                descriptor.checkable_arithmetic_binding_kinds
            ),
            "check_primitives": [
                _resolved_provider_name(catalog, requirement)
                for requirement in descriptor.check_primitives
            ],
            "masked_check_primitives": [
                _resolved_provider_name(catalog, requirement)
                for requirement in descriptor.masked_check_primitives
            ],
            "compatible_memory_accesses": sorted(
                access.value for access in descriptor.compatible_memory_accesses
            ),
            "compatible_memory_addressings": sorted(
                addressing.value
                for addressing in descriptor.compatible_memory_addressings
            ),
        }
        for descriptor in sorted(
            PRECONDITION_DESCRIPTORS.values(),
            key=lambda item: item.kind.value,
        )
    ]


def _resolved_provider_name(
    catalog: Catalog,
    requirement: PrimitiveProviderRequirement,
) -> str:
    provider = catalog.resolve_primitive_provider(requirement)
    if isinstance(provider, Diagnostic):
        raise ValueError(provider.message)
    return provider.name


def _checked_error_contract() -> dict[str, object]:
    """Freeze semantic failures and both backend-owned public spellings."""

    return {
        "cpp_success": "none",
        "failures": [
            {
                "kind": error.value,
                "cpp": cpp_precondition_error(error, qualified=False),
                "rust": rust_precondition_error(error, prefix=""),
            }
            for error in PreconditionErrorKind
        ],
    }


def _exact_backend_declarations(
    context: RepoContext,
    catalog: Catalog,
) -> dict[str, object]:
    """Build the reviewed exact declaration scope through normal lowering."""

    loaded_profiles = load_machine_profiles_checked(
        context.machine_profiles_path,
        catalog.target_families,
    )
    profile_errors = tuple(
        diagnostic
        for diagnostic in loaded_profiles.diagnostics
        if diagnostic.severity == "error"
    )
    if profile_errors:
        raise RuntimeError(
            "exact public declaration profile loading failed: "
            + "; ".join(item.message for item in profile_errors)
        )
    policy = load_release_policy(canonical_policy_path(context))
    policy_by_backend = {
        item.backend_id: item for item in policy.backend_profiles
    }
    missing = sorted(set(_EXACT_DECLARATION_BACKENDS) - set(policy_by_backend))
    if missing:
        raise RuntimeError(
            "exact public declaration policy is missing backends: "
            + ", ".join(missing)
        )
    profiles_by_backend = {
        backend_id: tuple(
            profile.name
            for profile in select_release_profiles(
                policy_by_backend[backend_id],
                loaded_profiles.profiles,
            )
        )
        for backend_id in _EXACT_DECLARATION_BACKENDS
    }
    all_profiles = tuple(
        sorted(
            {
                profile
                for profiles in profiles_by_backend.values()
                for profile in profiles
            }
        )
    )

    result = generate_project(
        (context.data_root,),
        machine_profiles_path=context.machine_profiles_path,
        profiles=all_profiles,
        backend_profiles=profiles_by_backend,
        type_tags=_ARITH_TYPE_TAGS,
        backends=_EXACT_DECLARATION_BACKENDS,
        render_artifacts=False,
    )
    errors = tuple(
        diagnostic for diagnostic in result.diagnostics if diagnostic.severity == "error"
    )
    if errors:
        raise RuntimeError(
            "exact public declaration planning failed: "
            + "; ".join(item.message for item in errors)
        )
    static_selection = plan_rust_static_selection(result.emitted_profiles)
    cpp_helpers = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    rust_helpers = BackendHelperPlan.resolve(RUST_HELPER_MANIFEST, catalog)
    algorithm = plan_rust_algorithm(
        result.emitted_profiles, static_selection, rust_helpers
    )
    facade = plan_rust_facade(result.emitted_profiles, static_selection)
    dispatch = plan_rust_dispatch(result.emitted_profiles, static_selection, facade)
    return {
        "profiles_by_backend": {
            backend_id: list(profiles_by_backend[backend_id])
            for backend_id in _EXACT_DECLARATION_BACKENDS
        },
        "cpp": cpp_public_api_manifest(
            result.emitted_profiles, helper_plan=cpp_helpers
        ).payload(),
        "rust": rust_public_api_manifest(
            result.emitted_profiles,
            static_selection,
            algorithm,
            facade,
            dispatch,
        ).payload(),
    }


def build_public_api_baseline(context: RepoContext) -> dict[str, object]:
    """Project public identities from typed catalog and backend manifests."""

    catalog = load_repository_catalog(context, purpose="public-API baseline")
    primitives = [_primitive_family(primitive) for primitive in catalog.primitives]
    primitives.sort(
        key=lambda item: (
            str(item["name"]),
            str(item["signature"]),
            json.dumps(item, sort_keys=True),
        )
    )
    return {
        "version": 4,
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
                "typed source callable-family contracts plus backend-owned exact "
                "declaration records for every backend/profile in the reviewed "
                "release policy; "
                "each generated project also carries its scope-exact manifest"
            ),
        },
        "cpp_core_identities": list(CPP_CORE_PUBLIC_IDENTITIES),
        "rust_root_identities": [
            identity.replace("crate::", "tsl::", 1)
            for identity in RUST_ROOT_PUBLIC_IDENTITIES
        ],
        "primitive_callable_families": primitives,
        "checked_precondition_contracts": _checked_precondition_contracts(catalog),
        "checked_error_contract": _checked_error_contract(),
        "algorithm_callable_families": sorted(ALGORITHM_PUBLIC_FAMILIES),
        "checked_algorithm_contracts": _checked_algorithm_contracts(),
        "cpp_checked_algorithm_families": sorted(cpp_checked_algorithm_families()),
        "rust_algorithm_callables": sorted(RUST_ALGORITHM_RESERVED_NAMES),
        "exact_backend_declarations": _exact_backend_declarations(context, catalog),
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
