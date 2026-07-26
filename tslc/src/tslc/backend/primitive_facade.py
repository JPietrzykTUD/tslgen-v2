"""Shared policy for generated dataparallel primitive facades."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryAlignment,
    memory_operation,
)
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


class DataparallelPrimitiveFacadeKind(Enum):
    """The facade shape a backend may print for a lowered primitive."""

    REGISTER_MASK_OR_REDUCTION = "register_mask_or_reduction"
    TARGET_BASE_CONVERSION = "target_base_conversion"
    CONTIGUOUS_MEMORY = "contiguous_memory"


@dataclass(frozen=True, slots=True)
class DataparallelPrimitiveFacade:
    primitive_name: str
    shape: LoweredSpecialization
    kind: DataparallelPrimitiveFacadeKind
    memory_access: MemoryAccess | None = None
    memory_addressing: MemoryAddressing | None = None
    alignment_axis_name: str | None = None
    overload_parameter_positions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        is_memory = self.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
        has_memory_facts = (
            self.memory_access is not None
            and self.memory_addressing is not None
            and self.alignment_axis_name is not None
        )
        if is_memory != has_memory_facts:
            raise ValueError(
                "Contiguous-memory facades require exactly the typed memory facts"
            )
        if (
            self.memory_addressing is not None
            and self.memory_addressing is not MemoryAddressing.CONTIGUOUS
        ):
            raise ValueError("A contiguous-memory facade requires contiguous addressing")
        if not is_memory and self.overload_parameter_positions:
            raise ValueError(
                "Only contiguous-memory facades retain overload dispatch positions"
            )
        if (
            self.memory_access is MemoryAccess.READ
            and self.overload_parameter_positions
        ):
            raise ValueError("Contiguous reads cannot require overload dispatch")
        if (
            self.memory_access is MemoryAccess.WRITE
            and self.overload_parameter_positions not in {(), (1,)}
        ):
            raise ValueError(
                "Contiguous writes can dispatch only their value operand"
            )


@dataclass(frozen=True, slots=True)
class DataparallelPrimitiveFacadeDecision:
    facade: DataparallelPrimitiveFacade | None
    diagnostic_reason: str | None = None
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        populated = sum(
            item is not None
            for item in (
                self.facade,
                self.diagnostic_reason,
                self.exclusion_reason,
            )
        )
        if populated != 1:
            raise ValueError(
                "A dataparallel facade decision requires exactly one outcome"
            )


def classify_dataparallel_primitive_facade(
    primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
) -> DataparallelPrimitiveFacade | None:
    """Classify whether a primitive can expose a policy-based facade.

    This is shared compiler policy: a facade is admitted only for primitive
    signatures whose vector choice can be expressed as `(Policy, T)` without
    backend-specific overload repair.
    """

    return plan_dataparallel_primitive_facade(
        primitive_name, specializations
    ).facade


def plan_dataparallel_primitive_facade(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> DataparallelPrimitiveFacadeDecision:
    """Plan one shared facade without inferring semantics from its name."""

    memory_decision = _memory_facade_decision(primitive_name, specializations)
    if memory_decision is not None:
        return memory_decision
    if not specializations:
        return DataparallelPrimitiveFacadeDecision(
            None, exclusion_reason="primitive has no lowered specializations"
        )
    shape = specializations[0]
    target_base_conversion = _is_target_base_conversion(shape, specializations)
    if not _supports_register_mask_or_reduction_facade(
        shape, target_base_conversion
    ):
        return DataparallelPrimitiveFacadeDecision(
            None, exclusion_reason="signature is not policy-facade compatible"
        )
    if (
        shape.type_params
        or shape.axis
        or shape.immediate is not None
        or shape.generic_params
        or varying_positions(specializations)
    ):
        return DataparallelPrimitiveFacadeDecision(
            None, exclusion_reason="specialization axes are not facade-compatible"
        )
    return DataparallelPrimitiveFacadeDecision(
        DataparallelPrimitiveFacade(
            primitive_name=primitive_name,
            shape=shape,
            kind=(
                DataparallelPrimitiveFacadeKind.TARGET_BASE_CONVERSION
                if target_base_conversion
                else DataparallelPrimitiveFacadeKind.REGISTER_MASK_OR_REDUCTION
            ),
        ),
    )


def contiguous_memory_primitive_facades(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> tuple[
    DataparallelPrimitiveFacade,
    DataparallelPrimitiveFacade,
] | None:
    """Return the unique typed contiguous read/write pair, when available."""

    by_access: dict[MemoryAccess, DataparallelPrimitiveFacade] = {}
    for primitive_name in sorted(by_primitive):
        decision = plan_dataparallel_primitive_facade(
            primitive_name,
            by_primitive[primitive_name],
        )
        if decision.diagnostic_reason is not None:
            raise ValueError(
                "invalid lowered memory facade: "
                f"{primitive_name}: {decision.diagnostic_reason}"
            )
        facade = decision.facade
        if (
            facade is None
            or facade.kind
            is not DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
        ):
            continue
        access = facade.memory_access
        if access is None:
            raise ValueError("contiguous-memory facade has no typed access")
        if access in by_access:
            raise ValueError(
                f"multiple contiguous-memory facades provide {access.value} access"
            )
        by_access[access] = facade
    read = by_access.get(MemoryAccess.READ)
    write = by_access.get(MemoryAccess.WRITE)
    return None if read is None or write is None else (read, write)


__all__ = (
    "DataparallelPrimitiveFacade",
    "DataparallelPrimitiveFacadeDecision",
    "DataparallelPrimitiveFacadeKind",
    "classify_dataparallel_primitive_facade",
    "contiguous_memory_primitive_facades",
    "plan_dataparallel_primitive_facade",
)


def _memory_facade_decision(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> DataparallelPrimitiveFacadeDecision | None:
    if not any(
        spec.primitive_semantics.memory is not None
        or (
            spec.primitive_semantics.operation is not None
            and spec.primitive_semantics.operation.kind
            in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
        )
        for spec in specializations
    ):
        return None

    for spec in specializations:
        issue = _memory_specialization_issue(spec)
        if issue is not None:
            return DataparallelPrimitiveFacadeDecision(
                None, diagnostic_reason=issue
            )

    compatible = tuple(
        spec for spec in specializations if _is_contiguous_memory_facade_shape(spec)
    )
    if not compatible:
        return DataparallelPrimitiveFacadeDecision(
            None,
            exclusion_reason="memory shape is not an unmasked vector load or store",
        )
    access_values = {
        spec.primitive_semantics.memory.access
        for spec in compatible
        if spec.primitive_semantics.memory is not None
    }
    if len(access_values) != 1:
        return DataparallelPrimitiveFacadeDecision(
            None,
            diagnostic_reason="memory facade specializations disagree on access",
        )
    alignment_records = tuple(
        spec.primitive_semantics.memory_alignment for spec in compatible
    )
    if any(record is None for record in alignment_records):
        return DataparallelPrimitiveFacadeDecision(
            None,
            exclusion_reason="memory facade requires an explicit alignment axis",
        )
    axis_names = {
        record.axis_name for record in alignment_records if record is not None
    }
    modes = {
        record.mode for record in alignment_records if record is not None
    }
    if len(axis_names) != 1:
        return DataparallelPrimitiveFacadeDecision(
            None,
            diagnostic_reason="memory facade specializations disagree on alignment axis",
        )
    if modes != {MemoryAlignment.ALIGNED, MemoryAlignment.UNALIGNED}:
        return DataparallelPrimitiveFacadeDecision(
            None,
            exclusion_reason=(
                "memory facade requires aligned and unaligned specializations"
            ),
        )
    shape = min(compatible, key=_specialization_sort_key)
    overload_parameter_positions = varying_positions(specializations)
    memory = shape.primitive_semantics.memory
    alignment = shape.primitive_semantics.memory_alignment
    assert memory is not None
    assert alignment is not None
    if (
        memory.access is MemoryAccess.READ
        and overload_parameter_positions
    ) or (
        memory.access is MemoryAccess.WRITE
        and overload_parameter_positions not in {(), (1,)}
    ):
        return DataparallelPrimitiveFacadeDecision(
            None,
            exclusion_reason="memory overload layout is not facade-compatible",
        )
    return DataparallelPrimitiveFacadeDecision(
        DataparallelPrimitiveFacade(
            primitive_name=primitive_name,
            shape=shape,
            kind=DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY,
            memory_access=memory.access,
            memory_addressing=memory.addressing,
            alignment_axis_name=alignment.axis_name,
            overload_parameter_positions=overload_parameter_positions,
        )
    )


def _memory_specialization_issue(
    spec: LoweredSpecialization,
) -> str | None:
    semantics = spec.primitive_semantics
    operation = semantics.operation
    memory = semantics.memory
    if memory is None:
        return "memory operation is missing its typed memory contract"
    expected_operation = memory_operation(memory.access)
    if operation is None or operation.kind is not expected_operation:
        return (
            f"memory access {memory.access.value!r} disagrees with its "
            "typed operation"
        )
    bindings = operation.operand_bindings
    source_bindings = tuple(
        binding
        for binding in bindings
        if binding.role is OperandRole.MEMORY_SOURCE
    )
    destination_bindings = tuple(
        binding
        for binding in bindings
        if binding.role is OperandRole.MEMORY_DESTINATION
    )
    expected_bindings = (
        source_bindings
        if memory.access is MemoryAccess.READ
        else destination_bindings
    )
    forbidden_bindings = (
        destination_bindings
        if memory.access is MemoryAccess.READ
        else source_bindings
    )
    expected_kind = "cptr" if memory.access is MemoryAccess.READ else "ptr"
    if (
        len(expected_bindings) != 1
        or expected_bindings[0].parameter_kind != expected_kind
        or forbidden_bindings
    ):
        return (
            f"memory access {memory.access.value!r} has inconsistent "
            "memory operand roles"
        )
    alignment = semantics.memory_alignment
    if alignment is not None:
        axis_values = dict(spec.axis)
        expected_value = (
            "true"
            if alignment.mode is MemoryAlignment.ALIGNED
            else "false"
        )
        if axis_values.get(alignment.axis_name) != expected_value:
            return "memory alignment fact disagrees with its specialization axis"
    return None


def _is_contiguous_memory_facade_shape(
    spec: LoweredSpecialization,
) -> bool:
    semantics = spec.primitive_semantics
    memory = semantics.memory
    operation = semantics.operation
    if (
        memory is None
        or memory.addressing is not MemoryAddressing.CONTIGUOUS
        or operation is None
        or spec.target is not None
        or spec.type_params
        or spec.immediate is not None
        or spec.generic_params
        or spec.mask_policy is not None
    ):
        return False
    roles = tuple(
        sorted(
            (
                (binding.role, binding.parameter_index, binding.parameter_kind)
                for binding in operation.operand_bindings
            ),
            key=lambda item: item[1],
        )
    )
    if memory.access is MemoryAccess.READ:
        return (
            operation.kind is PrimitiveOperation.LOAD
            and spec.result_kind == "v"
            and spec.param_kinds == ("cptr",)
            and roles == ((OperandRole.MEMORY_SOURCE, 0, "cptr"),)
        )
    overload = semantics.overload
    return (
        operation.kind is PrimitiveOperation.STORE
        and spec.result_kind == "void"
        and spec.param_kinds == ("ptr", "v")
        and roles
        == (
            (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
            (OperandRole.VALUE, 1, "v"),
        )
        and overload is not None
        and overload.axis == "payload_extent"
        and overload.value == "vector"
        and overload.is_primary_value
    )


def _specialization_sort_key(
    spec: LoweredSpecialization,
) -> tuple[object, ...]:
    return (
        spec.source_primitive_name,
        spec.primitive_name,
        spec.type_tag,
        spec.extension_name,
        spec.axis,
    )


def _is_target_base_conversion(
    shape: LoweredSpecialization, specializations: tuple[LoweredSpecialization, ...]
) -> bool:
    return (
        shape.result_kind == "v"
        and shape.param_kinds == ("v",)
        and shape.target is not None
        and all(
            spec.target is not None
            and spec.target.extension_isa == spec.extension_name
            for spec in specializations
        )
    )


def _supports_register_mask_or_reduction_facade(
    shape: LoweredSpecialization, target_base_conversion: bool
) -> bool:
    return (
        target_base_conversion
        or (
            shape.target is None
            and shape.result_kind == "v"
            and shape.param_kinds in {("v",), ("v", "v")}
        )
        or (
            shape.target is None
            and shape.result_kind == "m"
            and shape.param_kinds in {(), ("v",), ("v", "v"), ("m",), ("m", "m")}
        )
        or (
            shape.target is None
            and shape.result_kind == "s"
            and shape.param_kinds in {("v",), ("m", "v"), ("v", "s")}
        )
        or (
            shape.target is None
            and shape.result_kind == "usize"
            and shape.param_kinds == ("m",)
        )
    )
