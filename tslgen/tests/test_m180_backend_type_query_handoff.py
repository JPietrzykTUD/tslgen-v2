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
    BackendTypeQueryDiscovery,
    BackendTypeQueryHandoffRequestSegment,
    BackendTypeQueryOpaqueTextSegment,
    BackendTypeQueryOpaqueTokenSegment,
    BackendTypeQueryRequestIslandSegment,
    BackendTypeSpellingRequest,
    CurrentVector,
    LoweredCurrentScalarType,
    LoweredIntrinsicVectorImaskType,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
    LoweredVectorAsExtensionType,
    Lowerer,
    discover_backend_type_queries_in_text,
    lower_backend_type_query_discovery,
)


def test_m180_lowers_text_discovered_island_to_backend_type_request() -> None:
    discovery = _text_discovery("type<backend>(size_t)")
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = lower_backend_type_query_discovery(
        Lowerer().context_for(selected),
        discovery,
    )

    segment = _single_handoff_request(result)
    assert segment.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredSizeType(),
        source_text="type<backend>(size_t)",
        source=_location(),
    )
    assert segment.island.payload_text == "size_t"
    assert segment.island.source_text == "type<backend>(size_t)"


def test_m180_lowers_body_discovery_preserving_opaque_tokens_and_text() -> None:
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
    selected = _selected(ImplementationBody(tokens=tokens, source=_location()))
    lowerer = Lowerer()
    discovery_result = lowerer.discover_backend_type_queries(selected)
    assert discovery_result.diagnostics == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_backend_type_query_discovery(
        selected,
        discovery_result.discovery,
    )

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 3
    assert result.handoff.segments[0] is discovery_result.discovery.segments[0]
    assert result.handoff.segments[2] is discovery_result.discovery.segments[2]
    assert isinstance(result.handoff.segments[0], BackendTypeQueryOpaqueTokenSegment)
    assert result.handoff.segments[0].tokens == (tokens[0], hidden_query_directive)
    assert isinstance(result.handoff.segments[1], BackendTypeQueryHandoffRequestSegment)
    assert result.handoff.segments[1].request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredScalarTypeIdentity(type_tag="ui8"),
        source_text="type<backend>(scalar::ui8)",
        source=_location(column=80),
    )
    assert result.handoff.segments[1].island is (
        discovery_result.discovery.segments[1].request
    )
    assert isinstance(result.handoff.segments[2], BackendTypeQueryOpaqueTextSegment)
    assert result.handoff.segments[2].text == " suffix"


def test_m180_lowers_multiple_islands_in_source_order() -> None:
    discovery = _text_discovery(
        "type<backend>(size_t) mid type<backend>(scalar::ui8)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_type_query_discovery(selected, discovery)

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert [
        segment.request.source_text
        for segment in result.handoff.segments
        if isinstance(segment, BackendTypeQueryHandoffRequestSegment)
    ] == ["type<backend>(size_t)", "type<backend>(scalar::ui8)"]
    assert isinstance(result.handoff.segments[1], BackendTypeQueryOpaqueTextSegment)
    assert result.handoff.segments[1].text == " mid "


@pytest.mark.parametrize(
    ("query", "value"),
    (
        ("type<backend>(size_t)", LoweredSizeType()),
        ("type<backend>(scalar::ui8)", LoweredScalarTypeIdentity(type_tag="ui8")),
        ("type<backend>(intrin::vector::imask)", LoweredIntrinsicVectorImaskType()),
        (
            "type<backend>(vector::as_extension(scalar))",
            LoweredVectorAsExtensionType(
                base_type=LoweredCurrentScalarType(type_tag="si32"),
                extension="scalar",
            ),
        ),
        (
            "type<backend>(vector::as_extension(generic))",
            LoweredVectorAsExtensionType(
                base_type=LoweredCurrentScalarType(type_tag="si32"),
                extension="generic",
            ),
        ),
    ),
)
def test_m180_lowers_representative_corpus_backend_type_forms(
    query: str,
    value: object,
) -> None:
    discovery = _text_discovery(query)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_type_query_discovery(selected, discovery)

    assert _single_handoff_request(result).request == BackendTypeSpellingRequest(
        backend="cpp",
        value=value,
        source_text=query,
        source=_location(),
    )


def test_m180_reuses_explicit_alias_environment() -> None:
    alias = LowerableDirective(
        name="let",
        arguments=("type", "AliasVec, Vec"),
        source=_location(line=2, column=3),
    )
    body = ImplementationBody(
        tokens=(alias, _raw("type<backend>(AliasVec)", line=3, column=5)),
        source=_location(),
    )
    selected = _selected(body, extension="avx2", type_tag="si64")
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)
    discovery_result = lowerer.discover_backend_type_queries(selected)
    assert environment.diagnostics == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_backend_type_query_discovery(
        selected,
        discovery_result.discovery,
        environment=environment,
    )

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert isinstance(result.handoff.segments[0], BackendTypeQueryOpaqueTokenSegment)
    segment = result.handoff.segments[1]
    assert isinstance(segment, BackendTypeQueryHandoffRequestSegment)
    assert segment.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=CurrentVector(extension="avx2", type_tag="si64"),
        source_text="type<backend>(AliasVec)",
        source=_location(line=3, column=5),
    )


