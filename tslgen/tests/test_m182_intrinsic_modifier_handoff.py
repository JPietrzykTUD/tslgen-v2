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
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierIntegerOperand,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicRequestSegment,
    BackendIntrinsicSuffixValueRequest,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
    lower_backend_intrinsic_discovery,
)


def test_m182_lowers_intrin_compose_modifiers_from_text() -> None:
    discovery = _text_discovery(
        "intrin_compose<srli, suffix=value<backend>(intrin::suffix), "
        "immediate(1)=4>(data, 4)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        lower_backend_intrinsic_discovery(
            Lowerer().context_for(selected),
            discovery,
        )
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    assert request.base_text == "srli"
    assert request.argument_text == "data, 4"
    assert len(request.modifiers) == 2
    suffix = request.modifiers[0]
    assert suffix.name == "suffix"
    assert suffix.key_text == "suffix"
    assert suffix.source_text == "suffix=value<backend>(intrin::suffix)"
    assert isinstance(suffix.value, BackendIntrinsicModifierBackendValueOperand)
    assert suffix.value.request == BackendIntrinsicSuffixValueRequest(
        backend="cpp",
        argument=None,
        source_text="value<backend>(intrin::suffix)",
        source=_location(column=29),
    )
    assert suffix.value.island.source_text == "value<backend>(intrin::suffix)"
    immediate = request.modifiers[1]
    assert immediate.name == "immediate"
    assert immediate.key_text == "immediate(1)"
    assert immediate.immediate_index == 1
    assert isinstance(immediate.value, BackendIntrinsicModifierIntegerOperand)
    assert immediate.value.value == 4
    assert immediate.value.source_text == "4"


def test_m182_lowers_intrin_compose_without_modifiers() -> None:
    discovery = _text_discovery("intrin_compose<svdup>(0)")
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    assert request.base_text == "svdup"
    assert request.modifiers == ()


def test_m182_lowers_observed_whitespace_separated_modifier_fields() -> None:
    discovery = _text_discovery(
        "intrin_compose<vgetq_lane suffix=value<backend>(intrin::suffix) "
        "immediate(1)=Index>(a, Index)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    assert request.base_text == "vgetq_lane"
    assert [modifier.name for modifier in request.modifiers] == [
        "suffix",
        "immediate",
    ]
    assert isinstance(
        request.modifiers[0].value,
        BackendIntrinsicModifierBackendValueOperand,
    )
    assert isinstance(request.modifiers[1].value, BackendIntrinsicModifierSymbolOperand)
    assert request.modifiers[1].value.text == "Index"


def test_m182_lowers_body_discovery_preserving_opaque_tokens_and_text() -> None:
    hidden_directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, intrin_compose<hidden, post=x>(data)"),
        source=_location(column=20),
    )
    tokens = (
        _raw("prefix ", column=1),
        hidden_directive,
        _raw("intrin_compose<svcnt, post=x>(pg, data) suffix", column=80),
    )
    selected = _selected(ImplementationBody(tokens=tokens, source=_location()))
    lowerer = Lowerer()
    discovery_result = lowerer.discover_backend_intrinsic_requests(selected)
    assert discovery_result.diagnostics == ()
    assert discovery_result.discovery is not None

    result = lowerer.lower_backend_intrinsic_discovery(
        selected,
        discovery_result.discovery,
    )

    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 3
    assert result.handoff.segments[0] is discovery_result.discovery.segments[0]
    assert isinstance(result.handoff.segments[0], BackendIntrinsicOpaqueTokenSegment)
    assert result.handoff.segments[0].tokens == (tokens[0], hidden_directive)
    assert isinstance(result.handoff.segments[1], BackendIntrinsicHandoffRequestSegment)
    assert result.handoff.segments[1].island is (
        discovery_result.discovery.segments[1].request
    )
    assert isinstance(
        result.handoff.segments[1].request,
        BackendIntrinsicComposeHandoffRequest,
    )
    assert result.handoff.segments[1].request.modifiers[0].name == "post"
    assert result.handoff.segments[2] is discovery_result.discovery.segments[2]
    assert isinstance(result.handoff.segments[2], BackendIntrinsicOpaqueTextSegment)
    assert result.handoff.segments[2].text == " suffix"


