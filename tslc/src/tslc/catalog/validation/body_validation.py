"""Validate syntax-only TSIL body region shapes before lowering."""

from __future__ import annotations

import re

from collections.abc import Callable

from tslc.catalog.validation.source_spans import source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.ir.region_registry import region_shell_validator
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower._text import split_top_level
from tslc.lower.calls import parse_call_selector
from tslc.lower.region_handlers.intrinsics import IntrinsicSelector
from tslc.syntax.ast import OuterTslParseResult, ParsedImplementationBodyEnvelope

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_body_regions(
    parsed: OuterTslParseResult,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate source-owned TSIL region shells without backend semantics."""

    for document in parsed.documents:
        for primitive in document.primitives:
            for envelope in primitive.body_envelopes:
                _validate_envelope(primitive.name, envelope, diagnostics)


def _validate_envelope(
    primitive_name: str,
    envelope: ParsedImplementationBodyEnvelope,
    diagnostics: list[Diagnostic],
) -> None:
    segments = scan(envelope.payload_text, source=source_span(envelope.payload_source))
    _validate_segments(primitive_name, segments, diagnostics)


def _validate_segments(
    primitive_name: str,
    segments: tuple[Segment, ...] | None,
    diagnostics: list[Diagnostic],
) -> None:
    if segments is None:
        return
    for segment in segments:
        if isinstance(segment, RawText):
            continue
        _validate_region(primitive_name, segment, diagnostics)
        _validate_segments(primitive_name, segment.body, diagnostics)
        _validate_segments(primitive_name, segment.block, diagnostics)
        _validate_segments(primitive_name, segment.else_block, diagnostics)
        if segment.arms is not None:
            for _label, body in segment.arms:
                _validate_segments(primitive_name, body, diagnostics)


def _validate_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    validator_id = region_shell_validator(region.keyword)
    if validator_id is None:
        return
    validator = _SHELL_VALIDATORS.get(validator_id)
    if validator is not None:
        validator(primitive_name, region, diagnostics)


def _validate_call_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    if parse_call_selector(region.selector_text) is not None:
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-CALL-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed call selector "
                f"{region.selector_text!r}"
            ),
            source=region.source,
        )
    )


def _validate_let_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    groups = split_top_level(_segments_text(region.body))
    if (
        region.selector_text.strip() == "type"
        and len(groups) == 2
        and _IDENTIFIER.fullmatch(groups[0].strip()) is not None
    ):
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-LET",
            message=(
                f"primitive {primitive_name!r}: let<type> must be "
                "`let<type>(Name, type-expression)`"
            ),
            source=region.source,
        )
    )


def _validate_intrin_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    selector = IntrinsicSelector.parse(region.selector_text)
    if selector.name is not None and not selector.unsupported_terms:
        return
    detail = (
        "missing intrinsic name"
        if selector.name is None
        else "selector modifiers must be inside build[...]"
    )
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-INTRIN-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed intrin selector "
                f"{region.selector_text!r}: {detail}"
            ),
            source=region.source,
        )
    )


def _segments_text(segments: tuple[Segment, ...]) -> str:
    return "".join(
        segment.text if isinstance(segment, RawText) else segment.full_text
        for segment in segments
    )


ShellValidator = Callable[[str, Region, list[Diagnostic]], None]

_SHELL_VALIDATORS: dict[str, ShellValidator] = {
    "call_selector": _validate_call_region,
    "let_type": _validate_let_region,
    "intrin_selector": _validate_intrin_region,
}


__all__ = ("validate_body_regions",)
