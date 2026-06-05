from __future__ import annotations

from dataclasses import is_dataclass
from hashlib import sha256
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.syntax.outer_ast import ParsedImplementationBodyEnvelope
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import (
    SourceBodyDelimitedSpan,
    SourceBodyKeyword,
    SourceBodyLexicalRegionCandidate,
    SourceBodyLexicalRegionScanner,
    SourceBodyRawSegment,
    SourceBodyRegionHead,
    SourceBodySpan,
    SourceBodyText,
    scan_source_body_envelope,
    scan_source_body_text,
)
from tslgen.syntax.tsil_lexical import ANGLE_DELIMITER, matching_close_lexical


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TSLDATA_ROOT = _REPO_ROOT / "tsldata"


def test_m230_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        SourceBodyDelimitedSpan,
        SourceBodyLexicalRegionCandidate,
        SourceBodyRawSegment,
        SourceBodyRegionHead,
        SourceBodySpan,
        SourceBodyText,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m230_quote_aware_delimiter_matching_ignores_quoted_delimiters() -> None:
    text = 'intrin_compose<name suffix="not>selector">(value)'
    open_index = len("intrin_compose")

    close_index = matching_close_lexical(text, open_index, ANGLE_DELIMITER)

    assert close_index == text.index(">(")


def test_m230_quote_aware_delimiter_matching_accepts_escaped_inline_quotes() -> None:
    paren_text = r'emit_return(\"not)done\");'
    angle_text = r'intrin_compose<name suffix=\"not>selector\">(value)'

    assert matching_close_lexical(paren_text, len("emit_return"), ("(", ")")) == (
        paren_text.rindex(")")
    )
    assert matching_close_lexical(angle_text, len("intrin_compose"), ANGLE_DELIMITER) == (
        angle_text.index(">(")
    )


def test_m230_inline_envelope_preserves_escaped_payload_and_finds_nested_region() -> None:
    document = _parse_one(_TSLDATA_ROOT / "primitives" / "conversion" / "cast.tsl")
    reinterpret = document.primitives[0]
    envelope = _body(
        reinterpret.body_envelopes,
        ("[avx512, avx2, sse]", "f?", "ToBase", "f?"),
    )

    result = scan_source_body_envelope(envelope)

    assert result.diagnostics == ()
    assert result.source_text.text == envelope.payload_text
    assert 'infix_sep=\\"\\"' in result.source_text.text
    assert _region_heads(result) == ("emit_return",)
    assert tuple(segment.span.text for segment in result.raw_segments) == (";",)

    emit_return = result.regions[0]
    assert emit_return.head.keyword is SourceBodyKeyword.EMIT_RETURN
    assert emit_return.payload is not None
    nested = scan_source_body_text(SourceBodyText.from_span(emit_return.payload.payload_span))
    assert nested.diagnostics == ()
    assert _region_heads(nested) == ("intrin_compose",)
    assert nested.regions[0].selector is not None
    assert 'infix_sep=\\"\\"' in nested.regions[0].selector.payload_span.text


def test_m230_multiline_envelope_preserves_spans_and_top_level_source_order() -> None:
    document = _parse_one(
        _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl"
    )
    add = document.primitives[0]
    envelope = _body(add.body_envelopes, ("[generic, oneAPIfpga, oneAPIfpgaRTL]", "arith"))

    result = scan_source_body_envelope(envelope)

    assert result.diagnostics == ()
    assert _region_heads(result) == ("loop", "emit_return")
    assert tuple(region.source_order for region in result.regions) == (1, 3)
    assert tuple(segment.source_order for segment in result.raw_segments) == (0, 2, 4)
    assert result.source_text.text == envelope.payload_text

    loop = result.regions[0]
    assert loop.head_span.line == 42
    assert loop.head_span.column == 13
    assert loop.selector is not None
    assert loop.selector.payload_span.text == "range"
    assert loop.payload is not None
    assert loop.payload.payload_span.text.startswith("i, 0, value<generation>")
    assert loop.body is not None
    assert "result[i] = call<primitive=@self" in loop.body.payload_span.text

    nested = scan_source_body_text(SourceBodyText.from_span(loop.body.payload_span))
    assert nested.diagnostics == ()
    assert _region_heads(nested) == ("call",)


