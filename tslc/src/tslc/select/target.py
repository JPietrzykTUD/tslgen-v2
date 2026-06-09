"""Selection request: which primitives/types to emit for a machine profile."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile


@dataclass(frozen=True, slots=True)
class ProfileRequest:
    """Emit ``primitives`` over ``type_tags`` for one machine ``profile``."""

    profile: MachineProfile
    primitive_names: tuple[str, ...]
    type_tags: tuple[str, ...]
