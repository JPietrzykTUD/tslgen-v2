"""Scalar, immediate, and vector shift lowering regressions."""

from __future__ import annotations

from _select_lower_extension_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
    _assert_x86_shift_register_path,
)


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "si8", "_mm_slli_epi16"),
        ("avx", "avx2", "si32", "::tsl::extract<Vec"),
        ("avx2", "avx2", "ui8", "::tsl::extract<Vec"),
        ("knl", "avx512", "ui8", "::tsl::extract<Vec"),
        ("skylake", "avx512", "ui8", "_mm512_slli_epi16"),
        ("avx2", "avx2", "f32", "::tsl::reinterpret<Vec"),
    ],
)
def test_x86_immediate_shift_left_avoids_array_fallback(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_left", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,sImm)"
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "si8", "_mm_srli_epi16"),
        ("sse2", "sse", "si64", "_mm_srai_epi32"),
        ("avx", "avx2", "si32", "::tsl::extract<Vec"),
        ("avx2", "avx2", "si64", "_mm256_srai_epi32"),
        ("knl", "avx512", "si16", "::tsl::extract<Vec"),
        ("skylake", "avx512", "ui8", "_mm512_srli_epi16"),
        ("avx2", "avx2", "f32", "::tsl::reinterpret<Vec"),
    ],
)
def test_x86_immediate_shift_right_avoids_array_fallback(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_right", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,sImm)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "si8", "_mm_sll_epi16"),
        ("sse2", "sse", "ui32", "_mm_sll_epi32"),
        ("avx", "avx2", "si64", "::tsl::extract<Vec"),
        ("avx2", "avx2", "ui16", "_mm256_sll_epi16"),
        ("knl", "avx512", "ui16", "::tsl::extract<Vec"),
        ("skylake", "avx512", "ui8", "_mm512_sll_epi16"),
        ("avx2", "avx2", "f64", "::tsl::reinterpret<Vec"),
    ],
)
def test_x86_scalar_shift_left_avoids_array_fallback(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_left", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,s)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "si8", "_mm_srl_epi16"),
        ("sse2", "sse", "si64", "_mm_srai_epi32"),
        ("avx", "avx2", "ui32", "::tsl::extract<Vec"),
        ("avx2", "avx2", "si64", "_mm256_srai_epi32"),
        ("knl", "avx512", "si8", "::tsl::extract<Vec"),
        ("skylake", "avx512", "ui8", "_mm512_srl_epi16"),
        ("avx2", "avx2", "f64", "::tsl::reinterpret<Vec"),
    ],
)
def test_x86_scalar_shift_right_avoids_array_fallback(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_right", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,s)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize(
    ("primitive", "profile", "extension", "signature", "type_tag", "forbidden"),
    [
        ("shift_left", "sse2", "sse", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_left", "sse2", "sse", "v:=(v,s)", "si8", "_mm_cvtsi32_si128"),
        ("shift_left", "avx2", "avx2", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_left", "skylake", "avx512", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_left", "skylake", "avx512", "v:=(v,s)", "si8", "_mm_cvtsi32_si128"),
        ("shift_right", "sse2", "sse", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_right", "sse2", "sse", "v:=(v,s)", "si16", "_mm_cvtsi32_si128"),
        ("shift_right", "sse2", "sse", "v:=(v,s)", "si64", "_mm_cvtsi32_si128"),
        ("shift_right", "sse2", "sse", "v:=(v,s)", "si8", "_mm_cvtsi32_si128"),
        ("shift_right", "avx2", "avx2", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_right", "avx2", "avx2", "v:=(v,s)", "si16", "_mm_cvtsi32_si128"),
        ("shift_right", "avx2", "avx2", "v:=(v,s)", "si64", "_mm_cvtsi32_si128"),
        ("shift_right", "avx2", "avx2", "v:=(v,s)", "si8", "_mm_cvtsi32_si128"),
        ("shift_right", "skylake", "avx512", "v:=(v,s)", "ui32", "_mm_cvtsi32_si128"),
        ("shift_right", "skylake", "avx512", "v:=(v,s)", "si16", "_mm_cvtsi32_si128"),
        ("shift_right", "skylake", "avx512", "v:=(v,s)", "si64", "_mm_cvtsi32_si128"),
        ("shift_right", "skylake", "avx512", "v:=(v,s)", "si8", "_mm_cvtsi32_si128"),
        ("shift_right", "sse2", "sse", "v:=(v,sImm)", "si64", "_mm_cvtsi32_si128"),
        ("shift_right", "avx2", "avx2", "v:=(v,sImm)", "si64", "_mm_cvtsi32_si128"),
        ("shift_left", "neon", "neon", "v:=(v,sImm)", "ui32", "vdupq_n"),
        ("shift_left", "neon", "neon", "v:=(v,s)", "ui32", "vdupq_n"),
    ],
)
def test_scalar_shift_count_uses_semantic_broadcast(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    signature: str,
    type_tag: str,
    forbidden: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == signature
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "set1" in lowered.body_text
        assert forbidden not in lowered.body_text


@pytest.mark.parametrize("signature", ["v:=(v,sImm)", "v:=(v,s)"])
@pytest.mark.parametrize(
    ("profile", "extension"),
    [("sse2", "sse"), ("avx2", "avx2"), ("skylake", "avx512")],
)
def test_x86_byte_shift_right_composes_sign_mask(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    signature: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "shift_right",
            ("si8",),
        )
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == signature
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "greater_than" in lowered.body_text
        assert "to_vector" in lowered.body_text
        assert "cmpgt_epi8" not in lowered.body_text
        assert "movm_epi8" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("avx2", "sse", "si32", "_mm_sllv_epi32"),
        ("avx2", "avx2", "ui8", "_mm256_sllv_epi32"),
        ("avx2", "sse", "si8", "_mm_sllv_epi32"),
        ("avx2", "avx2", "ui16", "_mm256_sllv_epi32"),
        ("avx2", "sse", "si16", "_mm_sllv_epi32"),
        ("skylake", "avx512", "si8", "_mm512_sllv_epi16"),
        ("skylake", "avx2_vl", "ui8", "_mm256_sllv_epi16"),
        ("skylake", "sse_vl", "si8", "_mm_sllv_epi16"),
        ("skylake", "sse_vl", "ui16", "_mm_sllv_epi16"),
        ("avx2", "avx2", "f32", "::tsl::reinterpret<Vec"),
        ("skylake", "avx512", "f64", "::tsl::reinterpret<Vec"),
        ("sse", "sse", "f32", "::tsl::shift_left<tsl::simd<float, tsl::scalar>"),
        ("sse2", "sse", "si32", "::tsl::shift_left<tsl::simd<int32_t, tsl::scalar>"),
        ("avx", "avx2", "si16", "::tsl::extract<Vec"),
        ("knl", "avx512", "ui8", "::tsl::extract<Vec"),
    ],
)
def test_x86_vector_shift_left_uses_native_or_bit_pattern_composition(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_left", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("avx2", "sse", "si32", "_mm_srav_epi32"),
        ("avx2", "avx2", "si8", "_mm256_srlv_epi32"),
        ("avx2", "sse", "ui8", "_mm_srlv_epi32"),
        ("avx2", "avx2", "si16", "_mm256_srav_epi32"),
        ("avx2", "sse", "ui16", "_mm_srlv_epi32"),
        ("avx2", "avx2", "si64", "_mm256_srlv_epi64"),
        ("skylake", "avx512", "si8", "_mm512_srlv_epi16"),
        ("skylake", "avx2_vl", "ui8", "_mm256_srlv_epi16"),
        ("skylake", "sse_vl", "si8", "_mm_srlv_epi16"),
        ("skylake", "avx512", "si16", "_mm512_srav_epi16"),
        ("skylake", "sse_vl", "ui16", "_mm_srlv_epi16"),
        ("avx2", "avx2", "f64", "::tsl::reinterpret<Vec"),
        ("sse", "sse", "f32", "::tsl::shift_right<tsl::simd<float, tsl::scalar>"),
        ("sse2", "sse", "si64", "::tsl::shift_right<tsl::simd<int64_t, tsl::scalar>"),
        ("avx", "avx2", "si16", "::tsl::extract<Vec"),
        ("kml", "avx512", "si8", "::tsl::extract<Vec"),
    ],
)
def test_x86_vector_shift_right_uses_native_or_bit_pattern_composition(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    expected_fragment: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "shift_right", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    _assert_x86_shift_register_path(cpp, expected_fragment)


@pytest.mark.parametrize("type_tag", ["si32", "ui32"])
def test_neon_vector_shift_right_composes_count_negation(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slots = [
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["neon"],
            "shift_right",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.signature == "v:=(v,v)"
    ]

    assert slots
    for slot in slots:
        cpp = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, "cpp")
        ).specialization

        assert cpp is not None
        assert "::tsl::sub<" in cpp.body_text
        assert "::tsl::set_zero<" in cpp.body_text
        assert "vshlq" in cpp.body_text
        assert "vnegq" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [("sve", "sve"), ("sve128", "sve128")],
)
@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_sve_float_vector_shift_left_casts_numeric_counts(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "shift_left",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "v:=(v,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "shift_u = ::tsl::cast<Vec" in cpp.body_text
    assert ">(shift)" in cpp.body_text
    assert "shift_u = ::tsl::reinterpret" not in cpp.body_text


def test_compile_time_branches_keep_type_aliases_lexically_scoped(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "shift_right", ("f32",))
        .selected
        if selected.extension.name == "sse"
        and selected.primitive.signature == "v:=(v,v)"
    )
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert rust is not None
    assert "Simd<u32, Sse>" in rust.body_text
    assert "Simd<i32, Sse>" in rust.body_text


def test_clang_vector_shift_left_uses_builtin_vector_operator(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "shift_left", ("si32",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.signature == "v:=(v,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::min<" in cpp.body_text
    assert "__builtin_elementwise_min" not in cpp.body_text
    assert "bits << safe_counts" in cpp.body_text
    assert "valid ? shifted" in cpp.body_text
    assert "for (" not in cpp.body_text
    assert "to_array" not in cpp.body_text


def test_clang_vector_shift_right_uses_builtin_vector_operator(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "shift_right", ("si32",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.signature == "v:=(v,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::min<" in cpp.body_text
    assert "__builtin_elementwise_min" not in cpp.body_text
    assert "data >> safe_counts" in cpp.body_text
    assert "for (" not in cpp.body_text
    assert "to_array" not in cpp.body_text
