"""Plan Rust primitive wrapper declarations from typed specializations."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.checked_api import (
    CheckedApiPlan,
    applicable_checked_api_plan,
    checked_memory_condition,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_public_declarations import (
    RustGenericParameter,
    RustPublicDeclaration,
    RustPublicParameter,
    rust_const_parameter,
    rust_parameter_role,
    rust_type_parameter,
)
from tslc.backend.rust_signatures import (
    axis_name,
    checked_parameter_types,
    checked_type_where_predicates,
    kind_type,
    param_kind_type,
    parameter_types,
    trait_args_by_name,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.rust_type_params import (
    type_param_base_key_args,
    type_param_names,
    type_param_where_clauses,
)
from tslc.catalog.memory import MemoryAccess
from tslc.catalog.preconditions import PreconditionCheckPrimitive, PreconditionKind
from tslc.lower.lowerer import LoweredSpecialization, varying_positions

PRIMITIVE_TRAIT_PREFIX = "detail::primitives::"


@dataclass(frozen=True, slots=True)
class RustPublicWrapperFacts:
    trait_args: tuple[str, ...]
    public_trait_args: tuple[str, ...]
    generic_parameters: tuple[RustGenericParameter, ...]
    target_owner: str | None
    result_owner: str
    index_type: str | None
    vector_bound: str


def rust_const_generic_parameters(
    shape: LoweredSpecialization,
) -> tuple[RustGenericParameter, ...]:
    parameters = [
        rust_const_parameter(axis_name(key), "bool") for key, _ in shape.axis
    ]
    if shape.immediate is not None:
        parameters.append(
            rust_const_parameter(shape.immediate[0], shape.immediate[1])
        )
    parameters.extend(
        rust_const_parameter(name, typ)
        for name, typ, _default in shape.generic_params
    )
    return tuple(parameters)


def rust_type_generic_parameters(
    shape: LoweredSpecialization,
) -> tuple[RustGenericParameter, ...]:
    return tuple(
        rust_type_parameter(
            parameter.name,
            "StaticSimdVector",
            *(
                f"{PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(bound)}"
                for bound in parameter.bounds
            ),
        )
        for parameter in shape.type_params
    )


def rust_public_wrapper_facts(
    primitive_name: str,
    shape: LoweredSpecialization,
) -> RustPublicWrapperFacts:
    public_trait_args = list(trait_args_by_name(shape))
    trait_args = list(public_trait_args)
    generic_parameters: list[RustGenericParameter] = list(
        rust_const_generic_parameters(shape)
    )
    target_owner: str | None = None
    result_owner = "S"
    if shape.target is not None:
        trait_args.insert(0, "T")
        public_trait_args.insert(0, "T")
        generic_parameters.insert(0, rust_type_parameter("T", "StaticSimdVector"))
        target_owner = "T"
        result_owner = "T"
    index_type: str | None = None
    if shape.type_params:
        type_names = type_param_names(shape)
        trait_args = [
            *type_names,
            *type_param_base_key_args(shape, mode="projection"),
            *trait_args,
        ]
        public_trait_args = [*type_names, *public_trait_args]
        generic_parameters = [
            *rust_type_generic_parameters(shape),
            *generic_parameters,
        ]
        index_type = f"{shape.type_params[0].name}::RegisterType"
        if shape.result_vector_param is not None:
            result_owner = shape.result_vector_param
    rendered_trait_args = f"<{', '.join(trait_args)}>" if trait_args else ""
    vector_bound = (
        f"{PRIMITIVE_TRAIT_PREFIX}"
        f"{rust_primitive_trait_name(primitive_name)}{rendered_trait_args}"
    )
    return RustPublicWrapperFacts(
        trait_args=tuple(trait_args),
        public_trait_args=tuple(public_trait_args),
        generic_parameters=tuple(generic_parameters),
        target_owner=target_owner,
        result_owner=result_owner,
        index_type=index_type,
        vector_bound=vector_bound,
    )


def rust_checked_generic_parameters(
    shape: LoweredSpecialization,
    facts: RustPublicWrapperFacts,
    plan: CheckedApiPlan,
) -> tuple[RustGenericParameter, ...]:
    """Add checked-guard dependencies owned by a free SIMD type parameter."""

    if not shape.type_params:
        return facts.generic_parameters
    index_owner = shape.type_params[0].name
    index_bounds: list[str] = []
    for condition in plan.conditions:
        if condition.kind is not PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            continue
        if (
            PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
            in condition.check_primitives
        ):
            primitive = PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
            index_bounds.append(
                f"{PRIMITIVE_TRAIT_PREFIX}"
                f"{rust_primitive_trait_name(primitive.value)}"
            )
    if not index_bounds:
        return facts.generic_parameters
    return tuple(
        rust_type_parameter(
            parameter.name,
            *parameter.bounds,
            *(bound for bound in index_bounds if bound not in parameter.bounds),
        )
        if parameter.name == index_owner
        else parameter
        for parameter in facts.generic_parameters
    )


def rust_overload_identity(
    specializations: tuple[LoweredSpecialization, ...], surface: str
) -> str:
    shapes = sorted(
        {
            f"{spec.result_kind}=({','.join(spec.param_kinds)})"
            for spec in specializations
        }
    )
    return f"{surface}:" + "|".join(shapes)


def rust_wrapper_declaration(
    primitive_name: str,
    shape: LoweredSpecialization,
    *,
    caller_unsafe: bool,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration:
    facts = rust_public_wrapper_facts(primitive_name, shape)
    parameters = tuple(
        RustPublicParameter(
            name,
            typ,
            rust_parameter_role(shape, index, shape.param_kinds[index]),
        )
        for index, name, typ in parameter_types(
            shape,
            "S",
            target_owner=facts.target_owner,
            vidx_type=facts.index_type,
        )
    )
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}#vector",
        name=rust_raw_identifier(primitive_name),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=rust_overload_identity((shape,), "vector"),
        visibility="pub",
        generic_parameters=(
            rust_type_parameter("S", facts.vector_bound),
            *facts.generic_parameters,
        ),
        parameters=parameters,
        where_predicates=tuple(
            type_param_where_clauses(shape, base_dispatch="projection")
        ),
        where_inline=True,
        result_type=kind_type(shape.result_kind, facts.result_owner),
        result_form="direct",
        unsafe=caller_unsafe,
    )


def rust_checked_wrapper_declaration(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    *,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration | None:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return None
    shape = specializations[0]
    facts = rust_public_wrapper_facts(primitive_name, shape)
    checked_where = checked_type_where_predicates(plan, "S")
    index_where = tuple(
        type_param_where_clauses(shape, base_dispatch="projection")
    )
    if checked_where and index_where:
        raise ValueError(
            "checked wrapper cannot combine numeric-domain and index-vector bounds"
        )
    parameters = tuple(
        RustPublicParameter(
            name,
            typ,
            rust_parameter_role(shape, index, shape.param_kinds[index]),
        )
        for index, name, typ in checked_parameter_types(
            shape,
            "S",
            plan,
            target_owner=facts.target_owner,
            vidx_type=facts.index_type,
        )
    )
    ordinary_identity = f"crate::profile::{primitive_name}#vector"
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}_checked#vector",
        name=rust_raw_identifier(f"{primitive_name}_checked"),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=rust_overload_identity(specializations, "checked-vector"),
        visibility="pub",
        generic_parameters=(
            rust_type_parameter("S", facts.vector_bound),
            *rust_checked_generic_parameters(shape, facts, plan),
        ),
        parameters=parameters,
        where_predicates=checked_where or index_where,
        result_type=(
            f"Result<{kind_type(shape.result_kind, facts.result_owner)}, "
            "PreconditionError>"
        ),
        result_form="result",
        attributes=("#[inline]",),
        checked_of=ordinary_identity,
        error_form="result",
    )


def rust_overloaded_wrapper_declaration(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    *,
    checked: bool,
    caller_unsafe: bool,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration | None:
    shape = specializations[0]
    varying = varying_positions(specializations)
    if len(varying) != 1:
        raise ValueError("Rust public overload requires one varying parameter")
    varying_index = varying[0]
    axis_args = "".join(f", {axis_name(key)}" for key, _ in shape.axis)
    generic_args = "".join(
        f", {name}" for name, _typ, _default in shape.generic_params
    )
    arg_trait = (
        f"{PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
    )
    generics: tuple[RustGenericParameter, ...] = (
        rust_type_parameter("S", "StaticSimdVector"),
        *rust_const_generic_parameters(shape),
        rust_type_parameter("V", f"{arg_trait}<S{axis_args}{generic_args}>"),
    )
    plan = applicable_checked_api_plan(specializations) if checked else None
    if checked and plan is None:
        return None
    memory = checked_memory_condition(plan.conditions) if plan is not None else None
    parameters: list[RustPublicParameter] = []
    for index, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds)):
        if index == varying_index:
            typ = "V"
        elif memory is not None and index == memory.parameter_index:
            typ = (
                "&[S::BaseType]"
                if memory.memory_access is MemoryAccess.READ
                else "&mut [S::BaseType]"
            )
        else:
            typ = param_kind_type(kind, "S")
        parameters.append(
            RustPublicParameter(
                name,
                typ,
                rust_parameter_role(shape, index, kind),
            )
        )
    suffix = "_checked" if checked else ""
    ordinary_identity = f"crate::profile::{primitive_name}#overload"
    result = kind_type(shape.result_kind, "S")
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}{suffix}#overload",
        name=rust_raw_identifier(f"{primitive_name}{suffix}"),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=rust_overload_identity(
            specializations, "checked-overload" if checked else "overload"
        ),
        visibility="pub",
        generic_parameters=generics,
        parameters=tuple(parameters),
        result_type=(
            f"Result<{result}, PreconditionError>" if checked else result
        ),
        result_form="result" if checked else "direct",
        attributes=("#[inline]",) if checked else (),
        unsafe=caller_unsafe and not checked,
        checked_of=ordinary_identity if checked else None,
        error_form="result" if checked else None,
    )


__all__ = (
    "PRIMITIVE_TRAIT_PREFIX",
    "rust_checked_wrapper_declaration",
    "rust_overloaded_wrapper_declaration",
    "rust_wrapper_declaration",
)
