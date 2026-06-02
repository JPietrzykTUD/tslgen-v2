from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendTranslatedTypeSpelling,
    BackendTranslatedValue,
    BackendValueText,
)
from tslgen.backends.cpp import (
    CppBodyText,
    CppRenderedTypeQueryBodyTokens,
    CppRenderedValueQueryBodyTokens,
    CppTypeQueryBodyTokenRenderResult,
    CppValueQueryBodyTokenRenderResult,
    render_cpp_body_tokens_from_type_query_handoff,
    render_cpp_body_tokens_from_value_query_handoff,
)
from tslgen.backends.rust import (
    RustBodyText,
    RustRenderedTypeQueryBodyTokens,
    RustRenderedValueQueryBodyTokens,
    RustTypeQueryBodyTokenRenderResult,
    RustValueQueryBodyTokenRenderResult,
    render_rust_body_tokens_from_type_query_handoff,
    render_rust_body_tokens_from_value_query_handoff,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendTranslationKey,
    BackendTypeKey,
    BackendTypeSpellingText,
)
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    BackendTypeQueryHandoff,
    BackendTypeQueryHandoffRequestSegment,
    BackendTypeSpellingRequest,
    BackendUninitValueRequest,
    BackendValueQueryHandoff,
    BackendValueQueryHandoffRequestSegment,
    Lowerer,
    discover_backend_type_queries_in_text,
    discover_backend_value_queries_in_text,
)


def test_m221_evidence_gate_selects_only_backend_type_and_value_families() -> None:
    type_handoff = _type_handoff("type<backend>(scalar::ui8)")
    type_segment = _type_segments(type_handoff)[0]
    type_spelling = _translated_type(type_segment, spelling="uint8_t")

    value_handoff = _value_handoff("value<backend>(uninit::scalar)")
    value_segment = _value_segments(value_handoff)[0]
    value = _translated_value(value_segment, value_text="{}")

    assert isinstance(type_segment.request, BackendTypeSpellingRequest)
    assert type_spelling.request is type_segment.request
    assert isinstance(value_segment.request, BackendUninitValueRequest)
    assert value.request is value_segment.request
    assert _excluded_m221_families() == (
        "source_operation",
        "control_directive",
        "loop",
        "primitive_call",
        "signature",
        "intrinsic",
        "general_body_token",
    )


def test_m221_cpp_substitutes_backend_type_query_between_raw_tokens() -> None:
    handoff = _type_handoff("Type = type<backend>(scalar::ui32);")
    segment = _type_segments(handoff)[0]
    spelling = _translated_type(segment, spelling="uint32_t")

    result = render_cpp_body_tokens_from_type_query_handoff(handoff, (spelling,))

    assert result.diagnostics == ()
    assert isinstance(result.body, CppRenderedTypeQueryBodyTokens)
    assert result.body.text == "Type = uint32_t;"
    assert result.body.handoff is handoff
    assert result.body.spellings == (spelling,)
    assert result.body.source == handoff.source


def test_m221_rust_substitutes_backend_type_query_between_raw_tokens() -> None:
    handoff = _type_handoff("let value: type<backend>(scalar::ui32);", backend="rust")
    segment = _type_segments(handoff)[0]
    spelling = _translated_type(segment, backend="rust", spelling="u32")

    result = render_rust_body_tokens_from_type_query_handoff(handoff, (spelling,))

    assert result.diagnostics == ()
    assert isinstance(result.body, RustRenderedTypeQueryBodyTokens)
    assert result.body.text == "let value: u32;"
    assert result.body.handoff is handoff
    assert result.body.spellings == (spelling,)


def test_m221_cpp_substitutes_backend_value_query_between_raw_tokens() -> None:
    handoff = _value_handoff("return value<backend>(uninit::scalar);")
    segment = _value_segments(handoff)[0]
    value = _translated_value(segment, value_text="{}")

    result = render_cpp_body_tokens_from_value_query_handoff(handoff, (value,))

    assert result.diagnostics == ()
    assert isinstance(result.body, CppRenderedValueQueryBodyTokens)
    assert result.body.text == "return {};"
    assert result.body.handoff is handoff
    assert result.body.values == (value,)
    assert result.body.source == handoff.source


def test_m221_rust_substitutes_backend_value_query_between_raw_tokens() -> None:
    handoff = _value_handoff("let value = value<backend>(uninit::scalar);", backend="rust")
    segment = _value_segments(handoff)[0]
    value = _translated_value(
        segment,
        backend="rust",
        value_text="core::mem::MaybeUninit::zeroed().assume_init()",
    )

    result = render_rust_body_tokens_from_value_query_handoff(handoff, (value,))

    assert result.diagnostics == ()
    assert isinstance(result.body, RustRenderedValueQueryBodyTokens)
    assert result.body.text == (
        "let value = core::mem::MaybeUninit::zeroed().assume_init();"
    )
    assert result.body.values == (value,)


