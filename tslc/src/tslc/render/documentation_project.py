"""Render generated documentation data for the specialization explorer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tslc.backend.cpp import CppBackend
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender

_CPP_BACKEND = CppBackend()


def documentation_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    return [
        _artifact(
            "docs/specializations/specializations.json",
            _specializations_json(profiles),
            "application/json",
        ),
    ]


def _specializations_json(profiles: tuple[ProfileRender, ...]) -> str:
    strings = _StringTable()
    features = _IndexedTuples()
    safeties = _IndexedTuples()
    primitive_docs: dict[str, list[int]] = {}
    grouped: dict[int, dict[tuple[int, ...], int]] = {}
    for profile in profiles:
        for backend_id, by_primitive in profile.specializations_by_backend.items():
            for primitive_name in sorted(by_primitive):
                for spec in by_primitive[primitive_name]:
                    primitive_docs.setdefault(
                        primitive_name,
                        [
                            strings.id(primitive_name),
                            strings.id(spec.source_primitive_name),
                            strings.id(spec.documentation.brief),
                            strings.id(spec.documentation.detailed),
                            strings.id(spec.documentation.semantics),
                        ],
                    )
                    primitive_id = strings.id(spec.primitive_name)
                    row = _specialization_row(
                        spec,
                        backend_id=backend_id,
                        profile_name=profile.profile.name,
                        strings=strings,
                        features=features,
                        safeties=safeties,
                    )
                    primitive_rows = grouped.setdefault(primitive_id, {})
                    primitive_rows[row] = primitive_rows.get(row, 0) + 1
    payload = {
        "schema_version": 2,
        "columns": [
            "backend",
            "profile",
            "extension",
            "type_tag",
            "register_type",
            "features",
            "safety",
            "count",
        ],
        "strings": strings.values,
        "features": features.values,
        "safeties": [
            [caller, internal, list(reasons)]
            for caller, internal, reasons in safeties.values
        ],
        "primitives": [
            primitive_docs[name] for name in sorted(primitive_docs)
        ],
        "specialization_groups": [
            [
                primitive_id,
                [
                    [*row, count] if count > 1 else list(row)
                    for row, count in sorted(rows.items())
                ],
            ]
            for primitive_id, rows in sorted(grouped.items())
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"


class _StringTable:
    def __init__(self) -> None:
        self._ids: dict[str, int] = {}
        self.values: list[str] = []

    def id(self, value: str | None) -> int:
        text = value or ""
        existing = self._ids.get(text)
        if existing is not None:
            return existing
        identifier = len(self.values)
        self._ids[text] = identifier
        self.values.append(text)
        return identifier


class _IndexedTuples:
    def __init__(self) -> None:
        self._ids: dict[tuple[Any, ...], int] = {}
        self.values: list[tuple[Any, ...]] = []

    def id(self, value: tuple[Any, ...]) -> int:
        existing = self._ids.get(value)
        if existing is not None:
            return existing
        identifier = len(self.values)
        self._ids[value] = identifier
        self.values.append(value)
        return identifier


def _specialization_row(
    spec: LoweredSpecialization,
    *,
    backend_id: str,
    profile_name: str,
    strings: _StringTable,
    features: _IndexedTuples,
    safeties: _IndexedTuples,
) -> tuple[int, ...]:
    feature_id = features.id(
        tuple(strings.id(feature) for feature in sorted(spec.required_features))
    )
    safety_id = safeties.id(
        (
            spec.safety.caller_unsafe,
            spec.safety.internal_unsafe,
            tuple(strings.id(reason) for reason in sorted(spec.safety.reasons)),
        )
    )
    return (
        strings.id(backend_id),
        strings.id(profile_name),
        strings.id(spec.extension_name),
        strings.id(spec.type_tag),
        strings.id(_register_type(spec, backend_id)),
        feature_id,
        safety_id,
    )


def _register_type(spec: LoweredSpecialization, backend_id: str) -> str:
    if backend_id == "cpp":
        return _CPP_BACKEND.documentation_register_type(spec)
    return spec.register_spelling


def _artifact(logical_path: str, content: str, media_type: str) -> Artifact:
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
    )


__all__ = ["documentation_artifacts"]
