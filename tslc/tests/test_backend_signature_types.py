"""Signature type spellings are backend-owned and independently extensible."""

from __future__ import annotations

from dataclasses import fields

import pytest

from tslc.backend.signature_types import (
    BackendSignatureTypes,
    CPP_SIGNATURE_TYPES,
    RUST_SIGNATURE_TYPES,
    SignatureTypeForms,
    rust_free_type,
)
from tslc.catalog.signature_kinds import SignatureKindCapability


def test_catalog_signature_kinds_are_backend_neutral() -> None:
    names = {item.name for item in fields(SignatureKindCapability)}
    assert not any(name.startswith(("cpp_", "rust_")) for name in names)


def test_backend_emitters_own_signature_type_projections() -> None:
    assert CPP_SIGNATURE_TYPES.result_type("m") == "typename Vec::mask_type"
    assert (
        CPP_SIGNATURE_TYPES.parameter_type(
            "vidx",
            index_type="IndicesType",
            target_vector="ToVec",
        )
        == "typename tsl::reg_param<IndicesType>::type"
    )
    assert RUST_SIGNATURE_TYPES.owner_type("s", owner="Simd") == "Simd::BaseType"
    assert RUST_SIGNATURE_TYPES.parameter_type("s[]", owner="Simd") == "&Simd::Array"
    assert (
        RUST_SIGNATURE_TYPES.concrete_type(
            "v",
            base="i32",
            register="__m128i",
            array="[i32; 4]",
        )
        == "__m128i"
    )
    assert rust_free_type("cptr", "*mut i32") == "*const i32"
    assert CPP_SIGNATURE_TYPES.free_type("ptr", base="std::uint64_t") == (
        "std::uint64_t *"
    )
    assert CPP_SIGNATURE_TYPES.free_type("cptr", base="std::uint64_t") == (
        "const std::uint64_t *"
    )
    assert rust_free_type("ptr", "u64") == "*mut u64"


def test_free_pointer_projection_does_not_add_a_second_pointer_layer() -> None:
    assert (
        CPP_SIGNATURE_TYPES.free_type(
            "ptr",
            base="void *",
            base_type_tag="ptr",
        )
        == "void *"
    )
    assert (
        CPP_SIGNATURE_TYPES.free_type(
            "cptr",
            base="void *",
            base_type_tag="ptr",
        )
        == "const void *"
    )
    assert (
        rust_free_type(
            "ptr",
            "*mut core::ffi::c_void",
            base_type_tag="ptr",
        )
        == "*mut core::ffi::c_void"
    )
    assert (
        rust_free_type(
            "cptr",
            "*mut core::ffi::c_void",
            base_type_tag="ptr",
        )
        == "*const core::ffi::c_void"
    )


def test_projection_reports_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="requires index_type"):
        CPP_SIGNATURE_TYPES.parameter_type("vidx", target_vector="ToVec")


def test_cpp_member_projections_are_vector_scoped() -> None:
    assert (
        CPP_SIGNATURE_TYPES.member_type("v", vector="MyVec")
        == "typename MyVec::register_type"
    )
    assert (
        CPP_SIGNATURE_TYPES.member_parameter_type("v", vector="MyVec")
        == "typename ::tsl::reg_param<MyVec>::type"
    )
    assert (
        CPP_SIGNATURE_TYPES.member_parameter_type("cptr", vector="MyVec")
        == "typename MyVec::base_type const*"
    )
    assert CPP_SIGNATURE_TYPES.member_type("void", vector="MyVec") == "void"


def test_concrete_integral_mask_projections_are_width_scoped() -> None:
    for width, cpp, rust in (
        (8, "std::uint8_t", "u8"),
        (16, "std::uint16_t", "u16"),
        (32, "std::uint32_t", "u32"),
        (64, "std::uint64_t", "u64"),
    ):
        assert (
            CPP_SIGNATURE_TYPES.concrete_integral_mask_type("im", width=str(width))
            == cpp
        )
        assert (
            RUST_SIGNATURE_TYPES.concrete_integral_mask_type("im", width=str(width))
            == rust
        )


