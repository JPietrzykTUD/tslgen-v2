from dataclasses import fields
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
    GenerationVariableDeclarationRequestSegment,
    Lowerer,
    MaskLaneConstantOpaqueTextSegment,
    MaskLaneConstantOpaqueTokenSegment,
    MaskLaneConstantRequestSegment,
    discover_mask_lane_constant_requests_in_text,
)


@pytest.mark.parametrize("polarity", ("all_true", "all_false"))
def test_m177_discovers_exact_mask_lane_constant_requests(polarity: str) -> None:
    text = f"value<generation>(mask::lane::{polarity})"

    result = discover_mask_lane_constant_requests_in_text(text, _location())

    request = _single_request(result)
    assert request.polarity == polarity
    assert request.source_text == text
    assert request.source == _location()


def test_m177_preserves_prefix_suffix_and_multiple_requests_in_source_order() -> None:
    text = (
        "pre value<generation>(mask::lane::all_true) mid "
        "value<generation>(mask::lane::all_false) post"
    )

    result = discover_mask_lane_constant_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], MaskLaneConstantOpaqueTextSegment)
    assert isinstance(result.discovery.segments[1], MaskLaneConstantRequestSegment)
    assert isinstance(result.discovery.segments[2], MaskLaneConstantOpaqueTextSegment)
    assert isinstance(result.discovery.segments[3], MaskLaneConstantRequestSegment)
    assert isinstance(result.discovery.segments[4], MaskLaneConstantOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert result.discovery.segments[1].request.polarity == "all_true"
    assert result.discovery.segments[2].text == " mid "
    assert result.discovery.segments[3].request.polarity == "all_false"
    assert result.discovery.segments[4].text == " post"


def test_m177_ignores_other_generation_values_while_preserving_them_as_raw_text() -> None:
    text = (
        "value<generation>(vector::length) + "
        "value<generation>(mask::lane::all_true)"
    )

    result = discover_mask_lane_constant_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 2
    assert isinstance(result.discovery.segments[0], MaskLaneConstantOpaqueTextSegment)
    assert result.discovery.segments[0].text == (
        "value<generation>(vector::length) + "
    )
    assert isinstance(result.discovery.segments[1], MaskLaneConstantRequestSegment)
    assert result.discovery.segments[1].request.polarity == "all_true"


def test_m177_discovers_corpus_like_nested_set1_and_assignment_raw_body_text() -> None:
    directive = LowerableDirective(
        name="var",
        arguments=("const_infer", "hidden, value<generation>(mask::lane::all_false)"),
        source=_location(1, 1),
    )
    tokens = (
        directive,
        _raw("call<primitive=set1[Vec]>(", line=2, column=3),
        _raw("value<generation>(mask::lane::all_true)", line=3, column=5),
        _raw(
            "); values[i] = value<generation>(mask::lane::all_false);",
            line=4,
            column=7,
        ),
    )

    result = Lowerer().discover_mask_lane_constant_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 6
    assert isinstance(result.discovery.segments[0], MaskLaneConstantOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (directive,)
    assert isinstance(result.discovery.segments[1], MaskLaneConstantOpaqueTextSegment)
    assert result.discovery.segments[1].text == "call<primitive=set1[Vec]>("
    assert isinstance(result.discovery.segments[2], MaskLaneConstantRequestSegment)
    assert result.discovery.segments[2].request.polarity == "all_true"
    assert result.discovery.segments[2].request.source == _location(3, 5)
    assert isinstance(result.discovery.segments[3], MaskLaneConstantOpaqueTextSegment)
    assert result.discovery.segments[3].text == "); values[i] = "
    assert isinstance(result.discovery.segments[4], MaskLaneConstantRequestSegment)
    assert result.discovery.segments[4].request.polarity == "all_false"
    assert isinstance(result.discovery.segments[5], MaskLaneConstantOpaqueTextSegment)
    assert result.discovery.segments[5].text == ";"


def test_m177_discovers_var_const_infer_initializer_pair_as_request_text() -> None:
    true_var = _var(
        "const_infer",
        "true_value, value<generation>(mask::lane::all_true)",
        line=1,
        column=1,
    )
    false_var = _var(
        "const_infer",
        "false_value, value<generation>(mask::lane::all_false)",
        line=2,
        column=1,
    )

    declaration_result = Lowerer().discover_generation_variable_declarations(
        _selected(
            ImplementationBody(
                tokens=(true_var, false_var),
                source=_location(),
            )
        )
    )

    assert declaration_result.diagnostics == ()
    assert declaration_result.discovery is not None
    declarations = tuple(
        segment.declaration
        for segment in declaration_result.discovery.segments
        if isinstance(segment, GenerationVariableDeclarationRequestSegment)
    )
    initializer_requests = tuple(
        _single_request(
            discover_mask_lane_constant_requests_in_text(
                declaration.initializer.text,
                declaration.initializer.source,
            )
        )
        for declaration in declarations
        if declaration.initializer is not None
    )

    assert tuple(request.polarity for request in initializer_requests) == (
        "all_true",
        "all_false",
    )
    assert initializer_requests[0].source_text == (
        "value<generation>(mask::lane::all_true)"
    )
    assert initializer_requests[1].source_text == (
        "value<generation>(mask::lane::all_false)"
    )


@pytest.mark.parametrize(
    "text",
    (
        "value<generation>(mask::lane::all_true",
        "prefix value<generation>(mask::lane::all_false",
    ),
)
def test_m177_reports_malformed_outer_mask_lane_constant_islands(text: str) -> None:
    result = discover_mask_lane_constant_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("value<generation>(") + 1
    )
    assert "unbalanced outer payload" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-MALFORMED-MASK-LANE-CONSTANT",)


def test_m177_reports_unknown_mask_lane_name() -> None:
    text = "value<generation>(mask::lane::maybe)"

    result = discover_mask_lane_constant_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=len("value<generation>(mask::lane::") + 1
    )
    assert "maybe" in result.diagnostics[0].message
    assert "all_false, all_true" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-UNKNOWN-MASK-LANE-CONSTANT",)


def test_m177_request_values_do_not_carry_backend_helper_text() -> None:
    request = _single_request(
        discover_mask_lane_constant_requests_in_text(
            "value<generation>(mask::lane::all_true)",
            _location(),
        )
    )

    assert tuple(field.name for field in fields(request)) == (
        "polarity",
        "source_text",
        "source",
    )
    assert not hasattr(request, "value")
    assert "mask_true_lane_value" not in repr(request)
    assert "::tsl::details" not in repr(request)
    assert "BaseType::default" not in repr(request)


@pytest.mark.parametrize("polarity", ("all_true", "all_false"))
def test_m177_generation_value_query_does_not_materialize_mask_lane_constants(
    polarity: str,
) -> None:
    query = f"value<generation>(mask::lane::{polarity})"

    result = Lowerer().lower_generation_value_query(
        _selected(ImplementationBody(tokens=(), source=_location())),
        query,
        _location(),
    )

    assert result.value is None
    assert result.diagnostics[0].severity == "error"
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",)


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, MaskLaneConstantRequestSegment)
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


def _var(
    selector: str,
    payload: str,
    *,
    line: int = 1,
    column: int = 1,
) -> LowerableDirective:
    return LowerableDirective(
        name="var",
        arguments=(selector, payload),
        source=_location(line, column),
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
