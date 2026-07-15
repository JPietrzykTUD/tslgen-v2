"""Typed values and parser for the TSIL query language."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

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

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        """Resolve this query from already-evaluated arguments, or None if invalid."""
