"""Core scalar, type, intrinsic, and primitive query functions."""

from __future__ import annotations

from tslc.catalog.scalar_types import (
    is_signed,
    scalar_byte_width_or_default,
    signed_of,
    unsigned_of,
)
from tslc.lower._query_model import BoolValue, TextValue, TypeValue


class BaseInQuery:
    head = "base::in"

    def apply(self, args, context):  # noqa: ANN001 - protocol-typed
        return TypeValue(context.env.type_tag)


class SignedOfQuery:
    head = "base::signed_of"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TypeValue(signed_of(args[0].type_tag))


class UnsignedOfQuery:
    """``base::unsigned_of(x)`` -> the same-width unsigned integer tag."""

    head = "base::unsigned_of"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TypeValue(unsigned_of(args[0].type_tag))


class TypeQuery:
    """``type(x)`` passthrough wrapper."""

    head = "type"

    def apply(self, args, context):  # noqa: ANN001
        return args[0] if len(args) == 1 else None


class ValueQuery:
    """``value(x)`` passthrough wrapper."""

    head = "value"

    def apply(self, args, context):  # noqa: ANN001
        return args[0] if len(args) == 1 else None


class SelectQuery:
    """``select(cond, then, else)`` -> one already-evaluated branch."""

    head = "select"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 3 or not isinstance(args[0], BoolValue):
            return None
        true_value = args[1]
        false_value = args[2]
        if type(true_value) is not type(false_value):
            return None
        return true_value if args[0].value else false_value


class IntrinPrefixQuery:
    """``intrin::prefix`` -> the selected extension's backend intrinsic prefix."""

    head = "intrin::prefix"

    def apply(self, args, context):  # noqa: ANN001
        if args:
            return None
        fragment = context.env.extension.compose_prefix.get(context.env.backend.backend_id)
        return TextValue(fragment) if fragment is not None else None


class IntrinSuffixQuery:
    """``intrin::suffix(x)`` -> the composed intrinsic suffix fragment."""

    head = "intrin::suffix"

    def apply(self, args, context):  # noqa: ANN001
        if not args:
            fragment = context.env.extension.compose_suffix_by_type.get(context.env.type_tag)
            return TextValue(fragment) if fragment is not None else None
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            fragment = context.env.extension.compose_suffix_by_type.get(arg.type_tag)
            return TextValue(fragment) if fragment is not None else None
        if isinstance(arg, TextValue):
            key = f"intrinsic_suffix_{arg.as_text()}_{context.env.extension.name}"
            fragment = context.env.backend.templates.template(key)
            return TextValue(fragment) if fragment is not None else None
        return None


class IsSameQuery:
    """``type::is_same(a, b)`` -> generation-time boolean."""

    head = "type::is_same"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 2 or not all(isinstance(arg, TypeValue) for arg in args):
            return None
        return BoolValue(args[0].type_tag == args[1].type_tag)


class SizeBytesQuery:
    """``type::size_bytes(x)`` -> byte width of a type tag."""

    head = "type::size_bytes"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TextValue(str(scalar_byte_width_or_default(args[0].type_tag)))


class IsSignedQuery:
    """``type::is_signed(x)`` -> generation-time boolean."""

    head = "type::is_signed"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            return BoolValue(is_signed(arg.type_tag))
        if isinstance(arg, TextValue):
            return BoolValue(False)
        return None


class AttributeQuery:
    """``primitive::attribute(name)`` -> selected primitive attribute boolean."""

    head = "primitive::attribute"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        return BoolValue(context.env.attributes.get(args[0].as_text()) == "true")
