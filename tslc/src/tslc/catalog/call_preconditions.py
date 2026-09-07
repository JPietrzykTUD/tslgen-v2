"""Typed proof records for preconditions on generated primitive calls.

Call selectors author only a disposition.  This module resolves that source
claim against promoted primitive contracts; it never interprets target-language
expressions.  Forwarding is admitted only when exact call-argument identities
map the callee's bound operands to the caller's matching root precondition and
the call preserves its typed vector and condition context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from tslc.catalog.arithmetic import ArithmeticOperandBinding
from tslc.catalog.memory import (
    MemoryAddressing,
    MemoryIndexedLaneExtent,
    MemoryPayloadExtent,
)
from tslc.catalog.model import Catalog, Primitive, PrimitiveMaskMode
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionHazard,
    PreconditionKind,
    PrimitivePrecondition,
    precondition_applies_to_type,
)
from tslc.catalog.semantics import OperandBinding, OperandRole
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import SourceSpan


class CallPreconditionDispositionKind(StrEnum):
    """How an implementation accounts for one callee precondition."""

    FORWARD = "forward"
    DISCHARGE = "discharge"


class CallPreconditionObligationStatus(StrEnum):
    """Resolution state retained on a lowered call edge."""

    RESOLVED = "resolved"
    MISSING = "missing"
    INVALID_FORWARD = "invalid_forward"


@dataclass(frozen=True, slots=True)
class CallArgumentBinding:
    """An exact call argument that is one of the caller's parameters."""

    callee_parameter_index: int
    caller_parameter_index: int

    def __post_init__(self) -> None:
        if self.callee_parameter_index < 0 or self.caller_parameter_index < 0:
            raise ValueError("call argument bindings require nonnegative indexes")


@dataclass(frozen=True, slots=True)
class CallPreconditionDisposition:
    """One source-authored forwarding claim or discharge assertion."""

    condition: PreconditionKind
    kind: CallPreconditionDispositionKind
    source: SourceSpan | None = None
    forwarded_root: PreconditionKind | None = None

    def __post_init__(self) -> None:
        expected = (
            self.condition
            if self.kind is CallPreconditionDispositionKind.FORWARD
            else None
        )
        if self.forwarded_root is not expected:
            raise ValueError(
                "forward dispositions require the matching root precondition; "
                "discharges cannot name one"
            )


@dataclass(frozen=True, slots=True)
class CallPreconditionObligation:
    """One applicable catastrophic callee condition and its proof state."""

    callee_condition: PreconditionKind
    disposition: CallPreconditionDisposition | None
    status: CallPreconditionObligationStatus
    source: SourceSpan | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status is CallPreconditionObligationStatus.MISSING:
            if self.disposition is not None:
                raise ValueError("missing call obligations cannot have a disposition")
        elif self.disposition is None:
            raise ValueError("resolved call obligations require a disposition")
        if self.status is CallPreconditionObligationStatus.RESOLVED:
            if self.reason is not None:
                raise ValueError("resolved call obligations cannot retain a failure reason")
        elif not self.reason:
            raise ValueError("unresolved call obligations require a reason")

    @property
    def resolved(self) -> bool:
        return self.status is CallPreconditionObligationStatus.RESOLVED


@dataclass(frozen=True, slots=True)
class CallPreconditionResolution:
    """Resolved obligations plus source dispositions that match no callee fact."""

    obligations: tuple[CallPreconditionObligation, ...]
    stale_dispositions: tuple[CallPreconditionDisposition, ...] = ()

    @property
    def unresolved(self) -> tuple[CallPreconditionObligation, ...]:
        return tuple(item for item in self.obligations if not item.resolved)


@dataclass(frozen=True, slots=True)
class _ConditionOperandIdentity:
    domain: str
    role: str
    parameter_index: int


@dataclass(frozen=True, slots=True)
class _ConditionIdentity:
    """The condition facts that must survive an exact forward."""

    operands: tuple[_ConditionOperandIdentity, ...]
    memory_addressing: MemoryAddressing | None = None
    memory_payload_extent: MemoryPayloadExtent | None = None
    memory_indexed_lane_extent: MemoryIndexedLaneExtent | None = None


