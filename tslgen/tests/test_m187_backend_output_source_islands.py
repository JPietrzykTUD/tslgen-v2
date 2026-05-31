from dataclasses import fields
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
    BackendOutputOpaqueTextSegment,
    BackendOutputOpaqueTokenSegment,
    BackendOutputRequest,
    BackendOutputRequestKind,
    BackendOutputRequestSegment,
    Lowerer,
    discover_backend_output_requests_in_text,
)


def test_m187_discovers_all_backend_output_islands_in_source_order() -> None:
    text = (
        "load(assume_aligned<value<generation>(vector::alignment)>(ptr)); "
        "var<typed>(array_type<type<generation>(base::in), "
        "value<generation>(vector::length)>, tmp, "
        "value<backend>(uninit::array)); "
        "emit_return(pack<first>(args...));"
    )

    result = discover_backend_output_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 7
    assert isinstance(result.discovery.segments[0], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[0].text == "load("
    assert isinstance(result.discovery.segments[1], BackendOutputRequestSegment)
    assert result.discovery.segments[1].request.kind is (
        BackendOutputRequestKind.ASSUME_ALIGNED
    )
    assert result.discovery.segments[1].request.angle_payload_text == (
        "value<generation>(vector::alignment)"
    )
    assert result.discovery.segments[1].request.argument_text == "ptr"
    assert isinstance(result.discovery.segments[2], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[2].text == "); var<typed>("
    assert isinstance(result.discovery.segments[3], BackendOutputRequestSegment)
    assert result.discovery.segments[3].request.kind is BackendOutputRequestKind.ARRAY_TYPE
    assert result.discovery.segments[3].request.angle_payload_text == (
        "type<generation>(base::in), value<generation>(vector::length)"
    )
    assert result.discovery.segments[3].request.argument_text is None
    assert result.discovery.segments[3].request.argument_source is None
    assert isinstance(result.discovery.segments[4], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[4].text == (
        ", tmp, value<backend>(uninit::array)); emit_return("
    )
    assert isinstance(result.discovery.segments[5], BackendOutputRequestSegment)
    assert result.discovery.segments[5].request.kind is BackendOutputRequestKind.PACK
    assert result.discovery.segments[5].request.angle_payload_text == "first"
    assert result.discovery.segments[5].request.argument_text == "args..."
    assert isinstance(result.discovery.segments[6], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[6].text == ");"


@pytest.mark.parametrize(
    ("text", "kind", "angle_payload", "argument_payload"),
    (
        (
            "assume_aligned<value<generation>(vector::alignment)>(tmp.data())",
            BackendOutputRequestKind.ASSUME_ALIGNED,
            "value<generation>(vector::alignment)",
            "tmp.data()",
        ),
        (
            "array_type<type<generation>(base::in), "
            "value<generation>(vector::length), "
            "value<generation>(vector::alignment)>",
            BackendOutputRequestKind.ARRAY_TYPE,
            (
                "type<generation>(base::in), "
                "value<generation>(vector::length), "
                "value<generation>(vector::alignment)"
            ),
            None,
        ),
        (
            'pack<first>(intrin<svdup>("not ) close"), mask<zero>())',
            BackendOutputRequestKind.PACK,
            "first",
            'intrin<svdup>("not ) close"), mask<zero>()',
        ),
    ),
)
def test_m187_preserves_backend_output_payloads_opaque(
    text: str,
    kind: BackendOutputRequestKind,
    angle_payload: str,
    argument_payload: str | None,
) -> None:
    request = _single_request(discover_backend_output_requests_in_text(text, _location()))

    assert request.kind is kind
    assert request.angle_payload_text == angle_payload
    assert request.argument_text == argument_payload
    assert request.source_text == text


def test_m187_body_discovery_preserves_opaque_tokens_and_raw_token_identity() -> None:
    directive = LowerableDirective(
        name="if",
        arguments=("compile", "assume_aligned<hidden>(ptr)"),
        source=_location(column=20),
    )
    fragment = LowerableOperationFragment(
        operation="add",
        arguments=("left", "right"),
        source=_location(column=60),
    )
    tokens = (
        _raw("prefix "),
        directive,
        _raw("assume_aligned<", column=40),
        _raw("value<generation>(vector::alignment)>(", line=2, column=3),
        _raw("tmp.data()); ", line=3, column=5),
        fragment,
        _raw(" array_type<", line=4, column=7),
        _raw("type<generation>(base::in)> tail", line=5, column=9),
    )

    result = Lowerer().discover_backend_output_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 7
    assert isinstance(result.discovery.segments[0], BackendOutputOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], directive)
    assert isinstance(result.discovery.segments[1], BackendOutputRequestSegment)
    first_request = result.discovery.segments[1].request
    assert first_request.kind is BackendOutputRequestKind.ASSUME_ALIGNED
    assert first_request.source == _location(column=40)
    assert first_request.angle_payload_source == _location(line=2, column=3)
    assert first_request.argument_source == _location(line=3, column=5)
    assert isinstance(result.discovery.segments[2], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[2].text == "; "
    assert isinstance(result.discovery.segments[3], BackendOutputOpaqueTokenSegment)
    assert result.discovery.segments[3].tokens == (fragment,)
    assert isinstance(result.discovery.segments[4], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[4].text == " "
    assert isinstance(result.discovery.segments[5], BackendOutputRequestSegment)
    second_request = result.discovery.segments[5].request
    assert second_request.kind is BackendOutputRequestKind.ARRAY_TYPE
    assert second_request.source == _location(line=4, column=8)
    assert second_request.angle_payload_source == _location(line=5, column=9)
    assert second_request.argument_text is None
    assert isinstance(result.discovery.segments[6], BackendOutputOpaqueTextSegment)
    assert result.discovery.segments[6].text == " tail"


@pytest.mark.parametrize(
    "text",
    (
        "assume_aligned<value<generation>(vector::alignment)(ptr)",
        "assume_aligned<value<generation>(vector::alignment)>",
        "pack<first>(args",
        "array_type<>",
        "array_type<type<generation>(base::in)>()",
    ),
)
def test_m187_reports_malformed_backend_output_islands(text: str) -> None:
    result = discover_backend_output_requests_in_text(text, _location())

    first_keyword = min(
        index
        for keyword in ("assume_aligned", "array_type", "pack")
        if (index := text.find(keyword)) != -1
    )
    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(column=first_keyword + 1)
    assert "invalid outer shape" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-BACKEND-OUTPUT-SOURCE-ISLAND",)


@pytest.mark.parametrize(
    "text",
    (
        "details::arith_add(left, right)",
        "my_assume_aligned<value<generation>(vector::alignment)>(ptr)",
        "array_type_helper<type<generation>(base::in)>",
        "packing<first>(args)",
    ),
)
def test_m187_reports_no_backend_output_when_requested_for_text(text: str) -> None:
    result = discover_backend_output_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location()
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-OUTPUT-SOURCE-ISLAND",)


def test_m187_reports_no_backend_output_when_requested_for_body_tokens() -> None:
    result = Lowerer().discover_backend_output_requests(
        _selected(
            ImplementationBody(
                tokens=(
                    _raw("details::arith_mul(left, right)"),
                    LowerableDirective(
                        name="var",
                        arguments=("infer", "tmp, pack<hidden>(x)"),
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
    assert _codes(result) == ("TSL-LOWER-NO-BACKEND-OUTPUT-SOURCE-ISLAND",)


def test_m187_request_kind_is_typed_and_payload_text_is_source_owned() -> None:
    request = BackendOutputRequest(
        kind=BackendOutputRequestKind.ARRAY_TYPE,
        angle_payload_text="type<generation>(base::in)",
        angle_payload_source=_location(column=12),
        argument_text=None,
        argument_source=None,
        source_text="array_type<type<generation>(base::in)>",
        source=_location(),
    )

    assert tuple(field.name for field in fields(request)) == (
        "kind",
        "angle_payload_text",
        "angle_payload_source",
        "source_text",
        "source",
        "argument_text",
        "argument_source",
    )
    assert isinstance(request.kind, BackendOutputRequestKind)
    assert request.argument_text is None
    assert request.source_text == "array_type<type<generation>(base::in)>"


def test_m187_discovery_is_deterministic() -> None:
    text = (
        "assume_aligned<value<generation>(vector::alignment)>(ptr); "
        "array_type<type<generation>(base::in)>; "
        "pack<first>(args...)"
    )

    first = discover_backend_output_requests_in_text(text, _location())
    second = discover_backend_output_requests_in_text(text, _location())

    assert first == second


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, BackendOutputRequestSegment)
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
