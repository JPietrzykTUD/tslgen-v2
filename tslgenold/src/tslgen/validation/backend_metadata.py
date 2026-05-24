from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.backends import (
    ACTIVE_BACKEND_IDS,
    DEFERRED_BACKEND_IDS,
    BackendManifestSet,
    BackendMetadataBoundary,
    BackendMetadataCatalog,
    LanguageTypeEntry,
    LanguageTypeMap,
    TranslationMap,
    TranslationSnippet,
    backend_id_list_text,
)
from tslgen.domain.catalog import Catalog, CatalogEntry
from tslgen.domain.values import CatalogMap, CatalogValue


def backend_metadata_from_catalog(catalog: Catalog) -> Result[BackendMetadataCatalog]:
    diagnostics: list[Diagnostic] = []
    language_maps = [
        _language_type_map(entry, diagnostics)
        for entry in catalog.entries
        if entry.kind == "language"
    ]
    translation_maps = [
        _translation_map(entry, diagnostics)
        for entry in catalog.entries
        if entry.kind == "translation"
    ]

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        BackendMetadataCatalog(
            language_maps=tuple(
                item for item in language_maps if item is not None
            ),
            translation_maps=tuple(
                item for item in translation_maps if item is not None
            ),
        ),
        diagnostics=ordered,
    )


def validate_backend_metadata_boundary(
    manifests: BackendManifestSet,
    metadata: BackendMetadataCatalog,
    *,
    active_backend_ids: tuple[str, ...] = ACTIVE_BACKEND_IDS,
) -> Result[BackendMetadataBoundary]:
    active_ids = tuple(sorted(active_backend_ids))
    diagnostics: list[Diagnostic] = []
    for manifest in manifests.manifests:
        if manifest.backend_id not in active_ids:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-METADATA-UNSUPPORTED-BACKEND",
                    f"backend manifest {manifest.backend_id!r} is not active for "
                    f"this redesign slice; active backends: "
                    f"{backend_id_list_text(active_ids)}; deferred backends: "
                    f"{backend_id_list_text(DEFERRED_BACKEND_IDS)}",
                )
            )
            continue

        if manifest.language_id not in active_ids:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-METADATA-UNSUPPORTED-LANGUAGE",
                    f"backend manifest {manifest.backend_id!r} references "
                    f"unsupported language id {manifest.language_id!r}; active "
                    f"languages: {backend_id_list_text(active_ids)}",
                )
            )
        if manifest.language_id not in metadata.language_maps_by_backend:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-METADATA-MISSING-LANGUAGE",
                    f"backend manifest {manifest.backend_id!r} requires language "
                    f"type map {manifest.language_id!r}",
                )
            )
        if manifest.backend_id not in metadata.translation_maps_by_backend:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-METADATA-MISSING-TRANSLATION",
                    f"backend manifest {manifest.backend_id!r} requires "
                    f"translation map {manifest.backend_id!r}",
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        BackendMetadataBoundary(
            manifests=manifests,
            metadata=metadata,
            active_backend_ids=active_ids,
        ),
        diagnostics=ordered,
    )


def validate_backend_manifests_against_catalog(
    manifests: BackendManifestSet,
    catalog: Catalog,
    *,
    active_backend_ids: tuple[str, ...] = ACTIVE_BACKEND_IDS,
) -> Result[BackendMetadataBoundary]:
    metadata = backend_metadata_from_catalog(catalog)
    if not metadata.is_ok:
        return Result.failure(metadata.diagnostics)
    boundary = validate_backend_metadata_boundary(
        manifests,
        metadata.unwrap(),
        active_backend_ids=active_backend_ids,
    )
    diagnostics = (*metadata.diagnostics, *boundary.diagnostics)
    if not boundary.is_ok:
        return Result.failure(diagnostics)
    return Result.ok(boundary.unwrap(), diagnostics=diagnostics)


def _language_type_map(
    entry: CatalogEntry,
    diagnostics: list[Diagnostic],
) -> LanguageTypeMap | None:
    typed_entries: list[LanguageTypeEntry] = []
    for source_type, value in entry.fields.items():
        fields = _as_map(value)
        if fields is None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-LANGUAGE-MAP-SHAPE",
                    f"language map {entry.name!r} type {source_type!r} must be "
                    "a field map containing string field 'type'",
                    location=entry.source_span.location,
                )
            )
            continue
        target_type = fields.get("type")
        if not isinstance(target_type, str) or not target_type:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-LANGUAGE-MAP-SHAPE",
                    f"language map {entry.name!r} type {source_type!r} must "
                    "define non-empty string field 'type'",
                    location=entry.source_span.location,
                )
            )
            continue
        typed_entries.append(
            LanguageTypeEntry(
                source_type=source_type,
                target_type=target_type,
                fields=fields,
            )
        )
    if not typed_entries:
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-LANGUAGE-MAP-EMPTY",
                f"language map {entry.name!r} must define at least one type entry",
                location=entry.source_span.location,
            )
        )
        return None
    return LanguageTypeMap(
        backend_id=entry.name,
        entries=tuple(typed_entries),
        source_span=entry.source_span,
    )


def _translation_map(
    entry: CatalogEntry,
    diagnostics: list[Diagnostic],
) -> TranslationMap | None:
    snippets: list[TranslationSnippet] = []
    for name, value in entry.fields.items():
        if not isinstance(value, str):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-TRANSLATION-MAP-SHAPE",
                    f"translation map {entry.name!r} entry {name!r} must be a "
                    "string template",
                    location=entry.source_span.location,
                )
            )
            continue
        snippets.append(TranslationSnippet(name=name, template=value))
    if not snippets:
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-TRANSLATION-MAP-EMPTY",
                f"translation map {entry.name!r} must define at least one snippet",
                location=entry.source_span.location,
            )
        )
        return None
    return TranslationMap(
        backend_id=entry.name,
        snippets=tuple(snippets),
        source_span=entry.source_span,
    )


def _as_map(value: CatalogValue) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return value
    return None
