"""Translate typed checked conditions for the ordinary Rust facade."""

from __future__ import annotations

from tslc.backend.checked_api import CheckedConditionPlan, checked_memory_condition
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.rust_api_arms import RustComprehensivePrivateImplementationArm
from tslc.backend.rust_api_model import RustComprehensiveMethod, RustFacadeParameter
from tslc.backend.rust_api_kinds import RustFacadeParameterPlacement
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.memory import MemoryAccess, MemoryAddressing, MemoryPayloadExtent
from tslc.catalog.preconditions import PreconditionErrorKind, PreconditionKind


def rust_checked_conditions_for_type(
    conditions: tuple[CheckedConditionPlan, ...],
    type_tag: str,
) -> tuple[CheckedConditionPlan, ...]:
    return tuple(
        condition
        for condition in conditions
        if type_tag in condition.applicable_type_tags
    )


def rust_checked_error_names(
    errors: tuple[PreconditionErrorKind, ...],
) -> str:
    return ", ".join(
        f"`{rust_precondition_error(error).removeprefix('crate::')}`"
        for error in errors
    )


def rust_checked_guards(
    method: RustComprehensiveMethod,
    conditions: tuple[CheckedConditionPlan, ...],
    element: str,
    lanes: str,
    *,
    trait_name: str,
    identity_const_names: tuple[str, ...],
    indent: str,
) -> tuple[str, ...]:
    guards: list[str] = []
    for condition_index, condition in enumerate(conditions):
        error = rust_precondition_error(
            condition.error, prefix="crate::PreconditionError::"
        )
        if condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
            parameter = _checked_parameter_expression(
                method, condition.parameter_name
            )
            guards.append(
                f"{indent}if {parameter} >= {lanes} {{"
                f" return Err({error}); }}"
            )
            continue
        if condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
            divisor = _checked_parameter_expression(
                method, condition.parameter_name
            )
            divisor_lanes = f"__tsl_checked_divisors_{condition_index}"
            guards.append(f"{indent}let {divisor_lanes} = {divisor}.to_array();")
            if condition.mask_parameter_name is not None:
                mask = _checked_parameter_expression(
                    method, condition.mask_parameter_name
                )
                active_lanes = f"__tsl_checked_active_{condition_index}"
                guards.append(f"{indent}let {active_lanes} = {mask}.to_array();")
                guards.extend(
                    (
                        f"{indent}if {divisor_lanes}.into_iter().enumerate().any(",
                        f"{indent}    |(lane, value)| {active_lanes}[lane] "
                        "&& value == 0,",
                        f"{indent}) {{ return Err({error}); }}",
                    )
                )
            else:
                guards.extend(
                    (
                        f"{indent}if {divisor_lanes}.into_iter().any(",
                        f"{indent}    |value| value == 0,",
                        f"{indent}) {{ return Err({error}); }}",
                    )
                )
            continue
        if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
            memory = _checked_parameter_expression(
                method, condition.parameter_name
            )
            required_extent = _checked_memory_extent(condition, lanes)
            invalid_extent = (
                f"{memory}.is_empty()"
                if required_extent == "1"
                else f"{memory}.len() < {required_extent}"
            )
            guards.append(
                f"{indent}if {invalid_extent} {{"
                f" return Err({error}); }}"
            )
            continue
        if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
            memory = _checked_parameter_expression(
                method, condition.parameter_name
            )
            alignment_parameter = next(
                (
                    parameter.public_name
                    for parameter in method.const_parameters
                    if parameter.source_name
                    == condition.memory_alignment_axis_name
                ),
                None,
            )
            if alignment_parameter is None:
                raise ValueError(
                    "checked Rust facade memory alignment axis is unresolved"
                )
            identity_arguments = "".join(
                f", {name}" for name in identity_const_names
            )
            active_guard = ""
            if condition.memory_addressing is MemoryAddressing.COMPACTED:
                if condition.mask_parameter_name is None:
                    raise ValueError(
                        "checked Rust facade compacted alignment has no mask"
                    )
                mask = _checked_parameter_expression(
                    method, condition.mask_parameter_name
                )
                active_guard = (
                    f"{mask}.to_array().into_iter().any(|active| active) && "
                )
            guards.append(
                f"{indent}if {alignment_parameter} && "
                f"{active_guard}!({memory}.as_ptr() as usize).is_multiple_of("
                f"<{element} as private::{trait_name}<{lanes}"
                f"{identity_arguments}"
                ">>::__tsl_checked_memory_alignment()) {"
                f" return Err({error}); }}"
            )
            continue
        if condition.kind is PreconditionKind.COMPACTED_MEMORY_EXTENT:
            if condition.mask_parameter_name is None:
                raise ValueError("checked Rust facade compacted memory has no mask")
            memory = _checked_parameter_expression(
                method, condition.parameter_name
            )
            mask = _checked_parameter_expression(
                method, condition.mask_parameter_name
            )
            active_lanes = f"__tsl_checked_active_{condition_index}"
            required = f"__tsl_checked_required_{condition_index}"
            guards.extend(
                (
                    f"{indent}let {active_lanes} = {mask}.to_array();",
                    f"{indent}let {required} = "
                    f"{active_lanes}.into_iter().filter(|active| *active).count();",
                    f"{indent}if {memory}.len() < {required} {{"
                    f" return Err({error}); }}",
                )
            )
            continue
        if condition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            raise ValueError(
                "indexed-memory checked facades require an admitted index-vector "
                "public type"
            )
        raise ValueError(f"unsupported Rust facade check {condition.kind.value!r}")
    return tuple(guards)


