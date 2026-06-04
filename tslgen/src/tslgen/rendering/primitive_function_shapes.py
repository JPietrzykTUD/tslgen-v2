"""Primitive function-shape template rendering for already-decided values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.signatures import PrimitiveSignature, SignatureTermKind
from tslgen.rendering.primitive_render_model import (
    PrimitiveBackendId,
    RenderedPrimitiveDefinitionText,
)

CPP_V_ASSIGN_V_V_FUNCTION_TEMPLATE_PATH = "templates/cpp/shapes/v_assign_v_v.hpp.in"
RUST_V_ASSIGN_V_V_FUNCTION_TEMPLATE_PATH = "templates/rust/shapes/v_assign_v_v.rs.in"


@dataclass(frozen=True, slots=True)
class _TextValue:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionShapeKey(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionNameText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionResultTypeText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionParameterListText(_TextValue):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionBodyText(_TextValue):
    pass


V_ASSIGN_V_V_FUNCTION_SHAPE = PrimitiveFunctionShapeKey("v:=(v,v)")


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionShapeSelectionResult:
    shape_key: PrimitiveFunctionShapeKey | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionShapeRenderContext:
    backend_id: PrimitiveBackendId
    shape_key: PrimitiveFunctionShapeKey
    function_name: PrimitiveFunctionNameText
    result_type: PrimitiveFunctionResultTypeText
    parameters: PrimitiveFunctionParameterListText
    body_text: PrimitiveFunctionBodyText

    def format_values(self) -> dict[str, str]:
        return {
            "body_text": self.body_text.text,
            "function_name": self.function_name.text,
            "parameters": self.parameters.text,
            "result_type": self.result_type.text,
        }


@dataclass(frozen=True, slots=True)
class PrimitiveFunctionShapeRenderResult:
    definition: RenderedPrimitiveDefinitionText | None
    diagnostics: tuple[Diagnostic, ...] = ()


_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "body_text",
        "function_name",
        "parameters",
        "result_type",
    }
)

_SEMANTIC_TEMPLATE_FIELDS = frozenset(
    {
        "backend_metadata_key",
        "backend_translation_key",
        "dependency",
        "extension",
        "fallback",
        "feature_gate",
        "intrinsic",
        "intrinsic_name",
        "lowering_request",
        "primitive",
        "primitive_name",
        "selector",
        "signature",
        "signature_shape",
        "source",
        "source_payload",
        "tsil",
        "type",
        "type_spelling",
        "type_tag",
    }
)


def select_primitive_function_shape(
    signature: PrimitiveSignature | None,
    *,
    source: SourceLocation | None = None,
) -> PrimitiveFunctionShapeSelectionResult:
    if signature is None:
        return PrimitiveFunctionShapeSelectionResult(
            shape_key=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-FUNCTION-SHAPE-MISSING-SIGNATURE",
                    message=(
                        "primitive function shape selection requires a typed "
                        "catalog signature model"
                    ),
                    location=source,
                ),
            ),
        )

    if _is_v_assign_v_v(signature):
        return PrimitiveFunctionShapeSelectionResult(
            shape_key=V_ASSIGN_V_V_FUNCTION_SHAPE,
        )

    return PrimitiveFunctionShapeSelectionResult(
        shape_key=None,
        diagnostics=(
            Diagnostic(
                severity="error",
                code="TSL-PRIMITIVE-FUNCTION-SHAPE-UNSUPPORTED-SIGNATURE",
                message=(
                    "primitive function shape template rendering supports only "
                    f"{V_ASSIGN_V_V_FUNCTION_SHAPE.text!r}; got "
                    f"{signature.source_text!r}"
                ),
                location=source,
            ),
        ),
    )


def render_primitive_function_shape(
    supplementary_root: Path,
    context: PrimitiveFunctionShapeRenderContext,
) -> PrimitiveFunctionShapeRenderResult:
    template_path = _template_path(context)
    if template_path is None:
        return PrimitiveFunctionShapeRenderResult(
            definition=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-FUNCTION-SHAPE-UNSUPPORTED-BACKEND",
                    message=(
                        "primitive function shape template rendering does not "
                        f"support backend {context.backend_id.text!r} with shape "
                        f"{context.shape_key.text!r}"
                    ),
                ),
            ),
        )

    source = supplementary_root.resolve() / template_path
    if not source.is_file():
        return PrimitiveFunctionShapeRenderResult(
            definition=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-FUNCTION-SHAPE-MISSING-TEMPLATE",
                    message=f"missing primitive function shape template {template_path!r}",
                ),
            ),
        )

    template_text = source.read_text(encoding="utf-8")
    values = context.format_values()
    diagnostics = _template_field_diagnostics(template_path, template_text, values)
    if diagnostics:
        return PrimitiveFunctionShapeRenderResult(
            definition=None,
            diagnostics=diagnostics,
        )
    return PrimitiveFunctionShapeRenderResult(
        definition=RenderedPrimitiveDefinitionText(template_text.format_map(values)),
    )


def _is_v_assign_v_v(signature: PrimitiveSignature) -> bool:
    return (
        signature.result.kind is SignatureTermKind.VECTOR
        and len(signature.parameters) == 2
        and all(
            parameter.kind is SignatureTermKind.VECTOR
            for parameter in signature.parameters
        )
    )


def _template_path(context: PrimitiveFunctionShapeRenderContext) -> str | None:
    if context.shape_key != V_ASSIGN_V_V_FUNCTION_SHAPE:
        return None
    if context.backend_id.text == "cpp":
        return CPP_V_ASSIGN_V_V_FUNCTION_TEMPLATE_PATH
    if context.backend_id.text == "rust":
        return RUST_V_ASSIGN_V_V_FUNCTION_TEMPLATE_PATH
    return None


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
                    code="TSL-PRIMITIVE-FUNCTION-SHAPE-TEMPLATE-SEMANTIC-FIELD",
                    message=(
                        f"primitive function shape template {template_path!r} "
                        f"references semantic field {root_name!r}"
                    ),
                )
            )
            continue
        if root_name != field_name:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=(
                        "TSL-PRIMITIVE-FUNCTION-SHAPE-TEMPLATE-UNSUPPORTED-FIELD-SHAPE"
                    ),
                    message=(
                        f"primitive function shape template {template_path!r} "
                        f"uses unsupported field shape {field_name!r}"
                    ),
                )
            )
            continue
        if root_name not in _ALLOWED_TEMPLATE_FIELDS or root_name not in values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-FUNCTION-SHAPE-TEMPLATE-UNKNOWN-FIELD",
                    message=(
                        f"primitive function shape template {template_path!r} "
                        f"references unknown field {root_name!r}"
                    ),
                )
            )
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
