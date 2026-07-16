"""Conversion and representation lowering regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize(
    ("type_tag", "to_target"),
    [
        ("si8", "si16"),
        ("ui16", "ui32"),
        ("si32", "si64"),
        ("f32", "f64"),
    ],
)
def test_neon_widening_cast_reuses_convert_up_low_chunk(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
    to_target: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "cast", (type_tag,))
        .selected
        if selected.extension.name == "neon" and selected.to_target == to_target
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "convert_up" in lowered.body_text
        assert "vget_low" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "low_intrinsic", "widen_intrinsic"),
    [
        ("si8", "si16", "vget_low_s8", "vmovl_s8"),
        ("ui16", "ui32", "vget_low_u16", "vmovl_u16"),
        ("si32", "si64", "vget_low_s32", "vmovl_s32"),
        ("f32", "f64", "vget_low_f32", "vcvt_f64_f32"),
    ],
)
def test_neon_convert_up_low_chunk_is_the_intrinsic_leaf(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    low_intrinsic: str,
    widen_intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["neon"], "convert_up", (source_type,)
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
        assert low_intrinsic in lowered.body_text
        assert widen_intrinsic in lowered.body_text
        assert "::tsl::cast<" not in lowered.body_text


@pytest.mark.parametrize("source_type", ["si64", "ui64"])
def test_avx2_i64_to_f64_cast_composes_semantic_operations(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", (source_type,))
        .selected
        if selected.extension.name == "avx2" and selected.to_target == "f64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        for primitive in (
            "set1",
            "shift_right",
            "binary_xor",
            "reinterpret",
            "to_mask",
            "blend",
            "sub",
            "add",
        ):
            assert primitive in lowered.body_text
        assert "_mm256_blend_epi32" not in lowered.body_text
        assert "_mm256_set1_epi64x" not in lowered.body_text
        assert "_mm256_srli_epi64" not in lowered.body_text
        assert "_mm256_xor_si256" not in lowered.body_text
        assert "_mm256_sub_pd" not in lowered.body_text
        assert "_mm256_add_pd" not in lowered.body_text


def test_sse_i64_to_f64_cast_is_pure_primitive_composition(
    catalog: Catalog,
    machine_profiles,
) -> None:
    source_type = "si64"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", (source_type,))
        .selected
        if selected.extension.name == "sse" and selected.to_target == "f64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        for primitive in (
            "set1",
            "shift_right",
            "binary_or" if source_type == "ui64" else "set_zero",
            "reinterpret",
            "to_mask",
            "blend",
            "sub",
            "add",
        ):
            assert primitive in lowered.body_text
        assert "_mm" not in lowered.body_text


def test_sse_ui64_to_f64_cast_prefers_exact_additive_fallback(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", ("ui64",))
        .selected
        if selected.extension.name == "sse" and selected.to_target == "f64"
    )

    assert slot.required_features == frozenset({"sse2"})
    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" in lowered.body_text
        assert "from_array" in lowered.body_text


@pytest.mark.parametrize("source_type", ["si64", "ui64"])
def test_sse2_i64_to_f64_cast_keeps_additive_array_fallback(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sse2"], "cast", (source_type,))
        .selected
        if selected.extension.name == "sse" and selected.to_target == "f64"
    )

    assert slot.required_features == frozenset({"sse2"})
    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" in lowered.body_text
        assert "from_array" in lowered.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "evidence"),
    [
        ("f32", "ui32", "::tsl::extract<Vec"),
        ("f64", "ui64", "::tsl::extract<Vec"),
    ],
)
def test_avx_float_to_unsigned_cast_keeps_lower_feature_path(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx"], "cast", (source_type,))
        .selected
        if selected.extension.name == "avx2"
        and selected.to_target == target_type
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert slot.required_features == frozenset({"avx"})
    assert cpp is not None
    assert evidence in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("source_type", "target_type", "evidence"),
    [
        ("f32", "ui32", "_mm256_cvttps_epi32"),
        ("f64", "ui64", "_mm256_cvtepi32_epi64"),
    ],
)
def test_avx2_float_to_unsigned_cast_keeps_preferred_existing_path(
    catalog: Catalog,
    machine_profiles,
    source_type: str,
    target_type: str,
    evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", (source_type,))
        .selected
        if selected.extension.name == "avx2" and selected.to_target == target_type
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert slot.required_features == frozenset({"avx2"})
    assert cpp is not None
    assert evidence in cpp.body_text
    assert "::tsl::extract<Vec" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "source_type", "target_type", "forbidden"),
    [
        ("avx2", "avx2", "f64", "si32", "zextsi128"),
        ("avx2", "avx2", "f64", "ui32", "zextsi128"),
        ("skylake", "avx512", "f64", "si32", "zextsi256"),
        ("skylake", "avx512", "f64", "ui32", "zextsi256"),
        ("skylake", "avx512", "si64", "f32", "zextps256"),
        ("skylake", "avx512", "ui64", "f32", "zextps256"),
    ],
)
def test_x86_narrow_result_cast_uses_semantic_zero_and_insert(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    forbidden: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "cast", (source_type,))
        .selected
        if selected.extension.name == extension and selected.to_target == target_type
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "set_zero" in lowered.body_text
        assert "insert" in lowered.body_text
        assert forbidden not in lowered.body_text


def test_avx512_partial_narrow_gather_defaults_to_intrinsic_and_keeps_fallback(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            "gather_narrow_partial",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "avx512"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "i64gather" in lowered.body_text
        assert "set_zero" in lowered.body_text
        assert "insert" in lowered.body_text
        assert "zextsi256" not in lowered.body_text
        assert [body.name for body in lowered.variant_bodies] == [
            "scalar_lanes_fallback"
        ]
        assert "to_array" in lowered.variant_bodies[0].body_text
        assert "from_array" in lowered.variant_bodies[0].body_text


@pytest.mark.parametrize("primitive", ["compress_store", "expand_load"])
def test_clang_pack_memory_paths_unroll_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "lane_primitive"),
    [("compress_store", "extract_value"), ("expand_load", "insert_value")],
)
@pytest.mark.parametrize("type_tag", ["ui8", "ui32", "f32", "f64"])
def test_wasm_pack_memory_paths_compose_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    lane_primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            primitive,
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
        assert lane_primitive in lowered.body_text
        assert "extract_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "to_integral" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "lane_primitive"),
    [("compress_store", "extract_value"), ("expand_load", "insert_value")],
)
@pytest.mark.parametrize("type_tag", ["ui8", "ui32", "f32", "f64"])
def test_neon_pack_memory_paths_compose_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    lane_primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lane_primitive in lowered.body_text
        assert "vgetq_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "to_integral" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [("sse2", "sse"), ("avx2", "avx2")],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si32", "f32", "f64"])
def test_x86_compress_store_uses_typed_register_lane_extraction(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "compress_store", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "to_integral" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text
