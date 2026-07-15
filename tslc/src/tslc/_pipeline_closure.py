"""Dependency closure and pruning helpers for generated specializations."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import ImplementationSafety
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    VectorIdentity,
    dependency_sort_key,
)
from tslc.lower.implementation_state import combine_implementation_states
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(slots=True, eq=False)
class _LoweredSlot:
    backend: str
    spec: LoweredSpecialization
    callees: frozenset[CallDependency]
    callee_origins: tuple["CallDependencyOrigin", ...] = ()
    unresolved_callee: "CallDependencyOrigin | None" = None


type _SlotKey = tuple[
    str,
    str,
    str | None,
    VectorIdentity,
    VectorIdentity | None,
]
type _CallFactKey = tuple[
    _SlotKey,
    tuple[str, ...],
    tuple[str, str] | None,
    tuple[tuple[str, str, str], ...],
]


def _prune_unresolved(
    slots: list[_LoweredSlot],
    split_names: frozenset[str] = frozenset(),
) -> tuple[dict[str, dict[str, list[LoweredSpecialization]]], list[_LoweredSlot]]:
    """Drop emitted specializations whose called primitives are not themselves emitted.

    The fixpoint matters because pruning a callee can in turn dangle its
    callers. Identity is policy-aware only for names that are actually split
    into more than one emitted form, so a single-form masked primitive can still
    satisfy bare calls that lower to that one emitted specialization.
    """

    slot_keys = tuple(_slot_key(slot, split_names) for slot in slots)
    available: dict[_SlotKey, int] = {}
    for slot_key in slot_keys:
        available[slot_key] = available.get(slot_key, 0) + 1

    dependency_items: list[tuple[tuple[CallDependency, _SlotKey], ...]] = []
    dependents: dict[_SlotKey, list[int]] = {}
    for index, slot in enumerate(slots):
        items = tuple(
            (dependency, _dependency_key(slot, dependency, split_names))
            for dependency in sorted(slot.callees, key=dependency_sort_key)
        )
        dependency_items.append(items)
        for _dependency, dependency_key in items:
            dependents.setdefault(dependency_key, []).append(index)

    invalid = [False] * len(slots)
    candidates = list(range(len(slots)))
    while candidates:
        removed: list[int] = []
        for index in candidates:
            if invalid[index]:
                continue
            missing = next(
                (
                    dependency
                    for dependency, dependency_key in dependency_items[index]
                    if available.get(dependency_key, 0) == 0
                ),
                None,
            )
            if missing is None:
                continue
            slot = slots[index]
            origins = {
                origin.dependency: origin for origin in slot.callee_origins
            }
            slot.unresolved_callee = origins.get(
                missing,
                CallDependencyOrigin(missing, "implementation"),
            )
            invalid[index] = True
            removed.append(index)

        if not removed:
            break

        unavailable_keys: set[_SlotKey] = set()
        for index in removed:
            slot_key = slot_keys[index]
            available[slot_key] -= 1
            if available[slot_key] == 0:
                unavailable_keys.add(slot_key)
        candidates = sorted(
            {
                dependent
                for slot_key in unavailable_keys
                for dependent in dependents.get(slot_key, ())
                if not invalid[dependent]
            }
        )

    live_slots = [slot for index, slot in enumerate(slots) if not invalid[index]]
    # Full generation retains earlier profiles while closing the next one, so
    # release pruning indexes before constructing the propagation graph.
    del available, candidates, dependency_items, dependents, slot_keys
    _propagate_transitive_call_facts(live_slots, split_names)

    grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {}
    pruned: list[_LoweredSlot] = []
    for index, slot in enumerate(slots):
        if not invalid[index]:
            grouped.setdefault(slot.backend, {}).setdefault(
                slot.spec.primitive_name, []
            ).append(slot.spec)
        else:
            pruned.append(slot)
    return grouped, pruned


def _profile_with_required_features(
    profile: MachineProfile,
    grouped: dict[str, dict[str, list[LoweredSpecialization]]],
) -> MachineProfile:
    """Profile plus the transitive target features required by live lowered specs."""

    required = set(profile.features)
    for by_primitive in grouped.values():
        for specs in by_primitive.values():
            for spec in specs:
                required.update(spec.required_features)
    features = frozenset(required)
    return profile if features == profile.features else replace(profile, features=features)


def _policy_of(
    name: str,
    policy: str | None,
    split_names: frozenset[str],
) -> str | None:
    return policy if name in split_names else None


def _slot_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> _SlotKey:
    spec = slot.spec
    return (
        slot.backend,
        spec.primitive_name,
        _policy_of(spec.primitive_name, spec.mask_policy, split_names),
        VectorIdentity(spec.type_tag, spec.extension_name),
        (
            VectorIdentity(spec.target.base_tag, spec.target.extension_isa)
            if spec.target is not None
            else None
        ),
    )


def _dependency_key(
    slot: _LoweredSlot,
    dependency: CallDependency,
    split_names: frozenset[str],
) -> _SlotKey:
    return (
        slot.backend,
        dependency.primitive,
        _policy_of(dependency.primitive, dependency.mask_policy, split_names),
        dependency.source,
        dependency.target,
    )


def _propagate_transitive_call_facts(
    slots: list[_LoweredSlot],
    split_names: frozenset[str],
) -> None:
    """Propagate callee safety, required features, and implementation state.

    A caller that reaches unsafe callee metadata records an internal unsafe
    dependency for review/diagnostics. Required target features propagate
    bottom-up as well, so a profile gets every feature needed by the bodies that
    remain live after dependency pruning. Implementation state joins through the
    same live dependency graph so query APIs report composed/fallback callees.
    """

    slot_keys = tuple(_slot_key(slot, split_names) for slot in slots)
    fact_keys = tuple(
        _call_fact_key_from_slot_key(slot, slot_key)
        for slot, slot_key in zip(slots, slot_keys, strict=True)
    )
    fact_ids: dict[_CallFactKey, int] = {}
    slot_fact_ids: list[int] = []
    safety: list[ImplementationSafety] = []
    features: list[frozenset[str]] = []
    states = []
    for slot, fact_key in zip(slots, fact_keys, strict=True):
        fact_id = fact_ids.get(fact_key)
        if fact_id is None:
            fact_id = len(fact_ids)
            fact_ids[fact_key] = fact_id
            safety.append(slot.spec.safety)
            features.append(slot.spec.required_features)
            states.append(slot.spec.implementation_state)
        else:
            # Match the previous fact-map construction when duplicate lowered
            # body identities occur: the last slot supplies the direct facts.
            safety[fact_id] = slot.spec.safety
            features[fact_id] = slot.spec.required_features
            states[fact_id] = slot.spec.implementation_state
        slot_fact_ids.append(fact_id)
    fact_count = len(fact_ids)
    del fact_ids, fact_keys

    dependency_targets: dict[_SlotKey, list[int]] = {}
    for slot_key, fact_id in zip(slot_keys, slot_fact_ids, strict=True):
        targets = dependency_targets.setdefault(slot_key, [])
        if not targets or targets[-1] != fact_id:
            targets.append(fact_id)

    callers_by_callee: dict[int, list[int]] = {}
    for slot, caller_id in zip(slots, slot_fact_ids, strict=True):
        for dependency in sorted(slot.callees, key=dependency_sort_key):
            dependency_key = _dependency_key(slot, dependency, split_names)
            for callee_id in dependency_targets.get(dependency_key, ()):
                callers = callers_by_callee.setdefault(callee_id, [])
                if not callers or callers[-1] != caller_id:
                    callers.append(caller_id)

    del dependency_targets, slot_keys
    queue = deque(range(fact_count))
    queued = [True] * fact_count
    while queue:
        callee_id = queue.popleft()
        queued[callee_id] = False
        callee_safety = safety[callee_id]
        callee_features = features[callee_id]
        callee_state = states[callee_id]
        for caller_id in callers_by_callee.get(callee_id, ()):
            caller_safety = safety[caller_id]
            propagated_safety = caller_safety
            if callee_safety.internal_unsafe or callee_safety.caller_unsafe:
                propagated_safety = caller_safety.merge(
                    ImplementationSafety(
                        internal_unsafe=True,
                        reasons=callee_safety.reasons
                        | frozenset({"unsafe_callee"}),
                    )
                )
            caller_features = features[caller_id]
            propagated_features = caller_features | callee_features
            caller_state = states[caller_id]
            propagated_state = combine_implementation_states(
                (caller_state, callee_state)
            )
            if (
                propagated_safety == caller_safety
                and propagated_features == caller_features
                and propagated_state == caller_state
            ):
                continue
            safety[caller_id] = propagated_safety
            features[caller_id] = propagated_features
            states[caller_id] = propagated_state
            if not queued[caller_id]:
                queue.append(caller_id)
                queued[caller_id] = True

    for slot, fact_id in zip(slots, slot_fact_ids, strict=True):
        propagated_safety = safety[fact_id]
        propagated_features = features[fact_id]
        propagated_state = states[fact_id]
        if (
            propagated_safety == slot.spec.safety
            and propagated_features == slot.spec.required_features
            and propagated_state == slot.spec.implementation_state
        ):
            continue
        slot.spec = replace(
            slot.spec,
            safety=propagated_safety,
            required_features=propagated_features,
            implementation_state=propagated_state,
        )


def _call_fact_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> _CallFactKey:
    """A lowered-body identity for transitive call facts before emitted-name splits."""

    return _call_fact_key_from_slot_key(slot, _slot_key(slot, split_names))


def _call_fact_key_from_slot_key(
    slot: _LoweredSlot,
    slot_key: _SlotKey,
) -> _CallFactKey:
    """Build a call-fact key from an already-computed emitted-slot identity."""

    spec = slot.spec
    return (
        slot_key,
        spec.param_kinds,
        spec.immediate,
        spec.generic_params,
    )
