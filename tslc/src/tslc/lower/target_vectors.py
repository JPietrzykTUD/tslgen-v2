"""Target-vector resolution for representation-change primitives."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend import translation_common
from tslc.backend.translation import BackendDialect
from tslc.catalog.model import RESULT_DIM_BASE, Catalog
from tslc.diagnostics import Diagnostic
from tslc.lower._diagnostics import (
    implementation_source,
    lowering_error_diagnostic,
    lowering_skip_diagnostic,
)
from tslc.lower.context import LoweringScope
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy


@dataclass(frozen=True, slots=True)
class TargetVector:
    """The target vector of a representation-change primitive.

    A `return_type: base|extension: ...` primitive produces the source vector
    with one dimension replaced. Bundling every spelling of that one concept
    keeps downstream code branching on `spec.target is None` instead of
    juggling correlated nullable fields.
    """

    vector_spelling: str
    register_spelling: str
    extension_isa: str
    base_tag: str
    base_spelling: str
    uses_sized_vector: bool = False
    lane_parameter: str | None = None
    windowed: bool = False
    native_register_spelling: str | None = None


TargetVectorResolution = TargetVector | None | Diagnostic


def resolve_target_vector(
    selected: SelectedImplementation,
    catalog: Catalog,
    backend: BackendDialect,
    base_type_spelling: str,
    scope: LoweringScope,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> TargetVectorResolution:
    """Resolve and bind the target of a representation-change primitive.

    Returns ``None`` for an ordinary primitive, a :class:`TargetVector` for a
    representation-change primitive, or a diagnostic when the target cannot be
    expressed by the selected backend/support policy.
    """

    if selected.primitive.result_target is None or selected.to_target is None:
        return None
    dim, alias = selected.primitive.result_target
    if support.uses_sized_vector(selected.extension):
        return _resolve_sized_target(
            selected, backend, dim, alias, scope, support
        )
    if dim == RESULT_DIM_BASE:
        return _resolve_base_target(selected, catalog, backend, alias, scope, support)
    return _resolve_extension_target(
        selected, catalog, backend, base_type_spelling, alias, support, scope
    )


def _resolve_sized_target(
    selected: SelectedImplementation,
    backend: BackendDialect,
    dim: str,
    alias: str,
    scope: LoweringScope,
    support: SupportPolicy,
) -> TargetVector | Diagnostic:
    if not support.supports_sized_vector_target_dimension(dim):
        return lowering_skip_diagnostic(
            "TSL-LOWER-UNSUPPORTED-TARGET-VECTOR",
            f"extension-dim representation-change on a sized vector is not "
            f"supported: {selected.primitive.name!r}",
            source=implementation_source(selected),
        )
    to_base_spelling = backend.types.scalar_spelling(selected.to_target)
    if to_base_spelling is None:
        return _no_target_base_type(selected, backend)
    scope.bind_target_type_symbol(alias, selected.to_target)
    scope.bind_target_type_symbol("ToType", selected.to_target)
    lane_parameter, windowing = _sized_target_lane_parameter(selected, support)
    register_spelling = backend.types.target_register_spelling(
        selected.to_target,
        selected.extension.isa_name,
        uses_sized_vector=True,
        lane_parameter=lane_parameter,
    )
    if register_spelling is None:
        return _no_target_register(selected, backend, selected.extension.isa_name)
    return TargetVector(
        vector_spelling=backend.types.sized_vector_spelling(
            to_base_spelling, lane_parameter
        ),
        register_spelling=register_spelling,
        extension_isa=selected.extension.isa_name,
        base_tag=selected.to_target,
        base_spelling=to_base_spelling,
        uses_sized_vector=True,
        lane_parameter=lane_parameter,
        windowed=windowing,
    )


def _resolve_base_target(
    selected: SelectedImplementation,
    catalog: Catalog,
    backend: BackendDialect,
    alias: str,
    scope: LoweringScope,
    support: SupportPolicy,
) -> TargetVector | Diagnostic:
    to_base_spelling = backend.types.scalar_spelling(selected.to_target)
    if to_base_spelling is None:
        return _no_target_base_type(selected, backend)
    scope.bind_target_type_symbol(alias, selected.to_target)
    scope.bind_target_type_symbol("ToType", selected.to_target)
    uses_sized_vector = support.uses_sized_vector(selected.extension)
    lane_parameter = (
        support.size_parameter_name(selected.extension) if uses_sized_vector else None
    )
    register_spelling = backend.types.target_register_spelling(
        selected.to_target,
        selected.extension.isa_name,
        uses_sized_vector=uses_sized_vector,
        lane_parameter=lane_parameter,
    )
    if register_spelling is None:
        return _no_target_register(selected, backend, selected.extension.isa_name)
    return TargetVector(
        vector_spelling=(
            backend.types.sized_vector_spelling(to_base_spelling, lane_parameter)
            if uses_sized_vector and lane_parameter is not None
            else backend.types.vector_type_spelling(
                to_base_spelling, selected.extension.isa_name
            )
        ),
        register_spelling=register_spelling,
        extension_isa=selected.extension.isa_name,
        base_tag=selected.to_target,
        base_spelling=to_base_spelling,
        uses_sized_vector=uses_sized_vector,
        lane_parameter=lane_parameter,
        native_register_spelling=translation_common.vector_register_type(
            catalog,
            backend.backend_id,
            selected.extension.isa_name,
            selected.to_target,
        ),
    )


def _resolve_extension_target(
    selected: SelectedImplementation,
    catalog: Catalog,
    backend: BackendDialect,
    base_type_spelling: str,
    alias: str,
    support: SupportPolicy,
    scope: LoweringScope,
) -> TargetVector | Diagnostic:
    target_ext = catalog.extensions.get(selected.to_target)
    target_isa = target_ext.isa_name if target_ext else selected.to_target
    target_uses_sized_vector = (
        target_ext is not None and support.uses_sized_vector(target_ext)
    )
    lane_count = support.lane_count(selected.extension, selected.type_tag)
    target_lane_parameter = (
        str(lane_count)
        if lane_count is not None
        else support.size_parameter_name(selected.extension)
    )
    scope.bind_extension_symbol(alias, target_isa)
    register_spelling = backend.types.target_register_spelling(
        selected.type_tag,
        target_isa,
        uses_sized_vector=target_uses_sized_vector,
        lane_parameter=target_lane_parameter,
    )
    if register_spelling is None:
        return _no_target_register(selected, backend, target_isa, selected.type_tag)
    return TargetVector(
        vector_spelling=(
            backend.types.sized_vector_spelling(base_type_spelling, target_lane_parameter)
            if target_uses_sized_vector
            else backend.types.vector_type_spelling(base_type_spelling, target_isa)
        ),
        register_spelling=register_spelling,
        extension_isa=target_isa,
        base_tag=selected.type_tag,
        base_spelling=base_type_spelling,
        uses_sized_vector=target_uses_sized_vector,
        lane_parameter=target_lane_parameter if target_uses_sized_vector else None,
        native_register_spelling=translation_common.vector_register_type(
            catalog,
            backend.backend_id,
            target_isa,
            selected.type_tag,
        ),
    )


def _sized_target_lane_parameter(
    selected: SelectedImplementation, support: SupportPolicy
) -> tuple[str, bool]:
    """Lane parameter for sized target vectors, including width-changing windows."""

    windowing = "direction" in selected.primitive.attributes
    if selected.concrete_lanes is not None:
        return (
            str(
                support.windowed_lane_count(
                    selected.type_tag, selected.to_target, selected.concrete_lanes
                )
                if windowing
                else selected.concrete_lanes
            ),
            windowing,
        )
    if windowing:
        return (
            support.windowed_lane_parameter(
                selected.extension, selected.type_tag, selected.to_target
            ),
            windowing,
        )
    return support.size_parameter_name(selected.extension), windowing


def _no_target_base_type(
    selected: SelectedImplementation, backend: BackendDialect
) -> Diagnostic:
    return lowering_error_diagnostic(
        "TSL-LOWER-NO-BASE-TYPE",
        f"no {backend.backend_id} base-type spelling for the target "
        f"{selected.to_target!r}",
        source=implementation_source(selected),
    )


def _no_target_register(
    selected: SelectedImplementation,
    backend: BackendDialect,
    extension_isa: str,
    type_tag: str | None = None,
) -> Diagnostic:
    return lowering_error_diagnostic(
        "TSL-LOWER-NO-REGISTER-TYPE",
        f"no {backend.backend_id} register-type spelling for target "
        f"{extension_isa!r} / {type_tag or selected.to_target!r}",
        source=implementation_source(selected),
    )
