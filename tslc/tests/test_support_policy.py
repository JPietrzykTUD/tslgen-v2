"""Central support policy facts stay in one small module."""

from __future__ import annotations

import pytest

from tslc.backend.registry import (
    backend_capabilities,
    create_backend_dialect,
    registered_backend_ids,
)
from tslc.catalog.model import Catalog, RESULT_DIM_BASE, RESULT_DIM_EXTENSION
from tslc.catalog.signature_kinds import (
    SignatureKindCapability,
    SignatureKindCatalog,
)
from tslc.catalog.signatures import parse_signature
from tslc.render.backend_drivers import render_backend_drivers
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def test_policy_owns_backend_and_signature_support(catalog: Catalog) -> None:
    policy = DEFAULT_SUPPORT_POLICY

    assert policy.default_backend_ids == ("cpp", "rust")
    assert policy.supports_backend("cpp")
    assert not policy.supports_backend("c17")
    assert policy.supports_signature(parse_signature("v:=(ptr,vidx,sImm)"))
    assert policy.supports_signature(parse_signature("v:=(cptr,vidx,sImm)"))
    lane_list_shape = parse_signature("v:=(lanes<s>)")
    assert lane_list_shape is not None
    assert lane_list_shape.param_kinds == ("lanes<s>",)
    assert lane_list_shape.param_terms[0].is_lane_list
    assert lane_list_shape.param_terms[0].lane_element_kind == "s"
    assert policy.supports_signature(lane_list_shape)
    assert policy.has_lane_list_parameter(lane_list_shape)
    sve = catalog.extensions["sve"]
    assert policy.deferred_signature_kinds_for_extension(lane_list_shape, sve) == (
        frozenset({"lanes<s>"})
    )
    assert policy.unsupported_signature_kinds_for_extension(lane_list_shape, sve) == (
        frozenset({"lanes<s>"})
    )
    result_lane_list_shape = parse_signature("lanes<s>:=v")
    assert result_lane_list_shape is not None
    assert not policy.supports_signature(result_lane_list_shape)
    assert policy.unsupported_signature_kinds(parse_signature("opaque:=v")) == frozenset(
        {"opaque"}
    )


def test_backend_registries_agree_with_support_policy(catalog: Catalog) -> None:
    assert registered_backend_ids() == DEFAULT_SUPPORT_POLICY.default_backend_ids
    capabilities = backend_capabilities(DEFAULT_SUPPORT_POLICY.default_backend_ids)
    assert tuple(capability.backend_id for capability in capabilities) == (
        DEFAULT_SUPPORT_POLICY.default_backend_ids
    )
    assert tuple(
        driver.backend_id
        for driver in render_backend_drivers(DEFAULT_SUPPORT_POLICY.default_backend_ids)
    ) == DEFAULT_SUPPORT_POLICY.default_backend_ids
    assert tuple(capability.root_path for capability in capabilities) == ("cpp", "rust")
    assert tuple(
        capability.value_test_support().backend_id for capability in capabilities
    ) == DEFAULT_SUPPORT_POLICY.default_backend_ids
    assert tuple(capability.verify_driver().backend_id for capability in capabilities) == (
        DEFAULT_SUPPORT_POLICY.default_backend_ids
    )
    assert create_backend_dialect(catalog, "cpp").backend_id == "cpp"
    assert create_backend_dialect(catalog, "rust").backend_id == "rust"
    with pytest.raises(ValueError, match="unsupported backend"):
        create_backend_dialect(catalog, "c17")
    with pytest.raises(ValueError, match="unsupported backend"):
        backend_capabilities(("c17",))


def test_policy_owns_mask_forms() -> None:
    policy = DEFAULT_SUPPORT_POLICY
    add_shape = parse_signature("v:=(m,v,v)")
    gather_shape = parse_signature("v:=(m,cptr,vidx,v,sImm)")
    assert add_shape is not None
    assert gather_shape is not None

    assert policy.mask_suffix("zero") == "_maskz"
    assert policy.mask_suffix("pass_through") == "_mask"
    assert policy.mask_split_base("add_maskz") == "add"
    assert policy.is_maskable_signature(add_shape)
    assert not policy.is_maskable_signature(gather_shape)


