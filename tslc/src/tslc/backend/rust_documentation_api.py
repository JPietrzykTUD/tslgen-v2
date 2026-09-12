"""Rust documentation-only public API wrappers."""

from __future__ import annotations

from tslc.backend.checked_api import (
    applicable_checked_api_plan,
    checked_memory_condition,
)
from tslc.backend.rust_documentation import rust_doc
from tslc.backend.rust_signatures import (
    checked_params,
    checked_type_where,
    free_kind_type,
    generic_decls,
    kind_type,
    param_kind_type,
    params,
    unsafe_prefix,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.rust_type_params import index_where
from tslc.catalog.memory import MemoryAccess
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


def documentation_checked_wrapper(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return ""
    shape = specializations[0]
    declarations = generic_decls(shape)
    result_owner = "S"
    target_owner: str | None = None
    if shape.target is not None:
        declarations = ["T: StaticSimdVector", *declarations]
        result_owner = "T"
        target_owner = "T"
    index_type: str | None = None
    if shape.type_params:
        declarations = [
            *(f"{param.name}: StaticSimdVector" for param in shape.type_params),
            *declarations,
        ]
        index_type = f"{shape.type_params[0].name}::RegisterType"
        if shape.result_vector_param is not None:
            result_owner = shape.result_vector_param
    generics = ", ".join(("S: StaticSimdVector", *declarations))
    rendered_params = checked_params(
        shape,
        "S",
        plan,
        target_owner=target_owner,
        vidx_type=index_type,
    )
    result_type = kind_type(shape.result_kind, result_owner)
    doc = rust_doc(
        shape,
        context="Rust checked documentation facade",
        concrete=False,
        checked_conditions=plan.conditions,
        specializations=specializations,
    )
    where_clause = checked_type_where(plan, "S")
    index_clause = index_where(shape, base_dispatch="projection")
    if where_clause and index_clause:
        raise ValueError(
            "checked documentation wrapper cannot combine numeric and index bounds"
        )
    where_clause = where_clause or index_clause
    opening_brace = f"{where_clause}\n{{" if where_clause else " {"
    return (
        (f"{doc}\n" if doc else "")
        + "#[inline]\n"
        + f"pub fn {rust_raw_identifier(primitive_name + '_checked')}"
        f"<{generics}>({rendered_params}) -> Result<{result_type}, PreconditionError>"
        f"{opening_brace}\n"
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
    doc = rust_doc(
        shape,
        context="Rust documentation facade",
        concrete=False,
        specializations=specs,
    )
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
        f"<{', '.join(declarations)}>({rendered_params}) -> {result_type} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def documentation_overloaded_checked_wrapper(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specs)
    if plan is None:
        return ""
    shape = specs[0]
    varying_index = varying_positions(specs)[0]
    memory = checked_memory_condition(plan.conditions)
    if memory is None:
        raise ValueError(
            "checked Rust documentation overload requires one memory binding"
        )
    memory_index = memory.parameter_index
    memory_name = memory.parameter_name
    memory_access = memory.memory_access
    declarations = ["S: StaticSimdVector", *generic_decls(shape), "V"]
    rendered_params = ", ".join(
        (
            f"{name}: V"
            if index == varying_index
            else f"{name}: {'&' if memory_access is MemoryAccess.READ else '&mut '}"
            f"[S::BaseType]"
            if index == memory_index and name == memory_name
            else f"{name}: {param_kind_type(kind, 'S')}"
        )
        for index, (name, kind) in enumerate(
            zip(shape.param_names, shape.param_kinds)
        )
    )
    result_type = kind_type(shape.result_kind, "S")
    doc = rust_doc(
        shape,
        context="Rust checked documentation facade",
        concrete=False,
        checked_conditions=plan.conditions,
        specializations=specs,
    )
    return (
        (f"{doc}\n" if doc else "")
        + "#[inline]\n"
        + f"pub fn {rust_raw_identifier(primitive_name + '_checked')}"
        f"<{', '.join(declarations)}>({rendered_params}) "
        f"-> Result<{result_type}, PreconditionError> {{\n"
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
    "documentation_checked_wrapper",
    "documentation_free_function",
    "documentation_overloaded_checked_wrapper",
    "documentation_overloaded_wrapper",
    "documentation_wrapper",
)
