"""Extension coverage and arithmetic lowering regressions."""

from __future__ import annotations

from _select_lower_extension_support import (
    Catalog,
    concrete_target_candidates,
    create_backend_dialect,
    DEFAULT_SUPPORT_POLICY,
    Lowerer,
    parse_signature,
    pytest,
    Selector,
    _ALL_ARITH_TYPES,
    _by_key,
    _slots,
)


def test_clang_representation_change_constraints_select_every_valid_width_pair(
    catalog: Catalog, machine_profiles
) -> None:
    profile = machine_profiles["avx2"]

    def pairs(name: str) -> set[tuple[str, str]]:
        return {
            (slot.extension.name, slot.to_target)
            for slot in _slots(catalog, profile, name)
            if slot.type_tag == "si32"
            and slot.extension.name.startswith("clang_v")
            and slot.to_target is not None
        }

    clang_widths = {
        "clang_v128": 128,
        "clang_v256": 256,
        "clang_v512": 512,
        "clang_v128_bool": 128,
        "clang_v256_bool": 256,
        "clang_v512_bool": 512,
    }
    assert pairs("extract") == {
        (source, target)
        for source, source_width in clang_widths.items()
        for target, target_width in clang_widths.items()
        if target_width < source_width
    }
    assert pairs("insert") == {
        (source, target)
        for source, source_width in clang_widths.items()
        for target, target_width in clang_widths.items()
        if target_width > source_width
    }
    assert pairs("resize_down") == pairs("extract")
    assert pairs("resize_up_undef") == pairs("insert")
    assert pairs("resize_up_zero") == pairs("insert")
    assert pairs("concat") == {
        (source, target)
        for source, source_width in clang_widths.items()
        for target, target_width in clang_widths.items()
        if target_width == 2 * source_width
    }

    slot = next(
        slot
        for slot in _slots(catalog, profile, "extract")
        if slot.type_tag == "si32"
        and slot.extension.name == "clang_v512"
        and slot.to_target == "clang_v128"
    )
    assert slot.implementation.target_constraint is not None
    assert slot.implementation.target_constraint.family == "same_as"
    assert slot.implementation.target_constraint.width == "smaller_than"
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert lowered is not None
    assert "result[0] = data[start + 0]" in lowered.body_text
    assert "result[3] = data[start + 3]" in lowered.body_text
    assert "std::memcpy" not in lowered.body_text

    concat_slot = next(
        slot
        for slot in _slots(catalog, profile, "concat")
        if slot.type_tag == "si32"
        and slot.extension.name == "clang_v128"
        and slot.to_target == "clang_v256"
    )
    assert concat_slot.implementation.target_constraint is not None
    assert concat_slot.implementation.target_constraint.width == "twice_as_wide"


def test_clang_overlay_has_authored_coverage_for_every_supported_corpus_slot(
    catalog: Catalog, machine_profiles
) -> None:
    selector = Selector()
    profile = machine_profiles["icelake_rockerlake"]
    clang_extensions = {
        "clang_v128",
        "clang_v256",
        "clang_v512",
        "clang_v128_bool",
        "clang_v256_bool",
        "clang_v512_bool",
    }
    selected_names: set[str] = set()
    inherited: list[str] = []

    for name in sorted({primitive.name for primitive in catalog.primitives}):
        selection = selector.select_profile(catalog, profile, name, _ALL_ARITH_TYPES)
        for slot in selection.selected:
            if slot.extension.name not in clang_extensions:
                continue
            selected_names.add(name)
            if slot.implementation.extension not in clang_extensions:
                inherited.append(
                    f"{name}:{slot.primitive.signature}:{slot.extension.name}:"
                    f"{slot.type_tag}:{slot.to_target}<-{slot.implementation.extension}"
                )

    free_names = {
        primitive.name
        for primitive in catalog.primitives
        if (shape := parse_signature(primitive.signature)) is not None
        and DEFAULT_SUPPORT_POLICY.shape_is_free_function(shape)
    }
    assert inherited == []
    assert (
        {primitive.name for primitive in catalog.primitives} - selected_names
        == free_names
    )

    declaration_gaps: list[str] = []
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is not None and DEFAULT_SUPPORT_POLICY.shape_is_free_function(shape):
            continue
        applicable_types = {
            member
            for implementation in primitive.implementations
            for member in catalog.type_group_members(implementation.type_group)
            if member in _ALL_ARITH_TYPES
        }
        for extension_name in sorted(clang_extensions):
            for type_tag in sorted(applicable_types):
                targets = concrete_target_candidates(
                    catalog, primitive, extension_name, type_tag
                )
                if primitive.result_target is not None and not targets:
                    continue
                for target in targets:
                    ranked = selector.evaluate_candidates(
                        catalog,
                        profile,
                        primitive,
                        extension_name,
                        type_tag,
                        target,
                    ).ranked
                    if (
                        not ranked
                        or ranked[0].implementation.extension not in clang_extensions
                    ):
                        owner = ranked[0].implementation.extension if ranked else "missing"
                        declaration_gaps.append(
                            f"{primitive.name}:{primitive.signature}:{extension_name}:"
                            f"{type_tag}:{target}<-{owner}"
                        )
    assert declaration_gaps == []


