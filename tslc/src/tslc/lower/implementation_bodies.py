"""Lower one selected implementation's default and variant bodies."""

from __future__ import annotations

from dataclasses import dataclass, replace

from tslc.backend.translation import BackendLoweringPolicy
from tslc.catalog.model import ImplementationSafety, RESULT_DIM_VECTOR
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionHazard,
    precondition_applies_to_type,
)
from tslc.catalog.signatures import SignatureShape
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.ir.scan import scan
from tslc.ir.segments import Segment
from tslc.lower.body_rendering import body_context, render_body
from tslc.lower.context import LoweringScope, LoweringSession
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    CallDependencyOriginKind,
    GenericVectorReference,
    VectorIdentity,
    origin_sort_key,
)
from tslc.lower.fixed_native import lower_preferred_fixed_native
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.model import LoweredImplementationVariant
from tslc.lower.region_handlers import RegionLowerer
from tslc.lower.target_vectors import TargetVector
from tslc.select.selector import SelectedImplementation
from tslc.target_text import LoweredBody


@dataclass(frozen=True, slots=True)
class LoweredImplementationBodies:
    """Complete lowered body facts consumed by specialization assembly."""

    body: LoweredBody
    implementation_state: ImplementationState
    safety: ImplementationSafety
    variants: tuple[LoweredImplementationVariant, ...]
    source_segment_groups: tuple[tuple[Segment, ...], ...]
    call_dependency_origins: tuple[CallDependencyOrigin, ...]
    diagnostics: tuple[Diagnostic, ...]


class ImplementationBodyLowerer:
    """Scan and lower default/variant bodies without assembling a specialization."""

    def __init__(self, region_lowerers: tuple[RegionLowerer, ...]) -> None:
        self._region_lowerers = region_lowerers

    def lower(
        self,
        *,
        selected: SelectedImplementation,
        shape: SignatureShape,
        context: LoweringSession,
        scope: LoweringScope,
        current_register_spelling: str,
        target: TargetVector | None,
        body_segments: tuple[Segment, ...] | None = None,
    ) -> tuple[LoweredImplementationBodies | None, tuple[Diagnostic, ...]]:
        segments = (
            body_segments
            if body_segments is not None
            else scan(
                selected.implementation.body_text,
                source=selected.implementation.body_source,
            )
        )
        default_body = lower_preferred_fixed_native(
            selected,
            shape,
            context,
            current_register_spelling=current_register_spelling,
            target=target,
        )
        if default_body is None:
            default_body = render_body(
                selected=selected,
                shape=shape,
                context=context,
                segments=segments,
                region_lowerers=self._region_lowerers,
            )
        if default_body.rendered is None:
            return None, sort_diagnostics(default_body.diagnostics)

        safety = selected.implementation.safety.merge(default_body.safety)
        body = LoweredBody.from_render_text(
            default_body.rendered,
            unsafe_block_renderer=context.env.backend.syntax.render_unsafe_block,
            requires_unsafe=safety.internal_unsafe,
        )
        variant_sources = tuple(
            (
                variant,
                scan(variant.body_text, source=variant.body_source),
            )
            for variant in selected.implementation.variants
        )
        variants: list[LoweredImplementationVariant] = []
        effective_safety = safety
        diagnostics = [*default_body.diagnostics]
        call_dependency_origins = set(context.effects.call_dependency_origins)
        call_dependency_origins.update(
            _checked_precondition_dependencies(
                selected,
                lowering_policy=context.env.backend.lowering_policy,
                result_kind=shape.result_kind,
                target=target,
            )
        )
        for variant, variant_segments in variant_sources:
            variant_context = body_context(
                replace(
                    context.env,
                    dependency_origin=f"implementation variant {variant.name!r}",
                ),
                scope,
            )
            rendered_variant = render_body(
                selected=selected,
                shape=shape,
                context=variant_context,
                segments=variant_segments,
                region_lowerers=self._region_lowerers,
                variant_name=variant.name,
                variant_source=variant.body_source,
            )
            if rendered_variant.rendered is None:
                return None, sort_diagnostics(rendered_variant.diagnostics)
            variant_safety = (
                selected.implementation.safety
                .merge(variant.safety)
                .merge(rendered_variant.safety)
            )
            effective_safety = effective_safety.merge(variant_safety)
            diagnostics.extend(rendered_variant.diagnostics)
            call_dependency_origins.update(
                variant_context.effects.call_dependency_origins
            )
            variants.append(
                LoweredImplementationVariant(
                    name=variant.name,
                    body=LoweredBody.from_render_text(
                        rendered_variant.rendered,
                        unsafe_block_renderer=(
                            context.env.backend.syntax.render_unsafe_block
                        ),
                        requires_unsafe=variant_safety.internal_unsafe,
                    ),
                    implementation_state=rendered_variant.implementation_state,
                    safety=variant_safety,
                )
            )

        return (
            LoweredImplementationBodies(
                body=body,
                implementation_state=default_body.implementation_state,
                safety=effective_safety,
                variants=tuple(variants),
                source_segment_groups=(
                    segments,
                    *(item[1] for item in variant_sources),
                ),
                call_dependency_origins=tuple(
                    sorted(call_dependency_origins, key=origin_sort_key)
                ),
                diagnostics=tuple(diagnostics),
            ),
            (),
        )


def _checked_precondition_dependencies(
    selected: SelectedImplementation,
    *,
    lowering_policy: BackendLoweringPolicy,
    result_kind: str,
    target: TargetVector | None,
) -> tuple[CallDependencyOrigin, ...]:
    current = VectorIdentity(selected.type_tag, selected.extension.isa_name)
    dependencies: list[CallDependencyOrigin] = []
    has_checked_condition = False
    for precondition in selected.primitive.preconditions:
        descriptor = PRECONDITION_DESCRIPTORS[precondition.kind]
        if not precondition_applies_to_type(precondition, selected.type_tag):
            continue
        if descriptor.hazard is PreconditionHazard.CATASTROPHIC:
            has_checked_condition = True
        check_primitives = descriptor.check_primitives
        if selected.primitive.mask_mode is not None:
            check_primitives += descriptor.masked_check_primitives
        dependencies.extend(
            CallDependencyOrigin(
                dependency=CallDependency(
                    primitive=primitive.value,
                    mask_policy=None,
                    source=current,
                ),
                origin=f"checked precondition {precondition.kind.value!r}",
                kind=CallDependencyOriginKind.CHECKED_GUARD,
                source=precondition.source,
            )
            for primitive in check_primitives
        )
    failure_primitive = lowering_policy.checked_failure_primitive(result_kind)
    if has_checked_condition and failure_primitive is not None:
        result_vector: GenericVectorReference | VectorIdentity
        result_target = selected.primitive.result_target
        if result_target is not None and result_target[0] == RESULT_DIM_VECTOR:
            base_binding = next(
                (
                    binding.base_tag
                    for binding in selected.simd_type_base_bindings
                    if binding.param_name == result_target[1]
                ),
                None,
            )
            result_vector = GenericVectorReference(result_target[1], base_binding)
        elif target is not None:
            result_vector = VectorIdentity(target.base_tag, target.extension_isa)
        else:
            result_vector = current
        dependencies.append(
            CallDependencyOrigin(
                dependency=CallDependency(
                    primitive=failure_primitive.value,
                    mask_policy=None,
                    source=result_vector,
                ),
                origin="checked failure value",
                kind=CallDependencyOriginKind.CHECKED_GUARD,
                source=selected.primitive.source,
            )
        )
    return tuple(dependencies)


__all__ = ("ImplementationBodyLowerer", "LoweredImplementationBodies")
