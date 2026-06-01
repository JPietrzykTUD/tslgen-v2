from __future__ import annotations

from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicImmediateParameterReference,
    translate_backend_intrinsic_modifier_field,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Implementation, ImplementationBody, Primitive
from tslgen.domain.signatures import (
    PrimitiveSignature,
    SignatureParameterTerm,
    SignatureTerm,
    SignatureTermKind,
    parse_primitive_signature,
    signature_parameter_terms,
)
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierSymbolOperand,
    LoweredSelectedSignatureImmediateParameter,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.lowering._source_islands import matching_delimiter_close

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_m208_lowers_and_translates_selected_signature_immediate_parameter() -> None:
    request = _single_compose_request(
        "intrin_compose<extracti128 suffix=si256 immediate(1)=index>(data, index)",
        _selected(signature_text="v:=(v,sImm)", parameter_names=("data", "index")),
    )
    field = _immediate_field(request)

    immediate = field.value
    assert isinstance(immediate, LoweredSelectedSignatureImmediateParameter)
    assert immediate.argument_index == 1
    assert immediate.parameter.name == "index"
    assert immediate.parameter.term.kind is SignatureTermKind.SCALAR_IMMEDIATE
    assert immediate.source_text == "index"

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.field is field
    assert result.modifier.value == BackendIntrinsicImmediateParameterReference(
        argument_index=1,
        parameter=immediate.parameter,
        source_text="index",
        source=immediate.source,
    )


def test_m208_selected_signature_immediate_is_not_hardcoded_to_index() -> None:
    request = _single_compose_request(
        "intrin_compose<extracti128 immediate(1)=arbitrary>(data, arbitrary)",
        _selected(
            signature_text="v:=(v,sImm)",
            parameter_names=("data", "arbitrary"),
        ),
    )
    field = _immediate_field(request)

    assert isinstance(field.value, LoweredSelectedSignatureImmediateParameter)
    assert field.value.parameter.name == "arbitrary"

    result = translate_backend_intrinsic_modifier_field(field, "rust")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicImmediateParameterReference(
        argument_index=1,
        parameter=field.value.parameter,
        source_text="arbitrary",
        source=field.value.source,
    )


def test_m208_backend_consumes_lowered_immediate_without_selected_context() -> None:
    parameter = SignatureParameterTerm(
        name="lane",
        term=SignatureTerm(SignatureTermKind.SCALAR_IMMEDIATE, "sImm"),
        source=_location(1, 1),
    )
    operand = LoweredSelectedSignatureImmediateParameter(
        argument_index=2,
        parameter=parameter,
        source_text="lane",
        source=_location(1, 31),
    )
    field = _immediate_modifier_field(value=operand, immediate_index=None)

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicImmediateParameterReference(
        argument_index=2,
        parameter=parameter,
        source_text="lane",
        source=operand.source,
    )


@pytest.mark.parametrize(
    ("signature_text", "parameter_names", "symbol"),
    (
        ("v:=(v,v)", ("data", "index"), "index"),
        ("v:=(v,sImm)", ("data", "index"), "missing"),
        ("s:=v[idx]", ("a",), "Index"),
    ),
)
def test_m208_non_signature_immediate_symbols_remain_unsupported(
    signature_text: str,
    parameter_names: tuple[str, ...],
    symbol: str,
) -> None:
    request = _single_compose_request(
        f"intrin_compose<vgetq_lane immediate(1)={symbol}>(a, {symbol})",
        _selected(signature_text=signature_text, parameter_names=parameter_names),
    )
    field = _immediate_field(request)

    assert isinstance(field.value, BackendIntrinsicModifierSymbolOperand)
    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
    )


def test_m208_backend_does_not_resolve_raw_symbol_immediates() -> None:
    field = _immediate_modifier_field(
        value=BackendIntrinsicModifierSymbolOperand(
            text="index",
            source=_location(1, 31),
        ),
        immediate_index=1,
    )

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
    )


