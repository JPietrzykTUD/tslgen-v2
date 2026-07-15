"""Horizontal min/max, population count, and leading-zero regressions."""

from __future__ import annotations

from _select_lower_extension_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "ui8", "_mm_srli_si128"),
        ("sse2", "sse", "si64", "extract_value"),
        ("avx2", "avx2", "ui16", "tsl::sse"),
        ("skylake", "avx512", "ui8", "tsl::avx2"),
        ("knl", "avx512", "si16", "tsl::sse"),
        ("skylake", "avx2_vl", "si8", "_mm256_reduce_"),
    ],
)
def test_x86_integer_horizontal_minmax_stays_in_registers(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert expected_fragment in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_intrinsic"),
    [
        ("skylake", "avx2_vl", "ui8", "_mm256_mask_reduce_"),
        ("skylake", "sse_vl", "si8", "_mm_mask_reduce_"),
    ],
)
def test_vl_masked_small_integer_horizontal_minmax_uses_direct_reduction(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    type_tag: str,
    expected_intrinsic: str,
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
    assert expected_intrinsic in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("extension", "type_tag", "intrinsic"),
    [
        ("avx512", "ui8", "_mm512_popcnt_epi8"),
        ("avx2_vl", "ui8", "_mm256_popcnt_epi8"),
        ("sse_vl", "ui8", "_mm_popcnt_epi8"),
        ("avx512", "ui64", "_mm512_popcnt_epi64"),
    ],
)
def test_x86_popcnt_prefers_native_vpopcnt_when_available(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["icelake_rockerlake"],
            "popcnt",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == f"return {intrinsic}(data);"
    assert rust is not None
    assert rust.body_text == (
        f"unsafe {{ return core::arch::x86_64::{intrinsic}(data); }}"
    )


@pytest.mark.parametrize(
    ("extension", "type_tag", "lane_width"),
    [
        ("clang_v128", "si8", 8),
        ("clang_v256", "ui32", 32),
        ("clang_v512", "si64", 64),
    ],
)
def test_clang_lzc_uses_elementwise_builtin_with_defined_zero_result(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    type_tag: str,
    lane_width: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], "lzc", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "to_array" not in cpp.body_text
    assert "__builtin_elementwise_clzg" in cpp.body_text
    assert f">({lane_width})" in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "ui8"),
        ("sse2", "sse", "si64"),
        ("avx2", "avx2", "si16"),
        ("avx2", "avx2", "ui32"),
    ],
)
def test_x86_lzc_without_avx512cd_uses_register_bit_propagation(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "lzc", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "shift_right" in lowered.body_text
        assert "srli" not in lowered.body_text
        assert "binary_andnot" in lowered.body_text
        assert "popcnt" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "evidence"),
    [
        ("avx", "avx2", "ui8", "extract"),
        ("avx", "avx2", "f64", "extract"),
        ("kml", "avx512", "si8", "shift_right"),
        ("kml", "avx512", "ui16", "shift_right"),
    ],
)
def test_x86_lzc_handles_avx1_and_avx512f_without_bw_in_registers(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "lzc", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert evidence in lowered.body_text
        if profile == "avx":
            assert "_mm256_" not in lowered.body_text
            assert lowered.body_text.count("insert") == 2
        else:
            assert "_mm512_" not in lowered.body_text
            assert "binary_or" in lowered.body_text
            assert "reinterpret" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_avx512_bitalg_lzc_keeps_preferred_composed_path(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["icelake_rockerlake"],
            "lzc",
            ("ui8",),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert "avx512_bitalg" in slot.required_features
    assert cpp is not None
    assert "::tsl::popcnt<" in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("scalar", "clang_v128", "f32"),
        ("sse2", "sse", "f64"),
        ("avx2", "avx2", "f32"),
        ("skylake", "avx512", "f64"),
        ("skylake", "avx2_vl", "f32"),
        ("skylake", "sse_vl", "f64"),
        ("sve", "sve", "f32"),
        ("wasm32-simd128", "wasm128", "f32"),
    ],
)
def test_float_lzc_composes_native_integer_lzc_and_numeric_cast(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "lzc", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "::tsl::lzc<" in cpp.body_text
    assert "::tsl::cast<" in cpp.body_text


@pytest.mark.parametrize("type_tag", ["si64", "ui64"])
def test_neon_lzc_64_composes_native_word_intrinsics(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "lzc", (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "vclzq_u32" in lowered.body_text
        assert "vmovn_u64" in lowered.body_text
        assert "vbsl_u32" in lowered.body_text
        assert "vmovl_u32" in lowered.body_text


@pytest.mark.parametrize(("type_tag", "lanes"), [("ui8", 16), ("si64", 2)])
def test_wasm_integer_lzc_unrolls_semantic_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
    lanes: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "lzc",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "wasm128"
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == lanes
        assert lowered.body_text.count("insert_value") == lanes
        assert "extract_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_neon_lzc_float_composes_bit_lzc_and_numeric_conversion(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "lzc", (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        for function_name in ("reinterpret", "lzc", "cast"):
            assert (
                f"{function_name}<" in lowered.body_text
                or f"{function_name}::<" in lowered.body_text
            )
