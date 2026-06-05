from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendComposedIntrinsicInvocation,
    BackendDirectIntrinsicInvocation,
    BackendIntrinsicImmediateLiteral,
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
    assemble_backend_intrinsic_invocation,
)
from tslgen.backends.rust import (
    RustArchitectureModule,
    RustIntrinsicCallRenderResult,
    RustIntrinsicCallText,
    RustIntrinsicNameQualification,
    RustRenderedIntrinsicCall,
    render_rust_intrinsic_invocation_call,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import Implementation, ImplementationBody, Primitive
from tslgen.lowering import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)


def test_m219_renders_direct_rust_x86_intrinsic_call() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
    )

    assert result.diagnostics == ()
    assert isinstance(result.call, RustRenderedIntrinsicCall)
    assert result.call.invocation is invocation
    assert result.call.architecture_module == RustArchitectureModule("x86_64")
    assert result.call.call_text == (
        "core::arch::x86_64::_mm_add_epi32(left, right)"
    )
    assert result.call.immediates == ()
    assert result.call.source == invocation.source


def test_m219_renders_direct_rust_aarch64_intrinsic_call() -> None:
    invocation = _direct_invocation("intrin<vaddq_u32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("aarch64"),
    )

    assert result.diagnostics == ()
    assert isinstance(result.call, RustRenderedIntrinsicCall)
    assert result.call.call_text == "core::arch::aarch64::vaddq_u32(left, right)"


def test_m219_uses_explicit_module_without_inferring_from_intrinsic_name() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("aarch64"),
    )

    assert result.diagnostics == ()
    assert result.call is not None
    assert result.call.call_text == (
        "core::arch::aarch64::_mm_add_epi32(left, right)"
    )


def test_m219_renders_already_qualified_rust_intrinsic_name() -> None:
    invocation = _direct_invocation(
        "intrin<core::arch::x86_64::_mm_add_epi32>(left, right)"
    )

    result = render_rust_intrinsic_invocation_call(
        invocation,
        None,
        name_qualification=RustIntrinsicNameQualification.ALREADY_QUALIFIED,
    )

    assert result.diagnostics == ()
    assert result.call is not None
    assert result.call.architecture_module is None
    assert result.call.call_text == (
        "core::arch::x86_64::_mm_add_epi32(left, right)"
    )


def test_m219_renders_composed_rust_intrinsic_call() -> None:
    invocation = _composed_invocation(
        "intrin_compose<add, prefix=p, suffix=s>(left, right)",
        (
            ("prefix", BackendIntrinsicLiteralFragment("_mm256_")),
            ("suffix", BackendIntrinsicLiteralFragment("epi32")),
        ),
    )

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
    )

    assert result.diagnostics == ()
    assert isinstance(result.call, RustRenderedIntrinsicCall)
    assert result.call.call_text == (
        "core::arch::x86_64::_mm256_add_epi32(left, right)"
    )
    assert result.call.immediates == ()


def test_m219_renders_empty_argument_payload_as_qualified_empty_call() -> None:
    invocation = _direct_invocation("intrin<_mm_lfence>()")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
    )

    assert result.diagnostics == ()
    assert result.call is not None
    assert result.call.call_text == "core::arch::x86_64::_mm_lfence()"


def test_m219_preserves_opaque_nested_tsil_looking_argument_payload() -> None:
    invocation = _direct_invocation(
        "intrin<_mm_blend_epi32>(left, intrin_compose<nested, suffix=si32>(right))"
    )

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
    )

    assert result.diagnostics == ()
    assert result.call is not None
    assert result.call.call_text == (
        "core::arch::x86_64::_mm_blend_epi32"
        "(left, intrin_compose<nested, suffix=si32>(right))"
    )


