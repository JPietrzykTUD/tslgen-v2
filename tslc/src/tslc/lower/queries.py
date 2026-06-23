"""Evaluate the small TSIL generation/backend query language.

Queries are the nested ``head(arg)`` forms that appear inside intrinsic
modifiers, e.g.::

    value<backend>(intrin::suffix(type<generation>(base::signed_of(type<generation>(base::in)))))

Design (so this grows by *vocabulary*, not by lengthening a function):

- :class:`QueryParser` turns query text into a uniform :class:`QueryTerm` tree.
- A :class:`QueryValue` is the typed result of evaluating a term (a resolved
  type tag or a literal fragment). New value kinds are added as new queries
  need them (e.g. an int for ``vector::length``).
- Each query head is a small :class:`QueryFunction` class registered by head
  name. :class:`QueryEvaluator` evaluates a term's arguments, then dispatches
  to the matching function. Adding ``intrin::prefix`` or ``vector::length`` is a
  new ``QueryFunction`` class plus one registry entry — no edits to a megafunction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Protocol

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from tslc.backend.translation import (
    is_signed,
    is_type_tag,
    signed_of,
    unsigned_of,
)
from tslc.catalog.model import Extension
from tslc.lower._text import split_head_arg, split_top_level
from tslc.lower.context import LoweringSession, VectorValue
from tslc.render.model import RenderField, render_text
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


# --- query value types (extend as new queries need new result kinds) ---------


@dataclass(frozen=True, slots=True)
class TypeValue:
    type_tag: str


@dataclass(frozen=True, slots=True)
class TextValue:
    text: RenderField

    def as_text(self) -> str:
        return render_text(self.text)


@dataclass(frozen=True, slots=True)
class BoolValue:
    value: bool


QueryValue = TypeValue | TextValue | BoolValue | VectorValue


def _type_bits(base_tag: str) -> int:
    digits = "".join(c for c in base_tag if c.isdigit())
    return int(digits) if digits else 8


def _vector_value(base_tag: str, context: LoweringSession) -> VectorValue:
    """A :class:`VectorValue` for ``base_tag`` in the *current* extension.

    When the current sized vector is monomorphized at a concrete lane count (`unroll_variants`),
    its lane parameter is that concrete integer rather than the symbolic ``LANES`` — so a
    same-width re-base (`as_base`) under the current extension spells ``Generic<16>``."""

    value = _vector_value_from_extension(base_tag, context.env.extension)
    if value.uses_sized_vector:
        return replace(value, lane_parameter=context.env.lane_symbol())
    return value


def _vector_value_for_extension(
    base_tag: str, extension_name: str, context: LoweringSession
) -> VectorValue | None:
    """A source-level vector identity for ``base_tag`` under ``extension_name``.

    The name may be an internal extension block name (``avx2_vl``) or an emitted ISA tag
    (``avx2``). Lane count follows the same convention as :func:`_vector_value`: ``None`` for
    a sized generic vector, 1 for scalar, otherwise ``vector_bits / base-bit-width``.
    """

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


# --- parsed query terms ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QueryTerm:
    head: str  # e.g. "base::in", "base::signed_of", "type", "value", "intrin::suffix"
    mode: str | None  # the <...> scope, e.g. "generation" / "backend"; None if absent
    args: tuple["QueryTerm", ...]


class QueryParser:
    def parse(self, text: str) -> QueryTerm | None:
        text = text.strip()
        split = split_head_arg(text)
        if split is None:
            head, mode = _split_head_mode(text)
            return QueryTerm(head=head, mode=mode, args=())
        head_text, arg_text = split
        head, mode = _split_head_mode(head_text)
        args: list[QueryTerm] = []
        for piece in split_top_level(arg_text):
            parsed = self.parse(piece)
            if parsed is None:
                return None
            args.append(parsed)
        return QueryTerm(head=head, mode=mode, args=tuple(args))


def _split_head_mode(text: str) -> tuple[str, str | None]:
    text = text.strip()
    if text.endswith(">") and "<" in text:
        name, _, rest = text.partition("<")
        return name.strip(), rest[:-1].strip()
    return text, None


# --- query functions (one class per head) ------------------------------------


class QueryFunction(Protocol):
    head: str

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        """Resolve this query from already-evaluated arguments, or None if invalid."""


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
    """``base::unsigned_of(x)`` -> the same-width unsigned integer tag (``f32`` -> ``ui32``),
    for bit-level reinterpretation."""

    head = "base::unsigned_of"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TypeValue(unsigned_of(args[0].type_tag))


class TypeQuery:
    """``type<generation>(x)`` / ``type<backend>(x)`` — identity on the type for now."""

    head = "type"

    def apply(self, args, context):  # noqa: ANN001
        return args[0] if len(args) == 1 else None


class ValueQuery:
    """``value<backend>(x)`` / ``value<generation>(x)`` — passthrough wrapper."""

    head = "value"

    def apply(self, args, context):  # noqa: ANN001
        return args[0] if len(args) == 1 else None


class IntrinSuffixQuery:
    """``intrin::suffix(x)`` -> the composed intrinsic suffix fragment.

    Two forms: a *type* argument (``si32`` -> ``epi32``) via the extension's
    by-type compose map, or a *named policy* string literal (``"stream"`` ->
    ``si256``) resolved per-extension from the ``intrinsic_suffix_<name>_<ext>``
    translate template (e.g. whole-register integer ops: ``_mm256_xor_si256``).
    """

    head = "intrin::suffix"

    def apply(self, args, context):  # noqa: ANN001
        if not args:  # `intrin::suffix` (no arg) -> the CURRENT type's suffix fragment
            fragment = context.env.extension.compose_suffix_by_type.get(context.env.type_tag)
            return TextValue(fragment) if fragment is not None else None
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            fragment = context.env.extension.compose_suffix_by_type.get(arg.type_tag)
            return TextValue(fragment) if fragment is not None else None
        if isinstance(arg, TextValue):  # a named suffix policy, keyed by extension block name
            key = f"intrinsic_suffix_{arg.as_text()}_{context.env.extension.name}"
            fragment = context.env.backend.templates.template(key)
            return TextValue(fragment) if fragment is not None else None
        return None


class IsSameQuery:
    """``type::is_same(a, b)`` -> a generation-time boolean (the two type tags match)."""

    head = "type::is_same"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 2 or not all(isinstance(arg, TypeValue) for arg in args):
            return None
        return BoolValue(args[0].type_tag == args[1].type_tag)


class SizeBytesQuery:
    """``type::size_bytes(x)`` -> the byte width of a type as a generation-time integer
    (``si32`` -> ``4``), used for bit-width math in emulated bodies (``size_bytes(base::in)*8``).
    A type *tag* resolves by its trailing bit width / 8. NOTE: it does NOT yet resolve the
    integral-mask type, which arrives as a *spelling* (``vector::imask`` -> ``TextValue``) with
    no concrete width — those bodies need an imask-as-concrete-type query first."""

    head = "type::size_bytes"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return TextValue(str(_type_byte_width(args[0].type_tag)))


def _type_byte_width(type_tag: str) -> int:
    """Byte width of a scalar type tag (``si8`` -> 1, ``f64`` -> 8)."""

    digits = ""
    for char in reversed(type_tag):
        if not char.isdigit():
            break
        digits = char + digits
    return (int(digits) if digits else 8) // 8


class IsSignedQuery:
    """``type::is_signed(x)`` -> a generation-time boolean. A type *tag* (``base::in``,
    ``base::signed_of(...)``) resolves by prefix (``si*``/``f*`` signed, ``ui*`` not). The
    integral-mask type arrives as a *spelling* (``vector::imask`` -> ``TextValue``) and is
    unsigned by construction, so it folds to ``false`` — which short-circuits a
    ``is_signed(imask) && ...`` predicate to the logical-shift arm."""

    head = "type::is_signed"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            return BoolValue(is_signed(arg.type_tag))
        if isinstance(arg, TextValue):  # the imask spelling — unsigned by construction
            return BoolValue(False)
        return None


class AttributeQuery:
    """``primitive::attribute(name)`` -> the boolean value of the (concrete, after
    wildcard expansion) attribute on the primitive being lowered, e.g. ``aligned``."""

    head = "primitive::attribute"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        return BoolValue(context.env.attributes.get(args[0].as_text()) == "true")


class RegisterQuery:
    """``vector::register`` -> the backend spelling of the vector register type
    (C++ ``typename Vec::register_type`` / Rust ``Self::RegisterType``)."""

    head = "vector::register"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.env.backend.types.register_type_spelling())


class RegisterGenericQuery:
    """``register::generic(x)`` -> the concrete register-type spelling of the vector whose
    base is ``x`` in the current extension (C++ ``typename tsl::simd<uint32_t,
    tsl::avx2>::register_type`` / Rust ``core::arch::x86_64::__m256i``). Used by a
    representation-change body to name the target register it bit-casts to —
    ``cast<bitcast>(type<generation>(register::generic(ToType)), data)``."""

    head = "register::generic"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1:
            return None
        arg = args[0]
        # A bare base tag (`register::generic(ToType)`) -> that base's register in the current
        # extension. A `VectorValue` (`register::generic(vector::as_base(ToBase))`) carries its
        # own extension, so the target register is read from it (needed when it differs, e.g. a
        # widening load's input vector).
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
    """``vector::mask`` -> the backend spelling of the vector mask type
    (C++ ``typename Vec::mask_type`` / Rust ``Self::MaskType``)."""

    head = "vector::mask"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.env.backend.types.mask_type_spelling())


class ImaskQuery:
    """``vector::imask`` -> the integral-mask type (the integer ``to_integral`` packs a mask
    into: a ``movemask`` result / ``__mmaskN``).

    On scalar/generic (no SIMD register, ``vector_bits == 0``) the integral mask is concretely a
    ``u64`` bitset in the static substrate, so resolve to the concrete ``ui64`` *tag* — both its
    type-position uses (``let<type>(ImaskT, …)``) and ``type::size_bytes(vector::imask)`` then
    work. On SIMD it is a register-derived *spelling* (``Vec::imask_type`` / ``Self::ImaskType``)
    whose concrete width varies per lane count, so it stays a ``TextValue``."""

    head = "vector::imask"

    def apply(self, args, context):  # noqa: ANN001
        if context.env.extension.vector_bits == 0:
            return TypeValue("ui64")
        return TextValue(context.env.backend.types.imask_type_spelling())


class MaskLaneQuery:
    """``mask::lane::all_true`` / ``mask::lane::all_false`` -> the all-bits-set / all-bits-clear
    lane value of the current base type, as a substrate call (C++ ``::tsl::mask_lane_all_true<T>()``
    / Rust ``<T as TslMaskLaneValue>::all_true()``). Broadcast by ``set1`` to build an all-true /
    all-false lane-bitmask mask. The per-`head` template key is supplied at registration."""

    def __init__(self, head: str, template_key: str) -> None:
        self.head = head
        self._template_key = template_key

    def apply(self, args, context):  # noqa: ANN001
        if args:
            return None
        base = context.env.backend.types.scalar_spelling(context.env.type_tag)
        if base is None or context.env.backend.templates.template(self._template_key) is None:
            return None
        return TextValue(
            context.env.backend.templates.render_template(self._template_key, base=base)
        )


class VectorAlignmentQuery:
    """``vector::alignment`` -> the register's natural byte alignment (`vector_bits/8`)."""

    head = "vector::alignment"

    def apply(self, args, context):  # noqa: ANN001
        # The register's natural byte alignment — used by the *aligned* load/store variants
        # (e.g. avx2 -> 32). Sized vectors have no fixed hardware register, so they report their
        # element alignment instead.
        return TextValue(
            str(
                DEFAULT_SUPPORT_POLICY.vector_alignment_bytes(
                    context.env.extension, context.env.type_tag
                )
            )
        )


