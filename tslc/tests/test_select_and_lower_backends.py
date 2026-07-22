"""WebAssembly and core backend lowering regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
    _by_key,
    _wasm_slot,
    _wasm_unmasked_slots,
)


@pytest.mark.parametrize(
    "primitive",
    ("binary_and", "binary_andnot", "binary_or", "binary_xor", "inv"),
)
@pytest.mark.parametrize(
    "type_tag",
    ("si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64", "f32", "f64"),
)
def test_lower_wasm128_bitwise_slice_for_all_arith_types(
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

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None


@pytest.mark.parametrize(
    ("primitive", "type_tag", "expected_cpp", "expected_rust"),
    (
        (
            "sub",
            "si32",
            "return wasm_i32x4_sub(left, right);",
            "unsafe { return core::arch::wasm32::i32x4_sub(left, right); }",
        ),
        (
            "set1",
            "ui32",
            "return wasm_i32x4_splat(static_cast<int32_t>(value));",
            "unsafe { return core::arch::wasm32::i32x4_splat((value) as i32); }",
        ),
        (
            "set_zero",
            "f32",
            "return ::tsl::set1<Vec>(static_cast<float>(0));",
            "return set1::<Self>((0) as f32);",
        ),
    ),
)
def test_lower_initial_wasm128_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
    expected_cpp,
    expected_rust,
) -> None:
    slots = _by_key(catalog, machine_profiles["wasm32-simd128"], primitive)
    slot = slots[(type_tag, "wasm128")]

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


@pytest.mark.parametrize(
    ("primitive", "type_tag", "expected_cpp", "expected_rust"),
    (
        (
            "load",
            "si32",
            (
                "return wasm_v128_load("
                "reinterpret_cast<typename Vec::register_type const *>(ptr));"
            ),
            (
                "unsafe { return core::arch::wasm32::v128_load("
                "ptr as *const Self::RegisterType); }"
            ),
        ),
        (
            "store",
            "f32",
            (
                "wasm_v128_store(reinterpret_cast<typename Vec::register_type *>(ptr),\n"
                "              data);"
            ),
            (
                "unsafe { core::arch::wasm32::v128_store("
                "ptr as *mut Self::RegisterType,\n"
                "              data); }"
            ),
        ),
    ),
)
def test_lower_wasm128_memory_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
    expected_cpp,
    expected_rust,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, type_tag)

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


def test_lower_wasm128_array_roundtrip_primitives(catalog: Catalog, machine_profiles) -> None:
    from_array = _wasm_slot(catalog, machine_profiles, "from_array", "si32")
    to_array = _wasm_slot(catalog, machine_profiles, "to_array", "si32")

    cpp_from = Lowerer().lower(
        from_array, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp_from is not None
    assert (
        cpp_from.body_text
        == "return ::tsl::load<Vec, false>(data.as_ptr());"
    )

    cpp_to = Lowerer().lower(
        to_array, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp_to is not None
    assert "array_type<int32_t, 4> tmp{};" in cpp_to.body_text
    assert "::tsl::store<Vec, false>(tmp.data(), a)" in cpp_to.body_text
    assert "return tmp;" in cpp_to.body_text


def test_lower_scalar_and_generic_division_use_normalized_lane_helper(
    catalog: Catalog,
    machine_profiles,
) -> None:
    scalar = next(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["scalar"], "div", ("si32",))
        .selected
        if slot.extension.name == "scalar"
        and slot.primitive.attributes.get("mask") is None
    )
    generic = next(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "div", ("si32",))
        .selected
        if slot.extension.name == "generic"
        and slot.primitive.attributes.get("mask") is None
    )

    for backend_id, helper_call in (
        ("cpp", "::tsl::detail::helpers::arith_div"),
        ("rust", "crate::tsl_core::detail::helpers::arith_div"),
    ):
        dialect = create_backend_dialect(catalog, backend_id)
        scalar_body = Lowerer().lower(scalar, catalog, dialect).specialization
        generic_body = Lowerer().lower(generic, catalog, dialect).specialization
        assert scalar_body is not None
        assert generic_body is not None
        assert helper_call in scalar_body.body_text
        assert helper_call in generic_body.body_text


def test_lower_generic_masked_division_sanitizes_inactive_operands(
    catalog: Catalog,
    machine_profiles,
) -> None:
    masked = tuple(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "div", ("si32",))
        .selected
        if slot.extension.name == "generic"
        and slot.primitive.attributes.get("mask") is not None
    )
    assert {slot.primitive.attributes.get("mask") for slot in masked} == {
        "zero",
        "pass_through",
    }

    for slot in masked:
        for backend_id in ("cpp", "rust"):
            lowered = Lowerer().lower(
                slot,
                catalog,
                create_backend_dialect(catalog, backend_id),
            ).specialization
            assert lowered is not None
            body = lowered.body_text
            assert "safe_dividend" in body
            assert "safe_divisor" in body
            assert body.index("safe_divisor") < body.rindex("div")


def test_lower_sve_integer_division_checks_participating_zero_lanes(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = tuple(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["sve"], "div", ("si32",))
        .selected
        if slot.extension.name == "sve"
    )
    assert len(slots) == 3

    for slot in slots:
        lowered = Lowerer().lower(
            slot,
            catalog,
            create_backend_dialect(catalog, "cpp"),
        ).specialization
        assert lowered is not None
        body = lowered.body_text
        assert "arith_zero_divisor_fail" in body
        assert body.index("arith_zero_divisor_fail") < body.index("svdiv")
        if slot.primitive.attributes.get("mask") is not None:
            assert "active_zero_divisors" in body
            assert "mask_binary_and" in body


def test_lower_scalar_generic_and_clang_integer_remainder_use_normalized_helper(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = (
        next(
            slot
            for slot in Selector()
            .select_profile(catalog, machine_profiles["scalar"], "mod", ("si32",))
            .selected
            if slot.extension.name == extension
            and slot.primitive.attributes.get("mask") is None
        )
        for extension in ("scalar", "generic", "clang_v128")
    )

    for slot in slots:
        backend_helpers = [("cpp", "::tsl::detail::helpers::arith_rem")]
        if slot.extension.name != "clang_v128":
            backend_helpers.append(
                ("rust", "crate::tsl_core::detail::helpers::arith_rem")
            )
        for backend_id, helper_call in backend_helpers:
            lowered = Lowerer().lower(
                slot,
                catalog,
                create_backend_dialect(catalog, backend_id),
            ).specialization
            assert lowered is not None
            assert helper_call in lowered.body_text


def test_lower_sve_floating_remainder_uses_fmod_helper_without_vector_quotient(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["sve"], "mod", ("f32",))
        .selected
        if slot.extension.name == "sve"
        and slot.primitive.attributes.get("mask") is None
    )
    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "cpp"),
    ).specialization

    assert lowered is not None
    assert "arith_rem" in lowered.body_text
    assert "svlastb" in lowered.body_text
    assert "svdiv" not in lowered.body_text


def test_lower_generic_masked_remainder_sanitizes_inactive_operands(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = tuple(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "mod", ("si32",))
        .selected
        if slot.extension.name == "generic"
        and slot.primitive.attributes.get("mask") is not None
    )
    assert {slot.primitive.attributes.get("mask") for slot in slots} == {
        "zero",
        "pass_through",
    }

    for slot in slots:
        for backend_id in ("cpp", "rust"):
            lowered = Lowerer().lower(
                slot,
                catalog,
                create_backend_dialect(catalog, backend_id),
            ).specialization
            assert lowered is not None
            body = lowered.body_text
            assert "safe_dividend" in body
            assert "safe_divisor" in body
            assert body.index("safe_divisor") < body.rindex("mod")


@pytest.mark.parametrize(
    ("primitive", "type_tag", "expected_cpp", "expected_rust"),
    (
        (
            "mul",
            "si32",
            "return wasm_i32x4_mul(factor1, factor2);",
            "unsafe { return core::arch::wasm32::i32x4_mul(factor1, factor2); }",
        ),
        (
            "div",
            "f32",
            "return wasm_f32x4_div(dividend, divisor);",
            "unsafe { return core::arch::wasm32::f32x4_div(dividend, divisor); }",
        ),
        (
            "popcnt",
            "ui8",
            "return wasm_i8x16_popcnt(data);",
            "unsafe { return core::arch::wasm32::i8x16_popcnt(data); }",
        ),
    ),
)
def test_lower_wasm128_expanded_direct_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
    expected_cpp,
    expected_rust,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, type_tag)

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


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "lanes"),
    [
        ("neon", "neon", "si32", 4),
        ("wasm32-simd128", "wasm128", "ui32", 4),
    ],
)
def test_integer_div_composes_unrolled_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    lanes: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "div", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == lanes * 2
        assert lowered.body_text.count("insert_value") == lanes
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "lanes"),
    [
        ("neon", "neon", "ui8", 16),
        ("wasm32-simd128", "wasm128", "ui32", 4),
        ("wasm32-simd128", "wasm128", "f32", 4),
    ],
)
def test_mod_composes_unrolled_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    lanes: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "mod", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract_value") == lanes * 2
        assert lowered.body_text.count("insert_value") == lanes
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "si16"])
def test_sve_narrow_mod_uses_register_lane_predicates(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "mod", (type_tag,))
        .selected
        if selected.extension.name == "sve"
        and selected.primitive.attributes.get("mask") is None
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svlastb" in lowered.body_text
    assert "masked_set1" in lowered.body_text
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svdup_n" not in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "free" not in lowered.body_text


@pytest.mark.parametrize(
    (
        "profile",
        "extension",
        "type_tag",
        "extract_operation",
        "extract_count",
        "insert_operation",
        "insert_count",
    ),
    [
        ("sse2", "sse", "ui8", "extract_value", 32, "insert_value", 16),
        ("sse2", "sse", "f32", "extract_value", 8, "insert_value", 4),
        ("avx", "avx2", "si32", "extract", 4, "insert", 2),
        ("avx2", "avx2", "f64", "extract", 4, "insert", 2),
        ("skylake", "avx512", "ui8", "extract", 4, "insert", 2),
        ("skylake", "avx512", "f64", "extract", 4, "insert", 2),
        ("kml", "avx512", "ui8", "extract", 8, "insert", 4),
        ("knl", "avx512", "f64", "extract", 8, "insert", 4),
    ],
)
def test_x86_mod_composes_through_semantic_register_operations(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    extract_operation: str,
    extract_count: int,
    insert_operation: str,
    insert_count: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "mod", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count(extract_operation) == extract_count
        assert lowered.body_text.count(insert_operation) == insert_count
        assert "_mm" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_lower_wasm128_lzc_uses_scalar_lane_helper(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, "lzc", "ui32")

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert "::tsl::lzc_scalar<tsl::simd<uint32_t, tsl::scalar>>" in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None


@pytest.mark.parametrize(
    ("primitive", "type_tag", "cpp_needles", "rust_needles"),
    (
        (
            "mul",
            "si8",
            (
                "wasm_u16x8_extmul_low_u8x16",
                "::tsl::convert_down<",
                "::tsl::binary_or<",
            ),
            ("u16x8_extmul_low_u8x16", "convert_down::<", "binary_or::<"),
        ),
            (
                "max",
                "si32",
                ("wasm_i32x4_max",),
                ("i32x4_max",),
        ),
    ),
)
def test_lower_wasm128_native_or_composed_primitives_avoid_generic_bridge(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
    cpp_needles,
    rust_needles,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, type_tag)

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert "tsl::generic" not in cpp.body_text
    for needle in cpp_needles:
        assert needle in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert "Generic" not in rust.body_text
    for needle in rust_needles:
        assert needle in rust.body_text


def test_lower_wasm128_shift_overloads_keep_scalar_and_vector_counts_distinct(
    catalog: Catalog,
    machine_profiles,
) -> None:
    left_slots = {
        slot.primitive.signature: slot
        for slot in _wasm_unmasked_slots(catalog, machine_profiles, "shift_left", "si32")
    }
    slots = {
        slot.primitive.signature: slot
        for slot in _wasm_unmasked_slots(catalog, machine_profiles, "shift_right", "si32")
    }
    assert {"v:=(v,sImm)", "v:=(v,s)", "v:=(v,v)"} <= set(left_slots)
    assert {"v:=(v,sImm)", "v:=(v,s)", "v:=(v,v)"} <= set(slots)

    cpp = create_backend_dialect(catalog, "cpp")
    rust = create_backend_dialect(catalog, "rust")

    left_imm = Lowerer().lower(left_slots["v:=(v,sImm)"], catalog, cpp).specialization
    left_scalar = Lowerer().lower(left_slots["v:=(v,s)"], catalog, cpp).specialization
    left_vector = Lowerer().lower(left_slots["v:=(v,v)"], catalog, cpp).specialization
    left_imm_rust = Lowerer().lower(
        left_slots["v:=(v,sImm)"], catalog, rust
    ).specialization
    left_scalar_rust = Lowerer().lower(
        left_slots["v:=(v,s)"], catalog, rust
    ).specialization
    left_vector_rust = Lowerer().lower(
        left_slots["v:=(v,v)"], catalog, rust
    ).specialization

    imm = Lowerer().lower(slots["v:=(v,sImm)"], catalog, cpp).specialization
    scalar = Lowerer().lower(slots["v:=(v,s)"], catalog, cpp).specialization
    vector = Lowerer().lower(slots["v:=(v,v)"], catalog, cpp).specialization
    vector_rust = Lowerer().lower(slots["v:=(v,v)"], catalog, rust).specialization

    assert left_imm is not None
    assert "::tsl::shift_left<Vec>" in left_imm.body_text
    assert "wasm_i32x4_shl(data, shift)" not in left_imm.body_text

    assert left_imm_rust is not None
    assert "shift_left::<Self, _>" in left_imm_rust.body_text
    assert "i32x4_shl::<" not in left_imm_rust.body_text

    assert left_scalar is not None
    assert left_scalar.body_text == (
        "return wasm_i32x4_shl(data, static_cast<uint32_t>(shift));"
    )

    assert left_scalar_rust is not None
    assert left_scalar_rust.body_text == (
        "unsafe { return core::arch::wasm32::i32x4_shl(data, (shift) as u32); }"
    )

    assert left_vector is not None
    assert left_vector.body_text.count("extract_value") == 8
    assert left_vector.body_text.count("insert_value") == 4
    assert "wasm_i32x4_extract_lane" not in left_vector.body_text
    assert "wasm_i32x4_replace_lane" not in left_vector.body_text
    assert "to_array" not in left_vector.body_text

    assert left_vector_rust is not None
    assert left_vector_rust.body_text.count("extract_value") == 8
    assert left_vector_rust.body_text.count("insert_value") == 4
    assert "i32x4_extract_lane" not in left_vector_rust.body_text
    assert "i32x4_replace_lane" not in left_vector_rust.body_text
    assert "to_array" not in left_vector_rust.body_text

    assert imm is not None
    assert "::tsl::shift_right<Vec, PreserveSign>" in imm.body_text
    assert "static_cast<int32_t>(shift)" in imm.body_text
    assert "::tsl::to_array<Vec>(shift)" not in imm.body_text

    assert scalar is not None
    assert "wasm_i32x4_shr(data, static_cast<uint32_t>(shift))" in scalar.body_text
    assert "wasm_u32x4_shr(udata, static_cast<uint32_t>(shift))" in scalar.body_text
    assert "generic_shift" not in scalar.body_text

    assert vector is not None
    assert vector.body_text.count("extract_value") == 8
    assert vector.body_text.count("insert_value") == 4
    assert "wasm_i32x4_extract_lane" not in vector.body_text
    assert "wasm_i32x4_replace_lane" not in vector.body_text
    assert "to_array" not in vector.body_text

    assert vector_rust is not None
    assert vector_rust.body_text.count("extract_value") == 8
    assert vector_rust.body_text.count("insert_value") == 4
    assert "i32x4_extract_lane" not in vector_rust.body_text
    assert "i32x4_replace_lane" not in vector_rust.body_text
    assert "to_array" not in vector_rust.body_text
