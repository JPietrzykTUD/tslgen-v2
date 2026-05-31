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
    BackendValueQueryOpaqueTextSegment,
    BackendValueQueryOpaqueTokenSegment,
    BackendValueQueryRequestSegment,
    GenerationVariableDeclarationText,
    Lowerer,
    discover_backend_value_queries_in_text,
)


@pytest.mark.parametrize(
    "query",
    (
        "uninit::array",
        "uninit::scalar",
    ),
)
def test_m164_discovers_backend_uninit_value_queries(query: str) -> None:
    result = discover_backend_value_queries_in_text(
        f"value<backend>({query})",
        _location(),
    )

    request = _single_request(result)

    assert request.query_text == query
    assert request.source_text == f"value<backend>({query})"
    assert request.source == _location()
    assert request.query_source == _location(1, len("value<backend>(") + 1)


@pytest.mark.parametrize(
    "query",
    (
        (
            "intrin::suffix(type<generation>("
            "base::signed_of(type<generation>(base::in))))"
        ),
        "intrin::suffix",
        "intrin::prefix",
        'intrin::suffix("stream")',
        'intrin::suffix("a)b")',
        r'intrin::suffix("a\" ) b")',
        "x86::mm_fround_to_zero",
    ),
)
def test_m164_preserves_intrinsic_backend_query_payloads_opaque(query: str) -> None:
    result = discover_backend_value_queries_in_text(
        f"value<backend>({query})",
        _location(),
    )

    request = _single_request(result)

    assert request.query_text == query


def test_m164_preserves_nested_delimiter_payload_without_backend_evaluation() -> None:
    query = (
        "intrin::suffix(call<primitive=cast[Vec, "
        "type<backend>(vector::as_extension(scalar))]>("
        "type<generation>(base::unsigned_of(type<generation>(base::in)))))"
    )

    result = discover_backend_value_queries_in_text(
        f"value<backend>({query})",
        _location(),
    )

    request = _single_request(result)

    assert request.query_text == query


def test_m164_preserves_prefix_suffix_and_multiple_queries_in_source_order() -> None:
    text = (
        "pre value<backend>(intrin::suffix) mid "
        "value<backend>(intrin::prefix) post"
    )

    result = discover_backend_value_queries_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], BackendValueQueryOpaqueTextSegment)
    assert isinstance(result.discovery.segments[1], BackendValueQueryRequestSegment)
    assert isinstance(result.discovery.segments[2], BackendValueQueryOpaqueTextSegment)
    assert isinstance(result.discovery.segments[3], BackendValueQueryRequestSegment)
    assert isinstance(result.discovery.segments[4], BackendValueQueryOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert result.discovery.segments[1].request.query_text == "intrin::suffix"
    assert result.discovery.segments[2].text == " mid "
    assert result.discovery.segments[3].request.query_text == "intrin::prefix"
    assert result.discovery.segments[4].text == " post"


def test_m164_discovers_queries_inside_raw_body_tokens() -> None:
    hidden_query_directive = LowerableDirective(
        name="var",
        arguments=("typed", "Type, hidden, value<backend>(uninit::scalar)"),
        source=_location(column=50),
    )
    tokens = (
        _raw("prefix ", column=1),
        hidden_query_directive,
        _raw("value<backend>(uninit::array) suffix", column=80),
    )

    result = Lowerer().discover_backend_value_queries(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 3
    assert isinstance(result.discovery.segments[0], BackendValueQueryOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], tokens[1])
    assert isinstance(result.discovery.segments[1], BackendValueQueryRequestSegment)
    assert result.discovery.segments[1].request.query_text == "uninit::array"
    assert isinstance(result.discovery.segments[2], BackendValueQueryOpaqueTextSegment)
    assert result.discovery.segments[2].text == " suffix"


def test_m178_preserves_m164_per_raw_token_backend_value_boundary() -> None:
    tokens = (
        _raw("value<backend>(", line=1, column=3),
        _raw("uninit::array)", line=2, column=5),
    )

    result = Lowerer().discover_backend_value_queries(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(line=1, column=3)
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",)


def test_m164_text_helper_works_for_m163_style_declaration_text() -> None:
    declaration_text = GenerationVariableDeclarationText(
        text="value<backend>(uninit::array)",
        source=_location(3, 11),
    )

    result = discover_backend_value_queries_in_text(
        declaration_text.text,
        declaration_text.source,
    )

    request = _single_request(result)

    assert request.query_text == "uninit::array"
    assert request.source == declaration_text.source


@pytest.mark.parametrize(
    "text",
    (
        "value<backend>(intrin::suffix(",
        "prefix value<backend>(uninit::array",
    ),
)
def test_m164_reports_malformed_outer_query(text: str) -> None:
    result = discover_backend_value_queries_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("value<backend>(") + 1
    )
    assert "unbalanced outer payload" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",)


def test_m164_reports_no_query_when_requested_for_text() -> None:
    result = discover_backend_value_queries_in_text(
        "value<generation>(vector::length)",
        _location(),
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-VALUE-QUERY",)


def test_m164_reports_no_query_when_requested_for_body_tokens() -> None:
    result = Lowerer().discover_backend_value_queries(
        _selected(ImplementationBody(tokens=(_raw("return result;"),), source=_location()))
    )

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-VALUE-QUERY",)


def test_m164_discovery_is_deterministic() -> None:
    text = (
        "{{value<backend>(intrin::suffix)}} "
        "value<backend>(intrin::suffix(type<generation>(base::in)))"
    )

    first = discover_backend_value_queries_in_text(text, _location())
    second = discover_backend_value_queries_in_text(text, _location())

    assert first == second


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, BackendValueQueryRequestSegment)
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
