"""Rust facade orchestration and corpus-integration tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rust_api_test_support import _plan, _spec
from tslc.api import generate_project
from tslc.backend.rust_api_model import (
    RustFacadeReceiverKind,
    RustFacadeTraitRhsKind,
)
from tslc.backend.rust_api_planner import (
    plan_rust_facade,
    validate_rust_facade,
)
from tslc.backend.rust_static_selection import plan_rust_static_selection
from tslc.catalog.arithmetic import ArithmeticOperation
from tslc.compiler_assets import RenderAssets
from tslc.diagnostics import has_errors
from tslc.render.rust_facade import rust_facade_module
from tslc.render.rust_facade_comprehensive import render_comprehensive_facade


def test_reduced_inventory_validation_does_not_require_facade_core_closure() -> None:
    spec = _spec("isolated_semantic_primitive")
    static = _plan(spec)

    assert validate_rust_facade((), static) == ()


def test_current_lowered_families_plan_without_reopening_the_catalog(
    data_root: Path,
    machine_profiles_path: Path,
    render_assets: RenderAssets,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "div",
            "equal",
            "nequal",
            "less_than",
            "less_than_or_equal",
            "greater_than",
            "greater_than_or_equal",
            "select",
            "convert_lanes",
            "reinterpret",
            "shift_left_wrapping",
            "shift_right_wrapping",
        ],
        profiles=["scalar", "sse2", "avx", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }

    assert validate_rust_facade(result.emitted_profiles, static) == ()
    plan = plan_rust_facade(result.emitted_profiles, static)
    reversed_profiles = tuple(reversed(result.emitted_profiles))
    reversed_static = plan_rust_static_selection(reversed_profiles)
    reversed_plan = plan_rust_facade(reversed_profiles, reversed_static)

    assert reversed_plan == plan
    assert rust_facade_module(reversed_plan, render_assets) == (
        rust_facade_module(plan, render_assets)
    )

    assert any(
        trait.trait_path == "core::ops::Add"
        and trait.operation is ArithmeticOperation.ADDITION
        and trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        for trait in plan.trait_implementations
    )
    assert any(method.public_name == "simd_eq" for method in plan.curated_methods)
    assert {
        method.public_name
        for method in plan.curated_methods
        if method.receiver_kind is RustFacadeReceiverKind.VECTOR
    } >= {
        "simd_eq",
        "simd_ne",
        "simd_lt",
        "simd_le",
        "simd_gt",
        "simd_ge",
        "cast",
    }
    cast = next(
        method for method in plan.curated_methods if method.public_name == "cast"
    )
    assert {pair.target_type_tag for pair in cast.conversion_pairs} == {
        "f32",
        "f64",
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    }
    assert ("si32", 4) in cast.shape_keys
    assert {
        (conversion.float_type_tag, conversion.bits_type_tag)
        for conversion in plan.bit_conversions
    } == {("f32", "ui32"), ("f64", "ui64")}
    assert all(
        conversion.to_bits.source_type_tag == conversion.float_type_tag
        and conversion.to_bits.target_type_tag == conversion.bits_type_tag
        and conversion.from_bits.source_type_tag == conversion.bits_type_tag
        and conversion.from_bits.target_type_tag == conversion.float_type_tag
        and all(
            vector.type_tag == conversion.to_bits.source_type_tag
            for delegate in conversion.to_bits.delegates
            for vector in delegate.vectors
        )
        and all(
            vector.type_tag == conversion.from_bits.source_type_tag
            for delegate in conversion.from_bits.delegates
            for vector in delegate.vectors
        )
        for conversion in plan.bit_conversions
    )
    assert any(
        pair.shape_keys
        and {delegate.profile_name for delegate in pair.delegates}
        > {None}
        for pair in cast.conversion_pairs
    )
    assert any(
        method.public_name == "select"
        and method.receiver_kind is RustFacadeReceiverKind.MASK
        for method in plan.curated_methods
    )
    assert any(
        method.public_name == "shift_left_wrapping_each"
        for method in plan.comprehensive_methods
    )
    assert any(
        shape.type_tag == "si32"
        and shape.lanes == 8
        and {item.profile_name for item in shape.representations}
        == {None, "avx2"}
        for shape in plan.shapes
    )
    si32_native = next(alias for alias in plan.native_aliases if alias.type_tag == "si32")
    assert next(
        selection.lanes
        for selection in si32_native.selections
        if selection.profile_name == "avx"
    ) == 4
    expected_native_profiles = {None} | {
        profile.profile_name for profile in static.profiles
    }
    assert all(
        {selection.profile_name for selection in alias.selections}
        == expected_native_profiles
        for alias in plan.native_aliases
    )
    assert {
        trait.rhs_kind
        for trait in plan.trait_implementations
        if trait.trait_path in {"core::ops::Shl", "core::ops::Shr"}
    } == {
        RustFacadeTraitRhsKind.SAME_TYPE,
        RustFacadeTraitRhsKind.SCALAR,
    }
    assert any(
        trait.trait_path == "core::ops::Div"
        and ("si32", 4) in trait.shape_keys
        for trait in plan.trait_implementations
    )
    assert all(
        method.implementation_arms
        for method in plan.comprehensive_methods
    )
    assert all(
        method.implementation_arms
        or method.conversion_implementation_arms
        for method in plan.curated_methods
    )
    assert all(
        conversion.implementation_arms
        for conversion in plan.bit_conversions
    )
    assert all(
        (
            trait.generic_mask_implementation is not None
            and not trait.implementations
        )
        if trait.receiver_kind is RustFacadeReceiverKind.MASK
        else (
            bool(trait.implementations)
            and all(
                implementation.canonical_arms
                for implementation in trait.implementations
            )
        )
        for trait in plan.trait_implementations
    )
    assert all(
        call.call.delegate is not None
        for arm in plan.core_implementation_arms
        for call in arm.calls
    )
    assert all(
        arm.call.generic_arguments[
            -len(arm.call.delegate.overload_parameter_positions) :
        ]
        == ("_",) * len(arm.call.delegate.overload_parameter_positions)
        for trait in plan.trait_implementations
        for implementation in trait.implementations
        for arm in implementation.canonical_arms
        if arm.call.delegate.overload_parameter_positions
    )
    comparison = next(
        method
        for method in plan.curated_methods
        if method.public_name == "simd_eq"
        and any(
            sum(
                arm.shape == candidate.shape
                for candidate in method.implementation_arms
            )
            > 1
            for arm in method.implementation_arms
        )
    )
    removed_arm = next(
        arm
        for arm in comparison.implementation_arms
        if sum(
            arm.shape == candidate.shape
            for candidate in comparison.implementation_arms
        )
        > 1
    )
    with pytest.raises(ValueError, match="cover every representation"):
        replace(
            plan,
            curated_methods=tuple(
                replace(
                    method,
                    implementation_arms=tuple(
                        arm
                        for arm in method.implementation_arms
                        if arm is not removed_arm
                    ),
                )
                if method is comparison
                else method
                for method in plan.curated_methods
            ),
        )
    assert {
        delegate.role
        for delegate in plan.core_delegates
        if delegate.type_tag == "si32"
        and delegate.lanes == 8
        and delegate.profile_name == "avx2"
    } >= {
        "vector_splat",
        "vector_from_array",
        "vector_to_array",
        "load",
        "store",
        "mask_from_integral",
        "mask_to_integral",
    }
    assert next(
        delegate.extension_name
        for delegate in plan.core_delegates
        if delegate.role == "store"
        and delegate.type_tag == "si32"
        and delegate.lanes == 8
        and delegate.profile_name == "avx2"
    ) == "avx2"
    assert next(
        delegate.extension_name
        for delegate in plan.core_delegates
        if delegate.role == "store"
        and delegate.type_tag == "si32"
        and delegate.lanes == 8
        and delegate.profile_name is None
    ) == "generic"
    assert next(
        delegate.extension_name
        for delegate in plan.core_delegates
        if delegate.role == "store"
        and delegate.type_tag == "si32"
        and delegate.lanes == 1
        and delegate.profile_name is None
    ) == "scalar"
    facade = artifacts["rust/src/tsl_facade.rs"]
    library = artifacts["rust/src/lib.rs"]
    assert "pub fn add(self, right: Simd<i32, 4>)" in facade
    assert "pub fn add_masked(" in facade
    assert "pub fn add_masked_zero(" in facade
    assert "pub fn convert_lanes<U>(self)" in facade
    assert "pub unsafe fn store<T, const N: usize, const ALIGNED: bool>" in facade
    assert "load_masked, load_masked_zero" in library
    assert "macro_rules! impl_mask_binary_operator" not in facade


def test_scalar_only_native_aliases_use_the_scalar_lane(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)

    plan = plan_rust_facade(result.emitted_profiles, static)

    assert {alias.type_tag for alias in plan.native_aliases} == {
        "f32",
        "f64",
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    }
    assert all(
        tuple(
            (selection.profile_name, selection.lanes)
            for selection in alias.selections
        )
        == ((None, 1),)
        for alias in plan.native_aliases
    )


def test_facade_owner_equivalence_and_wrapper_audit(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "shift_left_wrapping", "store"],
        profiles=["scalar", "sse2", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)
    plan = plan_rust_facade(result.emitted_profiles, static)
    rendered = render_comprehensive_facade(plan)
    lowered_sources = {
        spec.source_primitive_name
        for profile in result.emitted_profiles
        for specs in profile.specializations("rust").values()
        for spec in specs
    } | {
        spec.source_primitive_name
        for _name, specs in static.fallback_module.primitive_specializations
        for spec in specs
    }
    lowered_names = {
        spec.primitive_name
        for profile in result.emitted_profiles
        for specs in profile.specializations("rust").values()
        for spec in specs
    } | {
        spec.primitive_name
        for _name, specs in static.fallback_module.primitive_specializations
        for spec in specs
    }

    assert plan.comprehensive_methods
    for method in plan.comprehensive_methods:
        assert method.source_primitive_name in lowered_sources
        assert all(delegate.primitive_name in lowered_names for delegate in method.delegates)
        assert f"fn {method.public_name}" in rendered.public_items

    assert rendered.private_impls.count("fn call") == sum(
        len(method.implementation_arms)
        for method in plan.comprehensive_methods
    )
    assert rendered.public_items.count("pub fn ") + rendered.public_items.count(
        "pub unsafe fn "
    ) == sum(
        1
        if method.receiver_kind is RustFacadeReceiverKind.FREE
        else len(method.public_shapes)
        for method in plan.comprehensive_methods
    )
    delegate_lines = tuple(
        line
        for line in rendered.private_impls.splitlines()
        if "crate::tsl_" in line and "::<" in line
    )
    assert rendered.private_impls.count("fn call") == len(delegate_lines)
    assert rendered.public_items.count("pub fn ") + rendered.public_items.count(
        "pub unsafe fn "
    ) == rendered.public_items.count("::call")
    for forbidden in (
        "\n        for ",
        "\n        while ",
        "core::arch",
        "std::arch",
        "rem_euclid",
    ):
        assert forbidden not in rendered.private_impls
        assert forbidden not in rendered.public_items
