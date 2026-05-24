from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, TypeGuard, cast

import yaml  # type: ignore[import-untyped]

from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.backends import (
    ACTIVE_BACKEND_IDS,
    DEFERRED_BACKEND_IDS,
    ArtifactSpec,
    BackendManifest,
    BackendManifestSet,
    BackendTemplatePolicy,
    backend_id_list_text,
)
from tslgen.domain.catalog import Catalog
from tslgen.domain.values import CatalogValue


SUPPORTED_BACKEND_MANIFEST_VERSION = 1

_DEFAULT_ARTIFACT_SPECS: FrozenMap[str, ArtifactSpec] = FrozenMap(
    {
        "cpp": ArtifactSpec(
            kind="generated",
            logical_name="generated",
            extension="hpp",
        ),
        "rust": ArtifactSpec(
            kind="generated",
            logical_name="generated",
            extension="rs",
        ),
    }
)


def load_backend_manifest(path: Path) -> Result[BackendManifest]:
    path = Path(path)
    location = SourceLocation(path=path, line=1, column=1)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-READ",
                    f"could not read backend manifest {path.as_posix()!r}: {exc}",
                    location=location,
                ),
            )
        )
    return parse_backend_manifest_text(
        text,
        source_name=path.as_posix(),
        location=location,
    )


def load_backend_manifests(paths: Iterable[Path]) -> Result[BackendManifestSet]:
    diagnostics: list[Diagnostic] = []
    manifests: list[BackendManifest] = []
    for path in sorted((Path(path) for path in paths), key=lambda item: item.as_posix()):
        loaded = load_backend_manifest(path)
        diagnostics.extend(loaded.diagnostics)
        if loaded.is_ok:
            manifests.append(loaded.unwrap())

    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))
    return _manifest_set(manifests, diagnostics=diagnostics)


def parse_backend_manifest_text(
    text: str,
    *,
    source_name: str | None = None,
    location: SourceLocation | None = None,
) -> Result[BackendManifest]:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SYNTAX",
                    f"backend manifest is not valid YAML: {exc}",
                    location=location,
                ),
            )
        )
    if not isinstance(loaded, Mapping):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    "backend manifest root must be a mapping",
                    location=location,
                ),
            )
        )
    return backend_manifest_from_mapping(
        cast(Mapping[str, object], loaded),
        source_name=source_name,
        location=location,
    )


def backend_manifest_from_mapping(
    data: Mapping[str, object],
    *,
    source_name: str | None = None,
    location: SourceLocation | None = None,
) -> Result[BackendManifest]:
    diagnostics: list[Diagnostic] = []
    version = _required_int(
        data,
        "version",
        diagnostics,
        location=location,
    )
    if version is not None and version != SUPPORTED_BACKEND_MANIFEST_VERSION:
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-MANIFEST-VERSION",
                f"backend manifest version {version!r} is not supported; expected "
                f"{SUPPORTED_BACKEND_MANIFEST_VERSION}",
                location=location,
            )
        )

    backend_id = _required_string(data, "backend", diagnostics, location=location)
    language_id = (
        _optional_string(data, "language", diagnostics, location=location)
        or backend_id
    )
    artifacts = _artifact_specs(data, diagnostics, location=location)
    template_policy = _template_policy(data, diagnostics, location=location)
    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    assert version is not None
    assert backend_id is not None
    assert language_id is not None
    return Result.ok(
        BackendManifest(
            version=version,
            backend_id=backend_id,
            language_id=language_id,
            artifacts=artifacts,
            template_policy=template_policy,
            source_name=source_name,
        ),
        diagnostics=diagnostics,
    )


