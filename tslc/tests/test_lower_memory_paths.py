"""Gather, scatter, load, store, and pack lowering regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    SelectedImplementation,
    Selector,
)


@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_scalar_scatter_supports_floating_lanes(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
    type_tag: str,
) -> None:
    primitive = next(
        candidate
        for candidate in catalog.primitives_named("scatter", unmasked=False)
        if ("mask" in candidate.attribute_keys) is masked
    )
    candidate = Selector().evaluate_candidates(
        catalog,
        machine_profiles["scalar"],
        primitive,
        "scalar",
        type_tag,
        None,
    ).ranked[0]
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=candidate.implementation,
        extension=catalog.extensions["scalar"],
        type_tag=type_tag,
        required_features=candidate.required_features,
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" in lowered.body_text
        assert "idx_offset" in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("sse2", "sse"),
        ("avx2", "avx2"),
        ("neon", "neon"),
        ("wasm32-simd128", "wasm128"),
    ],
)
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui16", "f32"])
def test_fixed_width_scatter_extracts_values_without_value_array_round_trips(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    masked: bool,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "scatter", (type_tag,))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "idx_offset" in lowered.body_text
        assert "idx_array" in lowered.body_text
        assert "to_array" in lowered.body_text
        assert "val_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("extension", ["avx512", "avx2_vl", "sse_vl"])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize(
    ("type_tag", "intrinsic"),
    [("ui32", "i32scatter"), ("f64", "i64scatter")],
)
def test_avx512_scatter_keeps_native_scales_and_extracts_default_scale_values(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    masked: bool,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["skylake"], "scatter", (type_tag,))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert intrinsic in lowered.body_text
        assert "extract_value" in lowered.body_text
        assert "val_array" not in lowered.body_text


@pytest.mark.parametrize("masked", [False, True])
def test_clang_scatter_uses_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "scatter", ("ui16",))
        .selected
        if selected.extension.name == "clang_v256"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "index[0]" in lowered.body_text
    assert "a[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "masked", "keeps_index_array", "uses_extract_value"),
    [
        ("gather", False, False, True),
        ("gather", True, False, True),
        ("gather_narrow_partial", False, True, False),
        ("gather_narrow", False, False, False),
    ],
)
def test_clang_gather_writes_result_vector_directly(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    masked: bool,
    keeps_index_array: bool,
    uses_extract_value: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("si16",))
        .selected
        if selected.extension.name == "clang_v256"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "result[" in lowered.body_text
    assert ("idx_array" in lowered.body_text) is keeps_index_array
    assert ("extract_value" in lowered.body_text) is uses_extract_value
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text or keeps_index_array


@pytest.mark.parametrize(
    ("profile", "extension"),
    [("neon", "neon"), ("wasm32-simd128", "wasm128")],
)
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui8", "ui32", "f32", "f64"])
def test_neon_wasm_gather_composes_lane_insertion_without_result_array(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    masked: bool,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "gather", (type_tag,))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "insert_value" in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "idx_array" in lowered.body_text
        assert "to_array" in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "result = to_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [("neon", "neon"), ("wasm32-simd128", "wasm128")],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16", "ui32", "f32"])
def test_neon_wasm_gather_narrow_composes_lane_insertion_directly(
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
            catalog, machine_profiles[profile], "gather_narrow", (type_tag,)
        )
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "insert_value" in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_store_uses_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slots = Selector().select_profile(
        catalog, machine_profiles[profile], "store", ("ui32",)
    ).selected
    slot = next(
        selected for selected in slots if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "data[idx]" in lowered.body_text
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_sequence_mutates_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
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
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