def test_m208_selected_context_accepts_all_observed_convert_up_index_immediates() -> None:
    path = _REPO_ROOT / "tsldata" / "primitives" / "conversion" / "repr_change.tsl"
    text = path.read_text(encoding="utf-8")
    selected = _selected(
        signature_text="v:=(v,sImm)",
        parameter_names=("data", "index"),
    )

    snippets = tuple(
        snippet
        for snippet, _source in _intrin_compose_snippets(path, text)
        if "immediate(1)=index" in snippet
    )

    assert len(snippets) == 18
    for snippet in snippets:
        request = _single_compose_request(snippet, selected)
        field = _immediate_field(request)

        assert isinstance(field.value, LoweredSelectedSignatureImmediateParameter)
        assert field.value.argument_index == 1
        assert field.value.parameter.name == "index"
        assert field.value.parameter.term.kind is SignatureTermKind.SCALAR_IMMEDIATE
        translation = translate_backend_intrinsic_modifier_field(field, "cpp")
        assert translation.diagnostics == ()
        assert translation.modifier is not None
        assert isinstance(
            translation.modifier.value,
            BackendIntrinsicImmediateParameterReference,
        )


def _selected(
    *,
    signature_text: str,
    parameter_names: tuple[str, ...],
) -> SelectedImplementation:
    source = _location()
    signature = _signature(signature_text)
    bindings = signature_parameter_terms(signature, parameter_names, source)
    assert bindings.diagnostics == ()
    implementation = Implementation(
        extension="avx2",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature=signature.source_text,
        parameters=parameter_names,
        template="unknown",
        implementations=(implementation,),
        source=source,
        signature_model=signature,
        parameter_signature_terms=bindings.bindings,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="avx2",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _signature(text: str) -> PrimitiveSignature:
    result = parse_primitive_signature(text, _location())
    assert result.diagnostics == ()
    assert result.signature is not None
    return result.signature


def _single_compose_request(
    text: str,
    selected: SelectedImplementation,
) -> BackendIntrinsicComposeHandoffRequest:
    lowerer = Lowerer()
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    environment = lowerer.type_environment_for(selected)
    result = lowerer.lower_backend_intrinsic_discovery(
        selected,
        discovery.discovery,
        environment=environment,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    assert isinstance(segment.request, BackendIntrinsicComposeHandoffRequest)
    return segment.request


def _immediate_field(
    request: BackendIntrinsicComposeHandoffRequest,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == "immediate")
    assert len(matches) == 1
    return matches[0]


def _immediate_modifier_field(
    *,
    value,
    immediate_index: int | None,
) -> BackendIntrinsicModifierField:
    key_index = "missing" if immediate_index is None else str(immediate_index)
    return BackendIntrinsicModifierField(
        name="immediate",
        key_text=f"immediate({key_index})",
        value=value,
        source_text=f"immediate({key_index})=value",
        source=_location(1, 1),
        key_source=_location(1, 1),
        value_source=_location(1, 31),
        immediate_index=immediate_index,
        immediate_index_text=None if immediate_index is None else str(immediate_index),
    )


def _intrin_compose_snippets(
    path: Path,
    text: str,
) -> tuple[tuple[str, SourceLocation], ...]:
    snippets: list[tuple[str, SourceLocation]] = []
    position = 0
    head = "intrin_compose"
    while True:
        start = text.find(f"{head}<", position)
        if start == -1:
            break

        angle_open = start + len(head)
        angle_close = matching_delimiter_close(text, angle_open, "<", ">")
        if angle_close is None:
            position = start + 1
            continue

        args_open = _skip_whitespace(text, angle_close + 1)
        if args_open >= len(text) or text[args_open] != "(":
            position = start + 1
            continue

        args_close = matching_delimiter_close(text, args_open, "(", ")")
        if args_close is None:
            position = start + 1
            continue

        snippets.append((text[start : args_close + 1], _source_at(path, text, start)))
        position = start + 1

    return tuple(snippets)


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _source_at(path: Path, text: str, offset: int) -> SourceLocation:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    column = len(prefix.rsplit("\n", 1)[-1]) + 1
    return SourceLocation(path, line, column)


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
