"""Typed primitive requirements for backend-supplied helper surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from tslc.catalog.model import PrimitiveMaskMode

if TYPE_CHECKING:
    from tslc.catalog.model import Catalog
    from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class PrimitiveRequirement:
    """One source primitive form required by a backend helper feature."""

    source_name: str
    mask_policy: PrimitiveMaskMode | None = None

    def is_satisfied_by(self, specialization: LoweredSpecialization) -> bool:
        return (
            specialization.source_primitive_name == self.source_name
            and specialization.mask_policy == self.mask_policy
        )


@dataclass(frozen=True, slots=True)
class HelperFeature:
    """A separately gated helper feature and the primitive forms it calls."""

    name: str
    requirements: tuple[PrimitiveRequirement, ...]


@dataclass(frozen=True, slots=True)
class BackendHelperManifest:
    """Backend helper requirements shared by closure and render admission."""

    backend_id: str
    features: tuple[HelperFeature, ...]
    _by_name: Mapping[str, HelperFeature] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        by_name = {feature.name: feature for feature in self.features}
        if len(by_name) != len(self.features):
            raise ValueError(f"duplicate helper feature for backend {self.backend_id!r}")
        object.__setattr__(self, "_by_name", MappingProxyType(by_name))

    @property
    def source_primitives(self) -> tuple[str, ...]:
        """Unique closure roots in deterministic manifest order."""

        ordered: list[str] = []
        seen: set[str] = set()
        for feature in self.features:
            for requirement in feature.requirements:
                if requirement.source_name not in seen:
                    seen.add(requirement.source_name)
                    ordered.append(requirement.source_name)
        return tuple(ordered)

    def closure_seed_primitives(self, catalog: Catalog) -> tuple[str, ...]:
        return tuple(
            source_name
            for source_name in self.source_primitives
            if catalog.primitives_named(source_name, unmasked=False)
        )

    def supports(
        self,
        feature_name: str,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> bool:
        return not self.missing_requirements(feature_name, by_primitive)

    def requirements(self, feature_name: str) -> tuple[PrimitiveRequirement, ...]:
        feature = self._by_name.get(feature_name)
        if feature is None:
            raise KeyError(
                f"backend {self.backend_id!r} has no helper feature {feature_name!r}"
            )
        return feature.requirements

    def matching_specializations(
        self,
        requirement: PrimitiveRequirement,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> tuple[LoweredSpecialization, ...]:
        return tuple(
            specialization
            for group in by_primitive.values()
            for specialization in group
            if requirement.is_satisfied_by(specialization)
        )

    def missing_requirements(
        self,
        feature_name: str,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> tuple[PrimitiveRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements(feature_name)
            if not self.matching_specializations(requirement, by_primitive)
        )


CPP_HELPER_MANIFEST = BackendHelperManifest(
    "cpp",
    (
        HelperFeature(
            "algorithm",
            (
                PrimitiveRequirement("load"),
                PrimitiveRequirement("store"),
                PrimitiveRequirement("store", PrimitiveMaskMode.PASS_THROUGH),
                PrimitiveRequirement("to_integral"),
                PrimitiveRequirement("to_mask"),
                PrimitiveRequirement("gather_narrow"),
                PrimitiveRequirement("compress_store"),
                PrimitiveRequirement("mask_population_count"),
                PrimitiveRequirement("mask_binary_and"),
            ),
        ),
    ),
)


RUST_HELPER_MANIFEST = BackendHelperManifest(
    "rust",
    (
        HelperFeature(
            "masked_store",
            (PrimitiveRequirement("store", PrimitiveMaskMode.PASS_THROUGH),),
        ),
        HelperFeature(
            "selected_load",
            (
                PrimitiveRequirement("set_zero"),
                PrimitiveRequirement("to_array"),
                PrimitiveRequirement("from_array"),
            ),
        ),
        HelperFeature(
            "gather_narrow",
            (PrimitiveRequirement("gather_narrow"),),
        ),
        HelperFeature(
            "compress_store",
            (PrimitiveRequirement("compress_store"),),
        ),
        HelperFeature(
            "mask_population_count",
            (PrimitiveRequirement("mask_population_count"),),
        ),
        HelperFeature(
            "integral_mask",
            (PrimitiveRequirement("to_integral"),),
        ),
        HelperFeature(
            "mask_from_integral",
            (PrimitiveRequirement("to_mask"),),
        ),
    ),
)


EMPTY_HELPER_MANIFEST = BackendHelperManifest("none", ())


__all__ = (
    "BackendHelperManifest",
    "CPP_HELPER_MANIFEST",
    "EMPTY_HELPER_MANIFEST",
    "HelperFeature",
    "PrimitiveRequirement",
    "RUST_HELPER_MANIFEST",
)
