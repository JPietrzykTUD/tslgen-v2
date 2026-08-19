"""Catalog-derived support policy views stay outside the policy object."""

from __future__ import annotations

from tslc.catalog.model import (
    Catalog,
    PrimitiveCastMode,
    PrimitiveMaskMode,
    PrimitiveValueMode,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.support_policy_views import (
    concrete_target_candidates,
    explicit_mask_split_names,
    immediate_split_names,
    is_maskable_primitive,
    policy_split_names,
    selectable_variants,
)


def test_views_classify_maskable_and_immediate_splits(catalog: Catalog) -> None:
    policy = DEFAULT_SUPPORT_POLICY
    add = catalog.primitives_named("add", unmasked=False)
    gather = catalog.primitives_named("gather", unmasked=False)

    assert [is_maskable_primitive(p, policy) for p in add] == [True, True, True]
    assert [is_maskable_primitive(p, policy) for p in gather] == [True, True]
    assert "add" in policy_split_names(catalog, policy)
    assert "gather" in policy_split_names(catalog, policy)
    assert {"shift_left", "shift_right"} <= immediate_split_names(catalog, policy)
    assert "insert" not in immediate_split_names(catalog, policy)
    assert "hadd" in explicit_mask_split_names(catalog)
    assert "add" not in explicit_mask_split_names(catalog)


def test_views_select_callable_variants(catalog: Catalog) -> None:
    policy = DEFAULT_SUPPORT_POLICY

    add_variants = selectable_variants(catalog, "add", policy)
    gather_variants = selectable_variants(catalog, "gather", policy)

    assert add_variants
    assert any("mask" in p.attributes for p in add_variants)
    assert {p.mask_mode for p in add_variants} == {
        None,
        PrimitiveMaskMode.PASS_THROUGH,
        PrimitiveMaskMode.ZERO,
    }
    assert all(p.name == "add" for p in add_variants)
    assert gather_variants
    assert any("mask" in p.attributes for p in gather_variants)


def test_views_filter_representation_change_targets(catalog: Catalog) -> None:
    policy = DEFAULT_SUPPORT_POLICY
    reinterpret = catalog.primitives_named("reinterpret", unmasked=False)[0]
    extract = catalog.primitives_named("extract", unmasked=False)[0]
    set_undef = catalog.primitives_named("set_undef", unmasked=False)[0]

    assert reinterpret.cast_mode is PrimitiveCastMode.REINTERPRET
    assert set_undef.value_mode is PrimitiveValueMode.UNDEFINED

    assert concrete_target_candidates(
        catalog, reinterpret, "avx2", "si32", policy
    ) == (
        "f32",
        "f64",
        "si16",
        "si32",
        "si64",
        "si8",
        "ui16",
        "ui32",
        "ui64",
        "ui8",
    )
    assert concrete_target_candidates(
        catalog, reinterpret, "generic", "si32", policy
    ) == ("f32", "si32", "ui32")
    assert concrete_target_candidates(
        catalog, reinterpret, "scalar", "si32", policy
    ) == ("f32", "si32", "ui32")
    assert concrete_target_candidates(catalog, extract, "avx2", "si32", policy) == ("sse",)
