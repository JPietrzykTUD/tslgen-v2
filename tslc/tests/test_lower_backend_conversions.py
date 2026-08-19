"""Backend conversion and narrowing lowering regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize(
    ("profile", "source_type", "target_type", "extension", "intrinsic"),
    [
        ("sse2", "f32", "si32", "sse", "_mm_cvttps_epi32"),
        ("sse2", "f32", "ui32", "sse", "_mm_cvttps_epi32"),
        ("sse2", "f64", "si32", "sse", "_mm_cvttpd_epi32"),
        ("sse2", "f64", "ui32", "sse", "_mm_cvttpd_epi32"),
        ("avx2", "f32", "si32", "avx2", "_mm256_cvttps_epi32"),
        ("avx2", "f32", "ui32", "avx2", "_mm256_cvttps_epi32"),
        ("avx2", "f64", "si32", "avx2", "_mm256_cvttpd_epi32"),
        ("avx2", "f64", "ui32", "avx2", "_mm256_cvttpd_epi32"),
    ],
)
def test_x86_float_to_i32_cast_uses_register_only_truncation(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    source_type: str,
    target_type: str,
    extension: str,
    intrinsic: str,
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(
            catalog, machine_profiles[profile], "cast", (source_type,)
        )
        .selected
        if s.extension.name == extension
        and s.type_tag == source_type
        and s.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "round_" not in lowered.body_text
        if profile == "avx2" and source_type == "f64" and target_type == "ui32":
            expected_half = (
                "tsl::simd<uint32_t, tsl::sse>"
                if backend_id == "cpp"
                else "Simd<u32, Sse>"
            )
            expected_extract = "extract<" if backend_id == "cpp" else "extract::<"
            assert expected_extract in lowered.body_text
            assert expected_half in lowered.body_text

        if target_type == "ui32":
            assert "2147483648" in lowered.body_text
            assert "xor" in lowered.body_text


def test_clang_same_width_cast_uses_builtin_convertvector(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "cast",
            ("f32",),
            backend_id="cpp",
        )
        .selected
        if selected.extension.name == "clang_v256"
        and selected.to_target == "si32"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "__builtin_convertvector(data," in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    [("si8", "f64"), ("f64", "si32")],
)
def test_clang_width_changing_cast_unrolls_shared_lanes(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", (source_type,))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.to_target == target_type
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "result[0]" in cpp.body_text
    assert "data[0]" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "for " not in cpp.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "expected"),
    [
        ("si8", "ui8", "return data;"),
        ("f32", "si32", "i32x4_trunc_sat_f32x4"),
        ("f32", "f64", "f64x2_promote_low_f32x4"),
        ("si32", "f32", "f32x4_convert_i32x4"),
        ("ui32", "f64", "f64x2_convert_low_u32x4"),
        ("f64", "ui32", "u32x4_trunc_sat_f64x2_zero"),
        ("f64", "f32", "f32x4_demote_f64x2_zero"),
    ],
)
def test_wasm_cast_prefers_native_width_preserving_conversions(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "cast",
            (source_type,),
        )
        .selected
        if selected.extension.name == "wasm128"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization
        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "expected"),
    [
        ("si8", "si16", "i16x8_extend_low_i8x16"),
        ("ui8", "ui32", "convert_up"),
        ("si8", "si64", "convert_up"),
        ("ui16", "ui32", "u32x4_extend_low_u16x8"),
        ("si16", "ui64", "convert_up"),
        ("si32", "si64", "i64x2_extend_low_i32x4"),
        ("f32", "f64", "f64x2_promote_low_f32x4"),
    ],
)
def test_wasm_convert_up_uses_native_widening_steps(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == "wasm128"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "narrow_intrinsic", "placement"),
    [
        ("si32", "si8", "cvtsepi32_epi8", "insert"),
        ("ui32", "ui8", "cvtusepi32_epi8", "insert"),
        ("si64", "si16", "cvtsepi64_epi16", "insert"),
        ("ui64", "ui16", "cvtusepi64_epi16", "insert"),
        ("si64", "si8", "cvtsepi64_epi8", "maskz_set1_epi64"),
        ("ui64", "ui8", "cvtusepi64_epi8", "maskz_set1_epi64"),
    ],
)
def test_avx512_convert_down_places_native_narrow_result_without_arrays(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    narrow_intrinsic: str,
    placement: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["knl"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert narrow_intrinsic in lowered.body_text
        assert placement in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "source_type", "target_type", "expected"),
    [
        ("sse2", "sse", "ui16", "ui8", "min"),
        ("avx", "sse", "ui32", "ui16", "min"),
        ("avx2", "avx2", "ui16", "ui8", "min"),
        ("avx2", "avx2", "ui32", "ui16", "min"),
    ],
)
def test_x86_unsigned_convert_down_clamps_before_signed_input_pack(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "set1" in lowered.body_text
        if source_type == "ui16":
            assert "min" in lowered.body_text
            assert "subs_epu16" not in lowered.body_text
            assert "set1_epi16" not in lowered.body_text
        else:
            assert "_min_epu32" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "source_type", "target_type", "expected"),
    [
        ("sse2", "sse", "si16", "ui8", "_mm_packus_epi16"),
        ("sse2", "sse", "ui16", "si8", "min"),
        ("avx", "sse", "si32", "ui16", "_mm_packus_epi32"),
        ("avx", "sse", "ui32", "si16", "min"),
        ("avx2", "avx2", "si16", "ui8", "_mm_packus_epi16"),
        ("avx2", "avx2", "ui16", "si8", "min"),
        ("avx2", "avx2", "si32", "ui16", "_mm_packus_epi32"),
        ("avx2", "avx2", "ui32", "si16", "min"),
    ],
)
def test_x86_cross_signed_convert_down_uses_register_saturating_packs(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        if source_type == "ui16":
            assert "set1" in lowered.body_text
            assert "min" in lowered.body_text
            assert "subs_epu16" not in lowered.body_text
            assert "set1_epi16" not in lowered.body_text
        elif source_type == "ui32":
            assert "set1" in lowered.body_text
            assert "_min_epu32" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    [
        ("si32", "ui16"),
        ("ui32", "si16"),
    ],
)
def test_sse_cross_signed_dword_narrowing_composes_range_clamp(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sse2"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "sse" and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        for primitive in ("equal", "shift_right", "select", "set1"):
            assert primitive in lowered.body_text
        if source_type == "si32":
            for primitive in ("greater_than", "to_vector", "binary_andnot", "sub", "binary_xor"):
                assert primitive in lowered.body_text
        assert "_mm_packs_epi32" in lowered.body_text
        for duplicated in (
            "_mm_cmpgt_epi32",
            "_mm_cmpeq_epi32",
            "_mm_srli_epi32",
            "_mm_and_si128",
            "_mm_andnot_si128",
            "_mm_or_si128",
            "_mm_sub_epi32",
            "_mm_xor_si128",
            "_mm_set1_epi32",
            "_mm_set1_epi16",
        ):
            assert duplicated not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "source_type", "target_type", "expected"),
    [
        ("sse2", "sse", "ui32", "ui16", "binary_xor"),
        ("sse2", "sse", "ui32", "si16", "shift_right"),
        ("sse2", "sse", "si32", "ui8", "convert_down"),
        ("sse2", "sse", "si64", "ui16", "convert_down"),
        ("sse2", "sse", "ui64", "si32", "insert_value"),
        ("sse2", "sse", "f64", "f32", "_mm_cvtpd_ps"),
        ("avx", "sse", "ui32", "ui16", "min"),
        ("avx", "sse", "si32", "ui16", "_mm_packus_epi32"),
        ("avx2", "avx2", "ui32", "si8", "convert_down"),
        ("avx2", "avx2", "si64", "ui8", "convert_down"),
        ("avx2", "avx2", "ui64", "si32", "insert_value"),
    ],
)
def test_x86_convert_down_complete_integer_matrix_stays_in_registers(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("source_type", ["si64", "ui64"])
@pytest.mark.parametrize("target_type", ["si32", "ui32"])
def test_sse_qword_to_dword_convert_down_is_pure_primitive_composition(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sse2"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "sse" and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert "_mm" not in lowered.body_text


@pytest.mark.parametrize("source_type", ["si64", "ui64"])
@pytest.mark.parametrize("target_type", ["si32", "ui32"])
def test_avx2_qword_to_dword_convert_down_is_pure_primitive_composition(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "avx2" and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert "_mm" not in lowered.body_text


def test_sse_f64_to_f32_convert_down_composes_lane_placement(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sse2"],
            "convert_down",
            ("f64",),
        )
        .selected
        if selected.extension.name == "sse" and selected.to_target == "f32"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "_mm_cvtpd_ps" in lowered.body_text
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert "_mm_movelh_ps" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "source_type", "target_type", "expected"),
    [
        ("skylake", "si16", "ui8", "max"),
        ("skylake", "ui16", "ui8", "min"),
        ("skylake", "ui16", "si8", "_mm512_cvtsepi16_epi8"),
        ("knl", "si16", "ui8", "convert_down"),
        ("knl", "ui16", "si8", "convert_down"),
        ("knl", "si32", "ui16", "max"),
        ("knl", "ui32", "ui16", "min"),
        ("knl", "ui32", "si16", "_mm512_cvtsepi32_epi16"),
        ("knl", "si64", "ui32", "max"),
        ("knl", "ui64", "ui32", "min"),
        ("knl", "ui64", "si32", "_mm512_cvtsepi64_epi32"),
    ],
)
def test_avx512_cross_signed_and_unsigned_narrowing_stays_in_registers(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "expected"),
    [
        ("si16", "ui8", "max"),
        ("ui16", "si8", "min"),
        ("si32", "si16", "i16x8_narrow_i32x4"),
        ("si32", "ui8", "convert_down"),
        ("ui64", "si32", "saturating_cast"),
        ("si64", "ui8", "convert_down"),
        ("f64", "f32", "f32x4_demote_f64x2_zero"),
    ],
)
def test_wasm_convert_down_uses_register_only_saturating_steps(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "wasm128"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "full_intrinsic"),
    [
        ("si16", "si8", "_mm512_cvtsepi16_epi8"),
        ("ui16", "ui8", "_mm512_cvtusepi16_epi8"),
        ("f64", "f32", "_mm512_cvtpd_ps"),
    ],
)
def test_avx512f_convert_down_composes_fixed_width_chunks_without_bw_or_dq(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    full_intrinsic: str,
) -> None:
    for profile in ("knl", "skylake"):
        slot = next(
            selected
            for selected in Selector()
            .select_profile(
                catalog,
                machine_profiles[profile],
                "convert_down",
                (source_type,),
            )
            .selected
            if selected.extension.name == "avx512"
            and selected.to_target == target_type
        )

        for backend_id in ("cpp", "rust"):
            lowered = Lowerer().lower(
                slot, catalog, create_backend_dialect(catalog, backend_id)
            ).specialization

            assert lowered is not None
            assert "to_array" not in lowered.body_text
            assert "from_array" not in lowered.body_text
            if profile == "knl":
                assert "convert_down" in lowered.body_text
                assert "extract" in lowered.body_text
                assert "insert" in lowered.body_text
                assert full_intrinsic not in lowered.body_text
            else:
                assert full_intrinsic in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "avx512f_evidence"),
    [
        ("si8", "si16", "load_convert_up"),
        ("ui8", "ui16", "load_convert_up"),
        ("si8", "si32", "_mm512_cvtepi8_epi32"),
        ("ui8", "ui32", "_mm512_cvtepu8_epi32"),
        ("si8", "si64", "_mm512_cvtepi8_epi64"),
        ("ui8", "ui64", "_mm512_cvtepu8_epi64"),
        ("si16", "si32", "_mm512_cvtepi16_epi32"),
        ("ui16", "ui64", "_mm512_cvtepu16_epi64"),
    ],
)
def test_avx512f_load_convert_up_avoids_bw_gated_array_fallback(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    avx512f_evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["knl"],
            "load_convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert avx512f_evidence in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("profile", ["knl", "kml"])
@pytest.mark.parametrize("type_tag", ["si8", "ui8", "si16", "ui16"])
def test_avx512f_to_array_materializes_small_integer_registers(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "to_array",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "avx512"
    )

    assert slot.required_features == frozenset({"avx512f"})
    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "store" in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "intrinsic"),
    [
        ("si8", "si16", "_mm512_cvtepi8_epi16"),
        ("ui8", "ui16", "_mm512_cvtepu8_epi16"),
    ],
)
def test_avx512bw_load_convert_up_keeps_single_instruction_leaf(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            "load_convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.to_target == target_type
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert intrinsic in cpp.body_text
    assert "load_convert_up" not in cpp.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "load_intrinsic", "widen_intrinsic"),
    [
        ("si8", "si16", "vld1_s8", "vmovl_s8"),
        ("ui8", "ui16", "vld1_u8", "vmovl_u8"),
        ("si16", "si32", "vld1_s16", "vmovl_s16"),
        ("ui16", "ui32", "vld1_u16", "vmovl_u16"),
        ("si32", "si64", "vld1_s32", "vmovl_s32"),
        ("ui32", "ui64", "vld1_u32", "vmovl_u32"),
        ("f32", "f64", "vld1_f32", "vcvt_f64_f32"),
    ],
)
def test_neon_load_convert_up_uses_exact_64_bit_load_and_widen(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    load_intrinsic: str,
    widen_intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["neon"],
            "load_convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == "neon"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert load_intrinsic in lowered.body_text
        assert widen_intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "expected"),
    [
        ("si16", "ui8", "vqmovun_s16"),
        ("ui16", "si8", "min"),
        ("si32", "si16", "vqmovn_s32"),
        ("si32", "ui8", "convert_down"),
        ("ui64", "si32", "min"),
        ("si64", "ui8", "convert_down"),
        ("f64", "f32", "vcvt_f32_f64"),
    ],
)
def test_neon_convert_down_uses_native_saturating_steps(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    expected: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["neon"],
            "convert_down",
            (source_type,),
        )
        .selected
        if selected.extension.name == "neon"
        and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert expected in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