def test_benchmark_policy_parameter_types_come_from_the_shared_table() -> None:
    from tslc.benchmark.render_cpp import _policy_parameter_type

    kinds = sorted(
        kind
        for kind in CPP_SIGNATURE_TYPES.supported_kinds
        if CPP_SIGNATURE_TYPES.supports(kind, "member_parameter")
    )
    assert {"v", "s", "m", "im", "usize", "ptr", "ptr+", "cptr", "cptr+"} <= set(kinds)
    for kind in kinds:
        assert _policy_parameter_type(kind, "MyVec") == (
            CPP_SIGNATURE_TYPES.member_parameter_type(kind, vector="MyVec")
        )


def test_cpp_dataparallel_facade_types_come_from_the_shared_table() -> None:
    from tslc.backend.cpp import (
        _dataparallel_facade_param_type,
        _dataparallel_facade_result_type,
    )

    for kind in ("v", "m", "s", "usize", "void"):
        assert _dataparallel_facade_result_type(kind, "MyVec") == (
            CPP_SIGNATURE_TYPES.member_type(kind, vector="MyVec")
        )
    for kind in ("v", "m", "s", "cptr", "ptr"):
        assert _dataparallel_facade_param_type(kind, "MyVec", None) == (
            CPP_SIGNATURE_TYPES.member_parameter_type(kind, vector="MyVec")
        )
    assert _dataparallel_facade_param_type("vt", "MyVec", "ToVec") == (
        CPP_SIGNATURE_TYPES.member_parameter_type("vt", vector="ToVec")
    )


def test_rust_facade_types_come_from_the_shared_table() -> None:
    from tslc.backend.rust_facades import (
        _rust_facade_param_type,
        _rust_facade_result_type,
    )

    for kind in ("v", "m", "s", "usize"):
        assert _rust_facade_result_type(kind, "V") == (
            RUST_SIGNATURE_TYPES.owner_type(kind, owner="<V as SimdVector>")
        )
    for kind in ("v", "m", "s"):
        assert _rust_facade_param_type(kind, "V", None) == (
            RUST_SIGNATURE_TYPES.parameter_type(kind, owner="<V as SimdVector>")
        )
    assert _rust_facade_param_type("vt", "V", "W") == (
        RUST_SIGNATURE_TYPES.parameter_type("vt", owner="<W as SimdVector>")
    )


def test_pivot_fixed_types_match_the_backend_projection() -> None:
    from tslc.pivot.model import PivotLanguage
    from tslc.pivot.planner import _SUPPORTED_KINDS, _fixed_type

    cpp_expected = {
        "v": "typename MyVec::register_type",
        "m": "typename MyVec::mask_type",
        "im": "typename MyVec::imask_type",
        "s": "base_t",
        "usize": "std::size_t",
    }
    rust_expected = {
        "v": "<MyVec as tsl::tsl_core::SimdVector>::RegisterType",
        "m": "<MyVec as tsl::tsl_core::SimdVector>::MaskType",
        "im": "<MyVec as tsl::tsl_core::SimdVector>::ImaskType",
        "s": "base_t",
        "usize": "usize",
    }
    assert set(cpp_expected) == set(_SUPPORTED_KINDS)
    assert set(rust_expected) == set(_SUPPORTED_KINDS)
    for kind in sorted(_SUPPORTED_KINDS):
        assert (
            _fixed_type(PivotLanguage.CPP, kind, "MyVec", "base_t")
            == cpp_expected[kind]
        )
        assert (
            _fixed_type(PivotLanguage.RUST, kind, "MyVec", "base_t")
            == rust_expected[kind]
        )


def test_rust_fixed_vector_spelling_is_owned_by_the_rust_backend() -> None:
    from tslc.backend.rust_algorithm import rust_fixed_vector_spelling

    assert rust_fixed_vector_spelling("i32", 4) == (
        "<tsl::dataparallel::Fixed<4> as "
        "tsl::tsl_algorithm::VectorFor<tsl::profile::algo::Profile, i32>>::Vec"
    )


def test_new_backend_projection_does_not_change_catalog_model() -> None:
    fake = BackendSignatureTypes(
        "fake",
        {
            "v": SignatureTypeForms(
                result="vec<{base}>",
                parameter="&{owner}",
            )
        },
    )

    assert fake.result_type("v", base="i16") == "vec<i16>"
    assert fake.parameter_type("v", owner="Vector") == "&Vector"
    assert {item.name for item in fields(SignatureKindCapability)}.isdisjoint(
        {"fake_result", "fake_parameter"}
    )
