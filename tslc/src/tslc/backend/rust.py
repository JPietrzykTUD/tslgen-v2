"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from tslc.lower.lowerer import LoweredSpecialization

# Keyed by ISA name (the emitted tag); `_vl` variants are internal and never emitted.
_EXT_TAG = {"scalar": "Scalar", "sse": "Sse", "avx2": "Avx2", "avx512": "Avx512"}


class RustBackend:
    backend_id = "rust"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        trait = self._trait(primitive_name, shape)
        impls = [self._impl(spec) for spec in specializations]
        wrapper = self._wrapper(primitive_name, shape)
        return "\n\n".join([trait, *impls, wrapper])

    def _trait(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "Self")
        return (
            f"pub trait {_trait_name(primitive_name)}: SimdVector {{\n"
            f"    fn apply({params}) -> {_kind_type(shape.result_kind, 'Self')};\n"
            f"}}"
        )

    def _impl(self, spec: LoweredSpecialization) -> str:
        key = f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"
        params = _params(spec, "Self")
        return (
            f"impl {_trait_name(spec.primitive_name)} for {key} {{\n"
            f"    fn apply({params}) -> {_kind_type(spec.result_kind, 'Self')} {{\n"
            f"        {spec.body_text}\n"
            f"    }}\n"
            f"}}"
        )

    def _wrapper(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "S")
        names = ", ".join(shape.param_names)
        return (
            f"pub fn {primitive_name}<S: {_trait_name(primitive_name)}>({params}) "
            f"-> {_kind_type(shape.result_kind, 'S')} {{\n"
            f"    S::apply({names})\n"
            f"}}"
        )


def _trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def _ext_tag(extension_name: str) -> str:
    return _EXT_TAG.get(extension_name, extension_name[:1].upper() + extension_name[1:])


def _kind_type(kind: str, owner: str) -> str:
    return f"{owner}::RegisterType" if kind == "v" else f"{owner}::BaseType"


def _params(shape: LoweredSpecialization, owner: str) -> str:
    return ", ".join(
        f"{name}: {_kind_type(kind, owner)}"
        for name, kind in zip(shape.param_names, shape.param_kinds)
    )
