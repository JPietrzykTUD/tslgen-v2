"""Semantic primitive requirements for backend-supplied helper surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from tslc.catalog.model import Catalog, PrimitiveMaskMode
from tslc.catalog.semantics import (
    COMPACTED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT,
    MASK_AND_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_POPULATION_COUNT_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
    VECTOR_FROM_ARRAY_REQUIREMENT,
    VECTOR_TO_ARRAY_REQUIREMENT,
    VECTOR_ZERO_REQUIREMENT,
    PrimitiveProviderRequirement,
    ResolvedPrimitiveProvider,
)
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class PrimitiveRequirement:
    """One semantic primitive form required by a backend helper feature."""

    provider: PrimitiveProviderRequirement
    mask_policy: PrimitiveMaskMode | None = None


@dataclass(frozen=True, slots=True)
class HelperFeature:
    """A separately gated helper feature and the primitive forms it calls."""

    name: str
    requirements: tuple[PrimitiveRequirement, ...]


@dataclass(frozen=True, slots=True)
class BackendHelperManifest:
    """Static semantic helper requirements declared by one backend."""

    backend_id: str
    features: tuple[HelperFeature, ...]
    _by_name: Mapping[str, HelperFeature] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        by_name = {feature.name: feature for feature in self.features}
        if len(by_name) != len(self.features):
            raise ValueError(f"duplicate helper feature for backend {self.backend_id!r}")
        object.__setattr__(self, "_by_name", MappingProxyType(by_name))

    @property
    def provider_requirements(self) -> tuple[PrimitiveProviderRequirement, ...]:
        """Unique provider shapes in deterministic manifest order."""

        return tuple(
            dict.fromkeys(
                requirement.provider
                for feature in self.features
                for requirement in feature.requirements
            )
        )

    def requirements(self, feature_name: str) -> tuple[PrimitiveRequirement, ...]:
        feature = self._by_name.get(feature_name)
        if feature is None:
            raise KeyError(
                f"backend {self.backend_id!r} has no helper feature {feature_name!r}"
            )
        return feature.requirements


@dataclass(frozen=True, slots=True)
class BackendHelperPlan:
    """One catalog-resolved helper plan shared by closure and backend planning."""

    manifest: BackendHelperManifest
    providers: tuple[ResolvedPrimitiveProvider, ...]
    unresolved: tuple[tuple[PrimitiveProviderRequirement, Diagnostic], ...]

    def __post_init__(self) -> None:
        required = self.manifest.provider_requirements
        resolved_requirements = tuple(
            provider.requirement for provider in self.providers
        )
        unresolved_requirements = tuple(
            requirement for requirement, _ in self.unresolved
        )
        if len(set(resolved_requirements)) != len(resolved_requirements):
            raise ValueError("backend helper providers must be unique")
        if len(set(unresolved_requirements)) != len(unresolved_requirements):
            raise ValueError("backend helper unresolved requirements must be unique")
        if set(resolved_requirements) & set(unresolved_requirements):
            raise ValueError(
                "backend helper requirements cannot be both resolved and unresolved"
            )
        if set((*resolved_requirements, *unresolved_requirements)) != set(required):
            raise ValueError(
                "backend helper plan must resolve every manifest requirement"
            )
        resolved_set = set(resolved_requirements)
        if tuple(
            requirement for requirement in required if requirement in resolved_set
        ) != resolved_requirements:
            raise ValueError("backend helper providers must follow manifest order")
        unresolved_set = set(unresolved_requirements)
        if tuple(
            requirement for requirement in required if requirement in unresolved_set
        ) != unresolved_requirements:
            raise ValueError("backend helper diagnostics must follow manifest order")

    @classmethod
    def resolve(
        cls,
        manifest: BackendHelperManifest,
        catalog: Catalog,
    ) -> BackendHelperPlan:
        providers: list[ResolvedPrimitiveProvider] = []
        unresolved: list[tuple[PrimitiveProviderRequirement, Diagnostic]] = []
        for requirement in manifest.provider_requirements:
            result = catalog.resolve_primitive_provider(requirement)
            if isinstance(result, Diagnostic):
                unresolved.append((requirement, result))
            else:
                providers.append(ResolvedPrimitiveProvider(requirement, result.name))
        return cls(manifest, tuple(providers), tuple(unresolved))

    @property
    def backend_id(self) -> str:
        return self.manifest.backend_id

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(diagnostic for _requirement, diagnostic in self.unresolved)

    @property
    def ambiguity_diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.code == "TSL-CATALOG-AMBIGUOUS-PRIMITIVE-PROVIDER"
        )

    @property
    def closure_seed_primitives(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(provider.primitive_name for provider in self.providers)
        )

    def provider(
        self, requirement: PrimitiveRequirement
    ) -> ResolvedPrimitiveProvider | None:
        return next(
            (
                provider
                for provider in self.providers
                if provider.requirement == requirement.provider
            ),
            None,
        )

    def unresolved_diagnostic(
        self, requirement: PrimitiveRequirement
    ) -> Diagnostic | None:
        return next(
            (
                diagnostic
                for provider_requirement, diagnostic in self.unresolved
                if provider_requirement == requirement.provider
            ),
            None,
        )

    def matching_specializations(
        self,
        requirement: PrimitiveRequirement,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> tuple[LoweredSpecialization, ...]:
        provider = self.provider(requirement)
        if provider is None:
            return ()
        return tuple(
            specialization
            for group in by_primitive.values()
            for specialization in group
            if specialization.source_primitive_name == provider.primitive_name
            and specialization.mask_policy == requirement.mask_policy
        )

    def missing_requirements(
        self,
        feature_name: str,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> tuple[PrimitiveRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.manifest.requirements(feature_name)
            if not self.matching_specializations(requirement, by_primitive)
        )


CPP_HELPER_MANIFEST = BackendHelperManifest(
    "cpp",
    (
        HelperFeature(
            "contiguous_read",
            (PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT),),
        ),
        HelperFeature(
            "contiguous_write",
            (PrimitiveRequirement(CONTIGUOUS_VECTOR_STORE_REQUIREMENT),),
        ),
        HelperFeature(
            "masked_write",
            (
                PrimitiveRequirement(
                    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
                    PrimitiveMaskMode.PASS_THROUGH,
                ),
            ),
        ),
        HelperFeature(
            "selected_read",
            (PrimitiveRequirement(INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT),),
        ),
        HelperFeature(
            "integral_mask",
            (PrimitiveRequirement(MASK_TO_INTEGRAL_REQUIREMENT),),
        ),
        HelperFeature(
            "mask_from_integral",
            (PrimitiveRequirement(MASK_FROM_INTEGRAL_REQUIREMENT),),
        ),
        HelperFeature(
            "compaction",
            (PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT),),
        ),
        HelperFeature(
            "mask_population_count",
            (PrimitiveRequirement(MASK_POPULATION_COUNT_REQUIREMENT),),
        ),
        HelperFeature(
            "mask_intersection",
            (PrimitiveRequirement(MASK_AND_REQUIREMENT),),
        ),
    ),
)


RUST_HELPER_MANIFEST = BackendHelperManifest(
    "rust",
    (
        HelperFeature(
            "contiguous_memory",
            (
                PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT),
                PrimitiveRequirement(CONTIGUOUS_VECTOR_STORE_REQUIREMENT),
            ),
        ),
        HelperFeature(
            "masked_store",
            (
                PrimitiveRequirement(
                    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
                    PrimitiveMaskMode.PASS_THROUGH,
                ),
            ),
        ),
        HelperFeature(
            "selected_load",
            (
                PrimitiveRequirement(VECTOR_ZERO_REQUIREMENT),
                PrimitiveRequirement(VECTOR_TO_ARRAY_REQUIREMENT),
                PrimitiveRequirement(VECTOR_FROM_ARRAY_REQUIREMENT),
            ),
        ),
        HelperFeature(
            "gather_narrow",
            (PrimitiveRequirement(INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT),),
        ),
        HelperFeature(
            "compress_store",
            (PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT),),
        ),
        HelperFeature(
            "mask_population_count",
            (PrimitiveRequirement(MASK_POPULATION_COUNT_REQUIREMENT),),
        ),
        HelperFeature(
            "integral_mask",
            (PrimitiveRequirement(MASK_TO_INTEGRAL_REQUIREMENT),),
        ),
        HelperFeature(
            "mask_from_integral",
            (PrimitiveRequirement(MASK_FROM_INTEGRAL_REQUIREMENT),),
        ),
    ),
)


EMPTY_HELPER_MANIFEST = BackendHelperManifest("none", ())


__all__ = (
    "BackendHelperManifest",
    "BackendHelperPlan",
    "CPP_HELPER_MANIFEST",
    "EMPTY_HELPER_MANIFEST",
    "HelperFeature",
    "PrimitiveRequirement",
    "RUST_HELPER_MANIFEST",
)
