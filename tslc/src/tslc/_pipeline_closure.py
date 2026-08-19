"""Dependency closure and pruning helpers for generated specializations."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import ImplementationSafety
from tslc.diagnostics import SourceSpan
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    VectorIdentity,
    dependency_sort_key,
    is_concrete_call_dependency,
    origin_sort_key,
    vector_reference_label,
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
    # Selection-time facts retained for explicit analyses. Propagation rewrites
    # ``spec.required_features``; the declared set and the authored selector
    # entry stay available so analyses can attribute the transitive delta.
    selection_required_features: frozenset[str] = frozenset()
    selection_required_compiler_capabilities: frozenset[str] = frozenset()
    compiler_alternative_rank: int | None = None
    selector_source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class LoweringTraceSlot:
    """Immutable lowered call-graph facts retained for an explicit analysis."""

    profile: str
    backend: str
    specialization: LoweredSpecialization
    callees: tuple[CallDependency, ...]
    callee_origins: tuple[CallDependencyOrigin, ...]
    emitted: bool
    unresolved_callee: CallDependencyOrigin | None = None
    # Target features the selected implementation declared in source before
    # call-graph propagation; the delta against
    # ``specialization.required_features`` is what dependency closure added.
    selection_required_features: frozenset[str] = frozenset()
    selection_required_compiler_capabilities: frozenset[str] = frozenset()
    # The authored selector entry that produced this specialization, if any.
    selector_source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class LoweringTrace:
    """One deterministic dependency-closure snapshot from generation."""

    split_names: frozenset[str]
    slots: tuple[LoweringTraceSlot, ...]


type _SlotKey = tuple[
    str,
    str,
    str | None,
    VectorIdentity,
    VectorIdentity | None,
]
type _TypeParamFact = tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    bool,
    str | None,
    str | None,
]
type _CallFactKey = tuple[
    _SlotKey,
    tuple[str, ...],
    tuple[str, str] | None,
    tuple[tuple[str, str, str], ...],
]
type _CompilerAlternativeKey = tuple[
    _CallFactKey,
    tuple[tuple[str, str], ...],
    tuple[_TypeParamFact, ...],
    str | None,
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
            (dependency, dependency_key)
            for dependency in sorted(slot.callees, key=dependency_sort_key)
            if (
                dependency_key := _dependency_key(
                    slot,
                    dependency,
                    split_names,
                )
            )
            is not None
        )
        dependency_items.append(items)
        for _dependency, dependency_key in items:
            dependents.setdefault(dependency_key, []).append(index)
    compiler_groups: dict[_CompilerAlternativeKey, list[int]] = {}
    for index, slot in enumerate(slots):
        if slot.compiler_alternative_rank is None:
            continue
        key = _compiler_alternative_key(slot, split_names)
        compiler_groups.setdefault(key, []).append(index)

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
        for group_indices in compiler_groups.values():
            fallback_index = next(
                (
                    index
                    for index in group_indices
                    if not slots[index].spec.required_compiler_capabilities
                ),
                None,
            )
            if fallback_index is None or not invalid[fallback_index]:
                continue
            for index in group_indices:
                if invalid[index]:
                    continue
                slots[index].unresolved_callee = (
                    slots[fallback_index].unresolved_callee
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
    del available, candidates, compiler_groups
    del dependency_items, dependents, slot_keys
    _propagate_transitive_call_facts(live_slots, split_names)

    grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {}
    for slot in _merge_compiler_alternative_slots(live_slots, split_names):
        grouped.setdefault(slot.backend, {}).setdefault(
            slot.spec.primitive_name, []
        ).append(slot.spec)
    pruned = [
        slot
        for index, slot in enumerate(slots)
        if invalid[index]
    ]
    return grouped, pruned


def _merge_compiler_alternative_slots(
    slots: list[_LoweredSlot],
    split_names: frozenset[str],
) -> list[_LoweredSlot]:
    """Collapse auto-selected compiler branches into one logical slot."""

    by_key: dict[_CompilerAlternativeKey, list[_LoweredSlot]] = {}
    for slot in slots:
        if slot.compiler_alternative_rank is None:
            continue
        key = _compiler_alternative_key(slot, split_names)
        by_key.setdefault(key, []).append(slot)

    merged: dict[_CompilerAlternativeKey, _LoweredSlot] = {}
    for key, candidates in by_key.items():
        if not any(
            not candidate.spec.required_compiler_capabilities
            for candidate in candidates
        ):
            continue

        ranked = sorted(
            candidates,
            key=lambda item: item.compiler_alternative_rank or 0,
        )
        canonical = ranked[-1]
        if len(ranked) > 1:
            origins = tuple(
                sorted(
                    {
                        origin
                        for candidate in ranked
                        for origin in candidate.callee_origins
                    },
                    key=origin_sort_key,
                )
            )
            canonical.spec = replace(
                canonical.spec,
                compiler_alternatives=tuple(
                    candidate.spec for candidate in ranked[:-1]
                ),
                call_dependency_origins=origins,
            )
            canonical.callees = frozenset(
                dependency
                for candidate in ranked
                for dependency in candidate.callees
            )
            canonical.callee_origins = origins
        merged[key] = canonical

    emitted: list[_LoweredSlot] = []
    seen: set[_CompilerAlternativeKey] = set()
    for slot in slots:
        if slot.compiler_alternative_rank is None:
            emitted.append(slot)
            continue
        key = _compiler_alternative_key(slot, split_names)
        if key not in merged:
            continue
        if key in seen:
            continue
        seen.add(key)
        emitted.append(merged[key])
    return emitted


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
    return _specialization_key(slot.backend, slot.spec, split_names)


def lowering_trace_slot_key(
    slot: LoweringTraceSlot,
    split_names: frozenset[str],
) -> _SlotKey:
    """Return the same identity used by dependency pruning."""

    return _specialization_key(slot.backend, slot.specialization, split_names)


def _specialization_key(
    backend: str,
    spec: LoweredSpecialization,
    split_names: frozenset[str],
) -> _SlotKey:
    return (
        backend,
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
) -> _SlotKey | None:
    return _call_dependency_key(slot.backend, dependency, split_names)


def lowering_trace_dependency_key(
    slot: LoweringTraceSlot,
    dependency: CallDependency,
    split_names: frozenset[str],
) -> _SlotKey | None:
    """Resolve an analysis edge with the pipeline's pruning identity."""

    return _call_dependency_key(slot.backend, dependency, split_names)


