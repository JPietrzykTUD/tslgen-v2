"""C++ backend: render a primitive as primary template + simd<> specializations + wrapper."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.target_capability import x86_register_bits
from tslc.documentation import (
    DocumentationBlock,
    documentation_block,
    parameter_summary,
    render_cpp_doc,
    result_summary,
    safety_fact,
)
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


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

        shape = specializations[0]  # all share the same signature shape + axis keys
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive: a plain prototype (the definition follows in
            # render_definitions), so a free function can still call any wrapper.
            return _free_function(shape, define=False)
        # A representation-change primitive carries a SECOND vector type (the target): the
        # result is `ToVec::register_type` and `ToVec` is a free template param the caller binds.
        decl_params = "class Vec" + (
            ", class ToVec" if shape.target is not None else ""
        )
        # Free SIMD type params (gather's `IndicesType`) — a caller-bound vector type, like ToVec.
        decl_params += "".join(f", class {name}" for name, _ in shape.type_params)
        decl_params += "".join(f", bool {_axis_name(k)}" for k, _ in shape.axis)
        if shape.immediate is not None:  # an `sImm` non-type template parameter
            decl_params += f", {shape.immediate[1]} {shape.immediate[0]}"
        # `generic_params` (e.g. `PreserveSign`) are free template params too (defaults go on
        # the wrapper, not the primary template).
        decl_params += "".join(f", {typ} {name}" for name, typ, _ in shape.generic_params)
        return (
            f"template <{decl_params}>\nstruct {primitive_name}_impl;"
            + "\n\n"
            + self._wrapper(primitive_name, specializations)
        )

    def render_definitions(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """The `simd<>` specializations. Specs are grouped by `simd<>` + axis; an
        overloaded primitive (several signatures, e.g. store's `(ptr,v)`/`(ptr,s)`)
        emits one `apply` per signature in that group, resolved by C++ overloading."""

        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_function(shape, define=True)
        groups: dict[tuple, list[LoweredSpecialization]] = {}
        order: list[tuple] = []
        for spec in specializations:
            # A representation-change primitive keys on the target too: same-source different-
            # target specs are distinct specializations (`si8->ui8` vs `si8->si8`), not one group.
            key = (
                spec.base_type_spelling,
                spec.extension_name,
                spec.axis,
                spec.target.vector_spelling if spec.target else None,
            )
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(spec)
        return "\n\n".join(self._specialization(groups[key]) for key in order)

    def render_documentation_api_declaration(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render the public C++ API as a documentation-only declaration."""

        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_function(shape, define=False)
        return self._wrapper_declaration(primitive_name, specializations)

    def documentation_register_type(self, spec: LoweredSpecialization) -> str:
        return _cpp_register_doc(spec)

    def documentation_target_register_type(self, spec: LoweredSpecialization) -> str:
        return _cpp_target_register_doc(spec)

    def _specialization(self, group: list[LoweredSpecialization]) -> str:
        first = group[0]
        # A sized vector is parameterized by its lane parameter, so it emits as a partial
        # specialization rather than a full specialization.
        # Free template params of the (partial) specialization: the sized vector's lane parameter
        # and an `sImm` immediate (both unbound, so they appear in the head AND the key);
        # concrete axis values are bound literals (key only).
        free: list[str] = []
        vec = _vector_type(first)
        # A monomorphized slot (numeric `lane_parameter`) is a full specialization over a concrete
        # `generic<16>`, so it adds no lane template parameter; a `LANES`-parametric sized vector
        # adds the unbound lane param to the (partial-specialization) head.
        if first.uses_sized_vector and not first.lane_parameter.isdigit():
            free.append(f"std::size_t {first.lane_parameter}")
        if first.immediate is not None:
            free.append(f"{first.immediate[1]} {first.immediate[0]}")
        # Free SIMD type params are unbound in the (partial) specialization — head AND key.
        free += [f"class {name}" for name, _ in first.type_params]
        free += [f"{typ} {name}" for name, typ, _ in first.generic_params]
        head = f"template <{', '.join(free)}>" if free else "template <>"
        # A boolean-wildcard attribute keys the specialization so both variants coexist.
        # A representation-change primitive keys on (source, target) so each target is its
        # own specialization (`reinterpret_impl<simd<i32,avx2>, simd<u32,avx2>>`).
        key = vec
        if first.target is not None:
            key += f", {first.target.vector_spelling}"
        key += "".join(f", {name}" for name, _ in first.type_params)
        key += "".join(f", {value}" for _, value in first.axis)
        if first.immediate is not None:
            key += f", {first.immediate[0]}"
        key += "".join(f", {name}" for name, _, _ in first.generic_params)
        applies: list[str] = []
        seen: set[tuple[str, ...]] = set()
        for spec in group:
            # Dedup overloads that collapse to the same parameter types (a `v` and an
            # `s` parameter are identical where register_type == base_type, i.e. scalar).
            signature = effective_param_types(spec)
            if signature in seen:
                continue
            seen.add(signature)
            index_type = spec.type_params[0][0] if spec.type_params else None
            params = ", ".join(
                f"{_param_type(kind, index_type)} {name}"
                for name, kind in zip(spec.param_names, spec.param_kinds)
                if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
            )
            doc = _cpp_doc(spec, context="C++ specialization", indent="    ")
            prefix = f"{doc}\n" if doc else ""
            applies.append(
                f"{prefix}"
                f"    static inline {_apply_result_type(spec)} apply({params}) {{\n"
                f"        {spec.body_text}\n"
                f"    }}"
            )
        # A representation-change spec exposes `ToVec` (the target vector) in the impl so a
        # `tv` param / the result can project through it (`typename ToVec::register_type`).
        to_vec = (
            f"    using ToVec = {first.target.vector_spelling};\n"
            if first.target is not None
            else ""
        )
        return (
            f"{head}\nstruct {first.primitive_name}_impl<{key}> {{\n"
            f"    using Vec = {vec};\n" + to_vec + "\n".join(applies) + "\n};"
        )

    def _wrapper(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        signature = _wrapper_signature(specializations)
        doc = _cpp_doc(specializations[0], context="C++ wrapper", concrete=False)
        prefix = f"{doc}\n" if doc else ""
        return (
            prefix
            + f"template <{', '.join(signature.template_params)}>\n"
            f"inline {signature.result_type} {primitive_name}({signature.params}) {{\n"
            f"    return {primitive_name}_impl<{signature.impl_args}>::apply("
            f"{signature.argument_names});\n"
            f"}}"
        )

    def _wrapper_declaration(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        signature = _wrapper_signature(specializations)
        doc = _cpp_doc(specializations[0], context="C++ wrapper", concrete=False)
        prefix = f"{doc}\n" if doc else ""
        return (
            prefix
            + f"template <{', '.join(signature.template_params)}>\n"
            f"{signature.result_type} {primitive_name}({signature.params});"
        )


@dataclass(frozen=True, slots=True)
class _WrapperSignature:
    template_params: tuple[str, ...]
    params: str
    argument_names: str
    impl_args: str
    result_type: str


def _wrapper_signature(
    specializations: tuple[LoweredSpecialization, ...],
) -> _WrapperSignature:
    shape = specializations[0]
    # Positions whose parameter kind differs across signatures are the overload's
    # dispatch points: they become generic template params so C++ resolves the call.
    varying = varying_positions(specializations)
    immediate_params = (
        [f"{shape.immediate[1]} {shape.immediate[0]}"]
        if shape.immediate is not None
        else []
    )
    has_target = shape.target is not None
    index_type = shape.type_params[0][0] if shape.type_params else None
    template_params = (
        ["class Vec"]
        + (["class ToVec"] if has_target else [])
        + [f"class {name}" for name, _ in shape.type_params]
        + [f"bool {_axis_name(k)} = false" for k, _ in shape.axis]
        + immediate_params
        + [f"{typ} {name} = {default}" for name, typ, default in shape.generic_params]
        + [f"class Arg{i}" for i in varying]
    )
    params = ", ".join(
        (
            f"Arg{i} {name}"
            if i in varying
            else f"{_param_type(kind, index_type)} {name}"
        )
        for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    names = ", ".join(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    impl_args = (
        "Vec"
        + (", ToVec" if has_target else "")
        + "".join(f", {name}" for name, _ in shape.type_params)
        + "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        + (f", {shape.immediate[0]}" if shape.immediate is not None else "")
        + "".join(f", {name}" for name, _, _ in shape.generic_params)
    )
    # The wrapper's result projects through the caller-bound `ToVec` param.
    result_type = (
        "typename ToVec::register_type"
        if has_target
        else _result_type(shape.result_kind)
    )
    return _WrapperSignature(
        template_params=tuple(template_params),
        params=params,
        argument_names=names,
        impl_args=impl_args,
        result_type=result_type,
    )


def _free_function(spec: LoweredSpecialization, *, define: bool) -> str:
    """A non-vector primitive (`allocate`/`deallocate`): a plain `inline` function in the `tsl`
    namespace, not a `simd<>`-templated wrapper. `define=False` emits just the prototype (so a
    free function may call any wrapper regardless of emission order); `define=True` adds the body."""

    params = ", ".join(
        f"{_free_kind_type(kind, spec.base_type_spelling)} {name}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    signature = (
        f"inline {_free_kind_type(spec.result_kind, spec.base_type_spelling)} "
        f"{spec.primitive_name}({params})"
    )
    doc = _cpp_doc(spec, context="C++ free function")
    if not define:
        prefix = f"{doc}\n" if doc else ""
        return f"{prefix}{signature};"
    return f"{signature} {{\n    {spec.body_text}\n}}"


def _cpp_doc(
    spec: LoweredSpecialization,
    *,
    context: str,
    indent: str = "",
    concrete: bool = True,
) -> str:
    return render_cpp_doc(
        _doc_block(spec, context=context, concrete=concrete), indent=indent
    )


def _doc_block(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool,
) -> DocumentationBlock:
    if not concrete:
        return documentation_block(
            spec.documentation,
            facts=(
                ("Template parameters", _cpp_template_summary(spec)),
                ("Returns", _cpp_result_summary(spec, concrete=False)),
                ("Parameters", _runtime_parameter_summary(spec)),
            ),
            facts_title="API",
        )
    facts = [
        ("Extension", spec.extension_name),
        ("Element type", spec.base_type_spelling),
        ("Register type", _cpp_register_doc(spec)),
        ("Returns", _cpp_result_summary(spec, concrete=True)),
        ("Parameters", _runtime_parameter_summary(spec)),
    ]
    if spec.target is not None:
        facts.extend(
            [
                ("Target vector", spec.target.vector_spelling),
                ("Target register", _cpp_target_register_doc(spec)),
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


def _cpp_template_summary(spec: LoweredSpecialization) -> str:
    params = ["Vec selects the SIMD vector type"]
    if spec.target is not None:
        params.append("ToVec selects the target SIMD vector type")
    params.extend(
        f"{name} selects an additional SIMD vector type"
        for name, _ in spec.type_params
    )
    params.extend(f"{_axis_name(key)} selects `{key}`" for key, _ in spec.axis)
    if spec.immediate is not None:
        params.append(f"{spec.immediate[0]} is a compile-time immediate")
    params.extend(
        f"{name} selects `{name}`"
        for name, _typ, _default in spec.generic_params
    )
    return "; ".join(params)


def _cpp_result_summary(spec: LoweredSpecialization, *, concrete: bool) -> str:
    if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    ):
        return result_summary(
            spec.result_kind,
            _free_kind_type(spec.result_kind, spec.base_type_spelling),
        )
    if concrete:
        return result_summary(spec.result_kind, _cpp_concrete_result_type(spec))
    if spec.target is not None:
        return result_summary(spec.result_kind, "typename ToVec::register_type")
    return result_summary(spec.result_kind, _result_type(spec.result_kind))


def _cpp_concrete_result_type(spec: LoweredSpecialization) -> str:
    if spec.target is not None:
        return _cpp_target_register_doc(spec)
    if spec.result_kind == "v":
        return _cpp_register_doc(spec)
    return _apply_result_type(spec)


def _cpp_register_doc(spec: LoweredSpecialization) -> str:
    return _cpp_native_register_doc(
        extension_name=spec.extension_name,
        base_spelling=spec.base_type_spelling,
        uses_sized_vector=spec.uses_sized_vector,
        lane_parameter=spec.lane_parameter,
        register_is_base=spec.register_is_base,
        fallback=spec.register_spelling,
    )


def _cpp_target_register_doc(spec: LoweredSpecialization) -> str:
    if spec.target is None:
        return ""
    return _cpp_native_register_doc(
        extension_name=spec.target.extension_isa,
        base_spelling=spec.target.base_spelling,
        uses_sized_vector=spec.target.uses_sized_vector,
        lane_parameter=spec.target.lane_parameter or spec.lane_parameter,
        register_is_base=False,
        fallback=spec.target.register_spelling,
    )


def _cpp_native_register_doc(
    *,
    extension_name: str,
    base_spelling: str,
    uses_sized_vector: bool,
    lane_parameter: str | None,
    register_is_base: bool,
    fallback: str,
) -> str:
    if uses_sized_vector:
        return f"::tsl::array_type<{base_spelling}, {lane_parameter}>"
    bits = x86_register_bits(extension_name)
    if bits is not None:
        if base_spelling == "float":
            return f"__m{bits}"
        if base_spelling == "double":
            return f"__m{bits}d"
        return f"__m{bits}i"
    if register_is_base:
        return base_spelling
    return fallback


def _free_kind_type(kind: str, base_spelling: str) -> str:
    """A free function's kind -> concrete type (no `Vec` projection). Pointer spellings
    carry their own mutability; `usize` is a size; `void` is no value."""

    return DEFAULT_SUPPORT_POLICY.cpp_free_type(kind, base_type=base_spelling)


def _vector_type(spec: LoweredSpecialization) -> str:
    if spec.uses_sized_vector:
        lane_parameter = spec.lane_parameter
        return f"tsl::simd<{spec.base_type_spelling}, tsl::generic<{lane_parameter}>>"
    return f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"


def _axis_name(key: str) -> str:
    """An axis attribute key as a C++ template-parameter name (`aligned` -> `Aligned`)."""

    return key[:1].upper() + key[1:]


def _apply_result_type(spec: LoweredSpecialization) -> str:
    """The `apply` result type. A representation-change spec returns the (concrete) target
    register; otherwise the kind projects through `Vec`."""

    if spec.target is not None:
        return spec.target.register_spelling
    return _result_type(spec.result_kind)


def _result_type(kind: str) -> str:
    return DEFAULT_SUPPORT_POLICY.cpp_result_type(kind)


def _param_type(kind: str, index_type: str | None = None) -> str:
    return DEFAULT_SUPPORT_POLICY.cpp_param_type(kind, index_type=index_type)
