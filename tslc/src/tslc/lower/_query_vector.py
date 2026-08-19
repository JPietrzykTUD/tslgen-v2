"""Vector, register, mask, and generic query functions."""

from __future__ import annotations

from dataclasses import replace

from tslc.catalog.model import Extension
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.lane_count import LaneCount
from tslc.lower._query_model import (
    QueryValue,
    TextValue,
    TypeValue,
    query_argument,
    query_function,
)
from tslc.lower.object_representation import register_object_size
from tslc.lower.context import (
    LoweringSession,
    SimdTypeParameterValue,
    VectorSpellingPolicy,
    VectorValue,
)
from tslc.support_policy import SupportPolicy


def _vector_value(base_tag: str, context: LoweringSession) -> VectorValue:
    value = _vector_value_from_extension(
        base_tag, context.env.extension, context.env.support
    )
    if value.uses_sized_vector:
        return replace(
            value,
            lane_parameter=LaneCount.symbolic(context.env.lane_symbol()),
        )
    return value


def _vector_value_for_extension(
    base_tag: str, extension_name: str, context: LoweringSession
) -> VectorValue | None:
    extension = _catalog_extension(extension_name, context)
    if extension is None:
        return None
    return _vector_value_from_extension(base_tag, extension, context.env.support)


def _vector_value_from_extension(
    base_tag: str, extension: Extension, support: SupportPolicy
) -> VectorValue:
    uses_sized_vector = support.uses_sized_vector(extension)
    return VectorValue(
        base_tag=base_tag,
        extension_isa=extension.isa_name,
        lanes=support.lane_count(extension, base_tag),
        uses_sized_vector=uses_sized_vector,
        lane_parameter=(
            LaneCount.symbolic(support.size_parameter_name(extension))
            if uses_sized_vector
            else None
        ),
    )


def _fixed_facade_value(
    base_tag: str, context: LoweringSession
) -> VectorValue | None:
    extension = context.env.fixed_fallback_extension
    if extension is None:
        context.effects.skip(
            "TSL-LOWER-NO-FIXED-FALLBACK",
            f"extension {context.env.extension.name!r} has no emitted "
            "hardware-backed fixed-width fallback for this primitive and type",
        )
        return None
    return replace(
        _vector_value_from_extension(base_tag, extension, context.env.support),
        spelling_policy=VectorSpellingPolicy.FIXED_FACADE,
    )


def _catalog_extension(extension_name: str, context: LoweringSession) -> Extension | None:
    catalog = context.env.catalog
    extension = catalog.extensions.get(extension_name)
    if extension is not None:
        return extension
    for candidate in catalog.extensions.values():
        if candidate.isa_name == extension_name:
            return candidate
    return None


def _sized_vector_value(
    base_tag: str, extension: Extension, context: LoweringSession
) -> VectorValue | None:
    lanes = context.env.support.lane_count(context.env.extension, base_tag)
    if lanes is None:
        lane_parameter = LaneCount.symbolic(context.env.lane_symbol())
    else:
        lane_parameter = None
    return VectorValue(
        base_tag=base_tag,
        extension_isa=extension.isa_name,
        lanes=lanes,
        uses_sized_vector=True,
        lane_parameter=lane_parameter,
    )


class RegisterQuery:
    """``vector::register`` -> backend spelling of the vector register type."""

    head = "vector::register"
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return TextValue(
            context.env.backend.types.register_type_spelling(),
            object_size=register_object_size(
                context.env.type_tag,
                context.env.extension,
                uses_sized_vector=context.env.support.uses_sized_vector(
                    context.env.extension
                ),
                lane_count=(
                    LaneCount.fixed(context.env.concrete_lanes)
                    if context.env.concrete_lanes is not None
                    else LaneCount.symbolic(context.env.lane_symbol())
                ),
            ),
            all_bit_patterns_valid=scalar_bit_width(context.env.type_tag) is not None,
        )


