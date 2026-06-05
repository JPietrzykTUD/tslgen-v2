from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path

from tslgen.lowering.source_body_fragments import (
    BackendIntrinsicKeywordRequest,
    BackendIntrinsicKeywordRequestExtractionResult,
    KeywordRegionFragment,
    RawSourceFragment,
    SourceBodyFragmentLoweringResult,
    SourceBodyFragmentSequence,
    extract_intrin_compose_requests,
    lower_source_body_fragments,
)
from tslgen.syntax.source_body_regions import (
    SourceBodyDelimitedSpan,
    SourceBodyKeyword,
    SourceBodyLexicalRegionCandidate,
    SourceBodyRegionHead,
    SourceBodyText,
)


def test_m233_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        BackendIntrinsicKeywordRequest,
        BackendIntrinsicKeywordRequestExtractionResult,
        KeywordRegionFragment,
        RawSourceFragment,
        SourceBodyFragmentLoweringResult,
        SourceBodyFragmentSequence,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m233_raw_source_text_remains_one_raw_fragment() -> None:
    result = _lower("left + right")

    assert result.diagnostics == ()
    assert tuple(fragment.span.text for fragment in result.sequence.raw_fragments) == (
        "left + right",
    )
    assert result.sequence.keyword_fragments == ()


def test_m233_recursively_finds_intrin_compose_under_emit_return() -> None:
    result = _lower("emit_return(intrin_compose<add>(left, right));")

    assert result.diagnostics == ()
    emit_return = result.sequence.keyword_fragments[0]
    assert emit_return.keyword is SourceBodyKeyword.EMIT_RETURN
    assert emit_return.payload_fragments is not None
    nested = emit_return.payload_fragments.keyword_fragments[0]
    assert nested.keyword is SourceBodyKeyword.INTRIN_COMPOSE

    extraction = extract_intrin_compose_requests(result.sequence)

    assert extraction.diagnostics == ()
    assert len(extraction.requests) == 1
    request = extraction.requests[0].request
    assert request.intrinsic_kind == "intrin_compose"
    assert request.angle_payload_text == "add"
    assert request.argument_text == "left, right"
    assert request.source_text == "intrin_compose<add>(left, right)"
    assert request.source.column == len("emit_return(") + 1


def test_m233_recursively_finds_intrin_compose_under_call() -> None:
    result = _lower("call<primitive=foo>(intrin_compose<bar>(value));")

    assert result.diagnostics == ()
    call = result.sequence.keyword_fragments[0]
    assert call.keyword is SourceBodyKeyword.CALL
    assert call.payload_fragments is not None
    nested = call.payload_fragments.keyword_fragments[0]
    assert nested.keyword is SourceBodyKeyword.INTRIN_COMPOSE

    extraction = extract_intrin_compose_requests(result.sequence)

    assert extraction.diagnostics == ()
    assert len(extraction.requests) == 1
    request = extraction.requests[0].request
    assert request.angle_payload_text == "bar"
    assert request.argument_text == "value"
    assert request.source.column == len("call<primitive=foo>(") + 1


def test_m233_recursively_finds_intrin_compose_in_control_body() -> None:
    result = _lower(
        "if<generation>(cond) {\n"
        "  emit_return(intrin_compose<svadd, post=x>(left, right));\n"
        "}"
    )

    assert result.diagnostics == ()
    branch = result.sequence.keyword_fragments[0]
    assert branch.keyword is SourceBodyKeyword.IF
    assert branch.body_fragments is not None
    emit_return = branch.body_fragments.keyword_fragments[0]
    assert emit_return.keyword is SourceBodyKeyword.EMIT_RETURN
    assert emit_return.payload_fragments is not None
    nested = emit_return.payload_fragments.keyword_fragments[0]
    assert nested.keyword is SourceBodyKeyword.INTRIN_COMPOSE

    extraction = extract_intrin_compose_requests(result.sequence)

    assert extraction.diagnostics == ()
    assert len(extraction.requests) == 1
    assert extraction.requests[0].request.angle_payload_text == "svadd, post=x"


def test_m233_child_scan_diagnostics_propagate_without_source_repair() -> None:
    result = _lower("call<primitive=foo>(intrin_compose<bar(value));")

    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-ANGLE"
    ]
    call = result.sequence.keyword_fragments[0]
    assert call.payload_fragments is not None
    assert tuple(fragment.span.text for fragment in call.payload_fragments.raw_fragments) == (
        "intrin_compose<bar(value)",
    )

    extraction = extract_intrin_compose_requests(result.sequence)

    assert extraction.requests == ()
    assert extraction.diagnostics == ()


def test_m233_root_scan_diagnostics_propagate_without_source_repair() -> None:
    result = _lower("intrin_compose<add(value)")

    assert result.sequence.keyword_fragments == ()
    assert tuple(fragment.span.text for fragment in result.sequence.raw_fragments) == (
        "intrin_compose<add(value)",
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BODY-REGION-UNBALANCED-ANGLE"
    ]
    assert result.diagnostics[0].location is not None
    assert result.diagnostics[0].location.path == Path("fixture.tsl")
    assert result.diagnostics[0].location.line == 1
    assert result.diagnostics[0].location.column == len("intrin_compose") + 1


