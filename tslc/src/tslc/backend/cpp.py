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

        shape = specializations[0]  # all share the same signature shape + axis keys
        decl_params = "class Vec" + "".join(f", bool {_axis_name(k)}" for k, _ in shape.axis)
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

        groups: dict[tuple[str, str, tuple], list[LoweredSpecialization]] = {}
        order: list[tuple[str, str, tuple]] = []
        for spec in specializations:
            key = (spec.base_type_spelling, spec.extension_name, spec.axis)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(spec)
        return "\n\n".join(self._specialization(groups[key]) for key in order)

    def _specialization(self, group: list[LoweredSpecialization]) -> str:
        first = group[0]
        vec = f"tsl::simd<{first.base_type_spelling}, tsl::{first.extension_name}>"
        # A boolean-wildcard attribute keys the specialization so both variants coexist.
        key = vec + "".join(f", {value}" for _, value in first.axis)
        applies: list[str] = []
        seen: set[tuple[str, ...]] = set()
        for spec in group:
            # Dedup overloads that collapse to the same parameter types (a `v` and an
            # `s` parameter are identical where register_type == base_type, i.e. scalar).
            signature = _effective_param_types(spec)
            if signature in seen:
                continue
            seen.add(signature)
            params = ", ".join(
                f"{_param_type(kind)} {name}"
                for name, kind in zip(spec.param_names, spec.param_kinds)
            )
            applies.append(
                f"    static inline {_result_type(spec.result_kind)} apply({params}) {{\n"
                f"        {spec.body_text}\n"
                f"    }}"
            )
        return (
            f"template <>\nstruct {first.primitive_name}_impl<{key}> {{\n"
            f"    using Vec = {vec};\n" + "\n".join(applies) + "\n};"
        )

    def _wrapper(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        # Positions whose parameter kind differs across signatures are the overload's
        # dispatch points: they become generic template params so C++ resolves the call.
        varying = _varying_positions(specializations)
        template_params = (
            ["class Vec"]
            + [f"bool {_axis_name(k)} = false" for k, _ in shape.axis]
            + [f"class Arg{i}" for i in varying]
        )
        params = ", ".join(
            (f"Arg{i} {name}" if i in varying else f"{_param_type(kind)} {name}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        names = ", ".join(shape.param_names)
        impl_args = "Vec" + "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        return (
            f"template <{', '.join(template_params)}>\n"
            f"inline {_result_type(shape.result_kind)} {primitive_name}({params}) {{\n"
            f"    return {primitive_name}_impl<{impl_args}>::apply({names});\n"
            f"}}"
        )


def _varying_positions(specs: tuple[LoweredSpecialization, ...]) -> tuple[int, ...]:
    """Parameter positions whose kind differs across the primitive's signatures."""

    if not specs:
        return ()
    arity = len(specs[0].param_kinds)
    return tuple(
        i for i in range(arity) if len({spec.param_kinds[i] for spec in specs}) > 1
    )


def _effective_param_types(spec: LoweredSpecialization) -> tuple[str, ...]:
    """A per-position type token for overload dedup. `v` and `s` map to the same token
    where register_type == base_type (scalar/generic), so colliding overloads merge."""

    def token(kind: str) -> str:
        if kind == "v":
            return "base" if spec.register_is_base else "register"
        if kind == "m":
            return "mask"
        if kind == "ptr":
            return "ptr"
        return "base"  # s

    return tuple(token(kind) for kind in spec.param_kinds)


def _axis_name(key: str) -> str:
    """An axis attribute key as a C++ template-parameter name (`aligned` -> `Aligned`)."""

    return key[:1].upper() + key[1:]


def _result_type(kind: str) -> str:
    return {
        "v": "typename Vec::register_type",
        "s": "typename Vec::base_type",
        "m": "typename Vec::mask_type",
        "void": "void",
    }[kind]


def _param_type(kind: str) -> str:
    if kind == "v":
        return "typename tsl::reg_param<Vec>::type"
    if kind == "m":
        return "typename Vec::mask_type"
    if kind == "ptr":
        return "typename Vec::base_type *"
    return "typename Vec::base_type"
