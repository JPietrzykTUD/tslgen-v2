from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    LowerableDirective,
    LowerableOperationFragment,
    Primitive,
    RawStringToken,
)
from tslgen.lowering import (
    Lowerer,
    SourceOperationOpaqueTextSegment,
    SourceOperationOpaqueTokenSegment,
    SourceOperationRequestSegment,
    discover_source_operation_requests_in_text,
)


def test_m167_discovers_cast_request() -> None:
    result = discover_source_operation_requests_in_text(
        "cast<static>(type<generation>(base::in), value)",
        _location(),
    )

    request = _single_request(result)

    assert request.operation_kind == "cast"
    assert request.angle_payload_text == "static"
    assert request.argument_text == "type<generation>(base::in), value"
    assert request.source_text == "cast<static>(type<generation>(base::in), value)"
    assert request.source == _location()
    assert request.angle_payload_source == _location(column=len("cast<") + 1)
    assert request.argument_source == _location(column=len("cast<static>(") + 1)


def test_m167_discovers_memory_request() -> None:
    text = (
        "mem<copy>(cast<reinterpret>(void*, &bits), "
        "cast<reinterpret>(void const*, &data), "
        "value<generation>(type::size_bytes(type<generation>(base::in))))"
    )

    result = discover_source_operation_requests_in_text(text, _location())

    request = _single_request(result)

    assert request.operation_kind == "mem"
    assert request.angle_payload_text == "copy"
    assert request.argument_text == (
        "cast<reinterpret>(void*, &bits), "
        "cast<reinterpret>(void const*, &data), "
        "value<generation>(type::size_bytes(type<generation>(base::in)))"
    )
    assert request.source_text == text


def test_m167_discovers_io_request() -> None:
    text = (
        "io<write_base>(out, 16, "
        "value<generation>(type::size_bytes(type<generation>(base::in)))*8, "
        "cast<static>(cast_type, arr[idx]))"
    )

    result = discover_source_operation_requests_in_text(text, _location())

    request = _single_request(result)

    assert request.operation_kind == "io"
    assert request.angle_payload_text == "write_base"
    assert request.argument_text == (
        "out, 16, value<generation>(type::size_bytes(type<generation>(base::in)))*8, "
        "cast<static>(cast_type, arr[idx])"
    )
    assert request.source_text == text


@pytest.mark.parametrize(
    ("operation_kind", "angle_payload", "argument_payload"),
    (
        (
            "cast",
            "static",
            (
                "type<generation>(base::signed_of(type<generation>(base::in))), "
                "call<primitive=set1[Vec]>(value)"
            ),
        ),
        (
            "cast",
            "reinterpret",
            "type<backend>(scalar::ui8) *, ptr_add(ptr, i)",
        ),
        (
            "mem",
            "copy",
            (
                "cast<reinterpret>(void*, &bits), "
                "cast<reinterpret>(void const*, &data), "
                "value<generation>(type::size_bytes(type<generation>(base::in)))"
            ),
        ),
        (
            "io",
            "write",
            '"a)b", details::arith_add(left, right) + arr[i]',
        ),
        (
            "io",
            "write_base",
            "out, intrin<svcntp_b8>(pg, mask), mem<copy>(dst, src, n)",
        ),
        (
            "cast",
            "mode=value<backend>(cast::mode(\"x>y\"))",
            '"quoted ) text", intrin_compose<svdup, post=x>(0)',
        ),
    ),
)
def test_m167_preserves_source_operation_payloads_opaque(
    operation_kind: str,
    angle_payload: str,
    argument_payload: str,
) -> None:
    result = discover_source_operation_requests_in_text(
        f"{operation_kind}<{angle_payload}>({argument_payload})",
        _location(),
    )

    request = _single_request(result)

    assert request.operation_kind == operation_kind
    assert request.angle_payload_text == angle_payload
    assert request.argument_text == argument_payload


