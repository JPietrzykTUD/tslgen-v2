"""The TSIL body model: a recursive sequence of raw text and keyword regions.

A body is *not* an abstract syntax tree. The input is semi-valid target-language
code enriched with TSIL keywords. A body is an ordered ``tuple[Segment, ...]``
where each segment is either:

- :class:`RawText` — target-language source, passed through verbatim; or
- :class:`Region` — a recognized TSIL keyword island whose selector (``<...>``)
  is kept as raw text and whose argument payload (``(...)``) is itself a
  recursively-scanned ``tuple[Segment, ...]``. When a region appears in a
  statement stream and is followed by a source ``;``, the scanner consumes that
  terminator and records it on the region instead of leaking it as raw text.

The lowerer translates regions and passes raw text through.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class RawText:
    text: str
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class Region:
    keyword: str  # e.g. "complete", "intrin", "value", "type", "call"
    selector_text: str  # raw text inside <...>, "" when the keyword has no selector
    body: tuple["Segment", ...]  # recursively scanned (...) payload
    full_text: str  # original source text of the whole region (provenance)
    source: SourceSpan | None = None
    has_statement_terminator: bool = False
    # Brace-delimited trailing block(s), for block-bearing keywords like
    # ``if<generation>(cond) { ... } else<generation> { ... }``. Empty/None for
    # ordinary ``keyword<sel>(args)`` regions. ``else_block`` holds either the
    # plain ``else`` statements or, for an ``else if`` chain, a single nested
    # ``if`` region.
    block: tuple["Segment", ...] = ()
    else_block: tuple["Segment", ...] | None = None
    # Arms of a ``switch<compile>(sel) { label => { body } … _ => { body } }`` region: each is
    # (label, body-segments); ``_`` is the default. The lowerer emits a compile-time multi-way
    # selection over the const selector (``body`` holds the selector). None for other regions.
    arms: tuple[tuple[str, tuple["Segment", ...]], ...] | None = None


Segment = RawText | Region


def raw_concat(segments: tuple[Segment, ...]) -> str:
    """Join a segment sequence of pure raw text. Raises if a region is present."""

    parts: list[str] = []
    for segment in segments:
        if isinstance(segment, RawText):
            parts.append(segment.text)
        else:  # pragma: no cover - guarded by callers
            raise ValueError(f"expected only raw text, found region {segment.keyword!r}")
    return "".join(parts)
