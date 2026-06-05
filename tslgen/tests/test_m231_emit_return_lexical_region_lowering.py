from __future__ import annotations

from dataclasses import is_dataclass, replace
from hashlib import sha256
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.lowering.emit_return_regions import (
    EmitReturnLexicalRegionLoweringResult,
    EmitReturnOpaqueRawSegment,
    EmitReturnOpaqueRegion,
    LoweredEmitReturnDirective,
    lower_emit_return_regions,
)
from tslgen.syntax.outer_ast import ParsedImplementationBodyEnvelope
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import (
    SourceBodyKeyword,
    SourceBodyLexicalScanResult,
    SourceBodyText,
    scan_source_body_envelope,
    scan_source_body_text,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TSLDATA_ROOT = _REPO_ROOT / "tsldata"


def test_m231_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        EmitReturnLexicalRegionLoweringResult,
        EmitReturnOpaqueRawSegment,
        EmitReturnOpaqueRegion,
        LoweredEmitReturnDirective,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m231_inline_scalar_emit_return_lowers_symbolic_keyword_only() -> None:
    envelope = _envelope_containing(
        _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl",
        "emit_return(left + right);",
    )
    scan_result = scan_source_body_envelope(envelope)

    assert scan_result.diagnostics == ()
    assert scan_result.regions[0].head.keyword is SourceBodyKeyword.EMIT_RETURN

    result = lower_emit_return_regions(scan_result)

    assert result.diagnostics == ()
    assert tuple(item.source_order for item in result.items) == tuple(
        item.source_order for item in scan_result.items
    )
    assert len(result.emit_returns) == 1
    directive = result.emit_returns[0]
    assert directive.payload_text == "left + right"
    assert directive.full_span.text == "emit_return(left + right)"
    assert tuple(segment.segment.span.text for segment in result.opaque_raw_segments) == (
        ";",
    )


def test_m231_multiline_intrin_compose_payload_stays_raw() -> None:
    envelope = _envelope_containing(
        _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl",
        "suffix=value<backend>(intrin::suffix",
    )

    result = lower_emit_return_regions(scan_source_body_envelope(envelope))

    assert result.diagnostics == ()
    assert len(result.emit_returns) == 1
    payload_text = result.emit_returns[0].payload_text
    assert payload_text.startswith("\n              intrin_compose<")
    assert "suffix=value<backend>(intrin::suffix" in payload_text
    assert payload_text.endswith("\n            ")
    assert result.opaque_regions == ()


def test_m231_call_payload_from_real_tsl_stays_raw() -> None:
    envelope = _envelope_containing(
        _TSLDATA_ROOT / "primitives" / "conversion" / "cast.tsl",
        "emit_return(call<primitive=reinterpret[Vec, ToBase]>(data));",
    )

    result = lower_emit_return_regions(scan_source_body_envelope(envelope))

    assert result.diagnostics == ()
    assert len(result.emit_returns) == 1
    assert result.emit_returns[0].payload_text == (
        "call<primitive=reinterpret[Vec, ToBase]>(data)"
    )


def test_m231_raw_target_language_looking_payload_stays_raw() -> None:
    envelope = _envelope_containing(
        _TSLDATA_ROOT / "primitives" / "load_store" / "load.tsl",
        "emit_return(*ptr);",
    )

    result = lower_emit_return_regions(scan_source_body_envelope(envelope))

    assert result.diagnostics == ()
    assert len(result.emit_returns) == 1
    assert result.emit_returns[0].payload_text == "*ptr"


def test_m231_nested_payload_regions_are_not_recursively_lowered() -> None:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=(
            "emit_return(intrin_compose<svadd, post=x>("
            "call<primitive=mask_true[Vec]>(), left, right));"
        ),
    )
    scan_result = scan_source_body_text(source_text)
    nested_scan = scan_source_body_text(
        SourceBodyText.from_span(scan_result.regions[0].payload.payload_span)
    )

    result = lower_emit_return_regions(scan_result)

    assert result.diagnostics == ()
    assert tuple(region.head.keyword for region in nested_scan.regions) == (
        SourceBodyKeyword.INTRIN_COMPOSE,
    )
    assert len(result.emit_returns) == 1
    assert result.opaque_regions == ()
    assert "call<primitive=mask_true[Vec]>" in result.emit_returns[0].payload_text


def test_m231_non_return_region_is_preserved_as_opaque() -> None:
    scan_result = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=4,
            column=1,
            text="call<primitive=add>(left, right);",
        )
    )

    result = lower_emit_return_regions(scan_result)

    assert result.diagnostics == ()
    assert result.emit_returns == ()
    assert len(result.opaque_regions) == 1
    assert result.opaque_regions[0].region.head.keyword is SourceBodyKeyword.CALL
    assert tuple(segment.segment.span.text for segment in result.opaque_raw_segments) == (
        ";",
    )


def test_m231_malformed_scan_result_propagates_diagnostics_and_lowers_nothing() -> None:
    scan_result = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=11,
            column=2,
            text="prefix emit_return(call<primitive=add>(left, right); suffix",
        )
    )

    result = lower_emit_return_regions(scan_result)

    assert result.items == ()
    assert result.emit_returns == ()
    assert result.diagnostics == scan_result.diagnostics
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-PAREN"
    ]


def test_m231_unsupported_return_region_reports_without_source_repair() -> None:
    return_scan = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=3,
            column=1,
            text="emit_return(value);",
        )
    )
    selector_scan = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=3,
            column=1,
            text="call<primitive=add>(left, right);",
        )
    )
    bad_region = replace(
        return_scan.regions[0],
        selector=selector_scan.regions[0].selector,
    )
    bad_scan = SourceBodyLexicalScanResult(
        source_text=return_scan.source_text,
        items=(bad_region,),
        diagnostics=(),
    )

    result = lower_emit_return_regions(bad_scan)

    assert result.emit_returns == ()
    assert len(result.opaque_regions) == 1
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-EMIT-RETURN-UNSUPPORTED-REGION"
    ]
    assert result.diagnostics[0].location is not None
    assert result.diagnostics[0].location.line == 3
    assert "selectors are not part" in result.diagnostics[0].message


def _envelope_containing(path: Path, needle: str) -> ParsedImplementationBodyEnvelope:
    document = _parse_one(path)
    return next(
        envelope
        for primitive in document.primitives
        for envelope in primitive.body_envelopes
        if needle in envelope.payload_text
    )


def _parse_one(path: Path):
    source = _source_document(path)
    result = OuterTslParser().parse((source,))
    assert result.diagnostics == ()
    return result.documents[0]


def _source_document(path: Path) -> SourceDocument:
    text = path.read_text(encoding="utf-8")
    return SourceDocument(
        path=path.resolve(),
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
