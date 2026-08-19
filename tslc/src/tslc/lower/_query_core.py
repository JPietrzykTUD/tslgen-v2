"""Core scalar, type, intrinsic, and primitive query functions."""

from __future__ import annotations

from tslc.catalog.scalar_types import (
    is_signed,
    same_scalar_width,
    scalar_bit_width_or_default,
    scalar_byte_width_or_default,
    signed_of,
    unsigned_of,
)
from tslc.lower._query_model import (
    BoolValue,
    QueryValue,
    TextValue,
    TypeValue,
    query_argument,
    query_function,
)
from tslc.lower.context import LoweringSession


class BaseInQuery:
    head = "base::in"
    descriptor = query_function("type")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return TypeValue(context.env.type_tag)


class SignedOfQuery:
    head = "base::signed_of"
    descriptor = query_function(
        "type",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TypeValue(signed_of(args[0].type_tag))


class UnsignedOfQuery:
    """``base::unsigned_of(x)`` -> the same-width unsigned integer tag."""

    head = "base::unsigned_of"
    descriptor = query_function(
        "type",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TypeValue(unsigned_of(args[0].type_tag))


class TypeQuery:
    """``type(x)`` passthrough wrapper."""

    head = "type"
    descriptor = query_function(
        "type",
        "text",
        "bool",
        "vector",
        "simd_type",
        arguments=(query_argument(),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return args[0] if len(args) == 1 else None


class ValueQuery:
    """``value(x)`` passthrough wrapper."""

    head = "value"
    descriptor = query_function(
        "type",
        "text",
        "bool",
        "vector",
        "simd_type",
        arguments=(query_argument(),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        return args[0] if len(args) == 1 else None


class SelectQuery:
    """``select(cond, then, else)`` -> one already-evaluated branch."""

    head = "select"
    descriptor = query_function(
        "type",
        "text",
        "bool",
        "vector",
        "simd_type",
        arguments=(
            query_argument("bool"),
            query_argument(),
            query_argument(),
        ),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
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
    descriptor = query_function("text")

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if args:
            return None
        fragment = context.env.extension.intrinsic_composition.prefix_by_backend.get(
            context.env.backend.backend_id
        )
        return TextValue(fragment) if fragment is not None else None


class IntrinSuffixQuery:
    """``intrin::suffix(x)`` -> the composed intrinsic suffix fragment."""

    head = "intrin::suffix"
    descriptor = query_function(
        "text",
        arguments=(query_argument("type", "text"),),
        min_arguments=0,
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if not args:
            fragment = context.env.extension.intrinsic_composition.suffix_by_type.get(
                context.env.type_tag
            )
            return TextValue(fragment) if fragment is not None else None
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            fragment = context.env.extension.intrinsic_composition.suffix_by_type.get(
                arg.type_tag
            )
            return TextValue(fragment) if fragment is not None else None
        if isinstance(arg, TextValue):
            key = f"intrinsic_suffix_{arg.as_text()}_{context.env.extension.name}"
            fragment = context.env.backend.templates.template(key)
            return TextValue(fragment) if fragment is not None else None
        return None


class IsSameQuery:
    """``type::is_same(a, b)`` -> generation-time boolean."""

    head = "type::is_same"
    descriptor = query_function(
        "bool",
        arguments=(query_argument("type"), query_argument("type")),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 2:
            return None
        left, right = args
        if not isinstance(left, TypeValue) or not isinstance(right, TypeValue):
            return None
        return BoolValue(left.type_tag == right.type_tag)


class SizeBytesQuery:
    """``type::size_bytes(x)`` -> byte width of a type tag."""

    head = "type::size_bytes"
    descriptor = query_function(
        "text",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TextValue(str(scalar_byte_width_or_default(args[0].type_tag)))


class SizeBitsQuery:
    """``type::size_bits(x)`` -> bit width of a type tag."""

    head = "type::size_bits"
    descriptor = query_function(
        "text",
        arguments=(query_argument("type"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TextValue(str(scalar_bit_width_or_default(args[0].type_tag)))


class SameSizeQuery:
    """``type::same_size(a, b)`` -> whether two scalar tags have equal bit width."""

    head = "type::same_size"
    descriptor = query_function(
        "bool",
        arguments=(query_argument("type"), query_argument("type")),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 2:
            return None
        left, right = args
        if not isinstance(left, TypeValue) or not isinstance(right, TypeValue):
            return None
        return BoolValue(same_scalar_width(left.type_tag, right.type_tag))


class IsSignedQuery:
    """``type::is_signed(x)`` -> generation-time boolean."""

    head = "type::is_signed"
    descriptor = query_function(
        "bool",
        arguments=(query_argument("type", "text"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
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
    descriptor = query_function(
        "bool",
        arguments=(query_argument("text", role="attribute"),),
    )

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        return BoolValue(context.env.attributes.get(args[0].as_text()) == "true")
