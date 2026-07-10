"""Backend-owned snippets for specialization documentation examples."""

from __future__ import annotations

from tslc.backend.capability import BackendDocumentationFormatter, DocumentationSpec
from tslc.backend.cpp import CppBackend
from tslc.backend.target_capability import rust_extension_tag
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.signature_types import (
    CPP_SIGNATURE_TYPES,
    RUST_SIGNATURE_TYPES,
    rust_free_type,
)
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


class _CppDocumentationFormatter:
    def register_type(self, spec: LoweredSpecialization) -> str:
        return CppBackend().documentation_register_type(spec)

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
        if is_free_function(spec):
            call = _cpp_call(spec, ())
            prefix = "" if spec.result_kind == "void" else "auto result = "
            suffix = ";" if spec.result_kind == "void" else ";"
            return f"{prefix}{call}{suffix}"
        lines = [f"using Value = {spec.base_type_spelling};"]
        lines.append(_cpp_call_block(doc, "Vec", _cpp_vector_type(spec), _CPP_DIRECT_COMMENT))
        lines.append(
            _cpp_call_block(
                doc,
                "NativeVec",
                "tsl::dataparallel::simd_for_t<tsl::dataparallel::native, Value>",
                _NATIVE_COMMENT,
            )
        )
        lane_count = static_lane_count(doc)
        if lane_count is not None:
            lines.append(
                _cpp_call_block(
                    doc,
                    "FixedVec",
                    "tsl::dataparallel::simd_for_t<"
                    f"tsl::dataparallel::fixed<{lane_count}>, Value>",
                    _FIXED_COMMENT,
                )
            )
            lines.append(
                _cpp_call_block(
                    doc,
                    "GenericVec",
                    "tsl::dataparallel::simd_for_t<"
                    f"tsl::dataparallel::generic<{lane_count}>, Value>",
                    _GENERIC_COMMENT,
                )
            )
        return "\n".join(lines)


class _RustDocumentationFormatter:
    def register_type(self, spec: LoweredSpecialization) -> str:
        return spec.register_spelling

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
        if is_free_function(spec):
            call = _rust_call(spec, ())
            if spec.safety.caller_unsafe:
                call = f"unsafe {{ {call} }}"
            prefix = "" if spec.result_kind == "void" else "let result = "
            suffix = ";" if spec.result_kind == "void" else ";"
            return f"{prefix}{call}{suffix}"
        lines = [
            f"type Value = {spec.base_type_spelling};",
            "// Profile is the generated profile policy used by VectorFor.",
            "type Profile = profile::algo::Profile;",
        ]
        lines.append(_rust_call_block(doc, "S", _rust_vector_type(spec), _RUST_DIRECT_COMMENT))
        lines.append(
            _rust_call_block(
                doc,
                "NativeVec",
                "<dataparallel::Native as VectorFor<Profile, Value>>::Vec",
                _NATIVE_COMMENT,
            )
        )
        lane_count = static_lane_count(doc)
        if lane_count is not None:
            lines.append(
                _rust_call_block(
                    doc,
                    "FixedVec",
                    f"<dataparallel::Fixed<{lane_count}> as VectorFor<Profile, Value>>::Vec",
                    _FIXED_COMMENT,
                )
            )
            lines.append(
                _rust_call_block(
                    doc,
                    "GenericVec",
                    f"<dataparallel::Generic<{lane_count}> as VectorFor<Profile, Value>>::Vec",
                    _GENERIC_COMMENT,
                )
            )
        return "\n".join(lines)


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
        return CPP_SIGNATURE_TYPES.free_type(spec.result_kind, base=spec.base_type_spelling)
    if spec.target is not None:
        return "typename ToVec::register_type"
    return CPP_SIGNATURE_TYPES.result_type(spec.result_kind)


def _rust_facade_result_type(spec: LoweredSpecialization) -> str:
    if is_free_function(spec):
        return rust_free_type(spec.result_kind, spec.base_type_spelling)
    if spec.target is not None:
        return "T::RegisterType"
    return RUST_SIGNATURE_TYPES.owner_type(spec.result_kind, owner="S")


