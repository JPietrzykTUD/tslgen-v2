"""Comprehensive Rust facade admission and public-surface tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import (
    _aligned_memory_specs,
    _operation,
    _plan,
    _spec,
)
from tslc.backend.rust_api_model import (
    RustFacadeConstParameterSource,
    RustFacadeCoverageStatus,
    RustFacadeParameterPlacement,
    RustFacadeReceiverKind,
)
from tslc.backend.rust_api_planner import (
    RustFacadePlanningError,
    plan_rust_facade,
)
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryAlignment,
    PrimitiveMemoryContract,
)
from tslc.catalog.model import ImplementationSafety
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.primitive_semantics import LoweredMemoryAlignment


@pytest.mark.parametrize(
    ("spec", "expected"),
    (
        (
            _spec(
                "shift_left",
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", True
                ),
            ),
            "shift_left",
        ),
        (
            _spec(
                "shift_left",
                param_names=("data", "shift"),
                param_kinds=("v", "sImm"),
                roles=(
                    (OperandRole.PRIMARY, 0, "v"),
                    (OperandRole.COUNT, 1, "sImm"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", False
                ),
                immediate=("shift", "u32"),
            ),
            "shift_left_imm",
        ),
        (
            _spec(
                "shift_left",
                param_names=("data", "shift"),
                param_kinds=("v", "v"),
                roles=(
                    (OperandRole.PRIMARY, 0, "v"),
                    (OperandRole.COUNT, 1, "v"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "per_lane", False
                ),
            ),
            "shift_left_each",
        ),
        (
            _spec(
                "mul_imm",
                param_names=("mask", "data", "factor"),
                param_kinds=("m", "v", "sImm"),
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.PRIMARY, 1, "v"),
                    (OperandRole.COUNT, 2, "sImm"),
                ),
                immediate=("factor", "i32"),
                mask_policy="pass_through",
            ),
            "mul_imm_masked",
        ),
        (
            _spec(
                "shift_left",
                param_names=("mask", "data", "shift"),
                param_kinds=("m", "v", "sImm"),
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.PRIMARY, 1, "v"),
                    (OperandRole.COUNT, 2, "sImm"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", False
                ),
                immediate=("shift", "u32"),
                mask_policy="zero",
            ),
            "shift_left_imm_masked_zero",
        ),
    ),
)
def test_public_name_components_are_composed_once(
    spec: LoweredSpecialization,
    expected: str,
) -> None:
    plan = plan_rust_facade((), _plan(spec))

    assert [method.public_name for method in plan.comprehensive_methods] == [expected]


def test_receiver_is_finalized_before_explicit_arguments() -> None:
    spec = _spec(
        "masked_op",
        param_names=("mask", "data", "factor"),
        param_kinds=("m", "v", "sImm"),
        roles=(
            (OperandRole.CONTROL_MASK, 0, "m"),
            (OperandRole.PRIMARY, 1, "v"),
            (OperandRole.COUNT, 2, "sImm"),
        ),
        immediate=("factor", "i32"),
        mask_policy="pass_through",
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.VECTOR
    assert tuple(parameter.placement for parameter in method.parameters) == (
        RustFacadeParameterPlacement.ARGUMENT,
        RustFacadeParameterPlacement.RECEIVER,
        RustFacadeParameterPlacement.CONST_GENERIC,
    )
    assert method.parameters[0].role is OperandRole.CONTROL_MASK
    assert method.parameters[2].public_name == "FACTOR"


def test_mask_primary_becomes_a_mask_receiver() -> None:
    spec = _spec(
        "mask_not",
        result_kind="m",
        param_names=("mask",),
        param_kinds=("m",),
        operation=PrimitiveOperation.MASK_NOT,
        roles=((OperandRole.PRIMARY, 0, "m"),),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.MASK
    assert method.parameters[0].placement is RustFacadeParameterPlacement.RECEIVER


def test_attribute_and_generic_const_parameters_are_finalized() -> None:
    spec = replace(
        _spec("configured"),
        axis=(("aligned", "true"),),
        generic_params=(("PreserveSign", "bool", "true"),),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert tuple(item.public_name for item in method.const_parameters) == (
        "ALIGNED",
        "PRESERVE_SIGN",
    )
    assert method.const_parameters[1].source_default == "true"


def test_immediate_is_a_finalized_const_parameter() -> None:
    spec = _spec(
        "configured_immediate",
        param_names=("data", "shift"),
        param_kinds=("v", "sImm"),
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.COUNT, 1, "sImm"),
        ),
        immediate=("shift", "u32"),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert tuple(
        (item.public_name, item.type_spelling, item.source)
        for item in method.const_parameters
    ) == (("SHIFT", "u32", RustFacadeConstParameterSource.IMMEDIATE),)


def test_no_receiver_projects_as_a_free_function() -> None:
    method = plan_rust_facade(
        (),
        _plan(
            _spec(
                "broadcast_source",
                param_names=("value",),
                param_kinds=("s",),
                operation=PrimitiveOperation.VECTOR_SPLAT,
                roles=((OperandRole.VALUE, 0, "s"),),
            )
        ),
    ).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.FREE
    assert method.parameters[0].placement is RustFacadeParameterPlacement.ARGUMENT
    assert method.shape_keys == (("si32", 4),)


def test_vector_value_role_is_a_coherent_receiver() -> None:
    method = plan_rust_facade(
        (),
        _plan(
            _spec(
                "write_value",
                result_kind="void",
                param_names=("mask", "destination", "value"),
                param_kinds=("m", "ptr", "v"),
                operation=PrimitiveOperation.STORE,
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.MEMORY_DESTINATION, 1, "ptr"),
                    (OperandRole.VALUE, 2, "v"),
                ),
                memory=PrimitiveMemoryContract(
                    MemoryAccess.WRITE,
                    MemoryAddressing.CONTIGUOUS,
                ),
                mask_policy="pass_through",
            )
        ),
    ).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.VECTOR
    assert method.parameters[2].placement is RustFacadeParameterPlacement.RECEIVER


def test_curated_unmasked_memory_shapes_are_not_duplicated() -> None:
    vector_store = _spec(
        "source_store",
        result_kind="void",
        param_names=("destination", "value"),
        param_kinds=("ptr", "v"),
        operation=PrimitiveOperation.STORE,
        roles=(
            (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
            (OperandRole.VALUE, 1, "v"),
        ),
        overload=ResolvedPrimitiveOverload("payload_extent", "vector", True),
        memory=PrimitiveMemoryContract(
            MemoryAccess.WRITE,
            MemoryAddressing.CONTIGUOUS,
        ),
    )
    vector_store = replace(
        vector_store,
        axis=(("aligned", "false"),),
        primitive_semantics=replace(
            vector_store.primitive_semantics,
            memory_alignment=LoweredMemoryAlignment(
                "aligned", MemoryAlignment.UNALIGNED
            ),
        ),
    )
    aligned_vector_store = replace(
        vector_store,
        axis=(("aligned", "true"),),
        primitive_semantics=replace(
            vector_store.primitive_semantics,
            memory_alignment=LoweredMemoryAlignment(
                "aligned", MemoryAlignment.ALIGNED
            ),
        ),
    )
    scalar_store = replace(
        vector_store,
        param_names=("destination", "value"),
        param_kinds=("ptr", "s"),
        primitive_semantics=replace(
            vector_store.primitive_semantics,
            overload=ResolvedPrimitiveOverload(
                "payload_extent", "scalar", False
            ),
            operation=_operation(
                PrimitiveOperation.STORE,
                (
                    (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
                    (OperandRole.VALUE, 1, "s"),
                ),
                ("destination", "value"),
            ),
            memory_alignment=LoweredMemoryAlignment(
                "aligned", MemoryAlignment.UNALIGNED
            ),
        ),
    )
    aligned_scalar_store = replace(
        scalar_store,
        axis=(("aligned", "true"),),
        primitive_semantics=replace(
            scalar_store.primitive_semantics,
            memory_alignment=LoweredMemoryAlignment(
                "aligned", MemoryAlignment.ALIGNED
            ),
        ),
    )

    plan = plan_rust_facade(
        (),
        _plan(
            vector_store,
            aligned_vector_store,
            scalar_store,
            aligned_scalar_store,
        ),
    )

    assert len(plan.comprehensive_methods) == 1
    assert plan.comprehensive_methods[0].receiver_kind is RustFacadeReceiverKind.FREE
    assert any(
        entry.reason
        == "unmasked vector store is exposed by the curated memory boundary"
        for entry in plan.coverage
    )


def test_semantically_renamed_memory_primitives_feed_the_curated_core() -> None:
    read_specs = _aligned_memory_specs(
        "read_contiguous",
        operation=PrimitiveOperation.LOAD,
        access=MemoryAccess.READ,
        result_kind="v",
        param_names=("source",),
        param_kinds=("cptr",),
        roles=((OperandRole.MEMORY_SOURCE, 0, "cptr"),),
    )
    write_specs = _aligned_memory_specs(
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
        overload=ResolvedPrimitiveOverload(
            "payload_extent",
            "vector",
            True,
        ),
    )

    plan = plan_rust_facade((), _plan(*read_specs, *write_specs))

    memory_bindings = {
        binding.operation: binding
        for binding in plan.operation_bindings
        if binding.memory_access is not None
    }
    assert memory_bindings[PrimitiveOperation.LOAD].source_primitive_name == (
        "read_contiguous"
    )
    assert memory_bindings[PrimitiveOperation.LOAD].memory_access is (
        MemoryAccess.READ
    )
    assert memory_bindings[PrimitiveOperation.STORE].source_primitive_name == (
        "write_contiguous"
    )
    assert memory_bindings[PrimitiveOperation.STORE].memory_addressing is (
        MemoryAddressing.CONTIGUOUS
    )
    assert {
        (delegate.role, delegate.source_primitive_name)
        for delegate in plan.core_delegates
        if delegate.role in {"load", "store"}
    } == {
        ("load", "read_contiguous"),
        ("store", "write_contiguous"),
    }


def test_memory_operation_without_a_memory_contract_is_diagnostic() -> None:
    missing = _spec(
        "read_without_contract",
        result_kind="v",
        param_names=("source",),
        param_kinds=("cptr",),
        operation=PrimitiveOperation.LOAD,
        roles=((OperandRole.MEMORY_SOURCE, 0, "cptr"),),
        safety=ImplementationSafety(caller_unsafe=True),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(missing))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-MEMORY-CONTRACT"
    }


def test_memory_access_must_agree_with_the_typed_operation() -> None:
    inconsistent = _spec(
        "misclassified_memory",
        result_kind="v",
        param_names=("source",),
        param_kinds=("cptr",),
        operation=PrimitiveOperation.LOAD,
        roles=((OperandRole.MEMORY_SOURCE, 0, "cptr"),),
        safety=ImplementationSafety(caller_unsafe=True),
        memory=PrimitiveMemoryContract(
            MemoryAccess.WRITE,
            MemoryAddressing.CONTIGUOUS,
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(inconsistent))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-MEMORY-CONTRACT"
    }


def test_caller_safety_is_preserved_and_mismatches_are_rejected() -> None:
    unsafe_spec = _spec(
        "unsafe_op",
        safety=ImplementationSafety(caller_unsafe=True),
    )
    method = plan_rust_facade((), _plan(unsafe_spec)).comprehensive_methods[0]
    assert method.caller_unsafe

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(unsafe_spec, replace(unsafe_spec, safety=ImplementationSafety())),
        )
    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-SAFETY-MISMATCH"
    }


def test_public_name_collision_is_rejected_before_rendering() -> None:
    immediate = _spec(
        "collision",
        param_names=("data", "factor"),
        param_kinds=("v", "sImm"),
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.COUNT, 1, "sImm"),
        ),
        immediate=("factor", "i32"),
    )
    already_named = _spec("collision_imm")

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(immediate, already_named))

    assert "TSL-BACKEND-RUST-FACADE-NAME-COLLISION" in {
        diagnostic.code for diagnostic in error.value.diagnostics
    }


def test_curated_name_is_reserved_before_comprehensive_methods() -> None:
    comparison = _spec(
        "comparison_source",
        result_kind="m",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        operation=PrimitiveOperation.COMPARE_EQUAL,
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.SECONDARY, 1, "v"),
        ),
    )
    comprehensive = _spec("simd_eq")

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(comparison, comprehensive))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-NAME-COLLISION"
    }


def test_additive_unaliased_primitive_gets_only_a_comprehensive_method() -> None:
    plan = plan_rust_facade((), _plan(_spec("future_primitive")))

    assert plan.comprehensive_methods[0].public_name == "future_primitive"
    assert plan.trait_implementations == ()
    assert plan.curated_methods == ()


def test_unsupported_runtime_kind_is_excluded_during_planning() -> None:
    plan = plan_rust_facade(
        (),
        _plan(_spec("future_output", result_kind="o")),
    )

    assert plan.comprehensive_methods == ()
    assert plan.coverage[0].status is RustFacadeCoverageStatus.EXCLUDED
    assert plan.coverage[0].reason == "signature kind is not facade-representable"


def test_final_plan_rejects_missing_or_duplicate_comprehensive_arms() -> None:
    plan = plan_rust_facade((), _plan(_spec("future_primitive")))
    method = plan.comprehensive_methods[0]

    with pytest.raises(ValueError, match="require implementation arms"):
        replace(
            plan,
            comprehensive_methods=(
                replace(method, implementation_arms=()),
            ),
        )
    with pytest.raises(ValueError, match="must be unique"):
        replace(
            plan,
            comprehensive_methods=(
                replace(
                    method,
                    implementation_arms=(
                        *method.implementation_arms,
                        method.implementation_arms[0],
                    ),
                ),
            ),
        )
    with pytest.raises(ValueError, match="owner must match"):
        replace(
            method.implementation_arms[0],
            call=replace(
                method.implementation_arms[0].call,
                extension_name="wrong_owner",
            ),
        )
