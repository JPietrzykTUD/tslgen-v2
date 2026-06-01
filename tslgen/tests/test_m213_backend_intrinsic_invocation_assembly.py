from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendComposedIntrinsicInvocation,
    BackendDirectIntrinsicInvocation,
    BackendIntrinsicImmediateGenericParameterReference,
    BackendIntrinsicImmediateLiteral,
    BackendIntrinsicImmediateParameterReference,
    BackendIntrinsicInfixSeparator,
    BackendIntrinsicInvocationImmediate,
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
    assemble_backend_intrinsic_invocation,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    Primitive,
    PrimitiveGenericParameter,
    PrimitiveGenericParameterKind,
)
from tslgen.domain.signatures import (
    SignatureParameterTerm,
    SignatureTerm,
    SignatureTermKind,
)
from tslgen.lowering import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierIntegerOperand,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)


def test_m213_assembles_direct_literal_intrinsic_with_opaque_arguments() -> None:
    request = _direct_request(
        "intrin<_mm_add_epi32>(left, intrin_compose<nested, suffix=si32>(right))"
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp")

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendDirectIntrinsicInvocation)
    assert result.invocation.backend == BackendId("cpp")
    assert result.invocation.request is request
    assert result.invocation.intrinsic_name == "_mm_add_epi32"
    assert (
        result.invocation.arguments.text
        == "left, intrin_compose<nested, suffix=si32>(right)"
    )
    assert result.invocation.arguments.source == request.argument_source


def test_m213_diagnoses_direct_placeholder_intrinsic_names() -> None:
    request = _direct_request("intrin<vshlq_{{suffix}}>(data)")

    result = assemble_backend_intrinsic_invocation(request, "rust")

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-UNSUPPORTED-DIRECT-NAME",
    )
    assert result.diagnostics[0].location == request.angle_payload_source