def test_m230_discovers_configured_control_regions_without_body_semantics() -> None:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=10,
        column=3,
        text=(
            "if<generation>(value<generation>(primitive::attribute(aligned))) {\n"
            "  emit_return(call<primitive=load>(ptr));\n"
            "} else<generation> {\n"
            "  loop<range>(i, 0, n, 1) {\n"
            "    call<primitive=store>(i);\n"
            "  }\n"
            "}\n"
            "switch<compile>(value<generation>(primitive::attribute(kind))) {\n"
            "  emit_return(result);\n"
            "}"
        ),
    )

    result = scan_source_body_text(source_text)

    assert result.diagnostics == ()
    assert _region_heads(result) == ("if", "else", "switch")
    assert all(region.body is not None for region in result.regions)
    assert result.regions[0].payload is not None
    assert result.regions[0].payload.payload_span.text.startswith("value<generation>")
    assert result.regions[1].payload is None
    assert result.regions[2].selector is not None
    assert result.regions[2].selector.payload_span.text == "compile"

    else_region = result.regions[1]
    assert else_region.body is not None
    nested = scan_source_body_text(SourceBodyText.from_span(else_region.body.payload_span))
    assert nested.diagnostics == ()
    assert _region_heads(nested) == ("loop",)


def test_m230_raw_target_language_if_is_not_a_generation_region() -> None:
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=3,
        column=1,
        text="if (mask) { emit_return(value); }",
    )

    result = SourceBodyLexicalRegionScanner().scan(source_text)

    assert result.diagnostics == ()
    assert _region_heads(result) == ("emit_return",)
    assert result.regions[0].head_span.column == 13


def test_m230_custom_region_heads_remain_configurable() -> None:
    custom_head = SourceBodyRegionHead.custom("custom_kw", expects_selector=True)
    source_text = SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text="custom_kw<selector>(payload);",
    )

    result = SourceBodyLexicalRegionScanner((custom_head,)).scan(source_text)

    assert result.diagnostics == ()
    assert len(result.regions) == 1
    assert result.regions[0].head.keyword is SourceBodyKeyword.CUSTOM
    assert result.regions[0].head.name == "custom_kw"
    assert result.regions[0].selector is not None
    assert result.regions[0].selector.payload_span.text == "selector"
    assert result.regions[0].payload is not None
    assert result.regions[0].payload.payload_span.text == "payload"


def test_m230_malformed_configured_regions_report_source_locations() -> None:
    missing_paren = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=5,
            column=7,
            text="call<primitive=add> left, right",
        )
    )
    unbalanced_paren = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=11,
            column=2,
            text="prefix emit_return(call<primitive=add>(left, right); suffix",
        )
    )
    missing_brace = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=17,
            column=1,
            text="if<generation>(cond) emit_return(value);",
        )
    )
    unbalanced_angle = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=23,
            column=4,
            text="call<primitive=add(left, right)",
        )
    )

    assert [diagnostic.code for diagnostic in missing_paren.diagnostics] == [
        "TSL-BODY-REGION-MISSING-PAREN"
    ]
    assert missing_paren.diagnostics[0].location is not None
    assert missing_paren.diagnostics[0].location.line == 5
    assert missing_paren.diagnostics[0].location.column == 27
    assert missing_paren.regions == ()
    assert tuple(segment.span.text for segment in missing_paren.raw_segments) == (
        "call<primitive=add> left, right",
    )

    assert [diagnostic.code for diagnostic in unbalanced_paren.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-PAREN"
    ]
    assert unbalanced_paren.regions == ()
    assert tuple(segment.span.text for segment in unbalanced_paren.raw_segments) == (
        "prefix emit_return(call<primitive=add>(left, right); suffix",
    )
    assert unbalanced_paren.diagnostics[0].location is not None
    assert unbalanced_paren.diagnostics[0].location.line == 11
    assert unbalanced_paren.diagnostics[0].location.column == 20

    assert [diagnostic.code for diagnostic in missing_brace.diagnostics] == [
        "TSL-BODY-REGION-MISSING-BRACE"
    ]
    assert missing_brace.regions == ()
    assert tuple(segment.span.text for segment in missing_brace.raw_segments) == (
        "if<generation>(cond) emit_return(value);",
    )
    assert missing_brace.diagnostics[0].location is not None
    assert missing_brace.diagnostics[0].location.line == 17
    assert missing_brace.diagnostics[0].location.column == 22

    assert [diagnostic.code for diagnostic in unbalanced_angle.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-ANGLE"
    ]
    assert unbalanced_angle.regions == ()
    assert unbalanced_angle.diagnostics[0].location is not None
    assert unbalanced_angle.diagnostics[0].location.line == 23
    assert unbalanced_angle.diagnostics[0].location.column == 8


