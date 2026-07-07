"""Render generated documentation data for the specialization explorer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tslc.backend.cpp import CppBackend
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.render.documentation_formatters import (
    DocumentationSpec as _DocSpec,
    documentation_formatter,
    is_free_function,
    static_lane_count,
)

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
    expressions = _IndexedTuples()
    target_classes = _IndexedTargetClasses(strings)
    profile_rows = [
        _profile_row(profile, strings=strings, features=features)
        for profile in profiles
    ]
    primitive_specs: dict[str, list[_DocSpec]] = {}
    grouped: dict[int, dict[tuple[int, ...], int]] = {}
    backend_ids: set[str] = set()
    type_tags: set[str] = set()
    for profile in profiles:
        for backend_id, by_primitive in profile.specializations_by_backend.items():
            backend_ids.add(backend_id)
            for primitive_name in sorted(by_primitive):
                for spec in by_primitive[primitive_name]:
                    type_tags.add(spec.type_tag)
                    primitive_specs.setdefault(primitive_name, []).append(
                        _DocSpec(
                            spec=spec,
                            extension=profile.extensions.get(spec.extension_name),
                        )
                    )
                    primitive_id = strings.id(spec.primitive_name)
                    row = _specialization_row(
                        spec,
                        backend_id=backend_id,
                        profile_name=profile.profile.name,
                        extension_family=_extension_family(profile, spec),
                        extension=profile.extensions.get(spec.extension_name),
                        strings=strings,
                        features=features,
                        safeties=safeties,
                        target_classes=target_classes,
                    )
                    primitive_rows = grouped.setdefault(primitive_id, {})
                    primitive_rows[row] = primitive_rows.get(row, 0) + 1
    primitive_docs = {
        name: _primitive_doc_row(name, specs, strings, expressions)
        for name, specs in sorted(primitive_specs.items())
    }
    payload = {
        "schema_version": 9,
        "columns": [
            "backend",
            "profile",
            "extension",
            "family",
            "target_class",
            "type_tag",
            "register_type",
            "features",
            "safety",
            "implementation_state",
            "width_label",
            "width_rank",
            "extension_group",
            "extension_rank",
            "family_rank",
            "count",
        ],
        "profile_columns": [
            "profile",
            "family",
            "features",
            "runner_kind",
            "runner_profile",
            "group_key",
            "group_label",
            "group_rank",
            "summary",
            "tooltip",
            "sort_key",
        ],
        "target_class_columns": [
            "key",
            "label",
            "family",
            "width_label",
            "sort_key",
        ],
        "backends": [
            _backend_row(backend_id, strings)
            for backend_id in sorted(backend_ids)
        ],
        "types": [
            _type_row(type_tag, strings)
            for type_tag in sorted(type_tags, key=_type_sort_key)
            if _is_specialized_data_type(type_tag)
        ],
        "strings": strings.values,
        "features": features.values,
        "expressions": expressions.values,
        "safeties": [
            [caller, internal, list(reasons)]
            for caller, internal, reasons in safeties.values
        ],
        "target_classes": target_classes.values,
        "profiles": profile_rows,
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


def _primitive_doc_row(
    primitive_name: str,
    specs: list[_DocSpec],
    strings: _StringTable,
    expressions: _IndexedTuples,
) -> list[int]:
    doc_spec = _representative_spec(specs)
    assert doc_spec is not None
    expression_rows = tuple(
        row
        for backend_id in sorted({doc.spec.backend_id for doc in specs})
        if (row := _expression_row(specs, backend_id, strings)) is not None
    )
    return [
        strings.id(primitive_name),
        strings.id(doc_spec.spec.source_primitive_name),
        strings.id(doc_spec.spec.documentation.brief),
        strings.id(doc_spec.spec.documentation.detailed),
        strings.id(doc_spec.spec.documentation.semantics),
        strings.id(_signature_summary(doc_spec.spec)),
        expressions.id(expression_rows),
    ]


def _representative_spec(
    specs: list[_DocSpec],
    *,
    backend_id: str | None = None,
) -> _DocSpec | None:
    candidates = [
        doc for doc in specs if backend_id is None or doc.spec.backend_id == backend_id
    ]
    if not candidates:
        return None
    return sorted(candidates, key=_representative_rank)[0]


def _representative_rank(doc: _DocSpec) -> tuple[int, int, str, str, str]:
    spec = doc.spec
    lane_count = static_lane_count(doc)
    lane_rank = 2
    if lane_count is not None:
        lane_rank = 0 if lane_count > 1 else 1
    return (
        1 if is_free_function(spec) else 0,
        lane_rank,
        spec.extension_name,
        spec.type_tag,
        spec.primitive_name,
    )


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


def _profile_row(
    profile: "ProfileRender",
    *,
    strings: _StringTable,
    features: _IndexedTuples,
) -> list[int]:
    runner = profile.profile.runner
    profile_features = tuple(sorted(profile.profile.features))
    group = _profile_group(profile)
    summary = _profile_summary(profile)
    return [
        strings.id(profile.profile.name),
        strings.id(profile.profile.family),
        features.id(
            tuple(strings.id(feature) for feature in profile_features)
        ),
        strings.id(runner.kind if runner is not None else ""),
        strings.id(runner.profile if runner is not None else ""),
        strings.id(group[0]),
        strings.id(group[1]),
        strings.id(group[2]),
        strings.id(summary),
        strings.id(_profile_tooltip(profile, summary)),
        strings.id(_profile_sort_key(profile)),
    ]


def _backend_row(backend_id: str, strings: _StringTable) -> list[int]:
    return [
        strings.id(backend_id),
        strings.id(_backend_label(backend_id)),
        strings.id(_text_rank(backend_id)),
    ]


def _type_row(type_tag: str, strings: _StringTable) -> list[int]:
    return [
        strings.id(type_tag),
        strings.id(_type_short_label(type_tag)),
        strings.id(_type_label(type_tag)),
        strings.id(_type_sort_key(type_tag)),
    ]


def _specialization_row(
    spec: LoweredSpecialization,
    *,
    backend_id: str,
    profile_name: str,
    extension_family: str,
    extension: Extension | None,
    strings: _StringTable,
    features: _IndexedTuples,
    safeties: _IndexedTuples,
    target_classes: "_IndexedTargetClasses",
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
        strings.id(extension_family),
        target_classes.id(spec, extension),
        strings.id(spec.type_tag),
        strings.id(_register_type(spec, backend_id)),
        feature_id,
        safety_id,
        strings.id(spec.implementation_state.value),
        strings.id(_width_label(spec, extension)),
        strings.id(_width_rank(spec, extension)),
        strings.id(_extension_group(spec)),
        strings.id(_extension_rank(spec, extension_family, extension)),
        strings.id(_text_rank(extension_family)),
    )


class _IndexedTargetClasses:
    def __init__(self, strings: _StringTable) -> None:
        self._strings = strings
        self._ids: dict[str, int] = {}
        self.values: list[list[int]] = []

    def id(self, spec: LoweredSpecialization, extension: Extension | None) -> int:
        row = _target_class_row(spec, extension, self._strings)
        key = self._strings.values[row[0]]
        existing = self._ids.get(key)
        if existing is not None:
            return existing
        identifier = len(self.values)
        self._ids[key] = identifier
        self.values.append(row)
        return identifier


def _target_class_row(
    spec: LoweredSpecialization,
    extension: Extension | None,
    strings: _StringTable,
) -> list[int]:
    family, width = _target_class_parts(spec, extension)
    key = _target_class_key(family, width)
    label = _target_class_label(family, width)
    return [
        strings.id(key),
        strings.id(label),
        strings.id(family),
        strings.id(width),
        strings.id(_target_class_sort_key(family, width)),
    ]


def _target_class_parts(
    spec: LoweredSpecialization,
    extension: Extension | None,
) -> tuple[str, str]:
    if extension is None:
        return ("unknown", "unknown")
    family = _public_target_family(extension.family or "unclassified")
    if family == "scalar":
        return ("scalar", "scalar")
    if family == "aarch64" and extension.name.startswith("sve"):
        return (family, "SVE")
    if extension.vector_bits_kind == "scalable":
        return (family, "scalable")
    if spec.uses_sized_vector:
        return ("generic", "lanes")
    if extension.vector_bits > 0:
        return (family, f"{extension.vector_bits}-bit")
    return (family, "scalar")


def _public_target_family(family: str) -> str:
    return "aarch64" if family == "arm" else family


def _target_class_key(family: str, width: str) -> str:
    return (
        f"{family}_{width}"
        .casefold()
        .replace(" ", "_")
        .replace("-", "_")
    )


def _target_class_label(family: str, width: str) -> str:
    if family == "scalar":
        return "scalar"
    if family == "generic":
        return "generic lanes"
    return f"{family} {width}"


def _target_class_sort_key(family: str, width: str) -> str:
    family_order = {
        "scalar": "00",
        "generic": "01",
        "x86": "10",
        "aarch64": "20",
    }.get(family, f"90-{family}")
    width_order = {
        "scalar": "0000",
        "lanes": "0001",
        "128-bit": "0128",
        "256-bit": "0256",
        "512-bit": "0512",
        "SVE": "9998",
        "scalable": "9999",
        "unknown": "zzzz",
    }.get(width, f"z-{width}")
    return f"{family_order}:{width_order}:{family}:{width}"


def _extension_family(profile: ProfileRender, spec: LoweredSpecialization) -> str:
    extension = profile.extensions.get(spec.extension_name)
    return extension.family if extension is not None else ""


def _profile_group(profile: ProfileRender) -> tuple[str, str, str]:
    family = profile.profile.family or "unclassified"
    return (
        family,
        _human_label(family),
        _text_rank(family),
    )


def _profile_summary(profile: ProfileRender, feature_limit: int = 2) -> str:
    family = profile.profile.family or "unclassified"
    base = f"{_human_label(family)} class"
    features = tuple(sorted(profile.profile.features))
    if not features:
        return base
    return f"{base} + {_feature_summary(features, feature_limit)}"


def _profile_tooltip(profile: ProfileRender, summary: str) -> str:
    features = tuple(sorted(profile.profile.features))
    feature_text = ", ".join(features) if features else "none"
    return "\n".join(
        (
            profile.profile.name,
            f"Class: {summary}",
            f"Features: {feature_text}",
        )
    )


def _profile_sort_key(profile: ProfileRender) -> str:
    features = tuple(sorted(profile.profile.features))
    return ":".join(
        (
            _text_rank(profile.profile.family or "unclassified"),
            str(len(features)).zfill(4),
            "|".join(features),
            profile.profile.name,
        )
    )


def _register_type(spec: LoweredSpecialization, backend_id: str) -> str:
    if backend_id == "cpp":
        return _CPP_BACKEND.documentation_register_type(spec)
    return spec.register_spelling


def _width_label(spec: LoweredSpecialization, extension: Extension | None) -> str:
    if extension is None:
        return "unknown"
    if extension.vector_bits_kind == "scalable":
        return "scalable"
    if spec.uses_sized_vector:
        return "generic lanes"
    if extension.vector_bits > 0:
        return f"{extension.vector_bits}-bit"
    return "scalar"


def _width_rank(spec: LoweredSpecialization, extension: Extension | None) -> str:
    if extension is None:
        return "z-unknown"
    if extension.vector_bits_kind == "scalable":
        return "9999"
    if spec.uses_sized_vector:
        return "0001"
    if extension.vector_bits > 0:
        return str(extension.vector_bits).zfill(4)
    return "0000"


def _extension_group(spec: LoweredSpecialization) -> str:
    return spec.extension_name


def _extension_rank(
    spec: LoweredSpecialization,
    extension_family: str,
    extension: Extension | None,
) -> str:
    return ":".join(
        (
            _text_rank(extension_family),
            _width_rank(spec, extension),
            spec.extension_name,
        )
    )


def _expression_row(
    specs: list[_DocSpec],
    backend_id: str,
    strings: _StringTable,
) -> tuple[int, int, int, int] | None:
    doc = _representative_spec(specs, backend_id=backend_id)
    formatter = documentation_formatter(backend_id)
    if doc is None or formatter is None:
        return None
    facade = formatter.facade(doc)
    expression = formatter.expression(doc)
    return (
        strings.id(backend_id),
        strings.id(_backend_label(backend_id)),
        strings.id(facade),
        strings.id(expression),
    )


def _signature_summary(spec: LoweredSpecialization) -> str:
    output = _signature_kind_phrase(spec.result_kind)
    inputs = tuple(_signature_kind_phrase(kind) for kind in spec.param_kinds)
    return f"({', '.join(inputs)}) => {output}"


def _signature_kind_phrase(kind: str) -> str:
    labels = {
        "v": "SIMD register",
        "vt": "target SIMD register",
        "m": "mask",
        "im": "integral mask",
        "s": "scalar",
        "sImm": "compile-time scalar immediate",
        "usize": "size",
        "ptr": "mutable pointer",
        "cptr": "const pointer",
        "cptr+": "const pointer with source element type",
        "s[]": "scalar array",
        "lanes<s>": "lane value list",
        "o": "output stream",
        "void": "no return value",
    }
    return labels.get(kind, kind)


def _backend_label(backend_id: str) -> str:
    return _human_label(backend_id)


def _type_short_label(type_tag: str) -> str:
    if type_tag == "f32":
        return "f32"
    if type_tag == "f64":
        return "f64"
    if type_tag.startswith("si"):
        return f"i{type_tag[2:]}"
    if type_tag.startswith("ui"):
        return f"u{type_tag[2:]}"
    return type_tag


def _type_label(type_tag: str) -> str:
    if type_tag == "f32":
        return "float"
    if type_tag == "f64":
        return "double"
    if type_tag.startswith("si"):
        return f"signed int{type_tag[2:]}"
    if type_tag.startswith("ui"):
        return f"unsigned int{type_tag[2:]}"
    return type_tag


def _type_sort_key(type_tag: str) -> str:
    order = {
        "si8": "00",
        "si16": "01",
        "si32": "02",
        "si64": "03",
        "ui8": "04",
        "ui16": "05",
        "ui32": "06",
        "ui64": "07",
        "f32": "08",
        "f64": "09",
    }
    return order.get(type_tag, f"z-{type_tag}")


def _is_specialized_data_type(type_tag: str) -> bool:
    return type_tag != "ptr"


def _feature_summary(features: tuple[str, ...], limit: int = 5) -> str:
    if not features:
        return "none"
    if len(features) <= limit:
        return ", ".join(features)
    return f"{', '.join(features[:limit])} +{len(features) - limit}"


def _human_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip() or "unclassified"


def _text_rank(value: str) -> str:
    return _human_label(value).casefold()


def _artifact(logical_path: str, content: str, media_type: str) -> Artifact:
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
    )


__all__ = ["documentation_artifacts"]
