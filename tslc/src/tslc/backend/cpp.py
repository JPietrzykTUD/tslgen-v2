"""C++ backend: render a primitive as primary template + simd<> specializations + wrapper."""

from __future__ import annotations

from tslc.lower.lowerer import LoweredSpecialization


class CppBackend:
    backend_id = "cpp"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        # Declarations (impl primary template + wrapper) first, then the
        # specialization bodies — see render_declarations/render_definitions.
        return (
            self.render_declarations(primitive_name, specializations)
            + "\n\n"
            + self.render_definitions(primitive_name, specializations)
        )

    def render_declarations(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """The impl primary template + the wrapper function template. Emitted for
        *every* primitive before any specialization body, so a body may call any
        other primitive's wrapper (``::tsl::set1<Vec>(...)``) regardless of order."""

        shape = specializations[0]  # all share the same signature shape
        return (
            f"template <class Vec>\nstruct {primitive_name}_impl;"
            + "\n\n"
            + self._wrapper(primitive_name, shape)
        )

    def render_definitions(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """The `simd<>` specializations (with their inline ``apply`` bodies)."""

        return "\n\n".join(self._specialization(spec) for spec in specializations)

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
