"""Backend language and translation metadata loading."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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

_ACTIVE_BACKENDS = ("cpp", "rust")
_LANGUAGE_HEADER_PATTERN = re.compile(
    r"^language (?P<backend>[A-Za-z_][A-Za-z0-9_]*):$"
)
_TYPE_ENTRY_PATTERN = re.compile(
    r'^  (?P<key>[A-Za-z_][A-Za-z0-9_]*) \{type "(?P<spelling>[^"]*)"\}$'
)
_TRANSLATION_HEADER_PATTERN = re.compile(
    r"^translation (?P<backend>[A-Za-z_][A-Za-z0-9_]*):$"
)
_TRANSLATION_INLINE_PATTERN = re.compile(
    r'^  (?P<key>[A-Za-z_][A-Za-z0-9_]*) "(?P<template>.*)"$'
)
_TRANSLATION_MULTILINE_PATTERN = re.compile(
    r'^(?P<indent>  )(?P<key>[A-Za-z_][A-Za-z0-9_]*) """(?P<first>.*)$'
)


@dataclass(frozen=True, slots=True)
class BackendTypeMapParseResult:
    type_spellings: tuple[BackendLanguageTypeSpelling, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendTranslationMapParseResult:
    translation_templates: tuple[BackendTranslationTemplate, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendMetadataCatalogBuildResult:
    catalog: BackendMetadataCatalog | None
    diagnostics: tuple[Diagnostic, ...] = ()


def load_active_backend_metadata_catalog(
    language_root: Path,
) -> BackendMetadataCatalogBuildResult:
    type_paths = tuple(
        language_root / "types" / f"types_{backend}.tsl"
        for backend in _ACTIVE_BACKENDS
    )
    translation_paths = tuple(
        language_root / f"translate_{backend}.tsl"
        for backend in _ACTIVE_BACKENDS
    )
    return load_backend_metadata_catalog(type_paths, translation_paths)


def load_backend_metadata_catalog(
    type_paths: tuple[Path, ...],
    translation_paths: tuple[Path, ...],
) -> BackendMetadataCatalogBuildResult:
    diagnostics: list[Diagnostic] = []
    type_spellings: list[BackendLanguageTypeSpelling] = []
    translation_templates: list[BackendTranslationTemplate] = []

    for path in sorted(type_paths, key=lambda item: item.as_posix()):
        resolved = path.resolve()
        if not resolved.is_file():
            diagnostics.append(_missing_source_diagnostic(resolved))
            continue
        result = parse_backend_type_map(resolved.read_text(encoding="utf-8"), resolved)
        diagnostics.extend(result.diagnostics)
        type_spellings.extend(result.type_spellings)

    for path in sorted(translation_paths, key=lambda item: item.as_posix()):
        resolved = path.resolve()
        if not resolved.is_file():
            diagnostics.append(_missing_source_diagnostic(resolved))
            continue
        result = parse_backend_translation_map(
            resolved.read_text(encoding="utf-8"),
            resolved,
        )
        diagnostics.extend(result.diagnostics)
        translation_templates.extend(result.translation_templates)

    diagnostics.extend(_duplicate_type_diagnostics(tuple(type_spellings)))
    diagnostics.extend(_duplicate_translation_diagnostics(tuple(translation_templates)))
    if diagnostics:
        return BackendMetadataCatalogBuildResult(
            catalog=None,
            diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
        )

    return BackendMetadataCatalogBuildResult(
        catalog=BackendMetadataCatalog(
            type_spellings=tuple(
                sorted(
                    type_spellings,
                    key=lambda item: (str(item.backend), str(item.type_key)),
                )
            ),
            translation_templates=tuple(
                sorted(
                    translation_templates,
                    key=lambda item: (str(item.backend), str(item.key)),
                )
            ),
        ),
        diagnostics=(),
    )


def parse_backend_type_map(text: str, path: Path) -> BackendTypeMapParseResult:
    lines = text.splitlines()
    if not lines:
        return BackendTypeMapParseResult(
            type_spellings=(),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-MALFORMED-LANGUAGE",
                    message="backend language map is empty",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    header = _LANGUAGE_HEADER_PATTERN.match(lines[0])
    if header is None:
        return BackendTypeMapParseResult(
            type_spellings=(),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-MALFORMED-LANGUAGE",
                    message="backend language map must start with 'language BACKEND:'",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    backend = BackendId(header.group("backend"))
    diagnostics: list[Diagnostic] = []
    spellings: list[BackendLanguageTypeSpelling] = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        match = _TYPE_ENTRY_PATTERN.match(line)
        if match is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-MALFORMED-TYPE",
                    message=(
                        "backend type entry must have form "
                        "'  TYPE {type \"SPELLING\"}'"
                    ),
                    location=SourceLocation(path, line_number, _first_column(line)),
                )
            )
            continue

        spellings.append(
            BackendLanguageTypeSpelling(
                backend=backend,
                type_key=BackendTypeKey(match.group("key")),
                spelling=BackendTypeSpellingText(match.group("spelling")),
                source=SourceLocation(path, line_number, 3),
            )
        )

    return BackendTypeMapParseResult(
        type_spellings=tuple(spellings),
        diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
    )


def parse_backend_translation_map(
    text: str,
    path: Path,
) -> BackendTranslationMapParseResult:
    lines = text.splitlines()
    if not lines:
        return BackendTranslationMapParseResult(
            translation_templates=(),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-MALFORMED-TRANSLATION",
                    message="backend translation map is empty",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    header = _TRANSLATION_HEADER_PATTERN.match(lines[0])
    if header is None:
        return BackendTranslationMapParseResult(
            translation_templates=(),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-MALFORMED-TRANSLATION",
                    message="backend translation map must start with 'translation BACKEND:'",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    backend = BackendId(header.group("backend"))
    diagnostics: list[Diagnostic] = []
    templates: list[BackendTranslationTemplate] = []
    index = 1
    while index < len(lines):
        line_number = index + 1
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        multiline = _TRANSLATION_MULTILINE_PATTERN.match(line)
        if multiline is not None:
            parsed = _parse_multiline_translation(
                backend,
                multiline,
                lines,
                path,
                line_number,
            )
            templates.append(parsed.template)
            if parsed.diagnostics:
                diagnostics.extend(parsed.diagnostics)
            index = parsed.next_index
            continue

        inline = _TRANSLATION_INLINE_PATTERN.match(line)
        if inline is not None:
            templates.append(
                BackendTranslationTemplate(
                    backend=backend,
                    key=BackendTranslationKey(inline.group("key")),
                    template=BackendTemplateText(inline.group("template")),
                    source=SourceLocation(path, line_number, 3),
                )
            )
            index += 1
            continue

        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-BACKEND-METADATA-MALFORMED-TRANSLATION-ENTRY",
                message=(
                    "backend translation entry must have form "
                    "'  KEY \"TEMPLATE\"' or '  KEY \"\"\"...\"\"\"'"
                ),
                location=SourceLocation(path, line_number, _first_column(line)),
            )
        )
        index += 1

    return BackendTranslationMapParseResult(
        translation_templates=tuple(templates),
        diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
    )


@dataclass(frozen=True, slots=True)
class _MultilineTranslationParseResult:
    template: BackendTranslationTemplate
    next_index: int
    diagnostics: tuple[Diagnostic, ...] = ()


def _parse_multiline_translation(
    backend: BackendId,
    match: re.Match[str],
    lines: list[str],
    path: Path,
    line_number: int,
) -> _MultilineTranslationParseResult:
    key = match.group("key")
    value_lines = [match.group("first")]
    index = line_number
    while index < len(lines):
        candidate = lines[index]
        if candidate == '"""':
            return _MultilineTranslationParseResult(
                template=BackendTranslationTemplate(
                    backend=backend,
                    key=BackendTranslationKey(key),
                    template=BackendTemplateText("\n".join(value_lines)),
                    source=SourceLocation(path, line_number, 3),
                ),
                next_index=index + 1,
            )
        value_lines.append(candidate)
        index += 1

    return _MultilineTranslationParseResult(
        template=BackendTranslationTemplate(
            backend=backend,
            key=BackendTranslationKey(key),
            template=BackendTemplateText("\n".join(value_lines)),
            source=SourceLocation(path, line_number, 3),
        ),
        next_index=len(lines),
        diagnostics=(
            Diagnostic(
                severity="error",
                code="TSL-BACKEND-METADATA-UNCLOSED-TRANSLATION-TEMPLATE",
                message=f"translation template {key!r} is missing closing triple quotes",
                location=SourceLocation(path, line_number, 3),
            ),
        ),
    )


def _duplicate_type_diagnostics(
    spellings: tuple[BackendLanguageTypeSpelling, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen: dict[tuple[str, str], SourceLocation] = {}
    for spelling in spellings:
        key = (str(spelling.backend), str(spelling.type_key))
        first = seen.get(key)
        if first is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-DUPLICATE-TYPE",
                    message=(
                        f"backend type spelling {key[0]!r}/{key[1]!r} is "
                        "declared more than once; first declaration is at "
                        f"{first.path}:{first.line}:{first.column}"
                    ),
                    location=spelling.source,
                )
            )
            continue
        seen[key] = spelling.source
    return tuple(diagnostics)


def _duplicate_translation_diagnostics(
    templates: tuple[BackendTranslationTemplate, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen: dict[tuple[str, str], SourceLocation] = {}
    for template in templates:
        key = (str(template.backend), str(template.key))
        first = seen.get(key)
        if first is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-METADATA-DUPLICATE-TRANSLATION",
                    message=(
                        f"backend translation template {key[0]!r}/{key[1]!r} "
                        "is declared more than once; first declaration is at "
                        f"{first.path}:{first.line}:{first.column}"
                    ),
                    location=template.source,
                )
            )
            continue
        seen[key] = template.source
    return tuple(diagnostics)


def _missing_source_diagnostic(path: Path) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-METADATA-SOURCE-NOT-FOUND",
        message=f"backend metadata source path {path} does not exist",
        location=SourceLocation(path, 1, 1),
    )


def _first_column(line: str) -> int:
    stripped = line.lstrip(" ")
    return len(line) - len(stripped) + 1


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, int, int, str]:
    location = diagnostic.location
    if location is None:
        return diagnostic.code, "", 0, 0, diagnostic.message
    return (
        diagnostic.code,
        location.path.as_posix(),
        location.line,
        location.column,
        diagnostic.message,
    )
