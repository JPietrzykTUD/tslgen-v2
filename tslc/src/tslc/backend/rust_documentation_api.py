"""Rust documentation-only public API wrappers."""

from __future__ import annotations

from tslc.backend.rust_documentation import rust_doc
from tslc.backend.rust_signatures import (
    free_kind_type,
    generic_decls,
    kind_type,
    param_kind_type,
    params,
    unsafe_prefix,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.rust_type_params import index_where
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


def documentation_wrapper(
    primitive_name: str,
    shape: LoweredSpecialization,
    *,
    caller_unsafe: bool,
) -> str:
    declarations = generic_decls(shape)
    result_type = kind_type(shape.result_kind, "S")
    target_owner: str | None = None
    if shape.target is not None:
        declarations = ["T: StaticSimdVector", *declarations]
        result_type = kind_type(shape.result_kind, "T")
        target_owner = "T"
    index_type: str | None = None
    if shape.type_params:
        declarations = [
            *(f"{param.name}: StaticSimdVector" for param in shape.type_params),
            *declarations,
        ]
        index_type = f"{shape.type_params[0].name}::RegisterType"
        if shape.result_vector_param is not None:
            result_type = kind_type(shape.result_kind, shape.result_vector_param)
    generics = ", ".join(("S: StaticSimdVector", *declarations))
    rendered_params = params(
        shape,
        "S",
        target_owner=target_owner,
        vidx_type=index_type,
    )
    doc = rust_doc(shape, context="Rust documentation facade", concrete=False)
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
        f"<{generics}>({rendered_params}) -> {result_type}"
        f"{index_where(shape, base_dispatch='projection')} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def documentation_overloaded_wrapper(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
    *,
    caller_unsafe: bool,
) -> str:
    shape = specs[0]
    varying_index = varying_positions(specs)[0]
    declarations = ["S: StaticSimdVector", *generic_decls(shape), "V"]
    rendered_params = ", ".join(
        (
            f"{name}: V"
            if index == varying_index
            else f"{name}: {param_kind_type(kind, 'S')}"
        )
        for index, (name, kind) in enumerate(
            zip(shape.param_names, shape.param_kinds)
        )
    )
    result_type = kind_type(shape.result_kind, "S")
    doc = rust_doc(shape, context="Rust documentation facade", concrete=False)
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
        f"<{', '.join(declarations)}>({rendered_params}) -> {result_type} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def documentation_free_function(spec: LoweredSpecialization) -> str:
    rendered_params = ", ".join(
        f"{name}: {free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    result = (
        ""
        if spec.result_kind == "void"
        else f" -> {free_kind_type(spec.result_kind, spec)}"
    )
    doc = rust_doc(spec, context="Rust documentation facade")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(spec.safety.caller_unsafe)}fn "
        f"{rust_raw_identifier(spec.primitive_name)}({rendered_params}){result} {{\n"
        "    unimplemented!()\n"
        "}"
    )


__all__ = (
    "documentation_free_function",
    "documentation_overloaded_wrapper",
    "documentation_wrapper",
)
