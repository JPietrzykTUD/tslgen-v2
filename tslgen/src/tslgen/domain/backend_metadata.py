"""Typed backend language and translation metadata values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation

BackendId = NewType("BackendId", str)
BackendTranslationKey = NewType("BackendTranslationKey", str)
BackendTypeKey = NewType("BackendTypeKey", str)
BackendTemplateText = NewType("BackendTemplateText", str)
BackendTypeSpellingText = NewType("BackendTypeSpellingText", str)


@dataclass(frozen=True, slots=True)
class BackendLanguageTypeSpelling:
    backend: BackendId
    type_key: BackendTypeKey
    spelling: BackendTypeSpellingText
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTranslationTemplate:
    backend: BackendId
    key: BackendTranslationKey
    template: BackendTemplateText
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendMetadataLookupResult:
    value: BackendLanguageTypeSpelling | BackendTranslationTemplate | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendMetadataCatalog:
    type_spellings: tuple[BackendLanguageTypeSpelling, ...]
    translation_templates: tuple[BackendTranslationTemplate, ...]

    @property
    def backends(self) -> tuple[BackendId, ...]:
        names = {
            item.backend
            for item in (*self.type_spellings, *self.translation_templates)
        }
        return tuple(sorted(names, key=str))

    def type_spelling(
        self,
        backend: BackendId | str,
        type_key: BackendTypeKey | str,
    ) -> BackendMetadataLookupResult:
        backend_text = str(backend)
        type_text = str(type_key)
        for spelling in self.type_spellings:
            if str(spelling.backend) == backend_text and str(spelling.type_key) == type_text:
                return BackendMetadataLookupResult(value=spelling)
        return BackendMetadataLookupResult(
            value=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-UNKNOWN-TYPE-SPELLING",
                    message=(
                        "unknown backend type spelling "
                        f"{backend_text!r}/{type_text!r}"
                    ),
                ),
            ),
        )

    def translation_template(
        self,
        backend: BackendId | str,
        key: BackendTranslationKey | str,
    ) -> BackendMetadataLookupResult:
        backend_text = str(backend)
        key_text = str(key)
        for template in self.translation_templates:
            if str(template.backend) == backend_text and str(template.key) == key_text:
                return BackendMetadataLookupResult(value=template)
        return BackendMetadataLookupResult(
            value=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-UNKNOWN-TRANSLATION",
                    message=(
                        "unknown backend translation template "
                        f"{backend_text!r}/{key_text!r}"
                    ),
                ),
            ),
        )
