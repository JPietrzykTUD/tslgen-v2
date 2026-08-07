"""Selection and lowerer ownership regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    ExtensionFamilyCapability,
    ImplementationState,
    Lowerer,
    lowerer_module,
    MachineProfile,
    ProfileFamilyCapability,
    replace,
    resolve_target_vector,
    Selector,
    TargetFamilyCatalog,
    TargetVector,
    _by_key,
    _slots,
    _TYPES,
)
from tslc.lower.lowerer import LoweredArithmeticPreconditionKind


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


def test_integer_immediate_zero_precondition_is_derived_from_arithmetic_contract(
    catalog: Catalog,
    machine_profiles,
) -> None:
    selected = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "mod_imm",
        ("si8", "si32", "f32"),
        backend_id="cpp",
    ).selected

    lowered = tuple(
        result.specialization
        for slot in selected
        if (
            result := Lowerer().lower(
                slot, catalog, create_backend_dialect(catalog, "cpp")
            )
        ).specialization
        is not None
    )
    integer = tuple(spec for spec in lowered if spec.type_tag in {"si8", "si32"})
    floating = tuple(spec for spec in lowered if spec.type_tag == "f32")

    assert integer
    assert floating
    assert {
        (precondition.kind, precondition.parameter_name, precondition.lane_bit_width)
        for spec in integer
        for precondition in spec.arithmetic_preconditions
    } == {
        (
            LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO,
            "divisor",
            8,
        ),
        (
            LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO,
            "divisor",
            32,
        ),
    }
    assert all(not spec.arithmetic_preconditions for spec in floating)


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
        catalog,
        machine_profiles["avx2"],
        "hadd",
        ("f32",),
        backend_id="cpp",
        compiler_capabilities=frozenset({"reduce_in_order_fadd"}),
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
    fallback_slots = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "hadd",
        ("f32",),
        backend_id="cpp",
        compiler_capabilities=frozenset(),
    ).selected
    fallback = next(
        slot
        for slot in fallback_slots
        if slot.extension.name == "clang_v256"
        and slot.primitive.signature == "s:=v"
    )
    fallback_cpp = Lowerer().lower(
        fallback, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    masked_cpp = Lowerer().lower(
        masked, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert unmasked_cpp is not None
    assert "#if" not in unmasked_cpp.body_text
    assert "__builtin_reduce_in_order_fadd(vec" in unmasked_cpp.body_text
    assert "vec[0]" not in unmasked_cpp.body_text
    assert "for " not in unmasked_cpp.body_text
    assert "to_array" not in unmasked_cpp.body_text
    assert fallback_cpp is not None
    assert "__builtin_reduce_in_order_fadd" not in fallback_cpp.body_text
    assert "vec[0]" in fallback_cpp.body_text
    assert masked_cpp is not None
    assert "::tsl::binary_and<Vec>(mask_vector, vec)" in masked_cpp.body_text
    assert "::tsl::hadd<Vec>" in masked_cpp.body_text
    assert "to_array" not in masked_cpp.body_text
