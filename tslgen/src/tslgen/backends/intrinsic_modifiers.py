"""Backend intrinsic compose modifier translation over typed handoff values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
)
from tslgen.domain.catalog import ExtensionCatalog, ExtensionName, TypeTag
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierIntegerOperand,
    BackendIntrinsicModifierName,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicSuffixValueRequest,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
)

BackendIntrinsicModifierFragmentText = NewType(
    "BackendIntrinsicModifierFragmentText",
    str,
)
BackendIntrinsicInfixSeparatorText = NewType(
    "BackendIntrinsicInfixSeparatorText",
    str,
)
BackendIntrinsicModifierValueKind = Literal[
    "literal_fragment",
    "infix_separator",
    "immediate_literal",
]
BackendIntrinsicStyle = NewType("BackendIntrinsicStyle", str)

_FRAGMENT_MODIFIER_NAMES = frozenset({"suffix", "post", "infix"})
_TO_TYPE_SUFFIX_SYMBOL = "to_type_suffix"
_PLACEHOLDER_PATTERN = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class BackendIntrinsicLiteralFragment:
    text: BackendIntrinsicModifierFragmentText


@dataclass(frozen=True, slots=True)
class BackendIntrinsicInfixSeparator:
    text: BackendIntrinsicInfixSeparatorText


@dataclass(frozen=True, slots=True)
class BackendIntrinsicImmediateLiteral:
    argument_index: int
    value: int


BackendTranslatedIntrinsicModifierValue = (
    BackendIntrinsicLiteralFragment
    | BackendIntrinsicInfixSeparator
    | BackendIntrinsicImmediateLiteral
)


@dataclass(frozen=True, slots=True)
class BackendTranslatedIntrinsicModifier:
    backend: BackendId
    field: BackendIntrinsicModifierField
    name: BackendIntrinsicModifierName
    value: BackendTranslatedIntrinsicModifierValue
    source: SourceLocation
    metadata_key: BackendTranslationKey | None = None
    metadata_source: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierTranslationResult:
    modifier: BackendTranslatedIntrinsicModifier | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierTranslationBatchResult:
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierTranslationContext:
    backend: BackendId
    selected_extension: ExtensionName
    extension_catalog: ExtensionCatalog
    metadata_catalog: BackendMetadataCatalog | None


@dataclass(frozen=True, slots=True)
class BackendIntrinsicTypeSuffixTranslationRule:
    intrinsic_style: BackendIntrinsicStyle
    type_tag: TypeTag
    metadata_key: BackendTranslationKey


_TYPE_SUFFIX_TRANSLATION_RULES: tuple[
    BackendIntrinsicTypeSuffixTranslationRule,
    ...,
] = (
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("si8"),
        BackendTranslationKey("intrinsic_suffix_x86_si8"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("si16"),
        BackendTranslationKey("intrinsic_suffix_x86_si16"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("si32"),
        BackendTranslationKey("intrinsic_suffix_x86_si32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("si64"),
        BackendTranslationKey("intrinsic_suffix_x86_si64"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("ui8"),
        BackendTranslationKey("intrinsic_suffix_x86_ui8"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("ui16"),
        BackendTranslationKey("intrinsic_suffix_x86_ui16"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("ui32"),
        BackendTranslationKey("intrinsic_suffix_x86_ui32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("ui64"),
        BackendTranslationKey("intrinsic_suffix_x86_ui64"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("f32"),
        BackendTranslationKey("intrinsic_suffix_x86_f32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("x86"),
        TypeTag("f64"),
        BackendTranslationKey("intrinsic_suffix_x86_f64"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("si8"),
        BackendTranslationKey("intrinsic_suffix_arm_si8"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("si16"),
        BackendTranslationKey("intrinsic_suffix_arm_si16"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("si32"),
        BackendTranslationKey("intrinsic_suffix_arm_si32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("si64"),
        BackendTranslationKey("intrinsic_suffix_arm_si64"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("ui8"),
        BackendTranslationKey("intrinsic_suffix_arm_ui8"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("ui16"),
        BackendTranslationKey("intrinsic_suffix_arm_ui16"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("ui32"),
        BackendTranslationKey("intrinsic_suffix_arm_ui32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("ui64"),
        BackendTranslationKey("intrinsic_suffix_arm_ui64"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("f32"),
        BackendTranslationKey("intrinsic_suffix_arm_f32"),
    ),
    BackendIntrinsicTypeSuffixTranslationRule(
        BackendIntrinsicStyle("arm"),
        TypeTag("f64"),
        BackendTranslationKey("intrinsic_suffix_arm_f64"),
    ),
)


def translate_backend_intrinsic_modifier_field(
    field: BackendIntrinsicModifierField,
    backend: BackendId | str,
) -> BackendIntrinsicModifierTranslationResult:
    """Translate one final literal intrinsic compose modifier field."""

    backend_id = BackendId(str(backend))

    if isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_backend_value_operand_diagnostic(field),),
        )

    if field.name in _FRAGMENT_MODIFIER_NAMES:
        return _translate_literal_fragment(field, backend_id)

    if field.name == "infix_sep":
        return _translate_infix_separator(field, backend_id)

    if field.name == "immediate":
        return _translate_immediate_literal(field, backend_id)

    return BackendIntrinsicModifierTranslationResult(
        modifier=None,
        diagnostics=(_unsupported_field_diagnostic(field),),
    )


def translate_backend_intrinsic_modifier_field_with_context(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationResult:
    """Translate one modifier using context for selected semantic families."""

    suffix_result = _translate_type_derived_suffix_modifier(field, context)
    if suffix_result is not None:
        return suffix_result
    return translate_backend_intrinsic_modifier_field(field, context.backend)


def translate_backend_intrinsic_compose_modifiers_with_context(
    request: BackendIntrinsicComposeHandoffRequest,
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate compose modifier fields with selected backend context."""

    return translate_backend_intrinsic_modifier_fields_with_context(
        request.modifiers,
        context,
    )