class VectorLengthQuery:
    """``vector::length`` -> the lane count (`vector_bits / type_bits`); scalar (a
    zero-width register) holds a single lane."""

    head = "vector::length"

    def apply(self, args, context):  # noqa: ANN001
        # A monomorphized sized slot has a concrete lane count; otherwise the symbolic `LANES`
        # for the sized vector or the fixed `vector_bits / type_bits` for a fixed extension.
        if context.env.concrete_lanes is not None:
            return TextValue(str(context.env.concrete_lanes))
        return TextValue(
            DEFAULT_SUPPORT_POLICY.lane_expression(
                context.env.extension, context.env.type_tag
            )
        )


class AsExtensionQuery:
    """``vector::as_extension(ext)`` -> the current base under a named extension.

    The named extension is resolved from the catalog, then rendered code turns the returned
    :class:`VectorValue` into backend spelling."""

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
    """``vector::as_base(base)`` -> the given base under the current extension.

    For a `si8`@avx2 source, ``as_base(si16)`` is ``simd<si16, avx2>`` (same
    256-bit register, 16 lanes). Conversion bodies bind it to a ``let<type>`` alias and then read
    ``generic::length(alias)`` / ``base::generic(alias)``."""

    head = "vector::as_base"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return _vector_value(args[0].type_tag, context)