def _cpp_call_block(
    doc: DocumentationSpec, vec_alias: str, vec_type: str, comment: str
) -> str:
    spec = doc.spec
    lines = [
        f"{{ // {comment}",
        f"  using {vec_alias} = {vec_type};",
    ]
    if spec.target is not None:
        lines.append(f"  using ToVec = {_strip_global_scope(spec.target.vector_spelling)};")
    lines.append(f"  {_cpp_statement(spec, vec_alias)}")
    lines.append("}")
    return "\n".join(lines)


def _cpp_statement(spec: LoweredSpecialization, vec_alias: str) -> str:
    call = _cpp_call(spec, (vec_alias,))
    if spec.result_kind == "void":
        return f"{call};"
    return f"auto result = {call};"


def _cpp_call(spec: LoweredSpecialization, vec_args: tuple[str, ...]) -> str:
    return _format_call(
        f"tsl::{spec.primitive_name}",
        _cpp_template_args(spec, vec_args),
        _runtime_args(spec),
        template_open="<",
        template_close=">",
    )


def _rust_call_block(
    doc: DocumentationSpec, vec_alias: str, vec_type: str, comment: str
) -> str:
    spec = doc.spec
    lines = [
        f"{{ // {comment}",
        f"  type {vec_alias} = {vec_type};",
    ]
    if spec.target is not None:
        lines.append(f"  type T = {spec.target.vector_spelling};")
    lines.append(f"  {_rust_statement(spec, vec_alias)}")
    lines.append("}")
    return "\n".join(lines)


def _rust_statement(spec: LoweredSpecialization, vec_alias: str) -> str:
    call = _rust_call(spec, (vec_alias,))
    if spec.safety.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    if spec.result_kind == "void":
        return f"{call};"
    return f"let result = {call};"


def _rust_call(spec: LoweredSpecialization, vec_args: tuple[str, ...]) -> str:
    return _format_call(
        rust_raw_identifier(spec.primitive_name),
        _rust_generic_args(spec, vec_args),
        _runtime_args(spec),
        template_open="::<",
        template_close=">",
    )


def _cpp_template_args(
    spec: LoweredSpecialization, vec_args: tuple[str, ...] = ("Vec",)
) -> tuple[str, ...]:
    if is_free_function(spec):
        return ()
    args = list(vec_args)
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


def _rust_generic_args(
    spec: LoweredSpecialization, vec_args: tuple[str, ...] = ("S",)
) -> tuple[str, ...]:
    if is_free_function(spec):
        return ()
    args = list(vec_args)
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
        return f"tsl::{spec.extension_name}<{spec.lane_parameter or 'LANES'}>"
    return f"tsl::{spec.extension_name}"


def _rust_vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        return (
            f"Simd<{spec.base_type_spelling}, "
            f"{rust_extension_tag(spec.extension_name)}<{spec.lane_parameter or 'LANES'}>>"
        )
    return f"Simd<{spec.base_type_spelling}, {rust_extension_tag(spec.extension_name)}>"


def _strip_global_scope(spelling: str) -> str:
    return spelling.replace("::tsl::", "tsl::").removeprefix("::")


_CPP_DIRECT_COMMENT = "use explicit extension identifier for the vector type"
_RUST_DIRECT_COMMENT = "use explicit extension identifier for the vector type"
_NATIVE_COMMENT = (
    'using "native" facade to select the available extension with the highest degree '
    "of data parallelism (or a scalable extension if available)"
)
_FIXED_COMMENT = (
    'using "fixed" facade to select a specific extension with a fixed degree of data '
    "parallelism; may not be available on all platforms"
)
_GENERIC_COMMENT = (
    'using "generic" facade to select an array-backed implementation with a fixed '
    "degree of data parallelism; is always available, but may be less efficient than "
    "the other facades"
)


CPP_DOCUMENTATION_FORMATTER = _CppDocumentationFormatter()
RUST_DOCUMENTATION_FORMATTER = _RustDocumentationFormatter()


__all__ = [
    "BackendDocumentationFormatter",
    "CPP_DOCUMENTATION_FORMATTER",
    "DocumentationSpec",
    "RUST_DOCUMENTATION_FORMATTER",
    "is_free_function",
    "static_lane_count",
]
