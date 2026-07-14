"""Backend-heavy selection and lowering regressions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.registry import create_backend_dialect
from tslc.backend.rust import RustBackend
from tslc.catalog.model import (
    Catalog,
    Extension,
    GenericParam,
    GenericParamBaseWidthConstraint,
    Implementation,
    Primitive,
)
from tslc.catalog.target_families import (
    ExtensionFamilyCapability,
    ProfileFamilyCapability,
    TargetFamilyCatalog,
)
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import (
    SelectedImplementation,
    Selector,
    SimdTypeBaseBinding,
)

_TYPES = ("si32", "ui32", "f32", "f64")


def _scalar_target_families() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar"}),
        universal_extension_families=frozenset({"scalar"}),
        extension_families={
            "scalar": ExtensionFamilyCapability(
                "scalar",
                implementation_fallback=True,
                requires_declared_vector_register=False,
            )
        },
        profile_families={"generic": ProfileFamilyCapability("generic")},
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


def _wasm_slot(catalog: Catalog, machine_profiles, primitive: str, type_tag: str):
    return next(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["wasm32-simd128"], primitive, (type_tag,))
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.attributes.get("mask") is None
    )


def _wasm_unmasked_slots(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
):
    return tuple(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["wasm32-simd128"], primitive, (type_tag,))
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.attributes.get("mask") is None
    )


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
            "return wasm_f32x4_div(divident, divisor);",
            "unsafe { return core::arch::wasm32::f32x4_div(divident, divisor); }",
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


def test_lower_scalar_add_has_no_unsafe(catalog: Catalog, machine_profiles) -> None:
    slot = _by_key(catalog, machine_profiles["scalar"], "add")[("si32", "scalar")]
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp.base_type_spelling == "int32_t"
    # `op<add>` lowers per backend: C++ keeps wrapping `+`, Rust uses the wrapping lane op.
    assert cpp.body_text == "return (left + right);"
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust.base_type_spelling == "i32"
    assert rust.body_text == "return left.tsl_add(right);"


def test_lower_to_vector_lane_bitmask_identity_is_native(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "to_vector", ("si64",))
        .selected
    }
    slot = slots[("si64", "avx2")]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return mask;"
    assert cpp.implementation_state is ImplementationState.NATIVE


def test_oneapi_exact_lane_mask_policy_lowers_lane_bitmask_operations(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["skylake-oneapi"], "less_than", ("si32",))
        .selected
        if s.primitive.attributes.get("mask") is None
    }
    slot = slots[("si32", "oneapi_fpga")]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::mask_type result = 0;" in cpp.body_text
    assert "result |= (1ull << i);" in cpp.body_text
    assert "typename Vec::register_type result" not in cpp.body_text


def test_rust_sse_float_nequal_uses_sse_cmpneq_intrinsic(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = _by_key(catalog, machine_profiles["sse"], "nequal")
    slot = slots[("f32", "sse")]

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert rust is not None
    assert "core::arch::x86_64::_mm_cmpneq_ps(left, right)" in rust.body_text
    assert "core::arch::x86_64::_mm_cmp_ps" not in rust.body_text


@pytest.mark.parametrize("backend_id", ("cpp", "rust"))
def test_fixed_non_x86_extension_requires_register_metadata(backend_id: str) -> None:
    ext = Extension(
        name="tiny_arm",
        isa_name="tiny_arm",
        family="arm",
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": True, "rust": True},
        vector_bits=128,
    )
    impl = Implementation(
        ("tiny_arm", "ints"),
        "tiny_arm",
        "ints",
        "complete(data);",
        source_order=0,
    )
    prim = Primitive(
        name="metadata_guard",
        signature="v:=v",
        parameters=("data",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"tiny_arm": ext},
        type_spellings={
            "cpp": {"s32": "int32_t"},
            "rust": {"s32": "i32"},
        },
        translations={
            "cpp": {"complete": "return {value}"},
            "rust": {"complete": "return {value}"},
        },
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    unsupported_slot = replace(
        slot,
        extension=replace(ext, backend_supported={}),
    )
    unsupported = Lowerer().lower(
        unsupported_slot,
        catalog,
        create_backend_dialect(catalog, backend_id),
    )

    assert unsupported.specialization is None
    assert [diagnostic.code for diagnostic in unsupported.diagnostics] == [
        "TSL-LOWER-BACKEND-UNSUPPORTED"
    ]

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.specialization is None
    assert [diagnostic.code for diagnostic in lowered.diagnostics] == [
        "TSL-LOWER-NO-REGISTER-TYPE"
    ]
    assert "tiny_arm" in lowered.diagnostics[0].message


def test_avx_truncating_cast_uses_exact_conversion_intrinsic(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", ("f32",))
        .selected
        if s.extension.name == "avx2" and s.to_target == "si32"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert "_mm256_cvttps_epi32" in cpp.body_text
    assert "_MM_FROUND_TO_ZERO" not in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert "core::arch::x86_64::_mm256_cvttps_epi32" in rust.body_text
    assert "_MM_FROUND_TO_ZERO" not in rust.body_text


@pytest.mark.parametrize(
    ("backend_id", "expected"),
    (
        ("cpp", "return IndexVec::lane_count_v;"),
        ("rust", "return IndexVec::ELEMENT_COUNT;"),
    ),
)
def test_simd_type_generic_param_queries_lower_from_authored_name(
    catalog: Catalog,
    backend_id: str,
    expected: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        "complete(value(generic::length(IndexVec)));",
        source_order=0,
    )
    primitive = Primitive(
        name="index_lane_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert tuple(
        (param.name, param.bounds, param.base_type_constraints)
        for param in lowered.specialization.type_params
    ) == (("IndexVec", (), ("?i32",)),)
    assert lowered.specialization.body_text == expected


@pytest.mark.parametrize("backend_id", ("cpp", "rust"))
def test_bound_simd_type_generic_base_folds_generation_condition(
    catalog: Catalog,
    backend_id: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        (
            "complete(value(select("
            "value(type::same_size(type(base::in), type(base::generic(IndexVec)))), "
            "\"1\", \"0\")));"
        ),
        source_order=0,
    )
    primitive = Primitive(
        name="index_base_width_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
                specialize_base=True,
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
        simd_type_base_bindings=(SimdTypeBaseBinding("IndexVec", "ui32"),),
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert lowered.specialization.body_text == "return 1;"
    expected_spelling = "uint32_t" if backend_id == "cpp" else "u32"
    assert tuple(
        (
            param.name,
            param.specialize_base,
            param.base_type_binding,
            param.base_type_binding_spelling,
        )
        for param in lowered.specialization.type_params
    ) == (("IndexVec", True, "ui32", expected_spelling),)


@pytest.mark.parametrize(
    ("backend_id", "expected"),
    (
        (
            "cpp",
            "return ((left == right) ? (static_cast<int32_t>(0)) : (left));",
        ),
        (
            "rust",
            "return if left == right { (0) as i32 } else { left };",
        ),
    ),
)
def test_select_expr_lowers_to_backend_conditional_expression(
    catalog: Catalog,
    backend_id: str,
    expected: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        (
            "complete(select_expr("
            "left == right, "
            "cast<static>(base::in, 0), "
            "left"
            "));"
        ),
        source_order=0,
    )
    primitive = Primitive(
        name="select_expr_probe",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        attribute_keys=(),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert lowered.specialization.body_text == expected


@pytest.mark.parametrize(
    ("backend_id", "expected_call"),
    (
        ("cpp", "to_array<IndexVec>(index)"),
        ("rust", "to_array::<IndexVec>(index)"),
    ),
)
def test_simd_type_generic_param_can_target_primitive_call(
    catalog: Catalog,
    backend_id: str,
    expected_call: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        """
        var<infer>(idx_array, call<primitive=to_array[IndexVec]>(index));
        complete(idx_array[0]);
        """,
        source_order=0,
    )
    primitive = Primitive(
        name="index_array_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert expected_call in lowered.specialization.body_text
    assert tuple(param.name for param in lowered.specialization.type_params) == ("IndexVec",)


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
        .select_profile(catalog, machine_profiles["avx2"], "cast", ("f32",))
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
        for primitive in ("equal", "shift_right", "blend", "set1"):
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


def test_runtime_array_var_lowers_sve_scratch_storage(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve"],
            "gather_narrow_partial",
            ("ui16",),
        )
        .selected
        if s.extension.name == "sve"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert (
        "std::vector<typename IndicesType::base_type> idx_array_storage"
        in cpp.body_text
    )
    assert "std::vector<uint16_t> result_storage" in cpp.body_text
    assert "auto *idx_array = idx_array_storage.data();" in cpp.body_text
    assert "auto *result = result_storage.data();" in cpp.body_text
    assert "std::malloc" not in cpp.body_text
    assert "std::free" not in cpp.body_text


@pytest.mark.parametrize("masked", [False, True])
def test_sve_gather_prefers_native_indexed_load_with_runtime_fallback(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "gather", ("ui32",))
        .selected
        if selected.extension.name == "sve"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svld1_gather_index" in lowered.body_text
    assert "if constexpr (scale == 4)" in lowered.body_text
    assert "IndicesType::extension_type" in lowered.body_text
    assert "index_lanes" in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert ("active_array_storage" in lowered.body_text) is masked


def test_sve_byte_gather_keeps_runtime_fallback_without_invalid_native_load(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "gather", ("ui8",))
        .selected
        if selected.extension.name == "sve"
        and "mask" not in selected.primitive.attribute_keys
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svld1_gather_index" not in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert "result_storage" in lowered.body_text


@pytest.mark.parametrize("masked", [False, True])
def test_sve_scatter_uses_runtime_index_and_predicate_storage(
    catalog: Catalog,
    machine_profiles,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "scatter", ("ui32",))
        .selected
        if selected.extension.name == "sve"
        and ("mask" in selected.primitive.attribute_keys) is masked
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "index_lanes" in lowered.body_text
    assert "idx_array_storage" in lowered.body_text
    assert "val_array_storage" in lowered.body_text
    assert ("active_array_storage" in lowered.body_text) is masked
    assert "svst1_scatter" not in lowered.body_text


def test_simd_type_base_specialization_expands_gather_narrow_slots(
    catalog: Catalog, machine_profiles
) -> None:
    slots = [
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "gather_narrow", ("ui16",))
        .selected
        if s.extension.name == "avx2"
    ]

    assert {
        tuple((binding.param_name, binding.base_tag) for binding in slot.simd_type_base_bindings)
        for slot in slots
    } == {
        (("IndicesType", "si32"),),
        (("IndicesType", "ui32"),),
        (("IndicesType", "si64"),),
        (("IndicesType", "ui64"),),
    }


def test_simd_type_base_width_constraint_filters_specialized_slots(
    catalog: Catalog, machine_profiles
) -> None:
    impl = Implementation(
        ("avx2", "arith"),
        "avx2",
        "arith",
        "complete(index);",
        source_order=0,
    )
    primitive = Primitive(
        name="wide_index_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32", "?i64"),
                specialize_base=True,
                base_width_constraints=(GenericParamBaseWidthConstraint(">="),),
            ),
        ),
        implementations=(impl,),
    )
    probe_catalog = Catalog(
        primitives=(*catalog.primitives, primitive),
        type_groups=catalog.type_groups,
        extensions=catalog.extensions,
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=catalog.target_families,
    )

    slots = Selector().select_profile(
        probe_catalog,
        machine_profiles["avx2"],
        "wide_index_probe",
        ("ui64",),
    ).selected

    assert {
        tuple((binding.param_name, binding.base_tag) for binding in slot.simd_type_base_bindings)
        for slot in slots
    } == {
        (("IndexVec", "si64"),),
        (("IndexVec", "ui64"),),
    }


def test_simd_type_base_width_constraint_rejects_unsatisfied_slots(
    catalog: Catalog, machine_profiles
) -> None:
    impl = Implementation(
        ("avx2", "arith"),
        "avx2",
        "arith",
        "complete(index);",
        source_order=0,
    )
    primitive = Primitive(
        name="too_narrow_index_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
                specialize_base=True,
                base_width_constraints=(GenericParamBaseWidthConstraint(">="),),
            ),
        ),
        implementations=(impl,),
    )
    probe_catalog = Catalog(
        primitives=(*catalog.primitives, primitive),
        type_groups=catalog.type_groups,
        extensions=catalog.extensions,
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=catalog.target_families,
    )

    slots = Selector().select_profile(
        probe_catalog,
        machine_profiles["avx2"],
        "too_narrow_index_probe",
        ("ui64",),
    ).selected

    assert slots == ()


def test_param_types_default_overrides_rendered_pointer_type(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "gather_narrow", ("ui16",))
        .selected
        if s.extension.name == "avx2"
    )
    lowerer = Lowerer()

    cpp = lowerer.lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust_dialect = create_backend_dialect(catalog, "rust")
    recording_syntax = _RecordingSyntax(rust_dialect.syntax)
    rust = lowerer.lower(
        slot, catalog, _RecordingDialect(rust_dialect, recording_syntax)
    ).specialization

    assert cpp is not None
    assert rust is not None
    assert cpp.type_params[0].base_type_binding in {"si32", "ui32", "si64", "ui64"}
    assert rust.type_params[0].base_type_binding == cpp.type_params[0].base_type_binding
    assert cpp.param_type_overrides[1] == "typename IndicesType::base_type const *"
    assert rust.param_type_overrides[1] == "*const IndicesType::BaseType"
    assert recording_syntax.param_type_calls == [(True, True)]
    cpp_source = CppBackend().render_primitive("gather_narrow", (cpp,))
    rust_source = RustBackend().render_primitive("gather_narrow", (rust,))
    assert "typename IndicesType::base_type const * index_ptr" in cpp_source
    assert "class IndicesTypeBaseKey = ::tsl::detail::base_type_dispatch_key_t" in cpp_source
    assert "::tsl::detail::base_" in cpp_source
    assert "index_ptr: *const IndicesType::BaseType" in rust_source
    assert "IndicesTypeBaseKey" in rust_source
    assert "<IndicesType::BaseType as BaseTypeDispatch>::Key" in rust_source


class _RecordingSyntax:
    def __init__(self, inner) -> None:  # noqa: ANN001
        self.inner = inner
        self.borrowed_call_arg_prefix = inner.borrowed_call_arg_prefix
        self.param_type_calls: list[tuple[bool, bool]] = []

    def frame_return(self, value):  # noqa: ANN001, ANN201
        return self.inner.frame_return(value)

    def render_call(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self.inner.render_call(*args, **kwargs)

    def render_pointer_cast(self, inner, *, is_const, expr):  # noqa: ANN001, ANN201
        return self.inner.render_pointer_cast(inner, is_const=is_const, expr=expr)

    def render_param_type(  # noqa: ANN001, ANN201
        self,
        value,
        *,
        is_pointer: bool = False,
        is_const: bool = False,
    ):
        self.param_type_calls.append((is_pointer, is_const))
        return self.inner.render_param_type(
            value,
            is_pointer=is_pointer,
            is_const=is_const,
        )

    def render_assume_aligned(self, expr, alignment):  # noqa: ANN001, ANN201
        return self.inner.render_assume_aligned(expr, alignment)

    def render_compile_switch(self, selector, arms):  # noqa: ANN001, ANN201
        return self.inner.render_compile_switch(selector, arms)

    def render_unsafe_block(self, body: str) -> str:
        return self.inner.render_unsafe_block(body)


class _RecordingDialect:
    def __init__(self, inner, syntax: _RecordingSyntax) -> None:  # noqa: ANN001
        self.backend_id = inner.backend_id
        self.types = inner.types
        self.intrinsics = inner.intrinsics
        self.templates = inner.templates
        self.syntax = syntax


def test_consumed_tsil_statement_terminators_render_once() -> None:
    ext = Extension(
        name="scalar",
        isa_name="scalar",
        family="scalar",
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("scalar", "ints"),
        "scalar",
        "ints",
        (
            "let<type>(Alias, type(base::in)); "
            "var<infer>(tmp, a); intrin<side_effect>(tmp); complete(tmp);"
        ),
        source_order=0,
    )
    prim = Primitive(
        name="semicolon_once",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"scalar": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={
            "cpp": {
                "complete": "return {value}",
                "var_infer": "auto {name} = {value};",
            }
        },
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "auto tmp = a; side_effect(tmp); return tmp;"
    assert ";;" not in cpp.body_text


def test_intrin_build_supports_explicit_prefix_and_suffix() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        'complete(intrin<foo, build[prefix="_custom_", suffix="bar"]>(a));',
        source_order=0,
    )
    prim = Primitive(
        name="explicit_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return _custom_foo_bar(a);"


def test_wasm_intrin_build_requires_lane_suffix_for_typed_ops() -> None:
    ext = Extension(
        name="wasm128",
        isa_name="wasm128",
        family="wasm",
        intrinsic_style="wasm",
        compose_prefix={"cpp": "wasm_"},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("wasm128", "ints"),
        "wasm128",
        "ints",
        "complete(intrin<add, build>(a, b));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_wasm_intrin_build",
        signature="v:=(v,v)",
        parameters=("a", "b"),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"wasm128": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-WASM-INTRIN-MISSING-LANE-SUFFIX"


def test_wasm_intrin_build_accepts_explicit_empty_suffix_for_v128_ops() -> None:
    ext = Extension(
        name="wasm128",
        isa_name="wasm128",
        family="wasm",
        intrinsic_style="wasm",
        compose_prefix={"cpp": "wasm_"},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("wasm128", "ints"),
        "wasm128",
        "ints",
        'complete(intrin<v128_load, build[suffix=""]>(a));',
        source_order=0,
    )
    prim = Primitive(
        name="wasm_v128_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"wasm128": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return wasm_v128_load(a);"


def test_intrin_build_suffix_and_infix_accept_type_values() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete("
        "intrin<foo, build[infix=base::signed_of(base::in), "
        'infix_sep="", suffix=base::signed_of(base::in)]>(a)'
        ");",
        source_order=0,
    )
    prim = Primitive(
        name="typed_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return _custom_fooepi32_epi32(a);"


def test_intrin_build_appends_literal_post_fragment() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": ""},
        compose_suffix_by_type={"si32": "s32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo, build[post=x]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="post_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return foo_s32_x(a);"


def test_intrin_build_prefix_remains_text_only() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo, build[prefix=base::in, suffix=base::in]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_prefix_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-UNRESOLVED-PREFIX"


def test_intrin_build_rejects_whitespace_separated_selector_terms() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo build[suffix=base::in]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_intrin_build_separator",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-UNSUPPORTED-INTRIN-SELECTOR"


def test_hadd_reduction_lowers_for_f64(catalog: Catalog, machine_profiles) -> None:
    slot = _by_key(catalog, machine_profiles["avx2"], "hadd")[("f64", "avx2")]
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert cpp.result_kind == "s"  # s:=v -> scalar result
    assert cpp.param_names == ("vec",)
    assert cpp.body_text.count("::tsl::extract<Vec") == 2
    assert "::tsl::add<tsl::simd<double, tsl::sse>>" in cpp.body_text
    assert "return ::tsl::hadd<tsl::simd<double, tsl::sse>>(folded);" in cpp.body_text


def test_ambiguous_specificity_warns(machine_profiles) -> None:
    # Two bodies on the same extension keyed to type-groups that are equally specific
    # (both 4 members) but incomparable — `si?` = {si8,si16,si32,si64} and
    # `idqword` = {si32,ui32,si64,ui64} both match `si32`, neither a subset of the other.
    # Cardinality ties them, so the pick falls to source order; the selector still chooses
    # a body (no failure) but emits a warning so the corpus author can disambiguate.
    ext = Extension(
        name="scalar", isa_name="scalar", family="scalar",
        compose_prefix={}, compose_suffix_by_type={},
    )
    prim = Primitive(
        name="amb", signature="v:=v", parameters=("a",), attribute_keys=(),
        implementations=(
            Implementation(("scalar", "si?"), "scalar", "si?", "complete(a);", source_order=0),
            Implementation(("scalar", "idqword"), "scalar", "idqword", "complete(a);", source_order=1),
        ),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={
            "si?": ("si8", "si16", "si32", "si64"),
            "idqword": ("si32", "ui32", "si64", "ui64"),
        },
        extensions={"scalar": ext},
        type_spellings={},
        translations={},
        target_families=_scalar_target_families(),
    )
    result = Selector().select_profile(catalog, machine_profiles["scalar"], "amb", ("si32",))
    assert [d.code for d in result.diagnostics] == ["TSL-SELECT-AMBIGUOUS-SPECIFICITY"]
    assert result.diagnostics[0].severity == "warning"
    # still resolves to one body (source-order tiebreak) — a warning, not a hard failure.
    assert len(result.selected) == 1
    assert result.selected[0].implementation.type_group == "si?"  # source_order 0 wins


def test_nested_specificity_does_not_warn(machine_profiles) -> None:
    # `?i32` ⊂ `si?` (nested, comparable): `?i32` is strictly more specific, so the pick is
    # unambiguous and no warning is emitted.
    ext = Extension(
        name="scalar", isa_name="scalar", family="scalar",
        compose_prefix={}, compose_suffix_by_type={},
    )
    prim = Primitive(
        name="amb2", signature="v:=v", parameters=("a",), attribute_keys=(),
        implementations=(
            Implementation(("scalar", "si?"), "scalar", "si?", "complete(a);", source_order=0),
            Implementation(("scalar", "?i32"), "scalar", "?i32", "complete(a);", source_order=1),
        ),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"si?": ("si8", "si16", "si32", "si64"), "?i32": ("si32", "ui32")},
        extensions={"scalar": ext},
        type_spellings={},
        translations={},
        target_families=_scalar_target_families(),
    )
    result = Selector().select_profile(catalog, machine_profiles["scalar"], "amb2", ("si32",))
    assert result.diagnostics == ()
    assert result.selected[0].implementation.type_group == "?i32"  # more specific (2 < 4)


def _generic_slots(catalog, machine_profiles, primitive, type_tag):
    return [
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, (type_tag,))
        .selected
        if s.extension.name == "generic"
        and s.type_tag == type_tag
        and s.primitive.attributes.get("mask") is None
    ]


def test_convert_up_monomorphizes_generic_over_size_bits(catalog, machine_profiles) -> None:
    # The generic (sized) extension declares `size_bits [128, 256, 512]` and convert_up's software
    # body opts into `unroll_variants`, so the generic slot fans out into one concrete-lane slot
    # per size (si32 -> 128/256/512 bits = 4/8/16 lanes), instead of one `LANES`-parametric slot.
    generic = _generic_slots(catalog, machine_profiles, "convert_up", "si32")
    assert generic, "generic convert_up should be selected (c1 wildcard)"
    assert {s.concrete_lanes for s in generic} == {4, 8, 16}
    assert all(s.concrete_lanes is not None for s in generic)


def test_add_not_monomorphized_on_generic(catalog, machine_profiles) -> None:
    # A lane-local primitive (no `unroll_variants`) stays a single `LANES`-parametric slot.
    generic = _generic_slots(catalog, machine_profiles, "add", "si32")
    assert len(generic) == 1
    assert generic[0].concrete_lanes is None


def test_monomorphized_convert_lowers_to_concrete_lanes(catalog, machine_profiles) -> None:
    # A monomorphized slot lowers to a concrete sized vector (numeric `lane_parameter`) on Rust —
    # the whole point: stable Rust can spell `Generic<8>` where it cannot spell `Generic<{LANES/2}>`.
    generic = _generic_slots(catalog, machine_profiles, "convert_up", "si32")
    slot = next(s for s in generic if s.concrete_lanes == 8)
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert rust.uses_sized_vector
    assert rust.lane_parameter == "8"  # concrete, not the symbolic "LANES"