def test_m219_preserves_immediate_metadata_without_rewriting_call_text() -> None:
    invocation = _composed_invocation(
        "intrin_compose<extract, immediate(1)=4>(data, 4)",
        (("immediate", BackendIntrinsicImmediateLiteral(argument_index=1, value=4)),),
    )

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("aarch64"),
    )

    assert result.diagnostics == ()
    assert isinstance(result.call, RustRenderedIntrinsicCall)
    assert result.call.call_text == "core::arch::aarch64::extract(data, 4)"
    assert result.call.immediates == invocation.immediates
    assert len(result.call.immediates) == 1
    assert result.call.immediates[0].value == BackendIntrinsicImmediateLiteral(
        argument_index=1,
        value=4,
    )


def test_m219_diagnoses_non_rust_invocation_values() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)", backend="cpp")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-BACKEND",
    )
    assert result.diagnostics[0].severity == "error"
    assert "'cpp'" in result.diagnostics[0].message
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_unsupported_invocation_shapes() -> None:
    result = render_rust_intrinsic_invocation_call(
        object(),
        RustArchitectureModule("x86_64"),
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-INVOCATION",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location is None


def test_m219_diagnoses_missing_architecture_module() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(invocation, None)

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-MISSING-ARCHITECTURE-MODULE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_invalid_architecture_module() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64::nested"),
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-INVALID-ARCHITECTURE-MODULE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_non_string_architecture_module_name() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule(8),
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-INVALID-ARCHITECTURE-MODULE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_untyped_architecture_module() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(invocation, "x86_64")

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-ARCHITECTURE-MODULE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_already_qualified_name_with_architecture_module() -> None:
    invocation = _direct_invocation(
        "intrin<core::arch::x86_64::_mm_add_epi32>(left, right)"
    )

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
        name_qualification=RustIntrinsicNameQualification.ALREADY_QUALIFIED,
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-ALREADY-QUALIFIED-MODULE-MISUSE",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_diagnoses_untyped_name_qualification() -> None:
    invocation = _direct_invocation("intrin<_mm_add_epi32>(left, right)")

    result = render_rust_intrinsic_invocation_call(
        invocation,
        RustArchitectureModule("x86_64"),
        name_qualification="already_qualified",
    )

    assert result.call is None
    assert _codes(result.diagnostics) == (
        "TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-NAME-QUALIFICATION",
    )
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].location == invocation.source


def test_m219_public_rust_backend_imports_are_available() -> None:
    from tslgen.backends.rust import (  # noqa: PLC0415
        RustArchitectureModule,
        RustIntrinsicCallRenderResult,
        RustIntrinsicCallText,
        RustIntrinsicNameQualification,
        RustRenderedIntrinsicCall,
        render_rust_intrinsic_invocation_call,
    )

    assert RustArchitectureModule("x86_64").name == "x86_64"
    assert RustIntrinsicCallText("core::arch::x86_64::_mm_lfence()") == (
        "core::arch::x86_64::_mm_lfence()"
    )
    assert RustIntrinsicCallRenderResult.__name__ == "RustIntrinsicCallRenderResult"
    assert RustRenderedIntrinsicCall.__name__ == "RustRenderedIntrinsicCall"
    assert RustIntrinsicNameQualification.ALREADY_QUALIFIED.value == (
        "already_qualified"
    )
    assert callable(render_rust_intrinsic_invocation_call)


def _direct_invocation(
    text: str,
    *,
    backend: str = "rust",
) -> BackendDirectIntrinsicInvocation:
    request = _direct_request(text)
    result = assemble_backend_intrinsic_invocation(request, backend)
    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendDirectIntrinsicInvocation)
    return result.invocation


def _composed_invocation(
    text: str,
    translated_values: tuple[tuple[str, object], ...],
    *,
    backend: str = "rust",
) -> BackendComposedIntrinsicInvocation:
    request = _compose_request(text)
    translations = tuple(
        _translated(_field(request, name), value, backend=backend)
        for name, value in translated_values
    )
    result = assemble_backend_intrinsic_invocation(request, backend, translations)
    assert result.diagnostics == ()
    assert isinstance(result.invocation, BackendComposedIntrinsicInvocation)
    return result.invocation


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
        backend="rust",
        primitive_name="fixture",
        extension="generic",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _translated(
    field: BackendIntrinsicModifierField,
    value,
    *,
    backend: str = "rust",
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


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
