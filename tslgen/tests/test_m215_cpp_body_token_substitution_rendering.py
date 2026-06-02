from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendComposedIntrinsicInvocation,
    BackendDirectIntrinsicInvocation,
    BackendIntrinsicImmediateLiteral,
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
    assemble_backend_intrinsic_invocation,
)
from tslgen.backends.cpp import (
    CppBodyText,
    CppIntrinsicCallText,
    CppRenderedBodyTokens,
    CppRenderedIntrinsicCall,
    render_cpp_body_tokens_from_intrinsic_handoff,
    render_cpp_intrinsic_invocation_call,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)


def test_m215_substitutes_direct_intrinsic_between_raw_return_tokens() -> None:
    handoff = _text_handoff("return intrin<_mm_add_epi32>(left, right);")
    segment = _request_segments(handoff)[0]
    call = _rendered_direct_call(segment)

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.diagnostics == ()
    assert isinstance(result.body, CppRenderedBodyTokens)
    assert result.body.text == "return _mm_add_epi32(left, right);"
    assert result.body.calls == (call,)
    assert result.body.source == handoff.source


def test_m215_preserves_assignment_and_indexing_raw_text_around_composed_call() -> None:
    handoff = _text_handoff(
        "result[i] = intrin_compose<add, prefix=p, suffix=s>(left[i], right[i]);"
    )
    segment = _request_segments(handoff)[0]
    request = segment.request
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    call = _rendered_composed_call(
        segment,
        (
            ("prefix", BackendIntrinsicLiteralFragment("_mm_")),
            ("suffix", BackendIntrinsicLiteralFragment("epi32")),
        ),
    )

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "result[i] = _mm_add_epi32(left[i], right[i]);"


def test_m215_substitutes_multiple_intrinsics_in_source_order() -> None:
    handoff = _text_handoff("intrin<_first>(a) + intrin<_second>(b)")
    first, second = _request_segments(handoff)
    first_call = _rendered_direct_call(first)
    second_call = _rendered_direct_call(second)

    result = render_cpp_body_tokens_from_intrinsic_handoff(
        handoff,
        (second_call, first_call),
    )

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "_first(a) + _second(b)"
    assert result.body.calls == (first_call, second_call)


def test_m215_keeps_empty_intrinsic_argument_payload_from_m214() -> None:
    handoff = _text_handoff("before intrin<_mm_lfence>() after")
    call = _rendered_direct_call(_request_segments(handoff)[0])

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "before _mm_lfence() after"


def test_m215_preserves_opaque_nested_tsil_looking_argument_payload() -> None:
    handoff = _text_handoff(
        "return intrin<_mm_blend_epi32>("
        "left, intrin_compose<nested, suffix=si32>(right));"
    )
    call = _rendered_direct_call(_request_segments(handoff)[0])

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.diagnostics == ()
    assert result.body is not None
    assert (
        result.body.text
        == "return _mm_blend_epi32("
        "left, intrin_compose<nested, suffix=si32>(right));"
    )


def test_m215_preserves_source_provenance_and_immediate_metadata() -> None:
    handoff = _text_handoff("return intrin_compose<extract, immediate(1)=4>(data, 4);")
    segment = _request_segments(handoff)[0]
    call = _rendered_composed_call(
        segment,
        (("immediate", BackendIntrinsicImmediateLiteral(argument_index=1, value=4)),),
    )

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.diagnostics == ()
    assert result.body is not None
    assert result.body.text == "return extract(data, 4);"
    assert result.body.handoff is handoff
    assert result.body.source == handoff.source
    assert result.body.calls == (call,)
    assert result.body.immediates == call.immediates
    assert len(result.body.immediates) == 1


def test_m215_diagnoses_missing_rendered_call_for_request_segment() -> None:
    handoff = _text_handoff("return intrin<_mm_add_epi32>(left, right);")

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, ())

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-BODY-TOKENS-MISSING-INTRINSIC-CALL",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _request_segments(handoff)[0].source


def test_m215_diagnoses_extra_rendered_call_not_in_handoff() -> None:
    handoff = _text_handoff("return intrin<_mm_add_epi32>(left, right);")
    other_handoff = _text_handoff("return intrin<_mm_sub_epi32>(left, right);")
    extra_call = _rendered_direct_call(_request_segments(other_handoff)[0])

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (extra_call,))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-BODY-TOKENS-EXTRA-INTRINSIC-CALL",
        "TSL-CPP-BODY-TOKENS-MISSING-INTRINSIC-CALL",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == extra_call.source


def test_m215_diagnoses_duplicate_rendered_call_for_request_segment() -> None:
    handoff = _text_handoff("return intrin<_mm_add_epi32>(left, right);")
    call = _rendered_direct_call(_request_segments(handoff)[0])

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call, call))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-BODY-TOKENS-DUPLICATE-INTRINSIC-CALL",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == call.source


