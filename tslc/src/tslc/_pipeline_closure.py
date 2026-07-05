"""Dependency closure and pruning helpers for generated specializations."""

from __future__ import annotations

from dataclasses import dataclass, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    ImplementationSafety,
    RESULT_DIM_BASE,
    RESULT_DIM_EXTENSION,
)
from tslc.lower.dependencies import CallDependency, VectorIdentity
from tslc.lower.lowerer import LoweredSpecialization
from tslc.select.selector import SelectedImplementation


@dataclass(slots=True, eq=False)
class _LoweredSlot:
    backend: str
    spec: LoweredSpecialization
    callees: frozenset[CallDependency]
    callee_origins: tuple["CallDependencyOrigin", ...] = ()
    unresolved_callee: "CallDependencyOrigin | None" = None


@dataclass(frozen=True, slots=True)
class CallDependencyOrigin:
    dependency: CallDependency
    origin: str


def _target_dependency_context(
    slot: SelectedImplementation,
) -> tuple[str | None, str | None, str | None]:
    target_alias = (
        slot.primitive.result_target[1] if slot.primitive.result_target is not None else None
    )
    target_base = (
        slot.to_target
        if slot.primitive.result_target is not None
        and slot.primitive.result_target[0] == RESULT_DIM_BASE
        else None
    )
    target_extension = (
        slot.to_target
        if slot.primitive.result_target is not None
        and slot.primitive.result_target[0] == RESULT_DIM_EXTENSION
        else None
    )
    return target_alias, target_base, target_extension


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

    valid = {_slot_key(slot, split_names) for slot in slots}
    changed = True
    while changed:
        changed = False
        for slot in slots:
            slot_key = _slot_key(slot, split_names)
            if slot_key not in valid:
                continue
            origins = {
                origin.dependency: origin for origin in slot.callee_origins
            }
            for dependency in slot.callees:
                resolved = _dependency_key(slot, dependency, split_names)
                if resolved not in valid:
                    slot.unresolved_callee = origins.get(
                        dependency,
                        CallDependencyOrigin(dependency, "implementation"),
                    )
                    valid.discard(slot_key)
                    changed = True
                    break

    live_slots = [slot for slot in slots if _slot_key(slot, split_names) in valid]
    _propagate_transitive_call_facts(live_slots, split_names)

    grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {}
    pruned: list[_LoweredSlot] = []
    for slot in slots:
        if _slot_key(slot, split_names) in valid:
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
    """Profile plus the transitive feature flags required by live lowered specs."""

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
) -> tuple[str, str, str | None, VectorIdentity, VectorIdentity | None]:
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
) -> tuple[str, str, str | None, VectorIdentity, VectorIdentity | None]:
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
    """Propagate unsafe callee metadata and required features through live calls.

    A caller that reaches unsafe callee metadata records an internal unsafe
    dependency for review/diagnostics. Required feature flags propagate
    bottom-up as well, so a profile gets every feature needed by the bodies that
    remain live after dependency pruning.
    """

    safety_by_key = {
        _safety_key(slot, split_names): slot.spec.safety for slot in slots
    }
    features_by_key = {
        _safety_key(slot, split_names): slot.spec.required_features for slot in slots
    }
    dependency_targets: dict[
        tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
        list[tuple[
            tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
            tuple[str, ...],
            tuple[str, str] | None,
            tuple[tuple[str, str, str], ...],
        ]],
    ] = {}
    for slot in slots:
        dependency_targets.setdefault(_slot_key(slot, split_names), []).append(
            _safety_key(slot, split_names)
        )
    changed = True
    while changed:
        changed = False
        for slot in slots:
            slot_key = _safety_key(slot, split_names)
            safety = safety_by_key[slot_key]
            features = features_by_key[slot_key]
            propagated = safety
            propagated_features = features
            for dependency in sorted(
                slot.callees,
                key=lambda dependency: (
                    dependency.primitive,
                    dependency.mask_policy or "",
                    dependency.source.base_tag,
                    dependency.source.extension_isa,
                    dependency.target.base_tag if dependency.target is not None else "",
                    dependency.target.extension_isa
                    if dependency.target is not None
                    else "",
                ),
            ):
                for dependency_safety_key in dependency_targets.get(
                    _dependency_key(slot, dependency, split_names), []
                ):
                    dependency_safety = safety_by_key[dependency_safety_key]
                    if (
                        dependency_safety.internal_unsafe
                        or dependency_safety.caller_unsafe
                    ):
                        propagated = propagated.merge(
                            ImplementationSafety(
                                internal_unsafe=True,
                                reasons=dependency_safety.reasons
                                | frozenset({"unsafe_callee"}),
                            )
                        )
                    dependency_features = features_by_key[dependency_safety_key]
                    if not dependency_features <= propagated_features:
                        propagated_features = propagated_features | dependency_features
            if propagated != safety or propagated_features != features:
                safety_by_key[slot_key] = propagated
                features_by_key[slot_key] = propagated_features
                changed = True

    for slot in slots:
        slot_key = _safety_key(slot, split_names)
        safety = safety_by_key[slot_key]
        features = features_by_key[slot_key]
        if safety == slot.spec.safety and features == slot.spec.required_features:
            continue
        slot.spec = replace(
            slot.spec,
            safety=safety,
            required_features=features,
        )


def _safety_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> tuple[
    tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
    tuple[str, ...],
    tuple[str, str] | None,
    tuple[tuple[str, str, str], ...],
]:
    """A lowered-body identity for safety propagation before emitted-name splits."""

    spec = slot.spec
    return (
        _slot_key(slot, split_names),
        spec.param_kinds,
        spec.immediate,
        spec.generic_params,
    )
