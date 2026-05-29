from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
    BackendIntrinsicRequestSegment,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)


def test_m166_discovers_direct_intrinsic_request() -> None:
    result = discover_backend_intrinsic_requests_in_text(
        "intrin<_mm512_srl_epi32>(data, shift)",
        _location(),
    )

    request = _single_request(result)

    assert request.intrinsic_kind == "intrin"
    assert request.angle_payload_text == "_mm512_srl_epi32"
    assert request.argument_text == "data, shift"
    assert request.source_text == "intrin<_mm512_srl_epi32>(data, shift)"
    assert request.source == _location()
    assert request.angle_payload_source == _location(column=len("intrin<") + 1)
    assert request.argument_source == _location(
        column=len("intrin<_mm512_srl_epi32>(") + 1
    )


def test_m166_discovers_intrinsic_compose_request() -> None:
    text = (
        "intrin_compose<srli, suffix=value<backend>(intrin::suffix), "
        "immediate(1)=4>(data, 4)"
    )

    result = discover_backend_intrinsic_requests_in_text(text, _location())

    request = _single_request(result)

    assert request.intrinsic_kind == "intrin_compose"
    assert request.angle_payload_text == (
        "srli, suffix=value<backend>(intrin::suffix), immediate(1)=4"
    )
    assert request.argument_text == "data, 4"
    assert request.source_text == text


@pytest.mark.parametrize(
    ("angle_payload", "argument_payload"),
    (
        (
            (
                "add, suffix=value<backend>(intrin::suffix("
                "type<generation>(base::signed_of(type<generation>(base::in)))))"
            ),
            "left, right",
        ),
        ("svadd, post=x", "call<primitive=mask_true[Vec]>(), left, right"),
        (
            "vcvtq infix=value<backend>(intrin::suffix(ToBase))",
            "cast<static>(type<generation>(base::in), data)",
        ),
        ("set1, suffix=value<backend>(intrin::suffix(\"a>b\"))", '"a)b"'),
        ("svsel", "out_pg, packed, intrin_compose<svdup, post=x>(0)"),
        ("direct", "details::arith_add(left, right) + data[i]"),
    ),
)
def test_m166_preserves_intrinsic_payloads_opaque(
    angle_payload: str,
    argument_payload: str,
) -> None:
    result = discover_backend_intrinsic_requests_in_text(
        f"intrin_compose<{angle_payload}>({argument_payload})",
        _location(),
    )

    request = _single_request(result)

    assert request.angle_payload_text == angle_payload
    assert request.argument_text == argument_payload


