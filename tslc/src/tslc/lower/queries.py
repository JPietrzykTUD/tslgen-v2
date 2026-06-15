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
from dataclasses import dataclass
from typing import Protocol

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from tslc.backend.translation import is_signed, is_type_tag, signed_of, unsigned_of
from tslc.lower._text import split_head_arg, split_top_level
from tslc.lower.context import LoweringContext, VectorValue


# --- query value types (extend as new queries need new result kinds) ---------


@dataclass(frozen=True, slots=True)
class TypeValue:
    type_tag: str


@dataclass(frozen=True, slots=True)
class TextValue:
    text: str


@dataclass(frozen=True, slots=True)
class BoolValue:
    value: bool


QueryValue = TypeValue | TextValue | BoolValue | VectorValue


def _vector_value(base_tag: str, context: LoweringContext) -> VectorValue:
    """A :class:`VectorValue` for ``base_tag`` in the *current* extension. Lane count: the
    LANES-symbol (None) for the generic vector, 1 for scalar (zero-width register), else
    ``vector_bits / base-bit-width``."""

    isa = context.extension.isa_name
    if isa == "generic":
        lanes: int | None = None
    elif context.extension.vector_bits == 0:
        lanes = 1
    else:
        digits = "".join(c for c in base_tag if c.isdigit())
        lanes = context.extension.vector_bits // (int(digits) if digits else 8)
    return VectorValue(base_tag=base_tag, extension_isa=isa, lanes=lanes)


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
        self, args: tuple[QueryValue, ...], context: LoweringContext
    ) -> QueryValue | None:
        """Resolve this query from already-evaluated arguments, or None if invalid."""


class BaseInQuery:
    head = "base::in"

    def apply(self, args, context):  # noqa: ANN001 - protocol-typed
        return TypeValue(context.type_tag)


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
        if len(args) != 1:
            return None
        arg = args[0]
        if isinstance(arg, TypeValue):
            fragment = context.extension.compose_suffix_by_type.get(arg.type_tag)
            return TextValue(fragment) if fragment is not None else None
        if isinstance(arg, TextValue):  # a named suffix policy, keyed by extension block name
            key = f"intrinsic_suffix_{arg.text}_{context.extension.name}"
            fragment = context.translation.template(key)
            return TextValue(fragment) if fragment is not None else None
        return None


class IsSameQuery:
    """``type::is_same(a, b)`` -> a generation-time boolean (the two type tags match)."""

    head = "type::is_same"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 2 or not all(isinstance(arg, TypeValue) for arg in args):
            return None
        return BoolValue(args[0].type_tag == args[1].type_tag)


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
        return BoolValue(context.attributes.get(args[0].text) == "true")


class RegisterQuery:
    """``vector::register`` -> the backend spelling of the vector register type
    (C++ ``typename Vec::register_type`` / Rust ``Self::RegisterType``)."""

    head = "vector::register"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.translation.register_type_spelling())


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
        # extension. A `VectorValue` (`register::generic(transform_extension(ToBase))`) carries its
        # own extension, so the target register is read from it (needed when it differs, e.g. a
        # widening load's input vector).
        if isinstance(arg, TypeValue):
            base_tag, isa = arg.type_tag, context.extension.isa_name
        elif isinstance(arg, VectorValue):
            base_tag, isa = arg.base_tag, arg.extension_isa
        else:
            return None
        spelling = context.translation.target_register_spelling(base_tag, isa)
        return TextValue(spelling) if spelling is not None else None


class MaskQuery:
    """``vector::mask`` -> the backend spelling of the vector mask type
    (C++ ``typename Vec::mask_type`` / Rust ``Self::MaskType``)."""

    head = "vector::mask"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.translation.mask_type_spelling())


class ImaskQuery:
    """``vector::imask`` -> the backend spelling of the integral-mask type
    (C++ ``typename Vec::imask_type`` / Rust ``Self::ImaskType``). This is the
    integer ``to_integral`` packs a mask into (``movemask`` result / ``__mmaskN``)."""

    head = "vector::imask"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(context.translation.imask_type_spelling())


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
        base = context.translation.scalar_spelling(context.type_tag)
        if base is None or context.translation.template(self._template_key) is None:
            return None
        return TextValue(context.translation.render_template(self._template_key, base=base))


