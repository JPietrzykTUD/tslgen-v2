"""Checked API twins are projected only from typed catastrophic preconditions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.checked_api import (
    CheckedConditionPlan,
    applicable_checked_api_plan,
    checked_api_plan,
    checked_memory_condition,
    public_call_requires_unsafe,
)
from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_checked_api import plan_cpp_checked_api
from tslc.backend.cpp_static_public_declarations import (
    cpp_static_declaration_holes,
)
from tslc.backend.rust import RustBackend
from tslc.backend.rust_static_public_declarations import (
    rust_static_declaration_holes,
)
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.call_preconditions import (
    CallPreconditionObligation,
    CallPreconditionObligationStatus,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryIndexedLaneExtent,
    MemoryPayloadExtent,
)
from tslc.catalog.model import Catalog, ImplementationSafety, PrimitiveMaskMode
from tslc.catalog.preconditions import (
    PreconditionCheckPrimitive,
    PreconditionErrorKind,
    PreconditionKind,
)
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import LoweredSpecialization, LoweredTypeParam, Lowerer
from tslc.select.selector import Selector


_FIXTURES = Path(__file__).parent / "fixtures" / "checked_api"


def test_checked_memory_conditions_require_one_complete_shared_binding() -> None:
    extent = CheckedConditionPlan(
        kind=PreconditionKind.COMPACTED_MEMORY_EXTENT,
        description="The compacted memory operand is valid.",
        unchecked_consequence="An invalid operand may cause undefined behavior.",
        error=PreconditionErrorKind.INSUFFICIENT_EXTENT,
        additional_errors=(),
        parameter_name="memory",
        parameter_index=1,
        applicable_type_tags=("si32",),
        check_primitives=(PreconditionCheckPrimitive.MASK_POPULATION_COUNT,),
        mask_parameter_name="mask",
        mask_parameter_index=0,
        memory_access=MemoryAccess.WRITE,
        memory_addressing=MemoryAddressing.COMPACTED,
        memory_payload_extents=(MemoryPayloadExtent.ACTIVE_LANES,),
    )
    alignment = CheckedConditionPlan(
        kind=PreconditionKind.SELECTED_MEMORY_ALIGNMENT,
        description="The compacted memory operand is valid.",
        unchecked_consequence="An invalid operand may cause undefined behavior.",
        error=PreconditionErrorKind.MISALIGNED,
        additional_errors=(),
        parameter_name="memory",
        parameter_index=1,
        applicable_type_tags=("si32",),
        mask_parameter_name="different_mask",
        mask_parameter_index=2,
        memory_access=MemoryAccess.WRITE,
        memory_addressing=MemoryAddressing.COMPACTED,
        memory_payload_extents=(MemoryPayloadExtent.ACTIVE_LANES,),
        memory_alignment_axis_name="aligned",
    )

    with pytest.raises(ValueError, match="disagree on their binding"):
        checked_memory_condition((extent, alignment))

    with pytest.raises(ValueError, match="indexed bindings must be complete"):
        replace(extent, index_parameter_name="indices")


def _lowered(
    catalog: Catalog,
    profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    backend: str,
    *,
    type_tag: str = "si32",
    mask_mode: PrimitiveMaskMode | None = None,
    extension_name: str = "avx2",
    profile_name: str = "avx2",
) -> LoweredSpecialization:
    selected = Selector().select_profile(
        catalog,
        profiles[profile_name],
        primitive_name,
        (type_tag,),
        backend_id=backend,
    )
    assert selected.diagnostics == ()
    slot = next(
        item
        for item in selected.selected
        if item.extension.name == extension_name
        and item.primitive.mask_mode is mask_mode
    )
    result = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend))
    assert result.specialization is not None, result.diagnostics
    return result.specialization


def _lowered_group(
    catalog: Catalog,
    profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    backend: str,
    *,
    type_tag: str = "si32",
    mask_mode: PrimitiveMaskMode | None = None,
    extension_name: str = "avx2",
) -> tuple[LoweredSpecialization, ...]:
    selected = Selector().select_profile(
        catalog,
        profiles["avx2"],
        primitive_name,
        (type_tag,),
        backend_id=backend,
    )
    assert selected.diagnostics == ()
    lowered = []
    for slot in selected.selected:
        if (
            slot.extension.name != extension_name
            or slot.primitive.mask_mode is not mask_mode
        ):
            continue
        result = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend)
        )
        assert result.specialization is not None, result.diagnostics
        lowered.append(result.specialization)
    assert lowered
    return tuple(lowered)


def test_cpp_lane_checked_twin_has_direct_result_and_error_reference(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "extract_value_at", "cpp")
    rendered = CppBackend().render_primitive("extract_value_at", (spec,))
    docs = CppBackend().render_documentation_api_declaration(
        "extract_value_at", (spec,)
    )

    shared_plan = checked_api_plan((spec,))
    assert shared_plan is not None
    assert shared_plan.conditions[0].applicable_type_tags == (spec.type_tag,)
    cpp_plan = plan_cpp_checked_api(
        (spec,), result_kind=spec.result_kind, result_type="typename Vec::base_type"
    )
    assert cpp_plan is not None
    assert cpp_plan.failure_placeholder_expression == "typename Vec::base_type{}"
    assert cpp_plan.error_parameter_declaration.endswith("& error")
    assert "inline typename Vec::base_type extract_value_at(" in rendered
    assert "[[nodiscard]] TSL_FORCE_INLINE auto extract_value_at_checked(" in rendered
    assert "::tsl::precondition_error & error" in rendered
    assert "if (index >= Vec::lane_count())" in rendered
    assert "error = ::tsl::precondition_error::none;" in rendered
    assert "return typename Vec::base_type{};" in rendered
    assert "does not invoke the unchecked operation" in docs


def test_rust_lane_unchecked_is_unsafe_and_checked_returns_result(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "extract_value_at", "rust")
    rendered = RustBackend().render_primitive("extract_value_at", (spec,))
    internal = RustBackend().render_primitive_internal(
        "extract_value_at", (spec,)
    )
    docs = RustBackend().render_documentation_api(
        "extract_value_at", (spec,)
    )

    assert public_call_requires_unsafe((spec,))
    assert "pub unsafe fn extract_value_at<" in rendered
    assert "pub fn extract_value_at_checked<" in rendered
    assert "-> Result<S::BaseType, PreconditionError>" in rendered
    assert "if index >= S::lane_count()" in rendered
    assert "return Err(PreconditionError::IndexOutOfBounds);" in rendered
    assert "Ok(unsafe { extract_value_at::<S>(data, index) })" in rendered
    assert "pub trait Extract_value_atImpl" in internal
    assert "unsafe fn apply(" in internal
    assert "Safety: caller must uphold unsafe preconditions" in internal
    assert "/// # Errors" in docs
    assert "Returns `PreconditionError::IndexOutOfBounds`" in docs
    assert "/// # Safety" in docs


def test_total_integral_mask_test_gets_no_checked_twin_or_unsafe_surface(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "test_imask", "rust")
    rendered = RustBackend().render_primitive("test_imask", (spec,))

    assert checked_api_plan((spec,)) is None
    assert not public_call_requires_unsafe((spec,))
    assert "test_imask_checked" not in rendered
    assert "pub unsafe fn test_imask" not in rendered
    assert "pub fn test_imask" in rendered


def test_empty_specialization_group_has_no_checked_or_unsafe_api() -> None:
    assert checked_api_plan(()) is None
    assert not public_call_requires_unsafe(())


def test_unresolved_transitive_obligation_fails_checked_admission_closed(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "extract_value_at", "cpp")
    unresolved = CallPreconditionObligation(
        callee_condition=PreconditionKind.CONTIGUOUS_MEMORY_EXTENT,
        disposition=None,
        status=CallPreconditionObligationStatus.MISSING,
        reason="fixture transitive obligation",
    )

    assert checked_api_plan(
        (replace(spec, unresolved_call_preconditions=(unresolved,)),)
    ) is None


def test_insert_and_mask_set_follow_the_same_declared_lane_contract(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    for primitive_name in ("insert_value_at", "set_mask_lane"):
        cpp_spec = _lowered(catalog, machine_profiles, primitive_name, "cpp")
        cpp = CppBackend().render_primitive(primitive_name, (cpp_spec,))
        assert f"{primitive_name}_checked" in cpp
        assert "if (index >= Vec::lane_count())" in cpp

        rust_spec = _lowered(catalog, machine_profiles, primitive_name, "rust")
        rust = RustBackend().render_primitive(primitive_name, (rust_spec,))
        assert f"pub unsafe fn {primitive_name}<" in rust
        assert f"pub fn {primitive_name}_checked<" in rust
        assert "if index >= S::lane_count()" in rust


def test_rust_insert_uses_an_unchecked_storage_write(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lowered(catalog, machine_profiles, "insert_value_at", "rust")
    assert "lane_set_unchecked" in spec.body_text
    assert "lanes[index]" not in spec.body_text


@pytest.mark.parametrize("primitive_name", ("div", "mod"))
def test_cpp_runtime_integer_divisor_gets_an_explicit_checked_twin(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
) -> None:
    spec = _lowered(catalog, machine_profiles, primitive_name, "cpp")
    backend = CppBackend()
    ordinary = backend.render_ordinary_wrappers(primitive_name, (spec,))
    checked = backend.render_checked_wrappers(primitive_name, (spec,))
    docs = backend.render_documentation_api_declaration(primitive_name, (spec,))

    plan = checked_api_plan((spec,))
    assert plan is not None
    assert tuple(condition.kind for condition in plan.conditions) == (
        PreconditionKind.ACTIVE_DIVISOR_NONZERO,
    )
    assert plan.conditions[0].error is PreconditionErrorKind.ZERO_DIVISOR
    assert "zero_divisor" not in ordinary
    assert "mask_population_count<Vec>(zero_divisors)" in checked
    assert "std::enable_if_t<(std::is_integral_v<typename Vec::base_type>)" in checked
    assert "error = ::tsl::precondition_error::zero_divisor;" in checked
    assert f"return ::tsl::{primitive_name}<Vec>(dividend, divisor);" in checked
    assert "precondition_error::zero_divisor" in docs
    assert "does not invoke the unchecked operation" in docs


@pytest.mark.parametrize(
    "mask_mode",
    (PrimitiveMaskMode.ZERO, PrimitiveMaskMode.PASS_THROUGH),
)
def test_cpp_masked_divisor_check_observes_only_active_lanes(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    mask_mode: PrimitiveMaskMode,
) -> None:
    emitted_name = "div_maskz" if mask_mode is PrimitiveMaskMode.ZERO else "div_mask"
    spec = _lowered(
        catalog,
        machine_profiles,
        "div",
        "cpp",
        mask_mode=mask_mode,
        extension_name="generic",
    )
    checked = CppBackend().render_checked_wrappers(emitted_name, (spec,))

    assert "mask_binary_and<Vec>(" in checked
    assert "mask, zero_divisors" in checked
    assert "mask_population_count<Vec>(active_zero_divisors)" in checked


def test_checked_divisor_dependencies_are_typed_and_domain_specific(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    integer = _lowered(catalog, machine_profiles, "div", "cpp")
    floating = _lowered(
        catalog,
        machine_profiles,
        "div",
        "cpp",
        type_tag="f32",
    )

    assert {
        origin.dependency.primitive for origin in integer.call_dependency_origins
    } >= {"equal", "mask_population_count", "set_zero"}
    assert not {
        origin
        for origin in floating.call_dependency_origins
        if origin.origin.startswith("checked precondition")
    }
    assert applicable_checked_api_plan((integer,)) is not None
    assert applicable_checked_api_plan((floating,)) is None
    floating_plan = checked_api_plan((floating,))
    assert floating_plan is not None
    assert floating_plan.conditions[0].applicable_type_tags == ()
    assert plan_cpp_checked_api(
        (floating,),
        result_kind=floating.result_kind,
        result_type="typename Vec::register_type",
    ) is None

    floating_rust = _lowered(
        catalog,
        machine_profiles,
        "div",
        "rust",
        type_tag="f32",
    )
    assert not public_call_requires_unsafe((floating_rust,))
    floating_public = RustBackend().render_primitive_public(
        "div", (floating_rust,)
    )
    assert "pub fn div<" in floating_public
    assert "pub unsafe fn div<" not in floating_public
    assert "div_checked" not in floating_public


@pytest.mark.parametrize("primitive_name", ("div", "mod"))
def test_rust_runtime_integer_divisor_is_unsafe_with_a_safe_checked_twin(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
) -> None:
    spec = _lowered(catalog, machine_profiles, primitive_name, "rust")
    backend = RustBackend()
    public = backend.render_primitive_public(primitive_name, (spec,))
    internal = backend.render_primitive_internal(primitive_name, (spec,))
    docs = backend.render_documentation_api(primitive_name, (spec,))
    rendered_name = "r#mod" if primitive_name == "mod" else primitive_name

    assert f"pub unsafe fn {rendered_name}<" in public
    assert f"pub fn {primitive_name}_checked<" in public
    assert "-> Result<S::RegisterType, PreconditionError>" in public
    assert "return Err(error);" in public
    assert "S::BaseType: CheckedIntegerLane" in public
    assert "S::BaseType: CheckedIntegerLane,\n{" in public
    assert "CheckedIntegerLane, {" not in public
    assert f"Ok(unsafe {{ {rendered_name}::<S>" in public
    assert "fn __tsl_precondition_error(" in internal
    assert "mask_population_count::<Self>(zero_divisors)" in internal
    assert "PreconditionError::ZeroDivisor" in internal
    assert "/// # Errors" in docs
    assert "is not invoked. active_divisor_nonzero" not in docs


def test_runtime_immediate_divisor_keeps_static_rejection_without_checked_twin(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    for backend_id, backend in (("cpp", CppBackend()), ("rust", RustBackend())):
        spec = _lowered(catalog, machine_profiles, "mod_imm", backend_id)
        rendered = backend.render_primitive("mod_imm", (spec,))
        assert checked_api_plan((spec,)) is None
        assert "mod_imm_checked" not in rendered
        if backend_id == "rust":
            assert "unsafe { r#mod::<" in spec.body_text
            assert not public_call_requires_unsafe((spec,))


def test_checked_error_assets_are_evolution_safe_and_debug_inline_is_portable(
    render_assets,
) -> None:
    cpp = render_assets.fill(
        "tsl_core.hpp", **cpp_static_declaration_holes("tsl_core.hpp")
    )
    rust = render_assets.fill("tsl_core.rs", **rust_static_declaration_holes())

    assert "#if defined(__OPTIMIZE__)" in cpp
    assert "#if defined(_DEBUG)" in cpp
    assert "#define TSL_FORCE_INLINE inline\n#endif" in cpp
    assert "#[non_exhaustive]\npub enum PreconditionError" in rust
    assert "zero_divisor," in cpp
    assert "ZeroDivisor," in rust
    assert "pub trait CheckedIntegerLane" in rust


def test_cpp_contiguous_memory_checked_twins_use_spans_and_typed_extents(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    loads = _lowered_group(catalog, machine_profiles, "load", "cpp")
    load = loads[0]
    assert load.safety.caller_unsafe
    load_plan = checked_api_plan(loads)
    assert load_plan is not None
    assert {
        extent
        for condition in load_plan.conditions
        for extent in condition.memory_payload_extents
    } == {MemoryPayloadExtent.VECTOR}
    rendered_load = CppBackend().render_checked_wrappers("load", loads)
    load_docs = CppBackend().render_documentation_api_declaration("load", loads)
    assert "::tsl::span<typename Vec::base_type const> ptr" in rendered_load
    assert "if (ptr.size() < Vec::lane_count())" in rendered_load
    assert "if constexpr (Aligned)" in rendered_load
    assert "precondition_error::insufficient_extent" in rendered_load
    assert "precondition_error::misaligned" in rendered_load
    assert "return ::tsl::load<Vec, Aligned>(ptr.data());" in rendered_load
    assert "ptr: read-only contiguous span" in load_docs
    assert "construction does not validate that C++ object invariant" in load_docs
    assert "@par Policy API" in load_docs
    assert "simd_for_t" in load_docs

    stores = _lowered_group(catalog, machine_profiles, "store", "cpp")
    rendered_store = CppBackend().render_checked_wrappers("store", stores)
    store_docs = CppBackend().render_documentation_api_declaration("store", stores)
    assert "::tsl::span<typename Vec::base_type> ptr" in rendered_store
    assert "std::is_same_v<std::decay_t<Arg1>, typename Vec::base_type>" in rendered_store
    assert "-> ::tsl::precondition_error" in rendered_store
    assert "::tsl::store<Vec, Aligned>(ptr.data(), data);" in rendered_store
    assert "return ::tsl::precondition_error::none;" in rendered_store
    assert "data: SIMD register or scalar value" in store_docs


@pytest.mark.parametrize(
    "unresolved_reason",
    (
        "foreign_invariant",
        "unchecked_index",
        "unsafe_operation",
    ),
)
def test_checked_memory_admission_fails_closed_for_unresolved_caller_obligations(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    unresolved_reason: str,
) -> None:
    specs = _lowered_group(catalog, machine_profiles, "load", "cpp")
    unsafe_spec = specs[0]
    assert unsafe_spec.safety.caller_unsafe
    replaced = replace(
        unsafe_spec,
        safety=ImplementationSafety(
            internal_unsafe=True,
            caller_unsafe=True,
            reasons=unsafe_spec.safety.reasons | {unresolved_reason},
        ),
    )

    assert checked_api_plan((replaced, *specs[1:])) is None


def test_free_pointer_results_have_exact_documented_indirection(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    cpp = _lowered(
        catalog,
        machine_profiles,
        "allocate",
        "cpp",
        type_tag="ui64",
        extension_name="generic",
        profile_name="scalar",
    )
    rust = _lowered(
        catalog,
        machine_profiles,
        "allocate",
        "rust",
        type_tag="ui64",
        extension_name="generic",
        profile_name="scalar",
    )

    cpp_docs = CppBackend().render_documentation_api_declaration(
        "allocate", (cpp,)
    )
    rust_docs = RustBackend().render_documentation_api("allocate", (rust,))

    assert "Returns: mutable element pointer (void *)" in cpp_docs
    assert "void * *" not in cpp_docs
    assert "Returns: mutable element pointer (`*mut core::ffi::c_void`)" in rust_docs
    assert "*mut *mut" not in rust_docs


def test_rust_contiguous_memory_checked_twins_use_slices_and_overload_facts(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    load = _lowered(catalog, machine_profiles, "load", "rust")
    rendered_load = RustBackend().render_primitive_public("load", (load,))
    load_docs = RustBackend().render_documentation_api("load", (load,))
    assert "pub fn load_checked<" in rendered_load
    assert "ptr: &[S::BaseType]" in rendered_load
    assert "if ptr.len() < S::lane_count()" in rendered_load
    assert (
        "if ALIGNED && !(ptr.as_ptr() as usize).is_multiple_of(S::ALIGN)"
        in rendered_load
    )
    assert "Ok(unsafe { load::<S, ALIGNED>(ptr.as_ptr()) })" in rendered_load
    assert "ptr: shared contiguous slice" in load_docs

    stores = _lowered_group(catalog, machine_profiles, "store", "rust")
    backend = RustBackend()
    internal = backend.render_primitive_internal("store", stores)
    public = backend.render_primitive_public("store", stores)
    docs = backend.render_documentation_api("store", stores)
    assert "fn __tsl_checked_memory_extent() -> usize;" in internal
    assert "fn __tsl_checked_memory_alignment() -> usize;" in internal
    assert "fn __tsl_checked_memory_extent() -> usize { 1 }" in internal
    assert "as SimdVector>::lane_count()" in internal
    assert "pub fn store_checked<" in public
    assert "ptr: &mut [S::BaseType]" in public
    assert "-> Result<(), PreconditionError>" in public
    assert "ptr.as_mut_ptr()" in public
    assert "Ok(unsafe" not in public
    assert "Ok(())" in public
    assert "pub fn store_checked<" in docs
    assert "ptr: &mut [S::BaseType]" in docs
    assert "data: SIMD register or scalar value" in docs


def test_checked_memory_assets_expose_range_and_error_contracts(render_assets) -> None:
    cpp = render_assets.fill(
        "tsl_core.hpp", **cpp_static_declaration_holes("tsl_core.hpp")
    )
    rust = render_assets.fill("tsl_core.rs", **rust_static_declaration_holes())

    assert "class span" in cpp
    assert "constexpr span(T* data, std::size_t size) noexcept" in cpp
    assert "Constructing a span does not validate its pointer" in cpp
    assert "insufficient_extent" in cpp
    assert "misaligned" in cpp
    assert "InsufficientExtent" in rust
    assert "Misaligned" in rust


def test_scalable_memory_checked_plan_uses_runtime_lane_count(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    cpp = _lowered(
        catalog,
        machine_profiles,
        "load",
        "cpp",
        extension_name="rvv",
        profile_name="rvv",
    )
    cpp_checked = CppBackend().render_checked_wrappers("load", (cpp,))
    assert "ptr.size() < Vec::lane_count()" in cpp_checked


def test_indexed_memory_checked_twins_use_typed_address_facts(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    gather = _lowered(catalog, machine_profiles, "gather", "cpp")
    plan = checked_api_plan((gather,))
    assert plan is not None
    assert len(plan.conditions) == 1
    condition = plan.conditions[0]
    assert condition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID
    assert condition.memory_addressing is MemoryAddressing.INDEXED
    assert (
        condition.memory_indexed_lane_extent
        is MemoryIndexedLaneExtent.VECTOR
    )
    assert condition.memory_payload_extents == (MemoryPayloadExtent.VECTOR,)
    assert condition.index_parameter_name == "index"
    assert condition.scale_parameter_name == "scale"
    assert condition.errors == (
        PreconditionErrorKind.INDEX_OUT_OF_BOUNDS,
        PreconditionErrorKind.ADDRESS_OVERFLOW,
        PreconditionErrorKind.MISALIGNED,
    )
    assert condition.check_primitives == (
        PreconditionCheckPrimitive.VECTOR_TO_ARRAY,
    )

    cpp = CppBackend().render_checked_wrappers("gather", (gather,))
    rust_spec = _lowered(catalog, machine_profiles, "gather", "rust")
    rust = RustBackend().render_primitive_public("gather", (rust_spec,))
    assert "::tsl::span<typename Vec::base_type const> base_ptr" in cpp
    assert "::tsl::to_array<IndicesType>(index)" in cpp
    assert "IndicesType::lane_count() < Vec::lane_count()" in cpp
    assert "__tsl_lane < Vec::lane_count()" in cpp
    assert "indexed_memory_address_error<typename Vec::base_type>" in cpp
    assert "base_ptr: &[S::BaseType]" in rust
    assert "let __tsl_indices = to_array::<IndicesType>(index);" in rust
    assert "IndicesType::lane_count() < S::lane_count()" in rust
    assert "0..S::lane_count()" in rust
    assert "indexed_memory_address_error::<_, S::BaseType>" in rust

    masked = _lowered(
        catalog,
        machine_profiles,
        "gather",
        "cpp",
        mask_mode=PrimitiveMaskMode.PASS_THROUGH,
    )
    masked_plan = checked_api_plan((masked,))
    assert masked_plan is not None
    assert masked_plan.conditions[0].mask_parameter_name == "mask"
    masked_cpp = CppBackend().render_checked_wrappers(
        "gather_mask", (masked,)
    )
    assert "::tsl::set_mask_lane<Vec>(" in masked_cpp
    assert "::tsl::mask_binary_and<Vec>(mask, __tsl_lane_mask)" in masked_cpp
    masked_rust = RustBackend().render_primitive_public(
        "gather_mask",
        (
            _lowered(
                catalog,
                machine_profiles,
                "gather",
                "rust",
                mask_mode=PrimitiveMaskMode.PASS_THROUGH,
            ),
        ),
    )
    assert "S::mask_lane_test(mask, __tsl_lane)" in masked_rust

    partial = _lowered(
        catalog,
        machine_profiles,
        "gather_narrow_partial",
        "cpp",
    )
    partial_plan = checked_api_plan((partial,))
    assert partial_plan is not None
    assert (
        partial_plan.conditions[0].memory_indexed_lane_extent
        is MemoryIndexedLaneExtent.INDEX_VECTOR
    )
    partial_cpp = CppBackend().render_checked_wrappers(
        "gather_narrow_partial", (partial,)
    )
    assert "IndicesType::lane_count() > Vec::lane_count()" in partial_cpp
    assert "__tsl_lane < IndicesType::lane_count()" in partial_cpp
    partial_rust = RustBackend().render_primitive_public(
        "gather_narrow_partial",
        (
            _lowered(
                catalog,
                machine_profiles,
                "gather_narrow_partial",
                "rust",
            ),
        ),
    )
    assert "IndicesType::lane_count() > S::lane_count()" in partial_rust
    assert "0..IndicesType::lane_count()" in partial_rust


def test_indexed_checked_backends_reject_ambiguous_vector_type_ownership(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    cpp = _lowered(catalog, machine_profiles, "gather", "cpp")
    ambiguous_cpp = replace(
        cpp,
        type_params=(*cpp.type_params, LoweredTypeParam("OtherVector")),
    )
    with pytest.raises(ValueError, match="one consistent index type parameter"):
        plan_cpp_checked_api(
            (ambiguous_cpp,),
            result_kind=ambiguous_cpp.result_kind,
            result_type="typename Vec::register_type",
        )

    rust = _lowered(catalog, machine_profiles, "gather", "rust")
    ambiguous_rust = replace(
        rust,
        type_params=(*rust.type_params, LoweredTypeParam("OtherVector")),
    )
    with pytest.raises(ValueError, match="exactly one index vector type"):
        RustBackend().render_primitive_public("gather", (ambiguous_rust,))


def test_compacted_memory_checked_twins_use_active_lane_capacity(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    compress = _lowered(catalog, machine_profiles, "compress_store", "cpp")
    plan = checked_api_plan((compress,))
    assert plan is not None
    assert tuple(condition.kind for condition in plan.conditions) == (
        PreconditionKind.COMPACTED_MEMORY_EXTENT,
        PreconditionKind.SELECTED_MEMORY_ALIGNMENT,
    )
    extent, alignment = plan.conditions
    assert extent.memory_addressing is MemoryAddressing.COMPACTED
    assert extent.memory_payload_extents == (
        MemoryPayloadExtent.ACTIVE_LANES,
    )
    assert extent.mask_parameter_name == "m"
    assert alignment.memory_addressing is MemoryAddressing.COMPACTED
    assert alignment.memory_payload_extents == (
        MemoryPayloadExtent.ACTIVE_LANES,
    )
    assert alignment.mask_parameter_name == "m"

    cpp = CppBackend().render_checked_wrappers("compress_store", (compress,))
    rust_spec = _lowered(catalog, machine_profiles, "compress_store", "rust")
    rust = RustBackend().render_primitive_public(
        "compress_store", (rust_spec,)
    )
    assert "ptr.size() < ::tsl::mask_population_count<Vec>(m)" in cpp
    assert "(::tsl::mask_population_count<Vec>(m) != 0) &&" in cpp
    assert "% Vec::vector_alignment" in cpp
    assert "bool Aligned = true" in cpp
    assert "ptr: &mut [S::BaseType]" in rust
    assert "let mut __tsl_required = 0usize;" in rust
    assert "S::mask_lane_test(m, __tsl_lane)" in rust
    assert "(0..S::lane_count()).any(|__tsl_lane|" in rust
    assert ".is_multiple_of(S::ALIGN)" in rust


def test_remaining_scalar_target_and_random_memory_twins_use_exact_extents(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    scalar = _lowered(
        catalog,
        machine_profiles,
        "load_scalar",
        "cpp",
        type_tag="ui32",
    )
    scalar_plan = checked_api_plan((scalar,))
    assert scalar_plan is not None
    assert scalar_plan.conditions[0].memory_payload_extents == (
        MemoryPayloadExtent.SCALAR,
    )
    scalar_cpp = CppBackend().render_checked_wrappers(
        "load_scalar", (scalar,)
    )
    assert "ptr.size() < std::size_t{1}" in scalar_cpp
    assert "precondition_error::misaligned" not in scalar_cpp

    converted = _lowered(
        catalog,
        machine_profiles,
        "load_convert_up",
        "cpp",
        type_tag="si8",
    )
    converted_plan = checked_api_plan((converted,))
    assert converted_plan is not None
    assert converted_plan.conditions[0].memory_payload_extents == (
        MemoryPayloadExtent.TARGET_VECTOR,
    )
    converted_cpp = CppBackend().render_checked_wrappers(
        "load_convert_up", (converted,)
    )
    assert "ptr.size() < ToVec::lane_count()" in converted_cpp
    converted_rust = RustBackend().render_primitive_public(
        "load_convert_up",
        (
            _lowered(
                catalog,
                machine_profiles,
                "load_convert_up",
                "rust",
                type_tag="si8",
            ),
        ),
    )
    assert "if ptr.len() < T::lane_count()" in converted_rust

    random_cpp_spec = _lowered(
        catalog,
        machine_profiles,
        "random_step",
        "cpp",
        type_tag="ui64",
    )
    random_cpp = CppBackend().render_primitive(
        "random_step", (random_cpp_spec,)
    )
    assert "random_step_checked(::tsl::span<uint64_t> out" in random_cpp
    assert "if (out.size() < std::size_t{1})" in random_cpp
    assert random_cpp.count("auto random_step_checked(") == 2
    assert random_cpp.count(
        "noexcept -> std::size_t {"
    ) == 1
    random_cpp_docs = CppBackend().render_documentation_api_declaration(
        "random_step", (random_cpp_spec,)
    )
    assert "Template parameters: none" in random_cpp_docs
    assert "precondition_error::insufficient_extent" in random_cpp_docs
    random_rust_spec = _lowered(
        catalog,
        machine_profiles,
        "random_step",
        "rust",
        type_tag="ui64",
    )
    random_rust = RustBackend().render_primitive_public(
        "random_step", (random_rust_spec,)
    )
    assert "pub fn random_step_checked(out: &mut [u64])" in random_rust
    assert "if out.is_empty()" in random_rust
    random_rust_docs = RustBackend().render_documentation_api(
        "random_step", (random_rust_spec,)
    )
    assert "Type parameters: none" in random_rust_docs
    assert "# Errors" in random_rust_docs
    assert "PreconditionError::InsufficientExtent" in random_rust_docs


@pytest.mark.parametrize(
    ("primitive_name", "type_tag"),
    (
        ("allocate", "ptr"),
        ("allocate_aligned", "ptr"),
        ("deallocate", "ptr"),
        ("memory_cp", "ui8"),
        ("load_mask_repr", "ui32"),
        ("gather_narrow", "si32"),
    ),
)
def test_unrepresentable_or_already_reported_raw_memory_has_no_checked_twin(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    type_tag: str,
) -> None:
    for backend in ("cpp", "rust"):
        spec = _lowered(
            catalog,
            machine_profiles,
            primitive_name,
            backend,
            type_tag=type_tag,
        )
        assert checked_api_plan((spec,)) is None
        rendered = (
            CppBackend().render_primitive(primitive_name, (spec,))
            if backend == "cpp"
            else RustBackend().render_primitive_public(primitive_name, (spec,))
        )
        assert f"{primitive_name}_checked" not in rendered


def test_unavailable_checked_guard_keeps_the_unchecked_specialization(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["scatter"],
        profiles=["sve"],
        type_tags=("si32",),
        backends=["cpp"],
    )

    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.emitted_profiles
    specializations = result.emitted_profiles[0].specializations("cpp")["scatter"]
    sve = next(spec for spec in specializations if spec.extension_name == "sve")
    assert tuple(
        origin.dependency.primitive
        for origin in sve.unavailable_checked_dependency_origins
    ) == ("to_array",)
    assert applicable_checked_api_plan((sve,)) is None

    source = "\n".join(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path.endswith("/include/tsl_sve.hpp")
    )
    assert "inline void scatter(" in source
    assert "scatter_checked" not in source


@pytest.fixture(scope="module")
def checked_lane_cpp_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-lane-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "extract_value_at",
            "insert_value_at",
            "set_mask_lane",
            "test_imask",
        ],
        profiles=["scalar", "avx2"],
        type_tags=("si32",),
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root / "cpp" / "include"


@pytest.fixture(scope="module")
def checked_division_cpp_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-division-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "div", "mod"],
        profiles=["scalar", "avx2"],
        type_tags=(
            "si8",
            "ui8",
            "si16",
            "ui16",
            "si32",
            "ui32",
            "si64",
            "ui64",
            "f32",
            "f64",
        ),
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root / "cpp" / "include"


@pytest.fixture(scope="module")
def checked_division_rust_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-division-rust-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["div"],
        profiles=["scalar"],
        type_tags=("si32",),
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root / "rust"


@pytest.fixture(scope="module")
def checked_memory_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-memory-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["load", "store", "mask_false"],
        profiles=["scalar", "avx2"],
        type_tags=("si32",),
        backends=["cpp", "rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root


@pytest.fixture(scope="module")
def checked_irregular_memory_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-irregular-memory-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "compress_store",
            "expand_load",
            "from_array",
            "gather",
            "gather_narrow_partial",
            "mask_false",
            "scatter",
            "set_mask_lane",
            "to_array",
        ],
        profiles=["avx2"],
        type_tags=("si32", "si64"),
        backends=["cpp", "rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root


@pytest.fixture(scope="module")
def checked_remaining_memory_project(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    output_root = tmp_path_factory.mktemp("checked-remaining-memory-project")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "load_convert_up",
            "load_scalar",
            "random_step",
            "to_array",
        ],
        profiles=["avx2"],
        type_tags=("si8", "si32", "ui32", "ui64"),
        backends=["cpp", "rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, output_root)
    assert not has_errors(report.diagnostics), report.diagnostics
    return output_root


def _cpp_compilers() -> tuple[str, ...]:
    return tuple(
        compiler
        for name in ("g++", "clang++")
        if (compiler := shutil.which(name)) is not None
    )


@pytest.mark.generated_build
def test_native_mask_layout_consumer_is_warning_clean(
    checked_lane_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "native_mask_layout_codegen.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        object_path = tmp_path / f"native-mask-layout-{compiler_id}.o"
        completed = subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-mavx2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DTSL_PROFILE_AVX2=1",
                "-I",
                str(checked_lane_cpp_project),
                "-c",
                str(source),
                "-o",
                str(object_path),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


@pytest.mark.generated_build
def test_checked_lane_cpp_consumer_is_warning_clean_and_sanitizer_safe(
    checked_lane_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "lane_index_scalar_consumer.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        debug_binary = tmp_path / f"lane-debug-{compiler_id}"
        subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O0",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(checked_lane_cpp_project),
                str(source),
                "-o",
                str(debug_binary),
            ),
            check=True,
        )
        subprocess.run((str(debug_binary),), check=True)

    sanitizer_binary = tmp_path / "lane-sanitizer"
    subprocess.run(
        (
            compilers[0],
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(checked_lane_cpp_project),
            str(source),
            "-o",
            str(sanitizer_binary),
        ),
        check=True,
    )
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run((str(sanitizer_binary),), check=True, env=environment)


@pytest.mark.generated_build
def test_unchecked_lane_codegen_has_no_validation_branch(
    checked_lane_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "lane_index_codegen.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        assembly_path = tmp_path / f"lane-{compiler_id}.s"
        subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-fno-stack-protector",
                "-mavx2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-S",
                "-masm=intel",
                "-I",
                str(checked_lane_cpp_project),
                str(source),
                "-o",
                str(assembly_path),
            ),
            check=True,
        )
        assembly = assembly_path.read_text(encoding="utf-8")
        unchecked = re.search(
            r"^unchecked_lane:.*?(?=^\s*(?:\.size\s+unchecked_lane|\.Lfunc_end))",
            assembly,
            flags=re.MULTILINE | re.DOTALL,
        )
        checked = re.search(
            r"^checked_lane:.*?(?=^\s*(?:\.size\s+checked_lane|\.Lfunc_end))",
            assembly,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert unchecked is not None
        assert checked is not None
        assert re.search(r"\bcmp\b", unchecked.group()) is None
        assert re.search(r"\bj[a-z]+\b", unchecked.group()) is None
        assert re.search(r"\bcmp\b", checked.group()) is not None
        assert re.search(r"\bj[a-z]+\b", checked.group()) is not None


@pytest.mark.generated_build
def test_checked_division_cpp_consumer_covers_domains_masks_and_no_invocation(
    checked_division_cpp_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "division_scalar_consumer.cpp"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        binary = tmp_path / f"division-{compiler_id}"
        subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fno-exceptions",
                "-I",
                str(checked_division_cpp_project),
                str(source),
                "-o",
                str(binary),
            ),
            check=True,
        )
        subprocess.run((str(binary),), check=True)

    sanitizer_binary = tmp_path / "division-sanitizer"
    subprocess.run(
        (
            compilers[0],
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(checked_division_cpp_project),
            str(source),
            "-o",
            str(sanitizer_binary),
        ),
        check=True,
    )
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run((str(sanitizer_binary),), check=True, env=environment)


def _assembly_function(assembly: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:.*?^\s*\.size\s+{re.escape(name)}\b",
        assembly,
    )
    assert match is not None, f"assembly has no function body for {name}"
    return match.group(0).lower()


@pytest.mark.generated_build
@pytest.mark.parametrize("compiler_name", ("g++", "clang++"))
def test_generated_checked_division_preserves_raw_register_return_abi(
    checked_division_cpp_project: Path,
    tmp_path: Path,
    compiler_name: str,
) -> None:
    compiler = shutil.which(compiler_name)
    if compiler is None:
        pytest.skip(f"{compiler_name} is not available")
    source = _FIXTURES / "division_avx2_codegen.cpp"
    assembly_path = tmp_path / f"division-{compiler_name.replace('+', 'p')}.s"
    completed = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O3",
            "-mavx2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-fno-exceptions",
            "-S",
            "-masm=intel",
            "-I",
            str(checked_division_cpp_project),
            str(source),
            "-o",
            str(assembly_path),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assembly = assembly_path.read_text(encoding="utf-8")

    checked = _assembly_function(assembly, "checked_divide_avx2")
    consumed = _assembly_function(assembly, "consume_checked_divide_avx2")
    unchecked = _assembly_function(assembly, "consume_unchecked_divide_avx2")

    for body in (checked, consumed, unchecked):
        assert "ymm0" in body
        assert "ret" in body
    assert re.search(r"byte ptr\s+\[rdi(?:\s*\+\s*0)?\]", checked)
    assert not re.search(r"ymmword ptr\s+\[rdi", checked)
    assert not re.search(
        r"\bcall\w*\s+(?:_?consume_unchecked_divide_avx2|"
        r"_?checked_divide_avx2)\b",
        consumed,
    )
    assert not re.search(r"\[(?:r|e)sp(?:\s*[+\-])?", consumed)


@pytest.mark.generated_build
def test_optimized_rust_unchecked_division_has_no_zero_validation_path(
    checked_division_rust_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    source = _FIXTURES / "division_rust_codegen.rs"
    binary_source = checked_division_rust_project / "src" / "bin"
    binary_source.mkdir(parents=True)
    shutil.copyfile(source, binary_source / source.name)
    target_dir = tmp_path / "cargo-target"
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(target_dir)
    completed = subprocess.run(
        (
            cargo,
            "rustc",
            "--release",
            "--bin",
            "division_rust_codegen",
            "--",
            "--emit=llvm-ir",
        ),
        cwd=checked_division_rust_project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    ir_files = sorted(
        (target_dir / "release" / "deps").glob("division_rust_codegen-*.ll")
    )
    assert ir_files
    ir = ir_files[0].read_text(encoding="utf-8")
    function = re.search(
        r"(?ms)^define .*@unchecked_divide_rust\(.*?^}",
        ir,
    )
    assert function is not None
    body = function.group(0)

    assert "panic_const_div_by_zero" not in body
    assert "precondition_check" not in body
    assert "panic" not in body


@pytest.mark.generated_build
def test_checked_memory_cpp_consumer_covers_extent_alignment_and_canaries(
    checked_memory_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "memory_consumer.cpp"
    include = checked_memory_project / "cpp" / "include"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        binary = tmp_path / f"memory-{compiler_id}"
        completed = subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-mavx2",
                "-mrdrnd",
                "-msse4.2",
                "-mssse3",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fno-exceptions",
                "-I",
                str(include),
                str(source),
                "-o",
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        subprocess.run((str(binary),), check=True)

    sanitizer = tmp_path / "memory-sanitizer"
    completed = subprocess.run(
        (
            compilers[0],
            "-std=c++17",
            "-O1",
            "-g",
            "-mavx2",
            "-mrdrnd",
            "-msse4.2",
            "-mssse3",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(include),
            str(source),
            "-o",
            str(sanitizer),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run((str(sanitizer),), check=True, env=environment)


@pytest.mark.generated_build
def test_checked_memory_rust_consumer_covers_extent_alignment_and_canaries(
    checked_memory_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    if os.uname().machine != "x86_64":
        pytest.skip("the checked AVX2 alignment consumer requires x86-64")
    project = checked_memory_project / "rust"
    source = _FIXTURES / "memory_consumer.rs"
    binary_source = project / "src" / "bin"
    binary_source.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, binary_source / source.name)
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(tmp_path / "cargo-target")
    environment["RUSTFLAGS"] = (
        "-C target-feature=+avx,+avx2,+rdrand,+sse,+sse2,+sse4.1,+sse4.2,+ssse3"
    )
    completed = subprocess.run(
        (cargo, "run", "--release", "--bin", "memory_consumer"),
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.generated_build
def test_checked_irregular_memory_cpp_consumer_covers_address_and_capacity_edges(
    checked_irregular_memory_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "irregular_memory_consumer.cpp"
    include = checked_irregular_memory_project / "cpp" / "include"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        binary = tmp_path / f"irregular-memory-{compiler_id}"
        completed = subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-mavx2",
                "-mrdrnd",
                "-msse4.2",
                "-mssse3",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fno-exceptions",
                "-I",
                str(include),
                str(source),
                "-o",
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        subprocess.run((str(binary),), check=True)

    sanitizer = tmp_path / "irregular-memory-sanitizer"
    completed = subprocess.run(
        (
            compilers[0],
            "-std=c++17",
            "-O1",
            "-g",
            "-mavx2",
            "-mrdrnd",
            "-msse4.2",
            "-mssse3",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(include),
            str(source),
            "-o",
            str(sanitizer),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run((str(sanitizer),), check=True, env=environment)


@pytest.mark.generated_build
def test_checked_irregular_memory_rust_consumer_covers_address_and_capacity_edges(
    checked_irregular_memory_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    if os.uname().machine != "x86_64":
        pytest.skip("the checked AVX2 irregular-memory consumer requires x86-64")
    project = checked_irregular_memory_project / "rust"
    source = _FIXTURES / "irregular_memory_consumer.rs"
    binary_source = project / "src" / "bin"
    binary_source.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, binary_source / source.name)
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(tmp_path / "cargo-target")
    environment["RUSTFLAGS"] = (
        "-C target-feature=+avx,+avx2,+rdrand,+sse,+sse2,+sse4.1,+sse4.2,+ssse3"
    )
    completed = subprocess.run(
        (cargo, "run", "--release", "--bin", "irregular_memory_consumer"),
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.generated_build
def test_checked_remaining_memory_cpp_consumer_covers_exact_target_extents(
    checked_remaining_memory_project: Path,
    tmp_path: Path,
) -> None:
    compilers = _cpp_compilers()
    if not compilers:
        pytest.skip("GCC or Clang C++ compiler required")
    source = _FIXTURES / "remaining_memory_consumer.cpp"
    include = checked_remaining_memory_project / "cpp" / "include"

    for compiler in compilers:
        compiler_id = Path(compiler).name.replace("+", "x")
        binary = tmp_path / f"remaining-memory-{compiler_id}"
        completed = subprocess.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-mavx2",
                "-mrdrnd",
                "-msse4.2",
                "-mssse3",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fno-exceptions",
                "-I",
                str(include),
                str(source),
                "-o",
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        subprocess.run((str(binary),), check=True)


@pytest.mark.generated_build
def test_checked_remaining_memory_rust_consumer_covers_exact_target_extents(
    checked_remaining_memory_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    if os.uname().machine != "x86_64":
        pytest.skip("the checked AVX2 remaining-memory consumer requires x86-64")
    project = checked_remaining_memory_project / "rust"
    source = _FIXTURES / "remaining_memory_consumer.rs"
    binary_source = project / "src" / "bin"
    binary_source.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, binary_source / source.name)
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(tmp_path / "cargo-target")
    environment["RUSTFLAGS"] = (
        "-C target-feature=+avx,+avx2,+rdrand,+sse,+sse2,+sse4.1,+sse4.2,+ssse3"
    )
    completed = subprocess.run(
        (cargo, "run", "--release", "--bin", "remaining_memory_consumer"),
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.generated_build
@pytest.mark.parametrize("compiler_name", ("g++", "clang++"))
def test_contiguous_memory_codegen_keeps_checks_out_of_the_ordinary_path(
    checked_memory_project: Path,
    tmp_path: Path,
    compiler_name: str,
) -> None:
    compiler = shutil.which(compiler_name)
    if compiler is None:
        pytest.skip(f"{compiler_name} is not available")
    source = _FIXTURES / "memory_codegen.cpp"
    assembly_path = tmp_path / f"memory-{compiler_name.replace('+', 'p')}.s"
    completed = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O3",
            "-mavx2",
            "-mrdrnd",
            "-msse4.2",
            "-mssse3",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fno-exceptions",
            "-S",
            "-masm=intel",
            "-I",
            str(checked_memory_project / "cpp" / "include"),
            str(source),
            "-o",
            str(assembly_path),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assembly = assembly_path.read_text(encoding="utf-8")
    unchecked_load = _assembly_function(assembly, "unchecked_load_avx2")
    checked_load = _assembly_function(assembly, "checked_load_avx2")
    unchecked_store = _assembly_function(assembly, "unchecked_store_avx2")

    for body in (unchecked_load, unchecked_store):
        assert re.search(r"\bcmp\b", body) is None
        assert re.search(r"\bj[a-z]+\b", body) is None
    assert "ymm0" in unchecked_load
    assert "ymm0" in checked_load
    assert re.search(r"\bcmp\b", checked_load) is not None
    assert re.search(r"\bj[a-z]+\b", checked_load) is not None
    assert not re.search(r"\[(?:r|e)sp(?:\s*[+\-])?", checked_load)


@pytest.mark.generated_build
def test_unchecked_rust_memory_codegen_has_no_extent_or_alignment_branch(
    checked_memory_project: Path,
    tmp_path: Path,
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    if os.uname().machine != "x86_64":
        pytest.skip("the unchecked AVX2 codegen probe requires x86-64")
    project = checked_memory_project / "rust"
    source = _FIXTURES / "memory_rust_codegen.rs"
    binary_source = project / "src" / "bin"
    binary_source.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, binary_source / source.name)
    target_dir = tmp_path / "cargo-target"
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(target_dir)
    environment["RUSTFLAGS"] = (
        "-C target-feature=+avx,+avx2,+rdrand,+sse,+sse2,+sse4.1,+sse4.2,+ssse3"
    )
    completed = subprocess.run(
        (
            cargo,
            "rustc",
            "--release",
            "--bin",
            "memory_rust_codegen",
            "--",
            "--emit=llvm-ir",
        ),
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    ir_files = sorted(
        (target_dir / "release" / "deps").glob("memory_rust_codegen-*.ll")
    )
    assert ir_files
    ir = ir_files[0].read_text(encoding="utf-8")
    function = re.search(
        r"(?ms)^define .*@unchecked_load_rust\(.*?^}",
        ir,
    )
    assert function is not None
    body = function.group(0)
    assert "icmp " not in body
    assert "br i1" not in body
    assert "panic_bounds_check" not in body
    assert "ret <4 x i64>" in body
