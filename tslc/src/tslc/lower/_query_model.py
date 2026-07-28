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
class ObjectSize:
    """Compiler-known size of a value-level object representation.

    Fixed-size objects carry ``fixed_bits``. Sized vectors carry an element
    width and lane-count symbol so equal symbolic layouts can be proven without
    inspecting a backend spelling.
    """

    fixed_bits: int | None = None
    element_bits: int | None = None
    lanes_symbol: str | None = None

    def __post_init__(self) -> None:
        has_fixed_size = self.fixed_bits is not None
        has_symbolic_size = (
            self.element_bits is not None or self.lanes_symbol is not None
        )
        if has_fixed_size == has_symbolic_size:
            raise ValueError("object size must be exactly one of fixed or symbolic")
        if has_fixed_size:
            if self.fixed_bits is None or self.fixed_bits <= 0:
                raise ValueError("fixed object size must be positive")
            return
        if (
            self.element_bits is None
            or self.element_bits <= 0
            or not self.lanes_symbol
        ):
            raise ValueError(
                "symbolic object size requires a positive element width and lane symbol"
            )

    @classmethod
    def fixed(cls, bits: int) -> "ObjectSize":
        return cls(fixed_bits=bits)

    @classmethod
    def sized(cls, element_bits: int, lanes_symbol: str) -> "ObjectSize":
        return cls(element_bits=element_bits, lanes_symbol=lanes_symbol)

    def same_size_as(self, other: "ObjectSize") -> bool:
        if self.fixed_bits is not None:
            return self.fixed_bits == other.fixed_bits
        if other.fixed_bits is not None:
            return False
        return (
            self.element_bits == other.element_bits
            and self.lanes_symbol == other.lanes_symbol
        )


@dataclass(frozen=True, slots=True)
class TextValue:
    text: RenderField
    object_size: ObjectSize | None = None
    all_bit_patterns_valid: bool = False

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
