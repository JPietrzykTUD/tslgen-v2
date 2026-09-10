"""Pre-render planning tests for profile-local Rust algorithm support."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import _aligned_memory_specs, _plan
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import PrimitiveRequirement
from tslc.backend.rust_algorithm import rust_algorithm_module
from tslc.backend.rust_algorithm_plan import plan_rust_algorithm
from tslc.backend.rust_static_selection import (
    RustStaticProfileSelection,
    RustTargetRequirement,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.memory import MemoryAccess
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization


def _memory_specs() -> tuple[
    tuple[LoweredSpecialization, ...],
    tuple[LoweredSpecialization, ...],
]:
    read = _aligned_memory_specs(
        "read_contiguous",
        operation=PrimitiveOperation.LOAD,
        access=MemoryAccess.READ,
        result_kind="v",
        param_names=("source",),
        param_kinds=("cptr",),
        roles=((OperandRole.MEMORY_SOURCE, 0, "cptr"),),
    )
    write = _aligned_memory_specs(
        "write_contiguous",
        operation=PrimitiveOperation.STORE,
        access=MemoryAccess.WRITE,
        result_kind="void",
        param_names=("destination", "value"),
        param_kinds=("ptr", "v"),
        roles=(
            (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
            (OperandRole.VALUE, 1, "v"),
        ),
        overload=ResolvedPrimitiveOverload("payload_extent", "vector", True),
    )
    return read, write


def _emitted_profile(
    name: str,
    read: tuple[LoweredSpecialization, ...],
    write: tuple[LoweredSpecialization, ...],
) -> EmittedProfile:
    return EmittedProfile(
        MachineProfile(name, "synthetic", frozenset(), {}),
        {
            "rust": {
                "write_contiguous": write,
                "read_contiguous": read,
            }
        },
        immediate_split_names=frozenset(),
    )


def test_missing_contiguous_store_is_structured_before_rendering() -> None:
    read, _write = _memory_specs()

    plan = plan_rust_algorithm((), _plan(*read))

    assert not plan.fallback.supported
    assert len(plan.fallback.unsupported) == 1
    gap = plan.fallback.unsupported[0]
    assert gap.profile_name == "target_fallback"
    assert gap.requirement == PrimitiveRequirement("store")
    assert gap.reason == "missing contiguous write primitive facade"
    assert plan.fallback.helper("masked_store").missing_requirements == (
        PrimitiveRequirement("store", PrimitiveMaskMode.PASS_THROUGH),
    )
    with pytest.raises(ValueError, match="unsupported Rust algorithm profile"):
        rust_algorithm_module(plan.fallback, RenderAssets({}))


def test_algorithm_planning_is_independent_of_primitive_input_order() -> None:
    read, write = _memory_specs()

    read_first = plan_rust_algorithm((), _plan(*read, *write))
    write_first = plan_rust_algorithm((), _plan(*write, *read))

    assert read_first == write_first


def test_renamed_and_reordered_profiles_are_planned_by_exact_identity(
    render_assets: RenderAssets,
) -> None:
    read, write = _memory_specs()
    base = _plan(*read, *write)
    alpha = _emitted_profile("alpha", read, write)
    beta = _emitted_profile("beta", read, write)
    requirement = RustTargetRequirement("x86_64", ())
    alpha_selection = RustStaticProfileSelection(
        "alpha", requirement, (), base.fallback_mappings, ()
    )
    beta_selection = replace(alpha_selection, profile_name="beta")
    static = replace(base, profiles=(beta_selection, alpha_selection))

    plan = plan_rust_algorithm((beta, alpha), static)

    assert tuple(profile.profile_name for profile in plan.profiles) == (
        "alpha",
        "beta",
    )
    profile = plan.profile("alpha")
    assert profile is not None

    renamed_emitted = _emitted_profile("renamed", read, write)
    renamed_static = replace(
        base,
        profiles=(replace(alpha_selection, profile_name="renamed"),),
    )
    renamed = plan_rust_algorithm((renamed_emitted,), renamed_static).profile(
        "renamed"
    )
    assert renamed is not None

    assert rust_algorithm_module(profile, render_assets) == rust_algorithm_module(
        renamed, render_assets
    )
