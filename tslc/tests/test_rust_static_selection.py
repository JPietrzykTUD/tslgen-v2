"""Compile-target selection for generated Rust representations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
    plan_rust_static_selection,
    validate_rust_static_selection,
)
from tslc.diagnostics import has_errors


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


def test_static_selection_uses_source_target_requirements(
    rust_static_plan: RustStaticSelectionPlan,
) -> None:
    assert tuple(profile.profile_name for profile in rust_static_plan.profiles) == (
        "sse2",
        "avx2",
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
    assert sse2.stronger_requirements == (avx2.requirement,)
    assert avx2.stronger_requirements == ()


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
        "TSL-BACKEND-RUST-AMBIGUOUS-TARGET-PROFILES"
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