class RegisterGenericQuery:
    """``register::generic(x)`` -> concrete register type for a vector/base."""

    head = "register::generic"
    descriptor = query_function(
        "text",
        arguments=(query_argument("type", "vector", "simd_type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1:
            return None
        arg = args[0]
        lane_count: LaneCount | None
        if isinstance(arg, TypeValue):
            base_tag, isa = arg.type_tag, context.env.extension.isa_name
            uses_sized_vector = context.env.support.uses_sized_vector(
                context.env.extension
            )
            lane_count = LaneCount.symbolic(context.env.lane_symbol())
        elif isinstance(arg, VectorValue):
            base_tag, isa = arg.base_tag, arg.extension_isa
            uses_sized_vector = arg.uses_sized_vector
            lane_count = arg.lane_parameter
        elif isinstance(arg, SimdTypeParameterValue):
            spelling = _simd_type_param_register_spelling(arg, context)
            return TextValue(spelling) if spelling is not None else None
        else:
            return None
        lane_parameter = (
            context.env.backend.types.render_lane_count(lane_count)
            if lane_count is not None
            else None
        )
        if uses_sized_vector and lane_parameter is None:
            return None
        spelling = context.env.backend.types.target_register_spelling(
            base_tag,
            isa,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
        )
        extension = _catalog_extension(isa, context)
        return (
            TextValue(
                spelling,
                object_size=(
                    register_object_size(
                        base_tag,
                        extension,
                        uses_sized_vector=uses_sized_vector,
                        lane_count=lane_count,
                    )
                    if extension is not None
                    else None
                ),
                all_bit_patterns_valid=(
                    extension is not None and scalar_bit_width(base_tag) is not None
                ),
            )
            if spelling is not None
            else None
        )


class MaskQuery:
    """``vector::mask`` -> backend spelling of the vector mask type."""

    head = "vector::mask"
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return TextValue(context.env.backend.types.mask_type_spelling())


class ImaskQuery:
    """``vector::imask`` -> integral-mask type or backend spelling."""

    head = "vector::imask"
    descriptor = query_function("type", "text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if context.env.extension.vector_bits == 0:
            if (
                context.env.support.register_is_base(context.env.extension)
                or context.env.support.uses_sized_vector(context.env.extension)
            ):
                return TypeValue("ui64")
        return TextValue(context.env.backend.types.imask_type_spelling())


class VectorAlignmentQuery:
    """``vector::alignment`` -> natural register byte alignment."""

    head = "vector::alignment"
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return TextValue(
            str(
                context.env.support.vector_alignment_bytes(
                    context.env.extension, context.env.type_tag
                )
            )
        )


class VectorLengthQuery:
    """``vector::length`` -> generation-time lane count expression."""

    head = "vector::length"
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if context.env.concrete_lanes is not None:
            return TextValue(str(context.env.concrete_lanes))
        if context.env.support.uses_scalable_vector(context.env.extension):
            return None
        return TextValue(
            context.env.support.lane_expression(
                context.env.extension, context.env.type_tag
            )
        )


class VectorRuntimeLengthQuery:
    """``vector::runtime_length`` -> lane count expression valid at runtime."""

    head = "vector::runtime_length"
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if args:
            return None
        if context.env.concrete_lanes is not None:
            return TextValue(str(context.env.concrete_lanes))
        if context.env.support.uses_sized_vector(context.env.extension):
            return TextValue(context.env.lane_symbol())
        lanes = context.env.support.lane_count(
            context.env.extension, context.env.type_tag
        )
        if lanes is not None:
            return TextValue(str(lanes))
        return _runtime_lane_count_text(
            context.env.extension,
            context.env.type_tag,
            context,
        )


class AsExtensionQuery:
    """``vector::as_extension(ext)`` -> current base under a named extension."""

    head = "vector::as_extension"
    descriptor = query_function(
        "vector",
        arguments=(query_argument("text", role="extension"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        ext = args[0].as_text()
        extension = _catalog_extension(ext, context)
        if extension is not None and context.env.support.uses_sized_vector(extension):
            return _sized_vector_value(context.env.type_tag, extension, context)
        return _vector_value_for_extension(context.env.type_tag, ext, context)


class FixedFacadeQuery:
    """``vector::fixed([base])`` -> the profile's exact-width hardware facade.

    With no argument it keeps the current base; a type argument rebases the facade.

    The backend-scoped selector records the concrete extension used for
    dependency closure; the active dialect spells its public facade.
    """

    head = "vector::fixed"
    descriptor = query_function(
        "vector",
        arguments=(query_argument("type"),),
        min_arguments=0,
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if not args:
            base_tag = context.env.type_tag
        elif len(args) == 1 and isinstance(args[0], TypeValue):
            base_tag = args[0].type_tag
        else:
            return None
        return _fixed_facade_value(base_tag, context)


class AsBaseQuery:
    """``vector::as_base(base)`` -> given base under the current extension."""

    head = "vector::as_base"
    descriptor = query_function(
        "vector",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return _vector_value(args[0].type_tag, context)


class WindowBaseQuery:
    """``vector::window_base(base)`` -> re-base at constant total bit width."""

    head = "vector::window_base"
    descriptor = query_function(
        "vector",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        to_base = args[0].type_tag
        extension = context.env.extension
        if not context.env.support.uses_sized_vector(extension):
            return _vector_value(to_base, context)
        if context.env.concrete_lanes is not None:
            return VectorValue(
                base_tag=to_base,
                extension_isa=extension.isa_name,
                lanes=None,
                uses_sized_vector=True,
                lane_parameter=LaneCount.fixed(
                    context.env.support.windowed_lane_count(
                        context.env.type_tag, to_base, context.env.concrete_lanes
                    )
                ),
            )
        lane_parameter = context.env.support.windowed_lane_parameter(
            extension, context.env.type_tag, to_base
        )
        if lane_parameter.is_plain_symbol(
            context.env.support.size_parameter_name(extension)
        ):
            return _vector_value(to_base, context)
        if context.env.backend.types.render_lane_count(lane_parameter) is None:
            context.effects.skip(
                "TSL-LOWER-SIZED-WIDTH-CHANGE",
                f"sized-vector windowing convert ({context.env.type_tag} -> {to_base}) needs a "
                "lane-count expression unsupported by this backend; skipped pending unroll",
            )
            return _vector_value(to_base, context)
        return VectorValue(
            base_tag=to_base,
            extension_isa=extension.isa_name,
            lanes=None,
            uses_sized_vector=True,
            lane_parameter=lane_parameter,
        )


class VectorAsQuery:
    """``vector::as(ext, base)`` -> the given base under the named extension."""

    head = "vector::as"
    descriptor = query_function(
        "vector",
        arguments=(
            query_argument("text", role="extension"),
            query_argument("type"),
        ),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 2:
            return None
        ext_arg, base_arg = args
        if not isinstance(ext_arg, TextValue) or not isinstance(base_arg, TypeValue):
            return None
        return _vector_value_for_extension(base_arg.type_tag, ext_arg.as_text(), context)


class BaseGenericQuery:
    """``base::generic(V)`` -> base type tag of a vector value."""

    head = "base::generic"
    descriptor = query_function(
        "type",
        "text",
        arguments=(query_argument("vector", "simd_type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, VectorValue):
            return TypeValue(arg.base_tag)
        if isinstance(arg, SimdTypeParameterValue):
            binding = context.env.simd_type_param_base_bindings.get(arg.name)
            if binding is not None:
                return TypeValue(binding)
            spelling = _simd_type_param_base_spelling(arg, context)
            return TextValue(spelling) if spelling is not None else None
        return None


class GenericLengthQuery:
    """``generic::length(V)`` -> lane count of a vector value."""

    head = "generic::length"
    descriptor = query_function(
        "text",
        arguments=(query_argument("vector", "simd_type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1:
            return None
        value = args[0]
        if isinstance(value, SimdTypeParameterValue):
            spelling = _simd_type_param_lane_count_spelling(
                value,
                context,
                runtime=False,
            )
            return TextValue(spelling) if spelling is not None else None
        if isinstance(value, VectorValue):
            if value.lanes is not None:
                return TextValue(str(value.lanes))
            if value.lane_parameter is not None:
                spelling = context.env.backend.types.render_lane_count(
                    value.lane_parameter
                )
                return TextValue(spelling) if spelling is not None else None
        return None


class GenericRuntimeLengthQuery:
    """``generic::runtime_length(V)`` -> runtime lane count of a vector value."""

    head = "generic::runtime_length"
    descriptor = query_function(
        "text",
        arguments=(query_argument("vector", "simd_type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1:
            return None
        value = args[0]
        if isinstance(value, SimdTypeParameterValue):
            spelling = _simd_type_param_lane_count_spelling(
                value,
                context,
                runtime=True,
            )
            return TextValue(spelling) if spelling is not None else None
        if not isinstance(value, VectorValue):
            return None
        if value.lanes is not None:
            return TextValue(str(value.lanes))
        if value.lane_parameter is not None:
            spelling = context.env.backend.types.render_lane_count(
                value.lane_parameter
            )
            return TextValue(spelling) if spelling is not None else None
        extension = _catalog_extension(value.extension_isa, context)
        if extension is None:
            return None
        return _runtime_lane_count_text(extension, value.base_tag, context)


def _runtime_lane_count_text(
    extension: Extension,
    type_tag: str,
    context: LoweringSession,
) -> TextValue | None:
    template = extension.runtime_lane_count.get(context.env.backend.backend_id)
    if template is None:
        return None
    base = context.env.backend.types.scalar_spelling(type_tag) or type_tag
    return TextValue(
        template.replace("{base_type}", base)
        .replace("{base}", base)
        .replace("{type_tag}", type_tag)
    )


def _simd_type_param_base_spelling(
    value: SimdTypeParameterValue,
    context: LoweringSession,
) -> str | None:
    return context.env.backend.types.simd_type_param_base_spelling(value.name)


def _simd_type_param_register_spelling(
    value: SimdTypeParameterValue,
    context: LoweringSession,
) -> str | None:
    return context.env.backend.types.simd_type_param_register_spelling(value.name)


def _simd_type_param_lane_count_spelling(
    value: SimdTypeParameterValue,
    context: LoweringSession,
    *,
    runtime: bool,
) -> str | None:
    return context.env.backend.types.simd_type_param_lane_count_spelling(
        value.name,
        runtime=runtime,
    )