def test_m167_preserves_prefix_suffix_and_multiple_requests_in_source_order() -> None:
    text = (
        "pre cast<static>(T, x) mid "
        "mem<copy>(dst, src, n) and io<endl>(out) post"
    )

    result = discover_source_operation_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 7
    assert isinstance(result.discovery.segments[0], SourceOperationOpaqueTextSegment)
    assert isinstance(result.discovery.segments[1], SourceOperationRequestSegment)
    assert isinstance(result.discovery.segments[2], SourceOperationOpaqueTextSegment)
    assert isinstance(result.discovery.segments[3], SourceOperationRequestSegment)
    assert isinstance(result.discovery.segments[4], SourceOperationOpaqueTextSegment)
    assert isinstance(result.discovery.segments[5], SourceOperationRequestSegment)
    assert isinstance(result.discovery.segments[6], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert result.discovery.segments[1].request.operation_kind == "cast"
    assert result.discovery.segments[2].text == " mid "
    assert result.discovery.segments[3].request.operation_kind == "mem"
    assert result.discovery.segments[4].text == " and "
    assert result.discovery.segments[5].request.operation_kind == "io"
    assert result.discovery.segments[6].text == " post"


def test_m167_discovers_source_operations_inside_raw_body_tokens_without_context_overfit() -> None:
    hidden_cast_directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, cast<hidden>(T, x)"),
        source=_location(column=20),
    )
    opaque_fragment = LowerableOperationFragment(
        operation="add",
        arguments=("left", "right"),
        source=_location(column=40),
    )
    tokens = (
        _raw("emit_return(", column=1),
        hidden_cast_directive,
        _raw("result[i] = cast<static>(T, arr[i]); ", column=60),
        opaque_fragment,
        _raw("intrin<svst1>(pg, ptr, mem<copy>(dst, src, n));", column=100),
    )

    result = Lowerer().discover_source_operation_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 8
    assert isinstance(result.discovery.segments[0], SourceOperationOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], hidden_cast_directive)
    assert isinstance(result.discovery.segments[1], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[1].text == "result[i] = "
    assert isinstance(result.discovery.segments[2], SourceOperationRequestSegment)
    assert result.discovery.segments[2].request.operation_kind == "cast"
    assert isinstance(result.discovery.segments[3], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[3].text == "; "
    assert isinstance(result.discovery.segments[4], SourceOperationOpaqueTokenSegment)
    assert result.discovery.segments[4].tokens == (opaque_fragment,)
    assert isinstance(result.discovery.segments[5], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[5].text == "intrin<svst1>(pg, ptr, "
    assert isinstance(result.discovery.segments[6], SourceOperationRequestSegment)
    assert result.discovery.segments[6].request.operation_kind == "mem"
    assert result.discovery.segments[6].request.argument_text == "dst, src, n"
    assert isinstance(result.discovery.segments[7], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[7].text == ");"


def test_m167_discovers_source_operation_split_across_contiguous_raw_tokens() -> None:
    tokens = (
        _raw("var<infer>(tmp, ", line=1, column=1),
        _raw("cast<", line=2, column=3),
        _raw("reinterpret>(", line=3, column=5),
        _raw("type<backend>(scalar::ui8) *, ptr", line=4, column=7),
        _raw("))", line=5, column=9),
    )

    result = Lowerer().discover_source_operation_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 3
    assert isinstance(result.discovery.segments[0], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[0].text == "var<infer>(tmp, "
    assert isinstance(result.discovery.segments[1], SourceOperationRequestSegment)
    request = result.discovery.segments[1].request
    assert request.operation_kind == "cast"
    assert request.angle_payload_text == "reinterpret"
    assert request.angle_payload_source == _location(line=3, column=5)
    assert request.argument_text == "type<backend>(scalar::ui8) *, ptr"
    assert request.argument_source == _location(line=4, column=7)
    assert request.source == _location(line=2, column=3)
    assert isinstance(result.discovery.segments[2], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[2].text == ")"


def test_m167_preserves_non_raw_tokens_when_no_source_operation_text_precedes_request() -> None:
    directive = LowerableDirective(
        name="if",
        arguments=("compile", "cast<hidden>(T, x)"),
        source=_location(column=10),
    )

    result = Lowerer().discover_source_operation_requests(
        _selected(
            ImplementationBody(
                tokens=(
                    directive,
                    _raw(" io<write>(out, \"|\")", column=40),
                ),
                source=_location(),
            )
        )
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert isinstance(result.discovery.segments[0], SourceOperationOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (directive,)
    assert isinstance(result.discovery.segments[1], SourceOperationOpaqueTextSegment)
    assert result.discovery.segments[1].text == " "
    assert isinstance(result.discovery.segments[2], SourceOperationRequestSegment)
    assert result.discovery.segments[2].request.operation_kind == "io"


@pytest.mark.parametrize(
    "text",
    (
        "cast<static",
        "cast<>()",
        "cast<static>",
        "mem<copy>(dst, src",
        "prefix io<write>(out, \"value\"",
    ),
)
def test_m167_reports_malformed_outer_source_operation_islands(text: str) -> None:
    result = discover_source_operation_requests_in_text(text, _location())

    first_keyword = min(
        index
        for keyword in ("cast", "mem", "io")
        if (index := text.find(keyword)) != -1
    )
    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(column=first_keyword + 1)
    assert "unbalanced or incomplete outer shape" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-SOURCE-OPERATION",)


@pytest.mark.parametrize(
    "text",
    (
        "details::arith_mul(left, right)",
        "value<backend>(intrin::suffix)",
        "my_cast<not_tsil>(value)",
        "memcpy(dst, src, n)",
        "bio<write>(out)",
    ),
)
def test_m167_reports_no_source_operation_when_requested_for_text(text: str) -> None:
    result = discover_source_operation_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-SOURCE-OPERATION",)


def test_m167_reports_no_source_operation_when_requested_for_body_tokens() -> None:
    result = Lowerer().discover_source_operation_requests(
        _selected(
            ImplementationBody(
                tokens=(
                    _raw("details::arith_mul(left, right)"),
                    LowerableDirective(
                        name="var",
                        arguments=("infer", "tmp, cast<hidden>(T, x)"),
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
    assert _codes(result) == ("TSL-LOWER-NO-SOURCE-OPERATION",)


def test_m167_discovery_is_deterministic() -> None:
    text = (
        "{{cast<static>(T, x)}} "
        "mem<copy>(cast<reinterpret>(void*, dst), src, n) "
        "io<endl>(out)"
    )

    first = discover_source_operation_requests_in_text(text, _location())
    second = discover_source_operation_requests_in_text(text, _location())

    assert first == second


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, SourceOperationRequestSegment)
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
