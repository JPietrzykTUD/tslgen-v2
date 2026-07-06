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
    expressions = _IndexedTuples()
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
                    )
                    primitive_rows = grouped.setdefault(primitive_id, {})
                    primitive_rows[row] = primitive_rows.get(row, 0) + 1
    primitive_docs = {
        name: _primitive_doc_row(name, specs, strings, expressions)
        for name, specs in sorted(primitive_specs.items())
    }
    payload = {
        "schema_version": 8,
        "columns": [
            "backend",
            "profile",
            "extension",
            "family",
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
            "emulator_kind",
            "emulator_profile",
            "group_key",
            "group_label",
            "group_rank",
            "summary",
            "tooltip",
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


def _profile_row(
    profile: "ProfileRender",
    *,
    strings: _StringTable,
    features: _IndexedTuples,
) -> list[int]:
    emulator = profile.profile.emulator
    profile_features = tuple(sorted(profile.profile.features))
    group = _profile_group(profile)
    summary = _profile_summary(profile)
    return [
        strings.id(profile.profile.name),
        strings.id(profile.profile.family),
        features.id(
            tuple(strings.id(feature) for feature in profile_features)
        ),
        strings.id(emulator.kind if emulator is not None else ""),
        strings.id(emulator.profile if emulator is not None else ""),
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
        strings.id(spec.implementation_state.value),
        strings.id(_width_label(spec, extension)),
        strings.id(_width_rank(spec, extension)),
        strings.id(_extension_group(spec)),
        strings.id(_extension_rank(spec, extension_family, extension)),
        strings.id(_text_rank(extension_family)),
    )


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
    if doc is None:
        return None
    facade = _backend_facade(doc)
    expression = _backend_expression(doc)
    if facade is None or expression is None:
        return None
    return (
        strings.id(backend_id),
        strings.id(_backend_label(backend_id)),
        strings.id(facade),
        strings.id(expression),
    )


def _backend_facade(doc: _DocSpec) -> str | None:
    if doc.spec.backend_id == "cpp":
        return _cpp_facade(doc)
    if doc.spec.backend_id == "rust":
        return _rust_facade(doc)
    return None


def _backend_expression(doc: _DocSpec) -> str | None:
    if doc.spec.backend_id == "cpp":
        return _cpp_expression(doc)
    if doc.spec.backend_id == "rust":
        return _rust_expression(doc)
    return None


def _cpp_facade(doc: _DocSpec) -> str:
    spec = doc.spec
    call = _format_call(
        f"tsl::{spec.primitive_name}",
        _cpp_template_args(spec),
        _runtime_args(spec),
        template_open="<",
        template_close=">",
    )
    return f"{call} -> {_cpp_facade_result_type(spec)}"


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


def _rust_facade(doc: _DocSpec) -> str:
    spec = doc.spec
    call = _format_call(
        rust_raw_identifier(spec.primitive_name),
        _rust_generic_args(spec),
        _runtime_args(spec),
        template_open="::<",
        template_close=">",
    )
    if spec.safety.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    return f"{call} -> {_rust_facade_result_type(spec)}"


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


def _cpp_facade_result_type(spec: LoweredSpecialization) -> str:
    if _is_free_function(spec):
        return DEFAULT_SUPPORT_POLICY.cpp_free_type(
            spec.result_kind,
            base_type=spec.base_type_spelling,
        )
    if spec.target is not None:
        return "typename ToVec::register_type"
    return DEFAULT_SUPPORT_POLICY.cpp_result_type(spec.result_kind)


def _rust_facade_result_type(spec: LoweredSpecialization) -> str:
    if _is_free_function(spec):
        return DEFAULT_SUPPORT_POLICY.rust_free_type(
            spec.result_kind,
            base_type=spec.base_type_spelling,
        )
    if spec.target is not None:
        return "T::RegisterType"
    return DEFAULT_SUPPORT_POLICY.rust_owner_type(spec.result_kind, owner="S")


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
