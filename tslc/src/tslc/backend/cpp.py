"""C++ backend: render a primitive as primary template + simd<> specializations + wrapper."""

from __future__ import annotations

from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)


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

    def _specialization(self, group: list[LoweredSpecialization]) -> str:
        first = group[0]
        # The `generic` vector is sized: its specialization is parameterized by `LANES` (the
        # tag carries it), so it emits as `template <std::size_t LANES> struct …_impl<simd<T,
        # generic<LANES>>>` rather than a full specialization.
        # Free template params of the (partial) specialization: the generic vector's `LANES`
        # and an `sImm` immediate (both unbound, so they appear in the head AND the key);
        # concrete axis values are bound literals (key only).
        free: list[str] = []
        if first.extension_name == "generic":
            vec = f"tsl::simd<{first.base_type_spelling}, tsl::generic<LANES>>"
            free.append("std::size_t LANES")
        else:
            vec = f"tsl::simd<{first.base_type_spelling}, tsl::{first.extension_name}>"
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
                if kind != "sImm"  # the immediate is a template param, not a runtime arg
            )
            applies.append(
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
        shape = specializations[0]
        # Positions whose parameter kind differs across signatures are the overload's
        # dispatch points: they become generic template params so C++ resolves the call.
        varying = varying_positions(specializations)
        immediate_params = (
            [f"{shape.immediate[1]} {shape.immediate[0]}"] if shape.immediate is not None else []
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
            (f"Arg{i} {name}" if i in varying else f"{_param_type(kind, index_type)} {name}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if kind != "sImm"  # the immediate is a template param, not a runtime arg
        )
        names = ", ".join(
            name
            for name, kind in zip(shape.param_names, shape.param_kinds)
            if kind != "sImm"
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
        result_type = "typename ToVec::register_type" if has_target else _result_type(shape.result_kind)
        return (
            f"template <{', '.join(template_params)}>\n"
            f"inline {result_type} {primitive_name}({params}) {{\n"
            f"    return {primitive_name}_impl<{impl_args}>::apply({names});\n"
            f"}}"
        )


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
    return {
        "v": "typename Vec::register_type",
        "s": "typename Vec::base_type",
        "m": "typename Vec::mask_type",
        "im": "typename Vec::imask_type",
        "usize": "std::size_t",
        "void": "void",
        "s[]": "typename ::tsl::array_for<Vec>::type",
    }[kind]


def _param_type(kind: str, index_type: str | None = None) -> str:
    if kind == "v":
        return "typename tsl::reg_param<Vec>::type"
    if kind == "vt":  # a target-axis vector param (`insert`'s `orig`) — the ToVec register
        return "typename tsl::reg_param<ToVec>::type"
    if kind == "vidx":  # a gather/scatter index vector — the IndicesType register
        return f"typename tsl::reg_param<{index_type}>::type"
    if kind == "m":
        return "typename Vec::mask_type"
    if kind == "im":
        return "typename Vec::imask_type"
    if kind == "usize":
        return "std::size_t"
    if kind == "ptr":
        return "typename Vec::base_type *"
    if kind == "s[]":
        return "typename ::tsl::array_for<Vec>::type"
    return "typename Vec::base_type"