def test_m230_escaped_inline_delimiters_do_not_create_false_regions_or_diagnostics() -> None:
    escaped_paren = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=3,
            column=1,
            text=r'emit_return(\"not)done\");',
        )
    )
    escaped_angle = scan_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=7,
            column=1,
            text=r'intrin_compose<name suffix=\"not>selector\">(value);',
        )
    )

    assert escaped_paren.diagnostics == ()
    assert _region_heads(escaped_paren) == ("emit_return",)
    assert escaped_paren.regions[0].payload is not None
    assert escaped_paren.regions[0].payload.payload_span.text == r'\"not)done\"'

    assert escaped_angle.diagnostics == ()
    assert _region_heads(escaped_angle) == ("intrin_compose",)
    assert escaped_angle.regions[0].selector is not None
    assert escaped_angle.regions[0].selector.payload_span.text == (
        r'name suffix=\"not>selector\"'
    )


def test_m230_representative_tsldata_payloads_scan_without_diagnostics() -> None:
    documents = tuple(
        _parse_one(path)
        for path in (
            _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl",
            _TSLDATA_ROOT / "primitives" / "conversion" / "cast.tsl",
            _TSLDATA_ROOT / "primitives" / "conversion" / "repr_change.tsl",
            _TSLDATA_ROOT / "primitives" / "bitwise" / "shifts.tsl",
            _TSLDATA_ROOT / "primitives" / "load_store" / "load.tsl",
            _TSLDATA_ROOT / "primitives" / "load_store" / "rnd_access.tsl",
        )
    )
    envelopes = tuple(
        envelope
        for document in documents
        for primitive in document.primitives
        for envelope in primitive.body_envelopes
    )

    scanned = tuple(scan_source_body_envelope(envelope) for envelope in envelopes)
    diagnostics = tuple(
        diagnostic for result in scanned for diagnostic in result.diagnostics
    )
    region_count = sum(len(result.regions) for result in scanned)
    recursive_heads = {
        region.head.name
        for result in scanned
        for region in _recursive_regions(result)
    }

    assert diagnostics == ()
    assert len(envelopes) > 100
    assert region_count > 100
    assert {
        "call",
        "else",
        "emit_return",
        "if",
        "intrin_compose",
        "loop",
        "switch",
    } <= recursive_heads


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


def _body(
    envelopes: tuple[ParsedImplementationBodyEnvelope, ...],
    selector_path: tuple[str, ...],
) -> ParsedImplementationBodyEnvelope:
    return next(
        envelope
        for envelope in envelopes
        if envelope.selector_path == selector_path
    )


def _region_heads(result) -> tuple[str, ...]:
    return tuple(region.head.name for region in result.regions)


def _recursive_regions(result):
    for region in result.regions:
        yield region
        for span in (region.selector, region.payload, region.body):
            if span is None:
                continue
            nested = scan_source_body_text(SourceBodyText.from_span(span.payload_span))
            assert nested.diagnostics == ()
            yield from _recursive_regions(nested)
