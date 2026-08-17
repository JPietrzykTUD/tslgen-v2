"""Bitwise-horizontal and WebAssembly lane-composition regressions."""

from __future__ import annotations

from _select_lower_extension_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
    _wasm_slot,
)


@pytest.mark.parametrize(("primitive", "binary_primitive"), [("hand", "binary_and"), ("hor", "binary_or")])
@pytest.mark.parametrize(
    ("type_tag", "reduction_steps"),
    [
        ("si8", 4),
        ("ui8", 4),
        ("si16", 3),
        ("ui16", 3),
        ("si32", 2),
        ("ui32", 2),
        ("si64", 1),
        ("ui64", 1),
        ("f32", 2),
        ("f64", 1),
    ],
)
def test_neon_unmasked_bitwise_horizontal_reduces_in_register(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    binary_primitive: str,
    type_tag: str,
    reduction_steps: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and len(selected.primitive.parameters) == 1
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert lowered.body_text.count("vextq") == reduction_steps
        assert binary_primitive in lowered.body_text
        assert lowered.body_text.count("extract_value") == 1
        assert "vgetq_lane" not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "binary_primitive"),
    [("hand", "binary_and"), ("hor", "binary_or")],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16"])
def test_avx512_small_integer_bitwise_horizontal_folds_sse_quarters(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    binary_primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["knl"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text.count("::tsl::extract<") == 4
    assert "_mm512_extracti32x4_epi32" not in cpp.body_text
    assert f"::tsl::{binary_primitive}<tsl::simd" in cpp.body_text
    assert f"::tsl::{primitive}<tsl::simd" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize(
    ("extension", "type_tag", "intrinsic"),
    [
        ("avx2_vl", "ui32", "_mm256_extracti128_si256"),
        ("sse_vl", "ui64", "_mm_unpackhi_epi64"),
    ],
)
def test_vl_bitwise_horizontal_inherits_fixed_width_register_reduction(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["skylake"], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=v"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        if extension == "avx2_vl":
            assert lowered.body_text.count("extract") == 2
            assert "_mm256_extracti128_si256" not in lowered.body_text
        else:
            assert intrinsic in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_sve_float_hand_bitcasts_native_integer_reduction(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "hand", ("f32",))
        .selected
        if selected.extension.name == "sve"
        and selected.primitive.signature == "s:=v"
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svandv" in lowered.body_text
    assert "bit_cast" in lowered.body_text
    assert "memcpy" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize(
    ("type_tag", "shift_steps"),
    [("ui8", 3), ("si16", 2), ("f32", 1), ("f64", 0)],
)
def test_wasm_bitwise_horizontal_composes_packed_word_extraction(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    shift_steps: int,
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
        and selected.primitive.signature == "s:=v"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == 2
        assert "i64x2_extract_lane" not in lowered.body_text
        assert "reinterpret" in lowered.body_text
        assert lowered.body_text.count("result >>") == shift_steps
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin"])
@pytest.mark.parametrize(("type_tag", "lanes"), [("ui8", 16), ("f32", 4)])
def test_wasm_arithmetic_horizontal_unrolls_semantic_lane_extraction(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    lanes: int,
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
        and selected.primitive.signature == "s:=v"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == lanes
        assert "extract_lane" not in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "(vec, i)" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize(("type_tag", "lanes"), [("ui8", 16), ("si64", 2)])
def test_wasm_masked_minmax_unrolls_mask_tests_and_semantic_lane_extraction(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    lanes: int,
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
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == lanes
        assert "extract_lane" not in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["si64", "ui64"])
def test_neon_mul_64_composes_widening_32_bit_products(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "mul", (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and len(selected.primitive.parameters) == 2
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert lowered.body_text.count("vmull_u32") == 3
        assert "shift_left" in lowered.body_text
        assert "shift_right" in lowered.body_text
        assert "add" in lowered.body_text
        assert "vshlq_n_u64" not in lowered.body_text
        assert "vshrq_n_u64" not in lowered.body_text
        assert "vaddq_u64" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["shift_left", "shift_right"])
@pytest.mark.parametrize("signature", ["v:=(v,sImm)", "v:=(v,s)", "v:=(v,v)"])
@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_neon_float_shifts_compose_integer_bit_shifts(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    signature: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.signature == signature
        and selected.primitive.mask_mode is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "reinterpret" in lowered.body_text
        assert primitive in lowered.body_text
        if signature == "v:=(v,v)":
            assert "cast" in lowered.body_text


@pytest.mark.parametrize(
    ("type_tag", "lane_shape"),
    [
        ("si8", "i8x16"),
        ("ui8", "i8x16"),
        ("si16", "i16x8"),
        ("ui16", "i16x8"),
        ("si32", "i32x4"),
        ("ui32", "i32x4"),
        ("si64", "i64x2"),
        ("ui64", "i64x2"),
        ("f32", "f32x4"),
        ("f64", "f64x2"),
    ],
)
def test_lower_add_wasm128(catalog: Catalog, machine_profiles, type_tag, lane_shape) -> None:
    slot = _wasm_slot(catalog, machine_profiles, "add", type_tag)

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert cpp.extension_name == "wasm128"
    assert cpp.body_text == f"return wasm_{lane_shape}_add(left, right);"

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert rust.body_text == (
        f"unsafe {{ return core::arch::wasm32::{lane_shape}_add(left, right); }}"
    )


@pytest.mark.parametrize(
    "primitive",
    ("add", "sub", "set1", "set_zero", "load", "store", "from_array", "to_array"),
)
@pytest.mark.parametrize(
    "type_tag",
    ("si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64", "f32", "f64"),
)
def test_lower_initial_wasm128_slice_for_all_arith_types(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, type_tag)

    assert slot.required_features == frozenset({"simd128"})

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert cpp.extension_name == "wasm128"

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert rust.extension_name == "wasm128"


@pytest.mark.parametrize(
    ("primitive", "expected_cpp", "expected_rust"),
    (
        (
            "binary_and",
            "return wasm_v128_and(left, right);",
            "unsafe { return core::arch::wasm32::v128_and(left, right); }",
        ),
        (
            "binary_andnot",
            "return wasm_v128_andnot(right, left);",
            "unsafe { return core::arch::wasm32::v128_andnot(right, left); }",
        ),
        (
            "binary_or",
            "return wasm_v128_or(left, right);",
            "unsafe { return core::arch::wasm32::v128_or(left, right); }",
        ),
        (
            "binary_xor",
            "return wasm_v128_xor(left, right);",
            "unsafe { return core::arch::wasm32::v128_xor(left, right); }",
        ),
        (
            "inv",
            "return wasm_v128_not(data);",
            "unsafe { return core::arch::wasm32::v128_not(data); }",
        ),
    ),
)
def test_lower_wasm128_bitwise_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive,
    expected_cpp,
    expected_rust,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, "si32")

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert cpp.body_text == expected_cpp

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert rust.body_text == expected_rust
