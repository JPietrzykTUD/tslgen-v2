"""Render-independent checked-API planning from lowered preconditions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.arithmetic import (
    ArithmeticNumericDomain,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
)
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PreconditionHazard,
    PreconditionKind,
    PreconditionCheckPrimitive,
    precondition_applies_to_type,
)
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryAlignment,
    MemoryIndexedLaneExtent,
    MemoryPayloadExtent,
)
from tslc.catalog.semantics import OperandBinding, OperandRole
from tslc.lower.lowerer import LoweredSpecialization


# These are the narrow implementation-mechanism labels observed on the
# reviewed memory families. ``value_reinterpretation`` and ``unsafe_callee``
# are included because the current lowerer adds them as internal-only effects;
# neither label itself declares a new public caller obligation.
# Labels such as ``unchecked_index`` and ``unsafe_operation`` are deliberately
# not accepted here: an internal framing label is not proof of a public caller
# obligation. Typed call-precondition dispositions and transitive closure own
# that proof independently, and checked admission fails on any unresolved gap.
_RANGE_COMPATIBLE_IMPLEMENTATION_REASONS = frozenset(
    {
        "compiler_builtin",
        "intrinsic",
        "raw_memory",
        "unsafe_callee",
        "value_reinterpretation",
    }
)
_RANGE_DISCHARGED_CALLER_REASON = "raw_pointer"


@dataclass(frozen=True, slots=True)
class CheckedConditionPlan:
    kind: PreconditionKind
    description: str
    unchecked_consequence: str
    error: PreconditionErrorKind
    additional_errors: tuple[PreconditionErrorKind, ...]
    parameter_name: str
    parameter_index: int
    applicable_type_tags: tuple[str, ...]
    numeric_domain: ArithmeticNumericDomain | None = None
    check_primitives: tuple[PreconditionCheckPrimitive, ...] = ()
    mask_parameter_name: str | None = None
    mask_parameter_index: int | None = None
    memory_access: MemoryAccess | None = None
    memory_addressing: MemoryAddressing | None = None
    memory_indexed_lane_extent: MemoryIndexedLaneExtent | None = None
    memory_payload_extents: tuple[MemoryPayloadExtent, ...] = ()
    memory_alignment_axis_name: str | None = None
    index_parameter_name: str | None = None
    scale_parameter_name: str | None = None

    @property
    def errors(self) -> tuple[PreconditionErrorKind, ...]:
        return (self.error, *self.additional_errors)

    def __post_init__(self) -> None:
        if not self.description.strip() or not self.unchecked_consequence.strip():
            raise ValueError("checked conditions require complete public prose")
        if self.error in self.additional_errors or len(set(self.errors)) != len(
            self.errors
        ):
            raise ValueError("checked condition errors must be unique")
        is_memory = PRECONDITION_DESCRIPTORS[self.kind].binds_memory_operand
        has_any_memory = (
            self.memory_access is not None
            or self.memory_addressing is not None
            or self.memory_indexed_lane_extent is not None
            or bool(self.memory_payload_extents)
            or self.memory_alignment_axis_name is not None
        )
        has_complete_memory = (
            self.memory_access is not None
            and self.memory_addressing is not None
            and bool(self.memory_payload_extents)
        )
        if has_any_memory and not has_complete_memory:
            raise ValueError(
                "checked conditions cannot retain partial typed memory facts"
            )
        if is_memory != has_complete_memory:
            raise ValueError(
                "checked memory conditions require complete typed memory facts"
            )
        if (self.memory_addressing is MemoryAddressing.INDEXED) != (
            self.memory_indexed_lane_extent is not None
        ):
            raise ValueError(
                "checked indexed-memory conditions require one lane extent"
            )
        if self.memory_payload_extents != tuple(
            sorted(set(self.memory_payload_extents), key=lambda item: item.value)
        ):
            raise ValueError(
                "checked memory payload extents must be unique and sorted"
            )
        if self.applicable_type_tags != tuple(
            sorted(set(self.applicable_type_tags))
        ):
            raise ValueError(
                "checked condition applicable type tags must be unique and sorted"
            )
        if (
            self.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT
            and self.memory_alignment_axis_name is None
        ):
            raise ValueError("checked alignment conditions require an alignment axis")
        if (self.mask_parameter_name is None) != (
            self.mask_parameter_index is None
        ):
            raise ValueError("checked mask bindings must be complete")
        if (
            self.memory_addressing is MemoryAddressing.COMPACTED
            and self.mask_parameter_name is None
        ):
            raise ValueError(
                "checked compacted-memory conditions require a mask binding"
            )
        has_any_indexed_binding = (
            self.index_parameter_name is not None
            or self.scale_parameter_name is not None
        )
        has_complete_indexed_bindings = (
            self.index_parameter_name is not None
            and self.scale_parameter_name is not None
        )
        if has_any_indexed_binding and not has_complete_indexed_bindings:
            raise ValueError("checked indexed bindings must be complete")
        if (
            self.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID
        ) != has_complete_indexed_bindings:
            raise ValueError(
                "checked indexed-address conditions require index and scale bindings"
            )


@dataclass(frozen=True, slots=True)
class CheckedApiPlan:
    conditions: tuple[CheckedConditionPlan, ...]

    def __post_init__(self) -> None:
        if not self.conditions:
            raise ValueError("checked API plans require at least one condition")
        kinds = tuple(condition.kind for condition in self.conditions)
        if len(set(kinds)) != len(kinds):
            raise ValueError("checked API plans require unique condition kinds")


def checked_memory_condition(
    conditions: tuple[CheckedConditionPlan, ...],
) -> CheckedConditionPlan | None:
    """Return the one shared memory binding represented by checked conditions."""

    memory_conditions = tuple(
        condition for condition in conditions if condition.memory_access is not None
    )
    if not memory_conditions:
        return None
    identities = {
        (
            condition.parameter_name,
            condition.parameter_index,
            condition.memory_access,
            condition.memory_addressing,
            condition.memory_indexed_lane_extent,
            condition.memory_payload_extents,
            condition.memory_alignment_axis_name,
            condition.mask_parameter_name,
            condition.mask_parameter_index,
            condition.index_parameter_name,
            condition.scale_parameter_name,
        )
        for condition in memory_conditions
    }
    if len(identities) != 1:
        raise ValueError("checked memory conditions disagree on their binding")
    return memory_conditions[0]


def checked_api_plan(
    specializations: tuple[LoweredSpecialization, ...],
) -> CheckedApiPlan | None:
    """Plan a checked twin only when every catastrophic condition is checkable."""

    if not specializations:
        return None
    if any(
        spec.unavailable_checked_dependency_origins
        for spec in specializations
    ):
        return None
    if any(spec.unresolved_call_preconditions for spec in specializations):
        return None
    first = specializations[0]
    declared = first.primitive_semantics.preconditions
    if not declared:
        return None
    semantic_keys = tuple(
        (
            item.kind,
            tuple(
                (
                    "arithmetic"
                    if isinstance(binding, ArithmeticOperandBinding)
                    else "operation",
                    binding.role.value,
                    binding.parameter_index,
                    binding.parameter_name,
                )
                for binding in item.operand_bindings
            ),
        )
        for item in declared
    )
    for spec in specializations[1:]:
        candidate = tuple(
            (
                item.kind,
                tuple(
                    (
                        "arithmetic"
                        if isinstance(binding, ArithmeticOperandBinding)
                        else "operation",
                        binding.role.value,
                        binding.parameter_index,
                        binding.parameter_name,
                    )
                    for binding in item.operand_bindings
                ),
            )
            for item in spec.primitive_semantics.preconditions
        )
        if candidate != semantic_keys:
            raise ValueError("checked API requires consistent lowered preconditions")
    conditions: list[CheckedConditionPlan] = []
    for precondition in declared:
        descriptor = PRECONDITION_DESCRIPTORS[precondition.kind]
        if descriptor.hazard is not PreconditionHazard.CATASTROPHIC:
            continue
        mask_name: str | None = None
        mask_index: int | None = None
        check_primitives = descriptor.check_primitives
        if first.mask_policy is not None and descriptor.masked_check_primitives:
            mask_indexes = tuple(
                index for index, kind in enumerate(first.param_kinds) if kind == "m"
            )
            if len(mask_indexes) != 1:
                raise ValueError("masked checked API requires one mask parameter")
            mask_index = mask_indexes[0]
            mask_name = first.param_names[mask_index]
            check_primitives += descriptor.masked_check_primitives
        binding: OperandBinding | ArithmeticOperandBinding | None
        if precondition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
            binding = precondition.binding(OperandRole.INDEX)
            if binding is None:
                raise ValueError("lane-index precondition has no resolved index binding")
        elif precondition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
            binding = precondition.arithmetic_binding(ArithmeticOperandRole.DIVISOR)
            if binding is None:
                raise ValueError("divisor precondition has no resolved divisor binding")
        elif precondition.kind is PreconditionKind.EQUAL_LANE_COUNT:
            binding = precondition.binding(OperandRole.PRIMARY)
            if binding is None:
                raise ValueError(
                    "equal-lane-count precondition has no resolved primary binding"
                )
            if first.target is None and first.result_vector_param is None:
                raise ValueError(
                    "equal-lane-count precondition has no resolved target vector"
                )
        elif descriptor.binds_memory_operand:
            memory = first.primitive_semantics.memory
            if memory is None:
                raise ValueError("memory precondition has no resolved memory contract")
            memory_role = (
                OperandRole.MEMORY_SOURCE
                if memory.access is MemoryAccess.READ
                else OperandRole.MEMORY_DESTINATION
            )
            binding = precondition.binding(memory_role)
            if binding is None:
                raise ValueError("memory precondition has no resolved memory binding")
        else:
            return None
        memory_access: MemoryAccess | None = None
        memory_addressing: MemoryAddressing | None = None
        memory_indexed_lane_extent: MemoryIndexedLaneExtent | None = None
        memory_payload_extents: tuple[MemoryPayloadExtent, ...] = ()
        memory_alignment_axis_name: str | None = None
        index_parameter_name: str | None = None
        scale_parameter_name: str | None = None
        if descriptor.binds_memory_operand:
            memories = tuple(
                spec.primitive_semantics.memory for spec in specializations
            )
            if any(memory is None for memory in memories):
                raise ValueError("checked memory family has an incomplete memory contract")
            memory_values = tuple(memory for memory in memories if memory is not None)
            access_values = {memory.access for memory in memory_values}
            if len(access_values) != 1:
                raise ValueError("checked memory family disagrees on memory access")
            memory_access = next(iter(access_values))
            addressing_values = {memory.addressing for memory in memory_values}
            if len(addressing_values) != 1:
                raise ValueError("checked memory family disagrees on memory addressing")
            memory_addressing = next(iter(addressing_values))
            indexed_lane_extent_values = {
                memory.indexed_lane_extent for memory in memory_values
            }
            if len(indexed_lane_extent_values) != 1:
                raise ValueError(
                    "checked memory family disagrees on indexed lane extent"
                )
            memory_indexed_lane_extent = next(iter(indexed_lane_extent_values))
            memory_payload_extents = tuple(
                sorted(
                    {memory.payload_extent for memory in memory_values},
                    key=lambda item: item.value,
                )
            )
            alignments = tuple(
                spec.primitive_semantics.memory_alignment
                for spec in specializations
            )
            axis_names = {
                alignment.axis_name
                for alignment in alignments
                if alignment is not None
            }
            if (
                precondition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT
                and len(axis_names) != 1
            ):
                raise ValueError(
                    "checked memory family requires one resolved alignment axis"
                )
            if len(axis_names) > 1:
                raise ValueError(
                    "checked memory family disagrees on its alignment axis"
                )
            memory_alignment_axis_name = next(iter(axis_names), None)
        if precondition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            index_binding = precondition.binding(OperandRole.INDEX)
            scale_binding = precondition.binding(OperandRole.SCALE)
            if index_binding is None or scale_binding is None:
                raise ValueError(
                    "indexed-address precondition has incomplete index/scale bindings"
                )
            index_parameter_name = index_binding.parameter_name
            scale_parameter_name = scale_binding.parameter_name
            operation = first.primitive_semantics.operation
            mask_binding = (
                None
                if operation is None
                else operation.binding(OperandRole.CONTROL_MASK)
            )
            if mask_binding is not None:
                mask_name = mask_binding.parameter_name
                mask_index = mask_binding.parameter_index
        if memory_addressing is MemoryAddressing.COMPACTED:
            mask_binding = precondition.binding(OperandRole.CONTROL_MASK)
            if mask_binding is None:
                operation = first.primitive_semantics.operation
                mask_binding = (
                    None
                    if operation is None
                    else operation.binding(OperandRole.CONTROL_MASK)
                )
            if mask_binding is None:
                raise ValueError(
                    "compacted-memory condition has no resolved mask binding"
                )
            mask_name = mask_binding.parameter_name
            mask_index = mask_binding.parameter_index
        conditions.append(
            CheckedConditionPlan(
                kind=precondition.kind,
                description=descriptor.description,
                unchecked_consequence=descriptor.unchecked_consequence,
                error=descriptor.error,
                additional_errors=descriptor.additional_errors,
                parameter_name=binding.parameter_name,
                parameter_index=binding.parameter_index,
                applicable_type_tags=tuple(
                    sorted(
                        {
                            spec.type_tag
                            for spec in specializations
                            for item in spec.primitive_semantics.preconditions
                            if item.kind is precondition.kind
                            and precondition_applies_to_type(item, spec.type_tag)
                        }
                    )
                ),
                numeric_domain=descriptor.numeric_domain,
                check_primitives=check_primitives,
                mask_parameter_name=mask_name,
                mask_parameter_index=mask_index,
                memory_access=memory_access,
                memory_addressing=memory_addressing,
                memory_indexed_lane_extent=memory_indexed_lane_extent,
                memory_payload_extents=memory_payload_extents,
                memory_alignment_axis_name=memory_alignment_axis_name,
                index_parameter_name=index_parameter_name,
                scale_parameter_name=scale_parameter_name,
            )
        )
    if not conditions:
        return None
    if (
        any(spec.safety.caller_unsafe for spec in specializations)
        and not _has_complete_memory_check(tuple(conditions), specializations)
    ):
        return None
    return CheckedApiPlan(tuple(conditions))


def _has_complete_memory_check(
    conditions: tuple[CheckedConditionPlan, ...],
    specializations: tuple[LoweredSpecialization, ...],
) -> bool:
    """Whether a richer range signature discharges raw-memory caller unsafety."""

    if any(
        not _caller_unsafety_is_range_only(spec)
        for spec in specializations
        if spec.safety.caller_unsafe
    ):
        return False

    try:
        memory_condition = checked_memory_condition(conditions)
    except ValueError:
        return False
    if memory_condition is None:
        return False
    addressing = memory_condition.memory_addressing
    if addressing is None:
        return False
    required = {
        MemoryAddressing.CONTIGUOUS: {
            PreconditionKind.CONTIGUOUS_MEMORY_EXTENT,
        },
        MemoryAddressing.INDEXED: {
            PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID,
        },
        MemoryAddressing.COMPACTED: {
            PreconditionKind.COMPACTED_MEMORY_EXTENT,
        },
    }
    required_kinds = required.get(addressing)
    if required_kinds is None:
        return False
    required_kinds = set(required_kinds)
    if any(
        alignment is not None and alignment.mode is MemoryAlignment.ALIGNED
        for spec in specializations
        for alignment in (spec.primitive_semantics.memory_alignment,)
    ):
        required_kinds.add(PreconditionKind.SELECTED_MEMORY_ALIGNMENT)
    return required_kinds.issubset(
        {
            condition.kind
            for condition in conditions
            if condition.memory_access is not None
        }
    )


def _caller_unsafety_is_range_only(spec: LoweredSpecialization) -> bool:
    """Prove that a range wrapper can discharge every caller obligation.

    Safety reason labels are intentionally open for source authors.  The
    checked API therefore admits only the one caller obligation it knows how
    to discharge and a closed set of implementation-only framing labels.
    Unknown labels and explicit caller obligations fail closed.  The lowerer's
    internal ``unsafe_callee`` framing label is admitted here, but does not prove
    that a callee precondition was forwarded or discharged; that separate typed
    call-edge proof remains a release gate.
    """

    reasons = spec.safety.reasons
    return _RANGE_DISCHARGED_CALLER_REASON in reasons and not (
        reasons
        - _RANGE_COMPATIBLE_IMPLEMENTATION_REASONS
        - {_RANGE_DISCHARGED_CALLER_REASON}
    )


def public_call_requires_unsafe(
    specializations: tuple[LoweredSpecialization, ...],
) -> bool:
    if not specializations:
        return False
    return any(spec.safety.caller_unsafe for spec in specializations) or any(
        PRECONDITION_DESCRIPTORS[precondition.kind].hazard
        is PreconditionHazard.CATASTROPHIC
        and precondition_applies_to_type(precondition, spec.type_tag)
        for spec in specializations
        for precondition in spec.primitive_semantics.preconditions
    )


def applicable_checked_api_plan(
    specializations: tuple[LoweredSpecialization, ...],
) -> CheckedApiPlan | None:
    """Plan conditions that apply to at least one represented concrete type."""

    plan = checked_api_plan(specializations)
    if plan is None:
        return None
    conditions = tuple(
        condition for condition in plan.conditions if condition.applicable_type_tags
    )
    return CheckedApiPlan(conditions) if conditions else None


__all__ = (
    "CheckedApiPlan",
    "CheckedConditionPlan",
    "applicable_checked_api_plan",
    "checked_api_plan",
    "checked_memory_condition",
    "public_call_requires_unsafe",
)
