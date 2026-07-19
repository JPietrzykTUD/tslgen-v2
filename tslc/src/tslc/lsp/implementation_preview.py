"""Authored implementation sites that can launch an explicit preview."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslc.catalog.model import Catalog
from tslc.diagnostics import SourceSpan
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedImplementationSelectorEntry,
    ParsedTslSourceSpan,
)


@dataclass(frozen=True, slots=True)
class ImplementationPreviewSite:
    """One physical implementation field and its selector-owned identity."""

    anchor: SourceSpan
    selector: SourceSpan


def implementation_preview_sites(
    catalog: Catalog,
    parsed: OuterTslParseResult | None,
    path: Path,
) -> tuple[ImplementationPreviewSite, ...]:
    """Project one stable preview site per promoted, source-authored body."""

    if parsed is None:
        return ()
    selected_path = path.resolve()
    promoted = {
        _span_key(implementation.selector_source)
        for primitive in catalog.primitives
        for implementation in primitive.implementations
        if implementation.selector_source is not None
        and implementation.selector_source.path.resolve() == selected_path
    }
    sites: dict[tuple[str, int, int, int, int], ImplementationPreviewSite] = {}
    for document in parsed.documents:
        if document.path.resolve() != selected_path:
            continue
        for primitive in document.primitives:
            for site in _entry_sites(primitive.impl_entries, promoted):
                sites.setdefault(_span_key(site.selector), site)
    return tuple(
        sorted(
            sites.values(),
            key=lambda site: (*_span_key(site.anchor), *_span_key(site.selector)),
        )
    )


def _entry_sites(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    promoted: set[tuple[str, int, int, int, int]],
) -> tuple[ImplementationPreviewSite, ...]:
    sites: list[ImplementationPreviewSite] = []
    for entry in entries:
        selector = _source_span(entry.source)
        if entry.body_envelopes and _span_key(selector) in promoted:
            implementation_field = next(
                (field for field in entry.fields if field.key.text == "implementation"),
                None,
            )
            if implementation_field is not None:
                sites.append(
                    ImplementationPreviewSite(
                        anchor=_source_span(implementation_field.key.source),
                        selector=selector,
                    )
                )
        sites.extend(_entry_sites(entry.children, promoted))
    return tuple(sites)


def _source_span(span: ParsedTslSourceSpan) -> SourceSpan:
    return SourceSpan(
        path=span.path,
        line=span.line,
        column=span.column,
        end_line=span.end_line,
        end_column=span.end_column,
    )


def _span_key(span: SourceSpan) -> tuple[str, int, int, int, int]:
    return (
        span.path.resolve().as_posix(),
        span.line,
        span.column,
        span.end_line,
        span.end_column,
    )


__all__ = ("ImplementationPreviewSite", "implementation_preview_sites")
