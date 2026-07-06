"""Render generated documentation data for the specialization explorer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tslc.backend.cpp import CppBackend
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

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
                            strings.id(_cpp_expression(spec)),
                            strings.id(_rust_expression(spec)),
                        ],
                    )
                    primitive_id = strings.id(spec.primitive_name)
                    row = _specialization_row(
                        spec,
                        backend_id=backend_id,
                        profile_name=profile.profile.name,
                        extension_family=_extension_family(profile, spec),
                        strings=strings,
                        features=features,
                        safeties=safeties,
                    )
                    primitive_rows = grouped.setdefault(primitive_id, {})
                    primitive_rows[row] = primitive_rows.get(row, 0) + 1
    payload = {
        "schema_version": 4,
        "columns": [
            "backend",
            "profile",
            "extension",
            "family",
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
    extension_family: str,
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
        strings.id(extension_family),
        strings.id(spec.type_tag),
        strings.id(_register_type(spec, backend_id)),
        feature_id,
        safety_id,
    )


def _extension_family(profile: ProfileRender, spec: LoweredSpecialization) -> str:
    extension = profile.extensions.get(spec.extension_name)
    return extension.family if extension is not None else ""


def _register_type(spec: LoweredSpecialization, backend_id: str) -> str:
    if backend_id == "cpp":
        return _CPP_BACKEND.documentation_register_type(spec)
    return spec.register_spelling


def _cpp_expression(spec: LoweredSpecialization) -> str:
    call = _format_call(
        f"tsl::{spec.primitive_name}",
        _cpp_template_args(spec),
        _runtime_args(spec),
        template_open="<",
        template_close=">",
    )
    if spec.result_kind == "void":
        return f"{call};"
    return f"auto result = {call};"


def _rust_expression(spec: LoweredSpecialization) -> str:
    call = _format_call(
        rust_raw_identifier(spec.primitive_name),
        _rust_generic_args(spec),
        _runtime_args(spec),
        template_open="::<",
        template_close=">",
    )
    if spec.safety.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    if spec.result_kind == "void":
        return f"{call};"
    return f"let result = {call};"


def _cpp_template_args(spec: LoweredSpecialization) -> tuple[str, ...]:
    if _is_free_function(spec):
        return ()
    args = ["Vec"]
    if spec.target is not None:
        args.append("ToVec")
    args.extend(param.name for param in spec.type_params)
    args.extend(_commented_arg(key, value) for key, value in spec.axis)
    if spec.immediate is not None:
        args.append(_commented_arg(spec.immediate[0], spec.immediate[0]))
    args.extend(
        _commented_arg(name, default or name)
        for name, _typ, default in spec.generic_params
    )
    return tuple(args)


def _rust_generic_args(spec: LoweredSpecialization) -> tuple[str, ...]:
    if _is_free_function(spec):
        return ()
    args = ["S"]
    args.extend(param.name for param in spec.type_params)
    if spec.target is not None:
        args.append("T")
    args.extend(_commented_arg(key, value) for key, value in spec.axis)
    if spec.immediate is not None:
        args.append(_commented_arg(spec.immediate[0], spec.immediate[0]))
    args.extend(
        _commented_arg(name, default or name)
        for name, _typ, default in spec.generic_params
    )
    return tuple(args)


def _runtime_args(spec: LoweredSpecialization) -> tuple[str, ...]:
    return tuple(
        name
        for name, kind in zip(spec.param_names, spec.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )


def _format_call(
    function_name: str,
    generic_args: tuple[str, ...],
    runtime_args: tuple[str, ...],
    *,
    template_open: str,
    template_close: str,
) -> str:
    generic_part = (
        f"{template_open}{', '.join(generic_args)}{template_close}"
        if generic_args
        else ""
    )
    return f"{function_name}{generic_part}({', '.join(runtime_args)})"


def _commented_arg(name: str, value: str) -> str:
    return f"/* {name} */ {value}"


def _is_free_function(spec: LoweredSpecialization) -> bool:
    return DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    )


def _artifact(logical_path: str, content: str, media_type: str) -> Artifact:
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
    )


__all__ = ["documentation_artifacts"]
