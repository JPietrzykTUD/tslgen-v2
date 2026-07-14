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
from tslc.catalog.target_families import (
    ExtensionFamilyCapability,
    ProfileFamilyCapability,
    TargetFamilyCatalog,
)
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
        "clang_v128_bool",
        "clang_v256_bool",
        "clang_v512_bool",
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


def test_backend_scoped_selection_keeps_fixed_facades_backend_owned(
    catalog: Catalog, machine_profiles
) -> None:
    cpp = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "hadd",
        ("si32",),
        backend_id="cpp",
    ).selected
    rust = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "hadd",
        ("si32",),
        backend_id="rust",
    ).selected

    cpp_overlay = next(slot for slot in cpp if slot.extension.name == "clang_v256")
    assert cpp_overlay.fixed_fallback_extension is not None
    assert all(not slot.extension.name.startswith("clang_") for slot in rust)
    assert all(slot.fixed_fallback_extension is None for slot in rust)


def test_renamed_extension_family_uses_declared_behavior_only(
    catalog: Catalog,
) -> None:
    family_name = "portable_demo"
    extension = replace(catalog.extensions["scalar"], family=family_name)
    families = TargetFamilyCatalog(
        known_extension_families=frozenset({family_name}),
        universal_extension_families=frozenset({family_name}),
        extension_families={
            family_name: ExtensionFamilyCapability(
                family_name,
                implementation_fallback=True,
                requires_declared_vector_register=False,
            )
        },
        profile_families={
            "portable_profile": ProfileFamilyCapability("portable_profile")
        },
    )
    renamed = Catalog(
        primitives=catalog.primitives,
        type_groups=catalog.type_groups,
        extensions={extension.name: extension},
        type_spellings=catalog.type_spellings,
        translations=catalog.translations,
        target_families=families,
    )
    profile = MachineProfile(
        "portable",
        "portable_profile",
        frozenset(),
        {},
    )

    selected = Selector().select_profile(
        renamed,
        profile,
        "add",
        ("si32",),
        backend_id="cpp",
    ).selected
    slot = next(
        slot
        for slot in selected
        if slot.primitive.attributes.get("mask") is None
    )
    lowered = Lowerer().lower(
        slot,
        renamed,
        create_backend_dialect(renamed, "cpp"),
    )

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert lowered.specialization.implementation_state is ImplementationState.FALLBACK


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


def test_clang_mask_kernels_use_their_declared_representation_and_integral_bridge(
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

    bool_equal_slot = _by_key(catalog, profile, "equal")[("f32", "clang_v256_bool")]
    bool_equal = Lowerer().lower(
        bool_equal_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_equal is not None
    assert "return left == right;" in bool_equal.body_text

    bool_to_integral_slot = _by_key(catalog, profile, "to_integral")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_integral = Lowerer().lower(
        bool_to_integral_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_integral is not None
    assert "if (mask[i])" in bool_to_integral.body_text

    bool_to_mask_slot = _by_key(catalog, profile, "to_mask")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_mask = Lowerer().lower(
        bool_to_mask_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_mask is not None
    assert "static_cast<typename Vec::mask_type>(false)" in bool_to_mask.body_text
    assert "result[i] = true;" in bool_to_mask.body_text

    bool_to_vector_slot = _by_key(catalog, profile, "to_vector")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_vector = Lowerer().lower(
        bool_to_vector_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_vector is not None
    assert "::tsl::blend<Vec>" in bool_to_vector.body_text
    assert "::tsl::set_zero<Vec>()" in bool_to_vector.body_text
    assert "::tsl::set1<Vec>" in bool_to_vector.body_text
    assert "::tsl::bit_cast" not in bool_to_vector.body_text
