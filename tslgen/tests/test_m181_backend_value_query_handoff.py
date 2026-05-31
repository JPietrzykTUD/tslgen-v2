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
    BackendConstantValueRequest,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendUninitValueRequest,
    BackendValueQueryDiscovery,
    BackendValueQueryHandoffRequestSegment,
    BackendValueQueryOpaqueTextSegment,
    BackendValueQueryOpaqueTokenSegment,
    BackendValueQueryRequestSegment,
    BackendValueStringLiteralOperand,
    BackendValueSymbolOperand,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
    Lowerer,
    discover_backend_value_queries_in_text,
    lower_backend_value_query_discovery,
)

_ARG_LOCATION = SourceLocation(Path("fixture.tsl"), 1, 31)


def test_m181_lowers_all_observed_payload_families_from_text() -> None:
    discovery = _text_discovery(
        "value<backend>(intrin::suffix) "
        "value<backend>(intrin::prefix) "
        "value<backend>(uninit::array) "
        "value<backend>(uninit::scalar) "
        "value<backend>(x86::mm_fround_to_zero)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = lower_backend_value_query_discovery(
        Lowerer().context_for(selected),
        discovery,
    )

    requests = _handoff_requests(result)
    assert requests == (
        BackendIntrinsicSuffixValueRequest(
            backend="cpp",
            argument=None,
            source_text="value<backend>(intrin::suffix)",
            source=_location(),
        ),
        BackendIntrinsicPrefixValueRequest(
            backend="cpp",
            source_text="value<backend>(intrin::prefix)",
            source=_location(column=32),
        ),
        BackendUninitValueRequest(
            backend="cpp",
            kind="array",
            source_text="value<backend>(uninit::array)",
            source=_location(column=63),
        ),
        BackendUninitValueRequest(
            backend="cpp",
            kind="scalar",
            source_text="value<backend>(uninit::scalar)",
            source=_location(column=93),
        ),
        BackendConstantValueRequest(
            backend="cpp",
            name="x86::mm_fround_to_zero",
            source_text="value<backend>(x86::mm_fround_to_zero)",
            source=_location(column=124),
        ),
    )


def test_m181_lowers_body_discovery_preserving_opaque_tokens_and_text() -> None:
    hidden_query_directive = LowerableDirective(
        name="var",
        arguments=("typed", "Type, hidden, value<backend>(uninit::scalar)"),
        source=_location(column=40),
    )
    tokens = (
        _raw("prefix ", column=1),
        hidden_query_directive,
        _raw("value<backend>(uninit::array) suffix", column=80),
    )
    selected = _selected(ImplementationBody(tokens=tokens, source=_location()))
    lowerer = Lowerer()
    discovery_result = lowerer.discover_backend_value_queries(selected)
    assert discovery_result.diagnostics == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_backend_value_query_discovery(
        selected,
        discovery_result.discovery,
    )

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 3
    assert result.handoff.segments[0] is discovery_result.discovery.segments[0]
    assert result.handoff.segments[2] is discovery_result.discovery.segments[2]
    assert isinstance(result.handoff.segments[0], BackendValueQueryOpaqueTokenSegment)
    assert result.handoff.segments[0].tokens == (tokens[0], hidden_query_directive)
    assert isinstance(result.handoff.segments[1], BackendValueQueryHandoffRequestSegment)
    assert result.handoff.segments[1].request == BackendUninitValueRequest(
        backend="cpp",
        kind="array",
        source_text="value<backend>(uninit::array)",
        source=_location(column=80),
    )
    assert result.handoff.segments[1].island is (
        discovery_result.discovery.segments[1].request
    )
    assert isinstance(result.handoff.segments[2], BackendValueQueryOpaqueTextSegment)
    assert result.handoff.segments[2].text == " suffix"