def test_m213_assembles_composed_prefix_base_and_suffix_name() -> None:
    request = _compose_request("intrin_compose<add, prefix=p, suffix=s>(left, right)")
    translations = (
        _translated(_field(request, "prefix"), BackendIntrinsicLiteralFragment("_mm256_")),
        _translated(_field(request, "suffix"), BackendIntrinsicLiteralFragment("epi32")),
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", translations)

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == "_mm256_add_epi32"
    assert [part.role for part in result.invocation.name_parts] == [
        "prefix",
        "base",
        "suffix",
    ]
    assert [part.text for part in result.invocation.name_parts] == [
        "_mm256_",
        "add",
        "epi32",
    ]
    assert result.invocation.arguments.text == "left, right"


def test_m213_assembles_infix_with_default_separator() -> None:
    request = _compose_request("intrin_compose<cvt, infix=ps, suffix=epi32>(data)")
    translations = (
        _translated(_field(request, "infix"), BackendIntrinsicLiteralFragment("ps")),
        _translated(_field(request, "suffix"), BackendIntrinsicLiteralFragment("epi32")),
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", translations)

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == "cvt_ps_epi32"


def test_m213_assembles_infix_with_explicit_empty_separator() -> None:
    request = _compose_request(
        'intrin_compose<cvt, infix=ps, infix_sep="", suffix=epi32>(data)'
    )
    translation = _translated_modifiers(request)

    result = assemble_backend_intrinsic_invocation(request, "cpp", translation)

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == "cvtps_epi32"


def test_m213_assembles_post_after_suffix() -> None:
    request = _compose_request("intrin_compose<svadd, suffix=s32, post=x>(pg, data)")
    translation = _translated_modifiers(request, backend="rust")

    result = assemble_backend_intrinsic_invocation(request, "rust", translation)

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == "svadd_s32_x"


def test_m213_preserves_all_typed_immediate_metadata_families() -> None:
    literal_field = _manual_immediate_field("immediate(0)=4", 0)
    signature_field = _manual_immediate_field("immediate(1)=lane", 1)
    generic_field = _manual_immediate_field("immediate(2)=Index", 2)
    request = _manual_compose_request(
        base_text="extract",
        modifiers=(literal_field, signature_field, generic_field),
    )
    signature_parameter = SignatureParameterTerm(
        name="lane",
        term=SignatureTerm(SignatureTermKind.SCALAR_IMMEDIATE, "sImm"),
        source=_location(1, 15),
    )
    generic_parameter = PrimitiveGenericParameter(
        name="Index",
        kind=PrimitiveGenericParameterKind.INT,
        default=0,
        source=_location(1, 24),
    )
    literal = BackendIntrinsicImmediateLiteral(argument_index=0, value=4)
    signature = BackendIntrinsicImmediateParameterReference(
        argument_index=1,
        parameter=signature_parameter,
        source_text="lane",
        source=_location(1, 31),
    )
    generic = BackendIntrinsicImmediateGenericParameterReference(
        argument_index=2,
        parameter=generic_parameter,
        source_text="Index",
        source=_location(1, 42),
    )
    translations = (
        _translated(literal_field, literal),
        _translated(signature_field, signature),
        _translated(generic_field, generic),
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", translations)

    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    assert result.invocation.intrinsic_name == "extract"
    assert result.invocation.immediates == (
        BackendIntrinsicInvocationImmediate(
            argument_index=0,
            value=literal,
            source=literal_field.source,
            modifier=translations[0],
        ),
        BackendIntrinsicInvocationImmediate(
            argument_index=1,
            value=signature,
            source=signature_field.source,
            modifier=translations[1],
        ),
        BackendIntrinsicInvocationImmediate(
            argument_index=2,
            value=generic,
            source=generic_field.source,
            modifier=translations[2],
        ),
    )


def test_m213_diagnoses_missing_modifier_translation() -> None:
    request = _compose_request("intrin_compose<add, suffix=epi32>(left, right)")

    result = assemble_backend_intrinsic_invocation(request, "cpp", ())

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-MISSING-MODIFIER-TRANSLATION",
    )
    assert result.diagnostics[0].location == request.modifiers[0].source


def test_m213_diagnoses_extra_modifier_translation() -> None:
    request = _compose_request("intrin_compose<add>(left, right)")
    other_request = _compose_request("intrin_compose<sub, suffix=epi32>(left, right)")
    extra = _translated(
        _field(other_request, "suffix"),
        BackendIntrinsicLiteralFragment("epi32"),
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", (extra,))

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-EXTRA-MODIFIER-TRANSLATION",
    )
    assert result.diagnostics[0].location == extra.source


def test_m213_diagnoses_modifier_backend_mismatch_without_missing_noise() -> None:
    request = _compose_request("intrin_compose<add, suffix=epi32>(left, right)")
    field = _field(request, "suffix")
    translation = _translated(
        field,
        BackendIntrinsicLiteralFragment("epi32"),
        backend="rust",
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", (translation,))

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-BACKEND-MISMATCH",
    )
    assert result.diagnostics[0].location == field.source


def test_m213_diagnoses_duplicate_modifier_translation() -> None:
    request = _compose_request("intrin_compose<add, suffix=epi32>(left, right)")
    field = _field(request, "suffix")
    first = _translated(field, BackendIntrinsicLiteralFragment("epi32"))
    second = _translated(field, BackendIntrinsicLiteralFragment("epi32"))

    result = assemble_backend_intrinsic_invocation(request, "cpp", (first, second))

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-DUPLICATE-MODIFIER-TRANSLATION",
    )
    assert result.diagnostics[0].location == field.source


def test_m213_diagnoses_unsupported_translated_modifier_value_kind() -> None:
    request = _compose_request("intrin_compose<add, suffix=epi32>(left, right)")
    field = _field(request, "suffix")
    translation = _translated(
        field,
        BackendIntrinsicImmediateLiteral(argument_index=1, value=4),
    )

    result = assemble_backend_intrinsic_invocation(request, "cpp", (translation,))

    assert result.invocation is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-ASSEMBLY-UNSUPPORTED-MODIFIER-VALUE",
    )
    assert result.diagnostics[0].location == field.source