def translate_backend_intrinsic_modifier_fields_with_context(
    fields: tuple[BackendIntrinsicModifierField, ...],
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate modifier fields in source order with selected backend context."""

    modifiers: list[BackendTranslatedIntrinsicModifier] = []
    diagnostics: list[Diagnostic] = []

    for field in fields:
        result = translate_backend_intrinsic_modifier_field_with_context(
            field,
            context,
        )
        diagnostics.extend(result.diagnostics)
        if result.modifier is not None:
            modifiers.append(result.modifier)

    return BackendIntrinsicModifierTranslationBatchResult(
        modifiers=tuple(modifiers),
        diagnostics=tuple(diagnostics),
    )


def translate_backend_intrinsic_handoff_request_modifiers_with_context(
    request: BackendIntrinsicHandoffRequest,
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate contextual compose modifiers; diagnose direct intrinsics."""

    if isinstance(request, BackendIntrinsicComposeHandoffRequest):
        return translate_backend_intrinsic_compose_modifiers_with_context(
            request,
            context,
        )

    if isinstance(request, BackendDirectIntrinsicHandoffRequest):
        return BackendIntrinsicModifierTranslationBatchResult(
            modifiers=(),
            diagnostics=(_unsupported_direct_intrinsic_diagnostic(request),),
        )

    return BackendIntrinsicModifierTranslationBatchResult(
        modifiers=(),
        diagnostics=(_unsupported_request_diagnostic(request),),
    )


def translate_backend_intrinsic_compose_modifiers(
    request: BackendIntrinsicComposeHandoffRequest,
    backend: BackendId | str,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate compose modifier fields in source order."""

    return translate_backend_intrinsic_modifier_fields(
        request.modifiers,
        backend,
    )


def translate_backend_intrinsic_modifier_fields(
    fields: tuple[BackendIntrinsicModifierField, ...],
    backend: BackendId | str,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate a sequence of modifier fields and accumulate diagnostics."""

    modifiers: list[BackendTranslatedIntrinsicModifier] = []
    diagnostics: list[Diagnostic] = []

    for field in fields:
        result = translate_backend_intrinsic_modifier_field(field, backend)
        diagnostics.extend(result.diagnostics)
        if result.modifier is not None:
            modifiers.append(result.modifier)

    return BackendIntrinsicModifierTranslationBatchResult(
        modifiers=tuple(modifiers),
        diagnostics=tuple(diagnostics),
    )


def translate_backend_intrinsic_handoff_request_modifiers(
    request: BackendIntrinsicHandoffRequest,
    backend: BackendId | str,
) -> BackendIntrinsicModifierTranslationBatchResult:
    """Translate modifiers for compose requests; diagnose direct intrinsics."""

    if isinstance(request, BackendIntrinsicComposeHandoffRequest):
        return translate_backend_intrinsic_compose_modifiers(request, backend)

    if isinstance(request, BackendDirectIntrinsicHandoffRequest):
        return BackendIntrinsicModifierTranslationBatchResult(
            modifiers=(),
            diagnostics=(_unsupported_direct_intrinsic_diagnostic(request),),
        )

    return BackendIntrinsicModifierTranslationBatchResult(
        modifiers=(),
        diagnostics=(_unsupported_request_diagnostic(request),),
    )


def _translate_type_derived_suffix_modifier(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationResult | None:
    if field.name != "suffix":
        return None
    if not isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return None
    request = field.value.request
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return None
    argument = request.argument
    if not isinstance(argument, BackendValueTypeOperand):
        return None
    if not isinstance(argument.value, LoweredScalarTypeIdentity):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_lowered_type_diagnostic(field, argument),),
        )

    catalog = context.metadata_catalog
    if catalog is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_metadata_diagnostic(field),),
        )

    backend = BackendId(str(context.backend))
    if backend not in catalog.backends:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_backend_diagnostic(field, backend, catalog),),
        )

    extension = context.extension_catalog.get(str(context.selected_extension))
    if extension is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unknown_extension_diagnostic(field, context),),
        )

    if extension.intrinsic_style is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_intrinsic_style_diagnostic(field, extension.source),),
        )

    style = BackendIntrinsicStyle(extension.intrinsic_style)
    rule = _type_suffix_rule(style, argument.value.type_tag)
    if rule is None:
        if style not in _known_type_suffix_styles():
            diagnostic = _unsupported_intrinsic_style_diagnostic(
                field,
                style,
                extension.source,
            )
        else:
            diagnostic = _unsupported_type_tag_diagnostic(field, style, argument)
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(diagnostic,),
        )

    lookup = catalog.translation_template(backend, rule.metadata_key)
    if lookup.value is None or not isinstance(lookup.value, BackendTranslationTemplate):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_suffix_metadata_diagnostic(field, backend, rule),),
        )

    template = lookup.value
    placeholders = _placeholders(template.template)
    if placeholders:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(
                _unresolved_suffix_placeholder_diagnostic(
                    field,
                    rule,
                    placeholders,
                ),
            ),
        )

    return BackendIntrinsicModifierTranslationResult(
        modifier=BackendTranslatedIntrinsicModifier(
            backend=backend,
            field=field,
            name=field.name,
            value=BackendIntrinsicLiteralFragment(
                text=BackendIntrinsicModifierFragmentText(str(template.template)),
            ),
            source=field.source,
            metadata_key=rule.metadata_key,
            metadata_source=template.source,
        ),
        diagnostics=(),
    )


