"""Typed primitive render models for already-decided presentation values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from tslgen.core.diagnostics import Diagnostic
from tslgen.rendering.primitive_templates import (
    PrimitiveTemplateRenderContext,
    cpp_primitive_template_context,
    rust_primitive_template_context,
)


@dataclass(frozen=True, slots=True)
class _TextValue:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class PrimitiveBackendId(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveProfileName(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveArtifactLogicalPath(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveRenderSortKey(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedIncludeLine(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedImportLine(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedNamespaceText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedModuleText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedPrimitiveDeclarationText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedPrimitiveDefinitionText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RenderedPrimitiveBodyText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class RawTsilPrimitiveRenderValue(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class UnresolvedPrimitiveRenderValue(_TextValue):
    pass


PrimitiveRenderInvalidValue = (
    RawTsilPrimitiveRenderValue | UnresolvedPrimitiveRenderValue
)
PrimitiveDeclarationValue = (
    RenderedPrimitiveDeclarationText | PrimitiveRenderInvalidValue
)
PrimitiveDefinitionValue = RenderedPrimitiveDefinitionText | PrimitiveRenderInvalidValue
PrimitiveBodyValue = RenderedPrimitiveBodyText | PrimitiveRenderInvalidValue
PrimitiveIncludeValue = RenderedIncludeLine | PrimitiveRenderInvalidValue
PrimitiveImportValue = RenderedImportLine | PrimitiveRenderInvalidValue
PrimitiveNamespaceValue = RenderedNamespaceText | PrimitiveRenderInvalidValue
PrimitiveModuleValue = RenderedModuleText | PrimitiveRenderInvalidValue


@dataclass(frozen=True, slots=True)
class PrimitiveRenderRecord:
    sort_key: PrimitiveRenderSortKey
    declarations: tuple[PrimitiveDeclarationValue, ...] = ()
    definitions: tuple[PrimitiveDefinitionValue, ...] = ()
    body_text: PrimitiveBodyValue | None = None


@dataclass(frozen=True, slots=True)
class BackendPrimitiveRenderModel:
    backend_id: PrimitiveBackendId
    logical_path: PrimitiveArtifactLogicalPath
    profile_name: PrimitiveProfileName
    includes: tuple[PrimitiveIncludeValue, ...] = ()
    imports: tuple[PrimitiveImportValue, ...] = ()
    namespace_open: PrimitiveNamespaceValue | None = None
    namespace_close: PrimitiveNamespaceValue | None = None
    module_open: PrimitiveModuleValue | None = None
    module_close: PrimitiveModuleValue | None = None
    primitives: tuple[PrimitiveRenderRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PrimitiveRenderContextAdaptationResult:
    contexts: tuple[PrimitiveTemplateRenderContext, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


_RenderedValueT = TypeVar("_RenderedValueT", bound=_TextValue)


def cpp_primitive_render_model(
    *,
    logical_path: PrimitiveArtifactLogicalPath,
    profile_name: PrimitiveProfileName,
    includes: tuple[PrimitiveIncludeValue, ...] = (),
    namespace_open: PrimitiveNamespaceValue | None = None,
    namespace_close: PrimitiveNamespaceValue | None = None,
    primitives: tuple[PrimitiveRenderRecord, ...] = (),
) -> BackendPrimitiveRenderModel:
    return BackendPrimitiveRenderModel(
        backend_id=PrimitiveBackendId("cpp"),
        logical_path=logical_path,
        profile_name=profile_name,
        includes=includes,
        namespace_open=namespace_open,
        namespace_close=namespace_close,
        primitives=primitives,
    )


def rust_primitive_render_model(
    *,
    logical_path: PrimitiveArtifactLogicalPath,
    profile_name: PrimitiveProfileName,
    imports: tuple[PrimitiveImportValue, ...] = (),
    module_open: PrimitiveModuleValue | None = None,
    module_close: PrimitiveModuleValue | None = None,
    primitives: tuple[PrimitiveRenderRecord, ...] = (),
) -> BackendPrimitiveRenderModel:
    return BackendPrimitiveRenderModel(
        backend_id=PrimitiveBackendId("rust"),
        logical_path=logical_path,
        profile_name=profile_name,
        imports=imports,
        module_open=module_open,
        module_close=module_close,
        primitives=primitives,
    )


def adapt_primitive_render_models(
    models: tuple[BackendPrimitiveRenderModel, ...],
) -> PrimitiveRenderContextAdaptationResult:
    contexts: list[PrimitiveTemplateRenderContext] = []
    diagnostics: list[Diagnostic] = []

    for model in sorted(models, key=lambda item: item.logical_path.text):
        context, context_diagnostics = _adapt_model(model)
        diagnostics.extend(context_diagnostics)
        if context is not None:
            contexts.append(context)

    if diagnostics:
        return PrimitiveRenderContextAdaptationResult(
            contexts=(),
            diagnostics=_sort_diagnostics(diagnostics),
        )
    return PrimitiveRenderContextAdaptationResult(contexts=tuple(contexts))


def _adapt_model(
    model: BackendPrimitiveRenderModel,
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    backend_id = model.backend_id.text
    if backend_id == "cpp":
        return _adapt_cpp_model(model)
    if backend_id == "rust":
        return _adapt_rust_model(model)
    return (
        None,
        (
            Diagnostic(
                severity="error",
                code="TSL-PRIMITIVE-RENDER-CONTEXT-UNKNOWN-BACKEND",
                message=f"unsupported primitive render backend {backend_id!r}",
            ),
        ),
    )


def _adapt_cpp_model(
    model: BackendPrimitiveRenderModel,
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    includes = _collect_texts(
        model.includes,
        RenderedIncludeLine,
        "C++ include line",
        diagnostics,
    )
    namespace_open = _optional_text(
        model.namespace_open,
        RenderedNamespaceText,
        "C++ namespace opening text",
        diagnostics,
    )
    namespace_close = _optional_text(
        model.namespace_close,
        RenderedNamespaceText,
        "C++ namespace closing text",
        diagnostics,
    )
    primitive_declarations, primitive_definitions, rendered_body_text = (
        _collect_primitive_text(model.primitives, diagnostics)
    )
    diagnostics.extend(
        _unexpected_backend_fields(
            model,
            disallowed=("imports", "module_open", "module_close"),
            backend_id="cpp",
        )
    )
    if diagnostics:
        return None, tuple(diagnostics)
    return (
        cpp_primitive_template_context(
            logical_path=model.logical_path.text,
            profile_name=model.profile_name.text,
            includes=includes,
            namespace_open=namespace_open,
            namespace_close=namespace_close,
            primitive_declarations=primitive_declarations,
            primitive_definitions=primitive_definitions,
            rendered_body_text=rendered_body_text,
        ),
        (),
    )


def _adapt_rust_model(
    model: BackendPrimitiveRenderModel,
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    imports = _collect_texts(
        model.imports,
        RenderedImportLine,
        "Rust import line",
        diagnostics,
    )
    module_open = _optional_text(
        model.module_open,
        RenderedModuleText,
        "Rust module opening text",
        diagnostics,
    )
    module_close = _optional_text(
        model.module_close,
        RenderedModuleText,
        "Rust module closing text",
        diagnostics,
    )
    _, primitive_definitions, rendered_body_text = _collect_primitive_text(
        model.primitives,
        diagnostics,
    )
    diagnostics.extend(
        _unexpected_backend_fields(
            model,
            disallowed=("includes", "namespace_open", "namespace_close"),
            backend_id="rust",
        )
    )
    if diagnostics:
        return None, tuple(diagnostics)
    return (
        rust_primitive_template_context(
            logical_path=model.logical_path.text,
            profile_name=model.profile_name.text,
            imports=imports,
            module_open=module_open,
            module_close=module_close,
            primitive_definitions=primitive_definitions,
            rendered_body_text=rendered_body_text,
        ),
        (),
    )


def _collect_primitive_text(
    primitives: tuple[PrimitiveRenderRecord, ...],
    diagnostics: list[Diagnostic],
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    declarations: list[str] = []
    definitions: list[str] = []
    body_blocks: list[str] = []

    for primitive in sorted(primitives, key=lambda item: item.sort_key.text):
        declarations.extend(
            _collect_texts(
                primitive.declarations,
                RenderedPrimitiveDeclarationText,
                f"primitive {primitive.sort_key.text!r} declaration text",
                diagnostics,
            )
        )
        definitions.extend(
            _collect_texts(
                primitive.definitions,
                RenderedPrimitiveDefinitionText,
                f"primitive {primitive.sort_key.text!r} definition text",
                diagnostics,
            )
        )
        body_text = _optional_text(
            primitive.body_text,
            RenderedPrimitiveBodyText,
            f"primitive {primitive.sort_key.text!r} body text",
            diagnostics,
        )
        if body_text:
            body_blocks.append(body_text)

    return tuple(declarations), tuple(definitions), "\n\n".join(body_blocks)


def _collect_texts(
    values: tuple[_TextValue, ...],
    expected_type: type[_RenderedValueT],
    label: str,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    result: list[str] = []
    if not isinstance(values, tuple):
        diagnostics.append(_unsupported_shape_diagnostic(label, values))
        return ()
    for value in values:
        text = _accepted_text(value, expected_type, label, diagnostics)
        if text is not None:
            result.append(text)
    return tuple(result)


def _optional_text(
    value: _TextValue | None,
    expected_type: type[_RenderedValueT],
    label: str,
    diagnostics: list[Diagnostic],
) -> str:
    if value is None:
        return ""
    text = _accepted_text(value, expected_type, label, diagnostics)
    return "" if text is None else text


def _accepted_text(
    value: object,
    expected_type: type[_RenderedValueT],
    label: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    if isinstance(value, expected_type):
        return value.text
    if isinstance(value, RawTsilPrimitiveRenderValue):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PRIMITIVE-RENDER-CONTEXT-RAW-TSIL",
                message=(
                    f"{label} received raw TSIL/source text {value.text!r}; "
                    "primitive render models require already-rendered text"
                ),
            )
        )
        return None
    if isinstance(value, UnresolvedPrimitiveRenderValue):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PRIMITIVE-RENDER-CONTEXT-UNRESOLVED-VALUE",
                message=(
                    f"{label} received unresolved semantic value {value.text!r}; "
                    "primitive render models require already-decided values"
                ),
            )
        )
        return None
    diagnostics.append(_unsupported_shape_diagnostic(label, value))
    return None


def _unexpected_backend_fields(
    model: BackendPrimitiveRenderModel,
    *,
    disallowed: tuple[str, ...],
    backend_id: str,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for field_name in disallowed:
        value = getattr(model, field_name)
        if value:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-RENDER-CONTEXT-UNSUPPORTED-BACKEND-FIELD",
                    message=(
                        f"primitive render backend {backend_id!r} does not "
                        f"consume field {field_name!r}"
                    ),
                )
            )
    return tuple(diagnostics)


def _unsupported_shape_diagnostic(label: str, value: object) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PRIMITIVE-RENDER-CONTEXT-UNSUPPORTED-VALUE",
        message=(
            f"{label} expected typed already-rendered presentation text, "
            f"got {type(value).__name__}"
        ),
    )


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
