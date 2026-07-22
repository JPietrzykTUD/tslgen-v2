"""Rust-backend ownership of direct implementation calls."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.rust import RustBackend
from tslc.benchmark.model import SpecializationKey
from tslc.catalog.model import ImplementationSafety
from tslc.lower.lowerer import (
    LoweredImplementationVariant,
    LoweredSpecialization,
)
from tslc.target_text import LoweredBody


def _spec() -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="rust",
        primitive_name="mul",
        source_primitive_name="mul",
        extension_name="sse2",
        type_tag="si8",
        base_type_spelling="i8",
        register_spelling="core::arch::x86_64::__m128i",
        result_kind="v",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        body=LoweredBody.from_text("return left;"),
        vector_spelling="Simd<i8, Sse2>",
        variant_bodies=(
            LoweredImplementationVariant(
                "generic_fallback",
                LoweredBody.from_text("return right;"),
            ),
        ),
    )


def test_direct_implementation_call_owns_default_and_variant_trait_names() -> None:
    backend = RustBackend()
    spec = _spec()
    module = "crate::tsl_sse2"

    assert backend.render_direct_implementation_call(
        spec,
        None,
        ("left", "right"),
        module_prefix=module,
    ) == (
        "<Simd<i8, Sse2> as "
        "crate::tsl_sse2::detail::primitives::MulImpl>::apply(left, right)"
    )

    selectable_spec = replace(
        spec,
        extension_name="sse",
        vector_spelling="Simd<i8, Sse>",
    )
    selectable_key = SpecializationKey(
        backend_id="rust",
        profile_name="sse2",
        primitive_name="mul",
        source_primitive_name="mul",
        extension_name="sse",
        type_tag="si8",
        result_kind="v",
        param_kinds=("v", "v"),
        lanes=16,
    )
    assert backend.render_direct_implementation_call(
        selectable_spec,
        None,
        ("left", "right"),
        module_prefix=module,
        selection_key=selectable_key,
    ) == (
        "<Simd<i8, Sse> as "
        "crate::tsl_sse2::detail::primitives::Mul_defaultImpl>"
        "::apply(left, right)"
    )
    assert backend.render_direct_implementation_call(
        spec,
        "generic_fallback",
        ("left", "right"),
        module_prefix=module,
    ) == (
        "<Simd<i8, Sse2> as "
        "crate::tsl_sse2::detail::primitives::Mul_generic_fallbackImpl>"
        "::apply(left, right)"
    )


def test_direct_implementation_call_owns_const_argument_order_and_unsafe() -> None:
    spec = replace(
        _spec(),
        axis=(("aligned", "false"),),
        immediate=("amount", "u32"),
        generic_params=(("PreserveSign", "bool", "true"),),
        param_names=("left", "amount"),
        param_kinds=("v", "sImm"),
        safety=ImplementationSafety(caller_unsafe=True),
    )

    rendered = RustBackend().render_direct_implementation_call(
        spec,
        "generic_fallback",
        ("left",),
        module_prefix="crate::profile",
        immediate_value="4",
    )

    assert rendered == (
        "unsafe { <Simd<i8, Sse2> as "
        "crate::profile::detail::primitives::Mul_generic_fallbackImpl"
        "<false, 4, true>>::apply(left) }"
    )


def test_direct_implementation_call_rejects_unknown_candidate_and_wrong_arity() -> None:
    backend = RustBackend()
    spec = _spec()

    with pytest.raises(ValueError, match="candidate 'missing' is not available"):
        backend.render_direct_implementation_call(spec, "missing", ("left", "right"))
    with pytest.raises(ValueError, match="requires 2 runtime arguments, got 1"):
        backend.render_direct_implementation_call(spec, None, ("left",))


def test_direct_implementation_call_owns_overload_receiver_dispatch() -> None:
    spec = replace(
        _spec(),
        primitive_name="shift_right",
        source_primitive_name="shift_right",
        generic_params=(("PreserveSign", "bool", "false"),),
        variant_bodies=(
            LoweredImplementationVariant(
                "generic_fallback",
                LoweredBody.from_text("return right;"),
            ),
        ),
    )

    rendered = RustBackend().render_direct_implementation_call(
        spec,
        "generic_fallback",
        ("data", "shift"),
        module_prefix="crate::profile",
        overload_parameter_positions=(1,),
    )

    assert rendered == (
        "<core::arch::x86_64::__m128i as "
        "crate::profile::detail::primitives::Shift_right_generic_fallbackImplArg"
        "<Simd<i8, Sse2>, false>>::apply(shift, data)"
    )


def test_concrete_vector_type_matches_normal_impl_rendering() -> None:
    backend = RustBackend()
    explicit = _spec()
    sized = replace(
        explicit,
        extension_name="sized",
        vector_spelling=None,
        uses_sized_vector=True,
        lane_parameter="LANES",
    )

    assert backend.concrete_vector_type(explicit) == "Simd<i8, Sse2>"
    assert backend.concrete_vector_type(sized) == "Simd<i8, Sized<LANES>>"
    assert "impl MulImpl for Simd<i8, Sse2>" in backend.render_primitive_internal(
        "mul", (explicit,)
    )