def test_m180_does_not_infer_aliases_from_surrounding_raw_text() -> None:
    raw = "let<type>(AliasVec, Vec); type<backend>(AliasVec)"
    body = ImplementationBody(tokens=(_raw(raw),), source=_location())
    selected = _selected(body)
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)
    discovery_result = lowerer.discover_backend_type_queries(selected)
    assert environment.alias_bindings == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_backend_type_query_discovery(
        selected,
        discovery_result.discovery,
        environment=environment,
    )

    assert result.handoff is None
    assert _codes(result) == ("TSL-LOWER-UNBOUND-TYPE-ALIAS",)
    assert result.diagnostics[0].location == _location(
        column=raw.index("type<backend>(") + 1
    )


def test_m180_keeps_malformed_islands_at_discovery_boundary() -> None:
    discovery_result = discover_backend_type_queries_in_text(
        "type<backend>(Vec",
        _location(),
    )

    assert discovery_result.discovery is None
    assert _codes(discovery_result) == ("TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY",)
    assert "unbalanced outer payload" in discovery_result.diagnostics[0].message


def test_m180_reports_semantic_type_query_diagnostics_from_island_source() -> None:
    discovery = _text_discovery("type<backend>(unknown::type(Vec))")
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_type_query_discovery(selected, discovery)

    assert result.handoff is None
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-TYPE-EXPRESSION",)
    assert result.diagnostics[0].location == _location()
    assert "unknown::type(Vec)" in result.diagnostics[0].message


def test_m180_keeps_raw_discovery_distinct_until_explicit_handoff() -> None:
    discovery = _text_discovery("type<backend>(scalar::ui64)")
    raw_segment = discovery.segments[0]
    assert isinstance(raw_segment, BackendTypeQueryRequestIslandSegment)
    assert isinstance(raw_segment.request, BackendTypeSpellingRequest) is False
    assert not hasattr(raw_segment.request, "backend")
    assert not hasattr(raw_segment.request, "value")

    selected = _selected(ImplementationBody(tokens=(), source=_location()))
    result = Lowerer().lower_backend_type_query_discovery(selected, discovery)

    handoff_segment = _single_handoff_request(result)
    assert handoff_segment.island is raw_segment.request
    assert handoff_segment.request == BackendTypeSpellingRequest(
        backend="cpp",
        value=LoweredScalarTypeIdentity(type_tag="ui64"),
        source_text="type<backend>(scalar::ui64)",
        source=_location(),
    )
    assert isinstance(handoff_segment.request.value, str) is False
    assert not hasattr(handoff_segment.request, "rendered_text")


def _text_discovery(text: str) -> BackendTypeQueryDiscovery:
    result = discover_backend_type_queries_in_text(text, _location())
    assert result.diagnostics == ()
    assert result.discovery is not None
    return result.discovery


def _single_handoff_request(result) -> BackendTypeQueryHandoffRequestSegment:
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendTypeQueryHandoffRequestSegment)
    return segment


def _selected(
    body: ImplementationBody,
    *,
    backend: str = "cpp",
    extension: str = "generic",
    type_tag: str = "si32",
) -> SelectedImplementation:
    implementation = Implementation(
        extension=extension,
        type_tag=type_tag,
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
        extension=extension,
        type_tag=type_tag,
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