def test_m215_diagnoses_backend_mismatched_rendered_call() -> None:
    handoff = _text_handoff("return intrin<_mm_add_epi32>(left, right);")
    segment = _request_segments(handoff)[0]
    assembly = assemble_backend_intrinsic_invocation(segment.request, "rust")
    assert assembly.diagnostics == ()
    assert isinstance(assembly.invocation, BackendDirectIntrinsicInvocation)
    mismatched_call = CppRenderedIntrinsicCall(
        invocation=assembly.invocation,
        call_text=CppIntrinsicCallText("_mm_add_epi32(left, right)"),
        immediates=(),
        source=assembly.invocation.source,
    )

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (mismatched_call,))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-BODY-TOKENS-BACKEND-MISMATCH",
        "TSL-CPP-BODY-TOKENS-MISSING-INTRINSIC-CALL",
    )
    assert result.diagnostics[0].severity == "error"
    assert "'rust'" in result.diagnostics[0].message


def test_m215_diagnoses_opaque_nonrenderable_token_segments() -> None:
    hidden_directive = LowerableDirective(
        name="if",
        arguments=("generation", "condition"),
        source=_location(),
    )
    body = ImplementationBody(
        tokens=(
            hidden_directive,
            RawStringToken(" intrin<_mm_add_epi32>(left, right)", _location()),
        ),
        source=_location(),
    )
    handoff = _body_handoff(body)
    call = _rendered_direct_call(_request_segments(handoff)[0])

    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, (call,))

    assert result.body is None
    assert _codes(result.diagnostics) == (
        "TSL-CPP-BODY-TOKENS-UNSUPPORTED-OPAQUE-TOKEN-SEGMENT",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == hidden_directive.source


def test_m215_public_cpp_backend_imports_are_available() -> None:
    from tslgen.backends.cpp import (  # noqa: PLC0415
        CppBodyText,
        CppBodyTokenRenderResult,
        CppRenderedBodyTokens,
        render_cpp_body_tokens_from_intrinsic_handoff,
    )

    assert CppBodyText("return x;") == "return x;"
    assert CppBodyTokenRenderResult.__name__ == "CppBodyTokenRenderResult"
    assert CppRenderedBodyTokens.__name__ == "CppRenderedBodyTokens"
    assert callable(render_cpp_body_tokens_from_intrinsic_handoff)


def _text_handoff(text: str) -> BackendIntrinsicHandoff:
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_intrinsic_discovery(
        _selected(),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _body_handoff(body: ImplementationBody) -> BackendIntrinsicHandoff:
    selected = _selected(body)
    lowerer = Lowerer()
    discovery = lowerer.discover_backend_intrinsic_requests(selected)
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = lowerer.lower_backend_intrinsic_discovery(selected, discovery.discovery)
    assert result.diagnostics == ()
    assert result.handoff is not None
    return result.handoff


def _rendered_direct_call(
    segment: BackendIntrinsicHandoffRequestSegment,
    *,
    backend: str = "cpp",
) -> CppRenderedIntrinsicCall:
    assembly = assemble_backend_intrinsic_invocation(segment.request, backend)
    assert assembly.diagnostics == ()
    assert isinstance(assembly.invocation, BackendDirectIntrinsicInvocation)
    result = render_cpp_intrinsic_invocation_call(assembly.invocation)
    assert result.diagnostics == ()
    assert result.call is not None
    return result.call


def _rendered_composed_call(
    segment: BackendIntrinsicHandoffRequestSegment,
    translated_values: tuple[tuple[str, object], ...],
    *,
    backend: str = "cpp",
) -> CppRenderedIntrinsicCall:
    request = segment.request
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    translations = tuple(
        _translated(_field(request, name), value, backend=backend)
        for name, value in translated_values
    )
    assembly = assemble_backend_intrinsic_invocation(request, backend, translations)
    assert assembly.diagnostics == ()
    assert isinstance(assembly.invocation, BackendComposedIntrinsicInvocation)
    result = render_cpp_intrinsic_invocation_call(assembly.invocation)
    assert result.diagnostics == ()
    assert result.call is not None
    return result.call


def _request_segments(
    handoff: BackendIntrinsicHandoff,
) -> tuple[BackendIntrinsicHandoffRequestSegment, ...]:
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    )


def _selected(body: ImplementationBody | None = None) -> SelectedImplementation:
    source = _location()
    implementation_body = body or ImplementationBody(tokens=(), source=source)
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=implementation_body,
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="unknown",
        implementations=(implementation,),
        source=source,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _translated(
    field: BackendIntrinsicModifierField,
    value,
    *,
    backend: str = "cpp",
) -> BackendTranslatedIntrinsicModifier:
    return BackendTranslatedIntrinsicModifier(
        backend=BackendId(backend),
        field=field,
        name=field.name,
        value=value,
        source=field.source,
    )


def _field(
    request: BackendIntrinsicComposeHandoffRequest,
    name: str,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == name)
    assert len(matches) == 1
    return matches[0]


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
