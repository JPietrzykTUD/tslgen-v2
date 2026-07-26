"""Rust facade signature-type and boundary-adaptation policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.backend.rust_api_model import RustFacadeRepresentation
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.backend.rust_static_selection import (
    RustStaticVectorMapping,
    RustTargetRequirement,
)


@pytest.mark.parametrize(
    (
        "kind",
        "public",
        "private_trait",
        "private_impl",
        "lower_parameter",
        "lower_result",
    ),
    (
        ("void", "()", "()", "()", None, "()"),
        (
            "v",
            "Simd<U, N>",
            "<U as Representation<N>>::Vector",
            "<U as private::Representation<4>>::Vector",
            "Vec::RegisterType",
            "Vec::RegisterType",
        ),
        (
            "m",
            "Mask<U, N>",
            "<U as Representation<N>>::Mask",
            "<U as private::Representation<4>>::Mask",
            "Vec::MaskType",
            "Vec::MaskType",
        ),
        ("im", "u64", "u64", "u64", "Vec::ImaskType", "Vec::ImaskType"),
        ("imt", "u64", "u64", "u64", "Vec::ImaskType", "Vec::ImaskType"),
        ("s", "T", "T", "U", "Vec::BaseType", "Vec::BaseType"),
        ("usize", "usize", "usize", "usize", "usize", "usize"),
        (
            "ptr",
            "*mut T",
            "*mut T",
            "*mut U",
            "*mut Vec::BaseType",
            "*mut Vec::BaseType",
        ),
        (
            "cptr",
            "*const T",
            "*const T",
            "*const U",
            "*const Vec::BaseType",
            "*const Vec::BaseType",
        ),
    ),
)
def test_facade_type_policy_covers_every_runtime_kind(
    kind: str,
    public: str,
    private_trait: str,
    private_impl: str,
    lower_parameter: str | None,
    lower_result: str,
) -> None:
    assert RUST_FACADE_SIGNATURE_TYPES.public_type(
        kind,
        element="T",
        lanes="N",
        result_element="U",
    ) == public
    assert RUST_FACADE_SIGNATURE_TYPES.private_trait_type(
        kind,
        owner="T",
        target_owner="U",
        lanes="N",
    ) == private_trait
    assert RUST_FACADE_SIGNATURE_TYPES.private_impl_type(
        kind,
        owner="U",
        lanes=4,
    ) == private_impl
    if lower_parameter is not None:
        assert RUST_FACADE_SIGNATURE_TYPES.lower_parameter_type(
            kind, owner="Vec"
        ) == lower_parameter
    assert RUST_FACADE_SIGNATURE_TYPES.lower_result_type(
        kind, owner="Vec"
    ) == lower_result


def test_facade_type_policy_excludes_const_only_immediates() -> None:
    assert not RUST_FACADE_SIGNATURE_TYPES.supports_runtime_kind("sImm")
    with pytest.raises(ValueError, match="no runtime type policy"):
        RUST_FACADE_SIGNATURE_TYPES.public_type(
            "sImm",
            element="T",
            lanes="N",
            result_element="T",
        )


def test_facade_type_policy_owns_vector_and_mask_wrapping() -> None:
    assert (
        RUST_FACADE_SIGNATURE_TYPES.adapt_public_argument("v", "value")
        == "value.value"
    )
    assert (
        RUST_FACADE_SIGNATURE_TYPES.adapt_public_argument("m", "mask")
        == "mask.value"
    )
    assert RUST_FACADE_SIGNATURE_TYPES.adapt_public_result(
        "v", "call()", target_element=None
    ) == "Simd { value: call() }"
    assert RUST_FACADE_SIGNATURE_TYPES.adapt_public_result(
        "m", "call()", target_element="U"
    ) == "Mask::<U, _> { value: call() }"


@pytest.mark.parametrize(
    ("imask_spelling", "imask_bits", "argument", "result"),
    (
        ("u8", 8, "bits as u8", "call() as u64"),
        ("u16", 16, "bits as u16", "call() as u64"),
        ("u32", 32, "bits as u32", "call() as u64"),
        ("u64", 64, "bits", "call()"),
    ),
)
def test_facade_type_policy_owns_integral_mask_width_adaptation(
    imask_spelling: str,
    imask_bits: int,
    argument: str,
    result: str,
) -> None:
    mapping = RustStaticVectorMapping(
        "si32",
        "i32",
        4,
        128,
        "Register",
        imask_spelling,
        imask_bits=imask_bits,
    )

    assert RUST_FACADE_SIGNATURE_TYPES.adapt_lower_argument(
        "im", "bits", mapping
    ) == argument
    assert RUST_FACADE_SIGNATURE_TYPES.adapt_lower_result(
        "imt", "call()", mapping
    ) == result


def test_facade_type_policy_rejects_signed_lower_integral_mask() -> None:
    mapping = RustStaticVectorMapping(
        "si32",
        "i32",
        4,
        128,
        "Register",
        "i8",
        imask_bits=8,
    )

    with pytest.raises(ValueError, match="requires the lower scalar spelling"):
        RUST_FACADE_SIGNATURE_TYPES.adapt_lower_argument(
            "im", "bits", mapping
        )


def test_facade_representation_finalizes_qualified_vector_descriptor() -> None:
    fallback = RustFacadeRepresentation(
        None,
        None,
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Register",
            "u64",
            uses_sized_vector=True,
        ),
    )
    hardware = RustFacadeRepresentation(
        "x86-avx2",
        RustTargetRequirement("x86_64", ("avx2",)),
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            8,
            256,
            "__m256i",
            "u8",
            extension_name="avx2",
            extension_tag_spelling="Avx2",
        ),
    )

    assert fallback.vector_descriptor == (
        "crate::tsl_core::Simd<i32, crate::tsl_core::Generic<4>>"
    )
    assert hardware.vector_descriptor == (
        "crate::tsl_core::Simd<i32, crate::tsl_x86_avx2::Avx2>"
    )


def test_comprehensive_renderer_has_no_local_signature_kind_tables() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "tslc"
        / "render"
        / "rust_facade_comprehensive.py"
    ).read_text(encoding="utf-8")

    assert "def _raw_type" not in source
    assert "def _impl_raw_type" not in source
    assert "def _public_type" not in source
    assert '"im": "u64"' not in source
    assert '"imt": "u64"' not in source

    curated_source = (
        Path(__file__).parents[1]
        / "src"
        / "tslc"
        / "render"
        / "rust_facade.py"
    ).read_text(encoding="utf-8")
    assert "documentation_short_label" not in curated_source