def backend_manifests_from_catalog(catalog: Catalog) -> Result[BackendManifestSet]:
    language_names = frozenset(
        entry.name for entry in catalog.entries if entry.kind == "language"
    )
    translation_names = frozenset(
        entry.name for entry in catalog.entries if entry.kind == "translation"
    )
    diagnostics: list[Diagnostic] = []
    for backend_id in sorted(language_names - translation_names):
        if backend_id not in ACTIVE_BACKEND_IDS:
            continue
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-MANIFEST-MISSING-TRANSLATION",
                f"backend {backend_id!r} has language type data but no translation map",
            )
        )
    for backend_id in sorted(translation_names - language_names):
        if backend_id not in ACTIVE_BACKEND_IDS:
            continue
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-MANIFEST-MISSING-LANGUAGE",
                f"backend {backend_id!r} has translation data but no language type map",
            )
        )
    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    manifests: list[BackendManifest] = []
    for backend_id in sorted(language_names & translation_names):
        if backend_id in DEFERRED_BACKEND_IDS:
            continue
        if backend_id not in ACTIVE_BACKEND_IDS:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-UNSUPPORTED-BACKEND",
                    f"backend {backend_id!r} is not active for manifest "
                    f"derivation; active backends: "
                    f"{backend_id_list_text(ACTIVE_BACKEND_IDS)}",
                )
            )
            continue
        artifact = _DEFAULT_ARTIFACT_SPECS.get(backend_id)
        if artifact is None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-ARTIFACT-MISSING",
                    f"backend {backend_id!r} needs an artifact descriptor",
                )
            )
            continue
        manifests.append(
            BackendManifest(
                version=SUPPORTED_BACKEND_MANIFEST_VERSION,
                backend_id=backend_id,
                language_id=backend_id,
                artifacts=(artifact,),
            )
        )

    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))
    return _manifest_set(manifests, diagnostics=diagnostics)


def _manifest_set(
    manifests: Iterable[BackendManifest],
    *,
    diagnostics: Iterable[Diagnostic] = (),
) -> Result[BackendManifestSet]:
    diagnostics = tuple(diagnostics)
    manifest_tuple = tuple(manifests)
    backend_ids = [manifest.backend_id for manifest in manifest_tuple]
    duplicate_ids = sorted(
        backend_id for backend_id in set(backend_ids) if backend_ids.count(backend_id) > 1
    )
    if duplicate_ids:
        return Result.failure(
            (
                *diagnostics,
                *(
                    Diagnostic.error(
                        "TSL-BACKEND-MANIFEST-DUPLICATE-BACKEND",
                        f"duplicate backend manifest id {backend_id!r}",
                    )
                    for backend_id in duplicate_ids
                ),
            )
        )
    return Result.ok(BackendManifestSet(manifest_tuple), diagnostics=diagnostics)


def _artifact_specs(
    data: Mapping[str, object],
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> tuple[ArtifactSpec, ...]:
    artifact_values: list[object] = []
    if "artifact" in data:
        artifact_values.append(data["artifact"])
    if "artifacts" in data:
        artifacts = data["artifacts"]
        if isinstance(artifacts, list):
            artifact_values.extend(artifacts)
        else:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    "backend manifest field 'artifacts' must be a list",
                    location=location,
                )
            )

    if not artifact_values:
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-MANIFEST-MISSING",
                "backend manifest must define 'artifact' or 'artifacts'",
                location=location,
            )
        )
        return ()

    specs: list[ArtifactSpec] = []
    for value in artifact_values:
        if not isinstance(value, Mapping):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    "backend manifest artifact entries must be mappings",
                    location=location,
                )
            )
            continue
        artifact = cast(Mapping[str, object], value)
        kind = (
            _optional_string(artifact, "kind", diagnostics, location=location)
            or "generated"
        )
        name = _required_string(artifact, "name", diagnostics, location=location)
        extension = _required_string(
            artifact,
            "extension",
            diagnostics,
            location=location,
        )
        if name is None or extension is None:
            continue
        if extension.startswith("."):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    "backend manifest artifact extension must not include a "
                    "leading dot",
                    location=location,
                )
            )
            continue
        try:
            specs.append(ArtifactSpec(kind=kind, logical_name=name, extension=extension))
        except ValueError as exc:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    f"backend manifest artifact entry is invalid: {exc}",
                    location=location,
                )
            )

    targets = [spec.target_path.as_posix() for spec in specs]
    for target in sorted(target for target in set(targets) if targets.count(target) > 1):
        diagnostics.append(
            Diagnostic.error(
                "TSL-BACKEND-MANIFEST-DUPLICATE-ARTIFACT",
                f"backend manifest defines duplicate artifact target {target!r}",
                location=location,
            )
        )
    return tuple(specs)


