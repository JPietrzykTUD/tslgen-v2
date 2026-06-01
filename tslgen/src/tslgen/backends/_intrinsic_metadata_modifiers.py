"""Typed metadata-backed intrinsic modifier rule families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendTranslationKey
from tslgen.domain.catalog import Extension, ExtensionName, TypeTag
from tslgen.lowering.model import (
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierName,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
)

BackendIntrinsicStyle = NewType("BackendIntrinsicStyle", str)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicTypeSuffixTranslationRule:
    intrinsic_style: BackendIntrinsicStyle
    type_tag: TypeTag
    metadata_key: BackendTranslationKey


@dataclass(frozen=True, slots=True)
class BackendIntrinsicPrefixTranslationRule:
    extension: ExtensionName
    metadata_key: BackendTranslationKey


@dataclass(frozen=True, slots=True)
class MetadataBackedModifierFamily:
    field_name: BackendIntrinsicModifierName
    label: str
    diagnostic_name: str
    request_matches: Callable[[object], bool]
    precondition_diagnostic: Callable[
        [BackendIntrinsicModifierField, object],
        Diagnostic | None,
    ]
    metadata_key: Callable[
        [BackendIntrinsicModifierField, object, Extension, TypeTag],
        BackendTranslationKey | Diagnostic,
    ]


TYPE_SUFFIX_TRANSLATION_RULES: tuple[
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

PREFIX_TRANSLATION_RULES: tuple[
    BackendIntrinsicPrefixTranslationRule,
    ...,
] = (
    BackendIntrinsicPrefixTranslationRule(
        ExtensionName("sse"),
        BackendTranslationKey("intrinsic_prefix_sse"),
    ),
    BackendIntrinsicPrefixTranslationRule(
        ExtensionName("sse_vl"),
        BackendTranslationKey("intrinsic_prefix_sse_vl"),
    ),
    BackendIntrinsicPrefixTranslationRule(
        ExtensionName("avx2"),
        BackendTranslationKey("intrinsic_prefix_avx2"),
    ),
    BackendIntrinsicPrefixTranslationRule(
        ExtensionName("avx2_vl"),
        BackendTranslationKey("intrinsic_prefix_avx2_vl"),
    ),
    BackendIntrinsicPrefixTranslationRule(
        ExtensionName("avx512"),
        BackendTranslationKey("intrinsic_prefix_avx512"),
    ),
)


def _is_type_or_current_suffix_request(request: object) -> bool:
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return False
    return request.argument is None or isinstance(
        request.argument,
        BackendValueTypeOperand,
    )


def _is_current_suffix_request(request: object) -> bool:
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return False
    return request.argument is None


def _is_prefix_request(request: object) -> bool:
    return isinstance(request, BackendIntrinsicPrefixValueRequest)


def _no_metadata_precondition_diagnostic(
    field: BackendIntrinsicModifierField,
    request: object,
) -> Diagnostic | None:
    del field, request
    return None


def _type_suffix_precondition_diagnostic(
    field: BackendIntrinsicModifierField,
    request: object,
) -> Diagnostic | None:
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return None
    argument = request.argument
    if argument is None:
        return None
    if not isinstance(argument, BackendValueTypeOperand):
        return None
    if isinstance(argument.value, LoweredScalarTypeIdentity):
        return None
    return _unsupported_lowered_type_diagnostic(field, argument)


def _type_suffix_metadata_key(
    field: BackendIntrinsicModifierField,
    request: object,
    extension: Extension,
    selected_type_tag: TypeTag,
) -> BackendTranslationKey | Diagnostic:
    if not isinstance(request, BackendIntrinsicSuffixValueRequest):
        return _invalid_metadata_family_request_diagnostic(field)

    type_tag_result = _type_suffix_type_tag(field, request, selected_type_tag)
    if isinstance(type_tag_result, Diagnostic):
        return type_tag_result
    type_tag, type_tag_source = type_tag_result

    if extension.intrinsic_style is None:
        return _missing_intrinsic_style_diagnostic(field, extension.source)

    style = BackendIntrinsicStyle(extension.intrinsic_style)
    rule = _type_suffix_rule(style, type_tag)
    if rule is not None:
        return rule.metadata_key
    if style not in _known_type_suffix_styles():
        return _unsupported_intrinsic_style_diagnostic(
            field,
            style,
            extension.source,
        )
    return _unsupported_type_tag_diagnostic(field, style, type_tag, type_tag_source)


def _prefix_metadata_key(
    field: BackendIntrinsicModifierField,
    request: object,
    extension: Extension,
    selected_type_tag: TypeTag,
) -> BackendTranslationKey | Diagnostic:
    del selected_type_tag
    if not isinstance(request, BackendIntrinsicPrefixValueRequest):
        return _invalid_metadata_family_request_diagnostic(field)

    rule = _prefix_rule(ExtensionName(extension.name))
    if rule is not None:
        return rule.metadata_key

    return _unsupported_prefix_extension_diagnostic(field, extension)


METADATA_BACKED_MODIFIER_FAMILIES: tuple[
    MetadataBackedModifierFamily,
    ...,
] = (
    MetadataBackedModifierFamily(
        field_name="suffix",
        label="intrinsic suffix",
        diagnostic_name="TYPE-SUFFIX",
        request_matches=_is_type_or_current_suffix_request,
        precondition_diagnostic=_type_suffix_precondition_diagnostic,
        metadata_key=_type_suffix_metadata_key,
    ),
    MetadataBackedModifierFamily(
        field_name="infix",
        label="current-type intrinsic suffix",
        diagnostic_name="TYPE-SUFFIX",
        request_matches=_is_current_suffix_request,
        precondition_diagnostic=_type_suffix_precondition_diagnostic,
        metadata_key=_type_suffix_metadata_key,
    ),
    MetadataBackedModifierFamily(
        field_name="prefix",
        label="intrinsic prefix",
        diagnostic_name="PREFIX",
        request_matches=_is_prefix_request,
        precondition_diagnostic=_no_metadata_precondition_diagnostic,
        metadata_key=_prefix_metadata_key,
    ),
)


def _type_suffix_rule(
    style: BackendIntrinsicStyle,
    type_tag: TypeTag,
) -> BackendIntrinsicTypeSuffixTranslationRule | None:
    for rule in TYPE_SUFFIX_TRANSLATION_RULES:
        if str(rule.intrinsic_style) == str(style) and str(rule.type_tag) == str(
            type_tag
        ):
            return rule
    return None


def _type_suffix_type_tag(
    field: BackendIntrinsicModifierField,
    request: BackendIntrinsicSuffixValueRequest,
    selected_type_tag: TypeTag,
) -> tuple[TypeTag, SourceLocation] | Diagnostic:
    argument = request.argument
    if argument is None:
        return selected_type_tag, field.value_source
    if not isinstance(argument, BackendValueTypeOperand):
        return _invalid_metadata_family_request_diagnostic(field)
    if not isinstance(argument.value, LoweredScalarTypeIdentity):
        return _unsupported_lowered_type_diagnostic(field, argument)
    return argument.value.type_tag, argument.source


def _prefix_rule(
    extension: ExtensionName,
) -> BackendIntrinsicPrefixTranslationRule | None:
    for rule in PREFIX_TRANSLATION_RULES:
        if str(rule.extension) == str(extension):
            return rule
    return None


def _known_type_suffix_styles() -> frozenset[BackendIntrinsicStyle]:
    return frozenset(rule.intrinsic_style for rule in TYPE_SUFFIX_TRANSLATION_RULES)


def _known_prefix_extensions() -> tuple[str, ...]:
    return tuple(sorted(str(rule.extension) for rule in PREFIX_TRANSLATION_RULES))


def _type_tags_for_style(style: BackendIntrinsicStyle) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(rule.type_tag)
            for rule in TYPE_SUFFIX_TRANSLATION_RULES
            if str(rule.intrinsic_style) == str(style)
        )
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
    type_tag: TypeTag,
    source: SourceLocation,
) -> Diagnostic:
    expected = ", ".join(_type_tags_for_style(style)) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-TYPE-SUFFIX-UNSUPPORTED-TYPE",
        message=(
            f"type-derived intrinsic suffix translation does not support type "
            f"tag {str(type_tag)!r} for intrinsic style "
            f"{str(style)!r}; expected one of: {expected}"
        ),
        location=source or field.value_source,
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


def _unsupported_prefix_extension_diagnostic(
    field: BackendIntrinsicModifierField,
    extension: Extension,
) -> Diagnostic:
    expected = ", ".join(_known_prefix_extensions()) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-MODIFIER-PREFIX-UNSUPPORTED-EXTENSION",
        message=(
            f"intrinsic prefix translation does not support selected extension "
            f"{extension.name!r}; expected one of: {expected}"
        ),
        location=extension.source or field.value_source,
    )


def _invalid_metadata_family_request_diagnostic(
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


__all__ = [
    "BackendIntrinsicPrefixTranslationRule",
    "BackendIntrinsicStyle",
    "BackendIntrinsicTypeSuffixTranslationRule",
    "METADATA_BACKED_MODIFIER_FAMILIES",
    "MetadataBackedModifierFamily",
]
