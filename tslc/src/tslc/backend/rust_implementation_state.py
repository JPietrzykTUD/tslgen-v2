"""Rust profile queries for lowered primitive implementation state."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.backend.rust_const_args import RUST_CONST_ARG_WRAPPERS
from tslc.backend.rust_names import (
    rust_primitive_tag_name,
    rust_primitive_trait_name,
)
from tslc.backend.rust_type_params import (
    type_param_base_key_args,
    type_param_decls,
    type_param_where_clauses,
)
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def render_implementation_state_queries(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> str:
    parts: list[str] = []
    for primitive_name in sorted(by_primitive):
        specs = by_primitive[primitive_name]
        if not specs or DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            specs[0].result_kind,
            specs[0].param_kinds,
        ):
            continue
        rendered = (
            _overloaded_query(primitive_name, specs)
            if varying_positions(specs)
            else _ordinary_query(primitive_name, specs[0])
        )
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def _ordinary_query(
    primitive_name: str,
    shape: LoweredSpecialization,
) -> str:
    trait_name = rust_primitive_trait_name(primitive_name)
    tag_name = rust_primitive_tag_name(primitive_name)
    generics = _query_generics(shape)
    trait_args = _query_trait_args(shape)
    args = _query_args(shape)
    where_clauses = [
        f"S: detail::primitives::{trait_name}{_generic_args(trait_args)}",
        *type_param_where_clauses(shape, base_dispatch="projection"),
    ]
    return (
        f"impl<{', '.join(generics)}> "
        f"ImplementationStateOf<crate::primitive::{tag_name}, S, {_tuple_type(args)}> "
        "for Profile\n"
        "where\n"
        f"{_where_clause_lines(where_clauses)}\n"
        "{\n"
        "    const VALUE: ImplementationState = "
        f"<S as detail::primitives::{trait_name}{_generic_args(trait_args)}>"
        "::IMPLEMENTATION_STATE;\n"
        "}"
    )


def _overloaded_query(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
) -> str:
    shape = specs[0]
    trait_name = f"{rust_primitive_trait_name(primitive_name)}Arg"
    tag_name = rust_primitive_tag_name(primitive_name)
    generics = ["S: StaticSimdVector", *_query_const_generics(shape), "V"]
    trait_args = ["S", *_query_trait_const_args(shape)]
    args = [*_query_const_args(shape), "V"]
    where_clauses = [
        f"V: detail::primitives::{trait_name}{_generic_args(trait_args)}",
        *type_param_where_clauses(shape, base_dispatch="projection"),
    ]
    return (
        f"impl<{', '.join(generics)}> "
        f"ImplementationStateOf<crate::primitive::{tag_name}, S, {_tuple_type(args)}> "
        "for Profile\n"
        "where\n"
        f"{_where_clause_lines(where_clauses)}\n"
        "{\n"
        "    const VALUE: ImplementationState = "
        f"<V as detail::primitives::{trait_name}{_generic_args(trait_args)}>"
        "::IMPLEMENTATION_STATE;\n"
        "}"
    )


def _query_generics(shape: LoweredSpecialization) -> list[str]:
    generics = ["S"]
    if shape.target is not None:
        generics.append("ToVec: StaticSimdVector")
    generics.extend(type_param_decls(shape, trait_prefix="detail::primitives::"))
    generics.extend(_query_const_generics(shape))
    return generics


def _query_const_generics(shape: LoweredSpecialization) -> list[str]:
    generics = [f"const {_axis_name(key)}: bool" for key, _ in shape.axis]
    if shape.immediate is not None:
        generics.append(f"const {shape.immediate[0]}: {shape.immediate[1]}")
    generics.extend(f"const {name}: {typ}" for name, typ, _ in shape.generic_params)
    return generics


def _query_trait_args(shape: LoweredSpecialization) -> list[str]:
    args: list[str] = []
    if shape.target is not None:
        args.append("ToVec")
    args.extend(param.name for param in shape.type_params)
    args.extend(type_param_base_key_args(shape, mode="projection"))
    args.extend(_query_trait_const_args(shape))
    return args


def _query_trait_const_args(shape: LoweredSpecialization) -> list[str]:
    args = [_axis_name(key) for key, _ in shape.axis]
    if shape.immediate is not None:
        args.append(shape.immediate[0])
    args.extend(name for name, _typ, _default in shape.generic_params)
    return args


def _query_args(shape: LoweredSpecialization) -> list[str]:
    args: list[str] = []
    if shape.target is not None:
        args.append("ToVec")
    args.extend(param.name for param in shape.type_params)
    args.extend(_query_const_args(shape))
    return args


def _query_const_args(shape: LoweredSpecialization) -> list[str]:
    args = [f"BoolArg<{_axis_name(key)}>" for key, _ in shape.axis]
    if shape.immediate is not None:
        args.append(const_arg_type(shape.immediate[1], shape.immediate[0]))
    args.extend(
        const_arg_type(typ, name)
        for name, typ, _default in shape.generic_params
    )
    return args


def const_arg_type(typ: str, name: str) -> str:
    wrapper = RUST_CONST_ARG_WRAPPERS.get(typ)
    assert wrapper is not None, (
        "Rust profile validation missed an unsupported const argument type: "
        f"{typ!r}"
    )
    return f"{wrapper}<{name}>"


def _generic_args(args: list[str]) -> str:
    return f"<{', '.join(args)}>" if args else ""


def _tuple_type(args: list[str]) -> str:
    if not args:
        return "()"
    if len(args) == 1:
        return f"({args[0]},)"
    return f"({', '.join(args)})"


def _where_clause_lines(clauses: list[str]) -> str:
    return "\n".join(f"    {clause}," for clause in clauses)


def _axis_name(key: str) -> str:
    return key.upper()
