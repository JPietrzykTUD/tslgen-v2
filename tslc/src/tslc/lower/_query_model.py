"""Typed values and parser for the TSIL query language."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol

from tslc.ir.text import split_head_arg, split_top_level
from tslc.lower.context import LoweringSession, SimdTypeParameterValue, VectorValue
from tslc.target_text import RenderField, render_text


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


QueryValue = TypeValue | TextValue | BoolValue | VectorValue | SimdTypeParameterValue

QueryValueKind = Literal["type", "text", "bool", "vector", "simd_type"]
QueryArgumentRole = Literal["query", "extension", "attribute"]

ALL_QUERY_KINDS: frozenset[QueryValueKind] = frozenset(
    {"type", "text", "bool", "vector", "simd_type"}
)


@dataclass(frozen=True, slots=True)
class QueryArgumentDescriptor:
    """Accepted typed values and authoring role for one query argument."""

    kinds: frozenset[QueryValueKind] = ALL_QUERY_KINDS
    role: QueryArgumentRole = "query"


@dataclass(frozen=True, slots=True)
class QueryFunctionDescriptor:
    """Typed call contract shared by query evaluation and authoring tools."""

    result_kinds: frozenset[QueryValueKind]
    arguments: tuple[QueryArgumentDescriptor, ...] = ()
    min_arguments: int | None = None

    @property
    def minimum_arguments(self) -> int:
        return len(self.arguments) if self.min_arguments is None else self.min_arguments

    def argument(self, index: int) -> QueryArgumentDescriptor | None:
        return self.arguments[index] if index < len(self.arguments) else None

    def accepts(self, args: tuple[QueryValue, ...]) -> bool:
        if not self.minimum_arguments <= len(args) <= len(self.arguments):
            return False
        return all(
            _query_value_kind(value) in descriptor.kinds
            for value, descriptor in zip(args, self.arguments, strict=False)
        )


@dataclass(frozen=True, slots=True)
class QueryLeafNamespaceDescriptor:
    """Closed source spelling namespace for typed query leaves."""

    name: str
    values: tuple[str, ...]
    result_kinds: frozenset[QueryValueKind]


def query_argument(
    *kinds: QueryValueKind,
    role: QueryArgumentRole = "query",
) -> QueryArgumentDescriptor:
    return QueryArgumentDescriptor(frozenset(kinds) or ALL_QUERY_KINDS, role)


def query_function(
    *result_kinds: QueryValueKind,
    arguments: tuple[QueryArgumentDescriptor, ...] = (),
    min_arguments: int | None = None,
) -> QueryFunctionDescriptor:
    return QueryFunctionDescriptor(
        frozenset(result_kinds),
        arguments,
        min_arguments,
    )


def _query_value_kind(value: QueryValue) -> QueryValueKind:
    if isinstance(value, TypeValue):
        return "type"
    if isinstance(value, TextValue):
        return "text"
    if isinstance(value, BoolValue):
        return "bool"
    if isinstance(value, VectorValue):
        return "vector"
    return "simd_type"


@dataclass(frozen=True, slots=True)
class QueryTerm:
    head: str
    args: tuple["QueryTerm", ...]


class QueryParser:
    def parse(self, text: str) -> QueryTerm | None:
        return _cached_parse_query(text.strip())


_QUERY_PARSE_CACHE_SIZE = 512


@lru_cache(maxsize=_QUERY_PARSE_CACHE_SIZE)
def _cached_parse_query(text: str) -> QueryTerm | None:
    split = split_head_arg(text)
    if split is None:
        return QueryTerm(head=text, args=())
    head_text, arg_text = split
    args: list[QueryTerm] = []
    for piece in split_top_level(arg_text):
        parsed = _cached_parse_query(piece.strip())
        if parsed is None:
            return None
        args.append(parsed)
    return QueryTerm(head=head_text.strip(), args=tuple(args))


class QueryFunction(Protocol):
    head: str
    descriptor: QueryFunctionDescriptor

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        """Resolve this query from already-evaluated arguments, or None if invalid."""
