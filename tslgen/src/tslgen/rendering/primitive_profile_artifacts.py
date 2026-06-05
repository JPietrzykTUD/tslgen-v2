"""Primitive profile artifact presentation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from string import Formatter

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.generated_project import BackendProfileRenderModel
from tslgen.io.artifacts import ArtifactSet
from tslgen.rendering.primitive_render_model import (
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    RenderedImportLine,
    RenderedIncludeLine,
    RenderedModuleText,
    RenderedNamespaceText,
    RenderedPrimitiveBodyText,
    RenderedPrimitiveDeclarationText,
    RenderedPrimitiveDefinitionText,
)
from tslgen.rendering.primitive_templates import (
    PrimitiveTemplateRenderContext,
    PrimitiveTemplateRenderResult,
    cpp_primitive_template_context,
    render_primitive_templates,
    rust_primitive_template_context,
)

CPP_PRIMITIVE_PROFILE_SYSTEM_INCLUDE_TEMPLATE_PATH = (
    "templates/cpp/primitive_profile/system_include.hpp.in"
)
CPP_PRIMITIVE_PROFILE_LOCAL_INCLUDE_TEMPLATE_PATH = (
    "templates/cpp/primitive_profile/local_include.hpp.in"
)
CPP_PRIMITIVE_PROFILE_NAMESPACE_OPEN_TEMPLATE_PATH = (
    "templates/cpp/primitive_profile/namespace_open.hpp.in"
)
CPP_PRIMITIVE_PROFILE_NAMESPACE_CLOSE_TEMPLATE_PATH = (
    "templates/cpp/primitive_profile/namespace_close.hpp.in"
)
RUST_PRIMITIVE_PROFILE_IMPORT_TEMPLATE_PATH = (
    "templates/rust/primitive_profile/import.rs.in"
)
RUST_PRIMITIVE_PROFILE_MODULE_OPEN_TEMPLATE_PATH = (
    "templates/rust/primitive_profile/module_open.rs.in"
)

class CppPrimitiveProfileIncludeStyle(Enum):
    SYSTEM = "system"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class CppPrimitiveProfileInclude:
    target: str
    style: CppPrimitiveProfileIncludeStyle = CppPrimitiveProfileIncludeStyle.SYSTEM


@dataclass(frozen=True, slots=True)
class RustPrimitiveProfileImport:
    path: str


@dataclass(frozen=True, slots=True)
class PrimitiveProfileArtifactRenderContext:
    backend_id: PrimitiveBackendId
    logical_path: PrimitiveArtifactLogicalPath
    profile_name: PrimitiveProfileName
    profile: BackendProfileRenderModel
    cpp_includes: tuple[CppPrimitiveProfileInclude, ...] = ()
    rust_imports: tuple[RustPrimitiveProfileImport, ...] = ()
    primitive_declarations: tuple[RenderedPrimitiveDeclarationText, ...] = ()
    primitive_definitions: tuple[RenderedPrimitiveDefinitionText, ...] = ()
    rendered_body_text: RenderedPrimitiveBodyText | None = None


@dataclass(frozen=True, slots=True)
class PrimitiveProfileTemplateContextRenderResult:
    contexts: tuple[PrimitiveTemplateRenderContext, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class PrimitiveProfileArtifactRenderResult:
    artifacts: ArtifactSet
    contexts: tuple[PrimitiveTemplateRenderContext, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "family",
        "import_path",
        "include_target",
        "namespace",
        "profile_name",
        "rust_module",
    }
)

_SEMANTIC_TEMPLATE_FIELDS = frozenset(
    {
        "backend_metadata_key",
        "backend_translation_key",
        "dependency",
        "dependency_rules",
        "extension",
        "fallback",
        "feature_gate",
        "intrinsic",
        "intrinsic_name",
        "lowering_request",
        "overload",
        "primitive",
        "primitive_name",
        "primitive_selector",
        "selector",
        "source",
        "source_payload",
        "tsil",
        "type",
        "type_spelling",
        "type_tag",
    }
)


def build_primitive_profile_template_contexts(
    supplementary_root: Path,
    contexts: tuple[PrimitiveProfileArtifactRenderContext, ...],
) -> PrimitiveProfileTemplateContextRenderResult:
    root = supplementary_root.resolve()
    templates, template_diagnostics = _load_templates(root, _needed_templates(contexts))
    if template_diagnostics:
        return PrimitiveProfileTemplateContextRenderResult(
            diagnostics=_sort_diagnostics(list(template_diagnostics)),
        )

    rendered_contexts: list[PrimitiveTemplateRenderContext] = []
    diagnostics: list[Diagnostic] = []
    for context in sorted(contexts, key=lambda item: item.logical_path.text):
        rendered, context_diagnostics = _template_context(context, templates)
        diagnostics.extend(context_diagnostics)
        if rendered is not None:
            rendered_contexts.append(rendered)

    if diagnostics:
        return PrimitiveProfileTemplateContextRenderResult(
            diagnostics=_sort_diagnostics(diagnostics),
        )
    return PrimitiveProfileTemplateContextRenderResult(contexts=tuple(rendered_contexts))


def render_primitive_profile_artifacts(
    supplementary_root: Path,
    contexts: tuple[PrimitiveProfileArtifactRenderContext, ...],
) -> PrimitiveProfileArtifactRenderResult:
    context_result = build_primitive_profile_template_contexts(
        supplementary_root,
        contexts,
    )
    if context_result.diagnostics:
        return PrimitiveProfileArtifactRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=context_result.diagnostics,
        )

    template_result = render_primitive_templates(
        supplementary_root,
        context_result.contexts,
    )
    return PrimitiveProfileArtifactRenderResult(
        artifacts=template_result.artifacts,
        contexts=context_result.contexts,
        diagnostics=template_result.diagnostics,
    )


def _needed_templates(
    contexts: tuple[PrimitiveProfileArtifactRenderContext, ...],
) -> tuple[str, ...]:
    paths: set[str] = set()
    for context in contexts:
        if context.backend_id.text == "cpp":
            paths.add(CPP_PRIMITIVE_PROFILE_NAMESPACE_OPEN_TEMPLATE_PATH)
            paths.add(CPP_PRIMITIVE_PROFILE_NAMESPACE_CLOSE_TEMPLATE_PATH)
            paths.update(_cpp_include_template_path(include) for include in context.cpp_includes)
        elif context.backend_id.text == "rust":
            paths.add(RUST_PRIMITIVE_PROFILE_MODULE_OPEN_TEMPLATE_PATH)
            if context.rust_imports:
                paths.add(RUST_PRIMITIVE_PROFILE_IMPORT_TEMPLATE_PATH)
    return tuple(sorted(paths))


def _template_context(
    context: PrimitiveProfileArtifactRenderContext,
    templates: dict[str, str],
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    backend_id = context.backend_id.text
    diagnostics = list(_context_diagnostics(context))
    if diagnostics:
        return None, tuple(diagnostics)
    if backend_id == "cpp":
        return _cpp_template_context(context, templates)
    if backend_id == "rust":
        return _rust_template_context(context, templates)
    return None, (_unsupported_backend_diagnostic(context),)


def _cpp_template_context(
    context: PrimitiveProfileArtifactRenderContext,
    templates: dict[str, str],
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    includes: list[RenderedIncludeLine] = []
    for include in context.cpp_includes:
        template_path = _cpp_include_template_path(include)
        rendered, render_diagnostics = _render_template(
            template_path,
            templates[template_path],
            {"include_target": include.target},
        )
        diagnostics.extend(render_diagnostics)
        if rendered is not None:
            includes.append(RenderedIncludeLine(rendered.rstrip()))

    profile_values = _profile_values(context.profile)
    namespace_open, open_diagnostics = _render_template(
        CPP_PRIMITIVE_PROFILE_NAMESPACE_OPEN_TEMPLATE_PATH,
        templates[CPP_PRIMITIVE_PROFILE_NAMESPACE_OPEN_TEMPLATE_PATH],
        profile_values,
    )
    namespace_close, close_diagnostics = _render_template(
        CPP_PRIMITIVE_PROFILE_NAMESPACE_CLOSE_TEMPLATE_PATH,
        templates[CPP_PRIMITIVE_PROFILE_NAMESPACE_CLOSE_TEMPLATE_PATH],
        profile_values,
    )
    diagnostics.extend(open_diagnostics)
    diagnostics.extend(close_diagnostics)
    if diagnostics:
        return None, tuple(diagnostics)
    assert namespace_open is not None
    assert namespace_close is not None
    return (
        cpp_primitive_template_context(
            logical_path=context.logical_path.text,
            profile_name=context.profile_name.text,
            includes=tuple(include.text for include in includes),
            namespace_open=RenderedNamespaceText(namespace_open.rstrip()).text,
            namespace_close=RenderedNamespaceText(namespace_close.rstrip()).text,
            primitive_declarations=tuple(
                declaration.text for declaration in context.primitive_declarations
            ),
            primitive_definitions=tuple(
                definition.text for definition in context.primitive_definitions
            ),
            rendered_body_text=_optional_body(context),
        ),
        (),
    )


def _rust_template_context(
    context: PrimitiveProfileArtifactRenderContext,
    templates: dict[str, str],
) -> tuple[PrimitiveTemplateRenderContext | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    imports: list[RenderedImportLine] = []
    for rust_import in context.rust_imports:
        rendered, render_diagnostics = _render_template(
            RUST_PRIMITIVE_PROFILE_IMPORT_TEMPLATE_PATH,
            templates[RUST_PRIMITIVE_PROFILE_IMPORT_TEMPLATE_PATH],
            {"import_path": rust_import.path},
        )
        diagnostics.extend(render_diagnostics)
        if rendered is not None:
            imports.append(RenderedImportLine(rendered.rstrip()))

    module_open, module_diagnostics = _render_template(
        RUST_PRIMITIVE_PROFILE_MODULE_OPEN_TEMPLATE_PATH,
        templates[RUST_PRIMITIVE_PROFILE_MODULE_OPEN_TEMPLATE_PATH],
        _profile_values(context.profile),
    )
    diagnostics.extend(module_diagnostics)
    if diagnostics:
        return None, tuple(diagnostics)
    assert module_open is not None
    return (
        rust_primitive_template_context(
            logical_path=context.logical_path.text,
            profile_name=context.profile_name.text,
            imports=tuple(rust_import.text for rust_import in imports),
            module_open=RenderedModuleText(module_open.rstrip()).text,
            primitive_definitions=tuple(
                definition.text for definition in context.primitive_definitions
            ),
            rendered_body_text=_optional_body(context),
        ),
        (),
    )


def _cpp_include_template_path(include: CppPrimitiveProfileInclude) -> str:
    if include.style == CppPrimitiveProfileIncludeStyle.LOCAL:
        return CPP_PRIMITIVE_PROFILE_LOCAL_INCLUDE_TEMPLATE_PATH
    return CPP_PRIMITIVE_PROFILE_SYSTEM_INCLUDE_TEMPLATE_PATH


def _context_diagnostics(
    context: PrimitiveProfileArtifactRenderContext,
) -> tuple[Diagnostic, ...]:
    backend_id = context.backend_id.text
    if backend_id == "cpp" and context.rust_imports:
        return (_wrong_backend_field_diagnostic(context, "rust_imports"),)
    if backend_id == "rust" and context.cpp_includes:
        return (_wrong_backend_field_diagnostic(context, "cpp_includes"),)
    return ()


def _wrong_backend_field_diagnostic(
    context: PrimitiveProfileArtifactRenderContext,
    field_name: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PRIMITIVE-PROFILE-WRONG-BACKEND-FIELD",
        message=(
            f"primitive profile artifact backend {context.backend_id.text!r} "
            f"does not consume field {field_name!r}"
        ),
    )


def _unsupported_backend_diagnostic(
    context: PrimitiveProfileArtifactRenderContext,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-PRIMITIVE-PROFILE-UNSUPPORTED-BACKEND",
        message=(
            "primitive profile artifact rendering supports only backend "
            f"'cpp' or 'rust'; got {context.backend_id.text!r}"
        ),
    )


def _load_templates(
    root: Path,
    relative_paths: tuple[str, ...],
) -> tuple[dict[str, str], tuple[Diagnostic, ...]]:
    templates: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    for relative_path in relative_paths:
        path = root / relative_path
        if not path.is_file():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
                    message=f"missing primitive profile template {relative_path!r}",
                )
            )
            continue
        templates[relative_path] = path.read_text(encoding="utf-8")
    return templates, tuple(diagnostics)


def _render_template(
    template_path: str,
    template_text: str,
    values: dict[str, str],
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    diagnostics = _template_diagnostics(template_path, template_text, values)
    if diagnostics:
        return None, diagnostics
    return template_text.format_map(values), ()


def _template_diagnostics(
    template_path: str,
    template_text: str,
    values: dict[str, str],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for _, field_name, _, _ in Formatter().parse(template_text):
        if field_name is None:
            continue
        root_name = field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        if root_name in _SEMANTIC_TEMPLATE_FIELDS:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-PROFILE-SEMANTIC-FIELD",
                    message=(
                        f"primitive profile template {template_path!r} references "
                        f"semantic field {root_name!r}"
                    ),
                )
            )
            continue
        if root_name != field_name:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-PROFILE-UNSUPPORTED-FIELD-SHAPE",
                    message=(
                        f"primitive profile template {template_path!r} uses "
                        f"unsupported field shape {field_name!r}"
                    ),
                )
            )
            continue
        if root_name not in _ALLOWED_TEMPLATE_FIELDS or root_name not in values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-PROFILE-UNKNOWN-FIELD",
                    message=(
                        f"primitive profile template {template_path!r} references "
                        f"unsupported field {root_name!r}"
                    ),
                )
            )
    return tuple(diagnostics)


def _profile_values(profile: BackendProfileRenderModel) -> dict[str, str]:
    return {
        "family": str(profile.family),
        "namespace": str(profile.file_stem),
        "profile_name": str(profile.profile_name),
        "rust_module": str(profile.rust_module),
    }


def _optional_body(context: PrimitiveProfileArtifactRenderContext) -> str:
    if context.rendered_body_text is None:
        return ""
    return context.rendered_body_text.text


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
