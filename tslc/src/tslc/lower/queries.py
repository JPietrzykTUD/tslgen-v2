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

from dataclasses import dataclass
from typing import Protocol

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


QueryValue = TypeValue | TextValue


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
    head = "intrin::suffix"

    def apply(self, args, context):  # noqa: ANN001
        if len(args) != 1 or not isinstance(args[0], TypeValue):
            return None
        fragment = context.extension.compose_suffix_by_type.get(args[0].type_tag)
        return TextValue(fragment) if fragment is not None else None


DEFAULT_QUERY_FUNCTIONS: tuple[QueryFunction, ...] = (
    BaseInQuery(),
    SignedOfQuery(),
    TypeQuery(),
    ValueQuery(),
    IntrinSuffixQuery(),
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
        return None