def _type_suffix_rule(
    style: BackendIntrinsicStyle,
    type_tag: TypeTag,
) -> BackendIntrinsicTypeSuffixTranslationRule | None:
    for rule in _TYPE_SUFFIX_TRANSLATION_RULES:
        if str(rule.intrinsic_style) == str(style) and str(rule.type_tag) == str(
            type_tag
        ):
            return rule
    return None


def _known_type_suffix_styles() -> frozenset[BackendIntrinsicStyle]:
    return frozenset(rule.intrinsic_style for rule in _TYPE_SUFFIX_TRANSLATION_RULES)


def _type_tags_for_style(style: BackendIntrinsicStyle) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(rule.type_tag)
            for rule in _TYPE_SUFFIX_TRANSLATION_RULES
            if str(rule.intrinsic_style) == str(style)
        )
    )


def _placeholders(template: BackendTemplateText) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                match.group("name")
                for match in _PLACEHOLDER_PATTERN.finditer(str(template))
            }
        )
    )


def _translate_literal_fragment(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
) -> BackendIntrinsicModifierTranslationResult:
    value_text = _direct_literal_operand_text(field)
    if value_text is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_operand_diagnostic(field),),
        )

    if field.name == "suffix" and "?" in value_text:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsafe_literal_fragment_diagnostic(field, value_text),),
        )

    if field.name == "infix" and value_text == _TO_TYPE_SUFFIX_SYMBOL:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_semantic_infix_diagnostic(field, value_text),),
        )

    return BackendIntrinsicModifierTranslationResult(
        modifier=BackendTranslatedIntrinsicModifier(
            backend=backend,
            field=field,
            name=field.name,
            value=BackendIntrinsicLiteralFragment(
                text=BackendIntrinsicModifierFragmentText(value_text),
            ),
            source=field.source,
        ),
        diagnostics=(),
    )


