"""Typed values and parser for the TSIL query language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.lower._text import split_head_arg, split_top_level
from tslc.lower.context import LoweringSession, VectorValue
from tslc.render.model import RenderField, render_text


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


@dataclass(frozen=True, slots=True)
class QueryTerm:
    head: str
    args: tuple["QueryTerm", ...]


class QueryParser:
    def parse(self, text: str) -> QueryTerm | None:
        text = text.strip()
        split = split_head_arg(text)
        if split is None:
            return QueryTerm(head=text, args=())
        head_text, arg_text = split
        args: list[QueryTerm] = []
        for piece in split_top_level(arg_text):
            parsed = self.parse(piece)
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
