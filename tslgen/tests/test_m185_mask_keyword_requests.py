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
    Lowerer,
    MaskKeywordOpaqueTextSegment,
    MaskKeywordOpaqueTokenSegment,
    MaskKeywordRequest,
    MaskKeywordRequestSegment,
    MaskKeywordSelector,
    discover_mask_keyword_requests_in_text,
)


@pytest.mark.parametrize(
    ("selector_text", "selector"),
    (
        ("zero", MaskKeywordSelector.ZERO),
        ("test", MaskKeywordSelector.TEST),
        ("set", MaskKeywordSelector.SET),
        ("set:1", MaskKeywordSelector.SET_ONE),
    ),
)
def test_m185_discovers_exact_mask_keyword_selectors_from_text(
    selector_text: str,
    selector: MaskKeywordSelector,
) -> None:
    text = f"mask<{selector_text}>(mask, value)"

    request = _single_request(discover_mask_keyword_requests_in_text(text, _location()))

    assert request.selector is selector
    assert request.selector_source == _location(column=len("mask<") + 1)
    assert request.argument_text == "mask, value"
    assert request.argument_source == _location(
        column=len(f"mask<{selector_text}>(") + 1,
    )
    assert request.source_text == text
    assert request.source == _location()
    assert not hasattr(request, "selector_text")


def test_m185_preserves_prefix_suffix_and_multiple_requests_in_source_order() -> None:
    text = "pre mask<zero>() mid mask<test>(data, mask<set:1>(i)) post"

    result = discover_mask_keyword_requests_in_text(text, _location())

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 5
    assert isinstance(result.discovery.segments[0], MaskKeywordOpaqueTextSegment)
    assert result.discovery.segments[0].text == "pre "
    assert isinstance(result.discovery.segments[1], MaskKeywordRequestSegment)
    assert result.discovery.segments[1].request.selector is MaskKeywordSelector.ZERO
    assert isinstance(result.discovery.segments[2], MaskKeywordOpaqueTextSegment)
    assert result.discovery.segments[2].text == " mid "
    assert isinstance(result.discovery.segments[3], MaskKeywordRequestSegment)
    assert result.discovery.segments[3].request.selector is MaskKeywordSelector.TEST
    assert result.discovery.segments[3].request.argument_text == (
        "data, mask<set:1>(i)"
    )
    assert isinstance(result.discovery.segments[4], MaskKeywordOpaqueTextSegment)
    assert result.discovery.segments[4].text == " post"


def test_m185_body_discovery_preserves_opaque_tokens_and_raw_token_identity() -> None:
    directive = LowerableDirective(
        name="var",
        arguments=("infer", "hidden, mask<zero>()"),
        source=_location(column=20),
    )
    fragment = LowerableOperationFragment(
        operation="add",
        arguments=("left", "right"),
        source=_location(column=60),
    )
    tokens = (
        _raw("prefix ", column=1),
        directive,
        _raw(" mask<zero>(", column=80),
        _raw("); ", line=2, column=1),
        fragment,
        _raw('mask<test>(value, "not ) > close")', line=3, column=5),
    )

    result = Lowerer().discover_mask_keyword_requests(
        _selected(ImplementationBody(tokens=tokens, source=_location()))
    )

    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 6
    assert isinstance(result.discovery.segments[0], MaskKeywordOpaqueTokenSegment)
    assert result.discovery.segments[0].tokens == (tokens[0], directive)
    assert isinstance(result.discovery.segments[1], MaskKeywordOpaqueTextSegment)
    assert result.discovery.segments[1].text == " "
    assert isinstance(result.discovery.segments[2], MaskKeywordRequestSegment)
    assert result.discovery.segments[2].request.selector is MaskKeywordSelector.ZERO
    assert result.discovery.segments[2].request.argument_text == ""
    assert isinstance(result.discovery.segments[3], MaskKeywordOpaqueTextSegment)
    assert result.discovery.segments[3].text == "; "
    assert isinstance(result.discovery.segments[4], MaskKeywordOpaqueTokenSegment)
    assert result.discovery.segments[4].tokens == (fragment,)
    assert isinstance(result.discovery.segments[5], MaskKeywordRequestSegment)
    assert result.discovery.segments[5].request.selector is MaskKeywordSelector.TEST
    assert result.discovery.segments[5].request.argument_text == (
        'value, "not ) > close"'
    )


def test_m185_quoted_delimiter_like_characters_in_arguments_remain_opaque() -> None:
    text = 'mask<test>("not ) close", "not > close", value + 1)'

    request = _single_request(discover_mask_keyword_requests_in_text(text, _location()))

    assert request.selector is MaskKeywordSelector.TEST
    assert request.argument_text == '"not ) close", "not > close", value + 1'


@pytest.mark.parametrize(
    "text",
    (
        "details::mask_test<Vec>(mask, i)",
        "value<generation>(mask::lane::all_true)",
        "my_mask<zero>()",
        "mask_helper<zero>()",
        "backend_mask<test>(value)",
    ),
)
def test_m185_reports_no_match_for_non_mask_keyword_text(text: str) -> None:
    result = discover_mask_keyword_requests_in_text(text, _location())

    assert result.discovery is None
    assert _codes(result) == ("TSL-LOWER-NO-MASK-KEYWORD",)


@pytest.mark.parametrize(
    "text",
    (
        "mask<zero(value)",
        "prefix mask<test>(value",
        "mask<set:1> value",
    ),
)
def test_m185_reports_malformed_outer_mask_keyword_islands(text: str) -> None:
    result = discover_mask_keyword_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(column=text.index("mask<") + 1)
    assert _codes(result) == ("TSL-LOWER-MALFORMED-MASK-KEYWORD",)


@pytest.mark.parametrize(
    "text",
    (
        "mask<one>()",
        "mask< zero >()",
        "mask<>()",
        "mask<{selector}>()",
        "mask<selector=value<backend>(mask::selector)>()",
    ),
)
def test_m185_reports_unsupported_selector_payloads(text: str) -> None:
    result = discover_mask_keyword_requests_in_text(text, _location())

    assert result.discovery is None
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == _location(
        column=text.index("<") + 2,
    )
    assert "expected one of set, set:1, test, zero" in result.diagnostics[0].message
    assert _codes(result) == ("TSL-LOWER-UNSUPPORTED-MASK-KEYWORD-SELECTOR",)


def test_m185_request_keeps_selector_typed_and_payloads_source_owned() -> None:
    request = MaskKeywordRequest(
        selector=MaskKeywordSelector.SET_ONE,
        selector_source=_location(column=6),
        argument_text="lane",
        argument_source=_location(column=13),
        source_text="mask<set:1>(lane)",
        source=_location(),
    )

    assert tuple(field.name for field in fields(request)) == (
        "selector",
        "selector_source",
        "argument_text",
        "argument_source",
        "source_text",
        "source",
    )
    assert isinstance(request.selector, MaskKeywordSelector)
    assert request.argument_text == "lane"
    assert request.source_text == "mask<set:1>(lane)"


def _single_request(result):
    assert result.diagnostics == ()
    assert result.discovery is not None
    assert len(result.discovery.segments) == 1
    segment = result.discovery.segments[0]
    assert isinstance(segment, MaskKeywordRequestSegment)
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