class WindowBaseQuery:
    """``vector::window_base(base)`` -> the current vector re-based to ``base`` at constant total
    WIDTH — a *windowing* convert's output (``convert_up``/``convert_down``). For a fixed-width
    register this equals ``as_base`` (the lane count already follows the register width). For the
    SIZED generic vector the lane count scales by the byte ratio: i8->i16 turns ``generic<LANES>``
    into ``generic<(LANES * 8 / 16)>`` (half as many, twice as wide, same bits). This is the ONE
    place that scales a sized lane count; lane-PRESERVING base changes (``cast``/``reinterpret``,
    same element count) use ``vector::as_base`` instead. Backends that cannot spell a symbolic
    lane-count expression skip the width-changing window here (the ``unroll_variants``
    monomorphization over a finite size set can cover them later)."""

    head = "vector::window_base"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        to_base = args[0].type_tag
        extension = context.env.extension
        if not DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
            return _vector_value(to_base, context)  # fixed/scalar: lane count derived from bits
        # MONOMORPHIZED slot: the output count is a concrete integer (e.g. i8->i16 at 16 -> 8),
        # which stable Rust CAN spell — so no skip; emitted on every backend.
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
            return _vector_value(to_base, context)  # same width: lane count unchanged
        if not context.env.backend.supports_sized_vector_lane_expressions:
            context.effects.skip(
                "TSL-LOWER-SIZED-WIDTH-CHANGE",
                f"sized-vector windowing convert ({context.env.type_tag} -> {to_base}) needs a "
                "lane-count expression unsupported by this backend; skipped pending unroll",
            )
            return _vector_value(to_base, context)  # benign placeholder; the spec is dropped
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
    """``base::generic(V)`` -> the base type tag of a vector value (a `VectorValue`, typically a
    `let<type>` alias like `OutVec`)."""

    head = "base::generic"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], VectorValue):
            return None
        return TypeValue(args[0].base_tag)


