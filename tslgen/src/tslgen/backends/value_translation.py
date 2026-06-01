"""Backend value translation over typed lowering requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
)
from tslgen.lowering.model import (
    BackendConstantValueRequest,
    BackendValueConstantName,
    BackendValueUninitKind,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendUninitValueRequest,
    BackendValueRequest,
)

BackendValueText = NewType("BackendValueText", str)

_PLACEHOLDER_PATTERN = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class BackendUninitValueTranslationRule:
    kind: BackendValueUninitKind
    metadata_key: BackendTranslationKey


@dataclass(frozen=True, slots=True)
class BackendConstantValueTranslationRule:
    name: BackendValueConstantName
    metadata_key: BackendTranslationKey


@dataclass(frozen=True, slots=True)
class BackendTranslatedValue:
    request: BackendValueRequest
    backend: BackendId
    value: BackendValueText
    metadata_key: BackendTranslationKey
    metadata_source: SourceLocation
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueTranslationResult:
    value: BackendTranslatedValue | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendValueTranslationBatchResult:
    values: tuple[BackendTranslatedValue, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


_UNINIT_TRANSLATION_RULES: tuple[BackendUninitValueTranslationRule, ...] = (
    BackendUninitValueTranslationRule(
        kind="array",
        metadata_key=BackendTranslationKey("value_array_uninit"),
    ),
    BackendUninitValueTranslationRule(
        kind="scalar",
        metadata_key=BackendTranslationKey("value_uninit"),
    ),
)
_CONSTANT_TRANSLATION_RULES: tuple[BackendConstantValueTranslationRule, ...] = (
    BackendConstantValueTranslationRule(
        name="x86::mm_fround_to_zero",
        metadata_key=BackendTranslationKey("value_mm_fround_to_zero"),
    ),
)


def translate_backend_value_request(
    request: BackendValueRequest,
    catalog: BackendMetadataCatalog | None,
) -> BackendValueTranslationResult:
    """Translate one metadata-only backend value request through typed metadata."""

    if catalog is None:
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(_missing_metadata_diagnostic(request),),
        )

    backend = BackendId(request.backend)
    if backend not in catalog.backends:
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(_unsupported_backend_diagnostic(request, catalog),),
        )

    if isinstance(request, BackendUninitValueRequest):
        rule = _uninit_translation_rule(request)
        if rule is None:
            return BackendValueTranslationResult(
                value=None,
                diagnostics=(_unsupported_uninit_diagnostic(request),),
            )
        return _translate_template_backed_value(
            request,
            catalog,
            backend,
            rule.metadata_key,
        )

    if isinstance(request, BackendConstantValueRequest):
        rule = _constant_translation_rule(request)
        if rule is None:
            return BackendValueTranslationResult(
                value=None,
                diagnostics=(_unsupported_constant_diagnostic(request),),
            )
        return _translate_template_backed_value(
            request,
            catalog,
            backend,
            rule.metadata_key,
        )

    if isinstance(
        request,
        BackendIntrinsicPrefixValueRequest | BackendIntrinsicSuffixValueRequest,
    ):
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(_unsupported_request_diagnostic(request),),
        )

    return BackendValueTranslationResult(
        value=None,
        diagnostics=(_unsupported_request_diagnostic(request),),
    )


def translate_backend_value_requests(
    requests: tuple[BackendValueRequest, ...],
    catalog: BackendMetadataCatalog | None,
) -> BackendValueTranslationBatchResult:
    """Translate requests in source/input order and accumulate diagnostics."""

    values: list[BackendTranslatedValue] = []
    diagnostics: list[Diagnostic] = []

    for request in requests:
        result = translate_backend_value_request(request, catalog)
        diagnostics.extend(result.diagnostics)
        if result.value is not None:
            values.append(result.value)

    return BackendValueTranslationBatchResult(
        values=tuple(values),
        diagnostics=tuple(diagnostics),
    )


def _uninit_translation_rule(
    request: BackendUninitValueRequest,
) -> BackendUninitValueTranslationRule | None:
    for rule in _UNINIT_TRANSLATION_RULES:
        if rule.kind == request.kind:
            return rule
    return None


def _constant_translation_rule(
    request: BackendConstantValueRequest,
) -> BackendConstantValueTranslationRule | None:
    for rule in _CONSTANT_TRANSLATION_RULES:
        if rule.name == request.name:
            return rule
    return None


def _translate_template_backed_value(
    request: BackendValueRequest,
    catalog: BackendMetadataCatalog,
    backend: BackendId,
    key: BackendTranslationKey,
) -> BackendValueTranslationResult:
    lookup = catalog.translation_template(backend, key)
    if lookup.value is None:
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(_missing_translation_diagnostic(request, key),),
        )

    template = lookup.value
    if not isinstance(template, BackendTranslationTemplate):
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(_missing_translation_diagnostic(request, key),),
        )

    placeholders = _placeholders(template.template)
    if placeholders:
        return BackendValueTranslationResult(
            value=None,
            diagnostics=(
                _unresolved_placeholder_diagnostic(request, key, placeholders),
            ),
        )

    return BackendValueTranslationResult(
        value=BackendTranslatedValue(
            request=request,
            backend=backend,
            value=BackendValueText(str(template.template)),
            metadata_key=key,
            metadata_source=template.source,
            source=request.source,
        ),
        diagnostics=(),
    )


def _placeholders(template: BackendTemplateText) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                match.group("name")
                for match in _PLACEHOLDER_PATTERN.finditer(template)
            }
        )
    )


def _missing_metadata_diagnostic(request: BackendValueRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-MISSING-METADATA",
        message=(
            "backend value translation requires a backend metadata catalog "
            f"for request {request.source_text!r}"
        ),
        location=request.source,
    )


def _unsupported_backend_diagnostic(
    request: BackendValueRequest,
    catalog: BackendMetadataCatalog,
) -> Diagnostic:
    expected = ", ".join(str(backend) for backend in catalog.backends) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-BACKEND",
        message=(
            f"backend value request uses unsupported backend {request.backend!r}; "
            f"expected one of: {expected}"
        ),
        location=request.source,
    )


def _unsupported_request_diagnostic(request: BackendValueRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-REQUEST",
        message=(
            "backend value translation does not support request "
            f"{type(request).__name__} for {request.source_text!r}"
        ),
        location=request.source,
    )


def _unsupported_uninit_diagnostic(request: BackendUninitValueRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-UNINIT",
        message=(
            f"backend value translation does not support uninit kind "
            f"{request.kind!r}"
        ),
        location=request.source,
    )


def _unsupported_constant_diagnostic(request: BackendConstantValueRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-UNSUPPORTED-CONSTANT",
        message=f"backend value translation does not support constant {request.name!r}",
        location=request.source,
    )


def _missing_translation_diagnostic(
    request: BackendValueRequest,
    key: BackendTranslationKey,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-MISSING-TRANSLATION",
        message=(
            f"backend metadata has no value translation for backend "
            f"{request.backend!r} and key {str(key)!r}"
        ),
        location=request.source,
    )


def _unresolved_placeholder_diagnostic(
    request: BackendValueRequest,
    key: BackendTranslationKey,
    placeholders: tuple[str, ...],
) -> Diagnostic:
    names = ", ".join(placeholders)
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-VALUE-TRANSLATION-UNRESOLVED-PLACEHOLDER",
        message=(
            f"backend value translation for key {str(key)!r} requires unresolved "
            f"placeholder(s): {names}"
        ),
        location=request.source,
    )