def test_signature_kind_capabilities_single_source_projection_rules() -> None:
    policy = DEFAULT_SUPPORT_POLICY

    assert policy.supported_signature_kinds >= {
        "v",
        "s",
        "m",
        "im",
        "usize",
        "sImm",
        "ptr",
        "cptr",
        "void",
        "s[]",
        policy.lane_list_kind,
        "vt",
        "vidx",
        "o",
    }
    assert policy.pointer_kinds == frozenset({"ptr", "ptr+", "cptr", "cptr+"})
    assert policy.scalable_deferred_signature_kinds == frozenset(
        {"s[]", policy.lane_list_kind}
    )
    assert not policy.signature_kind_requires_vector_axis("ptr")
    assert policy.signature_kind_requires_vector_axis("s")
    assert policy.is_free_function_signature("ptr", ("usize",))
    assert not policy.is_free_function_signature("void", ("ptr", "s", "s"))
    assert policy.overload_identity_token("v", register_is_base=True) == "base"
    assert policy.overload_identity_token("v", register_is_base=False) == "register"
    assert policy.overload_identity_token("vidx", register_is_base=False) == (
        "index_register"
    )
    assert policy.cpp_result_type("m") == "typename Vec::mask_type"
    assert policy.cpp_param_type("vidx", index_type="IndicesType") == (
        "typename tsl::reg_param<IndicesType>::type"
    )
    assert policy.rust_owner_type("o", owner="S") == "&mut String"
    assert policy.rust_param_type("s[]", owner="S") == "&S::Array"
    assert (
        policy.rust_concrete_type(
            "ptr",
            base_type="i32",
            register_type="__m128i",
            array_type="[i32; 4]",
        )
        == "*mut i32"
    )
    with pytest.raises(ValueError, match="requires index_type"):
        policy.cpp_param_type("vidx")


def test_signature_kind_catalog_rejects_ambiguous_capabilities() -> None:
    required = (
        SignatureKindCapability("sImm", immediate_operand=True),
        SignatureKindCapability("lanes<s>", lane_list=True),
        SignatureKindCapability("vidx", index_vector=True),
    )
    with pytest.raises(ValueError, match="duplicate signature kind"):
        SignatureKindCatalog(
            (
                *required,
                SignatureKindCapability("x"),
                SignatureKindCapability("x"),
            )
        )

    with pytest.raises(ValueError, match="expected exactly one signature kind"):
        SignatureKindCatalog(
            (
                SignatureKindCapability("sImm", immediate_operand=True),
                SignatureKindCapability("lanes<s>", lane_list=True),
                SignatureKindCapability("vidx1", index_vector=True),
                SignatureKindCapability("vidx2", index_vector=True),
            )
        )


def test_target_family_catalog_drives_extension_profile_routing(catalog: Catalog) -> None:
    policy = DEFAULT_SUPPORT_POLICY
    target_families = catalog.target_families

    assert target_families.known_extension_families >= {
        "scalar",
        "generic_like",
        "x86",
        "arm",
        "cuda",
    }
    assert policy.supports_extension_family("arm", target_families)
    assert not policy.supports_extension_family("cuda", target_families)
    assert policy.extension_targets_profile("scalar", "aarch64", target_families)
    assert policy.extension_targets_profile("generic_like", "x86", target_families)
    assert policy.extension_targets_profile("x86", "x86", target_families)
    assert policy.extension_targets_profile("arm", "aarch64", target_families)
    assert not policy.extension_targets_profile("x86", "aarch64", target_families)
    assert not policy.extension_targets_profile("arm", "generic", target_families)


def test_policy_does_not_support_transition_variadic_shape() -> None:
    policy = DEFAULT_SUPPORT_POLICY
    set_shape = parse_signature("v:=s...")
    assert set_shape is not None

    assert not policy.supports_signature(set_shape)
    assert policy.unsupported_signature_kinds(set_shape) == frozenset({"s..."})


def test_policy_derives_sized_vector_capability_from_extension_metadata(
    catalog: Catalog,
) -> None:
    policy = DEFAULT_SUPPORT_POLICY
    sized = catalog.extensions["generic"]
    scalar = catalog.extensions["scalar"]

    assert sized.vector_bits_kind == "sized"
    assert sized.size_parameter_name == "LANES"
    assert policy.uses_sized_vector(sized)
    assert not policy.uses_sized_vector(scalar)
    assert policy.register_is_base(scalar)
    assert not policy.register_is_base(sized)


def test_policy_owns_type_width_and_target_dimension_rules() -> None:
    policy = DEFAULT_SUPPORT_POLICY

    assert policy.same_type_width("ui32", "si32")
    assert not policy.same_type_width("ui64", "si32")
    assert policy.supports_sized_vector_target_dimension(RESULT_DIM_BASE)
    assert not policy.supports_sized_vector_target_dimension(RESULT_DIM_EXTENSION)
