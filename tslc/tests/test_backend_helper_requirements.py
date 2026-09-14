"""Backend helper plans share one catalog-resolved semantic binding."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from types import SimpleNamespace

import pytest

from tslc.backend.algorithm_surface import AlgorithmSemanticFamily
from tslc.backend.cpp_algorithm import (
    CppAlgorithmHelperForm,
    cpp_unavailable_algorithm_helper_declaration,
)
from tslc.backend.cpp_algorithm_plan import plan_cpp_algorithm_admission
from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    BackendHelperPlan,
    CPP_HELPER_MANIFEST,
    HelperFeature,
    PrimitiveRequirement,
    RUST_HELPER_MANIFEST,
)
from tslc.catalog.model import Catalog, PrimitiveMaskMode
from tslc.catalog.memory import MemoryAddressing, MemoryIndexedLaneExtent
from tslc.catalog.semantics import (
    COMPACTED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    VECTOR_ZERO_REQUIREMENT,
    PrimitiveOperation,
    PrimitiveProviderRequirement,
)


@dataclass(frozen=True)
class _Specialization:
    source_primitive_name: str
    mask_policy: PrimitiveMaskMode | None = None
    primitive_name: str = ""

    def __post_init__(self) -> None:
        if not self.primitive_name:
            object.__setattr__(self, "primitive_name", self.source_primitive_name)


class _EmittedProfile:
    def __init__(
        self,
        name: str,
        specializations: dict[str, tuple[_Specialization, ...]],
    ) -> None:
        self.profile = SimpleNamespace(name=name)
        self._specializations = specializations

    def specializations(
        self, backend_id: str
    ) -> dict[str, tuple[_Specialization, ...]]:
        assert backend_id == "cpp"
        return self._specializations


def test_plan_matches_resolved_source_identity_not_emitted_name(
    catalog: Catalog,
) -> None:
    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    requirement = CPP_HELPER_MANIFEST.requirements("masked_write")[0]
    by_emitted_name = {
        "backend_specific_masked_store": (
            _Specialization("store", PrimitiveMaskMode.PASS_THROUGH),
        )
    }

    assert not plan.missing_requirements(  # type: ignore[arg-type]
        "masked_write", by_emitted_name
    )
    assert requirement == PrimitiveRequirement(
        CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
        PrimitiveMaskMode.PASS_THROUGH,
    )


def test_mask_policy_remains_an_independent_helper_requirement(
    catalog: Catalog,
) -> None:
    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    missing = plan.missing_requirements(  # type: ignore[arg-type]
        "masked_write",
        {
            "store": (_Specialization("store"),),
        },
    )

    assert missing == CPP_HELPER_MANIFEST.requirements("masked_write")


def test_new_semantic_manifest_requirement_becomes_a_resolved_closure_root(
    catalog: Catalog,
) -> None:
    manifest = BackendHelperManifest(
        "fake",
        (
            HelperFeature(
                "helper",
                (
                    PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT),
                    PrimitiveRequirement(VECTOR_ZERO_REQUIREMENT),
                    PrimitiveRequirement(
                        CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
                        PrimitiveMaskMode.ZERO,
                    ),
                ),
            ),
        ),
    )

    plan = BackendHelperPlan.resolve(manifest, catalog)

    assert manifest.provider_requirements == (
        CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
        VECTOR_ZERO_REQUIREMENT,
    )
    assert plan.closure_seed_primitives == ("load", "set_zero")


def test_renamed_catalog_yields_renamed_closure_roots(catalog: Catalog) -> None:
    renamed = replace(
        catalog,
        primitives=tuple(
            replace(primitive, name="read_contiguous")
            if primitive.name == "load"
            else primitive
            for primitive in catalog.primitives
        ),
    )

    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, renamed)

    assert "read_contiguous" in plan.closure_seed_primitives
    assert "load" not in plan.closure_seed_primitives


def test_duplicate_semantic_provider_has_stable_ambiguity(catalog: Catalog) -> None:
    provider = catalog.resolve_primitive_provider(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT)
    assert not hasattr(provider, "code")
    duplicate = replace(provider, name="duplicate_contiguous_read")  # type: ignore[arg-type]
    ambiguous = replace(catalog, primitives=(*catalog.primitives, duplicate))

    first = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, ambiguous)
    second = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, ambiguous)

    assert tuple(item.message for item in first.ambiguity_diagnostics) == tuple(
        item.message for item in second.ambiguity_diagnostics
    )
    assert len(first.ambiguity_diagnostics) == 1
    assert "duplicate_contiguous_read" in first.ambiguity_diagnostics[0].message
    assert "load" in first.ambiguity_diagnostics[0].message


def test_same_signature_with_different_operation_is_not_a_provider(
    catalog: Catalog,
) -> None:
    provider = catalog.resolve_primitive_provider(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT)
    assert not hasattr(provider, "code")
    assert provider.operation is not None  # type: ignore[union-attr]
    unrelated = replace(  # type: ignore[arg-type]
        provider,
        name="same_shape_unrelated_operation",
        operation=replace(provider.operation, kind=PrimitiveOperation.CONVERT),
    )
    expanded = replace(catalog, primitives=(*catalog.primitives, unrelated))

    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, expanded)

    resolved = plan.provider(CPP_HELPER_MANIFEST.requirements("contiguous_read")[0])
    assert resolved is not None
    assert resolved.primitive_name == "load"
    assert not plan.ambiguity_diagnostics


def test_same_operation_shape_with_different_memory_semantics_is_not_a_provider(
    catalog: Catalog,
) -> None:
    provider = catalog.resolve_primitive_provider(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT)
    assert not hasattr(provider, "code")
    assert provider.memory is not None  # type: ignore[union-attr]
    unrelated = replace(  # type: ignore[arg-type]
        provider,
        name="indexed_single_pointer_read",
        memory=replace(
            provider.memory,
            addressing=MemoryAddressing.INDEXED,
            indexed_lane_extent=MemoryIndexedLaneExtent.VECTOR,
        ),
    )
    expanded = replace(catalog, primitives=(*catalog.primitives, unrelated))

    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, expanded)

    resolved = plan.provider(CPP_HELPER_MANIFEST.requirements("contiguous_read")[0])
    assert resolved is not None
    assert resolved.primitive_name == "load"
    assert not plan.ambiguity_diagnostics


def test_missing_provider_only_gaps_its_features(catalog: Catalog) -> None:
    without_compaction = replace(
        catalog,
        primitives=tuple(
            primitive
            for primitive in catalog.primitives
            if primitive.name != "compress_store"
        ),
    )

    plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, without_compaction)
    grouped: dict[str, list[_Specialization]] = {}
    for feature in CPP_HELPER_MANIFEST.features:
        for requirement in feature.requirements:
            provider = plan.provider(requirement)
            if provider is not None:
                grouped.setdefault(provider.primitive_name, []).append(
                    _Specialization(provider.primitive_name, requirement.mask_policy)
                )
    by_primitive = {name: tuple(items) for name, items in grouped.items()}

    assert len(plan.diagnostics) == 1
    assert plan.missing_requirements(  # type: ignore[arg-type]
        "compaction", by_primitive
    ) == (
        PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT),
    )
    assert all(
        not plan.missing_requirements(feature.name, by_primitive)  # type: ignore[arg-type]
        for feature in CPP_HELPER_MANIFEST.features
        if feature.name != "compaction"
    )
    admission = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (_EmittedProfile("synthetic", by_primitive),), plan
    )
    assert all(
        "no semantic provider in the corpus" in gap.reason
        for gap in admission.gaps
        if gap.feature_name == "compaction"
    )
    compaction = admission.helper(CppAlgorithmHelperForm.COMPACTION)
    assert compaction.provider is None
    assert compaction.emitted_callable_name == (
        "tslc_unavailable_algorithm_helper_compaction"
    )
    assert "compress_store" not in cpp_unavailable_algorithm_helper_declaration(
        compaction
    )


def test_static_helper_manifests_have_no_source_name_field() -> None:
    assert tuple(field.name for field in fields(PrimitiveRequirement)) == (
        "provider",
        "mask_policy",
    )
    assert all(
        isinstance(requirement.provider, PrimitiveProviderRequirement)
        for manifest in (CPP_HELPER_MANIFEST, RUST_HELPER_MANIFEST)
        for feature in manifest.features
        for requirement in feature.requirements
    )


def test_every_cpp_algorithm_helper_has_a_partial_profile_lookup_declaration(
    catalog: Catalog,
) -> None:
    helper_plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    specializations = {
        provider.primitive_name: (
            _Specialization(
                provider.primitive_name,
                requirement.mask_policy,
            ),
        )
        for feature in CPP_HELPER_MANIFEST.features
        for requirement in feature.requirements
        if (provider := helper_plan.provider(requirement)) is not None
    }
    plan = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (_EmittedProfile("synthetic", specializations),), helper_plan
    )

    declarations = tuple(
        cpp_unavailable_algorithm_helper_declaration(binding)
        for binding in plan.helper_bindings
    )

    assert len(declarations) == len(tuple(CppAlgorithmHelperForm))
    assert all(declaration.endswith("= delete;") for declaration in declarations)


def test_cpp_masked_store_uses_its_finalized_emitted_name(catalog: Catalog) -> None:
    helper_plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    requirement = CPP_HELPER_MANIFEST.requirements("masked_write")[0]
    provider = helper_plan.provider(requirement)
    assert provider is not None
    profile = _EmittedProfile(
        "synthetic",
        {
            "renamed_masked_write": (
                _Specialization(
                    provider.primitive_name,
                    requirement.mask_policy,
                    "renamed_masked_write",
                ),
            ),
        },
    )

    plan = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (profile,), helper_plan
    )

    binding = plan.helper(CppAlgorithmHelperForm.MASKED_WRITE)
    assert binding.provider == provider
    assert binding.emitted_callable_name == "renamed_masked_write"


def test_cpp_helper_callable_names_must_agree_across_profiles(
    catalog: Catalog,
) -> None:
    helper_plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    requirement = CPP_HELPER_MANIFEST.requirements("contiguous_read")[0]
    provider = helper_plan.provider(requirement)
    assert provider is not None
    profiles = (
        _EmittedProfile(
            "alpha",
            {
                "read_alpha": (
                    _Specialization(provider.primitive_name, None, "read_alpha"),
                )
            },
        ),
        _EmittedProfile(
            "beta",
            {
                "read_beta": (
                    _Specialization(provider.primitive_name, None, "read_beta"),
                )
            },
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "contiguous_read.*alpha=\\['read_alpha'\\].*"
            "beta=\\['read_beta'\\]"
        ),
    ):
        plan_cpp_algorithm_admission(profiles, helper_plan)  # type: ignore[arg-type]


def test_cpp_profile_local_gap_deletes_the_bound_callable(
    catalog: Catalog,
) -> None:
    helper_plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    grouped: dict[str, list[_Specialization]] = {}
    for feature in CPP_HELPER_MANIFEST.features:
        for requirement in feature.requirements:
            provider = helper_plan.provider(requirement)
            assert provider is not None
            grouped.setdefault(provider.primitive_name, []).append(
                _Specialization(provider.primitive_name, requirement.mask_policy)
            )
    complete = {name: tuple(items) for name, items in grouped.items()}
    partial = {
        name: items for name, items in complete.items() if name != "compress_store"
    }

    plan = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (
            _EmittedProfile("alpha", partial),
            _EmittedProfile("beta", complete),
        ),
        helper_plan,
    )

    compaction = plan.helper(CppAlgorithmHelperForm.COMPACTION)
    alpha = next(
        group for group in plan.unavailable_helpers if group.profile_name == "alpha"
    )
    assert compaction.emitted_callable_name == "compress_store"
    assert compaction in alpha.bindings
    assert " compress_store(" in cpp_unavailable_algorithm_helper_declaration(
        compaction
    )


def test_cpp_algorithm_admission_is_granular_around_compaction(
    catalog: Catalog,
) -> None:
    helper_plan = BackendHelperPlan.resolve(CPP_HELPER_MANIFEST, catalog)
    requirement_specs = (
        _Specialization(provider.primitive_name, requirement.mask_policy)
        for feature in CPP_HELPER_MANIFEST.features
        for requirement in feature.requirements
        if requirement.provider != COMPACTED_VECTOR_STORE_REQUIREMENT
        if (provider := helper_plan.provider(requirement)) is not None
    )
    grouped: dict[str, list[_Specialization]] = {}
    for specialization in requirement_specs:
        grouped.setdefault(specialization.source_primitive_name, []).append(
            specialization
        )
    specializations = {name: tuple(group) for name, group in grouped.items()}
    profile = _EmittedProfile("synthetic", specializations)

    plan = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (profile,), helper_plan
    )

    assert plan.supported
    assert tuple(header.semantic_family for header in plan.family_headers) == tuple(
        AlgorithmSemanticFamily
    )
    assert "transform_unary" in plan.admitted_family_names
    assert "predicate_unary" in plan.admitted_family_names
    absent = {
        family
        for family in (
            "select_unary",
            "select_binary",
            "select_masked_unary",
            "select_masked_binary",
            "select_indices_unary",
            "select_indices_binary",
            "select_masked_indices_unary",
            "select_masked_indices_binary",
            "select_selected_indices_unary",
            "select_selected_indices_binary",
        )
        if family not in plan.admitted_family_names
    }
    assert absent == {
        "select_unary",
        "select_binary",
        "select_masked_unary",
        "select_masked_binary",
    }
    compaction_requirement = PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT)
    compaction_gaps = tuple(
        gap for gap in plan.gaps if gap.feature_name == "compaction"
    )
    assert {
        (gap.backend_id, gap.profile_name, gap.family_name, gap.requirement)
        for gap in compaction_gaps
    } == {
        ("cpp", "synthetic", family_name, compaction_requirement)
        for family_name in absent
    }
    assert all(
        "resolved primitive 'compress_store' has no profile specialization"
        in gap.reason
        for gap in compaction_gaps
    )

    specializations["compress_store"] = (_Specialization("compress_store"),)
    completed = plan_cpp_algorithm_admission(  # type: ignore[arg-type]
        (_EmittedProfile("synthetic", specializations),), helper_plan
    )
    assert set(absent) <= set(completed.admitted_family_names)