def test_m181_lowers_multiple_islands_in_source_order() -> None:
    discovery = _text_discovery(
        "value<backend>(uninit::scalar) mid value<backend>(intrin::prefix)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_value_query_discovery(selected, discovery)

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert [
        segment.request.source_text
        for segment in result.handoff.segments
        if isinstance(segment, BackendValueQueryHandoffRequestSegment)
    ] == ["value<backend>(uninit::scalar)", "value<backend>(intrin::prefix)"]
    assert isinstance(result.handoff.segments[1], BackendValueQueryOpaqueTextSegment)
    assert result.handoff.segments[1].text == " mid "


@pytest.mark.parametrize(
    ("query", "expected_argument"),
    (
        ("value<backend>(intrin::suffix)", None),
        (
            (
                "value<backend>(intrin::suffix(type<generation>("
                "base::signed_of(type<generation>(base::in)))))"
            ),
            BackendValueTypeOperand(
                value=LoweredScalarTypeIdentity(type_tag="si32"),
                source_text=(
                    "type<generation>(base::signed_of("
                    "type<generation>(base::in)))"
                ),
                source=_ARG_LOCATION,
            ),
        ),
        (
            'value<backend>(intrin::suffix("stream"))',
            BackendValueStringLiteralOperand(
                value="stream",
                source_text='"stream"',
                source=_ARG_LOCATION,
            ),
        ),
        (
            "value<backend>(intrin::suffix(ToBase))",
            BackendValueSymbolOperand(text="ToBase", source=_ARG_LOCATION),
        ),
        (
            "value<backend>(intrin::suffix(si32))",
            BackendValueTypeOperand(
                value=LoweredScalarTypeIdentity(type_tag="si32"),
                source_text="si32",
                source=_ARG_LOCATION,
            ),
        ),
        (
            "value<backend>(intrin::suffix(si64))",
            BackendValueTypeOperand(
                value=LoweredScalarTypeIdentity(type_tag="si64"),
                source_text="si64",
                source=_ARG_LOCATION,
            ),
        ),
        (
            "value<backend>(intrin::suffix(si?))",
            BackendValueSymbolOperand(text="si?", source=_ARG_LOCATION),
        ),
    ),
)
def test_m181_lowers_suffix_argument_variants(
    query: str,
    expected_argument: object,
) -> None:
    discovery = _text_discovery(query)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_value_query_discovery(selected, discovery)
    ).request

    assert request == BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=expected_argument,
        source_text=query,
        source=_location(),
    )


@pytest.mark.parametrize(
    ("query", "code"),
    (
        (
            "value<backend>(intrin::unknown)",
            "TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        ),
        (
            "value<backend>(intrin::suffix(left, right))",
            "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY-PAYLOAD",
        ),
        (
            "value<backend>(intrin::prefix(stream))",
            "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY-PAYLOAD",
        ),
        (
            'value<backend>(intrin::suffix("bad\\x"))',
            "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY-PAYLOAD",
        ),
        (
            'value<backend>(intrin::suffix("other"))',
            "TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        ),
        (
            'value<backend>(intrin::suffix("str\\145am"))',
            "TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        ),
        (
            "value<backend>(intrin::suffix(call<primitive=set1>(x)))",
            "TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        ),
    ),
)
def test_m181_reports_unsupported_and_malformed_payloads(
    query: str,
    code: str,
) -> None:
    discovery = _text_discovery(query)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_value_query_discovery(selected, discovery)

    assert result.handoff is None
    assert _codes(result) == (code,)
    assert result.diagnostics[0].severity == "error"


def test_m181_keeps_malformed_outer_islands_at_discovery_boundary() -> None:
    discovery_result = discover_backend_value_queries_in_text(
        "value<backend>(intrin::suffix(",
        _location(),
    )

    assert discovery_result.discovery is None
    assert _codes(discovery_result) == ("TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",)
    assert "unbalanced outer payload" in discovery_result.diagnostics[0].message


def test_m181_keeps_raw_discovery_distinct_until_explicit_handoff() -> None:
    discovery = _text_discovery("value<backend>(uninit::array)")
    raw_segment = discovery.segments[0]
    assert isinstance(raw_segment, BackendValueQueryRequestSegment)
    assert isinstance(raw_segment.request, BackendUninitValueRequest) is False
    assert not hasattr(raw_segment.request, "backend")
    assert not hasattr(raw_segment.request, "kind")

    selected = _selected(ImplementationBody(tokens=(), source=_location()))
    result = Lowerer().lower_backend_value_query_discovery(selected, discovery)

    handoff_segment = _single_handoff_request(result)
    assert handoff_segment.island is raw_segment.request
    assert handoff_segment.request == BackendUninitValueRequest(
        backend="cpp",
        kind="array",
        source_text="value<backend>(uninit::array)",
        source=_location(),
    )
    assert not hasattr(handoff_segment.request, "rendered_text")


def _text_discovery(text: str) -> BackendValueQueryDiscovery:
    result = discover_backend_value_queries_in_text(text, _location())
    assert result.diagnostics == ()
    assert result.discovery is not None
    return result.discovery


def _single_handoff_request(result) -> BackendValueQueryHandoffRequestSegment:
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendValueQueryHandoffRequestSegment)
    return segment


def _handoff_requests(result) -> tuple[object, ...]:
    assert result.diagnostics == ()
    assert result.handoff is not None
    return tuple(
        segment.request
        for segment in result.handoff.segments
        if isinstance(segment, BackendValueQueryHandoffRequestSegment)
    )


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