def _translate_infix_separator(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
) -> BackendIntrinsicModifierTranslationResult:
    if not isinstance(field.value, BackendIntrinsicModifierStringOperand):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_operand_diagnostic(field),),
        )

    return BackendIntrinsicModifierTranslationResult(
        modifier=BackendTranslatedIntrinsicModifier(
            backend=backend,
            field=field,
            name=field.name,
            value=BackendIntrinsicInfixSeparator(
                text=BackendIntrinsicInfixSeparatorText(field.value.value),
            ),
            source=field.source,
        ),
        diagnostics=(),
    )


def _translate_immediate_literal(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
) -> BackendIntrinsicModifierTranslationResult:
    if field.immediate_index is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_immediate_index_diagnostic(field),),
        )

    if not isinstance(field.value, BackendIntrinsicModifierIntegerOperand):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unsupported_immediate_operand_diagnostic(field),),
        )

    return BackendIntrinsicModifierTranslationResult(
        modifier=BackendTranslatedIntrinsicModifier(
            backend=backend,
            field=field,
            name=field.name,
            value=BackendIntrinsicImmediateLiteral(
                argument_index=field.immediate_index,
                value=field.value.value,
            ),
            source=field.source,
        ),
        diagnostics=(),
    )


def _direct_literal_operand_text(field: BackendIntrinsicModifierField) -> str | None:
    if isinstance(field.value, BackendIntrinsicModifierSymbolOperand):
        return field.value.text
    if isinstance(field.value, BackendIntrinsicModifierStringOperand):
        return field.value.value
    return None


def _unsupported_field_diagnostic(field: BackendIntrinsicModifierField) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-FIELD",
        message=(
            f"backend intrinsic modifier translation does not support field "
            f"{field.key_text!r}; expected suffix, post, infix, infix_sep, "
            "or immediate(N) literal forms"
        ),
        location=field.key_source,
    )


def _missing_metadata_diagnostic(field: BackendIntrinsicModifierField) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-METADATA",
        message=(
            "type-derived intrinsic suffix translation requires a backend "
            f"metadata catalog for field {field.key_text!r}"
        ),
        location=field.value_source,
    )


def _unsupported_backend_diagnostic(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
    catalog: BackendMetadataCatalog,
) -> Diagnostic:
    expected = ", ".join(str(item) for item in catalog.backends) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-BACKEND",
        message=(
            f"type-derived intrinsic suffix translation does not support "
            f"backend {str(backend)!r}; expected one of: {expected}"
        ),
        location=field.value_source,
    )


def _unknown_extension_diagnostic(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNKNOWN-EXTENSION",
        message=(
            f"type-derived intrinsic suffix translation could not find selected "
            f"extension {str(context.selected_extension)!r} in the extension catalog"
        ),
        location=field.value_source,
    )


def _missing_intrinsic_style_diagnostic(
    field: BackendIntrinsicModifierField,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-STYLE",
        message=(
            "type-derived intrinsic suffix translation requires the selected "
            "extension to define intrinsic_style"
        ),
        location=source or field.value_source,
    )


def _unsupported_intrinsic_style_diagnostic(
    field: BackendIntrinsicModifierField,
    style: BackendIntrinsicStyle,
    source: SourceLocation,
) -> Diagnostic:
    expected = ", ".join(sorted(str(item) for item in _known_type_suffix_styles()))
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-STYLE",
        message=(
            f"type-derived intrinsic suffix translation does not support "
            f"intrinsic style {str(style)!r}; expected one of: {expected}"
        ),
        location=source or field.value_source,
    )


