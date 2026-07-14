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


def test_projection_reports_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="requires index_type"):
        CPP_SIGNATURE_TYPES.parameter_type("vidx", target_vector="ToVec")


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