def call_precondition_obligation_sort_key(
    obligation: CallPreconditionObligation,
) -> tuple[str, str, str, str, str, str, int, int]:
    disposition = obligation.disposition
    source = obligation.source
    return (
        obligation.callee_condition.value,
        obligation.status.value,
        "" if disposition is None else disposition.kind.value,
        (
            ""
            if disposition is None or disposition.forwarded_root is None
            else disposition.forwarded_root.value
        ),
        obligation.reason or "",
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
        source.column if source is not None else 0,
    )


def call_precondition_candidates(
    catalog: Catalog,
    callee_name: str,
    *,
    mask_policy: PrimitiveMaskMode | None,
    attributes: Mapping[str, str],
    argument_count: int,
) -> tuple[Primitive, ...]:
    """Return declaration candidates selected by typed call-shell facts."""

    candidates: list[Primitive] = []
    for primitive in catalog.primitives_named(callee_name, unmasked=False):
        if primitive.mask_mode is not mask_policy:
            continue
        shape = parse_signature(primitive.signature)
        if shape is None or len(shape.param_kinds) != argument_count:
            continue
        mismatch = False
        for name, value in attributes.items():
            if name == "mask":
                continue
            if name not in primitive.attributes:
                mismatch = True
                break
            declared = primitive.attributes[name]
            if value in {"true", "false"} and declared != value:
                mismatch = True
                break
        if not mismatch:
            candidates.append(primitive)
    return tuple(candidates)


def resolve_call_preconditions(
    caller: Primitive,
    callees: tuple[Primitive, ...],
    dispositions: tuple[CallPreconditionDisposition, ...],
    argument_bindings: tuple[CallArgumentBinding, ...],
    *,
    same_vector: bool,
    type_tag: str | None,
    attributes: Mapping[str, str],
    source: SourceSpan | None,
) -> CallPreconditionResolution:
    """Resolve source dispositions without interpreting raw argument expressions."""

    required: dict[PreconditionKind, list[tuple[Primitive, PrimitivePrecondition]]] = {}
    declared: set[PreconditionKind] = set()
    for callee in callees:
        for condition in callee.preconditions:
            descriptor = PRECONDITION_DESCRIPTORS[condition.kind]
            if descriptor.hazard is not PreconditionHazard.CATASTROPHIC:
                continue
            declared.add(condition.kind)
            if type_tag is not None and not precondition_applies_to_type(
                condition, type_tag
            ):
                continue
            if (
                condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT
                and attributes.get("aligned", "false") == "false"
            ):
                continue
            required.setdefault(condition.kind, []).append((callee, condition))

    by_condition = {item.condition: item for item in dispositions}
    obligations: list[CallPreconditionObligation] = []
    for kind in sorted(required, key=lambda item: item.value):
        disposition = by_condition.get(kind)
        if disposition is None:
            obligations.append(
                CallPreconditionObligation(
                    callee_condition=kind,
                    disposition=None,
                    status=CallPreconditionObligationStatus.MISSING,
                    source=source,
                    reason=f"no forward or discharge disposition for {kind.value!r}",
                )
            )
            continue
        if disposition.kind is CallPreconditionDispositionKind.DISCHARGE:
            obligations.append(
                CallPreconditionObligation(
                    callee_condition=kind,
                    disposition=disposition,
                    status=CallPreconditionObligationStatus.RESOLVED,
                    source=disposition.source or source,
                )
            )
            continue
        reason = _forwarding_error(
            caller,
            tuple(required[kind]),
            kind,
            argument_bindings,
            same_vector=same_vector,
        )
        obligations.append(
            CallPreconditionObligation(
                callee_condition=kind,
                disposition=disposition,
                status=(
                    CallPreconditionObligationStatus.RESOLVED
                    if reason is None
                    else CallPreconditionObligationStatus.INVALID_FORWARD
                ),
                source=disposition.source or source,
                reason=reason,
            )
        )

    stale = tuple(
        item
        for item in dispositions
        if callees
        if item.condition not in declared
    )
    return CallPreconditionResolution(tuple(obligations), stale)


