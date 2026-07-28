"""Orchestrate the finalized, render-independent ordinary Rust facade plan."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_candidates import (
    _candidate_key,
    _candidate_sort_key,
    _candidates,
    _fallback_mapping_owner_diagnostics,
    _invocation_from_roles,
    _specialization_vector_type_tags,
)
from tslc.backend.rust_api_comprehensive import (
    _comprehensive_method,
    _coverage_sort_key,
    _excluded,
    _method_collision_diagnostics,
    _method_sort_key,
)
from tslc.backend.rust_api_curated import (
    _bit_conversions,
    _curated_method_sort_key,
    _curated_methods,
    _curated_traits,
    _finalize_bit_conversions,
    _operation_bindings,
    _operation_values,
    _trait_collision_diagnostics,
    _trait_sort_key,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustFacadeConversionPair,
    RustFacadeCoverageEntry,
    RustFacadeCoverageStatus,
    RustFacadeDelegate,
    RustFacadePlan,
)
from tslc.backend.rust_api_surface import (
    RUST_FACADE_CORE_OPERATION_REQUIREMENTS,
    _core_delegates,
    _core_facade_type_tags,
    _core_implementation_arms,
    _equality_implementations,
    _finalize_bit_conversion_implementation_arms,
    _finalize_comprehensive_coverage,
    _finalize_comprehensive_implementation_arms,
    _finalize_comprehensive_shapes,
    _finalize_curated_implementation_arms,
    _finalize_curated_shapes,
    _finalize_delegate_owners,
    _finalize_operator_implementations,
    _finalize_trait_shapes,
    _logical_shapes,
    _native_aliases,
)
from tslc.backend.rust_static_selection import RustStaticSelectionPlan
from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, sort_diagnostics


class RustFacadePlanningError(ValueError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(item.message for item in diagnostics))


def plan_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> RustFacadePlan:
    plan, diagnostics = _plan_rust_facade(
        profiles, static_selection, require_core=False
    )
    if diagnostics:
        raise RustFacadePlanningError(diagnostics)
    assert plan is not None
    return plan


def validate_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> tuple[Diagnostic, ...]:
    _plan, diagnostics = _plan_rust_facade(
        profiles, static_selection, require_core=True
    )
    return diagnostics


def validate_rust_facade_plan(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    plan: RustFacadePlan,
) -> None:
    if plan != plan_rust_facade(profiles, static_selection):
        raise ValueError("Rust facade plan does not match the lowered profile inventory")


def rust_facade_closure_seed_primitives(catalog: Catalog) -> tuple[str, ...]:
    """Source primitives needed by the logical value boundary.

    Selection uses semantic operation identities and typed signatures. Primitive
    names remain outputs of this projection, never its classifier.
    """

    names = {
        primitive.name
        for primitive in catalog.primitives
        if primitive.operation is not None
        and (shape := parse_signature(primitive.signature)) is not None
        and any(
            primitive.operation.kind is requirement.operation
            and shape.result_kind == requirement.result_kind
            and (
                (
                    primitive.memory.access,
                    primitive.memory.addressing,
                )
                if primitive.memory is not None
                else None
            )
            == (
                (
                    requirement.memory_access,
                    requirement.memory_addressing,
                )
                if requirement.memory_access is not None
                else None
            )
            and all(
                axis_name in primitive.attributes
                for axis_name in requirement.axis_names
            )
            and _invocation_from_roles(
                shape.param_kinds,
                tuple(
                    (
                        binding.role,
                        binding.parameter_index,
                        binding.parameter_kind,
                    )
                    for binding in primitive.operation.operand_bindings
                ),
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is not None
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
        )
    }
    return tuple(sorted(names))


def _plan_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    *,
    require_core: bool,
) -> tuple[RustFacadePlan | None, tuple[Diagnostic, ...]]:
    candidates = _candidates(profiles, static_selection)
    baseline_keys = {
        _candidate_key(spec)
        for _name, specs in static_selection.fallback_module.primitive_specializations
        for spec in specs
    }
    diagnostics: list[Diagnostic] = list(
        _fallback_mapping_owner_diagnostics(static_selection)
    )
    methods: list[RustComprehensiveMethod] = []
    coverage: list[RustFacadeCoverageEntry] = []

    for candidate in sorted(candidates.values(), key=_candidate_sort_key):
        key = candidate.key
        if key not in baseline_keys:
            coverage.append(_excluded(candidate, "missing generic baseline"))
            continue
        method, reason, candidate_diagnostics = _comprehensive_method(candidate)
        diagnostics.extend(candidate_diagnostics)
        if candidate_diagnostics:
            continue
        if method is None:
            coverage.append(_excluded(candidate, reason or "not representable"))
            continue
        methods.append(method)
        coverage.append(
            RustFacadeCoverageEntry(
                key.source_name,
                key.signature,
                key.mask_policy,
                RustFacadeCoverageStatus.ADMITTED,
                public_name=method.public_name,
            )
        )

    curated_methods, curated_diagnostics = _curated_methods(methods, candidates)
    bit_conversions, bit_conversion_diagnostics = _bit_conversions(candidates)
    operation_bindings, operation_binding_diagnostics = _operation_bindings(
        candidates, baseline_keys
    )
    diagnostics.extend(curated_diagnostics)
    diagnostics.extend(bit_conversion_diagnostics)
    diagnostics.extend(operation_binding_diagnostics)
    ordered_diagnostics = sort_diagnostics(diagnostics)
    if ordered_diagnostics:
        return None, ordered_diagnostics

    facade_type_tags = _core_facade_type_tags(operation_bindings)
    has_core_inventory = facade_type_tags is not None
    if facade_type_tags is None:
        facade_type_tags = {
            type_tag
            for _primitive_name, specs in (
                static_selection.fallback_module.primitive_specializations
            )
            for spec in specs
            for type_tag in _specialization_vector_type_tags(spec)
        }
    shapes = _logical_shapes(
        static_selection,
        facade_type_tags,
        operation_bindings,
    )
    traits, trait_diagnostics = _curated_traits(methods, candidates, shapes)
    diagnostics.extend(trait_diagnostics)
    if diagnostics:
        return None, sort_diagnostics(diagnostics)
    owner_cache: dict[
        tuple[RustFacadeDelegate, ...],
        tuple[tuple[RustFacadeDelegate, ...], tuple[Diagnostic, ...]],
    ] = {}

    def finalize_owners(
        delegates: tuple[RustFacadeDelegate, ...],
    ) -> tuple[RustFacadeDelegate, ...]:
        cached = owner_cache.get(delegates)
        if cached is None:
            cached = _finalize_delegate_owners(delegates, shapes)
            owner_cache[delegates] = cached
            diagnostics.extend(cached[1])
        finalized, _owner_diagnostics = cached
        return finalized

    def finalize_pairs(
        pairs: tuple[RustFacadeConversionPair, ...],
    ) -> tuple[RustFacadeConversionPair, ...]:
        return tuple(
            replace(pair, delegates=finalize_owners(pair.delegates))
            for pair in pairs
        )

    operation_bindings = tuple(
        replace(binding, delegates=finalize_owners(binding.delegates))
        for binding in operation_bindings
    )
    methods = [
        replace(
            method,
            conversion_pairs=finalize_pairs(method.conversion_pairs),
            delegates=finalize_owners(method.delegates),
        )
        for method in methods
    ]
    curated_methods = [
        replace(
            method,
            conversion_pairs=finalize_pairs(method.conversion_pairs),
            delegates=finalize_owners(method.delegates),
        )
        for method in curated_methods
    ]
    traits = [
        replace(trait, delegates=finalize_owners(trait.delegates))
        for trait in traits
    ]
    bit_conversions = tuple(
        replace(
            conversion,
            to_bits=replace(
                conversion.to_bits,
                delegates=finalize_owners(conversion.to_bits.delegates),
            ),
            from_bits=replace(
                conversion.from_bits,
                delegates=finalize_owners(conversion.from_bits.delegates),
            ),
        )
        for conversion in bit_conversions
    )
    if diagnostics:
        unique_diagnostics = {
            (item.code, item.message): item for item in diagnostics
        }
        return None, sort_diagnostics(tuple(unique_diagnostics.values()))
    methods = _finalize_comprehensive_shapes(methods, shapes)
    coverage = _finalize_comprehensive_coverage(coverage, methods)
    curated_methods = _finalize_curated_shapes(curated_methods, shapes)
    traits = _finalize_trait_shapes(traits, shapes)
    bit_conversions = _finalize_bit_conversions(bit_conversions, shapes)
    diagnostics.extend(_method_collision_diagnostics(methods, curated_methods))
    diagnostics.extend(_trait_collision_diagnostics(traits, candidates))
    if diagnostics:
        return None, sort_diagnostics(diagnostics)
    operation_values = _operation_values(traits)
    core_delegates, core_diagnostics = _core_delegates(
        shapes,
        operation_bindings,
        require_complete=require_core and has_core_inventory,
    )
    if core_diagnostics:
        return None, sort_diagnostics(core_diagnostics)
    methods = _finalize_comprehensive_implementation_arms(methods, shapes)
    curated_methods = _finalize_curated_implementation_arms(
        curated_methods, shapes
    )
    bit_conversions = _finalize_bit_conversion_implementation_arms(
        bit_conversions, shapes
    )
    traits = _finalize_operator_implementations(traits, shapes)
    equality_arms = _equality_implementations(
        curated_methods, shapes
    )
    core_arms = _core_implementation_arms(core_delegates, shapes)
    return (
        RustFacadePlan(
            shapes=shapes,
            operation_bindings=operation_bindings,
            core_delegates=core_delegates,
            core_implementation_arms=core_arms,
            comprehensive_methods=tuple(sorted(methods, key=_method_sort_key)),
            curated_methods=tuple(sorted(curated_methods, key=_curated_method_sort_key)),
            equality_implementations=equality_arms,
            bit_conversions=bit_conversions,
            trait_implementations=tuple(sorted(traits, key=_trait_sort_key)),
            native_aliases=_native_aliases(
                profiles,
                static_selection,
                facade_type_tags,
                shapes,
            ),
            operation_values=operation_values,
            coverage=tuple(sorted(coverage, key=_coverage_sort_key)),
        ),
        (),
    )


__all__ = (
    "RUST_FACADE_CORE_OPERATION_REQUIREMENTS",
    "RustFacadePlanningError",
    "plan_rust_facade",
    "rust_facade_closure_seed_primitives",
    "validate_rust_facade",
    "validate_rust_facade_plan",
)
