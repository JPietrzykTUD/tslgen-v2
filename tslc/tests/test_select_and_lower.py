"""Profile-aware selection + lowering into specializations."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.backend.translation import create_backend_dialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    Extension,
    GenericParam,
    GenericParamBaseWidthConstraint,
    Implementation,
    Primitive,
)
from tslc.catalog.target_families import ProfileFamilyCapability, TargetFamilyCatalog
from tslc.lower import lowerer as lowerer_module
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import Lowerer
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
from tslc.select.selector import SelectedImplementation, Selector, SimdTypeBaseBinding

_TYPES = ("si32", "ui32", "f32", "f64")


def _scalar_target_families() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar"}),
        universal_extension_families=frozenset({"scalar"}),
        profile_families={"generic": ProfileFamilyCapability("generic")},
    )


def _slots(catalog, profile, primitive):
    return Selector().select_profile(catalog, profile, primitive, _TYPES).selected


def _by_key(catalog, profile, primitive):
    # The UNMASKED specs keyed by (type, ext). A dual name now also selects masked variants
    # (same key until the render `_mask`/`_maskz` rename), so filter them out — these tests
    # exercise the unmasked overload set.
    return {
        (s.type_tag, s.extension.name): s
        for s in _slots(catalog, profile, primitive)
        if s.primitive.attributes.get("mask") is None
    }


def test_lowerer_keeps_target_vector_resolution_boundary() -> None:
    assert lowerer_module.Lowerer.__module__ == "tslc.lower.lowerer"
    assert lowerer_module.TargetVector is TargetVector
    assert TargetVector.__module__ == "tslc.lower.target_vectors"
    assert resolve_target_vector.__module__ == "tslc.lower.target_vectors"


def test_unknown_primitive_is_error(catalog: Catalog, machine_profiles) -> None:
    result = Selector().select_profile(
        catalog, machine_profiles["avx2"], "does_not_exist", _TYPES
    )
    assert result.selected == ()
    assert result.diagnostics[0].code == "TSL-SELECT-UNKNOWN-PRIMITIVE"


def test_profile_reachability(catalog: Catalog, machine_profiles) -> None:
    # scalar profile: the scalar extension plus the always-available `generic` portable vector
    # (a base extension with no activation features). Target-family data routes
    # scalar/generic_like to every profile while keeping ISA-specific and non-emitted
    # families out.
    scalar = {s.extension.name for s in _slots(catalog, machine_profiles["scalar"], "add")}
    assert scalar == {"scalar", "generic"}

    # avx profile: avx2 integer add needs the avx2 flag (absent) -> falls to sse;
    # but avx2 float add only needs `avx`, so it IS present.
    avx = _by_key(catalog, machine_profiles["avx"], "add")
    assert ("si32", "avx2") not in avx
    assert ("si32", "sse") in avx
    assert ("f32", "avx2") in avx

    # avx2 profile: sse + avx2 (and scalar) all present; _vl is not active here.
    avx2 = {s.extension.name for s in _slots(catalog, machine_profiles["avx2"], "add")}
    assert {"scalar", "sse", "avx2"} <= avx2
    assert "avx2_vl" not in avx2

    # skylake: avx512vl present -> _vl supersedes base avx2/sse, plus avx512.
    sky = {s.extension.name for s in _slots(catalog, machine_profiles["skylake"], "add")}
    assert {"avx2_vl", "sse_vl", "avx512"} <= sky
    assert "avx2" not in sky and "sse" not in sky

    # neon is the fixed-width ARM substrate admitted in this slice; scalable SVE remains deferred.
    neon = {s.extension.name for s in _slots(catalog, machine_profiles["neon"], "add")}
    assert "neon" in neon
    assert "sve" not in neon

    wasm = {
        s.extension.name
        for s in _slots(catalog, machine_profiles["wasm32-simd128"], "add")
    }
    assert {"scalar", "generic", "wasm128"} <= wasm
    assert "neon" not in wasm
    assert "avx2" not in wasm


def test_oneapi_fpga_is_not_emitted_without_compile_mode(
    catalog: Catalog, machine_profiles
) -> None:
    for profile in machine_profiles.values():
        if "oneapi_fpga" in profile.compile_modes:
            continue

        emitted = {s.extension.name for s in _slots(catalog, profile, "add")}

        assert "oneapi_fpga" not in emitted
        assert "oneapi_fpga_rtl" not in emitted


def test_oneapi_fpga_is_compile_mode_opt_in(catalog: Catalog) -> None:
    profile = MachineProfile(
        name="fpga-dev",
        family="generic",
        features=frozenset(),
        compile_modes=frozenset({"oneapi_fpga"}),
        alternatives={},
    )

    emitted = {s.extension.name for s in _slots(catalog, profile, "add")}

    assert {"generic", "oneapi_fpga"} <= emitted


def test_type_group_specificity_resolves_hadd(catalog: Catalog, machine_profiles) -> None:
    # hadd avx2 has both an f64-specific body and an arith-general body; the
    # specific one must win at generation time.
    slots = _by_key(catalog, machine_profiles["avx2"], "hadd")
    chosen = slots[("f64", "avx2")]
    assert chosen.implementation.type_group == "f64"


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
            "unsafe { return set1::<Self>((0) as f32); }",
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
    ("primitive", "type_tag", "needle"),
    (
        ("div", "si32", "::tsl::div<tsl::simd<int32_t, tsl::generic<4>>>"),
        ("mod", "si32", "::tsl::mod<tsl::simd<int32_t, tsl::generic<4>>>"),
        ("lzc", "ui32", "::tsl::lzc_scalar<tsl::simd<uint32_t, tsl::scalar>>"),
    ),
)
def test_lower_wasm128_expanded_bridge_primitives(
    catalog: Catalog,
    machine_profiles,
    primitive,
    type_tag,
    needle,
) -> None:
    slot = _wasm_slot(catalog, machine_profiles, primitive, type_tag)

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    if primitive != "lzc":
        assert "tsl::generic" in cpp.body_text
    assert needle in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    if primitive != "lzc":
        assert "Generic" in rust.body_text


@pytest.mark.parametrize(
    ("primitive", "type_tag", "cpp_needles", "rust_needles"),
    (
        (
            "mul",
            "si8",
            ("wasm_u16x8_extmul_low_u8x16", "wasm_u8x16_narrow_i16x8"),
            ("u16x8_extmul_low_u8x16", "u8x16_narrow_i16x8"),
        ),
        (
            "max",
            "si32",
            ("::tsl::blend<Vec>", "::tsl::less_than<Vec>"),
            ("blend::<Self>", "less_than::<Self>"),
        ),
    ),
)
def test_lower_wasm128_composed_primitives_avoid_generic_bridge(
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

    imm = Lowerer().lower(slots["v:=(v,sImm)"], catalog, cpp).specialization
    scalar = Lowerer().lower(slots["v:=(v,s)"], catalog, cpp).specialization
    vector = Lowerer().lower(slots["v:=(v,v)"], catalog, cpp).specialization

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
    assert "generic_shift" in left_vector.body_text
    assert "::tsl::to_array<Vec>(shift)" in left_vector.body_text

    assert imm is not None
    assert "::tsl::shift_right<Vec, PreserveSign>" in imm.body_text
    assert "static_cast<int32_t>(shift)" in imm.body_text
    assert "::tsl::to_array<Vec>(shift)" not in imm.body_text

    assert scalar is not None
    assert "wasm_i32x4_shr(data, static_cast<uint32_t>(shift))" in scalar.body_text
    assert "wasm_u32x4_shr(udata, static_cast<uint32_t>(shift))" in scalar.body_text
    assert "generic_shift" not in scalar.body_text

    assert vector is not None
    assert "generic_shift" in vector.body_text
    assert "::tsl::to_array<Vec>(shift)" in vector.body_text


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


def test_backend_value_query_uses_backend_translation_template(
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
    assert "_MM_FROUND_TO_ZERO" in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert "core::arch::x86_64::_MM_FROUND_TO_ZERO" in rust.body_text


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


def test_sse41_cast_fast_path_wins_over_portable_fallback(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx"], "cast", ("f32",))
        .selected
        if s.extension.name == "sse" and s.type_tag == "f32" and s.to_target == "si32"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert "_mm_round_ps" in cpp.body_text
    assert "_mm_cvtps_epi32" in cpp.body_text


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
    assert "_mm_cmpeq_epi64" in cpp_f64.body_text


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
        self.supports_sized_vector_lane_expressions = (
            inner.supports_sized_vector_lane_expressions
        )
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
    # multi-statement body: var declarations + assignment + scalar return
    assert "auto const lo = _mm256_extractf128_pd(vec, 0);" in cpp.body_text
    assert "return _mm_cvtsd_f64(temp);" in cpp.body_text


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
