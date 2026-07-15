"""Additive candidate and composed fallback selection regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize(
    ("extension_name", "type_tag", "expected_body"),
    (
        ("clang_v128", "si8", "__builtin_elementwise_abs"),
        ("clang_v256", "si64", "__builtin_elementwise_abs"),
        ("clang_v512", "f32", "__builtin_elementwise_abs"),
        ("clang_v128_bool", "f64", "__builtin_elementwise_abs"),
        ("clang_v256_bool", "si16", "__builtin_elementwise_abs"),
        ("clang_v512_bool", "ui32", "return data"),
    ),
)
def test_clang_vector_abs_uses_elementwise_builtin_and_keeps_fallback(
    catalog: Catalog,
    machine_profiles,
    extension_name: str,
    type_tag: str,
    expected_body: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["avx2"], "abs", (type_tag,)
        )
        .selected
        if selected.extension.name == extension_name
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert expected_body in lowered.body_text
    assert "for (" not in lowered.body_text
    assert [variant.name for variant in lowered.variant_bodies] == [
        "scalar_lanes_fallback"
    ]
    assert "for (" in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag", "intrinsic"),
    (
        ("sse3", "sse", "si8", "_mm_abs_epi8"),
        ("avx2", "avx2", "si32", "_mm256_abs_epi32"),
        ("skylake", "avx512", "si16", "_mm512_abs_epi16"),
        ("skylake", "avx512", "si64", "_mm512_abs_epi64"),
        ("skylake", "avx2_vl", "si64", "_mm256_abs_epi64"),
        ("skylake", "sse_vl", "si64", "_mm_abs_epi64"),
    ),
)
def test_x86_abs_uses_exact_intrinsics_and_keeps_scalar_lane_fallback(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile_name], "abs", (type_tag,))
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert lowered.implementation_state.value == "native"
        assert [variant.name for variant in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "to_array" in lowered.variant_bodies[0].body_text
        assert "from_array" in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag"),
    (
        ("avx2", "avx2", "si64"),
        ("sse2", "sse", "f64"),
        ("avx2", "avx2", "f32"),
    ),
)
def test_x86_abs_composes_register_operations_when_no_exact_intrinsic_exists(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile_name], "abs", (type_tag,))
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert lowered.implementation_state.value == "composed"
        if type_tag == "si64":
            assert "greater_than" in lowered.body_text
            assert "binary_xor" in lowered.body_text
            assert "sub" in lowered.body_text
        else:
            assert "reinterpret" in lowered.body_text
            assert "shift_right" in lowered.body_text
            assert "binary_and" in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "to_array" in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("extension_name", "type_tag", "intrinsic"),
    (
        ("avx512", "ui32", "_mm512_alignr_epi32"),
        ("avx512", "f64", "_mm512_alignr_epi64"),
        ("avx2_vl", "si64", "_mm256_alignr_epi64"),
        ("sse_vl", "ui32", "_mm_alignr_epi32"),
    ),
)
def test_avx512_align_right_lanes_uses_full_vector_align_intrinsics(
    catalog: Catalog,
    machine_profiles,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            "align_right_lanes",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "to_array" in lowered.variant_bodies[0].body_text
        assert "from_array" in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name"),
    (("avx2", "avx2"), ("skylake", "avx512")),
)
def test_byte_alignr_is_not_used_for_full_vector_lane_alignment(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            "align_right_lanes",
            ("si8",),
        )
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "alignr_epi8" not in lowered.body_text
        assert "to_array" in lowered.body_text
        assert "from_array" in lowered.body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag", "intrinsic", "backends"),
    (
        ("neon", "neon", "si32", "vabsq_s32", ("cpp", "rust")),
        (
            "wasm32-simd128",
            "wasm128",
            "si16",
            "i16x8_abs",
            ("cpp", "rust"),
        ),
        ("sve", "sve", "si64", "svabs_s64_x", ("cpp",)),
    ),
)
def test_non_x86_abs_uses_native_intrinsics_and_keeps_fallback(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
    backends: tuple[str, ...],
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile_name], "abs", (type_tag,))
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in backends:
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "for " in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag", "intrinsic", "backends"),
    (
        ("sse3", "sse", "si32", "_mm_alignr_epi8", ("cpp", "rust")),
        ("neon", "neon", "si32", "vextq_u8", ("cpp", "rust")),
        (
            "wasm32-simd128",
            "wasm128",
            "si32",
            "i8x16_swizzle",
            ("cpp", "rust"),
        ),
        (
            "avx2",
            "clang_v128",
            "si32",
            "__builtin_shufflevector",
            ("cpp",),
        ),
        ("sve", "sve", "si32", "svtbl_s32", ("cpp",)),
    ),
)
def test_align_right_lanes_prefers_native_cross_lane_operations(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
    backends: tuple[str, ...],
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            "align_right_lanes",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in backends:
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "for " in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("primitive", "profile_name", "extension_name", "type_tag", "intrinsic"),
    (
        (
            "permute_lanes",
            "avx2",
            "avx2",
            "si32",
            "_mm256_permutevar8x32_epi32",
        ),
        (
            "permute_lanes",
            "cannonlake",
            "avx512",
            "si8",
            "_mm512_permutexvar_epi8",
        ),
        (
            "table_lookup",
            "skylake",
            "avx512",
            "si64",
            "_mm512_permutex2var_epi64",
        ),
        (
            "table_lookup",
            "skylake",
            "avx2_vl",
            "si64",
            "_mm256_permutex2var_epi64",
        ),
        ("permute_lanes", "neon", "neon", "si8", "vqtbl1q_s8"),
        (
            "table_lookup",
            "wasm32-simd128",
            "wasm128",
            "ui8",
            "i8x16_swizzle",
        ),
        ("table_lookup", "sve256", "sve256", "si32", "svtbl_s32"),
    ),
)
def test_runtime_permute_and_table_lookup_prefer_native_operations(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            primitive,
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
        and any(param.name == "IndicesType" for param in selected.primitive.generic_params)
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert intrinsic in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert [variant.name for variant in lowered.variant_bodies] == [
        "scalar_lanes_fallback"
    ]
    assert "for " in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag", "intrinsic"),
    (
        ("avx2", "avx2", "si32", "_mm256_shuffle_epi32"),
        ("sse2", "sse", "f64", "_mm_shuffle_pd"),
        ("skylake", "avx512", "si64", "_mm512_permutex_epi64"),
        (
            "avx2",
            "clang_v128",
            "si32",
            "__builtin_shufflevector",
        ),
    ),
)
def test_immediate_permute_lanes_prefers_native_operations(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            "permute_lanes",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
        and not any(
            param.name == "IndicesType" for param in selected.primitive.generic_params
        )
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert intrinsic in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert [variant.name for variant in lowered.variant_bodies] == [
        "scalar_lanes_fallback"
    ]
    assert "for " in lowered.variant_bodies[0].body_text


def test_sse41_to_mask_fast_paths_win_over_portable_fallback(
    catalog: Catalog, machine_profiles
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx"], "to_mask", ("si64", "f64"))
        .selected
    }

    cpp_si64 = Lowerer().lower(
        slots[("si64", "sse")], catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp_si64 is not None
    assert "sse4_1" in cpp_si64.required_features
    assert "::tsl::equal<Vec>" in cpp_si64.body_text

    cpp_f64 = Lowerer().lower(
        slots[("f64", "sse")], catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp_f64 is not None
    assert "::tsl::equal<tsl::simd<uint64_t, tsl::sse>>" in cpp_f64.body_text
    assert "::tsl::reinterpret<tsl::simd<uint64_t, tsl::sse>" in cpp_f64.body_text


@pytest.mark.parametrize("type_tag", ["si32", "f64"])
def test_avx_to_mask_composes_existing_sse_halves(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx"], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
    )

    assert slot.required_features == frozenset({"avx"})
    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("to_mask") == 2
        assert lowered.body_text.count("insert") == 2
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["si32", "ui32"])
def test_avx2_to_mask_keeps_generic_round_trip_as_additive_benchmark_candidate(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
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
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "generic_fallback"
        ]
        fallback = lowered.variant_bodies[0].body_text
        assert "to_mask" in fallback
        assert "to_vector" in fallback
        assert "to_array" in fallback
        assert "from_array" in fallback


@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin", "hand", "hor"])
def test_avx2_integer_reduction_keeps_generic_fallback_as_additive_candidate(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("si32",))
        .selected
        if selected.extension.name == "avx2"
        and len(selected.primitive.parameters) == 1
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "generic_fallback"
        ]
        fallback = lowered.variant_bodies[0].body_text
        assert "to_array" in fallback
        assert "from_array" in fallback
        assert primitive in fallback


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag"),
    (
        ("sse2", "sse", "si32"),
        ("sse2", "sse", "f32"),
        ("avx2", "avx2", "si32"),
        ("skylake", "avx512", "si32"),
        ("knl", "avx512", "si32"),
        ("neon", "neon", "si32"),
        ("wasm32-simd128", "wasm128", "si32"),
    ),
)
def test_fixed_width_modulo_keeps_generic_fallback_as_additive_candidate(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile_name], "mod", (type_tag,))
        .selected
        if selected.extension.name == extension_name
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "generic_fallback"
        ]
        fallback = lowered.variant_bodies[0].body_text
        assert fallback.count("to_array") == 2
        assert fallback.count("from_array") == 3
        assert "mod" in fallback


@pytest.mark.parametrize(
    ("primitive", "profile_name", "extension_name", "type_tag", "variant_names"),
    (
        ("popcnt", "sse2", "sse", "ui8", ["generic_fallback"]),
        (
            "popcnt",
            "avx2",
            "avx2",
            "ui8",
            ["sse_halves", "generic_fallback"],
        ),
        ("popcnt", "avx2", "avx2", "ui32", ["generic_fallback"]),
        ("lzc", "sse2", "sse", "ui32", ["generic_fallback"]),
        ("lzc", "avx2", "avx2", "ui8", ["generic_fallback"]),
        ("lzc", "avx2", "avx2", "ui32", ["generic_fallback"]),
        (
            "lzc",
            "avx2",
            "avx2",
            "f32",
            ["sse_halves", "generic_fallback"],
        ),
        ("lzc", "skylake", "avx512", "ui8", ["generic_fallback"]),
        ("lzc", "knl", "avx512", "ui8", ["generic_fallback"]),
    ),
)
def test_bit_count_algorithms_keep_additive_benchmark_candidates(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    variant_names: list[str],
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            primitive,
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert [variant.name for variant in lowered.variant_bodies] == variant_names
        fallback = next(
            variant
            for variant in lowered.variant_bodies
            if variant.name == "generic_fallback"
        )
        assert fallback.body_text.count("to_array") == 2
        assert fallback.body_text.count("from_array") == 2
        if "sse_halves" in variant_names:
            halves = next(
                variant
                for variant in lowered.variant_bodies
                if variant.name == "sse_halves"
            )
            assert halves.body_text.count("extract") == 2
            assert halves.body_text.count("insert") == 2


@pytest.mark.parametrize(
    ("profile_name", "extension_name"),
    (("neon", "neon"), ("wasm32-simd128", "wasm128")),
)
def test_integer_division_keeps_generic_round_trip_as_additive_candidate(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile_name], "div", ("si32",))
        .selected
        if selected.extension.name == extension_name
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert [variant.name for variant in lowered.variant_bodies] == [
            "generic_fallback"
        ]
        fallback = lowered.variant_bodies[0].body_text
        assert fallback.count("to_array") == 3
        assert fallback.count("from_array") == 3


def test_sse2_equal_64_composes_word_equality_and_mask_conversion(
    catalog: Catalog, machine_profiles
) -> None:
    for type_tag in ("si64", "ui64"):
        slot = next(
            s
            for s in Selector()
            .select_profile(catalog, machine_profiles["sse2"], "equal", (type_tag,))
            .selected
            if s.extension.name == "sse" and s.type_tag == type_tag
        )

        cpp = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, "cpp")
        ).specialization

        assert cpp is not None
        assert "::tsl::equal<tsl::simd<uint32_t, tsl::sse>>" in cpp.body_text
        assert "::tsl::to_integral<tsl::simd<uint32_t, tsl::sse>>" in cpp.body_text
        assert "::tsl::to_mask<Vec>(compact)" in cpp.body_text
        assert "intrin<" not in cpp.body_text
        assert "to_array" not in cpp.body_text


def test_sse2_less_than_64_compares_high_then_unsigned_low_words(
    catalog: Catalog, machine_profiles
) -> None:
    bodies = {}
    for type_tag in ("si64", "ui64"):
        slot = next(
            s
            for s in Selector()
            .select_profile(
                catalog, machine_profiles["sse2"], "less_than", (type_tag,)
            )
            .selected
            if s.extension.name == "sse" and s.type_tag == type_tag
        )
        cpp = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, "cpp")
        ).specialization
        assert cpp is not None
        bodies[type_tag] = cpp.body_text

    for body in bodies.values():
        assert "_mm_shuffle_epi32(left, 0xF5)" in body
        assert "_mm_shuffle_epi32(left, 0xA0)" in body
        assert "::tsl::equal<tsl::simd<int32_t, tsl::sse>>" in body
        assert "::tsl::binary_and<tsl::simd<int32_t, tsl::sse>>" in body
        assert "::tsl::binary_or<tsl::simd<int32_t, tsl::sse>>" in body
        assert "::tsl::binary_xor<tsl::simd<int32_t, tsl::sse>>" in body
        assert "::tsl::less_than<tsl::simd<int32_t, tsl::sse>>" in body
        assert "to_array" not in body
    assert "::tsl::less_than<tsl::simd<int32_t, tsl::sse>>(left_high, right_high)" in bodies["si64"]
    assert "::tsl::binary_xor<tsl::simd<int32_t, tsl::sse>>(left_high, sign_bit)" in bodies["ui64"]


def test_masked_set1_reuses_blend_and_set1_on_x86(
    catalog: Catalog, machine_profiles
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "masked_set1", ("si32",))
        .selected
    }

    cpp = Lowerer().lower(
        slots[("si32", "avx2")], catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::blend<Vec>" in cpp.body_text
    assert "::tsl::set1<Vec>" in cpp.body_text
    assert "to_array" not in cpp.body_text


def test_avx_integer_blend_composes_float_bitwise_intrinsics(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx"], "blend", ("si8",))
        .selected
        if s.extension.name == "avx2" and s.type_tag == "si8"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::binary_andnot<tsl::simd<float, tsl::avx2>>" in cpp.body_text
    assert "::tsl::binary_and<tsl::simd<float, tsl::avx2>>" in cpp.body_text
    assert "::tsl::binary_or<tsl::simd<float, tsl::avx2>>" in cpp.body_text
    assert "to_array" not in cpp.body_text
