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
    BackendTypeQueryOpaqueTextSegment,
    BackendTypeQueryOpaqueTokenSegment,
    BackendTypeQueryRequestIslandSegment,
    BackendTypeSpellingRequest,
    CurrentVector,
    Lowerer,
    discover_backend_type_queries_in_text,
)


def test_m179_discovers_backend_type_query_in_source_text() -> None:
    result = discover_backend_type_queries_in_text(
        "type<backend>(size_t)",
        _location(),
    )

    request = _single_request(result)

    assert request.payload_text == "size_t"
    assert request.source_text == "type<backend>(size_t)"
    assert request.source == _location()
    assert request.payload_source == _location(column=len("type<backend>(") + 1)


def test_m179_discovers_backend_type_query_inside_raw_body_tokens() -> None:
    hidden_query_directive = LowerableDirective(
        name="let",
        arguments=("type", "Hidden, type<backend>(scalar::ui64)"),
        source=_location(column=40),
    )
    tokens = (
        _raw("prefix ", column=1),
        hidden_query_directive,
        _raw("type<backend>(scalar::ui8) suffix", column=80),
    )

    result = Lowerer().discover_backend_type_queries(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 3
    assert isinstance(result.discovery.segments[0], BackendTypeQueryOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], hidden_query_directive)
    assert isinstance(result.discovery.segments[1], BackendTypeQueryRequestIslandSegment)
    assert result.discovery.segments[1].request.payload_text == "scalar::ui8"
    assert isinstance(result.discovery.segments[2], BackendTypeQueryOpaqueTextSegment)
    assert result.discovery.segments[2].text == " suffix"


def test_m179_discovers_multiple_backend_type_queries_in_source_order() -> None:
    text = (
        "pre type<backend>(size_t) mid "
        "type<backend>(vector::as_extension(scalar)) post"
    )

    result = discover_backend_type_queries_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], BackendTypeQueryOpaqueTextSegment)
    assert isinstance(result.discovery.segments[1], BackendTypeQueryRequestIslandSegment)
    assert isinstance(result.discovery.segments[2], BackendTypeQueryOpaqueTextSegment)
    assert isinstance(result.discovery.segments[3], BackendTypeQueryRequestIslandSegment)
    assert isinstance(result.discovery.segments[4], BackendTypeQueryOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert result.discovery.segments[1].request.payload_text == "size_t"
    assert result.discovery.segments[2].text == " mid "
    assert (
        result.discovery.segments[3].request.payload_text
        == "vector::as_extension(scalar)"
    )
    assert result.discovery.segments[4].text == " post"


def test_m179_preserves_nested_balanced_payload_opaque() -> None:
    result = discover_backend_type_queries_in_text(
        "type<backend>(vector::as_extension(scalar))",
        _location(),
    )

    request = _single_request(result)

    assert request.payload_text == "vector::as_extension(scalar)"
    assert request.source_text == "type<backend>(vector::as_extension(scalar))"


def test_m179_preserves_payload_without_backend_translation_or_source_repair() -> None:
    payload = (
        "vector::as_extension(call<primitive=pick[Vec]>("
        '"literal ) text", type<generation>(base::in)))'
    )

    result = discover_backend_type_queries_in_text(
        f"type<backend>({payload})",
        _location(),
    )

    request = _single_request(result)

    assert request.payload_text == payload
    assert isinstance(request, BackendTypeSpellingRequest) is False
    assert not hasattr(request, "backend")
    assert not hasattr(request, "value")


def test_m179_discovers_backend_type_query_split_across_contiguous_raw_tokens() -> None:
    tokens = (
        _raw("cast<static>(", line=1, column=1),
        _raw("type<backend>(", line=2, column=3),
        _raw("scalar::ui64", line=3, column=5),
        _raw("), 0)", line=4, column=7),
    )

    result = Lowerer().discover_backend_type_queries(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 3
    assert isinstance(result.discovery.segments[0], BackendTypeQueryOpaqueTextSegment)
    assert result.discovery.segments[0].text == "cast<static>("
    assert isinstance(result.discovery.segments[1], BackendTypeQueryRequestIslandSegment)
    request = result.discovery.segments[1].request
    assert request.payload_text == "scalar::ui64"
    assert request.payload_source == _location(line=3, column=5)
    assert request.source == _location(line=2, column=3)
    assert isinstance(result.discovery.segments[2], BackendTypeQueryOpaqueTextSegment)
    assert result.discovery.segments[2].text == ", 0)"


@pytest.mark.parametrize(
    "text",
    (
        "type<backend>(size_t",
        "prefix type<backend>(vector::as_extension(scalar)",
    ),
)
def test_m179_reports_malformed_outer_backend_type_query(text: str) -> None:
    result = discover_backend_type_queries_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("type<backend>(") + 1
    )
    assert "unbalanced outer payload" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY",)


@pytest.mark.parametrize(
    "text",
    (
        "type<generation>(base::in)",
        "mytype<backend>(size_t)",
        "value<backend>(intrin::suffix)",
    ),
)
def test_m179_reports_no_backend_type_query_when_requested_for_text(text: str) -> None:
    result = discover_backend_type_queries_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-TYPE-QUERY",)


def test_m179_reports_no_backend_type_query_when_requested_for_body_tokens() -> None:
    result = Lowerer().discover_backend_type_queries(
        _selected(ImplementationBody(tokens=(_raw("return result;"),), source=_location()))
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-TYPE-QUERY",)


def test_m179_preserves_existing_lower_backend_type_query_semantics() -> None:
    source = _location(3, 7)
    selected = _selected(ImplementationBody(tokens=(), source=source))

    result = Lowerer().lower_backend_type_query(
        selected,
        "type<backend>(Vec)",
        source,
    )

    assert result.diagnostics == ()
    assert result.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=CurrentVector(extension="generic", type_tag="si32"),
        source_text="type<backend>(Vec)",
        source=source,
    )


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, BackendTypeQueryRequestIslandSegment)
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
