"""Preserve raw target-language source text verbatim."""

from __future__ import annotations

from tslc.target_text import RenderText, literal_text


def render_raw_text(text: str) -> RenderText:
    """Return one terminal literal; only explicit TSIL regions may change source text."""

    return literal_text(text)


__all__ = ("render_raw_text",)
