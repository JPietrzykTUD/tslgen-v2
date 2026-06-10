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

from tslc.backend.translation import is_type_tag, signed_of
from tslc.lower._text import split_head_arg, split_top_level
from tslc.lower.context import LoweringContext


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


QueryValue = TypeValue | TextValue | BoolValue


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


class VectorAlignmentQuery:
    """``vector::alignment`` -> the register's natural byte alignment (`vector_bits/8`)."""

    head = "vector::alignment"

    def apply(self, args, context):  # noqa: ANN001
        return TextValue(str(context.extension.vector_bits // 8))


DEFAULT_QUERY_FUNCTIONS: tuple[QueryFunction, ...] = (
    BaseInQuery(),
    SignedOfQuery(),
    TypeQuery(),
    ValueQuery(),
    IntrinSuffixQuery(),
    IsSameQuery(),
    AttributeQuery(),
    RegisterQuery(),
    VectorAlignmentQuery(),
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
        # A bare leaf that names a concrete type tag resolves to itself.
        if not term.args and is_type_tag(term.head):
            return TypeValue(term.head)
        # A bare quoted string literal (e.g. a named suffix policy) is text.
        if not term.args and len(term.head) >= 2 and term.head[0] == '"' == term.head[-1]:
            return TextValue(term.head[1:-1])
        # A bare identifier (e.g. an attribute name `aligned`) is text. `?`-bearing
        # tokens like `si?` don't match, so the avx512 set1 quirk is unaffected.
        if not term.args and _IDENTIFIER.match(term.head):
            return TextValue(term.head)
        return None
