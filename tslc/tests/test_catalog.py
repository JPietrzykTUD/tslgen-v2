"""Catalog promotion: type groups, extensions, type spellings."""

from __future__ import annotations

import pytest

from tslc.catalog.machine_profiles import MachineProfile
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


def _flat_flags(impl):
    assert len(impl.requirements) == 1 and impl.requirements[0].type_group is None
    return impl.requirements[0].flags


def test_requirements_promoted_flat(catalog: Catalog) -> None:
    add = catalog.primitive("add")
    by_path = {(i.extension, i.type_group): i for i in add.implementations}
    assert _flat_flags(by_path[("avx2", "?i?")]) == frozenset({"avx", "avx2"})
    assert _flat_flags(by_path[("avx2", "f?")]) == frozenset({"avx"})
    assert _flat_flags(by_path[("sse", "?i?")]) == frozenset({"sse2"})
    assert _flat_flags(by_path[("scalar", "arith")]) == frozenset()


def test_nested_requires_promoted_per_type_group(catalog: Catalog) -> None:
    # avx512 add's ?i? body has a nested `requires:` map: idqword needs avx512f,
    # bword needs avx512f + avx512bw.
    add = catalog.primitive("add")
    nested = next(
        i for i in add.implementations if i.extension == "avx512" and i.type_group == "?i?"
    )
    clauses = {c.type_group: c.flags for c in nested.requirements}
    assert clauses["idqword"] == frozenset({"avx512f"})
    assert clauses["bword"] == frozenset({"avx512f", "avx512bw"})


def test_extension_inheritance_and_lscpu(catalog: Catalog) -> None:
    avx2_vl = catalog.extensions["avx2_vl"]
    assert avx2_vl.inherits == "avx2"
    assert avx2_vl.isa_name == "avx2"  # emitted as avx2; _vl is internal only
    assert {"avx512vl", "avx512f"} <= avx2_vl.lscpu_flags
    # compose metadata is inherited (flattened) from avx2.
    assert avx2_vl.compose_prefix["cpp"] == "_mm256_"
    assert avx2_vl.family == "x86"
    assert catalog.extension_chain("avx2_vl") == ("avx2_vl", "avx2")


def test_machine_profiles_loaded(machine_profiles) -> None:
    assert machine_profiles["scalar"].features == frozenset()
    assert "avx2" in machine_profiles["avx2"].features
    assert "avx2" not in machine_profiles["avx"].features
    assert "avx512f" in machine_profiles["skylake"].features


def test_catalog_mappings_are_read_only(catalog: Catalog) -> None:
    add = catalog.primitive("add")
    assert add is not None
    avx2 = catalog.extensions["avx2"]
    avx512 = catalog.extensions["avx512"]

    with pytest.raises(TypeError):
        catalog.type_groups["new"] = ("si32",)  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.extensions["new"] = avx2  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.type_spellings["cpp"]["s32"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.translations["cpp"]["emit_return"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        add.attributes["mask"] = "zero"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx2.compose_prefix["cpp"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx2.compose_suffix_by_type["si32"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx512.mask_policy.cpp_by_lanes[16] = "bad"  # type: ignore[index]


def test_machine_profile_mappings_are_read_only(machine_profiles) -> None:
    alternate_feature = "avx512_vpclmulqdq"
    with pytest.raises(TypeError):
        machine_profiles["new"] = MachineProfile(  # type: ignore[index]
            "new", "x86", frozenset(), {}
        )
    with pytest.raises(TypeError):
        machine_profiles["skylake"].alternatives[alternate_feature] = "bad"  # type: ignore[index]
