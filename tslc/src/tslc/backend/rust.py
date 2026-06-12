"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from tslc.backend.translation import X86_REGISTER_BITS
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)

# Keyed by ISA name (the emitted tag); `_vl` variants are internal and never emitted.
_EXT_TAG = {"scalar": "Scalar", "sse": "Sse", "avx2": "Avx2", "avx512": "Avx512"}


class RustBackend:
    backend_id = "rust"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        # Rust has no fn overloading: a primitive with several signatures (e.g. store's
        # `(ptr,v)`/`(ptr,s)`) dispatches on the varying argument's type via a trait
        # implemented for that type. Single-signature primitives keep the simple trait.
        if varying_positions(specializations):
            return self._render_overloaded(primitive_name, specializations)
        shape = specializations[0]
        trait = self._trait(primitive_name, shape)
        impls = [self._impl(spec) for spec in specializations]
        wrapper = self._wrapper(primitive_name, shape)
        return "\n\n".join([trait, *impls, wrapper])

    def _render_overloaded(
        self, primitive_name: str, specs: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specs[0]
        vi = varying_positions(specs)[0]  # one varying position in scope
        arg_trait = f"{_trait_name(primitive_name)}Arg"
        fixed = [
            (name, kind)
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if i != vi
        ]
        ret = _kind_type(shape.result_kind, "Self")
        axis_decl = "".join(f", const {_axis_name(k)}: bool" for k, _ in shape.axis)
        fixed_trait = "".join(f", {n}: {_kind_type(k, 'S')}" for n, k in fixed)
        trait = (
            f"pub trait {arg_trait}<S: SimdVector{axis_decl}> {{\n"
            f"    fn apply(self{fixed_trait}) -> {ret};\n"
            f"}}"
        )

        # Dedup is per (Vec, axis) group — one impl per distinct argument type *within*
        # a group (scalar's register==base collapses its two overloads to one).
        impls: list[str] = []
        seen: set[tuple[str, str, tuple, tuple[str, ...]]] = set()
        for spec in specs:
            signature = (
                spec.base_type_spelling,
                spec.extension_name,
                spec.axis,
                effective_param_types(spec),
            )
            if signature in seen:
                continue
            seen.add(signature)
            # The generic vector is sized: its overloaded impls are parameterized by `LANES`.
            if spec.extension_name == "generic":
                vec = f"Simd<{spec.base_type_spelling}, Generic<LANES>>"
                impl_prefix = "impl<const LANES: usize>"
            else:
                vec = f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"
                impl_prefix = "impl"
            self_ty = _rust_concrete(spec, spec.param_kinds[vi])
            trait_args = "<" + vec + "".join(f", {value}" for _, value in spec.axis) + ">"
            fixed_impl = "".join(
                f", {n}: {_rust_concrete(spec, k)}" for n, k in fixed
            )
            ret_impl = _rust_concrete_result(spec)
            # In an arg-trait impl, `Self` is the argument type, not the Simd vector, so
            # the body's `Self::RegisterType`/`Self::BaseType` (Simd associated types) are
            # concretized; the varying parameter is bound from `self`.
            bind = f"let {spec.param_names[vi]} = self;\n        "
            body = _concretize_simd_assoc(spec.body_text, spec, vec)
            impls.append(
                f"{impl_prefix} {arg_trait}{trait_args} for {self_ty} {{\n"
                f"    fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"        {bind}{body}\n"
                f"    }}\n"
                f"}}"
            )

        axis_wrap = "".join(f"const {_axis_name(k)}: bool, " for k, _ in shape.axis)
        axis_args = "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        wrap_params = ", ".join(
            (f"{name}: V" if i == vi else f"{name}: {_kind_type(kind, 'S')}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        fixed_names = ", ".join(n for n, _ in fixed)
        wrapper = (
            f"pub fn {primitive_name}<S: SimdVector, {axis_wrap}"
            f"V: {arg_trait}<S{axis_args}>>({wrap_params}) -> {_kind_type(shape.result_kind, 'S')} {{\n"
            f"    {shape.param_names[vi]}.apply({fixed_names})\n"
            f"}}"
        )
        return "\n\n".join([trait, *impls, wrapper])

    def _trait(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "Self", binding_mut=False)
        # A boolean-wildcard attribute axis becomes a const-generic on the trait, so the
        # `[aligned=*]` variants are distinct impls (`StoreImpl<false>` / `StoreImpl<true>`).
        generics = _axis_generics(shape.axis)
        return (
            f"pub trait {_trait_name(primitive_name)}{generics}: SimdVector {{\n"
            f"    fn apply({params}) -> {_kind_type(shape.result_kind, 'Self')};\n"
            f"}}"
        )

    def _impl(self, spec: LoweredSpecialization) -> str:
        # The `generic` vector is sized: the impl is parameterized by `LANES` (a const generic
        # on the `Generic<LANES>` tag), and the body's `LANES` refers to it.
        if spec.extension_name == "generic":
            impl_generics = "<const LANES: usize>"
            key = f"Simd<{spec.base_type_spelling}, Generic<LANES>>"
        else:
            impl_generics = ""
            key = f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"
        params = _params(spec, "Self")
        trait_args = "".join(f"<{value}>" for _, value in spec.axis)
        return (
            f"impl{impl_generics} {_trait_name(spec.primitive_name)}{trait_args} for {key} {{\n"
            f"    fn apply({params}) -> {_kind_type(spec.result_kind, 'Self')} {{\n"
            f"        {spec.body_text}\n"
            f"    }}\n"
            f"}}"
        )

    def _wrapper(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "S")
        names = ", ".join(shape.param_names)
        # `S` comes first, then const-generic axis params — the same turbofish order as the
        # overloaded wrapper (`S, ALIGNED, V`), so a call site can spell `name::<Self, …>`
        # uniformly. The trait bound carries the axis (`S: StoreImpl<ALIGNED>`); Rust allows
        # the const-generic to be referenced in the bound before it is declared.
        trait_args = "".join(f"<{_axis_name(k)}>" for k, _ in shape.axis)
        axis_decls = "".join(f", const {_axis_name(k)}: bool" for k, _ in shape.axis)
        return (
            f"pub fn {primitive_name}<S: {_trait_name(primitive_name)}{trait_args}{axis_decls}>"
            f"({params}) -> {_kind_type(shape.result_kind, 'S')} {{\n"
            f"    S::apply({names})\n"
            f"}}"
        )


def _trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def _axis_name(key: str) -> str:
    """An axis attribute key as a Rust const-generic name (`aligned` -> `ALIGNED`)."""

    return key.upper()


def _axis_generics(axis: tuple[tuple[str, str], ...]) -> str:
    """The trait's const-generic parameter list, e.g. ``<const ALIGNED: bool>``."""

    if not axis:
        return ""
    return "<" + ", ".join(f"const {_axis_name(k)}: bool" for k, _ in axis) + ">"


def _ext_tag(extension_name: str) -> str:
    return _EXT_TAG.get(extension_name, extension_name[:1].upper() + extension_name[1:])


def rust_register_type(extension_name: str, base: str) -> str:
    """Concrete register type spelling (scalar's register == its base type)."""

    # The generic vector's register is the lane array (the `array_type` wrapper, matching its
    # `Array`); `LANES` is in scope wherever this is used (a generic impl's const generic).
    if extension_name == "generic":
        return f"array_type<{base}, LANES>"
    width = X86_REGISTER_BITS.get(extension_name)
    if width is None:
        return base
    if base == "f32":
        return f"core::arch::x86_64::__m{width}"
    if base == "f64":
        return f"core::arch::x86_64::__m{width}d"
    return f"core::arch::x86_64::__m{width}i"


def _rust_concrete(spec: LoweredSpecialization, kind: str) -> str:
    """Concrete (non-associated) type for an overloaded impl's `for`/params: the impl is
    written for a concrete arg type, so associated-type projections won't do."""

    base = spec.base_type_spelling
    if kind == "v":
        return rust_register_type(spec.extension_name, base)
    if kind == "ptr":
        return f"*mut {base}"
    if kind == "void":
        return "()"
    if kind == "m":  # not reached by current overloads (store/shift vary in v/s)
        return rust_register_type(spec.extension_name, base)
    if kind == "im":  # not reached by current overloads (to_integral is single-param)
        return rust_register_type(spec.extension_name, base)
    return base  # s


def _rust_concrete_result(spec: LoweredSpecialization) -> str:
    return _rust_concrete(spec, spec.result_kind)


def _concretize_simd_assoc(body: str, spec: LoweredSpecialization, simd_vec: str) -> str:
    """Concretize references to the Simd vector inside an arg-trait impl, where `Self` is the
    *argument* type, not the vector: a `::<Self>` call turbofish (e.g. delegating
    `to_array::<Self>`) becomes `::<{simd_vec}>`, and the Simd associated types become their
    concrete spellings."""

    register = rust_register_type(spec.extension_name, spec.base_type_spelling)
    return (
        body.replace("::<Self>", f"::<{simd_vec}>")
        .replace("Self::RegisterType", register)
        .replace("Self::BaseType", spec.base_type_spelling)
    )


def _kind_type(kind: str, owner: str) -> str:
    if kind == "ptr":
        return f"*mut {owner}::BaseType"
    if kind == "void":
        return "()"
    if kind == "s[]":
        return f"{owner}::Array"
    suffix = {
        "v": "RegisterType",
        "s": "BaseType",
        "m": "MaskType",
        "im": "ImaskType",
    }[kind]
    return f"{owner}::{suffix}"


def _params(shape: LoweredSpecialization, owner: str, *, binding_mut: bool = True) -> str:
    # An array (`s[]`) parameter is bound `mut` so the body can take a pointer into it
    # (`data.data()` borrows `&mut`); `mut` on an owned binding is otherwise harmless.
    # A trait *declaration* has no body, where a binding pattern like `mut` is rejected,
    # so it passes ``binding_mut=False``.
    return ", ".join(
        f"{'mut ' if binding_mut and kind == 's[]' else ''}{name}: {_kind_type(kind, owner)}"
        for name, kind in zip(shape.param_names, shape.param_kinds)
    )
