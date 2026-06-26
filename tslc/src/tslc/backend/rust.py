"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.translation import X86_REGISTER_BITS
from tslc.catalog.signatures import is_free_function_signature
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.render.model import RenderContext
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

# Keyed by ISA name (the emitted tag); `_vl` variants are internal and never emitted.
_EXT_TAG = {"scalar": "Scalar", "sse": "Sse", "avx2": "Avx2", "avx512": "Avx512"}


class RustBackend:
    backend_id = "rust"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        if is_free_function_signature(shape.result_kind, shape.param_kinds):
            # A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module,
            # not a `SimdVector`-bound trait/impl/wrapper.
            return _free_function(shape)
        # Rust has no fn overloading: a primitive with several signatures (e.g. store's
        # `(ptr,v)`/`(ptr,s)`) dispatches on the varying argument's type via a trait
        # implemented for that type. Single-signature primitives keep the simple trait.
        if varying_positions(specializations):
            return self._render_overloaded(primitive_name, specializations)
        shape = specializations[0]
        caller_unsafe = _any_caller_unsafe(specializations)
        trait = self._trait(primitive_name, shape, caller_unsafe=caller_unsafe)
        impls = [
            self._impl(spec, caller_unsafe=caller_unsafe) for spec in specializations
        ]
        wrapper = self._wrapper(primitive_name, shape, caller_unsafe=caller_unsafe)
        return "\n\n".join([trait, *impls, wrapper])

    def _render_overloaded(
        self, primitive_name: str, specs: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specs[0]
        caller_unsafe = _any_caller_unsafe(specs)
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
        fixed_trait = "".join(f", {n}: {_param_kind_type(k, 'S')}" for n, k in fixed)
        trait = (
            f"pub trait {arg_trait}<S: SimdVector{axis_decl}{gp_decl}> {{\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_trait}) -> {ret};\n"
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
            # A sized vector's overloaded impls are parameterized by its lane parameter — UNLESS
            # the slot is monomorphized at a concrete lane count (a numeric `lane_parameter` like
            # "16"), in which case the impl is over a concrete `Generic<16>` with no lane generic.
            lane_parameter = spec.lane_parameter
            impl_generics = (
                [f"const {lane_parameter}: usize"]
                if spec.uses_sized_vector and not lane_parameter.isdigit()
                else []
            ) + [
                f"const {name}: {typ}" for name, typ, _ in spec.generic_params
            ]
            vec = _vector_type(spec)
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
                f", {n}: {_rust_concrete_param(spec, k)}" for n, k in fixed
            )
            ret_impl = _rust_concrete_result(spec)
            bind = f"let {spec.param_names[vi]} = self;\n        "
            body = spec.body.render(
                RenderContext(
                    backend_id=self.backend_id,
                    current_vector=vec,
                    current_register=rust_register_type(
                        spec.extension_name,
                        spec.base_type_spelling,
                        uses_sized_vector=spec.uses_sized_vector,
                        lane_parameter=lane_parameter,
                    ),
                    current_base=spec.base_type_spelling,
                    current_mask=f"<{vec} as SimdVector>::MaskType",
                    current_imask=f"<{vec} as SimdVector>::ImaskType",
                )
            )
            impls.append(
                f"{impl_prefix} {arg_trait}{trait_args} for {self_ty} {{\n"
                f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"        {bind}{body}\n"
                f"    }}\n"
                f"}}"
            )

        axis_wrap = "".join(f"const {_axis_name(k)}: bool, " for k, _ in shape.axis)
        axis_args = "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        gp_wrap = "".join(f"const {name}: {typ}, " for name, typ, _ in shape.generic_params)
        gp_args = "".join(f", {name}" for name in gp_names)
        wrap_params = ", ".join(
            (f"{name}: V" if i == vi else f"{name}: {_param_kind_type(kind, 'S')}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        fixed_names = ", ".join(n for n, _ in fixed)
        call = f"{shape.param_names[vi]}.apply({fixed_names})"
        call = _unsafe_call(call, caller_unsafe)
        unsafe_prefix = _unsafe_prefix(caller_unsafe)
        ret_type = _kind_type(shape.result_kind, "S")
        wrapper = (
            f"pub {unsafe_prefix}fn {primitive_name}"
            f"<S: SimdVector, {axis_wrap}{gp_wrap}"
            f"V: {arg_trait}<S{axis_args}{gp_args}>>"
            f"({wrap_params}) -> {ret_type} {{\n"
            f"    {call}\n"
            f"}}"
        )
        return "\n\n".join([trait, *impls, wrapper])

    def _trait(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        # Boolean-wildcard axes and an `sImm` immediate become const-generics on the trait,
        # so the `[aligned=*]` variants are distinct impls (`StoreImpl<false>`/`StoreImpl<true>`)
        # and the immediate is a free param (`MulImmImpl<const factor: u32>`).
        decls = _generic_decls(shape)
        ret = _kind_type(shape.result_kind, "Self")
        vt_type: str | None = None
        # A representation-change primitive takes the target vector as a first generic `ToVec`
        # and returns (and may take, via a `vt` param) its register type.
        if shape.target is not None:
            decls = ["ToVec: SimdVector", *decls]
            ret = "ToVec::RegisterType"
            vt_type = "ToVec::RegisterType"
        # Free SIMD type params (gather's `IndicesType`) — a `vidx` param projects through one.
        decls = _type_param_decls(shape) + decls
        vidx_type = f"{shape.type_params[0][0]}::RegisterType" if shape.type_params else None
        params = _params(shape, "Self", vt_type=vt_type, vidx_type=vidx_type)
        generics = f"<{', '.join(decls)}>" if decls else ""
        trait_header = (
            f"pub trait {_trait_name(primitive_name)}{generics}: "
            f"SimdVector{_index_where(shape)}"
        )
        return (
            f"{trait_header} {{\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret};\n"
            f"}}"
        )

    def _impl(self, spec: LoweredSpecialization, *, caller_unsafe: bool) -> str:
        # A sized vector's impl is parameterized by its lane const generic; an `sImm` immediate
        # is a further free const generic. A monomorphized slot (numeric `lane_parameter`) is over
        # a concrete `Generic<N>` instead, so it declares no lane generic.
        impl_parts: list[str] = []
        if spec.uses_sized_vector and not spec.lane_parameter.isdigit():
            lane_parameter = spec.lane_parameter
            impl_parts.append(f"const {lane_parameter}: usize")
        key = _vector_type(spec)
        if spec.immediate is not None:
            impl_parts.append(f"const {spec.immediate[0]}: {spec.immediate[1]}")
        impl_parts += [f"const {name}: {typ}" for name, typ, _ in spec.generic_params]
        # Free SIMD type params stay generic in the impl (a caller binds them); they precede the
        # const generics (Rust requires types before consts).
        impl_parts = _type_param_decls(spec) + impl_parts
        impl_generics = f"<{', '.join(impl_parts)}>" if impl_parts else ""
        targs = _trait_args_by_value(spec)
        ret = _kind_type(spec.result_kind, "Self")
        vt_type: str | None = None
        # The target vector is concrete in the impl's trait args; the result (and any `vt`
        # param) is its concrete register.
        if spec.target is not None:
            targs = [spec.target.vector_spelling, *targs]
            ret = spec.target.register_spelling
            vt_type = spec.target.register_spelling
        targs = [*_type_param_names(spec), *targs]
        vidx_type = f"{spec.type_params[0][0]}::RegisterType" if spec.type_params else None
        params = _params(spec, "Self", vt_type=vt_type, vidx_type=vidx_type)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        # On a real x86 ISA, pin the index register to that ISA's integer register so a native
        # intrinsic (which takes a concrete `__m256i`) type-checks; scalar/generic stay opaque.
        impl_register = (
            rust_register_type(spec.extension_name, "i32")
            if spec.extension_name in X86_REGISTER_BITS
            else None
        )
        return (
            f"impl{impl_generics} {_trait_name(spec.primitive_name)}{trait_args} for {key}"
            f"{_index_where(spec, impl_register=impl_register)} {{\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret} {{\n"
            f"        {spec.body_text}\n"
            f"    }}\n"
            f"}}"
        )

    def _wrapper(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        names = _runtime_names(shape)
        # `S` comes first, then the const-generic axis/immediate params — the same turbofish
        # order as the overloaded wrapper (`S, ALIGNED, V`), so a call site can spell
        # `name::<Self, …>` uniformly. The trait bound carries them (`S: MulImmImpl<factor>`);
        # Rust allows referencing a const-generic in the bound before it is declared.
        targs = _trait_args_by_name(shape)
        decl_list = _generic_decls(shape)
        ret = _kind_type(shape.result_kind, "S")
        call = f"S::apply({names})"
        vt_type: str | None = None
        # A representation-change primitive takes the target vector `T` as a generic, bounds `S`
        # on `…Impl<T, …>`, and returns (and may take, via a `vt` param) `T`'s register; the
        # call is qualified to pin the target.
        if shape.target is not None:
            targs = ["T", *targs]
            decl_list = ["T: SimdVector", *decl_list]
            ret = "T::RegisterType"
            vt_type = "T::RegisterType"
            call = f"<S as {_trait_name(primitive_name)}<{', '.join(targs)}>>::apply({names})"
        # Free SIMD type params: declare them (bounded) and pass them as trait args. The call is
        # qualified — `IndicesType::RegisterType` is non-injective, so it can't be inferred from
        # the `vidx` argument; pinning `IndicesType` in the trait path resolves `apply`.
        if shape.type_params:
            targs = [*_type_param_names(shape), *targs]
            decl_list = _type_param_decls(shape) + decl_list
            vidx_type = f"{shape.type_params[0][0]}::RegisterType"
            call = f"<S as {_trait_name(primitive_name)}<{', '.join(targs)}>>::apply({names})"
        else:
            vidx_type = None
        params = _params(shape, "S", vt_type=vt_type, vidx_type=vidx_type)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        decls = "".join(f", {d}" for d in decl_list)
        call = _unsafe_call(call, caller_unsafe)
        return (
            f"pub {_unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
            f"<S: {_trait_name(primitive_name)}{trait_args}{decls}>"
            f"({params}) -> {ret}{_index_where(shape)} {{\n"
            f"    {call}\n"
            f"}}"
        )


def _free_function(spec: LoweredSpecialization) -> str:
    """A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module, with
    concrete pointer/size types (no `SimdVector` projection). The body's `unsafe` framing is
    already applied by the lowered body (raw pointer / allocation access)."""

    params = ", ".join(
        f"{name}: {_free_kind_type(kind, spec.base_type_spelling)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    ret_clause = (
        ""
        if spec.result_kind == "void"
        else f" -> {_free_kind_type(spec.result_kind, spec.base_type_spelling)}"
    )
    unsafe_prefix = _unsafe_prefix(spec.safety.caller_unsafe)
    function_name = rust_raw_identifier(spec.primitive_name)
    return (
        f"pub {unsafe_prefix}fn {function_name}({params}){ret_clause} {{\n"
        f"    {spec.body_text}\n"
        f"}}"
    )


def _any_caller_unsafe(specs: tuple[LoweredSpecialization, ...]) -> bool:
    return any(spec.safety.caller_unsafe for spec in specs)


def _unsafe_prefix(enabled: bool) -> str:
    return "unsafe " if enabled else ""


def _unsafe_call(call: str, enabled: bool) -> str:
    return f"unsafe {{ {call} }}" if enabled else call


def _free_kind_type(kind: str, base_spelling: str) -> str:
    """A free function's kind -> concrete Rust type (no `Self` projection). Pointer spellings
    carry their own mutability; `usize` is a size; `void` is unit."""

    if kind == "void":
        return "()"
    if kind == "usize":
        return "usize"
    if DEFAULT_SUPPORT_POLICY.is_const_pointer_kind(kind):
        if base_spelling.startswith("*mut "):
            return "*const " + base_spelling[len("*mut ") :]
        return f"*const {base_spelling}"
    return base_spelling


def _trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def _type_param_decls(shape: LoweredSpecialization) -> list[str]:
    """`NAME: SimdVector + <Bound>Impl…` for each free SIMD type param (gather's `IndicesType`).
    The bound primitives are the ones the body calls on the param (recorded by the lowerer), so
    the param satisfies them — `to_array[IndicesType]` adds `To_arrayImpl`. C++ needs no such
    bound (templates are duck-typed); only Rust does. Type params precede const generics (Rust
    requires types before consts) and so are prepended to the generic list.

    The integer-index requirement of a `vidx`-backing param is carried by a where-clause
    (`_index_where`), not a bound here — a trait's where-clause is not an implied bound at use
    sites, so the constraint must be restated where the body needs it."""

    decls: list[str] = []
    for name, bounds in shape.type_params:
        traits = ["SimdVector", *(_trait_name(b) for b in bounds)]
        decls.append(f"{name}: {' + '.join(traits)}")
    return decls


def _index_where(shape: LoweredSpecialization, *, impl_register: str | None = None) -> str:
    """The where-clause(s) for a primitive with a `vidx` param. Always `IndicesType::BaseType:
    IndexBase` — the index lanes must convert to byte offsets (`idx_offset`). On a *real-ISA impl*
    (``impl_register`` set) it ALSO pins `IndicesType: SimdVector<RegisterType = …>` to that ISA's
    integer register: a native gather/scatter intrinsic takes a concrete register (`__m256i`), but
    `IndicesType::RegisterType` is otherwise an opaque associated type. A gather index is by kind
    that ISA's integer register whatever the data type — a kind-level fact, not primitive
    knowledge. Emitted on the trait/impl/wrapper so each constraint holds where the body needs it;
    empty for non-`vidx` primitives."""

    if (
        DEFAULT_SUPPORT_POLICY.index_vector_kind not in shape.param_kinds
        or not shape.type_params
    ):
        return ""
    index = shape.type_params[0][0]
    clauses = [f"{index}::BaseType: IndexBase"]
    if impl_register is not None:
        clauses.insert(0, f"{index}: SimdVector<RegisterType = {impl_register}>")
    return " where " + ", ".join(clauses)


def _type_param_names(shape: LoweredSpecialization) -> list[str]:
    return [name for name, _ in shape.type_params]


def _axis_name(key: str) -> str:
    """An axis attribute key as a Rust const-generic name (`aligned` -> `ALIGNED`)."""

    return key.upper()


def _ext_tag(extension_name: str) -> str:
    return _EXT_TAG.get(extension_name, extension_name[:1].upper() + extension_name[1:])


def rust_register_type(
    extension_name: str,
    base: str,
    *,
    uses_sized_vector: bool = False,
    lane_parameter: str | None = None,
) -> str:
    """Concrete register type spelling (scalar's register == its base type)."""

    # A sized vector's register is the lane array; the lane parameter is in scope wherever this is
    # used for a sized-vector impl.
    if uses_sized_vector:
        return f"array_type<{base}, {lane_parameter}>"
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
        return rust_register_type(
            spec.extension_name,
            base,
            uses_sized_vector=spec.uses_sized_vector,
            lane_parameter=spec.lane_parameter,
        )
    if DEFAULT_SUPPORT_POLICY.is_const_pointer_kind(kind):
        return f"*const {base}"
    if DEFAULT_SUPPORT_POLICY.is_mutable_pointer_kind(kind):
        return f"*mut {base}"
    if DEFAULT_SUPPORT_POLICY.is_borrowed_parameter_kind(kind):
        return _rust_concrete_array(spec)
    if kind == "void":
        return "()"
    if kind == "m":  # not reached by current overloads (store/shift vary in v/s)
        return rust_register_type(
            spec.extension_name,
            base,
            uses_sized_vector=spec.uses_sized_vector,
            lane_parameter=spec.lane_parameter,
        )
    if kind == "im":  # not reached by current overloads (to_integral is single-param)
        return rust_register_type(
            spec.extension_name,
            base,
            uses_sized_vector=spec.uses_sized_vector,
            lane_parameter=spec.lane_parameter,
        )
    if kind == "usize":  # a count type; not reached by current overloads
        return "usize"
    return base  # s


def _rust_concrete_param(spec: LoweredSpecialization, kind: str) -> str:
    if DEFAULT_SUPPORT_POLICY.is_borrowed_parameter_kind(kind):
        return f"&{_rust_concrete_array(spec)}"
    return _rust_concrete(spec, kind)


def _rust_concrete_result(spec: LoweredSpecialization) -> str:
    return _rust_concrete(spec, spec.result_kind)


def _rust_concrete_array(spec: LoweredSpecialization) -> str:
    lane_parameter = spec.lane_parameter
    return f"array_type<{spec.base_type_spelling}, {lane_parameter}>"


def _vector_type(spec: LoweredSpecialization) -> str:
    if spec.uses_sized_vector:
        lane_parameter = spec.lane_parameter
        return f"Simd<{spec.base_type_spelling}, Generic<{lane_parameter}>>"
    return f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"


def _kind_type(kind: str, owner: str) -> str:
    if DEFAULT_SUPPORT_POLICY.is_const_pointer_kind(kind):
        return f"*const {owner}::BaseType"
    if DEFAULT_SUPPORT_POLICY.is_mutable_pointer_kind(kind):
        return f"*mut {owner}::BaseType"
    if kind == "void":
        return "()"
    if kind in ("s[]", DEFAULT_SUPPORT_POLICY.lane_list_kind):
        return f"{owner}::Array"
    if kind == "usize":  # a fixed count type, not a vector projection
        return "usize"
    if kind == "o":  # a text-buffer stream; `out` is the only reference param, so the
        return "&mut String"  # returned `&mut String` lifetime elides to it
    suffix = {
        "v": "RegisterType",
        "s": "BaseType",
        "m": "MaskType",
        "im": "ImaskType",
    }[kind]
    return f"{owner}::{suffix}"


def _param_kind_type(kind: str, owner: str) -> str:
    if DEFAULT_SUPPORT_POLICY.is_borrowed_parameter_kind(kind):
        return f"&{owner}::Array"
    return _kind_type(kind, owner)


def _params(
    shape: LoweredSpecialization,
    owner: str,
    *,
    vt_type: str | None = None,
    vidx_type: str | None = None,
) -> str:
    # A body that needs a mutable `s[]` borrow should introduce a mutable local explicitly
    # in source (`var<infer>(local, data)`), keeping read-only array parameters const in
    # generated Rust. A `vt` (target-axis vector) param uses `vt_type` —
    # the per-context target register spelling (trait `ToVec::RegisterType` / impl concrete /
    # wrapper `T::RegisterType`); a `vidx` (index vector) param uses `vidx_type`
    # (`IndicesType::RegisterType` — the generic name is the same in every context).
    parts: list[str] = []
    for name, kind in zip(shape.param_names, shape.param_kinds):
        if kind == DEFAULT_SUPPORT_POLICY.immediate_kind:
            continue
        if kind == "vt":
            typ = vt_type
        elif kind == DEFAULT_SUPPORT_POLICY.index_vector_kind:
            typ = vidx_type
        else:
            typ = _param_kind_type(kind, owner)
        parts.append(f"{name}: {typ}")
    return ", ".join(parts)


def _runtime_names(shape: LoweredSpecialization) -> str:
    """The call-through argument names, excluding the `sImm` immediate (a const generic)."""

    return ", ".join(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
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
