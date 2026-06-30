"""Render raw TSIL source text into typed render fragments."""

from __future__ import annotations

from tslc.lower.context import LoweringSession
from tslc.render.model import RenderText, literal_text, render_sequence


def render_raw_text(text: str, context: LoweringSession) -> RenderText:
    """Turn raw source text into terminal literal chunks plus typed alias references.

    This is a source-boundary operation: aliases introduced by earlier ``let<type>`` regions are
    tokenized as explicit render values before the body becomes backend render text. Quoted string
    contents remain literal.
    """

    parts: list[RenderText] = []
    literal: list[str] = []
    index = 0

    def flush_literal() -> None:
        if literal:
            parts.append(literal_text("".join(literal)))
            literal.clear()

    while index < len(text):
        char = text[index]
        if char == '"':
            literal.append(char)
            index += 1
            escaped = False
            while index < len(text):
                inner = text[index]
                literal.append(inner)
                index += 1
                if escaped:
                    escaped = False
                elif inner == "\\":
                    escaped = True
                elif inner == '"':
                    break
            continue
        if _is_identifier_start(char):
            start = index
            index += 1
            while index < len(text) and _is_identifier_part(text[index]):
                index += 1
            name = text[start:index]
            alias = context.scope.type_aliases.get(name)
            if alias is None:
                literal.append(name)
            else:
                flush_literal()
                parts.append(alias)
            continue
        literal.append(char)
        index += 1
    flush_literal()
    return render_sequence(tuple(parts))


def _is_identifier_start(char: str) -> bool:
    return char == "_" or char.isalpha()


def _is_identifier_part(char: str) -> bool:
    return char == "_" or char.isalnum()


__all__ = ("render_raw_text",)
