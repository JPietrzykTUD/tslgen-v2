"""PIVOT-specific projection of machine profiles to hardware feature sets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from tslc.catalog.machine_profiles import MachineProfile


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


__all__ = ("profiles_for_distinct_feature_sets",)
