"""Typed backend-emission facts produced after selection and lowering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from tslc.backend.emitted_names import finalize_emitted_names
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability

if TYPE_CHECKING:
    from tslc.lower.lowerer import LoweredSpecialization

_EMPTY_SPECIALIZATIONS: Mapping[str, tuple[LoweredSpecialization, ...]] = (
    MappingProxyType({})
)


@dataclass(frozen=True, slots=True, init=False)
class EmittedProfile:
    """One profile's finalized backend inputs, before project formatting."""

    profile: MachineProfile
    specializations_by_backend: Mapping[
        str, Mapping[str, tuple[LoweredSpecialization, ...]]
    ]
    extensions: Mapping[str, Extension] = field(default_factory=dict)
    profile_family: ProfileFamilyCapability | None = None

    def __init__(
        self,
        profile: MachineProfile,
        specializations_by_backend: Mapping[
            str, Mapping[str, tuple[LoweredSpecialization, ...]]
        ],
        extensions: Mapping[str, Extension] = MappingProxyType({}),
        profile_family: ProfileFamilyCapability | None = None,
        *,
        immediate_split_names: frozenset[str] = frozenset(),
    ) -> None:
        finalized = {
            backend_id: finalize_emitted_names(
                by_primitive,
                immediate_split_names,
            )
            for backend_id, by_primitive in specializations_by_backend.items()
        }
        object.__setattr__(self, "profile", profile)
        object.__setattr__(
            self,
            "specializations_by_backend",
            _freeze_backend_specializations(finalized),
        )
        object.__setattr__(
            self,
            "extensions",
            MappingProxyType(dict(sorted(extensions.items()))),
        )
        object.__setattr__(self, "profile_family", profile_family)

    def specializations(
        self, backend_id: str
    ) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
        return self.specializations_by_backend.get(backend_id, _EMPTY_SPECIALIZATIONS)

    def used_extensions(self, backend_id: str) -> tuple[str, ...]:
        """Return extension ISAs referenced by one backend's emitted specializations."""

        return used_extensions(self.specializations(backend_id))


def used_extensions(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> tuple[str, ...]:
    names: set[str] = set()
    for specializations in by_primitive.values():
        names.update(spec.extension_name for spec in specializations)
        names.update(
            spec.target.extension_isa for spec in specializations if spec.target
        )
    return tuple(sorted(names))


def used_type_specs(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> tuple[tuple[str, str, str], ...]:
    """Used ``(extension, type_tag, base_spelling)`` facts, including targets."""

    facts: set[tuple[str, str, str]] = set()
    for specializations in by_primitive.values():
        facts.update(
            (spec.extension_name, spec.type_tag, spec.base_type_spelling)
            for spec in specializations
        )
        facts.update(
            (
                spec.target.extension_isa,
                spec.target.base_tag,
                spec.target.base_spelling,
            )
            for spec in specializations
            if spec.target
        )
    return tuple(sorted(facts))


def _freeze_specializations(
    mapping: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
    return MappingProxyType(
        {name: tuple(specs) for name, specs in sorted(mapping.items())}
    )


def _freeze_backend_specializations(
    mapping: Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]],
) -> Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]]:
    return MappingProxyType(
        {
            backend_id: _freeze_specializations(by_primitive)
            for backend_id, by_primitive in sorted(mapping.items())
        }
    )


__all__ = (
    "EmittedProfile",
    "used_extensions",
    "used_type_specs",
)