def _forwarding_error(
    caller: Primitive,
    callee_conditions: tuple[tuple[Primitive, PrimitivePrecondition], ...],
    kind: PreconditionKind,
    argument_bindings: tuple[CallArgumentBinding, ...],
    *,
    same_vector: bool,
) -> str | None:
    if not same_vector:
        return (
            f"forwarded {kind.value!r} crosses a vector identity; use discharge "
            "only when the implementation establishes the transformed condition"
        )
    caller_conditions = tuple(
        condition for condition in caller.preconditions if condition.kind is kind
    )
    if len(caller_conditions) != 1:
        return (
            f"forwarded {kind.value!r} requires exactly one matching root "
            "precondition on the caller"
        )
    caller_identity = _condition_identity(caller, caller_conditions[0])
    bindings = {
        item.callee_parameter_index: item.caller_parameter_index
        for item in argument_bindings
    }
    mapped_identities: set[_ConditionIdentity | None] = set()
    for callee, condition in callee_conditions:
        identity = _condition_identity(callee, condition)
        mapped: list[_ConditionOperandIdentity] = []
        for operand in identity.operands:
            caller_index = bindings.get(operand.parameter_index)
            if caller_index is None:
                mapped_identities.add(None)
                break
            mapped.append(
                _ConditionOperandIdentity(
                    operand.domain,
                    operand.role,
                    caller_index,
                )
            )
        else:
            mapped_identities.add(
                _ConditionIdentity(
                    tuple(
                        sorted(
                            mapped,
                            key=lambda item: (
                                item.domain,
                                item.role,
                                item.parameter_index,
                            ),
                        )
                    ),
                    identity.memory_addressing,
                    identity.memory_payload_extent,
                    identity.memory_indexed_lane_extent,
                )
            )
    if len(mapped_identities) != 1:
        return (
            f"forwarded {kind.value!r} is ambiguous across matching callee overloads"
        )
    mapped_identity = next(iter(mapped_identities))
    if mapped_identity is None:
        return (
            f"forwarded {kind.value!r} requires each bound callee operand to be "
            "an exact caller parameter"
        )
    if mapped_identity != caller_identity:
        return (
            f"forwarded {kind.value!r} does not map the callee operands to the "
            "caller's matching root precondition"
        )
    return None


def _condition_identity(
    primitive: Primitive,
    condition: PrimitivePrecondition,
) -> _ConditionIdentity:
    identity = [
        _ConditionOperandIdentity(
            (
                "arithmetic"
                if isinstance(binding, ArithmeticOperandBinding)
                else "operation"
            ),
            _binding_role_identity(binding),
            binding.parameter_index,
        )
        for binding in condition.operand_bindings
    ]
    mask_sensitive = condition.kind in {
        PreconditionKind.ACTIVE_DIVISOR_NONZERO,
        PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID,
        PreconditionKind.COMPACTED_MEMORY_EXTENT,
    }
    if mask_sensitive and primitive.mask_mode is not None:
        mask_index = _control_mask_parameter_index(primitive)
        if mask_index is not None and not any(
            isinstance(binding, OperandBinding)
            and binding.role is OperandRole.CONTROL_MASK
            for binding in condition.operand_bindings
        ):
            identity.append(
                _ConditionOperandIdentity(
                    "operation",
                    OperandRole.CONTROL_MASK.value,
                    mask_index,
                )
            )
    descriptor = PRECONDITION_DESCRIPTORS[condition.kind]
    memory = primitive.memory if descriptor.binds_memory_operand else None
    return _ConditionIdentity(
        tuple(
            sorted(
                identity,
                key=lambda item: (item.domain, item.role, item.parameter_index),
            )
        ),
        None if memory is None else memory.addressing,
        None if memory is None else memory.payload_extent,
        None if memory is None else memory.indexed_lane_extent,
    )


def _control_mask_parameter_index(primitive: Primitive) -> int | None:
    if primitive.operation is not None:
        binding = primitive.operation.binding(OperandRole.CONTROL_MASK)
        if binding is not None:
            return binding.parameter_index
    shape = parse_signature(primitive.signature)
    if shape is None:
        return None
    indexes = tuple(
        index for index, kind in enumerate(shape.param_kinds) if kind == "m"
    )
    return indexes[0] if len(indexes) == 1 else None


def _binding_role_identity(
    binding: OperandBinding | ArithmeticOperandBinding,
) -> str:
    if isinstance(binding, OperandBinding) and binding.role in {
        OperandRole.MEMORY_SOURCE,
        OperandRole.MEMORY_DESTINATION,
    }:
        return "memory"
    return binding.role.value


__all__ = (
    "CallArgumentBinding",
    "CallPreconditionDisposition",
    "CallPreconditionDispositionKind",
    "CallPreconditionObligation",
    "CallPreconditionObligationStatus",
    "CallPreconditionResolution",
    "call_precondition_obligation_sort_key",
    "call_precondition_candidates",
    "resolve_call_preconditions",
)