def test_m221_substitutes_multiple_type_queries_in_source_order() -> None:
    handoff = _type_handoff(
        "pair<type<backend>(scalar::ui8), type<backend>(scalar::ui16)>"
    )
    first, second = _type_segments(handoff)
    first_spelling = _translated_type(first, spelling="uint8_t")
    second_spelling = _translated_type(second, spelling="uint16_t")

    result = render_cpp_body_tokens_from_type_query_handoff(
        handoff,
        (second_spelling, first_spelling),
    )

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "pair<uint8_t, uint16_t>"
    assert result.body.spellings == (first_spelling, second_spelling)


def test_m221_substitutes_multiple_value_queries_in_source_order() -> None:
    handoff = _value_handoff(
        "value<backend>(uninit::scalar), value<backend>(x86::mm_fround_to_zero)"
    )
    first, second = _value_segments(handoff)
    first_value = _translated_value(first, value_text="{}")
    second_value = _translated_value(second, value_text="_MM_FROUND_TO_ZERO")

    result = render_cpp_body_tokens_from_value_query_handoff(
        handoff,
        (second_value, first_value),
    )

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "{}, _MM_FROUND_TO_ZERO"
    assert result.body.values == (first_value, second_value)


def test_m221_diagnoses_missing_rendered_type_value() -> None:
    handoff = _type_handoff("type<backend>(scalar::ui32)")

    result = render_cpp_body_tokens_from_type_query_handoff(handoff, ())

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-MISSING-RENDERED-VALUE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _type_segments(handoff)[0].source


def test_m221_diagnoses_extra_rendered_type_value() -> None:
    handoff = _type_handoff("type<backend>(scalar::ui32)")
    other_handoff = _type_handoff("type<backend>(scalar::ui64)")
    extra_spelling = _translated_type(_type_segments(other_handoff)[0])

    result = render_cpp_body_tokens_from_type_query_handoff(
        handoff,
        (extra_spelling,),
    )

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-EXTRA-RENDERED-VALUE",
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-MISSING-RENDERED-VALUE",
    )
    assert result.diagnostics[0].location == extra_spelling.source


def test_m221_diagnoses_duplicate_rendered_type_value() -> None:
    handoff = _value_handoff("value<backend>(uninit::scalar)")
    value = _translated_value(_value_segments(handoff)[0])

    result = render_cpp_body_tokens_from_value_query_handoff(handoff, (value, value))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-DUPLICATE-RENDERED-VALUE",
    )
    assert result.diagnostics[0].location == value.source


def test_m221_diagnoses_backend_mismatched_rendered_type_value() -> None:
    handoff = _type_handoff("type<backend>(scalar::ui32)")
    mismatched = _translated_type(
        _type_segments(handoff)[0],
        backend="rust",
        spelling="u32",
    )

    result = render_cpp_body_tokens_from_type_query_handoff(handoff, (mismatched,))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-BACKEND-MISMATCH",
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-MISSING-RENDERED-VALUE",
    )
    assert "'rust'" in result.diagnostics[0].message


def test_m221_diagnoses_opaque_nonrenderable_type_value_tokens() -> None:
    hidden_directive = LowerableDirective(
        name="var",
        arguments=("typed", "Type, hidden"),
        source=_location(column=40),
    )
    body = ImplementationBody(
        tokens=(
            RawStringToken("prefix ", _location()),
            hidden_directive,
            RawStringToken("type<backend>(scalar::ui32)", _location(column=80)),
        ),
        source=_location(),
    )
    handoff = _type_body_handoff(body)
    spelling = _translated_type(_type_segments(handoff)[0], spelling="uint32_t")

    result = render_cpp_body_tokens_from_type_query_handoff(handoff, (spelling,))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-TYPE-VALUE-BODY-TOKENS-UNSUPPORTED-OPAQUE-TOKEN-SEGMENT",
    )
    assert result.diagnostics[0].location == handoff.segments[0].source