class GenericLengthQuery:
    """``generic::length(V)`` -> the lane count of a vector value (`str(lanes)`, or the `LANES`
    symbol for the sized generic vector). Counterpart to `vector::length` (the current vector),
    but for a named vector alias."""

    head = "generic::length"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], VectorValue):
            return None
        value = args[0]
        return TextValue(
            str(value.lanes) if value.lanes is not None else value.lane_parameter
        )


DEFAULT_QUERY_FUNCTIONS: tuple[QueryFunction, ...] = (
    BaseInQuery(),
    SignedOfQuery(),
    UnsignedOfQuery(),
    TypeQuery(),
    ValueQuery(),
    IntrinSuffixQuery(),
    IsSameQuery(),
    SizeBytesQuery(),
    IsSignedQuery(),
    AttributeQuery(),
    RegisterQuery(),
    RegisterGenericQuery(),
    MaskQuery(),
    ImaskQuery(),
    MaskLaneQuery("mask::lane::all_true", "mask_lane_all_true"),
    MaskLaneQuery("mask::lane::all_false", "mask_lane_all_false"),
    VectorAlignmentQuery(),
    VectorLengthQuery(),
    AsExtensionQuery(),
    AsBaseQuery(),
    WindowBaseQuery(),
    VectorAsQuery(),
    BaseGenericQuery(),
    GenericLengthQuery(),
)


