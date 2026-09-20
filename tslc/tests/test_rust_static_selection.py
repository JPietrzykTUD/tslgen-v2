"""Compile-target selection for generated Rust representations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import BackendHelperPlan
from tslc.backend.rust_algorithm_plan import plan_rust_algorithm
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
    plan_rust_static_selection,
    validate_rust_static_selection,
)
from tslc.diagnostics import has_errors
from tslc.render.rust_static_selection import (
    rust_static_fallback_cfg,
    rust_static_profile_cfg,
    rust_target_requirement_cfg,
)


@pytest.fixture(scope="module")
def rust_static_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar", "sse2", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    return result


@pytest.fixture(scope="module")
def rust_static_plan(rust_static_result) -> RustStaticSelectionPlan:
    return plan_rust_static_selection(rust_static_result.emitted_profiles)


def _mapping(
    mappings: tuple[RustStaticVectorMapping, ...],
    type_tag: str,
    lanes: int,
) -> RustStaticVectorMapping:
    return next(
        mapping
        for mapping in mappings
        if mapping.type_tag == type_tag and mapping.lanes == lanes
    )


def _with_machine_profile(
    emitted: EmittedProfile,
    **changes: object,
) -> EmittedProfile:
    return EmittedProfile(
        profile=replace(emitted.profile, **changes),
        specializations_by_backend=emitted.specializations_by_backend,
        extensions=emitted.extensions,
        profile_family=emitted.profile_family,
        immediate_split_names=frozenset(),
    )


def test_static_selection_uses_source_target_requirements(
    rust_static_plan: RustStaticSelectionPlan,
) -> None:
    assert tuple(profile.profile_name for profile in rust_static_plan.profiles) == (
        "avx2",
        "sse2",
    )
    sse2 = rust_static_plan.profile("sse2")
    avx2 = rust_static_plan.profile("avx2")
    assert sse2 is not None
    assert avx2 is not None
    assert sse2.requirement.target_arch == "x86_64"
    assert sse2.requirement.target_features == ("sse", "sse2")
    assert avx2.requirement.target_features == (
        "avx",
        "avx2",
        "rdrand",
        "sse",
        "sse2",
        "sse4.1",
        "sse4.2",
        "ssse3",
    )
    assert sse2.higher_priority_requirements == (avx2.requirement,)
    assert avx2.higher_priority_requirements == ()


def test_static_selection_uses_only_exact_width_available_hardware(
    rust_static_plan: RustStaticSelectionPlan,
) -> None:
    sse2 = rust_static_plan.profile("sse2")
    avx2 = rust_static_plan.profile("avx2")
    assert sse2 is not None
    assert avx2 is not None

    sse_lanes = _mapping(sse2.mappings, "si32", 4)
    sse_wide = _mapping(sse2.mappings, "si32", 8)
    avx_lanes = _mapping(avx2.mappings, "si32", 8)
    assert sse_lanes.extension_name == "sse"
    assert sse_lanes.vector_spelling == "Simd<i32, Sse>"
    assert sse_wide.extension_name is None
    assert sse_wide.vector_spelling == "Simd<i32, Generic<8>>"
    assert avx_lanes.extension_name == "avx2"
    assert avx_lanes.vector_spelling == "Simd<i32, Avx2>"


def test_algorithm_native_mapping_reuses_static_selection_exactly(
    rust_static_result,
    rust_static_plan: RustStaticSelectionPlan,
    rust_helper_plan: BackendHelperPlan,
) -> None:
    static_avx2 = rust_static_plan.profile("avx2")
    assert static_avx2 is not None
    static_i32 = next(
        mapping
        for mapping in static_avx2.native_mappings
        if mapping.type_tag == "si32"
    )
    assert static_i32.extension_name == "avx2"
    assert any(
        mapping.type_tag == "si32" and mapping.extension_name == "sse"
        for mapping in static_avx2.mappings
    )

    algorithm = plan_rust_algorithm(
        rust_static_result.emitted_profiles,
        rust_static_plan,
        rust_helper_plan,
    )
    algorithm_avx2 = algorithm.profile("avx2")
    assert algorithm_avx2 is not None
    assert algorithm_avx2.static_mappings is static_avx2.mappings
    assert algorithm_avx2.native_mappings is static_avx2.native_mappings
    assert next(
        mapping
        for mapping in algorithm_avx2.native_mappings
        if mapping.type_tag == "si32"
    ) is static_i32


def test_static_selection_fallback_preserves_supported_lane_counts(
    rust_static_plan: RustStaticSelectionPlan,
) -> None:
    fallback_one = _mapping(rust_static_plan.fallback_mappings, "si32", 1)
    fallback_four = _mapping(rust_static_plan.fallback_mappings, "si32", 4)
    fallback_eight = _mapping(rust_static_plan.fallback_mappings, "si32", 8)
    assert fallback_four.vector_spelling == "Simd<i32, Generic<4>>"
    assert fallback_eight.vector_spelling == "Simd<i32, Generic<8>>"
    assert fallback_four.uses_sized_vector
    assert fallback_eight.uses_sized_vector
    assert not fallback_one.uses_sized_vector
    assert not fallback_four.uses_hardware
    assert not fallback_eight.uses_hardware
    assert rust_static_plan.fallback_module.metadata_profile_name == "target_fallback"
    assert rust_static_plan.fallback_module.metadata_profile_family == "fallback"
    fallback_primitives = dict(
        rust_static_plan.fallback_module.primitive_specializations
    )
    fallback_extensions = dict(rust_static_plan.fallback_module.extensions)
    assert "add" in fallback_primitives
    assert all(
        fallback_extensions[spec.extension_name]
        .family_capability.implementation_fallback
        for specializations in fallback_primitives.values()
        for spec in specializations
    )


def test_generated_rust_selects_profiles_by_cfg_not_cargo_features(
    rust_static_result,
) -> None:
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in rust_static_result.artifacts.artifacts
    }
    cargo = artifacts["rust/Cargo.toml"]
    lib = artifacts["rust/src/lib.rs"]
    fallback = artifacts["rust/src/tsl_target_fallback.rs"]

    assert "default = []" in cargo
    assert "sse2 = []" not in cargo
    assert "avx2 = []" not in cargo
    assert '#[cfg(all(all(target_arch = "x86_64"' in lib
    assert 'target_feature = "avx2"' in lib
    assert 'target_feature = "rdrand"' in lib
    assert "pub use crate::tsl_target_fallback as profile;" in lib
    assert "#![cfg(" not in fallback
    assert "#[doc(hidden)]\npub mod tsl_target_fallback;" in lib
    assert '#[cfg(all(not(doc), not(any(all(target_arch = "x86_64"' in lib
    assert "impl<const LANES: usize> AddImpl for Simd<i32, Generic<LANES>>" in fallback


def test_static_selection_rejects_missing_hardware_target_arch(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    assert emitted.profile_family is not None
    backends = dict(emitted.profile_family.backends)
    backends["rust"] = replace(backends["rust"], target_arch=None)
    invalid = EmittedProfile(
        profile=emitted.profile,
        specializations_by_backend=emitted.specializations_by_backend,
        extensions=emitted.extensions,
        profile_family=replace(emitted.profile_family, backends=backends),
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_rust_static_selection((invalid,))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-MISSING-TARGET-ARCH"
    }


def test_static_selection_rejects_ambiguous_compile_targets(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    alias = EmittedProfile(
        profile=replace(emitted.profile, name="sse2_alias"),
        specializations_by_backend=emitted.specializations_by_backend,
        extensions=emitted.extensions,
        profile_family=emitted.profile_family,
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_rust_static_selection((emitted, alias))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-DUPLICATE-TARGET-PROFILES"
    }


def test_static_selection_orders_incomparable_targets_by_typed_priority(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    alpha = _with_machine_profile(
        emitted,
        name="alpha",
        features=frozenset((*emitted.profile.features, "alpha")),
        backend_selection_priority={"rust": 10},
    )
    beta = _with_machine_profile(
        emitted,
        name="beta",
        features=frozenset((*emitted.profile.features, "beta")),
        backend_selection_priority={"rust": 20},
    )

    plan = plan_rust_static_selection((alpha, beta))
    reversed_plan = plan_rust_static_selection((beta, alpha))

    assert plan == reversed_plan
    assert tuple(profile.profile_name for profile in plan.profiles) == (
        "beta",
        "alpha",
    )
    beta_selection, alpha_selection = plan.profiles
    assert beta_selection.selection_priority == 20
    assert beta_selection.higher_priority_requirements == ()
    assert alpha_selection.selection_priority == 10
    assert alpha_selection.higher_priority_requirements == (
        beta_selection.requirement,
    )
    assert rust_static_profile_cfg(beta_selection) == rust_target_requirement_cfg(
        beta_selection.requirement
    )
    assert rust_static_profile_cfg(alpha_selection) == (
        "all("
        + rust_target_requirement_cfg(alpha_selection.requirement)
        + ", not(any("
        + rust_target_requirement_cfg(beta_selection.requirement)
        + ")))"
    )
    assert rust_static_fallback_cfg(plan) == (
        "not(any("
        + ", ".join(
            rust_target_requirement_cfg(selection.requirement)
            for selection in plan.profiles
        )
        + "))"
    )


def test_static_selection_accepts_an_additive_superset_profile(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    alpha = _with_machine_profile(
        emitted,
        name="alpha",
        features=frozenset((*emitted.profile.features, "alpha")),
        backend_selection_priority={"rust": 10},
    )
    beta = _with_machine_profile(
        emitted,
        name="beta",
        features=frozenset((*emitted.profile.features, "beta")),
        backend_selection_priority={"rust": 20},
    )
    future = _with_machine_profile(
        emitted,
        name="future",
        features=frozenset((*emitted.profile.features, "alpha", "beta")),
        backend_selection_priority={"rust": 30},
    )

    plan = plan_rust_static_selection((alpha, beta, future))
    reversed_plan = plan_rust_static_selection((future, beta, alpha))

    assert plan == reversed_plan
    assert tuple(selection.profile_name for selection in plan.profiles) == (
        "future",
        "beta",
        "alpha",
    )


def test_static_selection_feature_superset_precedes_higher_numeric_priority(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    subset = _with_machine_profile(
        emitted,
        name="subset",
        backend_selection_priority={"rust": 100},
    )
    superset = _with_machine_profile(
        emitted,
        name="superset",
        features=frozenset((*emitted.profile.features, "extra")),
        backend_selection_priority={"rust": 1},
    )

    plan = plan_rust_static_selection((subset, superset))

    assert tuple(profile.profile_name for profile in plan.profiles) == (
        "superset",
        "subset",
    )
    assert plan.profile("subset").higher_priority_requirements == (
        plan.profile("superset").requirement,
    )


def test_static_selection_requires_priority_for_incomparable_targets(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    alpha = _with_machine_profile(
        emitted,
        name="alpha",
        features=frozenset((*emitted.profile.features, "alpha")),
        backend_selection_priority={},
    )
    beta = _with_machine_profile(
        emitted,
        name="beta",
        features=frozenset((*emitted.profile.features, "beta")),
        backend_selection_priority={"rust": 20},
    )

    diagnostics = validate_rust_static_selection((alpha, beta))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-MISSING-SELECTION-PRIORITY"
    }
    assert "backend_selection_priority.rust for 'alpha'" in diagnostics[0].message


def test_static_selection_rejects_duplicate_priorities_within_architecture(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    alpha = _with_machine_profile(
        emitted,
        name="alpha",
        features=frozenset((*emitted.profile.features, "alpha")),
        backend_selection_priority={"rust": 10},
    )
    beta = _with_machine_profile(
        emitted,
        name="beta",
        features=frozenset((*emitted.profile.features, "beta")),
        backend_selection_priority={"rust": 10},
    )

    diagnostics = validate_rust_static_selection((alpha, beta))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-DUPLICATE-SELECTION-PRIORITY"
    }


def test_static_selection_rejects_duplicate_rust_feature_spellings(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    invalid = EmittedProfile(
        profile=replace(
            emitted.profile,
            alternatives={"sse": "duplicate", "sse2": "duplicate"},
        ),
        specializations_by_backend=emitted.specializations_by_backend,
        extensions=emitted.extensions,
        profile_family=emitted.profile_family,
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_rust_static_selection((invalid,))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-DUPLICATE-TARGET-FEATURE-SPELLING"
    }


def test_static_selection_rejects_partially_missing_register_architecture(
    rust_static_result,
) -> None:
    emitted = next(
        profile
        for profile in rust_static_result.emitted_profiles
        if profile.profile.name == "sse2"
    )
    extensions = dict(emitted.extensions)
    sse = extensions["sse"]
    backend_metadata = dict(sse.metadata.backend)
    backend_metadata["rust"] = replace(
        backend_metadata["rust"],
        arch_module=None,
    )
    extensions["sse"] = replace(
        sse,
        metadata=replace(sse.metadata, backend=backend_metadata),
    )
    invalid = EmittedProfile(
        profile=emitted.profile,
        specializations_by_backend=emitted.specializations_by_backend,
        extensions=extensions,
        profile_family=emitted.profile_family,
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_rust_static_selection((invalid,))

    assert {diagnostic.code for diagnostic in diagnostics} == {
        "TSL-BACKEND-RUST-TARGET-ARCH-MISMATCH"
    }