def test_m213_public_backend_imports_are_available() -> None:
    from tslgen.backends import (  # noqa: PLC0415
        BackendComposedIntrinsicInvocation,
        BackendIntrinsicNamePart,
        BackendIntrinsicNameText,
        assemble_backend_intrinsic_invocation,
    )

    assert (
        BackendComposedIntrinsicInvocation.__name__
        == "BackendComposedIntrinsicInvocation"
    )
    assert BackendIntrinsicNamePart.__name__ == "BackendIntrinsicNamePart"
    assert BackendIntrinsicNameText("x") == "x"
    assert callable(assemble_backend_intrinsic_invocation)


def _direct_request(text: str) -> BackendDirectIntrinsicHandoffRequest:
    request = _single_handoff_request(text)
    assert isinstance(request, BackendDirectIntrinsicHandoffRequest)
    return request


def _compose_request(text: str) -> BackendIntrinsicComposeHandoffRequest:
    request = _single_handoff_request(text)
    assert isinstance(request, BackendIntrinsicComposeHandoffRequest)
    return request


def _single_handoff_request(text: str):
    discovery = discover_backend_intrinsic_requests_in_text(text, _location())
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    result = Lowerer().lower_backend_intrinsic_discovery(
        _selected(),
        discovery.discovery,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    return segment.request


def _selected() -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension="generic",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="unknown",
        implementations=(implementation,),
        source=source,
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


def _translated_modifiers(
    request: BackendIntrinsicComposeHandoffRequest,
    *,
    backend: str = "cpp",
) -> tuple[BackendTranslatedIntrinsicModifier, ...]:
    return tuple(
        _translated(field, _translated_value(field), backend=backend)
        for field in request.modifiers
    )


def _translated_value(field: BackendIntrinsicModifierField):
    if field.name == "infix_sep":
        value = field.value
        assert hasattr(value, "value")
        return BackendIntrinsicInfixSeparator(value.value)
    value = field.value
    if hasattr(value, "text"):
        return BackendIntrinsicLiteralFragment(value.text)
    if hasattr(value, "value"):
        return BackendIntrinsicLiteralFragment(value.value)
    raise AssertionError(f"unsupported test modifier value: {field!r}")


def _translated(
    field: BackendIntrinsicModifierField,
    value,
    *,
    backend: str = "cpp",
) -> BackendTranslatedIntrinsicModifier:
    return BackendTranslatedIntrinsicModifier(
        backend=BackendId(backend),
        field=field,
        name=field.name,
        value=value,
        source=field.source,
    )


def _field(
    request: BackendIntrinsicComposeHandoffRequest,
    name: str,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == name)
    assert len(matches) == 1
    return matches[0]


def _manual_compose_request(
    *,
    base_text: str,
    modifiers: tuple[BackendIntrinsicModifierField, ...],
) -> BackendIntrinsicComposeHandoffRequest:
    return BackendIntrinsicComposeHandoffRequest(
        base_text=base_text,
        base_source=_location(),
        modifiers=modifiers,
        angle_payload_text=base_text,
        angle_payload_source=_location(),
        argument_text="data, lane, Index",
        argument_source=_location(1, 20),
        source_text=f"intrin_compose<{base_text}>(data, lane, Index)",
        source=_location(),
    )


def _manual_immediate_field(
    source_text: str,
    immediate_index: int,
) -> BackendIntrinsicModifierField:
    return BackendIntrinsicModifierField(
        name="immediate",
        key_text=f"immediate({immediate_index})",
        value=BackendIntrinsicModifierIntegerOperand(
            value=immediate_index,
            source_text=str(immediate_index),
            source=_location(),
        ),
        source_text=source_text,
        source=_location(),
        key_source=_location(),
        value_source=_location(),
        immediate_index=immediate_index,
        immediate_index_text=str(immediate_index),
    )


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