def test_m233_rejects_missing_intrin_compose_selector_without_repair() -> None:
    source_text = _source_text("intrin_compose")
    span = source_text.span(0, len(source_text.text))
    fragment = KeywordRegionFragment(
        source_order=0,
        source_region=SourceBodyLexicalRegionCandidate(
            source_order=0,
            head=SourceBodyRegionHead(
                SourceBodyKeyword.INTRIN_COMPOSE,
                "intrin_compose",
                expects_selector=True,
            ),
            full_span=span,
            head_span=span,
            selector=None,
            payload=None,
        ),
    )

    extraction = extract_intrin_compose_requests(
        SourceBodyFragmentSequence(
            source_text=source_text,
            fragments=(fragment,),
        )
    )

    assert extraction.requests == ()
    assert [diagnostic.code for diagnostic in extraction.diagnostics] == [
        "TSL-LOWER-INTRIN-COMPOSE-FRAGMENT-MALFORMED"
    ]
    assert extraction.diagnostics[0].location is not None
    assert extraction.diagnostics[0].severity == "error"
    assert extraction.diagnostics[0].location.path == Path("fixture.tsl")
    assert extraction.diagnostics[0].location.line == 1
    assert extraction.diagnostics[0].location.column == 1
    assert "balanced angle selector" in extraction.diagnostics[0].message


def test_m233_rejects_missing_intrin_compose_payload_without_repair() -> None:
    source_text = _source_text("intrin_compose<add>")
    full_span = source_text.span(0, len(source_text.text))
    selector = SourceBodyDelimitedSpan(
        kind="angle",
        delimiter=("<", ">"),
        full_span=source_text.span(len("intrin_compose"), len(source_text.text)),
        payload_span=source_text.span(
            len("intrin_compose<"),
            len("intrin_compose<add"),
        ),
    )
    fragment = KeywordRegionFragment(
        source_order=0,
        source_region=SourceBodyLexicalRegionCandidate(
            source_order=0,
            head=SourceBodyRegionHead(
                SourceBodyKeyword.INTRIN_COMPOSE,
                "intrin_compose",
                expects_selector=True,
            ),
            full_span=full_span,
            head_span=source_text.span(0, len("intrin_compose")),
            selector=selector,
            payload=None,
        ),
    )

    extraction = extract_intrin_compose_requests(
        SourceBodyFragmentSequence(
            source_text=source_text,
            fragments=(fragment,),
        )
    )

    assert extraction.requests == ()
    assert len(extraction.diagnostics) == 1
    diagnostic = extraction.diagnostics[0]
    assert diagnostic.severity == "error"
    assert diagnostic.code == "TSL-LOWER-INTRIN-COMPOSE-FRAGMENT-MALFORMED"
    assert diagnostic.location is not None
    assert diagnostic.location.path == Path("fixture.tsl")
    assert diagnostic.location.line == 1
    assert diagnostic.location.column == 1
    assert "parenthesized argument payload" in diagnostic.message


def test_m233_does_not_call_legacy_intrinsic_text_discovery(monkeypatch) -> None:
    from tslgen.lowering import backend_intrinsics

    def fail_legacy_discovery(*args, **kwargs):
        raise AssertionError("legacy intrinsic text discovery must not be used")

    monkeypatch.setattr(
        backend_intrinsics,
        "discover_backend_intrinsic_requests_in_text",
        fail_legacy_discovery,
    )

    result = _lower("call<primitive=foo>(intrin_compose<bar>(value));")
    extraction = extract_intrin_compose_requests(result.sequence)

    assert result.diagnostics == ()
    assert extraction.diagnostics == ()
    assert len(extraction.requests) == 1


def test_m233_fragment_names_do_not_encode_pairwise_contexts() -> None:
    names = (
        BackendIntrinsicKeywordRequest.__name__,
        BackendIntrinsicKeywordRequestExtractionResult.__name__,
        KeywordRegionFragment.__name__,
        RawSourceFragment.__name__,
        SourceBodyFragmentLoweringResult.__name__,
        SourceBodyFragmentSequence.__name__,
        extract_intrin_compose_requests.__name__,
        lower_source_body_fragments.__name__,
    )

    forbidden = ("EmitReturnIntrin", "EmitReturnCall", "ReturnPayloadIntrin")
    assert not any(
        forbidden_name in name
        for name in names
        for forbidden_name in forbidden
    )


def _lower(text: str) -> SourceBodyFragmentLoweringResult:
    return lower_source_body_fragments(_source_text(text))


def _source_text(text: str) -> SourceBodyText:
    return SourceBodyText(
        path=Path("fixture.tsl"),
        line=1,
        column=1,
        text=text,
    )
