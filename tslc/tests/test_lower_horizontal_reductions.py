"""Masked and fixed-width horizontal reduction regressions."""

from __future__ import annotations

from _select_lower_extension_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "ui64"),
        ("avx2", "avx2", "ui16"),
        ("skylake", "avx2_vl", "ui32"),
        ("neon", "neon", "f32"),
        ("wasm32-simd128", "wasm128", "ui8"),
    ],
)
def test_masked_bitwise_horizontal_reductions_compose_masked_vectors(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::to_vector<Vec>(mask)" in cpp.body_text
    assert f"::tsl::{primitive}<Vec>" in cpp.body_text
    assert "to_array" not in cpp.body_text
    if primitive == "hand":
        assert "::tsl::to_integral<Vec>(mask)" in cpp.body_text
        assert "::tsl::inv<Vec>(mask_vector)" in cpp.body_text
        assert "::tsl::binary_or<Vec>" in cpp.body_text
    else:
        assert "::tsl::binary_and<Vec>(mask_vector, vec)" in cpp.body_text


@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_sve_masked_bitwise_horizontal_uses_semantic_empty_test(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "hand",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.signature == "s:=(m,v)"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "mask_population_count" in lowered.body_text
    assert "svptest_any" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "si64"),
        ("avx2", "avx2", "ui64"),
        ("skylake", "avx2_vl", "si64"),
        ("neon", "neon", "ui8"),
        ("wasm32-simd128", "wasm128", "ui16"),
    ],
)
def test_masked_hadd_composes_masked_vector_with_unmasked_reduction(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "hadd", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::to_vector<Vec>(mask)" in cpp.body_text
    assert "::tsl::binary_and<Vec>(mask_vector, vec)" in cpp.body_text
    assert "::tsl::hadd<Vec>" in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "sum_intrinsic"),
    [
        ("sse2", "sse", "si8", "_mm_sad_epu8"),
        ("sse2", "sse", "ui16", "_mm_madd_epi16"),
        ("skylake", "avx512", "ui8", "_mm512_sad_epu8"),
        ("skylake", "avx512", "si16", "_mm512_madd_epi16"),
    ],
)
def test_x86_small_integer_hadd_reduces_in_register(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    sum_intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "hadd", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert sum_intrinsic in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "si16", "si32", "ui64", "f32", "f64"])
def test_avx2_hadd_composes_from_half_vector_primitives(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "hadd", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text.count("::tsl::extract<Vec") == 2
    assert "::tsl::add<tsl::simd<" in cpp.body_text
    assert "::tsl::hadd<tsl::simd<" in cpp.body_text
    assert "_mm256_" not in cpp.body_text


def test_knl_small_integer_hadd_composes_from_sse_quarters(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["knl"], "hadd", ("ui8",))
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text.count("::tsl::extract<Vec") == 4
    assert "::tsl::add<tsl::simd<uint8_t, tsl::sse>>" in cpp.body_text
    assert "::tsl::hadd<tsl::simd<uint8_t, tsl::sse>>" in cpp.body_text
    assert "_mm512_" not in cpp.body_text
