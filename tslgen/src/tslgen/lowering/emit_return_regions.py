"""Lower symbolic ``emit_return`` lexical regions into raw return directives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tslgen.core.diagnostics import Diagnostic
from tslgen.syntax.source_body_regions import (
    SourceBodyLexicalRegionCandidate,
    SourceBodyLexicalScanResult,
    SourceBodyRawSegment,
    SourceBodySpan,
    SourceBodyText,
    SourceBodyKeyword,
)


@dataclass(frozen=True, slots=True)
class LoweredEmitReturnDirective:
    source_order: int
    full_span: SourceBodySpan
    head_span: SourceBodySpan
    payload_span: SourceBodySpan
    source_region: SourceBodyLexicalRegionCandidate

    @property
    def payload_text(self) -> str:
        return self.payload_span.text


@dataclass(frozen=True, slots=True)
class EmitReturnOpaqueRawSegment:
    source_order: int
    segment: SourceBodyRawSegment


@dataclass(frozen=True, slots=True)
class EmitReturnOpaqueRegion:
    source_order: int
    region: SourceBodyLexicalRegionCandidate


EmitReturnLoweringItem: TypeAlias = (
    LoweredEmitReturnDirective | EmitReturnOpaqueRawSegment | EmitReturnOpaqueRegion
)


@dataclass(frozen=True, slots=True)
class EmitReturnLexicalRegionLoweringResult:
    source_text: SourceBodyText
    items: tuple[EmitReturnLoweringItem, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def emit_returns(self) -> tuple[LoweredEmitReturnDirective, ...]:
        return tuple(
            item for item in self.items if isinstance(item, LoweredEmitReturnDirective)
        )

    @property
    def opaque_raw_segments(self) -> tuple[EmitReturnOpaqueRawSegment, ...]:
        return tuple(
            item for item in self.items if isinstance(item, EmitReturnOpaqueRawSegment)
        )

    @property
    def opaque_regions(self) -> tuple[EmitReturnOpaqueRegion, ...]:
        return tuple(item for item in self.items if isinstance(item, EmitReturnOpaqueRegion))


def lower_emit_return_regions(
    scan_result: SourceBodyLexicalScanResult,
) -> EmitReturnLexicalRegionLoweringResult:
    if scan_result.diagnostics:
        return EmitReturnLexicalRegionLoweringResult(
            source_text=scan_result.source_text,
            items=(),
            diagnostics=scan_result.diagnostics,
        )

    items: list[EmitReturnLoweringItem] = []
    diagnostics: list[Diagnostic] = []
    for item in scan_result.items:
        if isinstance(item, SourceBodyRawSegment):
            items.append(
                EmitReturnOpaqueRawSegment(
                    source_order=item.source_order,
                    segment=item,
                )
            )
            continue

        if item.head.keyword is not SourceBodyKeyword.EMIT_RETURN:
            items.append(EmitReturnOpaqueRegion(source_order=item.source_order, region=item))
            continue

        directive, diagnostic = _lower_emit_return_region(item)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            items.append(EmitReturnOpaqueRegion(source_order=item.source_order, region=item))
            continue
        items.append(directive)

    return EmitReturnLexicalRegionLoweringResult(
        source_text=scan_result.source_text,
        items=tuple(items),
        diagnostics=tuple(diagnostics),
    )


def _lower_emit_return_region(
    region: SourceBodyLexicalRegionCandidate,
) -> tuple[LoweredEmitReturnDirective, None] | tuple[None, Diagnostic]:
    if region.selector is not None:
        return None, _unsupported_emit_return_region_diagnostic(
            region,
            "selectors are not part of the accepted return envelope",
        )
    if region.body is not None:
        return None, _unsupported_emit_return_region_diagnostic(
            region,
            "braced bodies are not part of the accepted return envelope",
        )
    if region.payload is None:
        return None, _unsupported_emit_return_region_diagnostic(
            region,
            "a balanced parenthesized payload is required",
        )

    return (
        LoweredEmitReturnDirective(
            source_order=region.source_order,
            full_span=region.full_span,
            head_span=region.head_span,
            payload_span=region.payload.payload_span,
            source_region=region,
        ),
        None,
    )


def _unsupported_emit_return_region_diagnostic(
    region: SourceBodyLexicalRegionCandidate,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-EMIT-RETURN-UNSUPPORTED-REGION",
        message=(
            f"TSIL source-body region {region.head.name!r} cannot be lowered as "
            f"a return directive: {reason}"
        ),
        location=region.head_span.start,
    )