def test_neg_selects_only_signed_and_floating_lane_types(
    catalog: Catalog,
    machine_profiles,
) -> None:
    selection = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "neg",
        _ALL_ARITH_TYPES,
        backend_id="cpp",
    )
    selected_types = {slot.type_tag for slot in selection.selected}

    assert selected_types == {"si8", "si16", "si32", "si64", "f32", "f64"}


def test_requirement_scoped_implementations_are_not_dead(catalog: Catalog) -> None:
    dead: list[str] = []
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            if not implementation.requirements:
                continue
            applicable = any(
                any(
                    (
                        clause.extension is None
                        or clause.extension == implementation.extension
                    )
                    and (
                        clause.type_group is None
                        or catalog.type_group_contains(clause.type_group, type_tag)
                    )
                    for clause in implementation.requirements
                )
                for type_tag in catalog.type_group_members(implementation.type_group)
            )
            if not applicable:
                dead.append(
                    f"{primitive.name}:{primitive.signature}:"
                    f"{implementation.extension}:{implementation.type_group}"
                )

    assert dead == []


@pytest.mark.parametrize(
    ("type_tag", "suffix"), [("si32", "epi32"), ("ui32", "epi32"), ("f32", "ps")]
)
def test_lower_add_avx2(catalog: Catalog, machine_profiles, type_tag, suffix) -> None:
    slots = _by_key(catalog, machine_profiles["avx2"], "add")
    slot = slots[(type_tag, "avx2")]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert cpp.extension_name == "avx2"
    assert cpp.body_text == f"return _mm256_add_{suffix}(left, right);"
    assert cpp.result_kind == "v"

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert rust.body_text == (
        f"unsafe {{ return core::arch::x86_64::_mm256_add_{suffix}(left, right); }}"
    )