def _unsupported_type_tag_diagnostic(
    field: BackendIntrinsicModifierField,
    style: BackendIntrinsicStyle,
    argument: BackendValueTypeOperand,
) -> Diagnostic:
    expected = ", ".join(_type_tags_for_style(style)) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-TYPE",
        message=(
            f"type-derived intrinsic suffix translation does not support type "
            f"tag {str(argument.value.type_tag)!r} for intrinsic style "
            f"{str(style)!r}; expected one of: {expected}"
        ),
        location=argument.source,
    )


def _unsupported_lowered_type_diagnostic(
    field: BackendIntrinsicModifierField,
    argument: BackendValueTypeOperand,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-TYPE-VALUE",
        message=(
            "type-derived intrinsic suffix translation requires "
            "LoweredScalarTypeIdentity, not "
            f"{type(argument.value).__name__}"
        ),
        location=argument.source or field.value_source,
    )


def _missing_suffix_metadata_diagnostic(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
    rule: BackendIntrinsicTypeSuffixTranslationRule,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-MISSING-ENTRY",
        message=(
            f"backend metadata has no type-derived intrinsic suffix entry for "
            f"backend {str(backend)!r} and key {str(rule.metadata_key)!r}"
        ),
        location=field.value_source,
    )


def _unresolved_suffix_placeholder_diagnostic(
    field: BackendIntrinsicModifierField,
    rule: BackendIntrinsicTypeSuffixTranslationRule,
    placeholders: tuple[str, ...],
) -> Diagnostic:
    names = ", ".join(placeholders)
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNRESOLVED-PLACEHOLDER",
        message=(
            f"type-derived intrinsic suffix metadata key "
            f"{str(rule.metadata_key)!r} requires unresolved placeholder(s): "
            f"{names}"
        ),
        location=field.value_source,
    )


def _unsupported_backend_value_operand_diagnostic(
    field: BackendIntrinsicModifierField,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-BACKEND-VALUE",
        message=(
            "backend intrinsic modifier translation does not resolve backend "
            f"value operand {field.value.source_text!r} for field {field.key_text!r}"
        ),
        location=field.value_source,
    )


def _unsupported_operand_diagnostic(field: BackendIntrinsicModifierField) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-OPERAND",
        message=(
            f"backend intrinsic modifier translation does not support operand "
            f"{field.value.source_text if hasattr(field.value, 'source_text') else type(field.value).__name__!r} "
            f"for field {field.key_text!r}"
        ),
        location=field.value_source,
    )


def _unsafe_literal_fragment_diagnostic(
    field: BackendIntrinsicModifierField,
    value_text: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSAFE-LITERAL",
        message=(
            f"backend intrinsic modifier translation does not treat {value_text!r} "
            "as a final literal suffix fragment because it contains an "
            "unresolved wildcard marker"
        ),
        location=field.value_source,
    )


def _semantic_infix_diagnostic(
    field: BackendIntrinsicModifierField,
    value_text: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-SEMANTIC-INFIX",
        message=(
            f"backend intrinsic modifier translation does not resolve semantic "
            f"infix marker {value_text!r}; a later typed rule must provide it"
        ),
        location=field.value_source,
    )


def _unsupported_immediate_operand_diagnostic(
    field: BackendIntrinsicModifierField,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
        message=(
            f"backend intrinsic modifier translation requires an integer literal "
            f"for {field.key_text!r}"
        ),
        location=field.value_source,
    )


def _missing_immediate_index_diagnostic(
    field: BackendIntrinsicModifierField,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-MISSING-IMMEDIATE-INDEX",
        message=(
            "backend intrinsic modifier translation requires immediate(N) "
            "to carry the integer argument index"
        ),
        location=field.key_source,
    )


def _unsupported_direct_intrinsic_diagnostic(
    request: BackendDirectIntrinsicHandoffRequest,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-DIRECT-INTRINSIC",
        message=(
            "backend intrinsic modifier translation only accepts "
            "intrin_compose<...>(...) handoff requests; direct intrinsic "
            f"{request.source_text!r} remains opaque"
        ),
        location=request.source,
    )


def _unsupported_request_diagnostic(
    request: BackendIntrinsicHandoffRequest,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-REQUEST",
        message=(
            "backend intrinsic modifier translation does not support handoff "
            f"request {type(request).__name__}"
        ),
        location=request.source,
    )
