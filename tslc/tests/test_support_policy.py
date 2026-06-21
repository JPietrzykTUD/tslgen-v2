"""Central support policy facts stay in one small module."""

from __future__ import annotations

from tslc.catalog.model import Catalog, RESULT_DIM_BASE, RESULT_DIM_EXTENSION
from tslc.catalog.signatures import parse_signature
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def test_policy_owns_backend_and_signature_support() -> None:
    policy = DEFAULT_SUPPORT_POLICY

    assert policy.default_backend_ids == ("cpp", "rust")
    assert policy.supports_backend("cpp")
    assert not policy.supports_backend("c17")
    assert policy.supports_signature(parse_signature("v:=(ptr,vidx,sImm)"))
    assert policy.unsupported_signature_kinds(parse_signature("opaque:=v")) == frozenset(
        {"opaque"}
    )


def test_policy_owns_mask_forms() -> None:
    policy = DEFAULT_SUPPORT_POLICY
    add_shape = parse_signature("v:=(m,v,v)")
    gather_shape = parse_signature("v:=(m,ptr,vidx,v,sImm)")
    assert add_shape is not None
    assert gather_shape is not None

    assert policy.mask_suffix("zero") == "_maskz"
    assert policy.mask_suffix("pass_through") == "_mask"
    assert policy.mask_split_base("add_maskz") == "add"
    assert policy.is_maskable_signature(add_shape)
    assert not policy.is_maskable_signature(gather_shape)


def test_policy_owns_deferred_family_and_variadic_rules() -> None:
    policy = DEFAULT_SUPPORT_POLICY
    set_shape = parse_signature("v:=s...")
    assert set_shape is not None

    assert policy.supports_extension_family("generic_like")
    assert not policy.supports_extension_family("arm")
    assert "sized-vector variadic fallback loops" in policy.deferred_cases


def test_policy_derives_sized_vector_capability_from_extension_metadata(
    catalog: Catalog,
) -> None:
    policy = DEFAULT_SUPPORT_POLICY
    set_shape = parse_signature("v:=s...")
    assert set_shape is not None
    sized = catalog.extensions["generic"]
    scalar = catalog.extensions["scalar"]

    assert sized.vector_bits_kind == "sized"
    assert sized.size_parameter_name == "LANES"
    assert policy.uses_sized_vector(sized)
    assert policy.skips_variadic_on_extension(sized, set_shape)
    assert not policy.uses_sized_vector(scalar)
    assert not policy.skips_variadic_on_extension(scalar, set_shape)
    assert policy.register_is_base(scalar)
    assert not policy.register_is_base(sized)


def test_policy_owns_type_width_and_target_dimension_rules() -> None:
    policy = DEFAULT_SUPPORT_POLICY

    assert policy.same_type_width("ui32", "si32")
    assert not policy.same_type_width("ui64", "si32")
    assert policy.supports_sized_vector_target_dimension(RESULT_DIM_BASE)
    assert not policy.supports_sized_vector_target_dimension(RESULT_DIM_EXTENSION)
