"""C++ backend: render a primitive as primary template + simd<> specializations + wrapper."""

from __future__ import annotations

from tslc.lower.lowerer import LoweredSpecialization


class CppBackend:
    backend_id = "cpp"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]  # all share the same signature shape
        parts = [f"template <class Vec>\nstruct {primitive_name}_impl;"]
        parts.extend(self._specialization(spec) for spec in specializations)
        parts.append(self._wrapper(primitive_name, shape))
        return "\n\n".join(parts)

    def _specialization(self, spec: LoweredSpecialization) -> str:
        key = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        params = ", ".join(
            f"{_param_type(kind)} {name}"
            for name, kind in zip(spec.param_names, spec.param_kinds)
        )
        return (
            f"template <>\nstruct {spec.primitive_name}_impl<{key}> {{\n"
            f"    using Vec = {key};\n"
            f"    static inline {_result_type(spec.result_kind)} apply({params}) {{\n"
            f"        {spec.body_text}\n"
            f"    }}\n"
            f"}};"
        )

    def _wrapper(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = ", ".join(
            f"{_param_type(kind)} {name}"
            for name, kind in zip(shape.param_names, shape.param_kinds)
        )
        names = ", ".join(shape.param_names)
        return (
            f"template <class Vec>\n"
            f"inline {_result_type(shape.result_kind)} {primitive_name}({params}) {{\n"
            f"    return {primitive_name}_impl<Vec>::apply({names});\n"
            f"}}"
        )


def _result_type(kind: str) -> str:
    return {
        "v": "typename Vec::register_type",
        "s": "typename Vec::base_type",
        "m": "typename Vec::mask_type",
    }[kind]


def _param_type(kind: str) -> str:
    if kind == "v":
        return "typename tsl::reg_param<Vec>::type"
    if kind == "m":
        return "typename Vec::mask_type"
    return "typename Vec::base_type"