def test_m182_lowers_unresolved_literal_symbol_modifier_operands() -> None:
    discovery = _text_discovery(
        'intrin_compose<set, suffix=si128, post=mask, infix=to_type_suffix, '
        'infix_sep="", immediate(2)=4>(x)'
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    values = tuple(modifier.value for modifier in request.modifiers)
    assert isinstance(values[0], BackendIntrinsicModifierSymbolOperand)
    assert values[0].text == "si128"
    assert isinstance(values[1], BackendIntrinsicModifierSymbolOperand)
    assert values[1].text == "mask"
    assert isinstance(values[2], BackendIntrinsicModifierSymbolOperand)
    assert values[2].text == "to_type_suffix"
    assert isinstance(values[3], BackendIntrinsicModifierStringOperand)
    assert values[3].value == ""
    assert isinstance(values[4], BackendIntrinsicModifierIntegerOperand)
    assert values[4].value == 4


def test_m182_keeps_intrinsic_arguments_opaque_without_nested_scans() -> None:
    text = (
        "intrin_compose<svsel, suffix=x>"
        "(value<backend>(uninit::scalar), intrin_compose<nested>(0), suffix=y)"
    )
    discovery = _text_discovery(text)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_intrinsic_discovery(selected, discovery)

    segment = _single_handoff_request(result)
    request = segment.request
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    assert len(result.handoff.segments) == 1
    assert len(request.modifiers) == 1
    assert isinstance(request.modifiers[0].value, BackendIntrinsicModifierSymbolOperand)
    assert request.argument_text == (
        "value<backend>(uninit::scalar), intrin_compose<nested>(0), suffix=y"
    )


def test_m182_keeps_quoted_modifier_values_delimiter_aware() -> None:
    discovery = _text_discovery(
        'intrin_compose<set, suffix="epi64,x", post="x suffix=y">(x)'
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    suffix = request.modifiers[0]
    post = request.modifiers[1]
    assert isinstance(suffix.value, BackendIntrinsicModifierStringOperand)
    assert suffix.value.value == "epi64,x"
    assert isinstance(post.value, BackendIntrinsicModifierStringOperand)
    assert post.value.value == "x suffix=y"


def test_m182_preserves_direct_intrinsic_payloads_opaque() -> None:
    text = "intrin<_mm_value<backend>(intrin::suffix)>(data)"
    discovery = _text_discovery(text)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendDirectIntrinsicHandoffRequest)
    assert request.angle_payload_text == "_mm_value<backend>(intrin::suffix)"
    assert request.argument_text == "data"
    assert request.source_text == text


def test_m182_keeps_m166_discovery_distinct_until_handoff() -> None:
    discovery = _text_discovery("intrin_compose<srli, suffix=si32>(data)")

    discovery_segment = discovery.segments[0]
    assert isinstance(discovery_segment, BackendIntrinsicRequestSegment)
    assert not isinstance(
        discovery_segment.request,
        BackendIntrinsicComposeHandoffRequest,
    )

    selected = _selected(ImplementationBody(tokens=(), source=_location()))
    handoff_segment = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    )

    assert isinstance(handoff_segment.request, BackendIntrinsicComposeHandoffRequest)
    assert handoff_segment.island is discovery_segment.request


def test_m182_lowers_prefix_backend_value_modifier() -> None:
    discovery = _text_discovery(
        "intrin_compose<vcvt, prefix=value<backend>(intrin::prefix)>(data)"
    )
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    request = _single_handoff_request(
        Lowerer().lower_backend_intrinsic_discovery(selected, discovery)
    ).request

    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    assert isinstance(
        request.modifiers[0].value,
        BackendIntrinsicModifierBackendValueOperand,
    )
    assert request.modifiers[0].value.request == BackendIntrinsicPrefixValueRequest(
        backend="cpp",
        source_text="value<backend>(intrin::prefix)",
        source=_location(column=29),
    )


@pytest.mark.parametrize(
    ("text", "expected_code"),
    (
        (
            "intrin_compose<add, immediate(foo)=1>(x)",
            "TSL-LOWER-MALFORMED-BACKEND-INTRINSIC-MODIFIER",
        ),
        (
            "intrin_compose<add, post=x, post=z>(x)",
            "TSL-LOWER-MALFORMED-BACKEND-INTRINSIC-MODIFIER",
        ),
        (
            "intrin_compose<add, suffix=call<primitive=set1>(x)>(x)",
            "TSL-LOWER-UNSUPPORTED-BACKEND-INTRINSIC-MODIFIER",
        ),
        (
            "intrin_compose<add, suffix=wrap(value<backend>(intrin::suffix))>(x)",
            "TSL-LOWER-UNSUPPORTED-BACKEND-INTRINSIC-MODIFIER",
        ),
        (
            "intrin_compose<add, suffix=value<backend>(intrin::suffix) extra>(x)",
            "TSL-LOWER-UNSUPPORTED-BACKEND-INTRINSIC-MODIFIER",
        ),
        (
            "intrin_compose<add, suffix=value<backend>(intrin::unknown)>(x)",
            "TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        ),
    ),
)
def test_m182_reports_malformed_or_unsupported_modifier_boundaries(
    text: str,
    expected_code: str,
) -> None:
    discovery = _text_discovery(text)
    selected = _selected(ImplementationBody(tokens=(), source=_location()))

    result = Lowerer().lower_backend_intrinsic_discovery(selected, discovery)

    assert result.handoff is None
    assert result.diagnostics[0].severity == "error"
    assert _codes(result) == (expected_code,)


def _text_discovery(text: str):
    result = discover_backend_intrinsic_requests_in_text(text, _location())
    assert result.diagnostics == ()
    assert result.discovery is not None
    return result.discovery


def _single_handoff_request(result):
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    return segment


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