# --- evaluator ---------------------------------------------------------------


class QueryEvaluator:
    def __init__(
        self,
        functions: tuple[QueryFunction, ...] = DEFAULT_QUERY_FUNCTIONS,
        parser: QueryParser | None = None,
    ) -> None:
        self._functions = {function.head: function for function in functions}
        self._parser = parser or QueryParser()

    def evaluate(self, text: str, context: LoweringSession) -> QueryValue | None:
        term = self._parser.parse(text)
        if term is None:
            return None
        return self.evaluate_term(term, context)

    def evaluate_term(self, term: QueryTerm, context: LoweringSession) -> QueryValue | None:
        evaluated_args: list[QueryValue] = []
        for arg in term.args:
            value = self.evaluate_term(arg, context)
            if value is None:
                return None
            evaluated_args.append(value)

        function = self._functions.get(term.head)
        if function is not None:
            return function.apply(tuple(evaluated_args), context)
        # A representation-change target alias (the declaration's alias, plus the current
        # `ToType` synonym) -> the target base type tag, so `register::generic(ToType)` and
        # sibling queries resolve against the target.
        if not term.args:
            target_type_symbol = context.scope.resolve_target_type_symbol(term.head)
            if target_type_symbol is not None:
                return TypeValue(target_type_symbol)
        # A representation-change extension target alias (`ToExtension`) names another vector
        # extension/ISA. It stays textual until consumed by `vector::as_extension`.
        if not term.args:
            extension_symbol = context.scope.resolve_extension_symbol(term.head)
            if extension_symbol is not None:
                return TextValue(extension_symbol)
        # A `let<type>` alias whose value is a source type tag (`AliasBase`) -> that type.
        if not term.args:
            type_symbol = context.scope.resolve_type_symbol(term.head)
            if type_symbol is not None:
                return TypeValue(type_symbol)
        # A `let<type>` vector alias (`OutVec`) -> its structured VectorValue, so a query arg that
        # names it (`generic::length(OutVec)` / `base::generic(OutVec)`) resolves to the vector.
        if not term.args:
            vector_alias = context.scope.resolve_vector_alias(term.head)
            if vector_alias is not None:
                return vector_alias
        # A `let<type>` alias whose value is a backend type spelling (`CountT` ->
        # `std::size_t` / `usize`, `MaskT` -> current mask type) stays typed so casts and
        # templates can render it in the active backend context.
        if not term.args:
            type_alias = context.scope.resolve_type_alias(term.head)
            if type_alias is not None:
                return TextValue(type_alias)
        # A bare leaf that names a concrete type tag resolves to itself.
        if not term.args and is_type_tag(term.head):
            return TypeValue(term.head)
        # Named scalar width tags stay semantic (`scalar::ui64` -> `TypeValue("ui64")`) so type
        # queries compose uniformly. Non-width scalar names such as `scalar::size` resolve to the
        # backend spelling because they are target-language type aliases, not source type tags.
        if not term.args and term.head.startswith("scalar::"):
            scalar_tag = term.head[len("scalar::") :]
            if is_type_tag(scalar_tag):
                return TypeValue(scalar_tag)
            spelling = context.env.backend.types.scalar_spelling(scalar_tag)
            return TextValue(spelling) if spelling is not None else None
        # A bare quoted string literal (e.g. a named suffix policy) is text.
        if not term.args and len(term.head) >= 2 and term.head[0] == '"' == term.head[-1]:
            return TextValue(term.head[1:-1])
        # A bare identifier (e.g. an attribute name `aligned`) is text. `?`-bearing
        # tokens like `si?` don't match, so the avx512 set1 quirk is unaffected.
        if not term.args and _IDENTIFIER.match(term.head):
            return TextValue(term.head)
        return None