@pytest.mark.parametrize(
    ("type_tag", "suffix"),
    [("ui16", "epi16"), ("ui32", "epi32"), ("ui64", "epi64")],
)
def test_mul_avx512_unsigned_uses_low_product_intrinsic(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
    suffix: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["icelake_rockerlake"],
            "mul",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.attributes.get("mask") is None
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == f"return _mm512_mullo_{suffix}(factor1, factor2);"
    assert rust is not None
    assert rust.body_text == (
        "unsafe { return "
        f"core::arch::x86_64::_mm512_mullo_{suffix}(factor1, factor2); }}"
    )


@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("sse2", "sse"),
        ("avx2", "avx2"),
        ("skylake", "avx512"),
    ],
)
def test_x86_byte_mul_composes_word_primitives_in_register(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "mul", ("ui8",))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    word_vec = f"tsl::simd<uint16_t, tsl::{extension}>"
    assert f"::tsl::mul<{word_vec}>" in cpp.body_text
    assert f"::tsl::shift_left<{word_vec}>" in cpp.body_text
    assert f"::tsl::shift_right<{word_vec}, false>" in cpp.body_text
    assert "_mullo_epi16" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("avx2", "avx2", "si32"),
        ("neon", "neon", "ui16"),
        ("wasm32-simd128", "wasm128", "f32"),
    ],
)
def test_insert_value_composes_masked_move(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "insert_value", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_mask" in lowered.body_text
        assert "mov" in lowered.body_text
        assert "set1" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_insert_value_array_assignment_is_backend_typed(
    catalog: Catalog,
    machine_profiles,
) -> None:
    rust_slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "insert_value",
            ("f32",),
            backend_id="rust",
        )
        .selected
        if selected.extension.name == "sse"
    )
    cpp_slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "insert_value",
            ("f32",),
            backend_id="cpp",
        )
        .selected
        if selected.extension.name == "sse"
    )

    rust = Lowerer().lower(
        rust_slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    cpp = Lowerer().lower(
        cpp_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert rust is not None
    assert cpp is not None
    assert "lanes[(Index) as usize] = value" in rust.body_text
    assert "lanes[Index] = value" in cpp.body_text
    assert "array<set>" not in rust.body_text
    assert "array<set>" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "expected_fragment"),
    [
        ("sse2", "sse", "ui32", "_mm_unpacklo_epi64"),
        ("sse2", "sse", "si64", "_mm_mul_epu32"),
        (
            "avx",
            "avx2",
            "ui16",
            "::tsl::extract<Vec, tsl::simd<uint16_t, tsl::sse>, 0>",
        ),
        ("avx2", "avx2", "si64", "_mm256_mul_epu32"),
        (
            "knl",
            "avx512",
            "ui16",
            "::tsl::extract<Vec, tsl::simd<uint16_t, tsl::sse>, 0>",
        ),
        ("knl", "avx512", "ui64", "_mm512_mul_epu32"),
    ],
)
def test_x86_wide_integer_mul_stays_in_registers(
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
        .select_profile(catalog, machine_profiles[profile], "mul", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert expected_fragment in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("primitive", "type_tag", "intrinsic"),
    [
        ("hadd", "ui64", "vaddvq_u64"),
        ("hmax", "si16", "vmaxvq_s16"),
        ("hmax", "f64", "vmaxvq_f64"),
        ("hmin", "ui32", "vminvq_u32"),
    ],
)
def test_neon_horizontal_reductions_use_across_vector_intrinsics(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.attributes.get("mask") is None
        and len(selected.primitive.parameters) == 1
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == f"return {intrinsic}(vec);"
    assert rust is not None
    assert rust.body_text == (
        f"unsafe {{ return core::arch::aarch64::{intrinsic}(vec); }}"
    )


@pytest.mark.parametrize(
    ("primitive", "type_tag"),
    [
        ("hmax", "si64"),
        ("hmax", "ui64"),
        ("hmin", "si64"),
        ("hmin", "ui64"),
    ],
)
def test_neon_horizontal_64_composes_two_lane_extractions(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.attributes.get("mask") is None
        and len(selected.primitive.parameters) == 1
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "to_array" not in cpp.body_text
    assert cpp.body_text.count("extract_value") == 2
    assert "vgetq_lane" not in cpp.body_text
    assert f"::tsl::{primitive[1:]}<tsl::simd" in cpp.body_text


@pytest.mark.parametrize(
    ("primitive", "profile", "extension", "type_tag", "intrinsic"),
    [
        ("max", "sse2", "sse", "ui8", "_mm_max_epu8"),
        ("min", "sse2", "sse", "si16", "_mm_min_epi16"),
        ("max", "avx2", "avx2", "si8", "_mm256_max_epi8"),
        ("min", "skylake", "avx512", "ui64", "_mm512_min_epu64"),
        ("max", "neon", "neon", "ui32", "vmaxq_u32"),
        ("min", "wasm32-simd128", "wasm128", "si16", "wasm_i16x8_min"),
    ],
)
def test_integer_minmax_prefers_exact_isa_intrinsic(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert intrinsic in cpp.body_text
    assert "::tsl::less_than" not in cpp.body_text
    assert "::tsl::select" not in cpp.body_text


@pytest.mark.parametrize("primitive", ["max", "min"])
def test_float_minmax_keeps_contract_preserving_compare_blend(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("f32",))
        .selected
        if selected.extension.name == "avx2"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::less_than<Vec>" in cpp.body_text
    assert "::tsl::select<Vec>" in cpp.body_text


@pytest.mark.parametrize(
    ("type_tag", "intrinsics"),
    [
        ("si16", ("vcntq_u8", "vpaddlq_u8")),
        ("ui32", ("vcntq_u8", "vpaddlq_u8", "vpaddlq_u16")),
        (
            "si64",
            ("vcntq_u8", "vpaddlq_u8", "vpaddlq_u16", "vpaddlq_u32"),
        ),
    ],
)
def test_neon_popcnt_uses_widening_pairwise_intrinsics(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
    intrinsics: tuple[str, ...],
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "popcnt", (type_tag,))
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
        assert all(intrinsic in lowered.body_text for intrinsic in intrinsics)


@pytest.mark.parametrize(
    ("type_tag", "pairwise_steps"),
    [("ui16", 1), ("si32", 2), ("ui64", 2)],
)
def test_wasm_popcnt_uses_unsigned_pairwise_widening(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
    pairwise_steps: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "popcnt",
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
        assert lowered.body_text.count("extadd_pairwise") == pairwise_steps
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        if type_tag == "ui64":
            assert "shift_right" in lowered.body_text
            assert "binary_and" in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "si16"),
        ("avx2", "avx2", "ui64"),
        ("knl", "avx512", "ui32"),
    ],
)
def test_x86_popcnt_without_vpopcnt_uses_vector_swar(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "popcnt", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "shift_right" in lowered.body_text
        assert "binary_and" in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("avx", "sse", "si8"),
        ("avx2", "avx2", "ui8"),
    ],
)
def test_x86_byte_popcnt_uses_ssse3_nibble_lookup(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "popcnt", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.attributes.get("mask") is None
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "shuffle_epi8" in lowered.body_text


def test_sse2_byte_popcnt_uses_word_swar_without_ssse3(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sse2"], "popcnt", ("ui8",))
        .selected
        if selected.extension.name == "sse"
        and selected.primitive.attributes.get("mask") is None
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "tsl::simd<uint16_t, tsl::sse>" in cpp.body_text
    assert "::tsl::shift_right<tsl::simd<uint16_t, tsl::sse>, false>" in cpp.body_text
    assert "::tsl::to_array<Vec>(data)" not in cpp.body_text
    assert "shuffle_epi8" not in cpp.body_text


def test_avx_popcnt_composes_two_sse_halves(
    catalog: Catalog,
    machine_profiles,
) -> None:
    for type_tag in ("si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64"):
        slot = next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["avx"], "popcnt", (type_tag,))
            .selected
            if selected.extension.name == "avx2"
            and selected.primitive.attributes.get("mask") is None
        )
        cpp = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, "cpp")
        ).specialization

        assert cpp is not None
        assert cpp.body_text.count("::tsl::extract<Vec") == 2
        assert "::tsl::popcnt<tsl::simd<" in cpp.body_text
        assert cpp.body_text.count("::tsl::insert<") == 2
        assert "_mm256_" not in cpp.body_text
        assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("avx2", "avx2", "si32"),
        ("skylake", "avx512", "f64"),
        ("neon", "neon", "f32"),
        ("wasm32-simd128", "wasm128", "ui16"),
    ],
)
def test_custom_sequence_composes_sequence_scale_and_offset(
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
            catalog, machine_profiles[profile], "custom_sequence", (type_tag,)
        )
        .selected
        if selected.extension.name == extension
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::sequence<Vec>()" in cpp.body_text
    assert "::tsl::mul<Vec>" in cpp.body_text
    assert "::tsl::add<Vec>" in cpp.body_text
    assert cpp.body_text.count("::tsl::set1<Vec>") == 2
    assert "to_array" not in cpp.body_text


def test_avx_integer_custom_sequence_keeps_additive_array_fallback(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["avx"], "custom_sequence", ("si32",)
        )
        .selected
        if selected.extension.name == "avx2"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert slot.required_features == frozenset({"avx"})
    assert cpp is not None
    assert "::tsl::to_array<Vec>" in cpp.body_text
    assert "::tsl::from_array<Vec>" in cpp.body_text
    assert "::tsl::sequence<Vec>" not in cpp.body_text


@pytest.mark.parametrize("primitive", ["allocate", "allocate_aligned", "deallocate"])
def test_free_functions_keep_profile_owner_out_of_compiler_overlay(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    selected = Selector().select_profile(
        catalog, machine_profiles["skylake"], primitive, ("si32",)
    ).selected

    assert tuple(
        (slot.extension.name, slot.type_tag, slot.to_target)
        for slot in selected
    ) == (("avx2_vl", "ptr", None),)
