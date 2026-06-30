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
    mode: str | None
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


class QueryFunction(Protocol):
    head: str

    def apply(
        self, args: tuple[QueryValue, ...], context: LoweringSession
    ) -> QueryValue | None:
        """Resolve this query from already-evaluated arguments, or None if invalid."""
