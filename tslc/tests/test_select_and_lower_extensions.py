"""Extension-focused selection and lowering regressions."""

from __future__ import annotations

import pytest

from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.support_policy_views import concrete_target_candidates

_TYPES = ("si32", "ui32", "f32", "f64")
_ALL_ARITH_TYPES = (
    "si8",
    "ui8",
    "si16",
    "ui16",
    "si32",
    "ui32",
    "si64",
    "ui64",
    "f32",
    "f64",
)


def _slots(catalog, profile, primitive):
    return Selector().select_profile(
        catalog, profile, primitive, _TYPES, backend_id="cpp"
    ).selected


def _by_key(catalog, profile, primitive):
    result = {}
    for slot in _slots(catalog, profile, primitive):
        if slot.primitive.attributes.get("mask") is not None:
            continue
        key = (slot.type_tag, slot.extension.name)
        current = result.get(key)
        if current is None or len(slot.primitive.parameters) < len(
            current.primitive.parameters
        ):
            result[key] = slot
    return result


def _assert_x86_shift_register_path(cpp, expected_fragment: str) -> None:
    assert cpp is not None
    assert expected_fragment in cpp.body_text
    if expected_fragment == "::tsl::extract<Vec":
        assert "::tsl::insert<" in cpp.body_text
        assert "_mm" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


def _wasm_slot(catalog: Catalog, machine_profiles, primitive: str, type_tag: str):
    return next(
        slot
        for slot in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            primitive,
            (type_tag,),
            backend_id="cpp",
        )
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.attributes.get("mask") is None
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
    assert "::tsl::blend" not in cpp.body_text


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
    assert "::tsl::blend<Vec>" in cpp.body_text


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

    assert selected
    assert {slot.extension.name for slot in selected} == {"avx2_vl"}


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "ui64"),
        ("avx2", "avx2", "ui16"),
        ("skylake", "avx2_vl", "ui32"),
        ("neon", "neon", "f32"),
        ("wasm32-simd128", "wasm128", "ui8"),
    ],
)
def test_masked_bitwise_horizontal_reductions_compose_masked_vectors(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    extension: str,
    type_tag: str,
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
    assert "::tsl::to_vector<Vec>(mask)" in cpp.body_text
    assert f"::tsl::{primitive}<Vec>" in cpp.body_text
    assert "to_array" not in cpp.body_text
    if primitive == "hand":
        assert "::tsl::to_integral<Vec>(mask)" in cpp.body_text
        assert "::tsl::inv<Vec>(mask_vector)" in cpp.body_text
        assert "::tsl::binary_or<Vec>" in cpp.body_text
    else:
        assert "::tsl::binary_and<Vec>(mask_vector, vec)" in cpp.body_text


@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_sve_masked_bitwise_horizontal_uses_semantic_empty_test(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "hand",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.signature == "s:=(m,v)"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "mask_population_count" in lowered.body_text
    assert "svptest_any" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag"),
    [
        ("sse2", "sse", "si64"),
        ("avx2", "avx2", "ui64"),
        ("skylake", "avx2_vl", "si64"),
        ("neon", "neon", "ui8"),
        ("wasm32-simd128", "wasm128", "ui16"),
    ],
)
def test_masked_hadd_composes_masked_vector_with_unmasked_reduction(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "hadd", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "::tsl::to_vector<Vec>(mask)" in cpp.body_text
    assert "::tsl::binary_and<Vec>(mask_vector, vec)" in cpp.body_text
    assert "::tsl::hadd<Vec>" in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "sum_intrinsic"),
    [
        ("sse2", "sse", "si8", "_mm_sad_epu8"),
        ("sse2", "sse", "ui16", "_mm_madd_epi16"),
        ("skylake", "avx512", "ui8", "_mm512_sad_epu8"),
        ("skylake", "avx512", "si16", "_mm512_madd_epi16"),
    ],
)
def test_x86_small_integer_hadd_reduces_in_register(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    sum_intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "hadd", (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert sum_intrinsic in cpp.body_text
    assert "to_array" not in cpp.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "si16", "si32", "ui64", "f32", "f64"])
def test_avx2_hadd_composes_from_half_vector_primitives(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "hadd", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text.count("::tsl::extract<Vec") == 2
    assert "::tsl::add<tsl::simd<" in cpp.body_text
    assert "::tsl::hadd<tsl::simd<" in cpp.body_text
    assert "_mm256_" not in cpp.body_text


def test_knl_small_integer_hadd_composes_from_sse_quarters(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["knl"], "hadd", ("ui8",))
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == "s:=v"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text.count("::tsl::extract<Vec") == 4
    assert "::tsl::add<tsl::simd<uint8_t, tsl::sse>>" in cpp.body_text
    assert "::tsl::hadd<tsl::simd<uint8_t, tsl::sse>>" in cpp.body_text
    assert "_mm512_" not in cpp.body_text


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
        and selected.primitive.attributes.get("mask") is None
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
