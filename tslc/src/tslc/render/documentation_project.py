"""Render generated documentation data for the specialization explorer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tslc.backend.cpp import CppBackend
from tslc.backend.target_capability import rust_extension_tag
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender

_CPP_BACKEND = CppBackend()


@dataclass(frozen=True, slots=True)
class _DocSpec:
    spec: LoweredSpecialization
    extension: Extension | None


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
    primitive_specs: dict[str, list[_DocSpec]] = {}
    grouped: dict[int, dict[tuple[int, ...], int]] = {}
    for profile in profiles:
        for backend_id, by_primitive in profile.specializations_by_backend.items():
            for primitive_name in sorted(by_primitive):
                for spec in by_primitive[primitive_name]:
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
                        strings=strings,
                        features=features,
                        safeties=safeties,
                    )
                    primitive_rows = grouped.setdefault(primitive_id, {})
                    primitive_rows[row] = primitive_rows.get(row, 0) + 1
    primitive_docs = {
        name: _primitive_doc_row(name, specs, strings)
        for name, specs in sorted(primitive_specs.items())
    }
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


def _primitive_doc_row(
    primitive_name: str,
    specs: list[_DocSpec],
    strings: _StringTable,
) -> list[int]:
    doc_spec = _representative_spec(specs)
    cpp_spec = _representative_spec(specs, backend_id="cpp")
    rust_spec = _representative_spec(specs, backend_id="rust")
    assert doc_spec is not None
    return [
        strings.id(primitive_name),
        strings.id(doc_spec.spec.source_primitive_name),
        strings.id(doc_spec.spec.documentation.brief),
        strings.id(doc_spec.spec.documentation.detailed),
        strings.id(doc_spec.spec.documentation.semantics),
        strings.id(_cpp_expression(cpp_spec) if cpp_spec is not None else ""),
        strings.id(_rust_expression(rust_spec) if rust_spec is not None else ""),
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
    lane_count = _static_lane_count(doc)
    lane_rank = 2
    if lane_count is not None:
        lane_rank = 0 if lane_count > 1 else 1
    return (
        1 if _is_free_function(spec) else 0,
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


def _cpp_expression(doc: _DocSpec) -> str:
    spec = doc.spec
    lines = list(_cpp_alias_lines(doc))
    call = _format_call(
        f"tsl::{spec.primitive_name}",
        _cpp_template_args(spec),
        _runtime_args(spec),
        template_open="<",
        template_close=">",
    )
    if spec.result_kind == "void":
        lines.append(f"{call};")
    else:
        lines.append(f"auto result = {call};")
    return "\n".join(lines)


def _rust_expression(doc: _DocSpec) -> str:
    spec = doc.spec
    lines = list(_rust_alias_lines(doc))
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
        lines.append(f"{call};")
    else:
        lines.append(f"let result = {call};")
    return "\n".join(lines)


def _cpp_alias_lines(doc: _DocSpec) -> tuple[str, ...]:
    spec = doc.spec
    if _is_free_function(spec):
        return ()
    lines = [
        f"using Value = {spec.base_type_spelling};",
        f"using Vec = {_cpp_vector_type(spec)};",
    ]
    if spec.target is not None:
        lines.append(f"using ToVec = {_strip_global_scope(spec.target.vector_spelling)};")
    lines.append(
        "using NativeVec = "
        "tsl::dataparallel::simd_for_t<tsl::dataparallel::native, Value>;"
    )
    lane_count = _static_lane_count(doc)
    if lane_count is not None:
        lines.extend(
            [
                "using FixedVec = "
                f"tsl::dataparallel::simd_for_t<"
                f"tsl::dataparallel::fixed<{lane_count}>, Value>;",
                "using GenericVec = "
                f"tsl::dataparallel::simd_for_t<"
                f"tsl::dataparallel::generic<{lane_count}>, Value>;",
            ]
        )
    return tuple(lines)


def _rust_alias_lines(doc: _DocSpec) -> tuple[str, ...]:
    spec = doc.spec
    if _is_free_function(spec):
        return ()
    lines = [
        f"type Value = {spec.base_type_spelling};",
        f"type S = {_rust_vector_type(spec)};",
    ]
    if spec.target is not None:
        lines.append(f"type T = {spec.target.vector_spelling};")
    lines.append(
        "type NativeVec = "
        "<dataparallel::Native as VectorFor<profile::algo::Profile, Value>>::Vec;"
    )
    lane_count = _static_lane_count(doc)
    if lane_count is not None:
        lines.extend(
            [
                "type FixedVec = "
                f"<dataparallel::Fixed<{lane_count}> "
                "as VectorFor<profile::algo::Profile, Value>>::Vec;",
                "type GenericVec = "
                f"<dataparallel::Generic<{lane_count}> "
                "as VectorFor<profile::algo::Profile, Value>>::Vec;",
            ]
        )
    return tuple(lines)


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


def _cpp_vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return _strip_global_scope(spec.vector_spelling)
    return f"tsl::simd<{spec.base_type_spelling}, {_cpp_extension_type(spec)}>"


def _cpp_extension_type(spec: LoweredSpecialization) -> str:
    if spec.uses_sized_vector:
        return f"tsl::generic<{spec.lane_parameter or 'LANES'}>"
    return f"tsl::{spec.extension_name}"


def _rust_vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        return f"Simd<{spec.base_type_spelling}, Generic<{spec.lane_parameter or 'LANES'}>>"
    return f"Simd<{spec.base_type_spelling}, {rust_extension_tag(spec.extension_name)}>"


def _static_lane_count(doc: _DocSpec) -> int | None:
    spec = doc.spec
    lane_parameter = spec.lane_parameter
    if lane_parameter is not None and lane_parameter.isdigit():
        return int(lane_parameter)
    if doc.extension is not None:
        return DEFAULT_SUPPORT_POLICY.lane_count(doc.extension, spec.type_tag)
    return None


def _strip_global_scope(spelling: str) -> str:
    return spelling.replace("::tsl::", "tsl::").removeprefix("::")


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
