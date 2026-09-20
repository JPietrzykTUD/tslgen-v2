"""Render ordinary Rust primitive wrapper functions."""

from __future__ import annotations

from tslc.backend.rust_documentation import rust_doc
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_primitive_declarations import (
    PRIMITIVE_TRAIT_PREFIX,
    rust_overloaded_wrapper_declaration,
    rust_wrapper_declaration,
)
from tslc.backend.rust_signatures import (
    axis_name,
    runtime_names,
    trait_args_by_name,
    unsafe_call,
)
from tslc.backend.rust_type_params import (
    type_param_base_key_args,
    type_param_names,
)
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


def render_overloaded_wrapper(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
    *,
    caller_unsafe: bool,
) -> str:
    shape = specs[0]
    varying_index = varying_positions(specs)[0]
    arg_trait = (
        f"{PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
    )
    axis_args = "".join(f", {axis_name(key)}" for key, _ in shape.axis)
    generic_args = "".join(
        f", {name}" for name, _typ, _default in shape.generic_params
    )
    fixed_names = [
        name
        for index, name in enumerate(shape.param_names)
        if index != varying_index
    ]
    call_args = ", ".join((shape.param_names[varying_index], *fixed_names))
    call = f"<V as {arg_trait}<S{axis_args}{generic_args}>>::apply({call_args})"
    call = unsafe_call(call, caller_unsafe)
    doc = rust_doc(
        shape,
        context="Rust wrapper",
        concrete=False,
        specializations=specs,
    )
    declaration = rust_overloaded_wrapper_declaration(
        primitive_name,
        specs,
        checked=False,
        caller_unsafe=caller_unsafe,
        reachability=("profile",),
    )
    assert declaration is not None
    return (
        (f"{doc}\n" if doc else "")
        + declaration.render_definition_head()
        + "\n"
        f"    {call}\n"
        "}"
    )


def render_wrapper(
    primitive_name: str,
    shape: LoweredSpecialization,
    *,
    caller_unsafe: bool,
) -> str:
    names = runtime_names(shape)
    # Generic arguments mirror the trait path exactly so non-injective
    # associated types such as index registers never rely on inference.
    trait_args = trait_args_by_name(shape)
    if shape.target is not None:
        trait_args = ["T", *trait_args]
    if shape.type_params:
        trait_args = [
            *type_param_names(shape),
            *type_param_base_key_args(shape, mode="projection"),
            *trait_args,
        ]
    rendered_trait_args = (
        f"<{', '.join(trait_args)}>" if trait_args else ""
    )
    call = (
        f"<S as {PRIMITIVE_TRAIT_PREFIX}"
        f"{rust_primitive_trait_name(primitive_name)}"
        f"{rendered_trait_args}>::apply({names})"
    )
    call = unsafe_call(call, caller_unsafe)
    doc = rust_doc(shape, context="Rust wrapper", concrete=False)
    declaration = rust_wrapper_declaration(
        primitive_name,
        shape,
        caller_unsafe=caller_unsafe,
        reachability=("profile",),
    )
    return (
        (f"{doc}\n" if doc else "")
        + declaration.render_definition_head()
        + "\n"
        f"    {call}\n"
        "}"
    )


__all__ = ("render_overloaded_wrapper", "render_wrapper")
