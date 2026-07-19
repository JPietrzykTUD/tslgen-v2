"""PIVOT-specific projection of machine profiles to hardware feature sets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.select.selector import SelectedImplementation


@dataclass(frozen=True, slots=True)
class SelectedProfile:
    profile: MachineProfile
    slots: tuple[SelectedImplementation, ...]


def profiles_for_distinct_feature_sets(
    profiles: tuple[MachineProfile, ...],
) -> tuple[MachineProfile, ...]:
    """Return one selection profile per distinct hardware feature set.

    Machine profiles also carry build, runner, and compiler-mode details that are
    meaningful to normal project generation.  PIVOT does not build or run a
    project, so processing profiles that differ only in those details repeats the
    same hardware projection.  Compiler modes are unioned within a feature-set
    group so mode-activated corpus extensions (fixed SVE and oneAPI FPGA) remain
    visible to the export.
    """

    grouped: dict[
        tuple[str, frozenset[str]], list[MachineProfile]
    ] = defaultdict(list)
    for profile in profiles:
        grouped[(profile.family, profile.features)].append(profile)

    projected: list[MachineProfile] = []
    for group in grouped.values():
        ordered = tuple(sorted(group, key=lambda item: item.name))
        if len(ordered) == 1:
            projected.append(ordered[0])
            continue
        projected.append(
            replace(
                ordered[0],
                name="+".join(profile.name for profile in ordered),
                compile_modes=frozenset().union(
                    *(profile.compile_modes for profile in ordered)
                ),
            )
        )
    return tuple(sorted(projected, key=lambda item: item.name))


def contributing_profiles(
    selections: tuple[SelectedProfile, ...],
    *,
    slot_identity: Callable[[SelectedImplementation], tuple[object, ...]],
) -> tuple[SelectedProfile, ...]:
    """Choose a deterministic cover of distinct selected implementations."""

    identities: dict[tuple[object, ...], int] = {}
    coverage: list[frozenset[int]] = []
    for selection in selections:
        covered: set[int] = set()
        for slot in selection.slots:
            key = slot_identity(slot)
            identity = identities.get(key)
            if identity is None:
                identity = len(identities)
                identities[key] = identity
            covered.add(identity)
        coverage.append(frozenset(covered))

    indexes = contributing_indexes(tuple(coverage))
    return tuple(selections[index] for index in indexes)


def contributing_indexes(
    coverage: tuple[frozenset[int], ...],
) -> tuple[int, ...]:
    """Greedily cover all implementations; each retained set adds coverage."""

    remaining = set().union(*coverage) if coverage else set()
    candidates = set(range(len(coverage)))
    selected: list[int] = []
    while remaining:
        best = min(
            candidates,
            key=lambda index: (
                -len(coverage[index] & remaining),
                -len(coverage[index]),
                index,
            ),
        )
        added = coverage[best] & remaining
        if not added:
            break
        selected.append(best)
        remaining.difference_update(added)
        candidates.remove(best)
    return tuple(selected)


__all__ = (
    "SelectedProfile",
    "contributing_indexes",
    "contributing_profiles",
    "profiles_for_distinct_feature_sets",
)