def test_m166_preserves_prefix_suffix_and_multiple_requests_in_source_order() -> None:
    text = (
        "pre intrin<svptrue_b8>() mid "
        "intrin_compose<svst1>(pg, ptr, data) post"
    )

    result = discover_backend_intrinsic_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], BackendIntrinsicOpaqueTextSegment)
    assert isinstance(result.discovery.segments[1], BackendIntrinsicRequestSegment)
    assert isinstance(result.discovery.segments[2], BackendIntrinsicOpaqueTextSegment)
    assert isinstance(result.discovery.segments[3], BackendIntrinsicRequestSegment)
    assert isinstance(result.discovery.segments[4], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert result.discovery.segments[1].request.intrinsic_kind == "intrin"
    assert result.discovery.segments[2].text == " mid "
    assert result.discovery.segments[3].request.intrinsic_kind == "intrin_compose"
    assert result.discovery.segments[4].text == " post"


def test_m166_discovers_intrinsics_inside_raw_body_tokens_without_context_overfit() -> None:
    hidden_intrinsic_directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, intrin<hidden>()"),
        source=_location(column=20),
    )
    tokens = (
        _raw("result[i] = ", column=1),
        hidden_intrinsic_directive,
        _raw(
            "intrin<svld1>(pg, ptr_add(ptr, i)); "
            "emit_return(intrin_compose<svdup>(0));",
            column=60,
        ),
    )

    result = Lowerer().discover_backend_intrinsic_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], BackendIntrinsicOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], hidden_intrinsic_directive)
    assert isinstance(result.discovery.segments[1], BackendIntrinsicRequestSegment)
    assert result.discovery.segments[1].request.angle_payload_text == "svld1"
    assert isinstance(result.discovery.segments[2], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[2].text == "; emit_return("
    assert isinstance(result.discovery.segments[3], BackendIntrinsicRequestSegment)
    assert result.discovery.segments[3].request.angle_payload_text == "svdup"
    assert isinstance(result.discovery.segments[4], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[4].text == ");"


def test_m166_discovers_intrinsic_split_across_contiguous_raw_tokens() -> None:
    tokens = (
        _raw("emit_return(", line=1, column=1),
        _raw("intrin_compose<", line=2, column=3),
        _raw("svadd, post=x>(", line=3, column=5),
        _raw("call<primitive=mask_true[Vec]>(), data", line=4, column=7),
        _raw("));", line=5, column=9),
    )

    result = Lowerer().discover_backend_intrinsic_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 3
    assert isinstance(result.discovery.segments[0], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[0].text == "emit_return("
    assert isinstance(result.discovery.segments[1], BackendIntrinsicRequestSegment)
    request = result.discovery.segments[1].request
    assert request.intrinsic_kind == "intrin_compose"
    assert request.angle_payload_text == "svadd, post=x"
    assert request.angle_payload_source == _location(line=3, column=5)
    assert request.argument_text == "call<primitive=mask_true[Vec]>(), data"
    assert request.argument_source == _location(line=4, column=7)
    assert request.source == _location(line=2, column=3)
    assert isinstance(result.discovery.segments[2], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[2].text == ");"


def test_m166_preserves_non_raw_tokens_when_no_intrinsic_text_precedes_request() -> None:
    directive = LowerableDirective(
        name="if",
        arguments=("compile", "intrin<hidden>()"),
        source=_location(column=10),
    )

    result = Lowerer().discover_backend_intrinsic_requests(
        _selected(
            ImplementationBody(
                tokens=(
                    directive,
                    _raw(" intrin_compose<svcnt, post=x>(pg, data)", column=40),
                ),
                source=_location(),
            )
        )
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert isinstance(result.discovery.segments[0], BackendIntrinsicOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (directive,)
    assert isinstance(result.discovery.segments[1], BackendIntrinsicOpaqueTextSegment)
    assert result.discovery.segments[1].text == " "
    assert isinstance(result.discovery.segments[2], BackendIntrinsicRequestSegment)
    assert result.discovery.segments[2].request.angle_payload_text == "svcnt, post=x"


@pytest.mark.parametrize(
    "text",
    (
        "intrin<_mm_add",
        "intrin<>()",
        "intrin<svptrue_b8>",
        "intrin<svld1>(pg, ptr",
        "prefix intrin_compose<svadd, post=x>(pg, data",
    ),
)
def test_m166_reports_malformed_outer_intrinsic_islands(text: str) -> None:
    result = discover_backend_intrinsic_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("intrin") + 1
    )
    assert "unbalanced or incomplete outer shape" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-INTRINSIC",)


@pytest.mark.parametrize(
    "text",
    (
        "details::arith_mul(left, right)",
        "value<backend>(intrin::suffix)",
        "my_intrin<not_tsil>(value)",
        "intrinsic<not_tsil>(value)",
    ),
)
def test_m166_reports_no_intrinsic_when_requested_for_text(text: str) -> None:
    result = discover_backend_intrinsic_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-INTRINSIC",)


def test_m166_reports_no_intrinsic_when_requested_for_body_tokens() -> None:
    result = Lowerer().discover_backend_intrinsic_requests(
        _selected(
            ImplementationBody(
                tokens=(
                    _raw("details::arith_mul(left, right)"),
                    LowerableDirective(
                        name="var",
                        arguments=("infer", "tmp, intrin<hidden>()"),
                        source=_location(column=30),
                    ),
                ),
                source=_location(),
            )
        )
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-INTRINSIC",)


def test_m166_discovery_is_deterministic() -> None:
    text = (
        "{{intrin<svptrue_b8>()}} "
        "intrin_compose<svcnt, post=x>(call<primitive=mask_true[Vec]>(), data)"
    )

    first = discover_backend_intrinsic_requests_in_text(text, _location())
    second = discover_backend_intrinsic_requests_in_text(text, _location())

    assert first == second


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, BackendIntrinsicRequestSegment)
    return segment.request


def _selected(body: ImplementationBody) -> SelectedImplementation:
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


def _raw(
    text: str,
    *,
    line: int = 1,
    column: int = 1,
) -> RawStringToken:
    return RawStringToken(text=text, source=_location(line, column))


def _codes(result) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in result.diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
