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
    # Distinct identities (keyed by block name), even though they share an ISA name.
    assert avx2.name == "avx2"
    assert avx2_vl.name == "avx2_vl"
    # The real avx2 compose metadata must not be clobbered by avx2_vl.
    assert avx2.compose_prefix["cpp"] == "_mm256_"
    assert avx2.compose_suffix_by_type["si32"] == "epi32"


def test_scalar_extension_has_no_intrinsic_compose(catalog: Catalog) -> None:
    scalar = catalog.extensions["scalar"]
    assert scalar.family == "scalar"
    assert scalar.compose_prefix == {}  # scalar has no intrinsic prefix


def test_type_spellings_normalized(catalog: Catalog) -> None:
    assert catalog.type_spellings["cpp"]["s32"] == "int32_t"
    assert catalog.type_spellings["cpp"]["f32"] == "float"
    assert catalog.type_spellings["rust"]["s32"] == "i32"
    assert catalog.type_spellings["rust"]["u64"] == "u64"


def test_bracketed_type_group_membership(catalog: Catalog) -> None:
    # hadd uses explicit type-list selectors like [si32, ui32].
    assert catalog.type_group_contains("[si32, ui32]", "si32")
    assert not catalog.type_group_contains("[si32, ui32]", "f32")
    assert catalog.type_group_specificity("[si32, ui32]") == 2
    assert catalog.type_group_specificity("f64") == 1  # bare concrete tag
    assert catalog.type_group_specificity("arith") == 10


def test_required_flags_promoted(catalog: Catalog) -> None:
    add = catalog.primitive("add")
    by_path = {(i.extension, i.type_group): i for i in add.implementations}
    assert by_path[("avx2", "?i?")].required_flags == frozenset({"avx", "avx2"})
    assert by_path[("avx2", "f?")].required_flags == frozenset({"avx"})
    assert by_path[("sse", "?i?")].required_flags == frozenset({"sse2"})
    assert by_path[("scalar", "arith")].required_flags == frozenset()


def test_nested_requires_marked_unavailable(catalog: Catalog) -> None:
    # avx512 add's ?i? body uses a nested per-type `requires:` map we don't
    # evaluate yet; it must be marked unavailable (None), not unconditionally usable.
    add = catalog.primitive("add")
    nested = [
        i for i in add.implementations if i.extension == "avx512" and i.type_group == "?i?"
    ]
    assert nested and all(i.required_flags is None for i in nested)


def test_machine_profiles_loaded(machine_profiles) -> None:
    assert machine_profiles["scalar"].features == frozenset()
    assert "avx2" in machine_profiles["avx2"].features
    assert "avx2" not in machine_profiles["avx"].features
    assert "avx512f" in machine_profiles["skylake"].features