def _template_policy(
    data: Mapping[str, object],
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> BackendTemplatePolicy:
    primary = _optional_mapping(data, "primary", diagnostics, location=location)
    specialization = _optional_mapping(
        data,
        "specialization",
        diagnostics,
        location=location,
    )
    specialization_overrides = _string_mapping(
        _nested_optional_mapping(
            specialization,
            "overrides",
            "specialization.overrides",
            diagnostics,
            location=location,
        ),
        "specialization.overrides",
        diagnostics,
        location=location,
    )
    return BackendTemplatePolicy(
        primary_default=_optional_string(
            primary or {},
            "default",
            diagnostics,
            location=location,
        ),
        primary_fallback=_optional_string(
            primary or {},
            "fallback",
            diagnostics,
            location=location,
        ),
        specialization_default=_optional_string(
            specialization or {},
            "default",
            diagnostics,
            location=location,
        ),
        specialization_overrides=FrozenMap(specialization_overrides),
        wrappers=_optional_string(data, "wrappers", diagnostics, location=location),
        trait=_optional_string(data, "tsl_trait", diagnostics, location=location),
        extra_fields=_extra_fields(data, diagnostics, location=location),
    )


def _extra_fields(
    data: Mapping[str, object],
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> FrozenMap[str, CatalogValue]:
    known = frozenset(
        {
            "artifact",
            "artifacts",
            "backend",
            "language",
            "primary",
            "specialization",
            "tsl_trait",
            "version",
            "wrappers",
        }
    )
    extras: dict[str, CatalogValue] = {}
    for key, value in data.items():
        if key in known:
            continue
        converted = _catalog_value(value)
        if converted is None and value is not None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    f"backend manifest extra field {key!r} has unsupported value "
                    "shape",
                    location=location,
                )
            )
            continue
        extras[key] = converted
    return FrozenMap(extras)


def _catalog_value(value: object) -> CatalogValue | None:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, list):
        list_values: list[CatalogValue] = []
        for item in value:
            if not _is_catalog_value_like(item):
                return None
            list_values.append(cast(CatalogValue, _catalog_value(item)))
        return tuple(list_values)
    if isinstance(value, Mapping):
        mapping_values: list[tuple[str, CatalogValue]] = []
        for key, item in value.items():
            if not isinstance(key, str) or not _is_catalog_value_like(item):
                return None
            mapping_values.append((key, cast(CatalogValue, _catalog_value(item))))
        return FrozenMap(mapping_values)
    return None


def _is_catalog_value_like(value: object) -> TypeGuard[CatalogValue]:
    if isinstance(value, str | int | float | bool) or value is None:
        return True
    if isinstance(value, list):
        return all(_is_catalog_value_like(item) for item in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _is_catalog_value_like(item)
            for key, item in value.items()
        )
    return False


def _required_string(
    data: Mapping[str, object],
    field_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> str | None:
    value = data.get(field_name)
    if isinstance(value, str) and value:
        return value
    diagnostics.append(
        Diagnostic.error(
            "TSL-BACKEND-MANIFEST-MISSING",
            f"backend manifest field {field_name!r} must be a non-empty string",
            location=location,
        )
    )
    return None


def _required_int(
    data: Mapping[str, object],
    field_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> int | None:
    value = data.get(field_name)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    diagnostics.append(
        Diagnostic.error(
            "TSL-BACKEND-MANIFEST-MISSING",
            f"backend manifest field {field_name!r} must be an integer",
            location=location,
        )
    )
    return None


def _optional_string(
    data: Mapping[str, object],
    field_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    diagnostics.append(
        Diagnostic.error(
            "TSL-BACKEND-MANIFEST-SHAPE",
            f"backend manifest field {field_name!r} must be a non-empty string",
            location=location,
        )
    )
    return None


def _string_mapping(
    data: Mapping[str, object] | None,
    field_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> dict[str, str]:
    if data is None:
        return {}
    values: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-BACKEND-MANIFEST-SHAPE",
                    f"backend manifest field {field_name!r} must contain only "
                    "string keys and values",
                    location=location,
                )
            )
            continue
        values[key] = value
    return values


def _as_mapping(value: object | None) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return None


def _optional_mapping(
    data: Mapping[str, object],
    field_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> Mapping[str, object] | None:
    if field_name not in data:
        return None
    value = data[field_name]
    mapping = _as_mapping(value)
    if mapping is not None:
        return mapping
    diagnostics.append(
        Diagnostic.error(
            "TSL-BACKEND-MANIFEST-SHAPE",
            f"backend manifest field {field_name!r} must be a mapping",
            location=location,
        )
    )
    return None


def _nested_optional_mapping(
    data: Mapping[str, object] | None,
    field_name: str,
    display_name: str,
    diagnostics: list[Diagnostic],
    *,
    location: SourceLocation | None,
) -> Mapping[str, object] | None:
    if data is None or field_name not in data:
        return None
    value = data[field_name]
    mapping = _as_mapping(value)
    if mapping is not None:
        return mapping
    diagnostics.append(
        Diagnostic.error(
            "TSL-BACKEND-MANIFEST-SHAPE",
            f"backend manifest field {display_name!r} must be a mapping",
            location=location,
        )
    )
    return None
