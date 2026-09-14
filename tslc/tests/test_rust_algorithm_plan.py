"""Pre-render planning tests for profile-local Rust algorithm support."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import _aligned_memory_specs, _plan
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    BackendHelperPlan,
    PrimitiveRequirement,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.rust_algorithm import (
    rust_algorithm_family_module,
    rust_algorithm_root_module,
    rust_algorithm_support_module,
)
from tslc.backend.rust_algorithm_plan import plan_rust_algorithm
from tslc.backend.rust_static_selection import (
    RustStaticProfileSelection,
    RustTargetRequirement,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.memory import MemoryAccess
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import (
    COMPACTED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_POPULATION_COUNT_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
    VECTOR_FROM_ARRAY_REQUIREMENT,
    VECTOR_TO_ARRAY_REQUIREMENT,
    VECTOR_ZERO_REQUIREMENT,
    OperandRole,
    PrimitiveOperation,
    ResolvedPrimitiveProvider,
)
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.primitive_semantics import LoweredPrimitiveSemantics


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


def _helper_plan() -> BackendHelperPlan:
    names = {
        CONTIGUOUS_VECTOR_LOAD_REQUIREMENT: "read_contiguous",
        CONTIGUOUS_VECTOR_STORE_REQUIREMENT: "write_contiguous",
        CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT: "store",
        VECTOR_ZERO_REQUIREMENT: "set_zero",
        VECTOR_TO_ARRAY_REQUIREMENT: "to_array",
        VECTOR_FROM_ARRAY_REQUIREMENT: "from_array",
        INDEXED_POINTER_VECTOR_LOAD_REQUIREMENT: "gather_narrow",
        COMPACTED_VECTOR_STORE_REQUIREMENT: "compress_store",
        MASK_POPULATION_COUNT_REQUIREMENT: "mask_population_count",
        MASK_TO_INTEGRAL_REQUIREMENT: "to_integral",
        MASK_FROM_INTEGRAL_REQUIREMENT: "to_mask",
    }
    return BackendHelperPlan(
        RUST_HELPER_MANIFEST,
        tuple(
            ResolvedPrimitiveProvider(requirement, names[requirement])
            for requirement in RUST_HELPER_MANIFEST.provider_requirements
        ),
        (),
    )


def _helper_specs(
    base: LoweredSpecialization,
    *,
    excluded: frozenset[str],
) -> tuple[LoweredSpecialization, ...]:
    helper_plan = _helper_plan()
    return tuple(
        replace(
            base,
            primitive_name=provider.primitive_name,
            source_primitive_name=provider.primitive_name,
            primitive_semantics=LoweredPrimitiveSemantics(),
            mask_policy=requirement.mask_policy,
            axis=(),
        )
        for feature in RUST_HELPER_MANIFEST.features
        for requirement in feature.requirements
        if (provider := helper_plan.provider(requirement)) is not None
        if provider.primitive_name
        not in {"read_contiguous", "write_contiguous", *excluded}
    )


def test_missing_contiguous_store_is_structured_before_rendering() -> None:
    read, _write = _memory_specs()

    plan = plan_rust_algorithm((), _plan(*read), _helper_plan())

    assert not plan.fallback.supported
    assert not plan.fallback.admission.admitted_forms
    assert plan.fallback.helper("contiguous_memory").missing_requirements == (
        PrimitiveRequirement(CONTIGUOUS_VECTOR_STORE_REQUIREMENT),
    )
    gap = plan.fallback.admission.family("transform_unary").gaps[0]
    assert gap.backend_id == "rust"
    assert gap.profile_name == "target_fallback"
    assert gap.feature_name == "contiguous_memory"
    assert gap.family_name == "transform_unary"
    assert gap.requirement == PrimitiveRequirement(CONTIGUOUS_VECTOR_STORE_REQUIREMENT)
    assert "resolved primitive 'write_contiguous' has no profile specialization" in gap.reason
    assert plan.fallback.helper("masked_store").missing_requirements == (
        PrimitiveRequirement(
            CONTIGUOUS_MASKED_VECTOR_STORE_REQUIREMENT,
            PrimitiveMaskMode.PASS_THROUGH,
        ),
    )
    with pytest.raises(ValueError, match="unsupported Rust algorithm profile"):
        rust_algorithm_support_module(plan.fallback)


def test_algorithm_planning_is_independent_of_primitive_input_order() -> None:
    read, write = _memory_specs()

    read_first = plan_rust_algorithm((), _plan(*read, *write), _helper_plan())
    write_first = plan_rust_algorithm((), _plan(*write, *read), _helper_plan())

    assert read_first == write_first


def test_missing_optional_compaction_only_excludes_dependent_rust_families() -> None:
    read, write = _memory_specs()
    helper_specs = _helper_specs(
        read[0], excluded=frozenset({"compress_store"})
    )

    incomplete = plan_rust_algorithm(
        (), _plan(*read, *write, *helper_specs), _helper_plan()
    ).fallback

    assert incomplete.supported
    assert incomplete.helper("compress_store").missing_requirements == (
        PrimitiveRequirement(COMPACTED_VECTOR_STORE_REQUIREMENT),
    )
    absent = {
        family.family.name
        for family in incomplete.admission.families
        if not family.admitted and family.family.name.startswith("select_")
    }
    assert absent == {
        "select_unary",
        "select_binary",
        "select_masked_unary",
        "select_masked_binary",
    }
    assert "transform_unary" in incomplete.admitted_family_names
    assert "predicate_unary" in incomplete.admitted_family_names

    compress = replace(
        read[0],
        primitive_name="compress_store",
        source_primitive_name="compress_store",
        primitive_semantics=LoweredPrimitiveSemantics(),
        axis=(),
    )
    complete = plan_rust_algorithm(
        (), _plan(*read, *write, *helper_specs, compress), _helper_plan()
    ).fallback
    assert absent <= set(complete.admitted_family_names)


def test_rust_mask_conversion_gap_only_excludes_layout_predicate_form() -> None:
    read, write = _memory_specs()
    helper_specs = _helper_specs(
        read[0], excluded=frozenset({"to_mask"})
    )

    plan = plan_rust_algorithm(
        (), _plan(*read, *write, *helper_specs), _helper_plan()
    ).fallback
    predicate = plan.admission.family("predicate_unary")
    masked_count = plan.admission.family("count_masked_unary")
    masked_indices = plan.admission.family("select_masked_indices_unary")

    assert tuple(form.name for form in predicate.admitted_forms) == (
        "predicate_unary",
    )
    assert tuple(form.name for form in masked_count.admitted_forms) == (
        "count_masked_unary",
    )
    assert tuple(form.name for form in masked_indices.admitted_forms) == (
        "select_masked_indices_unary",
    )
    assert tuple(
        (gap.form_name, gap.feature_name, gap.requirement)
        for gap in predicate.gaps
    ) == (
        (
            "predicate_unary_mask_layout",
            "mask_from_integral",
            PrimitiveRequirement(MASK_FROM_INTEGRAL_REQUIREMENT),
        ),
    )


def test_rust_population_count_gap_only_excludes_compacting_selection() -> None:
    read, write = _memory_specs()
    helper_specs = _helper_specs(
        read[0], excluded=frozenset({"mask_population_count"})
    )

    plan = plan_rust_algorithm(
        (), _plan(*read, *write, *helper_specs), _helper_plan()
    ).fallback

    assert "count_unary" in plan.admitted_family_names
    assert "count_masked_unary" in plan.admitted_family_names
    assert "select_indices_unary" in plan.admitted_family_names
    assert "select_masked_indices_unary" in plan.admitted_family_names
    assert "select_unary" not in plan.admitted_family_names
    assert "select_masked_unary" not in plan.admitted_family_names


def test_renamed_and_reordered_profiles_are_planned_by_exact_identity(
    render_assets: RenderAssets,
) -> None:
    read, write = _memory_specs()
    base = _plan(*read, *write)
    alpha = _emitted_profile("alpha", read, write)
    beta = _emitted_profile("beta", read, write)
    alpha_requirement = RustTargetRequirement("x86_64", ("alpha",))
    beta_requirement = RustTargetRequirement("x86_64", ("beta",))
    alpha_selection = RustStaticProfileSelection(
        "alpha",
        alpha_requirement,
        (beta_requirement,),
        base.fallback_mappings,
        (),
        10,
    )
    beta_selection = RustStaticProfileSelection(
        "beta",
        beta_requirement,
        (),
        base.fallback_mappings,
        (),
        20,
    )
    static = replace(base, profiles=(beta_selection, alpha_selection))

    plan = plan_rust_algorithm((beta, alpha), static, _helper_plan())

    assert tuple(profile.profile_name for profile in plan.profiles) == (
        "alpha",
        "beta",
    )
    profile = plan.profile("alpha")
    assert profile is not None

    renamed_emitted = _emitted_profile("renamed", read, write)
    renamed_static = replace(
        base,
        profiles=(
            replace(
                alpha_selection,
                profile_name="renamed",
                higher_priority_requirements=(),
            ),
        ),
    )
    renamed = plan_rust_algorithm(
        (renamed_emitted,), renamed_static, _helper_plan()
    ).profile("renamed")
    assert renamed is not None

    assert rust_algorithm_root_module(profile) == rust_algorithm_root_module(
        renamed
    )
    assert rust_algorithm_support_module(
        profile
    ) == rust_algorithm_support_module(renamed)
    assert tuple(
        rust_algorithm_family_module(family, render_assets)
        for family in profile.family_modules
    ) == tuple(
        rust_algorithm_family_module(family, render_assets)
        for family in renamed.family_modules
    )