def rust_checked_memory_alignment_condition(
    conditions: tuple[CheckedConditionPlan, ...],
) -> CheckedConditionPlan | None:
    return next(
        (
            condition
            for condition in conditions
            if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT
        ),
        None,
    )


def rust_checked_memory_alignment_expression(
    condition: CheckedConditionPlan,
    arm: RustComprehensivePrivateImplementationArm,
) -> str:
    if condition.memory_payload_extents == (MemoryPayloadExtent.SCALAR,):
        return f"core::mem::align_of::<{arm.source_shape.base_spelling}>()"
    if condition.memory_payload_extents in {
        (MemoryPayloadExtent.VECTOR,),
        (MemoryPayloadExtent.ACTIVE_LANES,),
    }:
        return (
            f"<{arm.source_representation.vector_descriptor} "
            "as crate::tsl_core::SimdVector>::ALIGN"
        )
    raise ValueError("checked Rust facade requires one memory payload extent")


def rust_checked_public_call_argument(
    parameter: RustFacadeParameter,
    conditions: tuple[CheckedConditionPlan, ...],
    expression: str,
) -> str | None:
    memory = checked_memory_condition(conditions)
    if memory is None or parameter.source_name != memory.parameter_name:
        return None
    if memory.memory_access is MemoryAccess.READ:
        return f"{expression}.as_ptr()"
    if memory.memory_access is MemoryAccess.WRITE:
        return f"{expression}.as_mut_ptr()"
    raise ValueError("checked Rust facade memory access is unresolved")


def rust_checked_public_parameter_type(
    parameter: RustFacadeParameter,
    conditions: tuple[CheckedConditionPlan, ...],
    element: str,
) -> str | None:
    memory = checked_memory_condition(conditions)
    if memory is None or parameter.source_name != memory.parameter_name:
        return None
    if memory.memory_access is MemoryAccess.READ:
        return f"&[{element}]"
    if memory.memory_access is MemoryAccess.WRITE:
        return f"&mut [{element}]"
    raise ValueError("checked Rust facade memory access is unresolved")


def _checked_memory_extent(
    condition: CheckedConditionPlan,
    lanes: str,
) -> str:
    if condition.memory_payload_extents == (MemoryPayloadExtent.SCALAR,):
        return "1"
    if condition.memory_payload_extents == (MemoryPayloadExtent.VECTOR,):
        return lanes
    raise ValueError("checked Rust facade requires one memory payload extent")


def _checked_parameter_expression(
    method: RustComprehensiveMethod,
    source_name: str,
) -> str:
    parameter = next(
        (item for item in method.parameters if item.source_name == source_name),
        None,
    )
    if parameter is None:
        raise ValueError(f"checked facade parameter {source_name!r} is unresolved")
    if parameter.placement is RustFacadeParameterPlacement.RECEIVER:
        return "self"
    return _identifier(parameter.public_name)


def _identifier(name: str) -> str:
    if name in {"self", "Self", "crate", "super"}:
        return f"{name.lower()}_value"
    return rust_raw_identifier(name)


__all__ = (
    "rust_checked_conditions_for_type",
    "rust_checked_error_names",
    "rust_checked_guards",
    "rust_checked_memory_alignment_condition",
    "rust_checked_memory_alignment_expression",
    "rust_checked_public_call_argument",
    "rust_checked_public_parameter_type",
)
