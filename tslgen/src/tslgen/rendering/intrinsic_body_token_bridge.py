"""Bridge intrinsic body-token rendering into primitive profile artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from tslgen.backends import (
    BackendIntrinsicComposeDefaultPolicy,
    BackendTranslatedIntrinsicModifier,
    assemble_backend_intrinsic_invocation,
    resolve_backend_intrinsic_compose_default_policy,
)
from tslgen.backends.cpp import (
    CppRenderedBodyTokens,
    CppRenderedIntrinsicCall,
    render_cpp_body_tokens_from_intrinsic_handoff,
    render_cpp_intrinsic_invocation_call,
)
from tslgen.backends.rust import (
    RustArchitectureModule,
    RustIntrinsicNameQualification,
    RustRenderedBodyTokens,
    RustRenderedIntrinsicCall,
    render_rust_body_tokens_from_intrinsic_handoff,
    render_rust_intrinsic_invocation_call,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import ExtensionCatalog, ExtensionName, TypeTag
from tslgen.domain.generated_project import BackendProfileRenderModel
from tslgen.io.artifacts import ArtifactSet
from tslgen.lowering.model import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequestSegment,
)
from tslgen.rendering.primitive_function_shapes import (
    PrimitiveFunctionBodyText,
    PrimitiveFunctionNameText,
    PrimitiveFunctionParameterListText,
    PrimitiveFunctionResultTypeText,
    PrimitiveFunctionShapeKey,
    PrimitiveFunctionShapeRenderContext,
    V_ASSIGN_V_V_FUNCTION_SHAPE,
    render_primitive_function_shape,
)
from tslgen.rendering.primitive_render_model import (
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    RenderedImportLine,
    RenderedIncludeLine,
    RenderedModuleText,
    RenderedNamespaceText,
    RenderedPrimitiveBodyText,
    RenderedPrimitiveDefinitionText,
)
from tslgen.rendering.primitive_profile_artifacts import (
    CppPrimitiveProfileInclude,
    PrimitiveProfileArtifactRenderContext,
    RustPrimitiveProfileImport,
    render_primitive_profile_artifacts,
)
from tslgen.rendering.primitive_templates import (
    PrimitiveTemplateRenderContext,
    cpp_primitive_template_context,
    render_primitive_templates,
    rust_primitive_template_context,
)


@dataclass(frozen=True, slots=True)
class SelectedImplementationRenderContext:
    backend_id: PrimitiveBackendId
    extension: ExtensionName
    type_tag: TypeTag
    extension_catalog: ExtensionCatalog | None


class RustIntrinsicBodySafety(Enum):
    PLAIN = "plain"
    UNSAFE_BLOCK = "unsafe_block"


@dataclass(frozen=True, slots=True)
class IntrinsicBodyTokenProfileRenderContext:
    backend_id: PrimitiveBackendId
    logical_path: PrimitiveArtifactLogicalPath
    profile_name: PrimitiveProfileName
    handoff: BackendIntrinsicHandoff
    function_name: PrimitiveFunctionNameText
    result_type: PrimitiveFunctionResultTypeText
    parameters: PrimitiveFunctionParameterListText
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...] = ()
    shape_key: PrimitiveFunctionShapeKey = V_ASSIGN_V_V_FUNCTION_SHAPE
    profile: BackendProfileRenderModel | None = None
    cpp_profile_includes: tuple[CppPrimitiveProfileInclude, ...] = ()
    rust_profile_imports: tuple[RustPrimitiveProfileImport, ...] = ()
    includes: tuple[RenderedIncludeLine, ...] = ()
    imports: tuple[RenderedImportLine, ...] = ()
    namespace_open: RenderedNamespaceText | None = None
    namespace_close: RenderedNamespaceText | None = None
    module_open: RenderedModuleText | None = None
    module_close: RenderedModuleText | None = None
    rust_architecture_module: RustArchitectureModule | None = None
    rust_body_safety: RustIntrinsicBodySafety = RustIntrinsicBodySafety.PLAIN
    selected_implementation: SelectedImplementationRenderContext | None = None


@dataclass(frozen=True, slots=True)
class IntrinsicBodyTokenProfileRenderResult:
    artifacts: ArtifactSet
    body_text: RenderedPrimitiveBodyText | None = None
    definition: RenderedPrimitiveDefinitionText | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_intrinsic_body_token_profile_artifact(
    supplementary_root: Path,
    context: IntrinsicBodyTokenProfileRenderContext,
) -> IntrinsicBodyTokenProfileRenderResult:
    """Render one already-lowered intrinsic body-token stream as a profile artifact."""

    diagnostics = list(_preflight_diagnostics(context))
    request_segments = _request_segments(context.handoff)
    if diagnostics:
        return _diagnostic_result(diagnostics)

    rendered_body, render_diagnostics = _render_body_tokens(context, request_segments)
    diagnostics.extend(render_diagnostics)
    if diagnostics:
        return _diagnostic_result(diagnostics)

    assert rendered_body is not None
    body_text = _primitive_body_text(context, rendered_body)
    shape_result = render_primitive_function_shape(
        supplementary_root,
        PrimitiveFunctionShapeRenderContext(
            backend_id=context.backend_id,
            shape_key=context.shape_key,
            function_name=context.function_name,
            result_type=context.result_type,
            parameters=context.parameters,
            body_text=PrimitiveFunctionBodyText(body_text.text),
        ),
    )
    if shape_result.diagnostics:
        return IntrinsicBodyTokenProfileRenderResult(
            artifacts=ArtifactSet.create(()),
            body_text=body_text,
            diagnostics=shape_result.diagnostics,
        )

    assert shape_result.definition is not None
    if context.profile is not None:
        template_result = render_primitive_profile_artifacts(
            supplementary_root,
            (_profile_context(context, shape_result.definition),),
        )
    else:
        template_result = render_primitive_templates(
            supplementary_root,
            (_template_context(context, shape_result.definition),),
        )
    if template_result.diagnostics:
        return IntrinsicBodyTokenProfileRenderResult(
            artifacts=ArtifactSet.create(()),
            body_text=body_text,
            definition=shape_result.definition,
            diagnostics=template_result.diagnostics,
        )

    return IntrinsicBodyTokenProfileRenderResult(
        artifacts=template_result.artifacts,
        body_text=body_text,
        definition=shape_result.definition,
        diagnostics=(),
    )


def _profile_context(
    context: IntrinsicBodyTokenProfileRenderContext,
    definition: RenderedPrimitiveDefinitionText,
) -> PrimitiveProfileArtifactRenderContext:
    assert context.profile is not None
    return PrimitiveProfileArtifactRenderContext(
        backend_id=context.backend_id,
        logical_path=context.logical_path,
        profile_name=context.profile_name,
        profile=context.profile,
        cpp_includes=context.cpp_profile_includes,
        rust_imports=context.rust_profile_imports,
        primitive_definitions=(definition,),
    )


def _render_body_tokens(
    context: IntrinsicBodyTokenProfileRenderContext,
    request_segments: tuple[BackendIntrinsicHandoffRequestSegment, ...],
) -> tuple[
    CppRenderedBodyTokens | RustRenderedBodyTokens | None,
    tuple[Diagnostic, ...],
]:
    backend_id = context.backend_id.text
    if backend_id == "cpp":
        calls, diagnostics = _render_cpp_calls(context, request_segments)
        if diagnostics:
            return None, diagnostics
        return _cpp_body(context.handoff, calls)
    if backend_id == "rust":
        calls, diagnostics = _render_rust_calls(context, request_segments)
        if diagnostics:
            return None, diagnostics
        return _rust_body(context.handoff, calls)
    return None, (_unsupported_backend_diagnostic(context),)


def _primitive_body_text(
    context: IntrinsicBodyTokenProfileRenderContext,
    rendered_body: CppRenderedBodyTokens | RustRenderedBodyTokens,
) -> RenderedPrimitiveBodyText:
    body = str(rendered_body.text)
    if (
        context.backend_id.text == "rust"
        and context.rust_body_safety is RustIntrinsicBodySafety.UNSAFE_BLOCK
    ):
        body = f"unsafe {{ {body} }}"
    return RenderedPrimitiveBodyText(body)


def _render_cpp_calls(
    context: IntrinsicBodyTokenProfileRenderContext,
    request_segments: tuple[BackendIntrinsicHandoffRequestSegment, ...],
) -> tuple[tuple[CppRenderedIntrinsicCall, ...], tuple[Diagnostic, ...]]:
    calls: list[CppRenderedIntrinsicCall] = []
    diagnostics: list[Diagnostic] = []
    used_modifiers: set[int] = set()

    for segment in request_segments:
        modifiers = _modifiers_for_request(segment, context.translated_modifiers)
        used_modifiers.update(id(modifier) for modifier in modifiers)
        default_policy, default_diagnostics, _ = _default_compose_policy_for_request(
            context,
            segment.request,
        )
        diagnostics.extend(default_diagnostics)
        if default_diagnostics:
            continue
        assembly = assemble_backend_intrinsic_invocation(
            segment.request,
            context.backend_id.text,
            modifiers,
            default_compose_policy=default_policy,
        )
        diagnostics.extend(assembly.diagnostics)
        if assembly.invocation is None:
            continue
        call_result = render_cpp_intrinsic_invocation_call(assembly.invocation)
        diagnostics.extend(call_result.diagnostics)
        if call_result.call is not None:
            calls.append(call_result.call)

    diagnostics.extend(_unused_modifier_diagnostics(context, used_modifiers))
    return tuple(calls), tuple(diagnostics)


def _render_rust_calls(
    context: IntrinsicBodyTokenProfileRenderContext,
    request_segments: tuple[BackendIntrinsicHandoffRequestSegment, ...],
) -> tuple[tuple[RustRenderedIntrinsicCall, ...], tuple[Diagnostic, ...]]:
    calls: list[RustRenderedIntrinsicCall] = []
    diagnostics: list[Diagnostic] = []
    used_modifiers: set[int] = set()

    for segment in request_segments:
        modifiers = _modifiers_for_request(segment, context.translated_modifiers)
        used_modifiers.update(id(modifier) for modifier in modifiers)
        (
            default_policy,
            default_diagnostics,
            name_qualification,
        ) = _default_compose_policy_for_request(
            context,
            segment.request,
        )
        diagnostics.extend(default_diagnostics)
        if default_diagnostics:
            continue
        assembly = assemble_backend_intrinsic_invocation(
            segment.request,
            context.backend_id.text,
            modifiers,
            default_compose_policy=default_policy,
        )
        diagnostics.extend(assembly.diagnostics)
        if assembly.invocation is None:
            continue
        call_result = render_rust_intrinsic_invocation_call(
            assembly.invocation,
            (
                None
                if name_qualification
                == RustIntrinsicNameQualification.ALREADY_QUALIFIED
                else context.rust_architecture_module
            ),
            name_qualification=name_qualification,
        )
        diagnostics.extend(call_result.diagnostics)
        if call_result.call is not None:
            calls.append(call_result.call)

    diagnostics.extend(_unused_modifier_diagnostics(context, used_modifiers))
    return tuple(calls), tuple(diagnostics)


def _cpp_body(
    handoff: BackendIntrinsicHandoff,
    calls: tuple[CppRenderedIntrinsicCall, ...],
) -> tuple[CppRenderedBodyTokens | None, tuple[Diagnostic, ...]]:
    result = render_cpp_body_tokens_from_intrinsic_handoff(handoff, calls)
    return result.body, result.diagnostics


def _rust_body(
    handoff: BackendIntrinsicHandoff,
    calls: tuple[RustRenderedIntrinsicCall, ...],
) -> tuple[RustRenderedBodyTokens | None, tuple[Diagnostic, ...]]:
    result = render_rust_body_tokens_from_intrinsic_handoff(handoff, calls)
    return result.body, result.diagnostics


def _template_context(
    context: IntrinsicBodyTokenProfileRenderContext,
    definition: RenderedPrimitiveDefinitionText,
) -> PrimitiveTemplateRenderContext:
    if context.backend_id.text == "cpp":
        return cpp_primitive_template_context(
            logical_path=context.logical_path.text,
            profile_name=context.profile_name.text,
            includes=_text_tuple(context.includes),
            namespace_open=_optional_text(context.namespace_open),
            namespace_close=_optional_text(context.namespace_close),
            primitive_definitions=(definition.text,),
        )
    return rust_primitive_template_context(
        logical_path=context.logical_path.text,
        profile_name=context.profile_name.text,
        imports=_text_tuple(context.imports),
        module_open=_optional_text(context.module_open),
        module_close=_optional_text(context.module_close),
        primitive_definitions=(definition.text,),
    )


def _preflight_diagnostics(
    context: IntrinsicBodyTokenProfileRenderContext,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if context.backend_id.text not in {"cpp", "rust"}:
        diagnostics.append(_unsupported_backend_diagnostic(context))
    if not _request_segments(context.handoff):
        diagnostics.append(_missing_handoff_request_diagnostic(context.handoff.source))
    return tuple(diagnostics)


def _request_segments(
    handoff: BackendIntrinsicHandoff,
) -> tuple[BackendIntrinsicHandoffRequestSegment, ...]:
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    )


def _modifiers_for_request(
    segment: BackendIntrinsicHandoffRequestSegment,
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...],
) -> tuple[BackendTranslatedIntrinsicModifier, ...]:
    request = segment.request
    if not isinstance(request, BackendIntrinsicComposeHandoffRequest):
        return ()

    field_ids = {id(field) for field in request.modifiers}
    return tuple(modifier for modifier in modifiers if id(modifier.field) in field_ids)


def _default_compose_policy_for_request(
    context: IntrinsicBodyTokenProfileRenderContext,
    request: object,
) -> tuple[
    BackendIntrinsicComposeDefaultPolicy | None,
    tuple[Diagnostic, ...],
    RustIntrinsicNameQualification,
]:
    name_qualification = RustIntrinsicNameQualification.ARCHITECTURE_MODULE
    if not isinstance(request, BackendIntrinsicComposeHandoffRequest):
        return None, (), name_qualification

    explicit_names = _explicit_compose_modifier_names(request)
    if {"prefix", "suffix"}.issubset(explicit_names):
        return None, (), name_qualification

    selected = context.selected_implementation
    if selected is None:
        return (
            None,
            (_missing_selected_context_diagnostic(request.source),),
            name_qualification,
        )
    if selected.backend_id.text != context.backend_id.text:
        return (
            None,
            (_selected_context_backend_mismatch_diagnostic(context, selected),),
            name_qualification,
        )
    if selected.extension_catalog is None:
        return (
            None,
            (_missing_extension_catalog_diagnostic(request.source),),
            name_qualification,
        )

    result = resolve_backend_intrinsic_compose_default_policy(
        selected.extension_catalog,
        selected.backend_id.text,
        selected.extension,
        selected.type_tag,
        request.source,
        needs_prefix="prefix" not in explicit_names,
        needs_suffix="suffix" not in explicit_names,
    )
    if result.policy is not None and (
        selected.backend_id.text == "rust" and "prefix" not in explicit_names
    ):
        name_qualification = RustIntrinsicNameQualification.ALREADY_QUALIFIED
    return result.policy, result.diagnostics, name_qualification


def _explicit_compose_modifier_names(
    request: BackendIntrinsicComposeHandoffRequest,
) -> frozenset[str]:
    return frozenset(field.name for field in request.modifiers)


def _unused_modifier_diagnostics(
    context: IntrinsicBodyTokenProfileRenderContext,
    used_modifiers: set[int],
) -> tuple[Diagnostic, ...]:
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-INTRINSIC-BODY-TOKEN-BRIDGE-UNUSED-MODIFIER-TRANSLATION",
            message=(
                "intrinsic body-token bridge received a translated modifier "
                "that does not belong to any intrinsic compose request segment"
            ),
            location=modifier.source,
        )
        for modifier in context.translated_modifiers
        if id(modifier) not in used_modifiers
    )


def _missing_selected_context_diagnostic(location: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=(
            "TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-SELECTED-IMPLEMENTATION-CONTEXT"
        ),
        message=(
            "intrin_compose default prefix/suffix policy requires the selected "
            "implementation backend, extension, type tag, and extension catalog"
        ),
        location=location,
    )


def _selected_context_backend_mismatch_diagnostic(
    context: IntrinsicBodyTokenProfileRenderContext,
    selected: SelectedImplementationRenderContext,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-INTRINSIC-BODY-TOKEN-BRIDGE-SELECTED-CONTEXT-BACKEND-MISMATCH",
        message=(
            "selected implementation render context backend "
            f"{selected.backend_id.text!r} does not match profile backend "
            f"{context.backend_id.text!r}"
        ),
        location=context.handoff.source,
    )


def _missing_extension_catalog_diagnostic(location: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-EXTENSION-CATALOG",
        message=(
            "selected implementation render context must include the extension "
            "catalog before intrin_compose default policy can be resolved"
        ),
        location=location,
    )


def _unsupported_backend_diagnostic(
    context: IntrinsicBodyTokenProfileRenderContext,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-INTRINSIC-BODY-TOKEN-BRIDGE-UNSUPPORTED-BACKEND",
        message=(
            "intrinsic body-token profile rendering supports only backend "
            f"'cpp' or 'rust'; got {context.backend_id.text!r}"
        ),
        location=context.handoff.source,
    )


def _missing_handoff_request_diagnostic(location: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-INTRINSIC-BODY-TOKEN-BRIDGE-MISSING-HANDOFF-REQUEST",
        message=(
            "intrinsic body-token profile rendering requires at least one "
            "already-lowered backend intrinsic request segment"
        ),
        location=location,
    )


def _diagnostic_result(
    diagnostics: list[Diagnostic],
) -> IntrinsicBodyTokenProfileRenderResult:
    return IntrinsicBodyTokenProfileRenderResult(
        artifacts=ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
    )


def _text_tuple(
    values: tuple[RenderedIncludeLine | RenderedImportLine, ...],
) -> tuple[str, ...]:
    return tuple(value.text for value in values)


def _optional_text(
    value: RenderedNamespaceText | RenderedModuleText | None,
) -> str:
    return "" if value is None else value.text
