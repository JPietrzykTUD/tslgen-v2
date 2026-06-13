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
        # In the arg-trait `Self` is the *argument* type, not the vector — a vector-typed
        # result (e.g. shift's `v` -> register) must project through the vector param `S`.
        ret = _kind_type(shape.result_kind, "S")
        axis_decl = "".join(f", const {_axis_name(k)}: bool" for k, _ in shape.axis)
        # `generic_params` (e.g. `PreserveSign`) are free const generics on the arg-trait too.
        gp_decl = "".join(f", const {name}: {typ}" for name, typ, _ in shape.generic_params)
        gp_names = [name for name, _, _ in shape.generic_params]
        fixed_trait = "".join(f", {n}: {_kind_type(k, 'S')}" for n, k in fixed)
        trait = (
            f"pub trait {arg_trait}<S: SimdVector{axis_decl}{gp_decl}> {{\n"
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
            impl_generics = (["const LANES: usize"] if spec.extension_name == "generic" else []) + [
                f"const {name}: {typ}" for name, typ, _ in spec.generic_params
            ]
            if spec.extension_name == "generic":
                vec = f"Simd<{spec.base_type_spelling}, Generic<LANES>>"
            else:
                vec = f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"
            impl_prefix = f"impl<{', '.join(impl_generics)}>" if impl_generics else "impl"
            self_ty = _rust_concrete(spec, spec.param_kinds[vi])
            trait_args = (
                "<"
                + vec
                + "".join(f", {value}" for _, value in spec.axis)
                + "".join(f", {name}" for name in gp_names)
                + ">"
            )
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
        gp_wrap = "".join(f"const {name}: {typ}, " for name, typ, _ in shape.generic_params)
        gp_args = "".join(f", {name}" for name in gp_names)
        wrap_params = ", ".join(
            (f"{name}: V" if i == vi else f"{name}: {_kind_type(kind, 'S')}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        fixed_names = ", ".join(n for n, _ in fixed)
        wrapper = (
            f"pub fn {primitive_name}<S: SimdVector, {axis_wrap}{gp_wrap}"
            f"V: {arg_trait}<S{axis_args}{gp_args}>>({wrap_params}) -> {_kind_type(shape.result_kind, 'S')} {{\n"
            f"    {shape.param_names[vi]}.apply({fixed_names})\n"
            f"}}"
        )
        return "\n\n".join([trait, *impls, wrapper])

    def _trait(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "Self", binding_mut=False)
        # Boolean-wildcard axes and an `sImm` immediate become const-generics on the trait,
        # so the `[aligned=*]` variants are distinct impls (`StoreImpl<false>`/`StoreImpl<true>`)
        # and the immediate is a free param (`MulImmImpl<const factor: u32>`).
        decls = _generic_decls(shape)
        generics = f"<{', '.join(decls)}>" if decls else ""
        return (
            f"pub trait {_trait_name(primitive_name)}{generics}: SimdVector {{\n"
            f"    fn apply({params}) -> {_kind_type(shape.result_kind, 'Self')};\n"
            f"}}"
        )

    def _impl(self, spec: LoweredSpecialization) -> str:
        # The `generic` vector is sized: the impl is parameterized by `LANES` (a const generic
        # on the `Generic<LANES>` tag); an `sImm` immediate is a further free const generic.
        impl_parts: list[str] = []
        if spec.extension_name == "generic":
            impl_parts.append("const LANES: usize")
            key = f"Simd<{spec.base_type_spelling}, Generic<LANES>>"
        else:
            key = f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"
        if spec.immediate is not None:
            impl_parts.append(f"const {spec.immediate[0]}: {spec.immediate[1]}")
        impl_parts += [f"const {name}: {typ}" for name, typ, _ in spec.generic_params]
        impl_generics = f"<{', '.join(impl_parts)}>" if impl_parts else ""
        params = _params(spec, "Self")
        targs = _trait_args_by_value(spec)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        return (
            f"impl{impl_generics} {_trait_name(spec.primitive_name)}{trait_args} for {key} {{\n"
            f"    fn apply({params}) -> {_kind_type(spec.result_kind, 'Self')} {{\n"
            f"        {spec.body_text}\n"
            f"    }}\n"
            f"}}"
        )

    def _wrapper(self, primitive_name: str, shape: LoweredSpecialization) -> str:
        params = _params(shape, "S")
        names = _runtime_names(shape)
        # `S` comes first, then the const-generic axis/immediate params — the same turbofish
        # order as the overloaded wrapper (`S, ALIGNED, V`), so a call site can spell
        # `name::<Self, …>` uniformly. The trait bound carries them (`S: MulImmImpl<factor>`);
        # Rust allows referencing a const-generic in the bound before it is declared.
        targs = _trait_args_by_name(shape)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        decls = "".join(f", {d}" for d in _generic_decls(shape))
        return (
            f"pub fn {primitive_name}<S: {_trait_name(primitive_name)}{trait_args}{decls}>"
            f"({params}) -> {_kind_type(shape.result_kind, 'S')} {{\n"
            f"    S::apply({names})\n"
            f"}}"
        )


def _trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def _axis_name(key: str) -> str:
    """An axis attribute key as a Rust const-generic name (`aligned` -> `ALIGNED`)."""

    return key.upper()


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
    if kind == "usize":  # a count type; not reached by current overloads
        return "usize"
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
    if kind == "usize":  # a fixed count type, not a vector projection
        return "usize"
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
        if kind != "sImm"  # the immediate is a const generic, not a runtime arg
    )


def _runtime_names(shape: LoweredSpecialization) -> str:
    """The call-through argument names, excluding the `sImm` immediate (a const generic)."""

    return ", ".join(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != "sImm"
    )


def _generic_decls(shape: LoweredSpecialization) -> list[str]:
    """Const-generic parameter declarations for a trait/wrapper: the boolean axes plus an
    `sImm` immediate, e.g. ``["const ALIGNED: bool", "const factor: u32"]``."""

    decls = [f"const {_axis_name(k)}: bool" for k, _ in shape.axis]
    if shape.immediate is not None:
        decls.append(f"const {shape.immediate[0]}: {shape.immediate[1]}")
    # `generic_params` (e.g. `PreserveSign`) — const generics with no default (Rust const-generic
    # defaults are unstable, so callers pass them).
    decls += [f"const {name}: {typ}" for name, typ, _ in shape.generic_params]
    return decls


def _trait_args_by_name(shape: LoweredSpecialization) -> list[str]:
    """Trait generic ARGS spelled by name (wrapper side): axis names + immediate + generic_params."""

    args = [_axis_name(k) for k, _ in shape.axis]
    if shape.immediate is not None:
        args.append(shape.immediate[0])
    args += [name for name, _, _ in shape.generic_params]
    return args


def _trait_args_by_value(spec: LoweredSpecialization) -> list[str]:
    """Trait generic ARGS for a concrete impl: axis literal values + immediate + generic_params
    (the immediate and generic_params stay free const generics on the impl)."""

    args = [value for _, value in spec.axis]
    if spec.immediate is not None:
        args.append(spec.immediate[0])
    args += [name for name, _, _ in spec.generic_params]
    return args
