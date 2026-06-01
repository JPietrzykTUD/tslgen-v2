"""Backend emitters and translation helpers for the clean restart generator."""

from tslgen.backends.type_spelling import (
    BackendTranslatedTypeSpelling,
    BackendTypeSpellingMetadataKind,
    BackendTypeSpellingTranslationBatchResult,
    BackendTypeSpellingTranslationResult,
    translate_backend_type_spelling_request,
    translate_backend_type_spelling_requests,
)

__all__ = [
    "BackendTranslatedTypeSpelling",
    "BackendTypeSpellingMetadataKind",
    "BackendTypeSpellingTranslationBatchResult",
    "BackendTypeSpellingTranslationResult",
    "translate_backend_type_spelling_request",
    "translate_backend_type_spelling_requests",
]
