"""Backend intrinsic compose modifier translation over typed handoff values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
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

_FRAGMENT_MODIFIER_NAMES = frozenset({"suffix", "post", "infix"})
_TO_TYPE_SUFFIX_SYMBOL = "to_type_suffix"


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


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierTranslationResult:
    modifier: BackendTranslatedIntrinsicModifier | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierTranslationBatchResult:
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


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
