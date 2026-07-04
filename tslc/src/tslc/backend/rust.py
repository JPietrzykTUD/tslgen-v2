"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.target_capability import rust_extension_tag
from tslc.documentation import (
    DocumentationBlock,
    documentation_block,
    parameter_summary,
    render_rust_doc,
    result_summary,
    safety_fact,
)
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.render.model import RenderContext
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_PRIMITIVE_TRAIT_PREFIX = "detail::primitives::"


class RustBackend:
    backend_id = "rust"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        internal = self.render_primitive_internal(primitive_name, specializations)
        public = self.render_primitive_public(primitive_name, specializations)
        if not internal:
            return public
        return "\n\n".join([_primitive_module(internal), public])

    def render_primitive_module(self, internal: str) -> str:
        return _primitive_module(internal) if internal.strip() else ""

    def render_primitive_internal(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return ""
        # Rust has no fn overloading: a primitive with several signatures (e.g. store's
        # `(ptr,v)`/`(ptr,s)`) dispatches on the varying argument's type via a trait
        # implemented for that type. Single-signature primitives keep the simple trait.
        if varying_positions(specializations):
            return self._render_overloaded_internal(primitive_name, specializations)
        caller_unsafe = _any_caller_unsafe(specializations)
        trait = self._trait(primitive_name, shape, caller_unsafe=caller_unsafe)
        impls = [
            self._impl(spec, caller_unsafe=caller_unsafe) for spec in specializations
        ]
        return "\n\n".join([trait, *impls])

    def render_primitive_public(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module,
            # not a `SimdVector`-bound trait/impl/wrapper.
            return _free_function(shape)
        caller_unsafe = _any_caller_unsafe(specializations)
        if varying_positions(specializations):
            return self._render_overloaded_wrapper(
                primitive_name, specializations, caller_unsafe=caller_unsafe
            )
        return self._wrapper(primitive_name, shape, caller_unsafe=caller_unsafe)

    def _render_overloaded_internal(
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
        doc = _rust_doc(
            shape, context="Rust overload dispatch trait", concrete=False
        )
        trait = (
            (f"{doc}\n" if doc else "")
            + f"pub trait {arg_trait}<S: StaticSimdVector{axis_decl}{gp_decl}> {{\n"
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
                    current_register=spec.register_spelling,
                    current_base=spec.base_type_spelling,
                    current_mask=f"<{vec} as SimdVector>::MaskType",
                    current_imask=f"<{vec} as SimdVector>::ImaskType",
                )
            )
            doc = _rust_doc(spec, context="Rust specialization")
            impls.append(
                (f"{doc}\n" if doc else "")
                + f"{impl_prefix} {arg_trait}{trait_args} for {self_ty} {{\n"
                f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"        {bind}{body}\n"
                f"    }}\n"
                f"}}"
            )

        return "\n\n".join([trait, *impls])

    def _render_overloaded_wrapper(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
        *,
        caller_unsafe: bool,
    ) -> str:
        shape = specs[0]
        vi = varying_positions(specs)[0]
        arg_trait = f"{_PRIMITIVE_TRAIT_PREFIX}{_trait_name(primitive_name)}Arg"
        fixed = [
            (name, kind)
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if i != vi
        ]
        axis_wrap = "".join(f"const {_axis_name(k)}: bool, " for k, _ in shape.axis)
        axis_args = "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        gp_wrap = "".join(f"const {name}: {typ}, " for name, typ, _ in shape.generic_params)
        gp_names = [name for name, _, _ in shape.generic_params]
        gp_args = "".join(f", {name}" for name in gp_names)
        wrap_params = ", ".join(
            (f"{name}: V" if i == vi else f"{name}: {_param_kind_type(kind, 'S')}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        fixed_names = [n for n, _ in fixed]
        call_args = ", ".join((shape.param_names[vi], *fixed_names))
        call = f"<V as {arg_trait}<S{axis_args}{gp_args}>>::apply({call_args})"
        call = _unsafe_call(call, caller_unsafe)
        unsafe_prefix = _unsafe_prefix(caller_unsafe)
        ret_type = _kind_type(shape.result_kind, "S")
        doc = _rust_doc(shape, context="Rust wrapper", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"pub {unsafe_prefix}fn {primitive_name}"
            f"<S: StaticSimdVector, {axis_wrap}{gp_wrap}"
            f"V: {arg_trait}<S{axis_args}{gp_args}>>"
            f"({wrap_params}) -> {ret_type} {{\n"
            f"    {call}\n"
            f"}}"
        )

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
            decls = ["ToVec: StaticSimdVector", *decls]
            ret = "ToVec::RegisterType"
            vt_type = "ToVec::RegisterType"
        # Free SIMD type params (gather's `IndicesType`) — a `vidx` param projects through one.
        decls = _type_param_decls(shape) + decls
        vidx_type = f"{shape.type_params[0].name}::RegisterType" if shape.type_params else None
        params = _params(shape, "Self", vt_type=vt_type, vidx_type=vidx_type)
        generics = f"<{', '.join(decls)}>" if decls else ""
        trait_header = (
            f"pub trait {_trait_name(primitive_name)}{generics}: "
            f"StaticSimdVector{_index_where(shape)}"
        )
        doc = _rust_doc(shape, context="Rust dispatch trait", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"{trait_header} {{\n"
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
        vidx_type = f"{spec.type_params[0].name}::RegisterType" if spec.type_params else None
        params = _params(spec, "Self", vt_type=vt_type, vidx_type=vidx_type)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        # Native index intrinsics take the concrete integer-register type for the selected ISA.
        # Lowering resolves it from source extension metadata; scalar/generic stay opaque.
        impl_register = spec.index_register_spelling
        body = spec.body.render(
            RenderContext(
                backend_id=self.backend_id,
                current_vector=key,
                current_register=spec.register_spelling,
                current_base=spec.base_type_spelling,
                current_mask=f"<{key} as SimdVector>::MaskType",
                current_imask=f"<{key} as SimdVector>::ImaskType",
            )
        )
        doc = _rust_doc(spec, context="Rust specialization")
        return (
            (f"{doc}\n" if doc else "")
            + f"impl{impl_generics} {_trait_name(spec.primitive_name)}{trait_args} for {key}"
            f"{_index_where(spec, impl_register=impl_register)} {{\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret} {{\n"
            f"        {body}\n"
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
        call = ""
        vt_type: str | None = None
        # A representation-change primitive takes the target vector `T` as a generic, bounds `S`
        # on `…Impl<T, …>`, and returns (and may take, via a `vt` param) `T`'s register; the
        # call is qualified to pin the target.
        if shape.target is not None:
            targs = ["T", *targs]
            decl_list = ["T: StaticSimdVector", *decl_list]
            ret = "T::RegisterType"
            vt_type = "T::RegisterType"
            call = (
                f"<S as {_PRIMITIVE_TRAIT_PREFIX}{_trait_name(primitive_name)}"
                f"<{', '.join(targs)}>>::apply({names})"
            )
        # Free SIMD type params: declare them (bounded) and pass them as trait args. The call is
        # qualified — `IndicesType::RegisterType` is non-injective, so it can't be inferred from
        # the `vidx` argument; pinning `IndicesType` in the trait path resolves `apply`.
        if shape.type_params:
            targs = [*_type_param_names(shape), *targs]
            decl_list = _type_param_decls(
                shape, trait_prefix=_PRIMITIVE_TRAIT_PREFIX
            ) + decl_list
            vidx_type = f"{shape.type_params[0].name}::RegisterType"
            call = (
                f"<S as {_PRIMITIVE_TRAIT_PREFIX}{_trait_name(primitive_name)}"
                f"<{', '.join(targs)}>>::apply({names})"
            )
        else:
            vidx_type = None
        params = _params(shape, "S", vt_type=vt_type, vidx_type=vidx_type)
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        decls = "".join(f", {d}" for d in decl_list)
        call = (
            f"<S as {_PRIMITIVE_TRAIT_PREFIX}{_trait_name(primitive_name)}"
            f"{trait_args}>::apply({names})"
        )
        call = _unsafe_call(call, caller_unsafe)
        doc = _rust_doc(shape, context="Rust wrapper", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"pub {_unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
            f"<S: {_PRIMITIVE_TRAIT_PREFIX}{_trait_name(primitive_name)}"
            f"{trait_args}{decls}>"
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
    doc = _rust_doc(spec, context="Rust free function")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix}fn {function_name}({params}){ret_clause} {{\n"
        f"    {spec.body_text}\n"
        f"}}"
    )


def _primitive_module(internal: str) -> str:
    return (
        "pub mod detail {\n"
        "    pub mod primitives {\n"
        "        use super::super::*;\n\n"
        f"{_indent(internal, 8)}\n"
        "    }\n"
        "}"
    )


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _rust_doc(
    spec: LoweredSpecialization, *, context: str, concrete: bool = True
) -> str:
    return render_rust_doc(_doc_block(spec, context=context, concrete=concrete))


def _doc_block(
    spec: LoweredSpecialization, *, context: str, concrete: bool
) -> DocumentationBlock:
    if not concrete:
        return documentation_block(
            spec.documentation,
            facts=(
                ("Type parameters", _rust_type_parameter_summary(spec)),
                ("Returns", _rust_result_summary(spec, concrete=False)),
                ("Parameters", _runtime_parameter_summary(spec)),
            ),
            facts_title="API",
        )
    facts = [
        ("Extension", spec.extension_name),
        ("Element type", spec.base_type_spelling),
        ("Register type", spec.register_spelling),
        ("Returns", _rust_result_summary(spec, concrete=True)),
        ("Parameters", _runtime_parameter_summary(spec)),
    ]
    if spec.target is not None:
        facts.extend(
            [
                ("Target vector", spec.target.vector_spelling),
                ("Target register", spec.target.register_spelling),
            ]
        )
    if spec.axis:
        facts.append(
            ("Attributes", ", ".join(f"{key}={value}" for key, value in spec.axis))
        )
    if spec.immediate is not None:
        facts.append(("Immediate", f"{spec.immediate[0]}: {spec.immediate[1]}"))
    if spec.required_features:
        facts.append(
            ("Required CPU features", ", ".join(sorted(spec.required_features)))
        )
    else:
        facts.append(("Required CPU features", "none"))
    facts.append(("Safety", safety_fact(spec.safety)))
    return documentation_block(
        spec.documentation,
        facts=tuple(facts),
        facts_title="Specialization",
    )


def _runtime_parameter_summary(spec: LoweredSpecialization) -> str:
    params = tuple(
        (name, kind)
        for name, kind in zip(spec.param_names, spec.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    return parameter_summary(
        tuple(name for name, _kind in params),
        tuple(kind for _name, kind in params),
    )


def _rust_type_parameter_summary(spec: LoweredSpecialization) -> str:
    params = ["S selects the SIMD vector type"]
    if spec.target is not None:
        params.append("T selects the target SIMD vector type")
    params.extend(
        f"{param.name} selects an additional SIMD vector type"
        for param in spec.type_params
    )
    params.extend(f"{_axis_name(key)} selects `{key}`" for key, _ in spec.axis)
    if spec.immediate is not None:
        params.append(f"{spec.immediate[0]} is a compile-time immediate")
    params.extend(
        f"{name} selects `{name}`"
        for name, _typ, _default in spec.generic_params
    )
    return "; ".join(params)


def _rust_result_summary(spec: LoweredSpecialization, *, concrete: bool) -> str:
    if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    ):
        return result_summary(
            spec.result_kind,
            _free_kind_type(spec.result_kind, spec.base_type_spelling),
        )
    if concrete:
        return result_summary(spec.result_kind, _rust_concrete_result(spec))
    if spec.target is not None:
        return result_summary(spec.result_kind, "T::RegisterType")
    return result_summary(spec.result_kind, _kind_type(spec.result_kind, "S"))


def _any_caller_unsafe(specs: tuple[LoweredSpecialization, ...]) -> bool:
    return any(spec.safety.caller_unsafe for spec in specs)


def _unsafe_prefix(enabled: bool) -> str:
    return "unsafe " if enabled else ""


def _unsafe_call(call: str, enabled: bool) -> str:
    return f"unsafe {{ {call} }}" if enabled else call


def _free_kind_type(kind: str, base_spelling: str) -> str:
    """A free function's kind -> concrete Rust type (no `Self` projection). Pointer spellings
    carry their own mutability; `usize` is a size; `void` is unit."""

    return DEFAULT_SUPPORT_POLICY.rust_free_type(kind, base_type=base_spelling)


def _trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def _type_param_decls(
    shape: LoweredSpecialization, *, trait_prefix: str = ""
) -> list[str]:
    """`NAME: StaticSimdVector + <Bound>Impl…` for each free SIMD type param (gather's `IndicesType`).
    The bound primitives are the ones the body calls on the param (recorded by the lowerer), so
    the param satisfies them — `to_array[IndicesType]` adds `To_arrayImpl`. C++ needs no such
    bound (templates are duck-typed); only Rust does. Type params precede const generics (Rust
    requires types before consts) and so are prepended to the generic list.

    The integer-index requirement of a `vidx`-backing param is carried by a where-clause
    (`_index_where`), not a bound here — a trait's where-clause is not an implied bound at use
    sites, so the constraint must be restated where the body needs it."""

    decls: list[str] = []
    for param in shape.type_params:
        traits = [
            "StaticSimdVector",
            *(f"{trait_prefix}{_trait_name(b)}" for b in param.bounds),
        ]
        decls.append(f"{param.name}: {' + '.join(traits)}")
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
    index = shape.type_params[0].name
    clauses = [f"{index}::BaseType: IndexBase"]
    if impl_register is not None:
        clauses.insert(0, f"{index}: SimdVector<RegisterType = {impl_register}>")
    return " where " + ", ".join(clauses)


def _type_param_names(shape: LoweredSpecialization) -> list[str]:
    return [param.name for param in shape.type_params]


def _axis_name(key: str) -> str:
    """An axis attribute key as a Rust const-generic name (`aligned` -> `ALIGNED`)."""

    return key.upper()


def _ext_tag(extension_name: str) -> str:
    return rust_extension_tag(extension_name)


def _rust_concrete(spec: LoweredSpecialization, kind: str) -> str:
    """Concrete (non-associated) type for an overloaded impl's `for`/params: the impl is
    written for a concrete arg type, so associated-type projections won't do."""

    return DEFAULT_SUPPORT_POLICY.rust_concrete_type(
        kind,
        base_type=spec.base_type_spelling,
        register_type=spec.register_spelling,
        array_type=_rust_concrete_array(spec),
    )


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
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        lane_parameter = spec.lane_parameter
        return f"Simd<{spec.base_type_spelling}, Generic<{lane_parameter}>>"
    return f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"


def _kind_type(kind: str, owner: str) -> str:
    return DEFAULT_SUPPORT_POLICY.rust_owner_type(kind, owner=owner)


def _param_kind_type(kind: str, owner: str) -> str:
    return DEFAULT_SUPPORT_POLICY.rust_param_type(kind, owner=owner)


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
