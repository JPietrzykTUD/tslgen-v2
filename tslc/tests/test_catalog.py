"""Catalog promotion: type groups, extensions, type spellings."""

from __future__ import annotations

from tslc.catalog.model import Catalog


def test_type_groups_expand(catalog: Catalog) -> None:
    assert catalog.type_groups["?i?"] == (
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    )
    assert catalog.type_groups["f?"] == ("f32", "f64")
    assert catalog.type_group_contains("?i?", "ui32")
    assert not catalog.type_group_contains("f?", "si8")


def test_avx2_and_avx2_vl_are_distinct_extensions(catalog: Catalog) -> None:
    avx2 = catalog.extensions["avx2"]
    avx2_vl = catalog.extensions["avx2_vl"]
    # Different extension identities even though they share the ISA spelling.
    assert avx2.name == "avx2"
    assert avx2_vl.name == "avx2_vl"
    assert avx2.isa_name == "avx2"
    assert avx2_vl.isa_name == "avx2"
    # The real avx2 metadata must not be clobbered by avx2_vl.
    assert avx2.compose_prefix["cpp"] == "_mm256_"
    assert avx2.compose_suffix_by_type["si32"] == "epi32"
    assert avx2.register_types["?i?"]["cpp"] == "__m256i"


def test_scalar_uses_base_type_register_policy(catalog: Catalog) -> None:
    scalar = catalog.extensions["scalar"]
    assert scalar.register_type_policy == "base_type"
    assert scalar.intrinsic_style == "scalar"


def test_type_spellings_normalized(catalog: Catalog) -> None:
    assert catalog.type_spellings["cpp"]["s32"] == "int32_t"
    assert catalog.type_spellings["cpp"]["f32"] == "float"
    assert catalog.type_spellings["rust"]["s32"] == "i32"
    assert catalog.type_spellings["rust"]["u64"] == "u64"