def test_m221_public_backend_imports_are_available() -> None:
    from tslgen.backends.cpp import (  # noqa: PLC0415
        CppRenderedTypeQueryBodyTokens,
        CppRenderedValueQueryBodyTokens,
        CppTypeQueryBodyTokenRenderResult,
        CppValueQueryBodyTokenRenderResult,
        render_cpp_body_tokens_from_type_query_handoff,
        render_cpp_body_tokens_from_value_query_handoff,
    )
    from tslgen.backends.rust import (  # noqa: PLC0415
        RustRenderedTypeQueryBodyTokens,
        RustRenderedValueQueryBodyTokens,
        RustTypeQueryBodyTokenRenderResult,
        RustValueQueryBodyTokenRenderResult,
        render_rust_body_tokens_from_type_query_handoff,
        render_rust_body_tokens_from_value_query_handoff,
    )

    assert CppBodyText("x") == "x"
    assert RustBodyText("x") == "x"
    assert CppRenderedTypeQueryBodyTokens.__name__ == "CppRenderedTypeQueryBodyTokens"
    assert CppRenderedValueQueryBodyTokens.__name__ == "CppRenderedValueQueryBodyTokens"
    assert CppTypeQueryBodyTokenRenderResult.__name__ == (
        "CppTypeQueryBodyTokenRenderResult"
    )
    assert CppValueQueryBodyTokenRenderResult.__name__ == (
        "CppValueQueryBodyTokenRenderResult"
    )
    assert RustRenderedTypeQueryBodyTokens.__name__ == "RustRenderedTypeQueryBodyTokens"
    assert RustRenderedValueQueryBodyTokens.__name__ == "RustRenderedValueQueryBodyTokens"
    assert RustTypeQueryBodyTokenRenderResult.__name__ == (
        "RustTypeQueryBodyTokenRenderResult"
    )
    assert RustValueQueryBodyTokenRenderResult.__name__ == (
        "RustValueQueryBodyTokenRenderResult"
    )
    assert callable(render_cpp_body_tokens_from_type_query_handoff)
    assert callable(render_cpp_body_tokens_from_value_query_handoff)
    assert callable(render_rust_body_tokens_from_type_query_handoff)
    assert callable(render_rust_body_tokens_from_value_query_handoff)


def _type_handoff(text: str, *, backend: str = "cpp") -> BackendTypeQueryHandoff:
    discovery = discover_backend_type_queries_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_type_query_discovery(
        _selected(ImplementationBody(tokens=(), source=_location()), backend=backend),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _value_handoff(text: str, *, backend: str = "cpp") -> BackendValueQueryHandoff:
    discovery = discover_backend_value_queries_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_value_query_discovery(
        _selected(ImplementationBody(tokens=(), source=_location()), backend=backend),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _type_body_handoff(body: ImplementationBody) -> BackendTypeQueryHandoff:
    selected = _selected(body)
    lowerer = Lowerer()
    discovery = lowerer.discover_backend_type_queries(selected)
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = lowerer.lower_backend_type_query_discovery(selected, discovery.discovery)
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _type_segments(
    handoff: BackendTypeQueryHandoff,
) -> tuple[BackendTypeQueryHandoffRequestSegment, ...]:
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendTypeQueryHandoffRequestSegment)
    )


def _value_segments(
    handoff: BackendValueQueryHandoff,
) -> tuple[BackendValueQueryHandoffRequestSegment, ...]:
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendValueQueryHandoffRequestSegment)
    )


def _translated_type(
    segment: BackendTypeQueryHandoffRequestSegment,
    *,
    backend: str | None = None,
    spelling: str = "int32_t",
) -> BackendTranslatedTypeSpelling:
    return BackendTranslatedTypeSpelling(
        request=segment.request,
        backend=BackendId(backend or segment.request.backend),
        spelling=BackendTypeSpellingText(spelling),
        metadata_kind="language_type",
        metadata_key=BackendTypeKey("s32"),
        metadata_source=_location(line=2),
        source=segment.request.source,
    )


def _translated_value(
    segment: BackendValueQueryHandoffRequestSegment,
    *,
    backend: str | None = None,
    value_text: str = "{}",
) -> BackendTranslatedValue:
    return BackendTranslatedValue(
        request=segment.request,
        backend=BackendId(backend or segment.request.backend),
        value=BackendValueText(value_text),
        metadata_key=BackendTranslationKey("value_uninit"),
        metadata_source=_location(line=3),
        source=segment.request.source,
    )


def _selected(
    body: ImplementationBody,
    *,
    backend: str = "cpp",
) -> SelectedImplementation:
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=body,
        source=body.source,
    )
    primitive = Primitive(
        name="fixture",
        signature="binary",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=body.source,
    )
    target = Target(
        backend=backend,
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _excluded_m221_families() -> tuple[str, ...]:
    return (
        "source_operation",
        "control_directive",
        "loop",
        "primitive_call",
        "signature",
        "intrinsic",
        "general_body_token",
    )


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
