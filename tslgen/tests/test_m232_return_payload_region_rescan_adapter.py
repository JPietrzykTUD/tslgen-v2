from __future__ import annotations

from dataclasses import is_dataclass
from hashlib import sha256
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.lowering.emit_return_regions import (
    EmitReturnPayloadRawSegmentAdapter,
    EmitReturnPayloadRegionAdapter,
    EmitReturnPayloadRescanResult,
    LoweredEmitReturnDirective,
    lower_emit_return_regions,
    rescan_emit_return_payload,
)
from tslgen.syntax.outer_ast import ParsedImplementationBodyEnvelope
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import (
    SourceBodyKeyword,
    SourceBodyText,
    scan_source_body_envelope,
    scan_source_body_text,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TSLDATA_ROOT = _REPO_ROOT / "tsldata"


def test_m232_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        EmitReturnPayloadRawSegmentAdapter,
        EmitReturnPayloadRegionAdapter,
        EmitReturnPayloadRescanResult,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m232_raw_scalar_payload_is_only_wrapped_m230_raw_text() -> None:
    directive = _return_directive_containing(
        _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl",
        "emit_return(left + right);",
    )

    result = rescan_emit_return_payload(directive)

    assert result.diagnostics == ()
    assert result.return_directive is directive
    assert result.source_text.text == directive.payload_text
    assert result.regions == ()
    assert tuple(item.source_order for item in result.items) == (0,)
    assert len(result.raw_segments) == 1
    assert result.raw_segments[0].return_directive is directive
    assert result.raw_segments[0].segment.span.text == "left + right"


def test_m232_multiline_intrin_compose_payload_is_wrapped_m230_region() -> None:
    directive = _return_directive_containing(
        _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl",
        "suffix=value<backend>(intrin::suffix",
    )

    result = rescan_emit_return_payload(directive)

    assert result.diagnostics == ()
    assert len(result.regions) == 1
    assert result.regions[0].return_directive is directive
    assert result.regions[0].region.head.keyword is SourceBodyKeyword.INTRIN_COMPOSE
    assert result.regions[0].region.selector is not None
    assert result.regions[0].region.payload is not None
    assert "suffix=value<backend>(intrin::suffix" in (
        result.regions[0].region.selector.payload_span.text
    )
    assert tuple(segment.segment.span.text for segment in result.raw_segments) == (
        "\n              ",
        "\n            ",
    )


def test_m232_call_payload_is_wrapped_m230_region() -> None:
    directive = _return_directive_containing(
        _TSLDATA_ROOT / "primitives" / "conversion" / "cast.tsl",
        "emit_return(call<primitive=reinterpret[Vec, ToBase]>(data));",
    )

    result = rescan_emit_return_payload(directive)

    assert result.diagnostics == ()
    assert result.raw_segments == ()
    assert len(result.regions) == 1
    assert result.regions[0].return_directive is directive
    assert result.regions[0].region.head.keyword is SourceBodyKeyword.CALL
    assert result.regions[0].region.selector is not None
    assert result.regions[0].region.selector.payload_span.text == (
        "primitive=reinterpret[Vec, ToBase]"
    )


def test_m232_raw_pointer_payload_remains_wrapped_m230_raw_text() -> None:
    directive = _return_directive_containing(
        _TSLDATA_ROOT / "primitives" / "load_store" / "load.tsl",
        "emit_return(*ptr);",
    )

    result = rescan_emit_return_payload(directive)

    assert result.diagnostics == ()
    assert result.regions == ()
    assert len(result.raw_segments) == 1
    assert result.raw_segments[0].segment.span.text == "*ptr"


def test_m232_malformed_nested_region_propagates_m230_diagnostics() -> None:
    directive = _return_directive_from_text(
        "emit_return(intrin_compose<add left, right);"
    )

    result = rescan_emit_return_payload(directive)

    assert result.items == ()
    assert result.regions == ()
    assert result.raw_segments == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-ANGLE"
    ]
    assert result.diagnostics[0].location is not None
    assert result.diagnostics[0].location.line == 1
    assert result.diagnostics[0].location.column == 27


def test_m232_does_not_recursively_lower_nested_region_semantics() -> None:
    directive = _return_directive_from_text(
        "emit_return(call<primitive=add>(intrin_compose<add>(left, right), right));"
    )

    result = rescan_emit_return_payload(directive)

    assert result.diagnostics == ()
    assert len(result.regions) == 1
    assert result.regions[0].region.head.keyword is SourceBodyKeyword.CALL
    assert "intrin_compose<add>(left, right)" in (
        result.regions[0].region.payload.payload_span.text
    )


def _return_directive_containing(path: Path, needle: str) -> LoweredEmitReturnDirective:
    envelope = _envelope_containing(path, needle)
    result = lower_emit_return_regions(scan_source_body_envelope(envelope))
    assert result.diagnostics == ()
    assert result.emit_returns
    return next(
        directive
        for directive in result.emit_returns
        if needle.removeprefix("emit_return(").removesuffix(");")
        in directive.payload_text
    )


def _return_directive_from_text(text: str) -> LoweredEmitReturnDirective:
    scan_result = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=1,
            column=1,
            text=text,
        )
    )
    result = lower_emit_return_regions(scan_result)
    assert result.diagnostics == ()
    assert len(result.emit_returns) == 1
    return result.emit_returns[0]


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
