"""Rust facade representation, delegate, and core-surface tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import (
    _fallback_extension,
    _plan,
    _spec,
)
from tslc.backend.rust_api_model import (
    RustFacadeCoreDelegate,
    RustFacadeInvocation,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustFacadeTargetSelection,
    rust_facade_representations_can_coexist,
)
from tslc.backend.rust_api_planner import (
    RUST_FACADE_CORE_OPERATION_REQUIREMENTS,
    RustFacadePlanningError,
    plan_rust_facade,
)
from tslc.backend.rust_static_selection import (
    RustStaticVectorMapping,
    RustTargetRequirement,
)
from tslc.backend.rust_api_surface import _core_implementation_arms
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryAlignment,
    PrimitiveMemoryContract,
)
from tslc.catalog.model import ImplementationSafety
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.lower.primitive_semantics import LoweredMemoryAlignment
from tslc.render.rust_facade import _facade_impl
from tslc.render.rust_facade_common import selection_cfg
from tslc.render.rust_facade_comprehensive import render_comprehensive_facade


def test_generic_fallback_excludes_exact_profile_arms_without_width_holes() -> None:
    avx2 = RustTargetRequirement("x86_64", ("avx2",))
    avx512 = RustTargetRequirement("x86_64", ("avx2", "avx512f"))
    fallback = RustFacadeRepresentation(
        None,
        None,
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Simd<i32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
        (RustFacadeTargetSelection(avx2, (avx512,)),),
    )
    avx2_representation = RustFacadeRepresentation(
        "avx2",
        avx2,
        (avx512,),
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Simd<i32, Sse>",
            "u8",
            "sse",
            "Sse",
        ),
    )
    avx512_representation = RustFacadeRepresentation(
        "avx512",
        avx512,
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            16,
            512,
            "Simd<i32, Avx512>",
            "u16",
            "avx512",
            "Avx512",
        ),
    )

    rendered = selection_cfg(fallback)

    assert 'target_feature = "avx2"' in rendered
    assert 'target_feature = "avx512f"' in rendered
    assert rendered.startswith("not(any(all(")
    assert not rust_facade_representations_can_coexist(
        fallback, avx2_representation
    )
    assert rust_facade_representations_can_coexist(
        fallback, avx512_representation
    )


def test_attribute_combinations_remain_delegate_owned() -> None:
    base = _spec("configured_axis")
    false_spec = replace(base, axis=(("aligned", "false"),))
    true_spec = replace(base, axis=(("aligned", "true"),))

    method = plan_rust_facade(
        (), _plan(false_spec, true_spec)
    ).comprehensive_methods[0]

    assert method.delegates[0].vectors[0].attribute_combinations == (
        (("aligned", "false"),),
        (("aligned", "true"),),
    )


def test_novel_fallback_ids_survive_shape_and_delegate_planning() -> None:
    scalar_extension = _fallback_extension("portable_lane_one", sized=False)
    sized_extension = _fallback_extension("portable_fixed_lanes", sized=True)
    base = _spec("portable_operation")
    scalar = replace(
        base,
        extension_name=scalar_extension.name,
        uses_sized_vector=False,
        lane_parameter=None,
        register_is_base=True,
        register_spelling="i32",
    )
    sized = replace(base, extension_name=sized_extension.name)
    static = _plan(
        scalar,
        sized,
        fallback_extensions=(scalar_extension, sized_extension),
        fallback_mappings=(
            RustStaticVectorMapping(
                "si32", "i32", 1, 32, "Simd<i32, Scalar>", "u64"
            ),
            RustStaticVectorMapping(
                "si32",
                "i32",
                4,
                128,
                "Simd<i32, Generic<4>>",
                "u64",
                uses_sized_vector=True,
            ),
        ),
    )

    plan = plan_rust_facade((), static)
    method = plan.comprehensive_methods[0]
    owners = {
        (owner.type_tag, owner.lanes): owner.extension_name
        for owner in method.delegates[0].owners
    }

    assert owners == {
        ("si32", 1): "portable_lane_one",
        ("si32", 4): "portable_fixed_lanes",
    }
    assert {
        arm.call.extension_name for arm in method.implementation_arms
    } == {"portable_lane_one", "portable_fixed_lanes"}
    rendered = render_comprehensive_facade(plan)
    assert rendered.private_impls.count("portable_operation::<") == 2


def test_same_lane_count_can_have_different_fallback_owners() -> None:
    first_extension = _fallback_extension("portable_first", sized=True)
    second_extension = _fallback_extension("portable_second", sized=True)
    first = replace(_spec("first_operation"), extension_name=first_extension.name)
    second = replace(
        _spec("second_operation"),
        extension_name=second_extension.name,
    )

    plan = plan_rust_facade(
        (),
        _plan(
            first,
            second,
            fallback_extensions=(first_extension, second_extension),
        ),
    )

    owners = {
        method.public_name: method.delegates[0].owners[0].extension_name
        for method in plan.comprehensive_methods
    }
    assert owners == {
        "first_operation": "portable_first",
        "second_operation": "portable_second",
    }


def test_ambiguous_fallback_delegate_owners_are_rejected() -> None:
    first_extension = _fallback_extension("portable_first", sized=True)
    second_extension = _fallback_extension("portable_second", sized=True)
    base = _spec("ambiguous_operation")

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(
                replace(base, extension_name=first_extension.name),
                replace(base, extension_name=second_extension.name),
                fallback_extensions=(first_extension, second_extension),
            ),
        )

    assert {item.code for item in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-AMBIGUOUS-DELEGATE-OWNER"
    }


def test_fallback_mapping_without_an_emitted_owner_is_rejected() -> None:
    scalar_extension = _fallback_extension("portable_lane_one", sized=False)
    scalar = replace(
        _spec("scalar_only"),
        extension_name=scalar_extension.name,
        uses_sized_vector=False,
        lane_parameter=None,
        register_is_base=True,
        register_spelling="i32",
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(
                scalar,
                fallback_extensions=(scalar_extension,),
            ),
        )

    assert {item.code for item in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-MISSING-FALLBACK-OWNER"
    }


def test_core_store_and_lane_insertion_render_from_finalized_invocations() -> None:
    representation = RustFacadeRepresentation(
        None,
        None,
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Simd<i32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
    )
    shape = RustFacadeShape("si32", "i32", 4, 128, (representation,))
    delegates = tuple(
        RustFacadeCoreDelegate(
            role=requirement.role,
            type_tag="si32",
            lanes=4,
            profile_name=None,
            source_primitive_name=f"test_{requirement.role}",
            extension_name="test_fallback",
            invocation=RustFacadeInvocation(
                (
                    (1, 0)
                    if requirement.role == "store"
                    else (2, 0, 1)
                    if requirement.role == "insert_lane"
                    else tuple(range(len(requirement.parameter_kinds)))
                )
            ),
        )
        for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
    )
    arm = _core_implementation_arms(delegates, (shape,))[0]

    rendered = _facade_impl(arm)

    assert "test_store::<" in rendered
    assert ">(value, destination)" in rendered
    assert "test_insert_lane::<" in rendered
    assert ">(lane, value, index)" in rendered
    with pytest.raises(ValueError, match="complete FacadeOps role inventory"):
        replace(arm, calls=arm.calls[:-1])


@pytest.mark.parametrize(
    "indices",
    (
        (0, 0),
        (1,),
        (0, 2),
    ),
)
def test_invocation_requires_an_exact_argument_permutation(
    indices: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError, match="exact permutation"):
        RustFacadeInvocation(indices)


def test_inconsistent_core_memory_roles_are_rejected_before_rendering() -> None:
    spec = _spec(
        "incomplete_store",
        result_kind="void",
        param_names=("value", "destination"),
        param_kinds=("v", "ptr"),
        operation=PrimitiveOperation.STORE,
        roles=((OperandRole.VALUE, 0, "v"),),
        overload=ResolvedPrimitiveOverload("payload_extent", "vector", True),
        safety=ImplementationSafety(caller_unsafe=True),
        memory=PrimitiveMemoryContract(
            MemoryAccess.WRITE,
            MemoryAddressing.CONTIGUOUS,
        ),
        memory_alignment=LoweredMemoryAlignment(
            "aligned", MemoryAlignment.UNALIGNED
        ),
    )
    spec = replace(spec, axis=(("aligned", "false"),))
    aligned_spec = replace(
        spec,
        axis=(("aligned", "true"),),
        primitive_semantics=replace(
            spec.primitive_semantics,
            memory_alignment=LoweredMemoryAlignment(
                "aligned", MemoryAlignment.ALIGNED
            ),
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(spec, aligned_spec))

    assert {item.code for item in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-MEMORY-CONTRACT"
    }
