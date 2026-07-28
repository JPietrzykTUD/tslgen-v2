"""Typed planning and generated proof for Rust whole-algorithm dispatch."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.rust_api_planner import plan_rust_facade
from tslc.backend.rust_dispatch import (
    RustDispatchAlgorithm,
    RustDispatchKernel,
    RustDispatchOperationKind,
    RustDispatchPlan,
    plan_rust_dispatch,
    validate_rust_dispatch_plan,
)
from tslc.backend.rust_static_selection import plan_rust_static_selection
from tslc.catalog.arithmetic import ArithmeticOperation
from tslc.diagnostics import has_errors


@pytest.fixture(scope="module")
def rust_dispatch_inputs(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar", "sse2", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)
    facade = plan_rust_facade(result.emitted_profiles, static)
    return result, static, facade


@pytest.fixture(scope="module")
def rust_dispatch_plan(rust_dispatch_inputs) -> RustDispatchPlan:
    result, static, facade = rust_dispatch_inputs
    return plan_rust_dispatch(result.emitted_profiles, static, facade)


def test_dispatch_plan_carries_complete_typed_surface(
    rust_dispatch_plan: RustDispatchPlan,
) -> None:
    representative = rust_dispatch_plan.representative_slots
    assert representative is not None
    builtin, stateful = representative

    assert builtin.algorithm is RustDispatchAlgorithm.TRANSFORM_BINARY
    assert builtin.operation.kind is RustDispatchOperationKind.BUILTIN_ZST
    assert builtin.operation.kernel is RustDispatchKernel.BINARY
    assert builtin.operation.public_name == "Add"
    assert builtin.operation.operation is ArithmeticOperation.ADDITION
    assert builtin.type_tag == "si32"
    assert builtin.base_spelling == "i32"
    assert tuple(
        (parameter.name, parameter.type_spelling)
        for parameter in builtin.public_signature.parameters
    ) == (
        ("operation", "Op"),
        ("left", "&[i32]"),
        ("right", "&[i32]"),
        ("output", "&mut [i32]"),
    )

    assert stateful.operation.kind is RustDispatchOperationKind.STATEFUL_MUTABLE
    assert stateful.operation.kernel is RustDispatchKernel.BINARY
    assert stateful.operation.operation is None
    assert stateful.public_signature == builtin.public_signature
    assert stateful.ordered_candidates == builtin.ordered_candidates
    assert stateful.generic_baseline == builtin.generic_baseline
    assert {
        slot.type_tag
        for slot in rust_dispatch_plan.slots
        if slot.operation.kind is RustDispatchOperationKind.BUILTIN_ZST
    } == {
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
    assert rust_dispatch_plan.skips == ()


def test_dispatch_plan_orders_guarded_hardware_before_mandatory_generic(
    rust_dispatch_plan: RustDispatchPlan,
) -> None:
    representative = rust_dispatch_plan.representative_slots
    assert representative is not None
    builtin, _stateful = representative
    assert builtin.generic_baseline.entry_index == 0
    assert builtin.generic_baseline.profile_name is None
    assert builtin.generic_baseline.requirement is None
    assert not builtin.generic_baseline.mapping.uses_hardware
    assert builtin.generic_baseline.mapping.lanes == 4

    assert len(builtin.ordered_candidates) == 2
    avx2, sse2 = builtin.ordered_candidates
    assert avx2.entry_index == 1
    assert avx2.profile_name == "avx2"
    assert avx2.requirement is not None
    assert avx2.requirement.target_arch == "x86_64"
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
    assert avx2.mapping.uses_hardware
    assert avx2.mapping.extension_name == "avx2"
    assert sse2.entry_index == 2
    assert sse2.profile_name == "sse2"
    assert sse2.mapping.extension_name == "sse"


def test_dispatch_planning_uses_semantics_not_source_primitive_name(
    rust_dispatch_inputs,
) -> None:
    result, static, facade = rust_dispatch_inputs
    operation_values = tuple(
        (
            replace(value, source_primitive_name="renamed_source")
            if value.operation is ArithmeticOperation.ADDITION
            else value
        )
        for value in facade.operation_values
    )
    trait_implementations = tuple(
        (
            replace(trait, source_primitive_name="renamed_source")
            if trait.operation is ArithmeticOperation.ADDITION
            else trait
        )
        for trait in facade.trait_implementations
    )
    renamed = replace(
        facade,
        operation_values=operation_values,
        trait_implementations=trait_implementations,
    )

    plan = plan_rust_dispatch(result.emitted_profiles, static, renamed)

    representative = plan.representative_slots
    assert representative is not None
    builtin, _stateful = representative
    assert builtin.operation.source_primitive_name == "renamed_source"
    assert builtin.generic_baseline.delegate_primitive_name == "add"


def test_dispatch_plan_validation_rejects_foreign_facts(
    rust_dispatch_inputs,
    rust_dispatch_plan: RustDispatchPlan,
) -> None:
    result, static, facade = rust_dispatch_inputs
    validate_rust_dispatch_plan(
        result.emitted_profiles,
        static,
        facade,
        rust_dispatch_plan,
    )

    with pytest.raises(ValueError, match="does not match"):
        validate_rust_dispatch_plan(
            result.emitted_profiles,
            static,
            facade,
            RustDispatchPlan(()),
        )


def test_dispatch_planning_requires_generic_algorithm_coverage(
    rust_dispatch_inputs,
) -> None:
    result, static, facade = rust_dispatch_inputs
    incomplete_static = replace(
        static,
        fallback_module=replace(
            static.fallback_module,
            primitive_specializations=(),
        ),
    )

    assert (
        plan_rust_dispatch(
            result.emitted_profiles,
            incomplete_static,
            facade,
        ).slots
        == ()
    )


def test_dispatch_plan_reports_incomplete_profile_combinations(
    rust_dispatch_inputs,
) -> None:
    result, static, facade = rust_dispatch_inputs
    traits = tuple(
        (
            replace(
                trait,
                delegates=tuple(
                    delegate
                    for delegate in trait.delegates
                    if delegate.profile_name != "avx2"
                ),
            )
            if trait.operation is ArithmeticOperation.ADDITION
            else trait
        )
        for trait in facade.trait_implementations
    )

    plan = plan_rust_dispatch(
        result.emitted_profiles,
        static,
        replace(facade, trait_implementations=traits),
    )

    avx2_skips = tuple(
        skip for skip in plan.skips if skip.profile_name == "avx2"
    )
    assert len(avx2_skips) == 10
    assert {skip.reason for skip in avx2_skips} == {
        "profile has no addition kernel delegate"
    }


def test_dispatch_plan_type_annotations_are_frozen(
    rust_dispatch_plan: RustDispatchPlan,
) -> None:
    with pytest.raises(AttributeError):
        rust_dispatch_plan.slots = ()  # type: ignore[misc]


def test_generated_dispatch_preserves_public_and_whole_loop_boundaries(
    rust_dispatch_inputs,
) -> None:
    result, _static, _facade = rust_dispatch_inputs
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
    dispatch = artifacts["rust/src/tsl_dispatch.rs"]
    external = artifacts["rust/tests/runtime_dispatch.rs"]
    library = artifacts["rust/src/lib.rs"]
    hardware = artifacts["rust/src/tsl_avx2.rs"]

    assert '#[cfg(feature = "runtime-dispatch")]' in library
    assert "mod tsl_dispatch;" in library
    assert "pub use tsl_dispatch::{algorithms, ops, Dispatcher};" in library
    assert (
        '#[cfg(all(all(feature = "runtime-dispatch", '
        'target_arch = "x86_64"), not('
    ) in library
    assert "mod tsl_avx2;" in library
    assert 'feature = "runtime-dispatch"' in hardware
    assert 'target_arch = "x86_64"' in hardware
    assert "pub struct Dispatcher" in dispatch
    assert "pub mod ops" in dispatch
    assert "pub struct Add;" in dispatch
    assert "pub mod algorithms" in dispatch
    assert "std::sync::OnceLock<Dispatcher>" in dispatch
    assert "std::is_x86_feature_detected!" in dispatch
    assert dispatch.count("Exactly one indirect whole-loop entry") >= 10
    assert '#[target_feature(enable = "sse2")]' in dispatch
    assert "Box<" not in dispatch
    assert "dyn " not in dispatch
    assert "Any" not in dispatch
    public_boundary = dispatch[
        dispatch.index("pub struct Dispatcher") : dispatch.index(
            "type BinaryEntry"
        )
    ]
    assert "Avx2" not in public_boundary
    assert "Sse" not in public_boundary
    assert "tsl_avx2" not in public_boundary
    assert "Dispatcher::new().transform_binary" in external
    assert "algorithms::transform_binary" in external
    assert "impl<Vector> BinaryKernel<Vector> for StatefulAdd" in external

    entries = dispatch[
        dispatch.index("unsafe fn transform_binary_f32_generic") :
        dispatch.index("#[cfg(test)]\nstatic ENTRY_CALLS")
    ]
    assert ".detect(" not in entries
    assert "select_table(" not in entries


@pytest.mark.generated_build
def test_generated_dispatch_executes(
    rust_dispatch_inputs,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is unavailable")
    result, _static, _facade = rust_dispatch_inputs

    report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(report.diagnostics), report.diagnostics
    completed = subprocess.run(
        (
            cargo,
            "test",
            "--quiet",
            "--lib",
            "--test",
            "runtime_dispatch",
            "--features",
            "runtime-dispatch",
        ),
        cwd=tmp_path / "rust",
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "4 passed" in completed.stdout
    assert "2 passed" in completed.stdout
