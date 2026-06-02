"""Primitive template rendering boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet

CPP_PRIMITIVE_TEMPLATE_PATH = "templates/cpp/primitive.hpp.in"
RUST_PRIMITIVE_TEMPLATE_PATH = "templates/rust/primitive.rs.in"


@dataclass(frozen=True, slots=True)
class PrimitiveTemplateRenderContext:
    backend_id: str
    template_path: str
    logical_path: str
    profile_name: str
    media_type: str
    includes: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    namespace_open: str = ""
    namespace_close: str = ""
    module_open: str = ""
    module_close: str = ""
    primitive_declarations: tuple[str, ...] = ()
    primitive_definitions: tuple[str, ...] = ()
    rendered_body_text: str = ""
    metadata: tuple[ArtifactMetadata, ...] = ()

    def format_values(self) -> dict[str, str]:
        return {
            "artifact_path": self.logical_path,
            "backend_id": self.backend_id,
            "includes": _join_lines(self.includes),
            "imports": _join_lines(self.imports),
            "module_close": self.module_close,
            "module_open": self.module_open,
            "namespace_close": self.namespace_close,
            "namespace_open": self.namespace_open,
            "primitive_declarations": _join_blocks(self.primitive_declarations),
            "primitive_definitions": _join_blocks(self.primitive_definitions),
            "profile_name": self.profile_name,
            "rendered_body_text": self.rendered_body_text,
        }


@dataclass(frozen=True, slots=True)
class PrimitiveTemplateRenderResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...] = ()


_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "artifact_path",
        "backend_id",
        "includes",
        "imports",
        "module_close",
        "module_open",
        "namespace_close",
        "namespace_open",
        "primitive_declarations",
        "primitive_definitions",
        "profile_name",
        "rendered_body_text",
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


def cpp_primitive_template_context(
    *,
    logical_path: str,
    profile_name: str,
    includes: tuple[str, ...] = (),
    namespace_open: str = "",
    namespace_close: str = "",
    primitive_declarations: tuple[str, ...] = (),
    primitive_definitions: tuple[str, ...] = (),
    rendered_body_text: str = "",
) -> PrimitiveTemplateRenderContext:
    metadata = (
        ArtifactMetadata("backend", "cpp"),
        ArtifactMetadata("profile", profile_name),
    )
    return PrimitiveTemplateRenderContext(
        backend_id="cpp",
        template_path=CPP_PRIMITIVE_TEMPLATE_PATH,
        logical_path=logical_path,
        profile_name=profile_name,
        media_type="text/x-c++hdr",
        includes=includes,
        namespace_open=namespace_open,
        namespace_close=namespace_close,
        primitive_declarations=primitive_declarations,
        primitive_definitions=primitive_definitions,
        rendered_body_text=rendered_body_text,
        metadata=metadata,
    )


def rust_primitive_template_context(
    *,
    logical_path: str,
    profile_name: str,
    imports: tuple[str, ...] = (),
    module_open: str = "",
    module_close: str = "",
    primitive_definitions: tuple[str, ...] = (),
    rendered_body_text: str = "",
) -> PrimitiveTemplateRenderContext:
    metadata = (
        ArtifactMetadata("backend", "rust"),
        ArtifactMetadata("profile", profile_name),
    )
    return PrimitiveTemplateRenderContext(
        backend_id="rust",
        template_path=RUST_PRIMITIVE_TEMPLATE_PATH,
        logical_path=logical_path,
        profile_name=profile_name,
        media_type="text/x-rust",
        imports=imports,
        module_open=module_open,
        module_close=module_close,
        primitive_definitions=primitive_definitions,
        rendered_body_text=rendered_body_text,
        metadata=metadata,
    )


def render_primitive_templates(
    supplementary_root: Path,
    contexts: tuple[PrimitiveTemplateRenderContext, ...],
) -> PrimitiveTemplateRenderResult:
    artifacts: list[Artifact] = []
    diagnostics: list[Diagnostic] = []
    root = supplementary_root.resolve()

    for context in sorted(contexts, key=lambda item: item.logical_path):
        artifact, context_diagnostics = _render_context(root, context)
        diagnostics.extend(context_diagnostics)
        if artifact is not None:
            artifacts.append(artifact)

    if diagnostics:
        return PrimitiveTemplateRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    return PrimitiveTemplateRenderResult(artifacts=ArtifactSet.create(tuple(artifacts)))


def _render_context(
    root: Path,
    context: PrimitiveTemplateRenderContext,
) -> tuple[Artifact | None, tuple[Diagnostic, ...]]:
    source = root / context.template_path
    if not source.is_file():
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-TEMPLATE-MISSING-TEMPLATE",
                    message=f"missing primitive template {context.template_path!r}",
                ),
            ),
        )

    template_text = source.read_text(encoding="utf-8")
    values = context.format_values()
    diagnostics = _template_field_diagnostics(
        context.template_path,
        template_text,
        values,
    )
    if diagnostics:
        return None, diagnostics

    return (
        Artifact(
            logical_path=context.logical_path,
            content=template_text.format_map(values),
            media_type=context.media_type,
            metadata=context.metadata,
        ),
        (),
    )


def _template_field_diagnostics(
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
                    code="TSL-PRIMITIVE-TEMPLATE-SEMANTIC-FIELD",
                    message=(
                        f"primitive template {template_path!r} references "
                        f"semantic field {root_name!r}"
                    ),
                )
            )
            continue
        if root_name != field_name:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-TEMPLATE-UNSUPPORTED-FIELD-SHAPE",
                    message=(
                        f"primitive template {template_path!r} uses unsupported "
                        f"field shape {field_name!r}"
                    ),
                )
            )
            continue
        if root_name not in _ALLOWED_TEMPLATE_FIELDS or root_name not in values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-TEMPLATE-UNKNOWN-FIELD",
                    message=(
                        f"primitive template {template_path!r} references "
                        f"unsupported field {root_name!r}"
                    ),
                )
            )
    return _sort_diagnostics(diagnostics)


def _join_lines(lines: tuple[str, ...]) -> str:
    return "\n".join(lines)


def _join_blocks(blocks: tuple[str, ...]) -> str:
    return "\n\n".join(blocks)


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
