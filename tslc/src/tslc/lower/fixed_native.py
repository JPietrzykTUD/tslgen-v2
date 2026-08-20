"""Typed ABI adaptation from compiler-vector overlays to exact-width native leaves."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.catalog.model import (
    RESULT_DIM_BASE,
    RESULT_DIM_VECTOR,
    Extension,
    PrimitiveMaskMode,
)
from tslc.catalog.signatures import SignatureShape
from tslc.lower.body_rendering import RenderedBodyResult
from tslc.lower.context import LoweringSession
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    VectorIdentity,
)
from tslc.lower.target_vectors import TargetVector
from tslc.select.selector import SelectedImplementation
from tslc.target_text import (
    RenderField,
    as_render_text,
    literal_text,
    render_sequence,
    unsafe_block,
)

_PASSTHROUGH_PARAM_KINDS = frozenset(
    {
        "im",
        "imt",
        "lanes<s>",
        "o",
        "ptr",
        "ptr+",
        "cptr",
        "cptr+",
        "s",
        "s[]",
        "usize",
    }
)
_PASSTHROUGH_RESULT_KINDS = frozenset({"im", "o", "s", "usize", "void"})


def lower_preferred_fixed_native(
    selected: SelectedImplementation,
    shape: SignatureShape,
    context: LoweringSession,
    *,
    current_register_spelling: str,
    target: TargetVector | None,
) -> RenderedBodyResult | None:
    """Lower an opted-in overlay body through its selected native substrate.

    The authored body remains the fallback whenever selection has no intrinsic
    leaf of exactly the same width. This function owns only representation
    adaptation; the primitive call still targets the generated public wrapper,
    so dependency closure and the hardware implementation remain ordinary
    compiler facts.
    """

    fixed = context.env.fixed_native_fallback_extension
    if (
        not selected.implementation.prefer_fixed_native
        or fixed is None
        or context.env.backend.backend_id != "cpp"
    ):
        return None

    # These primitives define the mask bridge used by every other delegated
    # call. Delegating either through itself would introduce a dependency cycle.
    if selected.primitive.name in {"to_integral", "to_mask"}:
        return None

    target_vectors = _target_vectors(selected, context, fixed.isa_name, target)
    if target_vectors is None:
        return None
    fixed_target, fixed_target_register = target_vectors

    if not _supports_shape(shape, target is not None):
        return None

    source = VectorIdentity(selected.type_tag, selected.extension.isa_name)
    fixed_source = VectorIdentity(selected.type_tag, fixed.isa_name)
    fixed_source_spelling = _fixed_facade_spelling(fixed_source, fixed, context)
    fixed_source_register = context.env.backend.types.target_register_spelling(
        selected.type_tag,
        fixed.isa_name,
    )
    if fixed_source_spelling is None or fixed_source_register is None:
        return None
    fixed_target_spelling = (
        None
        if fixed_target is None
        else _fixed_facade_spelling(fixed_target, fixed, context)
    )
    if fixed_target is not None and fixed_target_spelling is None:
        return None

    fixed_index_register: str | None = None
    fixed_generic_spellings: dict[str, str] = {}
    if "vidx" in shape.param_kinds:
        resolved_index = _fixed_index_abi(selected, fixed, context)
        if resolved_index is None:
            return None
        (
            index_param_name,
            fixed_index_register,
            fixed_index_spelling,
        ) = resolved_index
        fixed_generic_spellings[index_param_name] = fixed_index_spelling

    args: list[RenderField] = []
    for name, kind in zip(
        selected.primitive.parameters,
        shape.param_kinds,
        strict=True,
    ):
        adapted = _adapt_parameter(
            name,
            kind,
            source=source,
            fixed_source=fixed_source,
            fixed_source_register=fixed_source_register,
            fixed_source_spelling=fixed_source_spelling,
            fixed_index_register=fixed_index_register,
            fixed_target=fixed_target,
            fixed_target_register=fixed_target_register,
            context=context,
        )
        if isinstance(adapted, _Unsupported):
            return None
        if adapted is not None:
            args.append(adapted)

    call = _render_self_call(
        selected,
        context,
        fixed,
        fixed_source,
        fixed_source_spelling,
        fixed_target,
        fixed_target_spelling,
        fixed_generic_spellings,
        bool(shape.param_kinds and shape.param_kinds[0] == "m"),
        tuple(args),
    )
    if call is None:
        return None
    result = _adapt_result(
        call,
        shape.result_kind,
        source=source,
        fixed_source=fixed_source,
        fixed_source_spelling=fixed_source_spelling,
        current_register_spelling=(
            target.register_spelling if target is not None else current_register_spelling
        ),
        context=context,
    )
    if isinstance(result, _Unsupported):
        return None

    context.effects.mark_composition()
    statement = (
        as_render_text(result)
        if shape.result_kind == "void"
        else context.env.backend.syntax.frame_return(result)
    )
    rendered = render_sequence((as_render_text(statement), literal_text(";")))
    return RenderedBodyResult(
        rendered=as_render_text(rendered),
        safety=context.effects.safety,
        implementation_state=context.effects.implementation_state(selected),
        diagnostics=tuple(context.effects.diagnostics),
    )


class _Unsupported:
    pass


_UNSUPPORTED = _Unsupported()


def _supports_shape(shape: SignatureShape, has_target: bool) -> bool:
    supported_params = _PASSTHROUGH_PARAM_KINDS | {"m", "sImm", "v", "vidx"}
    if has_target:
        supported_params = supported_params | {"vt"}
    return set(shape.param_kinds) <= supported_params and (
        shape.result_kind in _PASSTHROUGH_RESULT_KINDS | {"m", "v", "void"}
    )


def _fixed_index_abi(
    selected: SelectedImplementation,
    fixed_extension: Extension,
    context: LoweringSession,
) -> tuple[str, str, str] | None:
    simd_params = tuple(
        param
        for param in selected.primitive.generic_params
        if param.kind == "simd_type"
    )
    if len(simd_params) != 1:
        return None
    param = simd_params[0]
    base_tag = next(
        (
            binding.base_tag
            for binding in selected.simd_type_base_bindings
            if binding.param_name == param.name
        ),
        None,
    )
    if base_tag is not None:
        spelling = _fixed_facade_spelling(
            VectorIdentity(base_tag, fixed_extension.isa_name),
            fixed_extension,
            context,
        )
        register = context.env.backend.types.target_register_spelling(
            base_tag,
            fixed_extension.isa_name,
        )
    else:
        base_spelling = context.env.backend.types.simd_type_param_base_spelling(
            param.name
        )
        lane_count = context.env.backend.types.simd_type_param_lane_count_spelling(
            param.name,
            runtime=False,
        )
        spelling = context.env.backend.types.fixed_vector_spelling(
            base_spelling,
            lane_count,
        )
        register = (
            None
            if spelling is None
            else context.env.backend.types.simd_type_param_register_spelling(
                spelling
            )
        )
    if spelling is None or register is None:
        return None
    return param.name, register, spelling


def _target_vectors(
    selected: SelectedImplementation,
    context: LoweringSession,
    fixed_isa: str,
    target: TargetVector | None,
) -> tuple[VectorIdentity | None, str | None] | None:
    result_target = selected.primitive.result_target
    if result_target is None:
        return (None, None)
    dimension, _alias = result_target
    if dimension == RESULT_DIM_VECTOR or dimension != RESULT_DIM_BASE:
        return None
    if target is None or selected.to_target is None:
        return None
    fixed_target = VectorIdentity(selected.to_target, fixed_isa)
    register = context.env.backend.types.target_register_spelling(
        fixed_target.base_tag,
        fixed_target.extension_isa,
    )
    if register is None:
        return None
    return fixed_target, register


def _adapt_parameter(
    name: str,
    kind: str,
    *,
    source: VectorIdentity,
    fixed_source: VectorIdentity,
    fixed_source_register: str,
    fixed_source_spelling: str,
    fixed_index_register: str | None,
    fixed_target: VectorIdentity | None,
    fixed_target_register: str | None,
    context: LoweringSession,
) -> RenderField | _Unsupported | None:
    value = literal_text(name)
    if kind == "sImm":
        return None
    if kind == "v":
        return _bitcast(fixed_source_register, value, context)
    if kind == "m":
        return _convert_mask(
            value,
            source,
            fixed_source,
            context,
            target_spelling=fixed_source_spelling,
        )
    if kind == "vidx":
        return (
            _UNSUPPORTED
            if fixed_index_register is None
            else _bitcast(fixed_index_register, value, context)
        )
    if kind == "vt":
        if fixed_target is None or fixed_target_register is None:
            return _UNSUPPORTED
        return _bitcast(fixed_target_register, value, context)
    if kind in _PASSTHROUGH_PARAM_KINDS:
        return value
    return _UNSUPPORTED


def _adapt_result(
    value: RenderField,
    kind: str,
    *,
    source: VectorIdentity,
    fixed_source: VectorIdentity,
    fixed_source_spelling: str,
    current_register_spelling: str,
    context: LoweringSession,
) -> RenderField | _Unsupported:
    if kind == "v":
        return _bitcast(current_register_spelling, value, context)
    if kind == "m":
        return _convert_mask(
            value,
            fixed_source,
            source,
            context,
            source_spelling=fixed_source_spelling,
        )
    if kind in _PASSTHROUGH_RESULT_KINDS:
        return value
    return _UNSUPPORTED


def _convert_mask(
    value: RenderField,
    source: VectorIdentity,
    target: VectorIdentity,
    context: LoweringSession,
    *,
    source_spelling: str | None = None,
    target_spelling: str | None = None,
) -> RenderField:
    packed = _render_primitive_call(
        "to_integral",
        source,
        (value,),
        context,
        vector_spelling=source_spelling,
    )
    return _render_primitive_call(
        "to_mask",
        target,
        (packed,),
        context,
        vector_spelling=target_spelling,
    )


def _render_self_call(
    selected: SelectedImplementation,
    context: LoweringSession,
    fixed_extension: Extension,
    source: VectorIdentity,
    source_spelling: str,
    target: VectorIdentity | None,
    target_spelling: str | None,
    fixed_generic_spellings: Mapping[str, str],
    has_explicit_mask_arg: bool,
    args: tuple[RenderField, ...],
) -> RenderField | None:
    extra_args: list[RenderField] = []
    if target is not None:
        if target_spelling is None:
            return None
        extra_args.append(literal_text(target_spelling))
    bindings = {
        binding.param_name: binding.base_tag
        for binding in selected.simd_type_base_bindings
    }
    for param in selected.primitive.generic_params:
        if param.kind != "simd_type":
            continue
        spelling = fixed_generic_spellings.get(param.name)
        if spelling is None:
            base_tag = bindings.get(param.name)
            if base_tag is None:
                return None
            spelling = _fixed_facade_spelling(
                VectorIdentity(base_tag, fixed_extension.isa_name),
                fixed_extension,
                context,
            )
        if spelling is None:
            return None
        extra_args.append(literal_text(spelling))
    if context.env.immediate_name is not None:
        extra_args.append(literal_text(context.env.immediate_name))
    for param in selected.primitive.generic_params:
        if param.kind != "simd_type":
            extra_args.append(literal_text(param.name))
    return _render_primitive_call(
        selected.primitive.name,
        source,
        args,
        context,
        vector_spelling=source_spelling,
        mask_policy=selected.primitive.mask_mode,
        target=target,
        attributes=selected.primitive.attributes,
        explicit_mask_args=has_explicit_mask_arg,
        immediate_forwarded=context.env.immediate_name is not None,
        extra_args=tuple(extra_args),
    )


def _render_primitive_call(
    primitive_name: str,
    source: VectorIdentity,
    args: tuple[RenderField, ...],
    context: LoweringSession,
    *,
    vector_spelling: str | None = None,
    mask_policy: PrimitiveMaskMode | None = None,
    target: VectorIdentity | None = None,
    attributes: Mapping[str, str] | None = None,
    explicit_mask_args: bool = False,
    immediate_forwarded: bool = False,
    extra_args: tuple[RenderField, ...] = (),
) -> RenderField:
    context.effects.record_call_dependency(
        CallDependencyOrigin(
            CallDependency(primitive_name, mask_policy, source, target),
            context.env.dependency_origin,
        )
    )
    call_name = primitive_name
    if mask_policy is not None and primitive_name in context.env.policy_split_names:
        call_name = f"{call_name}{context.env.support.mask_suffix(mask_policy)}"
    if (
        explicit_mask_args
        and primitive_name in context.env.explicit_mask_split_names
    ):
        call_name = f"{call_name}_mask"
    if immediate_forwarded and primitive_name in context.env.immediate_split_names:
        call_name = f"{call_name}_imm"
    attrs = attributes if attributes is not None else context.env.attributes
    axis_values = tuple(
        attrs.get(key, "false")
        for key in context.env.primitive_axes.get(primitive_name, ())
    )
    call = context.env.backend.syntax.render_call(
        call_name,
        _comma_join(args),
        axis_values,
        context.env.primitive_arg_generics.get(call_name, 0),
        literal_text(vector_spelling or _vector_spelling(source, context)),
        extra_args,
    )
    if context.env.primitive_caller_unsafe.get(primitive_name, False):
        return unsafe_block(call)
    return call


def _vector_spelling(identity: VectorIdentity, context: LoweringSession) -> str:
    base = context.env.backend.types.scalar_spelling(identity.base_tag)
    if base is None:
        raise ValueError(f"no scalar spelling for {identity.base_tag!r}")
    return context.env.backend.types.vector_type_spelling(
        base,
        identity.extension_isa,
    )


def _fixed_facade_spelling(
    identity: VectorIdentity,
    fixed_extension: Extension,
    context: LoweringSession,
) -> str | None:
    lanes = context.env.support.lane_count(fixed_extension, identity.base_tag)
    if lanes is None:
        return None
    base = context.env.backend.types.scalar_spelling(identity.base_tag)
    if base is None:
        return None
    return context.env.backend.types.fixed_vector_spelling(base, lanes)


def _bitcast(
    target: str,
    value: RenderField,
    context: LoweringSession,
) -> RenderField:
    return context.env.backend.templates.render_template(
        "cast_bitcast",
        "::tsl::bit_cast<{type}>({expr})",
        type=literal_text(target),
        expr=value,
    )


def _comma_join(values: tuple[RenderField, ...]) -> RenderField:
    parts: list[RenderField] = []
    for value in values:
        if parts:
            parts.append(literal_text(", "))
        parts.append(value)
    return render_sequence(tuple(as_render_text(part) for part in parts))


__all__ = ("lower_preferred_fixed_native",)
