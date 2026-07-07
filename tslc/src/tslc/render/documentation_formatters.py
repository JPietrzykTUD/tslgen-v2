"""Backend-owned snippets for specialization documentation examples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.backend.target_capability import rust_extension_tag
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


@dataclass(frozen=True, slots=True)
class DocumentationSpec:
    spec: LoweredSpecialization
    extension: Extension | None


class BackendDocumentationFormatter(Protocol):
    backend_id: str

    def facade(self, doc: DocumentationSpec) -> str:
        """Return a compact callable facade for documentation tables."""

    def expression(self, doc: DocumentationSpec) -> str:
        """Return a small example expression for documentation tables."""


@dataclass(frozen=True, slots=True)
class _CppDocumentationFormatter:
    backend_id: str = "cpp"

    def facade(self, doc: DocumentationSpec) -> str:
        spec = doc.spec
        call = _format_call(
            f"tsl::{spec.primitive_name}",
            _cpp_template_args(spec),
            _runtime_args(spec),
            template_open="<",
            template_close=">",
        )
        return f"{call} -> {_cpp_facade_result_type(spec)}"

    def expression(self, doc: DocumentationSpec) -> str:
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


@dataclass(frozen=True, slots=True)
class _RustDocumentationFormatter:
    backend_id: str = "rust"

    def facade(self, doc: DocumentationSpec) -> str:
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

    def expression(self, doc: DocumentationSpec) -> str:
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


def documentation_formatter(backend_id: str) -> BackendDocumentationFormatter | None:
    if backend_id == CPP_DOCUMENTATION_FORMATTER.backend_id:
        return CPP_DOCUMENTATION_FORMATTER
    if backend_id == RUST_DOCUMENTATION_FORMATTER.backend_id:
        return RUST_DOCUMENTATION_FORMATTER
    return None


def is_free_function(spec: LoweredSpecialization) -> bool:
    return DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    )


def static_lane_count(doc: DocumentationSpec) -> int | None:
    spec = doc.spec
    lane_parameter = spec.lane_parameter
    if lane_parameter is not None and lane_parameter.isdigit():
        return int(lane_parameter)
    if doc.extension is not None:
        return DEFAULT_SUPPORT_POLICY.lane_count(doc.extension, spec.type_tag)
    return None


def _cpp_facade_result_type(spec: LoweredSpecialization) -> str:
    if is_free_function(spec):
        return DEFAULT_SUPPORT_POLICY.cpp_free_type(
            spec.result_kind,
            base_type=spec.base_type_spelling,
        )
    if spec.target is not None:
        return "typename ToVec::register_type"
    return DEFAULT_SUPPORT_POLICY.cpp_result_type(spec.result_kind)


def _rust_facade_result_type(spec: LoweredSpecialization) -> str:
    if is_free_function(spec):
        return DEFAULT_SUPPORT_POLICY.rust_free_type(
            spec.result_kind,
            base_type=spec.base_type_spelling,
        )
    if spec.target is not None:
        return "T::RegisterType"
    return DEFAULT_SUPPORT_POLICY.rust_owner_type(spec.result_kind, owner="S")


def _cpp_alias_lines(doc: DocumentationSpec) -> tuple[str, ...]:
    spec = doc.spec
    if is_free_function(spec):
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
    lane_count = static_lane_count(doc)
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


def _rust_alias_lines(doc: DocumentationSpec) -> tuple[str, ...]:
    spec = doc.spec
    if is_free_function(spec):
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
    lane_count = static_lane_count(doc)
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
    if is_free_function(spec):
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
    if is_free_function(spec):
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


def _strip_global_scope(spelling: str) -> str:
    return spelling.replace("::tsl::", "tsl::").removeprefix("::")


CPP_DOCUMENTATION_FORMATTER = _CppDocumentationFormatter()
RUST_DOCUMENTATION_FORMATTER = _RustDocumentationFormatter()


__all__ = [
    "BackendDocumentationFormatter",
    "DocumentationSpec",
    "documentation_formatter",
    "is_free_function",
    "static_lane_count",
]
