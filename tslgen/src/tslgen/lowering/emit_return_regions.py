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
    scan_source_body_text,
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


@dataclass(frozen=True, slots=True)
class EmitReturnPayloadRawSegmentAdapter:
    source_order: int
    return_directive: LoweredEmitReturnDirective
    segment: SourceBodyRawSegment


@dataclass(frozen=True, slots=True)
class EmitReturnPayloadRegionAdapter:
    source_order: int
    return_directive: LoweredEmitReturnDirective
    region: SourceBodyLexicalRegionCandidate


EmitReturnPayloadRescanItem: TypeAlias = (
    EmitReturnPayloadRawSegmentAdapter | EmitReturnPayloadRegionAdapter
)


@dataclass(frozen=True, slots=True)
class EmitReturnPayloadRescanResult:
    return_directive: LoweredEmitReturnDirective
    source_text: SourceBodyText
    items: tuple[EmitReturnPayloadRescanItem, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def raw_segments(self) -> tuple[EmitReturnPayloadRawSegmentAdapter, ...]:
        return tuple(
            item
            for item in self.items
            if isinstance(item, EmitReturnPayloadRawSegmentAdapter)
        )

    @property
    def regions(self) -> tuple[EmitReturnPayloadRegionAdapter, ...]:
        return tuple(
            item for item in self.items if isinstance(item, EmitReturnPayloadRegionAdapter)
        )


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


def rescan_emit_return_payload(
    return_directive: LoweredEmitReturnDirective,
) -> EmitReturnPayloadRescanResult:
    source_text = SourceBodyText.from_span(return_directive.payload_span)
    scan_result = scan_source_body_text(source_text)
    if scan_result.diagnostics:
        return EmitReturnPayloadRescanResult(
            return_directive=return_directive,
            source_text=source_text,
            items=(),
            diagnostics=scan_result.diagnostics,
        )

    items: list[EmitReturnPayloadRescanItem] = []
    for item in scan_result.items:
        if isinstance(item, SourceBodyRawSegment):
            items.append(
                EmitReturnPayloadRawSegmentAdapter(
                    source_order=item.source_order,
                    return_directive=return_directive,
                    segment=item,
                )
            )
            continue
        items.append(
            EmitReturnPayloadRegionAdapter(
                source_order=item.source_order,
                return_directive=return_directive,
                region=item,
            )
        )

    return EmitReturnPayloadRescanResult(
        return_directive=return_directive,
        source_text=source_text,
        items=tuple(items),
        diagnostics=(),
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
