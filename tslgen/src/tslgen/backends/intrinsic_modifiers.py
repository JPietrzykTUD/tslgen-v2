"""Backend intrinsic compose modifier translation over typed handoff values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, NewType

from tslgen.backends._intrinsic_metadata_modifiers import (
    METADATA_BACKED_MODIFIER_FAMILIES,
    BackendIntrinsicNamedSuffixPolicy,
    BackendIntrinsicNamedSuffixTranslationRule,
    BackendIntrinsicPrefixTranslationRule,
    BackendIntrinsicStyle,
    BackendIntrinsicTypeSuffixTranslationRule,
    MetadataBackedModifierFamily,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
)
from tslgen.domain.catalog import (
    ExtensionCatalog,
    ExtensionName,
    PrimitiveGenericParameter,
    TypeTag,
)
from tslgen.domain.signatures import SignatureParameterTerm
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierDestinationTypeSuffixOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierIntegerOperand,
    BackendIntrinsicModifierName,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    LoweredSelectedGenericImmediateParameter,
    LoweredSelectedSignatureImmediateParameter,
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
    "immediate_generic_parameter_reference",
    "immediate_parameter_reference",
]
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


@dataclass(frozen=True, slots=True)
class BackendIntrinsicImmediateParameterReference:
    argument_index: int
    parameter: SignatureParameterTerm
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicImmediateGenericParameterReference:
    argument_index: int
    parameter: PrimitiveGenericParameter
    source_text: str
    source: SourceLocation


BackendTranslatedIntrinsicModifierValue = (
    BackendIntrinsicLiteralFragment
    | BackendIntrinsicInfixSeparator
    | BackendIntrinsicImmediateLiteral
    | BackendIntrinsicImmediateGenericParameterReference
    | BackendIntrinsicImmediateParameterReference
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
    selected_type_tag: TypeTag
    extension_catalog: ExtensionCatalog
    metadata_catalog: BackendMetadataCatalog | None


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
        return _translate_immediate_modifier(field, backend_id)

    return BackendIntrinsicModifierTranslationResult(
        modifier=None,
        diagnostics=(_unsupported_field_diagnostic(field),),
    )


def translate_backend_intrinsic_modifier_field_with_context(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
) -> BackendIntrinsicModifierTranslationResult:
    """Translate one modifier using context for selected semantic families."""

    for family in METADATA_BACKED_MODIFIER_FAMILIES:
        result = _translate_metadata_backed_modifier(field, context, family)
        if result is not None:
            return result
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


def _translate_metadata_backed_modifier(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
    family: MetadataBackedModifierFamily,
) -> BackendIntrinsicModifierTranslationResult | None:
    if field.name != family.field_name:
        return None
    request = _metadata_backed_modifier_request(field)
    if request is None:
        return None
    if not family.request_matches(request):
        return None

    precondition_diagnostic = family.precondition_diagnostic(field, request)
    if precondition_diagnostic is not None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(precondition_diagnostic,),
        )

    catalog = context.metadata_catalog
    if catalog is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_metadata_diagnostic(field, family),),
        )

    backend = BackendId(str(context.backend))
    if backend not in catalog.backends:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(
                _unsupported_backend_diagnostic(field, backend, catalog, family),
            ),
        )

    extension = context.extension_catalog.get(str(context.selected_extension))
    if extension is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_unknown_extension_diagnostic(field, context, family),),
        )

    metadata_key = family.metadata_key(
        field,
        request,
        extension,
        context.selected_type_tag,
    )
    if isinstance(metadata_key, Diagnostic):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(metadata_key,),
        )

    lookup = catalog.translation_template(backend, metadata_key)
    if lookup.value is None or not isinstance(lookup.value, BackendTranslationTemplate):
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(
                _missing_modifier_metadata_entry_diagnostic(
                    field,
                    backend,
                    metadata_key,
                    family,
                ),
            ),
        )

    template = lookup.value
    placeholders = _placeholders(template.template)
    if placeholders:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(
                _unresolved_modifier_placeholder_diagnostic(
                    field,
                    metadata_key,
                    placeholders,
                    family,
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
            metadata_key=metadata_key,
            metadata_source=template.source,
        ),
        diagnostics=(),
    )


def _metadata_backed_modifier_request(
    field: BackendIntrinsicModifierField,
) -> object | None:
    if isinstance(field.value, BackendIntrinsicModifierBackendValueOperand):
        return field.value.request
    if isinstance(field.value, BackendIntrinsicModifierDestinationTypeSuffixOperand):
        return field.value.request
    return None


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


def _translate_immediate_modifier(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
) -> BackendIntrinsicModifierTranslationResult:
    if isinstance(field.value, LoweredSelectedGenericImmediateParameter):
        return BackendIntrinsicModifierTranslationResult(
            modifier=BackendTranslatedIntrinsicModifier(
                backend=backend,
                field=field,
                name=field.name,
                value=BackendIntrinsicImmediateGenericParameterReference(
                    argument_index=field.value.argument_index,
                    parameter=field.value.parameter,
                    source_text=field.value.source_text,
                    source=field.value.source,
                ),
                source=field.source,
            ),
            diagnostics=(),
        )

    if isinstance(field.value, LoweredSelectedSignatureImmediateParameter):
        return BackendIntrinsicModifierTranslationResult(
            modifier=BackendTranslatedIntrinsicModifier(
                backend=backend,
                field=field,
                name=field.name,
                value=BackendIntrinsicImmediateParameterReference(
                    argument_index=field.value.argument_index,
                    parameter=field.value.parameter,
                    source_text=field.value.source_text,
                    source=field.value.source,
                ),
                source=field.source,
            ),
            diagnostics=(),
        )

    if field.immediate_index is None:
        return BackendIntrinsicModifierTranslationResult(
            modifier=None,
            diagnostics=(_missing_immediate_index_diagnostic(field),),
        )

    if isinstance(field.value, BackendIntrinsicModifierIntegerOperand):
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

    return BackendIntrinsicModifierTranslationResult(
        modifier=None,
        diagnostics=(_unsupported_immediate_operand_diagnostic(field),),
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


def _missing_metadata_diagnostic(
    field: BackendIntrinsicModifierField,
    family: MetadataBackedModifierFamily,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=(
            f"TSL-BACKEND-INTRINSIC-MODIFIER-"
            f"{family.diagnostic_name}-MISSING-METADATA"
        ),
        message=(
            f"{family.label} translation requires a backend "
            f"metadata catalog for field {field.key_text!r}"
        ),
        location=field.value_source,
    )


def _unsupported_backend_diagnostic(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
    catalog: BackendMetadataCatalog,
    family: MetadataBackedModifierFamily,
) -> Diagnostic:
    expected = ", ".join(str(item) for item in catalog.backends) or "<none>"
    return Diagnostic(
        severity="error",
        code=(
            f"TSL-BACKEND-INTRINSIC-MODIFIER-"
            f"{family.diagnostic_name}-UNSUPPORTED-BACKEND"
        ),
        message=(
            f"{family.label} translation does not support "
            f"backend {str(backend)!r}; expected one of: {expected}"
        ),
        location=field.value_source,
    )


def _unknown_extension_diagnostic(
    field: BackendIntrinsicModifierField,
    context: BackendIntrinsicModifierTranslationContext,
    family: MetadataBackedModifierFamily,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=(
            f"TSL-BACKEND-INTRINSIC-MODIFIER-"
            f"{family.diagnostic_name}-UNKNOWN-EXTENSION"
        ),
        message=(
            f"{family.label} translation could not find selected "
            f"extension {str(context.selected_extension)!r} in the extension catalog"
        ),
        location=field.value_source,
    )


def _missing_modifier_metadata_entry_diagnostic(
    field: BackendIntrinsicModifierField,
    backend: BackendId,
    metadata_key: BackendTranslationKey,
    family: MetadataBackedModifierFamily,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=(
            f"TSL-BACKEND-INTRINSIC-MODIFIER-"
            f"{family.diagnostic_name}-MISSING-ENTRY"
        ),
        message=(
            f"backend metadata has no {family.label} entry for backend "
            f"{str(backend)!r} and key {str(metadata_key)!r}"
        ),
        location=field.value_source,
    )


def _unresolved_modifier_placeholder_diagnostic(
    field: BackendIntrinsicModifierField,
    metadata_key: BackendTranslationKey,
    placeholders: tuple[str, ...],
    family: MetadataBackedModifierFamily,
) -> Diagnostic:
    names = ", ".join(placeholders)
    return Diagnostic(
        severity="error",
        code=(
            f"TSL-BACKEND-INTRINSIC-MODIFIER-"
            f"{family.diagnostic_name}-UNRESOLVED-PLACEHOLDER"
        ),
        message=(
            f"{family.label} metadata key {str(metadata_key)!r} requires "
            f"unresolved placeholder(s): {names}"
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
