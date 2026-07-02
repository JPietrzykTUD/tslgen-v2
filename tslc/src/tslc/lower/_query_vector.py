"""Vector, register, mask, and generic query functions."""

from __future__ import annotations

from dataclasses import replace

from tslc.catalog.model import Extension
from tslc.lower._query_model import TextValue, TypeValue
from tslc.lower.context import LoweringSession, VectorValue
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def _vector_value(base_tag: str, context: LoweringSession) -> VectorValue:
    value = _vector_value_from_extension(base_tag, context.env.extension)
    if value.uses_sized_vector:
        return replace(value, lane_parameter=context.env.lane_symbol())
    return value


def _vector_value_for_extension(
    base_tag: str, extension_name: str, context: LoweringSession
) -> VectorValue | None:
    extension = _catalog_extension(extension_name, context)
    if extension is None:
        return None
    return _vector_value_from_extension(base_tag, extension)


def _vector_value_from_extension(base_tag: str, extension: Extension) -> VectorValue:
    uses_sized_vector = DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
    return VectorValue(
        base_tag=base_tag,
        extension_isa=extension.isa_name,
        lanes=DEFAULT_SUPPORT_POLICY.lane_count(extension, base_tag),
        uses_sized_vector=uses_sized_vector,
        lane_parameter=(
            DEFAULT_SUPPORT_POLICY.size_parameter_name(extension)
            if uses_sized_vector
            else None
        ),
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
    lanes = DEFAULT_SUPPORT_POLICY.lane_count(context.env.extension, base_tag)
    if lanes is None:
        lane_parameter = context.env.lane_symbol()
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

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.env.backend.types.register_type_spelling())


class RegisterGenericQuery:
    """``register::generic(x)`` -> concrete register type for a vector/base."""

    head = "register::generic"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            base_tag, isa = arg.type_tag, context.env.extension.isa_name
            uses_sized_vector = DEFAULT_SUPPORT_POLICY.uses_sized_vector(
                context.env.extension
            )
            lane_parameter = context.env.lane_symbol()
        elif isinstance(arg, VectorValue):
            base_tag, isa = arg.base_tag, arg.extension_isa
            uses_sized_vector = arg.uses_sized_vector
            lane_parameter = arg.lane_parameter
        else:
            return None
        spelling = context.env.backend.types.target_register_spelling(
            base_tag,
            isa,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
        )
        return TextValue(spelling) if spelling is not None else None


class MaskQuery:
    """``vector::mask`` -> backend spelling of the vector mask type."""

    head = "vector::mask"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.env.backend.types.mask_type_spelling())


class ImaskQuery:
    """``vector::imask`` -> integral-mask type or backend spelling."""

    head = "vector::imask"

    def apply(self, args, context):  # noqa: ANN001
        if context.env.extension.vector_bits == 0:
            if (
                DEFAULT_SUPPORT_POLICY.register_is_base(context.env.extension)
                or DEFAULT_SUPPORT_POLICY.uses_sized_vector(context.env.extension)
            ):
                return TypeValue("ui64")
        return TextValue(context.env.backend.types.imask_type_spelling())


class VectorAlignmentQuery:
    """``vector::alignment`` -> natural register byte alignment."""

    head = "vector::alignment"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(
            str(
                DEFAULT_SUPPORT_POLICY.vector_alignment_bytes(
                    context.env.extension, context.env.type_tag
                )
            )
        )


class VectorLengthQuery:
    """``vector::length`` -> generation-time lane count expression."""

    head = "vector::length"

    def apply(self, args, context):  # noqa: ANN001
        if context.env.concrete_lanes is not None:
            return TextValue(str(context.env.concrete_lanes))
        if DEFAULT_SUPPORT_POLICY.uses_scalable_vector(context.env.extension):
            return None
        return TextValue(
            DEFAULT_SUPPORT_POLICY.lane_expression(
                context.env.extension, context.env.type_tag
            )
        )


class AsExtensionQuery:
    """``vector::as_extension(ext)`` -> current base under a named extension."""

    head = "vector::as_extension"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        ext = args[0].as_text()
        extension = _catalog_extension(ext, context)
        if extension is not None and DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
            return _sized_vector_value(context.env.type_tag, extension, context)
        return _vector_value_for_extension(context.env.type_tag, ext, context)


class AsBaseQuery:
    """``vector::as_base(base)`` -> given base under the current extension."""

    head = "vector::as_base"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return _vector_value(args[0].type_tag, context)


class WindowBaseQuery:
    """``vector::window_base(base)`` -> re-base at constant total bit width."""

    head = "vector::window_base"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        to_base = args[0].type_tag
        extension = context.env.extension
        if not DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
            return _vector_value(to_base, context)
        if context.env.concrete_lanes is not None:
            return VectorValue(
                base_tag=to_base,
                extension_isa=extension.isa_name,
                lanes=None,
                uses_sized_vector=True,
                lane_parameter=str(
                    DEFAULT_SUPPORT_POLICY.windowed_lane_count(
                        context.env.type_tag, to_base, context.env.concrete_lanes
                    )
                ),
            )
        lane_parameter = DEFAULT_SUPPORT_POLICY.windowed_lane_parameter(
            extension, context.env.type_tag, to_base
        )
        if lane_parameter == DEFAULT_SUPPORT_POLICY.size_parameter_name(extension):
            return _vector_value(to_base, context)
        if not context.env.backend.supports_sized_vector_lane_expressions:
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

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 2:
            return None
        ext_arg, base_arg = args
        if not isinstance(ext_arg, TextValue) or not isinstance(base_arg, TypeValue):
            return None
        return _vector_value_for_extension(base_arg.type_tag, ext_arg.as_text(), context)


class BaseGenericQuery:
    """``base::generic(V)`` -> base type tag of a vector value."""

    head = "base::generic"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], VectorValue):
            return None
        return TypeValue(args[0].base_tag)


class GenericLengthQuery:
    """``generic::length(V)`` -> lane count of a vector value."""

    head = "generic::length"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], VectorValue):
            return None
        value = args[0]
        if value.lanes is not None:
            return TextValue(str(value.lanes))
        if value.lane_parameter is not None:
            return TextValue(value.lane_parameter)
        return None
