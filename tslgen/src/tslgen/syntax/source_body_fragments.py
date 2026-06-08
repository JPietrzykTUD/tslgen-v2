"""Pure recursive source-body fragments over lexical TSIL regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tslgen.core.diagnostics import Diagnostic
from tslgen.syntax.source_body_regions import (
    SourceBodyDelimitedSpan,
    SourceBodyKeyword,
    SourceBodyLexicalRegionCandidate,
    SourceBodyLexicalScanResult,
    SourceBodyRawSegment,
    SourceBodySpan,
    SourceBodyText,
    scan_source_body_text,
)


@dataclass(frozen=True, slots=True)
class RawSourceFragment:
    source_order: int
    span: SourceBodySpan


@dataclass(frozen=True, slots=True)
class KeywordRegionFragment:
    source_order: int
    source_region: SourceBodyLexicalRegionCandidate
    selector_fragments: SourceBodyFragmentSequence | None = None
    payload_fragments: SourceBodyFragmentSequence | None = None
    body_fragments: SourceBodyFragmentSequence | None = None

    @property
    def keyword(self) -> SourceBodyKeyword:
        return self.source_region.head.keyword


SourceBodyFragment: TypeAlias = RawSourceFragment | KeywordRegionFragment


@dataclass(frozen=True, slots=True)
class SourceBodyFragmentSequence:
    source_text: SourceBodyText
    fragments: tuple[SourceBodyFragment, ...]

    @property
    def raw_fragments(self) -> tuple[RawSourceFragment, ...]:
        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, RawSourceFragment)
        )

    @property
    def keyword_fragments(self) -> tuple[KeywordRegionFragment, ...]:
        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, KeywordRegionFragment)
        )


@dataclass(frozen=True, slots=True)
class SourceBodyFragmentScanResult:
    sequence: SourceBodyFragmentSequence
    diagnostics: tuple[Diagnostic, ...]


def fragment_source_body_text(
    source: SourceBodyText | SourceBodyLexicalScanResult,
) -> SourceBodyFragmentScanResult:
    scan_result = (
        source if isinstance(source, SourceBodyLexicalScanResult) else scan_source_body_text(source)
    )
    sequence, diagnostics = _fragment_sequence_from_scan(scan_result)
    return SourceBodyFragmentScanResult(
        sequence=sequence,
        diagnostics=diagnostics,
    )


def _fragment_sequence_from_scan(
    scan_result: SourceBodyLexicalScanResult,
) -> tuple[SourceBodyFragmentSequence, tuple[Diagnostic, ...]]:
    fragments: list[SourceBodyFragment] = []
    diagnostics: list[Diagnostic] = list(scan_result.diagnostics)

    for item in scan_result.items:
        if isinstance(item, SourceBodyRawSegment):
            fragments.append(
                RawSourceFragment(
                    source_order=item.source_order,
                    span=item.span,
                )
            )
            continue

        selector_fragments, selector_diagnostics = _child_fragments(item.selector)
        diagnostics.extend(selector_diagnostics)
        payload_fragments, payload_diagnostics = _child_fragments(item.payload)
        diagnostics.extend(payload_diagnostics)
        body_fragments, body_diagnostics = _child_fragments(item.body)
        diagnostics.extend(body_diagnostics)

        fragments.append(
            KeywordRegionFragment(
                source_order=item.source_order,
                source_region=item,
                selector_fragments=selector_fragments,
                payload_fragments=payload_fragments,
                body_fragments=body_fragments,
            )
        )

    return (
        SourceBodyFragmentSequence(
            source_text=scan_result.source_text,
            fragments=tuple(fragments),
        ),
        tuple(diagnostics),
    )


def _child_fragments(
    span: SourceBodyDelimitedSpan | None,
) -> tuple[SourceBodyFragmentSequence | None, tuple[Diagnostic, ...]]:
    if span is None:
        return None, ()
    child_scan = scan_source_body_text(SourceBodyText.from_span(span.payload_span))
    return _fragment_sequence_from_scan(child_scan)