class VectorAlignmentQuery:
    """``vector::alignment`` -> the register's natural byte alignment (`vector_bits/8`)."""

    head = "vector::alignment"

    def apply(self, args, context):  # noqa: ANN001
        # The register's natural byte alignment — used by the *aligned* load/store variants
        # (e.g. avx2 -> 32). The generic vector has no hardware register, so it reports its
        # element alignment instead.
        if context.extension.isa_name == "generic":
            digits = "".join(c for c in context.type_tag if c.isdigit())
            return TextValue(str((int(digits) if digits else 8) // 8))
        return TextValue(str(context.extension.vector_bits // 8))


class VectorLengthQuery:
    """``vector::length`` -> the lane count (`vector_bits / type_bits`); scalar (a
    zero-width register) holds a single lane."""

    head = "vector::length"

    def apply(self, args, context):  # noqa: ANN001
        # The `generic` vector is sized: its lane count is the `LANES` template parameter,
        # not a concrete integer — emit the symbol so the body keys off the template param.
        if context.extension.isa_name == "generic":
            return TextValue("LANES")
        bits = context.extension.vector_bits
        if bits == 0:
            return TextValue("1")
        digits = "".join(c for c in context.type_tag if c.isdigit())
        type_bits = int(digits) if digits else 8
        return TextValue(str(bits // type_bits))


class AsExtensionQuery:
    """``vector::as_extension(ext)`` -> the current base type re-expressed as a vector under
    a different extension, e.g. ``as_extension(scalar)`` -> ``tsl::simd<int32_t, tsl::scalar>``
    / ``Simd<i32, Scalar>``. Used by the generic vector's per-lane delegation to scalar. (The
    lanes-matching ``as_extension(generic)`` and multi-arg forms are a later slice.)"""

    head = "vector::as_extension"

    def apply(self, args, context):  # noqa: ANN001
        # Single-extension forms only (the multi-arg `as_extension(sse, ToBase)` forms are a
        # later slice). `scalar` → the scalar vector; `generic` → the sized generic vector at
        # the caller's (generation-time) lane count, for cross-extension delegation.
        if len(args) != 1 or not isinstance(args[0], TextValue):
            return None
        base = context.translation.scalar_spelling(context.type_tag)
        if base is None:
            return None
        if args[0].text == "scalar":
            return TextValue(context.translation.vector_type_spelling(base, "scalar"))
        if args[0].text == "generic":
            bits = context.extension.vector_bits
            digits = "".join(c for c in context.type_tag if c.isdigit())
            type_bits = int(digits) if digits else 8
            if bits == 0:  # scalar/generic callers have no fixed lane count to delegate at
                return None
            return TextValue(context.translation.generic_vector_spelling(base, bits // type_bits))
        return None


class TransformExtensionQuery:
    """``vector::transform_extension(ToBase)`` -> the vector with the given base in the *current*
    extension (a :class:`VectorValue`), e.g. for a `si8`@avx2 source, `transform_extension(si16)`
    is `simd<si16, avx2>` (same 256-bit register, 16 lanes). The conversion bodies bind it to a
    `let<type>(OutVec, …)` and then read `generic::length(OutVec)` / `base::generic(OutVec)`."""

    head = "vector::transform_extension"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        return _vector_value(args[0].type_tag, context)


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
        return TextValue("LANES" if args[0].lanes is None else str(args[0].lanes))


DEFAULT_QUERY_FUNCTIONS: tuple[QueryFunction, ...] = (
    BaseInQuery(),
    SignedOfQuery(),
    UnsignedOfQuery(),
    TypeQuery(),
    ValueQuery(),
    IntrinSuffixQuery(),
    IsSameQuery(),
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
    TransformExtensionQuery(),
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

    def evaluate(self, text: str, context: LoweringContext) -> QueryValue | None:
        term = self._parser.parse(text)
        if term is None:
            return None
        return self.evaluate_term(term, context)

    def evaluate_term(self, term: QueryTerm, context: LoweringContext) -> QueryValue | None:
        evaluated_args: list[QueryValue] = []
        for arg in term.args:
            value = self.evaluate_term(arg, context)
            if value is None:
                return None
            evaluated_args.append(value)

        function = self._functions.get(term.head)
        if function is not None:
            return function.apply(tuple(evaluated_args), context)
        # A representation-change target alias (`ToBase`/`ToType`) -> the target base type tag,
        # so `register::generic(ToType)` / `base::unsigned_of(ToBase)` resolve against the target.
        if not term.args and term.head in context.target_type_aliases:
            return TypeValue(context.target_type_aliases[term.head])
        # A `let<type>` vector alias (`OutVec`) -> its structured VectorValue, so a query arg that
        # names it (`generic::length(OutVec)` / `base::generic(OutVec)`) resolves to the vector.
        if not term.args and term.head in context.vector_aliases:
            return context.vector_aliases[term.head]
        # A bare leaf that names a concrete type tag resolves to itself.
        if not term.args and is_type_tag(term.head):
            return TypeValue(term.head)
        # Named backend scalar types (`type<backend>(scalar::ui64)` / `scalar::size`): resolve
        # to the language type-map spelling (`ui64` -> `uint64_t`/`u64`; `size` ->
        # `std::size_t`/`usize`).
        if not term.args and term.head.startswith("scalar::"):
            spelling = context.translation.scalar_spelling(term.head[len("scalar::") :])
            return TextValue(spelling) if spelling is not None else None
        # A bare quoted string literal (e.g. a named suffix policy) is text.
        if not term.args and len(term.head) >= 2 and term.head[0] == '"' == term.head[-1]:
            return TextValue(term.head[1:-1])
        # A bare identifier (e.g. an attribute name `aligned`) is text. `?`-bearing
        # tokens like `si?` don't match, so the avx512 set1 quirk is unaffected.
        if not term.args and _IDENTIFIER.match(term.head):
            return TextValue(term.head)
        return None
