"""Profile-aware selection + lowering into specializations."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.backend.registry import create_backend_dialect
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
from tslc.catalog.signatures import parse_signature
from tslc.lower import lowerer as lowerer_module
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import Lowerer
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
from tslc.select.selector import SelectedImplementation, Selector, SimdTypeBaseBinding
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


def _scalar_target_families() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar"}),
        universal_extension_families=frozenset({"scalar"}),
        profile_families={"generic": ProfileFamilyCapability("generic")},
    )


def _slots(catalog, profile, primitive):
    return Selector().select_profile(catalog, profile, primitive, _TYPES).selected


def _by_key(catalog, profile, primitive):
    # The ordinary specs keyed by (type, ext). A dual source name can also select
    # masked-policy variants and explicit leading-mask overloads (same key until
    # emitted-name finalization), so prefer the declaration with fewer parameters.
    # Mask-consuming primitives such as to_integral remain visible when they are the
    # only declaration for the name.
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


def test_lowerer_keeps_target_vector_resolution_boundary() -> None:
    assert lowerer_module.Lowerer.__module__ == "tslc.lower.lowerer"
    assert lowerer_module.TargetVector is TargetVector
    assert TargetVector.__module__ == "tslc.lower.target_vectors"
    assert resolve_target_vector.__module__ == "tslc.lower.target_vectors"


def test_lowerer_catalog_facts_cache_is_owned_by_catalog_identity(
    catalog: Catalog,
) -> None:
    lowerer = Lowerer()
    first = lowerer._facts_for(catalog)
    equivalent_catalog = Catalog(
        primitives=catalog.primitives,
        type_groups=catalog.type_groups,
        extensions=catalog.extensions,
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=catalog.target_families,
    )

    assert lowerer._facts_for(catalog) is first
    assert lowerer._facts_for(equivalent_catalog) is not first
    assert lowerer._catalog_facts_catalog is equivalent_catalog


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
    assert scalar == {
        "scalar",
        "generic",
        "clang_v128",
        "clang_v256",
        "clang_v512",
    }

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
    # hadd avx2 has both an f?-specific body and an arith-general body; the
    # narrower floating-point group must win at generation time.
    slots = _by_key(catalog, machine_profiles["avx2"], "hadd")
    chosen = slots[("f64", "avx2")]
    assert chosen.implementation.type_group == "f?"


def test_clang_hadd_prefers_compiler_reduction_builtin(
    catalog: Catalog, machine_profiles
) -> None:
    slots = _by_key(catalog, machine_profiles["avx2"], "hadd")
    slot = slots[("si32", "clang_v256")]

    assert slot.fixed_fallback_extension is not None
    assert slot.fixed_fallback_extension.isa_name == "avx2"
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    )
    assert lowered.specialization is not None
    assert lowered.specialization.body_text == "return __builtin_reduce_add(vec);"
    assert lowered.specialization.call_dependency_origins == ()

    unsupported = slots[("si32", "clang_v512")]
    assert unsupported.fixed_fallback_extension is None
    wide = Lowerer().lower(
        unsupported, catalog, create_backend_dialect(catalog, "cpp")
    )
    assert wide.specialization is not None
    assert wide.specialization.body_text == "return __builtin_reduce_add(vec);"


def test_clang_float_hadd_uses_ordered_compiler_reduction(
    catalog: Catalog, machine_profiles
) -> None:
    slots = Selector().select_profile(
        catalog, machine_profiles["avx2"], "hadd", ("f32",)
    ).selected
    unmasked = next(
        slot
        for slot in slots
        if slot.extension.name == "clang_v256"
        and slot.primitive.signature == "s:=v"
    )
    masked = next(
        slot
        for slot in slots
        if slot.extension.name == "clang_v256"
        and slot.primitive.signature == "s:=(m,v)"
    )

    unmasked_cpp = Lowerer().lower(
        unmasked, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    masked_cpp = Lowerer().lower(
        masked, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert unmasked_cpp is not None
    assert "#if __has_builtin(__builtin_reduce_in_order_fadd)" in unmasked_cpp.body_text
    assert "__builtin_reduce_in_order_fadd(vec" in unmasked_cpp.body_text
    assert "vec[0]" in unmasked_cpp.body_text
    assert "for " not in unmasked_cpp.body_text
    assert "to_array" not in unmasked_cpp.body_text
    assert masked_cpp is not None
    assert "::tsl::binary_and<Vec>(mask_vector, vec)" in masked_cpp.body_text
    assert "::tsl::hadd<Vec>" in masked_cpp.body_text
    assert "to_array" not in masked_cpp.body_text


def test_clang_set_uses_native_vector_initializer(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "set", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::register_type{" in cpp.body_text
    assert "values[7]" in cpp.body_text
    assert "values[0]" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "::tsl::load" not in cpp.body_text


def _assert_x86_shift_register_path(cpp, expected_fragment: str) -> None:
    assert cpp is not None
    assert expected_fragment in cpp.body_text
    if expected_fragment == "::tsl::extract<Vec":
        assert "::tsl::insert<" in cpp.body_text
        assert "_mm" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "lanes"),
    [
        ("neon", "neon", 4),
        ("wasm32-simd128", "wasm128", 4),
    ],
)
def test_fixed_width_set_unrolls_insert_value_calls(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    lanes: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "set", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("insert_value") == lanes
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "values[3]" in lowered.body_text
        assert "values[0]" in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert "for " not in lowered.body_text


def test_clang_sequence_uses_native_vector_initializer(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "sequence", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::register_type{" in cpp.body_text
    assert "static_cast<uint32_t>(0)" in cpp.body_text
    assert "static_cast<uint32_t>(7)" in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "for (" not in cpp.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("neon", "neon"),
        ("wasm32-simd128", "wasm128"),
    ],
)
def test_fixed_width_sequence_unrolls_insert_value_calls(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
) -> None:
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
        assert lowered.body_text.count("insert_value") == 3
        assert "replace_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "::<i>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


def test_wasm_extract_value_uses_immediate_lane_intrinsic(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "extract_value",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "wasm128"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "i32x4_extract_lane" in lowered.body_text
        assert "Index" in lowered.body_text
        assert "::<Index>" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        if backend_id == "rust":
            assert "::<0>" in lowered.body_text
            assert "::<3>" in lowered.body_text
        else:
            assert "wasm_i32x4_extract_lane(a, 0)" in lowered.body_text
            assert "wasm_i32x4_extract_lane(a, 3)" in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "type_tag", "needle"),
    [
        ("sse", "f32", "cvtss_f32"),
        ("sse2", "ui8", "cvtsi128_si64"),
        ("sse2", "si16", "cvtsi128_si64"),
        ("sse2", "ui32", "cvtsi128_si64"),
        ("sse2", "si64", "cvtsi128_si64"),
        ("sse2", "f64", "cvtsd_f64"),
    ],
)
def test_sse_extract_value_stays_in_register(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    type_tag: str,
    needle: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == "sse"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert needle in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "store" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "chunk_count"),
    [
        ("avx", "avx2", 2),
        ("knl", "avx512", 4),
    ],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16", "f32", "f64"])
def test_wide_x86_extract_value_uses_register_chunks(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    chunk_count: int,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == chunk_count
        assert "_mm256_extract" not in lowered.body_text
        assert "_mm512_extract" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "store" not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "ui16", "f32", "f64"])
def test_wasm_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            "to_mask",
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
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "v128_load" not in lowered.body_text
        assert "and_values" not in lowered.body_text
        assert "replace_lane" in lowered.body_text
        if type_tag == "ui8":
            assert "convert_down" in lowered.body_text
            assert "binary_or" in lowered.body_text
            assert "narrow_i16x8" not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "ui16", "ui32", "ui64", "f32", "f64"])
def test_neon_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "neon"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert "vsetq_lane" in lowered.body_text


@pytest.mark.parametrize(
    ("type_tag", "evidence"),
    [
        ("ui8", "vaddv_u8"),
        ("ui16", "hadd"),
        ("ui32", "hadd"),
        ("ui64", "extract_value"),
        ("f32", "to_integral"),
        ("f64", "to_integral"),
    ],
)
def test_neon_to_integral_uses_native_mask_pack(
    catalog: Catalog, machine_profiles, type_tag: str, evidence: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == "neon"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "for " not in lowered.body_text
        assert evidence in lowered.body_text
        if type_tag == "ui64":
            assert "vgetq_lane" not in lowered.body_text


@pytest.mark.parametrize(
    ("type_tag", "intrinsic"),
    [
        ("ui16", "_mm256_set_epi16"),
        ("ui32", "_mm256_set_epi32"),
        ("ui64", "_mm256_set_epi64x"),
    ],
)
def test_avx2_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog, machine_profiles, type_tag: str, intrinsic: str
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
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert intrinsic in lowered.body_text
        if type_tag == "f64":
            assert "reinterpret" in lowered.body_text
            assert "castsi128_pd" not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "ui16"])
def test_avx_to_integral_uses_sse_half_width_composition(
    catalog: Catalog, machine_profiles, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx"], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == "avx2"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == 2
        assert "_mm256_extract" not in lowered.body_text
        assert lowered.body_text.count("to_integral") == 2
        assert "_mm_movemask_epi8" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "type_tag", "movemask"),
    [
        ("avx2", "avx2", "ui32", "movemask_ps"),
        ("avx2", "avx2", "ui64", "movemask_pd"),
        ("sse2", "sse", "ui32", "movemask_ps"),
        ("sse2", "sse", "ui64", "movemask_pd"),
    ],
)
def test_x86_integer_to_integral_uses_semantic_reinterpret(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
    movemask: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_integral", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "reinterpret" in lowered.body_text
        assert movemask in lowered.body_text
        assert "castsi" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension", "packs"),
    [
        ("avx2", "avx2", "_mm256_packs_epi16"),
        ("sse2", "sse", "_mm_packs_epi16"),
    ],
)
def test_x86_word_to_integral_uses_convert_down_and_byte_path(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    packs: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_integral", ("ui16",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "convert_down" in lowered.body_text
        assert "to_integral" in lowered.body_text
        assert packs not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hadd", "hand", "hor"])
@pytest.mark.parametrize("type_tag", ["ui8", "ui16"])
def test_knl_masked_small_reductions_use_sse_quarter_composition(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["knl"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == 4
        assert "_mm512_" not in lowered.body_text
        assert "to_mask" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui8", "si32", "f32", "f64"])
def test_clang_masked_extrema_unroll_direct_lane_access(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.signature == "s:=(m,v)"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "vec[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui8", "si32", "f32", "f64"])
def test_neon_masked_extrema_unroll_semantic_lane_extracts(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "vgetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_sve_masked_extrema_use_semantic_empty_mask_test(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["sve128"], primitive, (type_tag,)
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
    assert "to_integral" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("profile", ["sse2", "avx2", "knl"])
@pytest.mark.parametrize("type_tag", ["si8", "ui16", "si32", "ui64"])
def test_x86_masked_integer_extrema_avoid_array_fallback(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    type_tag: str,
) -> None:
    extension = {"sse2": "sse", "avx2": "avx2", "knl": "avx512"}[profile]
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text
        if profile == "knl" and type_tag in {"si32", "ui64"}:
            assert "mask_reduce" in lowered.body_text
        else:
            assert "blend" in lowered.body_text


@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("profile", ["sse2", "avx2"])
@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_x86_masked_float_extrema_unroll_native_lane_extracts(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    type_tag: str,
) -> None:
    extension = "sse" if profile == "sse2" else "avx2"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "shuffle" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["si8", "ui16", "si32", "ui64", "f32", "f64"])
def test_sve_extract_value_uses_semantic_singleton_lane_mask(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::set1<" in lowered.body_text
    assert "svlastb_" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text


def test_sve_runtime_lane_counts_use_typed_query(catalog: Catalog) -> None:
    offenders: list[str] = []
    typed_query_bodies = 0
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            bodies = [implementation.body_text]
            bodies.extend(variant.body_text for variant in implementation.variants)
            for body in bodies:
                if "value(generic::runtime_length(" in body:
                    typed_query_bodies += 1
                if "intrin<svcntb>" in body:
                    offenders.append(
                        f"{primitive.name}:{'/'.join(implementation.selector_path)}"
                    )

    assert typed_query_bodies > 0
    assert offenders == []


def test_sve_plain_load_store_intrinsics_stay_in_owning_primitives(
    catalog: Catalog,
) -> None:
    offenders: list[str] = []
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            bodies = [implementation.body_text]
            bodies.extend(variant.body_text for variant in implementation.variants)
            for body in bodies:
                has_plain_load = any(
                    token in body for token in ("intrin<svld1>", "intrin<svld1,")
                )
                has_plain_store = any(
                    token in body for token in ("intrin<svst1>", "intrin<svst1,")
                )
                if (has_plain_load and primitive.name != "load") or (
                    has_plain_store and primitive.name != "store"
                ):
                    offenders.append(
                        f"{primitive.name}:{'/'.join(implementation.selector_path)}"
                    )

    assert offenders == []


def test_clang_unpacked_mask_load_uses_vector_comparison(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "load_mask_repr", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.attributes["packed"] == "false"
        and selected.primitive.attributes["aligned"] == "false"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::load<" in lowered.body_text
    assert "::tsl::nequal<" in lowered.body_text
    assert "for " not in lowered.body_text
    assert "mask<set>" not in lowered.body_text


@pytest.mark.parametrize(
    ("packed", "semantic"),
    [("false", "nequal"), ("true", "mask_false")],
)
def test_sve_mask_load_uses_semantic_mask_operations(
    catalog: Catalog,
    machine_profiles,
    packed: str,
    semantic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "load_mask_repr",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.attributes["packed"] == packed
        and selected.primitive.attributes["aligned"] == "false"
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert semantic in lowered.body_text
    assert "svcmpne_n" not in lowered.body_text
    assert "svpfalse_b" not in lowered.body_text


def test_sve_packed_mask_store_uses_semantic_any_test(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "store_mask_repr",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.attributes["packed"] == "true"
        and selected.primitive.attributes["aligned"] == "false"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "mask_population_count" in lowered.body_text
    assert "mask_binary_and" in lowered.body_text
    assert "svptest_any" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["compress", "expand"])
def test_clang_compress_expand_use_direct_vector_lanes(
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


def test_clang_conflict_unrolls_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "conflict", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "data[1]" in lowered.body_text
    assert "data[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("wasm32-simd128", "wasm128"),
        ("neon", "neon"),
    ],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16", "ui32", "si64"])
def test_conflict_unrolls_semantic_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "conflict", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert "extract_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "vgetq_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["ui8", "si16", "ui32", "si64"])
def test_sve_conflict_accumulates_vector_matches_without_memory(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "conflict", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svlastb_" in lowered.body_text
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::greater_than<" in lowered.body_text
    assert "::tsl::mask_binary_and<" in lowered.body_text
    assert "::tsl::binary_or_mask<" in lowered.body_text
    assert "::tsl::set1<" in lowered.body_text
    assert "svindex_" not in lowered.body_text
    assert "svcmpeq_n_" not in lowered.body_text
    assert "svcmpgt_n_" not in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svand_b_z" not in lowered.body_text
    assert "svorr_n_" not in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text


def test_sve_insert_value_uses_semantic_singleton_lane_mask(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["sve128"], "insert_value", ("ui32",)
        )
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::mov_mask<" in lowered.body_text
    assert "imask_type" not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "type_tag", "evidence"),
    [
        ("compress", "ui8", "svlastb_u8"),
        ("expand", "si16", "svlastb_s16"),
        ("expand", "f64", "svlastb_f64"),
        ("compress_store", "ui8", "svlastb_u8"),
        ("expand_load", "f32", "::tsl::masked_set1<"),
    ],
)
def test_sve_pack_expand_paths_stay_register_only(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert evidence in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "std::free" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text
    assert "mask_population_count" in lowered.body_text
    assert "mask_binary_and" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svptest_any" not in lowered.body_text


@pytest.mark.parametrize("type_tag", ["si16", "ui32", "si64", "f64"])
def test_sve_convert_down_stays_register_only(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "convert_down", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svlastb_" in lowered.body_text
    assert "masked_set1" in lowered.body_text
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svdup_n_" not in lowered.body_text
    assert "saturating_cast" in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
@pytest.mark.parametrize("extension", ["clang_v128", "clang_v256", "clang_v512"])
def test_clang_width_conversion_uses_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("si16",))
        .selected
        if selected.extension.name == extension
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "data[" in lowered.body_text
    assert "result[" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("primitive", "extension", "to_extension"),
    [
        ("extract", "clang_v512", "clang_v128"),
        ("insert", "clang_v128", "clang_v512"),
    ],
)
def test_clang_repr_chunk_operations_use_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
    to_extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            primitive,
            ("si32",),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == to_extension
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "result[" in cpp.body_text
    assert "data[" in cpp.body_text
    assert "memcpy" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "for " not in cpp.body_text


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


def test_avx512_partial_narrow_gather_uses_semantic_zero_and_insert(
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
        variant = next(
            body for body in lowered.variant_bodies if body.name == "intrinsic_gather"
        )
        assert "set_zero" in variant.body_text
        assert "insert" in variant.body_text
        assert "zextsi256" not in variant.body_text


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


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin"])
@pytest.mark.parametrize("masked", [False, True])
def test_generic_like_horizontal_reductions_index_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "vec[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_generic_like_bitwise_reductions_index_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
    type_tag: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "vec[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_scalar_bitwise_reductions_do_not_materialize_single_lane_arrays(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    masked: bool,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "scalar"
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin"])
@pytest.mark.parametrize("masked", [False, True])
def test_scalar_arithmetic_reductions_do_not_materialize_single_lane_arrays(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, ("ui32",))
        .selected
        if selected.extension.name == "scalar"
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
def test_scalar_width_conversions_are_direct_scalar_casts(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, ("si16",))
        .selected
        if selected.extension.name == "scalar"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


def test_scalar_lzc_and_cast_are_direct_scalar_operations(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = (
        next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["scalar"], "lzc", ("ui32",))
            .selected
            if selected.extension.name == "scalar"
        ),
        next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["scalar"], "cast", ("si32",))
            .selected
            if selected.extension.name == "scalar" and selected.to_target == "f64"
        ),
    )

    for slot in slots:
        for backend_id in ("cpp", "rust"):
            lowered = Lowerer().lower(
                slot, catalog, create_backend_dialect(catalog, backend_id)
            ).specialization

            assert lowered is not None
            assert "to_array" not in lowered.body_text
            assert "from_array" not in lowered.body_text
            assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_clang_masked_bitwise_reductions_stay_in_vector_or_typed_composition(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "clang_v128"
        and len(selected.primitive.parameters) == 2
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert primitive in lowered.body_text
    assert "binary_" in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["popcnt", "lzc"])
def test_generic_like_bit_counts_mutate_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
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


def test_generic_cast_mutates_native_output_register_directly(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], "cast", ("si32",))
        .selected
        if selected.extension.name == "generic" and selected.to_target == "f64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "data[i]" in lowered.body_text
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
def test_generic_like_width_conversions_mutate_native_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("si16",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "data[" in lowered.body_text
        assert "result[" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_set_constructs_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "set", ("ui32",))
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


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_expand_load_mutates_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "expand_load", ("ui32",))
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


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_load_convert_up_mutates_output_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "load_convert_up",
            ("ui32",),
        )
        .selected
        if selected.extension.name == extension and selected.to_target == "ui64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "out[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    ("primitive", "masked", "type_tag", "keeps_index_array"),
    [
        ("gather", False, "ui32", True),
        ("gather", True, "ui32", True),
        ("gather_narrow_partial", False, "ui16", True),
        ("gather_narrow", False, "ui16", False),
    ],
)
def test_generic_like_gathers_write_native_array_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
    type_tag: str,
    keeps_index_array: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[i]" in lowered.body_text
        assert ("idx_array" in lowered.body_text) is keeps_index_array
        assert "from_array" not in lowered.body_text
        assert not any(
            "result" in line and "to_array" in line
            for line in lowered.body_text.splitlines()
        )


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("masked", [False, True])
def test_generic_like_scatters_read_native_value_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    masked: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "scatter", ("ui32",))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "a[i]" in lowered.body_text
        assert "idx_array" in lowered.body_text
        assert "val_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["blend", "compress", "expand", "conflict"])
def test_generic_like_misc_fallbacks_mutate_native_array_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    ("primitive", "operator"),
    [
        ("mask_binary_and", "&"),
        ("mask_binary_or", "|"),
        ("mask_binary_xor", "^"),
        ("mask_binary_not", None),
    ],
)
def test_generic_like_mask_logic_uses_packed_bitset_operations(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    operator: str | None,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "valid_lanes" in lowered.body_text
        assert "for " not in lowered.body_text
        assert "mask<" not in lowered.body_text
        if operator is not None:
            assert operator in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    "primitive",
    [
        "equal",
        "nequal",
        "less_than",
        "greater_than",
        "less_than_or_equal",
        "greater_than_or_equal",
    ],
)
def test_generic_like_masked_comparisons_compose_unmasked_compare_and_mask_logic(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
        and len(selected.primitive.parameters) == 3
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "mask_binary_and" in lowered.body_text
        assert primitive in lowered.body_text
        assert "for " not in lowered.body_text


def test_generic_mask_population_count_uses_packed_popcount(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["scalar"],
            "mask_population_count",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "generic"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "popcount" in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_ostream_formats_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_ostream", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "ostream_write" in lowered.body_text
        assert "to_array" not in lowered.body_text


def test_sve_ostream_uses_typed_runtime_storage(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "to_ostream", ("ui32",))
        .selected
        if selected.extension.name == "sve"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "values_storage" in lowered.body_text
    assert "std::malloc" not in lowered.body_text
    assert "std::free" not in lowered.body_text


def test_scalar_load_convert_up_is_a_direct_scalar_load_and_cast(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["scalar"],
            "load_convert_up",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "scalar" and selected.to_target == "ui64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "*ptr" in lowered.body_text
        assert "for " not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_clang_load_convert_up_unrolls_direct_output_lanes(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "load_convert_up", ("si8",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.to_target == "si16"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "out[0]" in lowered.body_text
    assert "ptr" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    (
        "profile",
        "extension",
        "source_type",
        "target_type",
        "copy_expression",
        "conversion",
    ),
    [
        ("sse2", "sse", "si8", "si64", "2 * 1", "convert_up"),
        ("sse2", "sse", "f32", "f64", "2 * 4", "convert_up"),
        ("avx2", "avx2", "si8", "si64", "4 * 1", "convert_up"),
        ("knl", "avx512", "si8", "si64", "8 * 1", "_mm512_cvtepi8_epi64"),
        ("neon", "neon", "si8", "si64", "2 * 1", "convert_up"),
        ("wasm32-simd128", "wasm128", "ui16", "ui64", "2 * 2", "convert_up"),
    ],
)
def test_fixed_width_load_convert_up_copies_only_consumed_bytes(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    copy_expression: str,
    conversion: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "load_convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == target_type
    )

    for backend_id, copy_spelling in (
        ("cpp", "memcpy"),
        ("rust", "mem_copy"),
    ):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert copy_spelling in lowered.body_text
        assert copy_expression in lowered.body_text
        assert conversion in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "type_tag", "intrinsic"),
    [
        ("sse2", "ui8", "_mm_set_epi8"),
        ("sse2", "ui16", "_mm_set_epi16"),
        ("sse2", "ui32", "_mm_set_epi32"),
        ("sse2", "ui64", "_mm_set_epi64x"),
        ("sse2", "f64", "_mm_set_epi64x"),
        ("avx2", "ui64", "_mm_set_epi64x"),
    ],
)
def test_sse_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "sse"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert intrinsic in lowered.body_text


def test_clang_mask_kernel_uses_comparison_lane_vectors_and_integral_bridge(
    catalog: Catalog, machine_profiles
) -> None:
    profile = machine_profiles["avx2"]

    equal_slot = _by_key(catalog, profile, "equal")[("f32", "clang_v256")]
    equal = Lowerer().lower(
        equal_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert equal is not None
    assert "return left == right;" in equal.body_text

    to_integral_slot = _by_key(catalog, profile, "to_integral")[
        ("f32", "clang_v256")
    ]
    to_integral = Lowerer().lower(
        to_integral_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert to_integral is not None
    assert "if (mask[i] != 0)" in to_integral.body_text
    assert (
        "result |= (static_cast<typename Vec::imask_type>(1)) << i;"
        in to_integral.body_text
    )

    to_mask_slot = _by_key(catalog, profile, "to_mask")[("f32", "clang_v256")]
    to_mask = Lowerer().lower(
        to_mask_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert to_mask is not None
    assert "typename Vec::mask_type result = static_cast<typename Vec::mask_type>(0);" in (
        to_mask.body_text
    )
    assert "result[i] = -1;" in to_mask.body_text


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

    assert pairs("extract") == {
        ("clang_v256", "clang_v128"),
        ("clang_v512", "clang_v128"),
        ("clang_v512", "clang_v256"),
    }
    assert pairs("insert") == {
        ("clang_v128", "clang_v256"),
        ("clang_v128", "clang_v512"),
        ("clang_v256", "clang_v512"),
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
    clang_extensions = {"clang_v128", "clang_v256", "clang_v512"}
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
