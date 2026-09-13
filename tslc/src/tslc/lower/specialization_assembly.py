"""Assemble final lowered specializations from resolved signature and body facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.translation import BackendDialect
from tslc.catalog.memory import resolve_memory_alignment
from tslc.catalog.model import BOOLEAN_WILDCARD_ATTRIBUTES, RESULT_DIM_VECTOR
from tslc.catalog.signatures import SignatureShape
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.documentation import primitive_documentation
from tslc.lower._diagnostics import implementation_source, lowering_error_diagnostic
from tslc.lower.catalog_facts import type_param_bounds
from tslc.lower.context import LoweringEnv
from tslc.lower.dependencies import symbolic_call_dependency_error
from tslc.lower.implementation_bodies import LoweredImplementationBodies
from tslc.lower.model import (
    LoweredArithmeticPrecondition,
    LoweredSpecialization,
    LoweredTypeParam,
    LoweringResult,
)
from tslc.lower.primitive_semantics import (
    LoweredMemoryAlignment,
    LoweredPrimitiveSemantics,
)
from tslc.lower.target_vectors import TargetVector
from tslc.select.selector import SelectedImplementation


@dataclass(frozen=True, slots=True)
class ResolvedSpecializationSignature:
    """Resolved callable, representation, target, and immediate facts."""

    shape: SignatureShape
    parameters: tuple[str, ...]
    base_type_spelling: str
    register_spelling: str
    param_type_overrides: tuple[str | None, ...]
    vector_spelling: str | None
    index_register_spelling: str | None
    native_register_spelling: str | None
    uses_sized_vector: bool
    lane_parameter: str | None
    target: TargetVector | None
    immediate: tuple[str, str] | None
    immediate_range: tuple[int, int, bool] | None
    immediate_valid_range: tuple[int, int, bool] | None
    arithmetic_preconditions: tuple[LoweredArithmeticPrecondition, ...]


def assemble_specialization(
    *,
    selected: SelectedImplementation,
    env: LoweringEnv,
    resolved: ResolvedSpecializationSignature,
    bodies: LoweredImplementationBodies,
    primitive_type_param_bounds: Mapping[
        tuple[str, str, int], tuple[str, ...]
    ],
) -> LoweringResult:
    """Validate symbolic dependencies and construct one final specialization."""

    backend = env.backend
    support = env.support
    shape = resolved.shape
    type_params = _lowered_type_params(
        selected,
        backend,
        env,
        bodies,
        primitive_type_param_bounds,
    )
    type_param_bound_map = {
        type_param.name: type_param.bounds for type_param in type_params
    }
    for origin in bodies.call_dependency_origins:
        message = symbolic_call_dependency_error(
            origin.dependency,
            type_param_bound_map,
        )
        if message is not None:
            return LoweringResult(
                specialization=None,
                diagnostics=(
                    _symbolic_dependency_diagnostic(selected, message),
                ),
            )

    specialization = LoweredSpecialization(
        backend_id=backend.backend_id,
        primitive_name=selected.primitive.name,
        source_primitive_name=selected.primitive.name,
        extension_name=env.extension.isa_name,
        type_tag=env.type_tag,
        base_type_spelling=resolved.base_type_spelling,
        register_spelling=resolved.register_spelling,
        result_kind=shape.result_kind,
        param_names=resolved.parameters,
        param_kinds=shape.param_kinds,
        body=bodies.body,
        source_signature=selected.primitive.signature,
        source_attributes=tuple(sorted(selected.primitive.attributes.items())),
        primitive_semantics=LoweredPrimitiveSemantics(
            overload=env.catalog.resolve_primitive_overload(selected.primitive),
            arithmetic=selected.primitive.arithmetic,
            operation=selected.primitive.operation,
            preconditions=selected.primitive.preconditions,
            memory=selected.primitive.memory,
            memory_alignment=_lowered_memory_alignment(selected),
            conversion=selected.primitive.conversion,
            shift=selected.primitive.shift,
        ),
        param_identity_tokens=tuple(
            support.overload_identity_token(
                kind,
                register_is_base=support.register_is_base(env.extension),
            )
            for kind in shape.param_kinds
        ),
        param_type_overrides=resolved.param_type_overrides,
        vector_spelling=resolved.vector_spelling,
        index_register_spelling=resolved.index_register_spelling,
        native_register_spelling=resolved.native_register_spelling,
        uses_sized_vector=resolved.uses_sized_vector,
        lane_parameter=resolved.lane_parameter,
        axis=tuple(
            (key, selected.primitive.attributes[key])
            for key in sorted(selected.primitive.attributes)
            if key in BOOLEAN_WILDCARD_ATTRIBUTES
        ),
        immediate=resolved.immediate,
        immediate_range=resolved.immediate_range,
        immediate_valid_range=resolved.immediate_valid_range,
        arithmetic_preconditions=resolved.arithmetic_preconditions,
        generic_params=tuple(
            (gp.name, backend.types.const_param_type(gp.kind), gp.default)
            for gp in selected.primitive.generic_params
            if gp.kind != "simd_type"
        ),
        type_params=type_params,
        result_vector_param=(
            selected.primitive.result_target[1]
            if selected.primitive.result_target is not None
            and selected.primitive.result_target[0] == RESULT_DIM_VECTOR
            else None
        ),
        register_is_base=support.register_is_base(env.extension),
        target=resolved.target,
        mask_policy=selected.primitive.mask_mode,
        lane_list_params=tuple(env.lane_list_params.values()),
        required_features=selected.required_features,
        required_compiler_capabilities=selected.required_compiler_capabilities,
        call_dependency_origins=bodies.call_dependency_origins,
        unresolved_call_preconditions=tuple(
            obligation
            for origin in bodies.call_dependency_origins
            for obligation in origin.unresolved_preconditions
        ),
        implementation_state=bodies.implementation_state,
        safety=bodies.safety,
        variant_bodies=bodies.variants,
        documentation=primitive_documentation(
            brief=selected.primitive.brief_description,
            detailed=selected.primitive.detailed_description,
            semantics=selected.primitive.semantics,
        ),
        source=implementation_source(selected),
    )
    return LoweringResult(
        specialization=specialization,
        diagnostics=sort_diagnostics(bodies.diagnostics),
    )


def _lowered_type_params(
    selected: SelectedImplementation,
    backend: BackendDialect,
    env: LoweringEnv,
    bodies: LoweredImplementationBodies,
    primitive_type_param_bounds: Mapping[
        tuple[str, str, int], tuple[str, ...]
    ],
) -> tuple[LoweredTypeParam, ...]:
    return tuple(
        LoweredTypeParam(
            name=generic.name,
            bounds=tuple(
                sorted(
                    {
                        bound
                        for segments in bodies.source_segment_groups
                        for bound in type_param_bounds(
                            segments,
                            generic.name,
                            primitive_type_param_bounds,
                            selected.extension.name,
                        )
                    }
                )
            ),
            base_type_constraints=generic.base_type_constraints,
            specialize_base=generic.specialize_base,
            base_type_binding=env.simd_type_param_base_bindings.get(generic.name),
            base_type_binding_spelling=(
                backend.types.scalar_spelling(binding)
                if (
                    binding := env.simd_type_param_base_bindings.get(generic.name)
                )
                is not None
                else None
            ),
        )
        for generic in selected.primitive.generic_params
        if generic.kind == "simd_type"
    )


def _lowered_memory_alignment(
    selected: SelectedImplementation,
) -> LoweredMemoryAlignment | None:
    primitive = selected.primitive
    if primitive.memory is None:
        return None
    resolved = resolve_memory_alignment(primitive.attributes)
    return (
        None
        if resolved is None
        else LoweredMemoryAlignment(axis_name=resolved[0], mode=resolved[1])
    )


def _symbolic_dependency_diagnostic(
    selected: SelectedImplementation,
    message: str,
) -> Diagnostic:
    return lowering_error_diagnostic(
        "TSL-LOWER-INVALID-SYMBOLIC-CALL-DEPENDENCY",
        message,
        source=implementation_source(selected),
    )


__all__ = (
    "ResolvedSpecializationSignature",
    "assemble_specialization",
)
