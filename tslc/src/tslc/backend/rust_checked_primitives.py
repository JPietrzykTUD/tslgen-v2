"""Render Rust checked primitive contracts and wrapper bodies."""

from __future__ import annotations

from tslc.backend.checked_api import (
    CheckedConditionPlan,
    applicable_checked_api_plan,
    applicable_checked_condition,
    checked_memory_condition,
)
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.rust_direct_calls import indent
from tslc.backend.rust_documentation import rust_doc
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_primitive_declarations import (
    PRIMITIVE_TRAIT_PREFIX,
    rust_checked_wrapper_declaration,
    rust_overloaded_wrapper_declaration,
)
from tslc.backend.rust_signatures import (
    axis_name,
    checked_runtime_names,
    param_kind_type,
    trait_args_by_name,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.rust_type_params import (
    type_param_base_key_args,
    type_param_names,
)
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryIndexedLaneExtent,
    MemoryPayloadExtent,
)
from tslc.catalog.preconditions import (
    PreconditionCheckPrimitive,
    PreconditionKind,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.lower.lowerer import LoweredSpecialization, varying_positions

PRECONDITION_METHOD = "__tsl_precondition_error"
CHECKED_MEMORY_EXTENT_METHOD = "__tsl_checked_memory_extent"
CHECKED_MEMORY_ALIGNMENT_METHOD = "__tsl_checked_memory_alignment"


def trait_precondition_condition(
    specializations: tuple[LoweredSpecialization, ...],
) -> CheckedConditionPlan | None:
    return applicable_checked_condition(
        specializations,
        PreconditionKind.ACTIVE_DIVISOR_NONZERO,
    )


def _precondition_method_parameters(
    spec: LoweredSpecialization,
    condition: CheckedConditionPlan,
    *,
    owner: str,
    arguments: bool = False,
) -> str:
    indexes = {condition.parameter_index}
    if condition.mask_parameter_index is not None:
        indexes.add(condition.mask_parameter_index)
    parts = []
    for index, (name, kind) in enumerate(zip(spec.param_names, spec.param_kinds)):
        if index not in indexes:
            continue
        parts.append(
            f"&{name}" if arguments else f"{name}: &{param_kind_type(kind, owner)}"
        )
    return ", ".join(parts)


def trait_precondition_declaration(
    spec: LoweredSpecialization,
    condition: CheckedConditionPlan | None,
) -> str:
    if condition is None:
        return ""
    params = _precondition_method_parameters(spec, condition, owner="Self")
    return f"    fn {PRECONDITION_METHOD}({params}) -> Option<PreconditionError>;\n"


def impl_precondition_method(
    spec: LoweredSpecialization,
    condition: CheckedConditionPlan | None,
) -> str:
    if condition is None:
        return ""
    params = _precondition_method_parameters(spec, condition, owner="Self")
    info = SCALAR_TYPE_INFOS.get(spec.type_tag)
    if info is None:
        raise ValueError(f"checked precondition has unknown type {spec.type_tag!r}")
    if info.floating:
        body = "None"
    else:
        required = {
            PreconditionCheckPrimitive.ZERO_VECTOR,
            PreconditionCheckPrimitive.EQUAL,
            PreconditionCheckPrimitive.MASK_POPULATION_COUNT,
        }
        if not required.issubset(condition.check_primitives):
            raise ValueError("zero-divisor check plan is missing support primitives")
        zero = rust_raw_identifier(PreconditionCheckPrimitive.ZERO_VECTOR.value)
        equal = rust_raw_identifier(PreconditionCheckPrimitive.EQUAL.value)
        population = rust_raw_identifier(
            PreconditionCheckPrimitive.MASK_POPULATION_COUNT.value
        )
        lines = [
            f"let zero_divisors = {equal}::<Self>(",
            f"    *{condition.parameter_name}, {zero}::<Self>());",
        ]
        checked_mask = "zero_divisors"
        if condition.mask_parameter_name is not None:
            if PreconditionCheckPrimitive.MASK_AND not in condition.check_primitives:
                raise ValueError("masked zero-divisor check has no mask-and primitive")
            mask_and = rust_raw_identifier(PreconditionCheckPrimitive.MASK_AND.value)
            lines.extend(
                (
                    f"let active_zero_divisors = {mask_and}::<Self>(",
                    f"    *{condition.mask_parameter_name}, zero_divisors);",
                )
            )
            checked_mask = "active_zero_divisors"
        lines.extend(
            (
                f"if {population}::<Self>({checked_mask}) != 0 {{",
                f"    Some({rust_precondition_error(condition.error)})",
                "} else {",
                "    None",
                "}",
            )
        )
        body = "\n".join(lines)
    return (
        "    #[inline]\n"
        "    #[allow(unused_variables)]\n"
        f"    fn {PRECONDITION_METHOD}({params}) -> Option<PreconditionError> {{\n"
        f"{indent(body, 8)}\n"
        "    }\n"
    )


def forwarded_precondition_method(
    spec: LoweredSpecialization,
    selected_trait_name: str,
    condition: CheckedConditionPlan | None,
) -> str:
    if condition is None:
        return ""
    params = _precondition_method_parameters(spec, condition, owner="Self")
    args = _precondition_method_parameters(
        spec, condition, owner="Self", arguments=True
    )
    return (
        "    #[inline(always)]\n"
        f"    fn {PRECONDITION_METHOD}({params}) -> Option<PreconditionError> {{\n"
        f"        <Self as {selected_trait_name}>::{PRECONDITION_METHOD}({args})\n"
        "    }\n"
    )


def _checked_memory_extent(
    condition: CheckedConditionPlan,
    owner: str,
    *,
    target_owner: str | None = None,
) -> str:
    payload_extents = condition.memory_payload_extents
    if payload_extents == (MemoryPayloadExtent.SCALAR,):
        return "1"
    if payload_extents == (MemoryPayloadExtent.VECTOR,):
        return f"{owner}::lane_count()"
    if payload_extents == (MemoryPayloadExtent.TARGET_VECTOR,):
        if target_owner is None:
            raise ValueError("target-vector checked memory requires a target owner")
        return f"{target_owner}::lane_count()"
    raise ValueError(
        "non-overloaded Rust checked memory API requires one static payload extent"
    )


def _checked_memory_alignment(
    condition: CheckedConditionPlan,
    owner: str,
) -> tuple[str, str]:
    payload_extents = condition.memory_payload_extents
    if payload_extents in {
        (MemoryPayloadExtent.SCALAR,),
        (MemoryPayloadExtent.TARGET_VECTOR,),
    }:
        alignment = f"core::mem::align_of::<{owner}::BaseType>()"
    elif payload_extents in {
        (MemoryPayloadExtent.VECTOR,),
        (MemoryPayloadExtent.ACTIVE_LANES,),
    }:
        alignment = f"{owner}::ALIGN"
    else:
        raise ValueError(
            "non-overloaded Rust checked memory API requires one payload extent"
        )
    axis = (
        None
        if condition.memory_alignment_axis_name is None
        else axis_name(condition.memory_alignment_axis_name)
    )
    if axis is None:
        raise ValueError("Rust checked alignment condition has no alignment axis")
    return alignment, axis


def overloaded_memory_trait_members(
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specializations)
    if plan is None or not any(
        condition.memory_access is not None for condition in plan.conditions
    ):
        return ""
    return (
        "    #[doc(hidden)]\n"
        f"    fn {CHECKED_MEMORY_EXTENT_METHOD}() -> usize;\n"
        "    #[doc(hidden)]\n"
        f"    fn {CHECKED_MEMORY_ALIGNMENT_METHOD}() -> usize;\n"
    )


def overloaded_memory_impl_members(
    specialization: LoweredSpecialization,
    vector_type: str,
) -> str:
    plan = applicable_checked_api_plan((specialization,))
    if plan is None or not any(
        condition.memory_access is not None for condition in plan.conditions
    ):
        return ""
    memory = specialization.primitive_semantics.memory
    if memory is None:
        raise ValueError("checked Rust memory overload has no memory contract")
    if memory.payload_extent is MemoryPayloadExtent.SCALAR:
        extent = "1"
        alignment = "core::mem::align_of::<Self>()"
    else:
        extent = f"<{vector_type} as SimdVector>::lane_count()"
        alignment = f"<{vector_type} as SimdVector>::ALIGN"
    return (
        "    #[inline]\n"
        f"    fn {CHECKED_MEMORY_EXTENT_METHOD}() -> usize {{ {extent} }}\n"
        "    #[inline]\n"
        f"    fn {CHECKED_MEMORY_ALIGNMENT_METHOD}() -> usize {{ {alignment} }}\n"
    )


def render_overloaded_checked_wrapper(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specs)
    if plan is None:
        return ""
    memory = checked_memory_condition(plan.conditions)
    if memory is None:
        raise ValueError("checked Rust overload has no supported memory plan")
    shape = specs[0]
    varying = varying_positions(specs)
    if len(varying) != 1:
        raise ValueError("checked Rust overload requires one varying parameter")
    varying_index = varying[0]
    memory_index, memory_name, memory_access, alignment_axis = (
        memory.parameter_index,
        memory.parameter_name,
        memory.memory_access,
        memory.memory_alignment_axis_name,
    )
    if memory_access is not MemoryAccess.WRITE:
        raise ValueError(
            "checked Rust memory overload currently requires writable memory"
        )
    if alignment_axis is None:
        raise ValueError("checked Rust memory overload has no alignment axis")
    arg_trait = (
        f"{PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
    )
    axis_args = "".join(f", {axis_name(key)}" for key, _ in shape.axis)
    generic_args = "".join(
        f", {name}" for name, _typ, _default in shape.generic_params
    )
    fixed_arguments = tuple(
        (f"{name}.as_mut_ptr()" if index == memory_index else name)
        for index, name in enumerate(shape.param_names)
        if index != varying_index
    )
    trait_application = f"<V as {arg_trait}<S{axis_args}{generic_args}>>"
    call = (
        f"unsafe {{ {trait_application}::apply("
        f"{shape.param_names[varying_index]}"
        f"{''.join(f', {argument}' for argument in fixed_arguments)}) }}"
    )
    checks: list[str] = []
    for condition in plan.conditions:
        error = rust_precondition_error(condition.error)
        if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
            checks.extend(
                (
                    f"    if {memory_name}.len() < "
                    f"{trait_application}::{CHECKED_MEMORY_EXTENT_METHOD}() {{",
                    f"        return Err({error});",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
            checks.extend(
                (
                    f"    if {axis_name(alignment_axis)} && "
                    f"!({memory_name}.as_ptr() as usize).is_multiple_of("
                    f"{trait_application}::{CHECKED_MEMORY_ALIGNMENT_METHOD}()) {{",
                    f"        return Err({error});",
                    "    }",
                )
            )
            continue
        raise ValueError(
            f"unsupported checked Rust overload condition {condition.kind.value!r}"
        )
    success = (
        f"    {call};\n    Ok(())"
        if shape.result_kind == "void"
        else f"    Ok({call})"
    )
    body = "\n".join((*checks, success))
    doc = rust_doc(
        shape,
        context="Rust checked wrapper",
        concrete=False,
        checked_conditions=plan.conditions,
        specializations=specs,
    )
    declaration = rust_overloaded_wrapper_declaration(
        primitive_name,
        specs,
        checked=True,
        caller_unsafe=False,
        reachability=("profile",),
    )
    assert declaration is not None
    return (
        (f"{doc}\n" if doc else "")
        + declaration.render_attributes()
        + "\n"
        + declaration.render_definition_head()
        + "\n"
        f"{body}\n"
        "}"
    )


def render_checked_wrapper(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return ""
    shape = specializations[0]
    public_trait_args = trait_args_by_name(shape)
    trait_args = list(public_trait_args)
    target_owner: str | None = shape.result_vector_param
    if shape.target is not None:
        trait_args = ["T", *trait_args]
        public_trait_args = ["T", *public_trait_args]
        target_owner = "T"
    if shape.type_params:
        type_names = type_param_names(shape)
        trait_args = [
            *type_names,
            *type_param_base_key_args(shape, mode="projection"),
            *trait_args,
        ]
        public_trait_args = [*type_names, *public_trait_args]
    rendered_trait_args = f"<{', '.join(trait_args)}>" if trait_args else ""
    vector_bound = (
        f"{PRIMITIVE_TRAIT_PREFIX}"
        f"{rust_primitive_trait_name(primitive_name)}{rendered_trait_args}"
    )
    doc = rust_doc(
        shape,
        context="Rust checked wrapper",
        concrete=False,
        checked_conditions=plan.conditions,
    )
    call = (
        f"unsafe {{ {rust_raw_identifier(primitive_name)}"
        f"::<{', '.join(('S', *public_trait_args))}>"
        f"({checked_runtime_names(shape, plan)}) }}"
    )
    checks: list[str] = []
    for condition in plan.conditions:
        if condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
            checks.extend(
                (
                    f"    if {condition.parameter_name} >= S::lane_count() {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.EQUAL_LANE_COUNT:
            if target_owner is None:
                raise ValueError("Rust equal-lane-count check has no target vector type")
            checks.extend(
                (
                    f"    if S::lane_count() != {target_owner}::lane_count() {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
            args = _precondition_method_parameters(
                shape, condition, owner="S", arguments=True
            )
            checks.extend(
                (
                    f"    if let Some(error) = <S as {vector_bound}>::"
                    f"{PRECONDITION_METHOD}({args}) {{",
                    "        return Err(error);",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
            extent = _checked_memory_extent(
                condition, "S", target_owner=target_owner
            )
            checks.extend(
                (
                    f"    if {condition.parameter_name}.len() < {extent} {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
            alignment, axis = _checked_memory_alignment(condition, "S")
            active_guard = ""
            if condition.memory_addressing is MemoryAddressing.COMPACTED:
                if condition.mask_parameter_name is None:
                    raise ValueError(
                        "Rust checked compacted alignment has no mask binding"
                    )
                active_guard = (
                    f"(0..S::lane_count()).any(|__tsl_lane| "
                    f"S::mask_lane_test({condition.mask_parameter_name}, "
                    "__tsl_lane)) && "
                )
            checks.extend(
                (
                    f"    if {axis} && {active_guard}!({condition.parameter_name}.as_ptr() as usize)"
                    f".is_multiple_of({alignment}) {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            if (
                condition.index_parameter_name is None
                or condition.scale_parameter_name is None
                or condition.memory_indexed_lane_extent is None
            ):
                raise ValueError("Rust checked indexed memory plan is incomplete")
            if (
                PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
                not in condition.check_primitives
            ):
                raise ValueError(
                    "indexed-memory check plan has no lane-extraction primitive"
                )
            if len(shape.type_params) != 1:
                raise ValueError(
                    "Rust checked indexed memory requires exactly one index vector type"
                )
            index_owner = shape.type_params[0].name
            if (
                condition.memory_indexed_lane_extent
                is MemoryIndexedLaneExtent.VECTOR
            ):
                invalid_lane_extent = f"{index_owner}::lane_count() < S::lane_count()"
                accessed_lanes = "S::lane_count()"
            elif (
                condition.memory_indexed_lane_extent
                is MemoryIndexedLaneExtent.INDEX_VECTOR
            ):
                invalid_lane_extent = f"{index_owner}::lane_count() > S::lane_count()"
                accessed_lanes = f"{index_owner}::lane_count()"
            else:  # pragma: no cover - closed enum, guarded above
                raise AssertionError("unknown indexed memory lane extent")
            active = (
                "true"
                if condition.mask_parameter_name is None
                else f"S::mask_lane_test({condition.mask_parameter_name}, __tsl_lane)"
            )
            checks.extend(
                (
                    f"    if {invalid_lane_extent} {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                    f"    for __tsl_lane in 0..{accessed_lanes} {{",
                    f"        if {active} {{",
                    "            let __tsl_index = unsafe { "
                    f"extract_value_at::<{index_owner}>("
                    f"{condition.index_parameter_name}, __tsl_lane) }};",
                    "            if let Some(error) = "
                    "indexed_memory_address_error::<_, S::BaseType>(",
                    "                __tsl_index, "
                    f"{condition.scale_parameter_name}, "
                    f"{condition.parameter_name}.len(),",
                    "            ) {",
                    "                return Err(error);",
                    "            }",
                    "        }",
                    "    }",
                )
            )
            continue
        if condition.kind is PreconditionKind.COMPACTED_MEMORY_EXTENT:
            if condition.mask_parameter_name is None:
                raise ValueError("Rust checked compacted memory plan has no mask")
            if (
                PreconditionCheckPrimitive.MASK_POPULATION_COUNT
                not in condition.check_primitives
            ):
                raise ValueError(
                    "compacted-memory check plan has no mask population primitive"
                )
            checks.extend(
                (
                    "    let mut __tsl_required = 0usize;",
                    "    for __tsl_lane in 0..S::lane_count() {",
                    f"        if S::mask_lane_test({condition.mask_parameter_name}, __tsl_lane) {{",
                    "            __tsl_required += 1;",
                    "        }",
                    "    }",
                    f"    if {condition.parameter_name}.len() < __tsl_required {{",
                    f"        return Err({rust_precondition_error(condition.error)});",
                    "    }",
                )
            )
            continue
        raise ValueError(
            f"unsupported Rust checked condition {condition.kind.value!r}"
        )
    success = (
        f"    {call};\n    Ok(())"
        if shape.result_kind == "void"
        else f"    Ok({call})"
    )
    body = "\n".join((*checks, success))
    declaration = rust_checked_wrapper_declaration(
        primitive_name,
        specializations,
        reachability=("profile",),
    )
    assert declaration is not None
    return (
        (f"{doc}\n" if doc else "")
        + declaration.render_attributes()
        + "\n"
        + declaration.render_definition_head()
        + "\n"
        f"{body}\n"
        "}"
    )


__all__ = (
    "forwarded_precondition_method",
    "impl_precondition_method",
    "overloaded_memory_impl_members",
    "overloaded_memory_trait_members",
    "render_checked_wrapper",
    "render_overloaded_checked_wrapper",
    "trait_precondition_condition",
    "trait_precondition_declaration",
)