def unresolved_trace_reason(slot: LoweringTraceSlot) -> str:
    """Explain why dependency pruning removed one traced specialization."""

    return unresolved_callee_reason(slot.unresolved_callee)


def unresolved_callee_reason(unresolved: CallDependencyOrigin | None) -> str:
    """Explain a dependency-pruning edge for generation and analysis."""

    if unresolved is None:
        return "pruned: a called primitive is not generated for this profile"
    return (
        f"pruned: {unresolved.origin} calls "
        f"{dependency_label(unresolved.dependency)}, but that specialization "
        "is not generated for this profile"
    )


def dependency_label(dependency: CallDependency) -> str:
    source_reference = vector_reference_label(dependency.source)
    source = (
        f"{dependency.primitive}{source_reference}"
        if isinstance(dependency.source, VectorIdentity)
        else f"{dependency.primitive}<{source_reference}>"
    )
    if dependency.mask_policy is not None:
        source = f"{source}[mask={dependency.mask_policy}]"
    if dependency.target is None:
        return source
    return f"{source} -> {vector_reference_label(dependency.target)}"


def _call_dependency_key(
    backend: str,
    dependency: CallDependency,
    split_names: frozenset[str],
) -> _SlotKey | None:
    if not is_concrete_call_dependency(dependency):
        return None
    assert isinstance(dependency.source, VectorIdentity)
    assert dependency.target is None or isinstance(
        dependency.target,
        VectorIdentity,
    )
    return (
        backend,
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
        elif slot.compiler_alternative_rank is None:
            # Preserve established last-body facts for ordinary duplicate
            # lowered identities such as scalar overload collapses.
            safety[fact_id] = slot.spec.safety
            features[fact_id] = slot.spec.required_features
            states[fact_id] = slot.spec.implementation_state
        else:
            # Compiler alternatives are one logical callable for conservative
            # safety, target-feature, and implementation-state propagation.
            safety[fact_id] = safety[fact_id].merge(slot.spec.safety)
            features[fact_id] = (
                features[fact_id] | slot.spec.required_features
            )
            states[fact_id] = combine_implementation_states(
                (states[fact_id], slot.spec.implementation_state)
            )
        slot_fact_ids.append(fact_id)
    fact_count = len(fact_ids)
    branch_compiler_capabilities = _propagate_compiler_capabilities_per_branch(
        slots, split_names
    )
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
            if dependency_key is None:
                continue
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

    for slot, fact_id, propagated_compiler_capabilities in zip(
        slots, slot_fact_ids, branch_compiler_capabilities, strict=True
    ):
        propagated_safety = safety[fact_id]
        propagated_features = features[fact_id]
        propagated_state = states[fact_id]
        if (
            propagated_safety == slot.spec.safety
            and propagated_features == slot.spec.required_features
            and propagated_compiler_capabilities
            == slot.spec.required_compiler_capabilities
            and propagated_state == slot.spec.implementation_state
        ):
            continue
        slot.spec = replace(
            slot.spec,
            safety=propagated_safety,
            required_features=propagated_features,
            required_compiler_capabilities=(
                propagated_compiler_capabilities
            ),
            implementation_state=propagated_state,
        )


def _propagate_compiler_capabilities_per_branch(
    slots: list[_LoweredSlot],
    split_names: frozenset[str],
) -> tuple[frozenset[str], ...]:
    """Propagate capability requirements without conflating alternative bodies."""

    slot_keys = tuple(_slot_key(slot, split_names) for slot in slots)
    target_groups: dict[
        _SlotKey,
        dict[_CallFactKey, list[int]],
    ] = {}
    for index, (slot, slot_key) in enumerate(
        zip(slots, slot_keys, strict=True)
    ):
        fact_key = _call_fact_key_from_slot_key(slot, slot_key)
        target_groups.setdefault(slot_key, {}).setdefault(
            fact_key, []
        ).append(index)

    dependencies: list[tuple[tuple[int, ...], ...]] = []
    for slot in slots:
        groups: list[tuple[int, ...]] = []
        seen: set[tuple[int, ...]] = set()
        for dependency in sorted(slot.callees, key=dependency_sort_key):
            dependency_key = _dependency_key(slot, dependency, split_names)
            if dependency_key is None:
                continue
            for indices in target_groups.get(dependency_key, {}).values():
                group = tuple(indices)
                if group in seen:
                    continue
                seen.add(group)
                groups.append(group)
        dependencies.append(tuple(groups))

    direct = tuple(
        slot.spec.required_compiler_capabilities for slot in slots
    )
    propagated = direct
    while True:
        updated: list[frozenset[str]] = []
        for index, dependency_groups in enumerate(dependencies):
            inherited: set[str] = set()
            for targets in dependency_groups:
                if any(
                    slots[target].compiler_alternative_rank is not None
                    for target in targets
                ):
                    shared = set(propagated[targets[0]])
                    for target in targets[1:]:
                        shared.intersection_update(propagated[target])
                    inherited.update(shared)
                else:
                    # Match ordinary duplicate lowered identities: the last
                    # body supplies the callable's facts.
                    inherited.update(propagated[targets[-1]])
            updated.append(direct[index] | inherited)
        result = tuple(updated)
        if result == propagated:
            return result
        propagated = result


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


def _compiler_alternative_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> _CompilerAlternativeKey:
    spec = slot.spec
    return (
        _call_fact_key_from_slot_key(
            slot,
            _slot_key(slot, split_names),
        ),
        spec.axis,
        _type_param_facts(spec),
        spec.lane_parameter,
    )


def _type_param_facts(
    spec: LoweredSpecialization,
) -> tuple[_TypeParamFact, ...]:
    return tuple(
        (
            parameter.name,
            parameter.bounds,
            parameter.base_type_constraints,
            parameter.specialize_base,
            parameter.base_type_binding,
            parameter.base_type_binding_spelling,
        )
        for parameter in spec.type_params
    )
