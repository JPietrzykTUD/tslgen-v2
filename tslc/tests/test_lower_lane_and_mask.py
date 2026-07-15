"""Lane construction, extraction, and mask-conversion regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


def test_clang_set_uses_native_vector_initializer(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "set", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::register_type{" in cpp.body_text
    assert "values[7]" in cpp.body_text
    assert "values[0]" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "::tsl::load" not in cpp.body_text

@pytest.mark.parametrize(
    ("profile", "extension", "lanes"),
    [
        ("neon", "neon", 4),
        ("wasm32-simd128", "wasm128", 4),
    ],
)
def test_fixed_width_set_unrolls_insert_value_calls(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    lanes: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "set", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("insert_value") == lanes
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "values[3]" in lowered.body_text
        assert "values[0]" in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert "for " not in lowered.body_text

def test_clang_sequence_uses_native_vector_initializer(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "sequence", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::register_type{" in cpp.body_text
    assert "static_cast<uint32_t>(0)" in cpp.body_text
    assert "static_cast<uint32_t>(7)" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "for (" not in cpp.body_text

@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("neon", "neon"),
        ("wasm32-simd128", "wasm128"),
    ],
)
def test_fixed_width_sequence_unrolls_insert_value_calls(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "sequence", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("insert_value") == 3
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text

def test_wasm_extract_value_uses_immediate_lane_intrinsic(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "extract_value",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "wasm128"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "i32x4_extract_lane" in lowered.body_text
        assert "Index" in lowered.body_text
        assert "::<Index>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        if backend_id == "rust":
            assert "::<0>" in lowered.body_text
            assert "::<3>" in lowered.body_text
        else:
            assert "wasm_i32x4_extract_lane(a, 0)" in lowered.body_text
            assert "wasm_i32x4_extract_lane(a, 3)" in lowered.body_text

@pytest.mark.parametrize(
    ("profile", "type_tag", "needle"),
    [
        ("sse", "f32", "cvtss_f32"),
        ("sse2", "ui8", "cvtsi128_si64"),
        ("sse2", "si16", "cvtsi128_si64"),
        ("sse2", "ui32", "cvtsi128_si64"),
        ("sse2", "si64", "cvtsi128_si64"),
        ("sse2", "f64", "cvtsd_f64"),
    ],
)
def test_sse_extract_value_stays_in_register(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    type_tag: str,
    needle: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == "sse"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert needle in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "store" not in lowered.body_text

@pytest.mark.parametrize(
    ("profile", "extension", "chunk_count"),
    [
        ("avx", "avx2", 2),
        ("knl", "avx512", 4),
    ],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16", "f32", "f64"])
def test_wide_x86_extract_value_uses_register_chunks(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    chunk_count: int,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == chunk_count
        assert "_mm256_extract" not in lowered.body_text
        assert "_mm512_extract" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "store" not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["ui8", "ui16", "f32", "f64"])
def test_wasm_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "to_mask",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "wasm128"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "v128_load" not in lowered.body_text
        assert "and_values" not in lowered.body_text
        assert "replace_lane" in lowered.body_text
        if type_tag == "ui8":
            assert "convert_down" in lowered.body_text
            assert "binary_or" in lowered.body_text
            assert "narrow_i16x8" not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["ui8", "ui16", "ui32", "ui64", "f32", "f64"])
def test_neon_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "neon"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert "vsetq_lane" in lowered.body_text

@pytest.mark.parametrize(
    ("type_tag", "evidence"),
    [
        ("ui8", "vaddv_u8"),
        ("ui16", "hadd"),
        ("ui32", "hadd"),
        ("ui64", "extract_value"),
        ("f32", "to_integral"),
        ("f64", "to_integral"),
    ],
)
def test_neon_to_integral_uses_native_mask_pack(
    catalog: Catalog, machine_profiles, type_tag: str, evidence: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == "neon"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "for " not in lowered.body_text
        assert evidence in lowered.body_text
        if type_tag == "ui64":
            assert "vgetq_lane" not in lowered.body_text

@pytest.mark.parametrize(
    ("type_tag", "intrinsic"),
    [
        ("ui16", "_mm256_set_epi16"),
        ("ui32", "_mm256_set_epi32"),
        ("ui64", "_mm256_set_epi64x"),
    ],
)
def test_avx2_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str, intrinsic: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert intrinsic in lowered.body_text
        if type_tag == "f64":
            assert "reinterpret" in lowered.body_text
            assert "castsi128_pd" not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["ui8", "ui16"])
def test_avx_to_integral_uses_sse_half_width_composition(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx"], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == 2
        assert "_mm256_extract" not in lowered.body_text
        assert lowered.body_text.count("to_integral") == 2
        assert "_mm_movemask_epi8" not in lowered.body_text
        assert "for " not in lowered.body_text

@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "movemask"),
    [
        ("avx2", "avx2", "ui32", "movemask_ps"),
        ("avx2", "avx2", "ui64", "movemask_pd"),
        ("sse2", "sse", "ui32", "movemask_ps"),
        ("sse2", "sse", "ui64", "movemask_pd"),
    ],
)
def test_x86_integer_to_integral_uses_semantic_reinterpret(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    movemask: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "reinterpret" in lowered.body_text
        assert movemask in lowered.body_text
        assert "castsi" not in lowered.body_text

@pytest.mark.parametrize(
    ("profile", "extension", "packs"),
    [
        ("avx2", "avx2", "_mm256_packs_epi16"),
        ("sse2", "sse", "_mm_packs_epi16"),
    ],
)
def test_x86_word_to_integral_uses_convert_down_and_byte_path(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    packs: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_integral", ("ui16",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "convert_down" in lowered.body_text
        assert "to_integral" in lowered.body_text
        assert packs not in lowered.body_text
