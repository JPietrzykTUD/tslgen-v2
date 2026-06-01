"""Backend type spelling translation over typed lowering requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import (
    BackendId,
    BackendLanguageTypeSpelling,
    BackendMetadataCatalog,
    BackendTemplateText,
    BackendTranslationKey,
    BackendTranslationTemplate,
    BackendTypeKey,
    BackendTypeSpellingText,
)
from tslgen.lowering.model import (
    BackendTypeSpellingRequest,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
)

BackendTypeSpellingMetadataKind = Literal["language_type", "translation_template"]

_SIZE_TYPE_TRANSLATION_KEY = BackendTranslationKey("type_size")


@dataclass(frozen=True, slots=True)
class BackendTranslatedTypeSpelling:
    request: BackendTypeSpellingRequest
    backend: BackendId
    spelling: BackendTypeSpellingText
    metadata_kind: BackendTypeSpellingMetadataKind
    metadata_key: BackendTypeKey | BackendTranslationKey
    metadata_source: SourceLocation
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeSpellingTranslationResult:
    spelling: BackendTranslatedTypeSpelling | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendTypeSpellingTranslationBatchResult:
    spellings: tuple[BackendTranslatedTypeSpelling, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


def translate_backend_type_spelling_request(
    request: BackendTypeSpellingRequest,
    catalog: BackendMetadataCatalog | None,
) -> BackendTypeSpellingTranslationResult:
    """Translate one backend type spelling request through typed metadata."""

    if catalog is None:
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_missing_metadata_diagnostic(request),),
        )

    backend = BackendId(request.backend)
    if backend not in catalog.backends:
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_unsupported_backend_diagnostic(request, catalog),),
        )

    value = request.value
    if isinstance(value, LoweredScalarTypeIdentity):
        return _translate_scalar_type_identity(request, catalog, backend, value)
    if isinstance(value, LoweredSizeType):
        return _translate_size_type(request, catalog, backend)

    return BackendTypeSpellingTranslationResult(
        spelling=None,
        diagnostics=(_unsupported_value_diagnostic(request),),
    )


def translate_backend_type_spelling_requests(
    requests: tuple[BackendTypeSpellingRequest, ...],
    catalog: BackendMetadataCatalog | None,
) -> BackendTypeSpellingTranslationBatchResult:
    """Translate requests in source/input order and accumulate diagnostics."""

    spellings: list[BackendTranslatedTypeSpelling] = []
    diagnostics: list[Diagnostic] = []

    for request in requests:
        result = translate_backend_type_spelling_request(request, catalog)
        diagnostics.extend(result.diagnostics)
        if result.spelling is not None:
            spellings.append(result.spelling)

    return BackendTypeSpellingTranslationBatchResult(
        spellings=tuple(spellings),
        diagnostics=tuple(diagnostics),
    )


def _translate_scalar_type_identity(
    request: BackendTypeSpellingRequest,
    catalog: BackendMetadataCatalog,
    backend: BackendId,
    value: LoweredScalarTypeIdentity,
) -> BackendTypeSpellingTranslationResult:
    type_key = _scalar_type_key(value)
    if type_key is None:
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_unsupported_scalar_tag_diagnostic(request, value),),
        )

    lookup = catalog.type_spelling(backend, type_key)
    if lookup.value is None:
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_missing_scalar_spelling_diagnostic(request, type_key),),
        )

    spelling = lookup.value
    if not isinstance(spelling, BackendLanguageTypeSpelling):
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_missing_scalar_spelling_diagnostic(request, type_key),),
        )

    return BackendTypeSpellingTranslationResult(
        spelling=BackendTranslatedTypeSpelling(
            request=request,
            backend=backend,
            spelling=spelling.spelling,
            metadata_kind="language_type",
            metadata_key=type_key,
            metadata_source=spelling.source,
            source=request.source,
        ),
        diagnostics=(),
    )


def _translate_size_type(
    request: BackendTypeSpellingRequest,
    catalog: BackendMetadataCatalog,
    backend: BackendId,
) -> BackendTypeSpellingTranslationResult:
    lookup = catalog.translation_template(backend, _SIZE_TYPE_TRANSLATION_KEY)
    if lookup.value is None:
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_missing_size_type_diagnostic(request),),
        )

    template = lookup.value
    if not isinstance(template, BackendTranslationTemplate):
        return BackendTypeSpellingTranslationResult(
            spelling=None,
            diagnostics=(_missing_size_type_diagnostic(request),),
        )

    return BackendTypeSpellingTranslationResult(
        spelling=BackendTranslatedTypeSpelling(
            request=request,
            backend=backend,
            spelling=_template_as_type_spelling(template.template),
            metadata_kind="translation_template",
            metadata_key=_SIZE_TYPE_TRANSLATION_KEY,
            metadata_source=template.source,
            source=request.source,
        ),
        diagnostics=(),
    )


def _scalar_type_key(value: LoweredScalarTypeIdentity) -> BackendTypeKey | None:
    tag = str(value.type_tag)
    if tag.startswith("si") and tag[2:] in {"8", "16", "32", "64"}:
        return BackendTypeKey(f"s{tag[2:]}")
    if tag.startswith("ui") and tag[2:] in {"8", "16", "32", "64"}:
        return BackendTypeKey(f"u{tag[2:]}")
    if tag in {"f32", "f64"}:
        return BackendTypeKey(tag)
    return None


def _template_as_type_spelling(template: BackendTemplateText) -> BackendTypeSpellingText:
    return BackendTypeSpellingText(str(template))


def _missing_metadata_diagnostic(request: BackendTypeSpellingRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-MISSING-METADATA",
        message=(
            "backend type spelling translation requires a backend metadata "
            f"catalog for request {request.source_text!r}"
        ),
        location=request.source,
    )


def _unsupported_backend_diagnostic(
    request: BackendTypeSpellingRequest,
    catalog: BackendMetadataCatalog,
) -> Diagnostic:
    expected = ", ".join(str(backend) for backend in catalog.backends) or "<none>"
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-BACKEND",
        message=(
            f"backend type spelling request uses unsupported backend "
            f"{request.backend!r}; expected one of: {expected}"
        ),
        location=request.source,
    )


def _unsupported_value_diagnostic(request: BackendTypeSpellingRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-VALUE",
        message=(
            "backend type spelling translation does not support lowered value "
            f"{type(request.value).__name__} for request {request.source_text!r}"
        ),
        location=request.source,
    )


def _unsupported_scalar_tag_diagnostic(
    request: BackendTypeSpellingRequest,
    value: LoweredScalarTypeIdentity,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-UNSUPPORTED-SCALAR-TAG",
        message=(
            f"backend type spelling translation does not support scalar type tag "
            f"{str(value.type_tag)!r}; expected si8/si16/si32/si64, "
            "ui8/ui16/ui32/ui64, f32, or f64"
        ),
        location=request.source,
    )


def _missing_scalar_spelling_diagnostic(
    request: BackendTypeSpellingRequest,
    type_key: BackendTypeKey,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-MISSING-SCALAR-SPELLING",
        message=(
            f"backend metadata has no scalar type spelling for backend "
            f"{request.backend!r} and normalized type key {str(type_key)!r}"
        ),
        location=request.source,
    )


def _missing_size_type_diagnostic(request: BackendTypeSpellingRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-TYPE-SPELLING-MISSING-SIZE-TYPE",
        message=(
            f"backend metadata has no {_SIZE_TYPE_TRANSLATION_KEY!s} translation "
            f"for backend {request.backend!r}"
        ),
        location=request.source,
    )
