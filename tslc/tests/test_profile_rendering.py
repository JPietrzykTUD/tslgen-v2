"""Backend selection, profile-name sanitization, and feature-flag spelling."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.target_families import (
    BackendProfileFamily,
    ProfileFamilyCapability,
    TargetFeatureCapability,
)
from tslc.diagnostics import has_errors
from tslc.render.cpp_build import _x86_profile_detection_source, cpp_flags, cpp_target
from tslc.render._common import slug
from tslc.render.rust_project import rust_linker, rust_target, rust_target_features


def _roots(result) -> set[str]:
    return {a.logical_path.split("/")[0] for a in result.artifacts.artifacts}


def _gen(data_root, mp, **kw):
    return generate_project([data_root], machine_profiles_path=mp, **kw)


@pytest.fixture(scope="module")
def sve_value_project(data_root: Path, machine_profiles_path: Path):
    return _gen(
        data_root,
        machine_profiles_path,
        primitives=[
            "add",
            "equal",
            "mask_binary_and",
            "mask_false",
            "mask_true",
            "store_mask_repr",
            "to_integral",
            "to_mask",
            "to_vector",
        ],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )


@pytest.fixture(scope="module")
def sve_value_artifacts(sve_value_project) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in sve_value_project.artifacts.artifacts
    }


def test_backend_selection_is_honored(data_root: Path, machine_profiles_path: Path) -> None:
    rust_only = _gen(
        data_root, machine_profiles_path, primitives=["add"], profiles=["avx2"], backends=["rust"]
    )
    assert _roots(rust_only) == {"docs", "rust"}

    cpp_only = _gen(
        data_root, machine_profiles_path, primitives=["add"], profiles=["avx2"], backends=["cpp"]
    )
    assert _roots(cpp_only) == {"cpp", "docs"}
    # verify description only covers the requested backend
    assert [b.backend_id for b in cpp_only.rendered.verify.backends] == ["cpp"]


def test_rust_profile_module_is_compiled_only_for_its_target_contract(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    profile = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "rust/src/tsl_avx2.rs"
    )

    assert "#![cfg(any(" in profile
    assert 'all(target_arch = "x86_64"' in profile
    assert (
        'all(feature = "runtime-dispatch", target_arch = "x86_64")'
        in profile
    )
    assert 'target_feature = "avx"' in profile
    assert 'target_feature = "avx2"' in profile
    assert 'target_feature = "rdrand"' in profile
    assert "TSL_RUST_PROFILE_TARGET_FEATURE_MISMATCH" not in profile


def test_generated_project_carries_apache_license_notices(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        backends=["cpp", "rust"],
    )
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }

    assert "Apache License" in artifacts["cpp/LICENSE"]
    assert "Apache License" in artifacts["rust/LICENSE"]
    assert artifacts["cpp/include/tsl.hpp"].startswith(
        "/*\n * Copyright 2026 Johannes Pietrzyk and TSL(c) contributors\n"
    )
    assert artifacts["rust/src/lib.rs"].startswith(
        "// Copyright 2026 Johannes Pietrzyk and TSL(c) contributors\n"
    )
    assert artifacts["cpp/CMakeLists.txt"].startswith(
        "# Copyright 2026 Johannes Pietrzyk and TSL(c) contributors\n"
    )
    assert artifacts["rust/Cargo.toml"].startswith(
        "# Copyright 2026 Johannes Pietrzyk and TSL(c) contributors\n"
    )
    assert artifacts["docs/specializations/specializations.json"].startswith("{")


def test_representative_project_shape_is_byte_stable(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["scalar", "avx2"],
        backends=["cpp", "rust"],
    )
    expected = {
        "cpp/CMakeLists.txt": "afd9ccd8ea6feffdfe0fa38e44e5027b3e49b8206938b23415c59bf35c510b87",
        "cpp/docs/input/tsl_api_docs.hpp": "25c8a21fafad064c394b933b6c5d27b6dc07aaf4a509150d9da7e87ff9f8027d",
        "cpp/include/tsl.hpp": "298cd47b4e1509cd59eb4100f7a0d82bcdbc6e5d9f4eedccb0a68ba0bf667e03",
        "cpp/include/tsl_primitives.hpp": "f1b98a21c8d349dc049eb9bf0d1d651a32156196bad5aa7de1c409ef5cbf496c",
        "cpp/include/tsl_scalar.hpp": "a3d1b9f8fd299e4710f39f7e887380668a9c666311440d0d6eae281e2ba5cef5",
        "cpp/tests/smoke_scalar.cpp": "43046adfe06468b6eb75f351dc8883cb1e35635e66f40fc3f033d41651554a1e",
        "rust/Cargo.toml": "ec632691434d5f98f5bb2035539e9df258ec7fb252f84e5b4cb21a0aa2a144cc",
        "rust/src/lib.rs": "a92242407733aa553b68d0770f97b50e5e92bdee6232f1638a8d44f2121b9339",
        "rust/src/tsl_documentation.rs": "41f2ff6e6cdcfb95751473db764e8d7e32fd2d7785a7fe5212b91d1d1771e07a",
        "rust/src/tsl_scalar.rs": "bf203ab3fd628764b20a91c6ea83e548992190557490d02d4edc8e5a20dee8fd",
        "rust/tests/smoke.rs": "a4d108f502689e7f29ba5259e22779e8ef0afa36ab83c239022e2772d68d6b44",
    }
    actual = {
        artifact.logical_path: sha256(artifact.content.encode()).hexdigest()
        for artifact in result.artifacts.artifacts
        if artifact.logical_path in expected
    }

    assert actual == expected


def test_clang_vector_overlay_is_split_guarded_and_uses_hardware_facade(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add", "hadd"],
        profiles=["avx2"],
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    by = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

    base = by["cpp/include/tsl_avx2.hpp"]
    overlay = by["cpp/include/tsl_avx2_clang.hpp"]
    dispatch = by["cpp/include/tsl.hpp"]
    cmake = by["cpp/CMakeLists.txt"]
    base_smoke = by["cpp/tests/smoke_avx2.cpp"]
    overlay_smoke = by["cpp/tests/smoke_avx2_clang.cpp"]

    assert "clang_v128" not in base
    assert "clang_v256" not in base
    assert "clang_v512" not in base
    assert "clang_v128" not in base_smoke
    assert "clang_fixed" not in base
    assert "clang_v128" in overlay_smoke
    assert "struct clang_v128 {};" in overlay
    assert "struct clang_v256 {};" in overlay
    assert "struct clang_v512 {};" in overlay
    assert "struct clang_v128_bool {};" in overlay
    assert "struct clang_v256_bool {};" in overlay
    assert "struct clang_v512_bool {};" in overlay
    assert "using mask_type = decltype(register_type{} == register_type{});" in overlay
    assert "using mask_type = bool __attribute__((ext_vector_type(4)));" in overlay
    assert "struct clang_fixed" in overlay
    assert "namespace clang_mask" in overlay
    assert "struct comparison_vector {};" in overlay
    assert "struct boolean_vector {};" in overlay
    assert "tsl::dataparallel::clang_fixed<N> requires N > 0" in overlay
    assert (
        "struct simd_for<clang_fixed<4, clang_mask::comparison_vector>, int32_t>"
        in overlay
    )
    assert "using type = ::tsl::simd<int32_t, ::tsl::clang_v128>;" in overlay
    assert (
        "struct simd_for<clang_fixed<8, clang_mask::comparison_vector>, int32_t>"
        in overlay
    )
    assert "using type = ::tsl::simd<int32_t, ::tsl::clang_v256>;" in overlay
    assert (
        "struct simd_for<clang_fixed<16, clang_mask::comparison_vector>, int32_t>"
        in overlay
    )
    assert "using type = ::tsl::simd<int32_t, ::tsl::clang_v512>;" in overlay
    assert (
        "struct simd_for<clang_fixed<4, clang_mask::boolean_vector>, int32_t>"
        in overlay
    )
    assert "using type = ::tsl::simd<int32_t, ::tsl::clang_v128_bool>;" in overlay
    assert "#if __has_feature(ext_vector_type_boolean)" in overlay
    assert "#if defined(__clang__) && __clang__ == 1" in overlay
    assert "return (left + right);" in overlay
    assert "return __builtin_reduce_add(vec);" in overlay
    assert "struct hadd_impl<tsl::simd<int32_t, tsl::clang_v512>>" in overlay
    assert "using type = ::tsl::simd<int32_t, ::tsl::clang_v256>;" not in base
    assert "#if defined(TSL_ENABLE_CLANG)" in dispatch
    assert '#  include "tsl_avx2_clang.hpp"' in dispatch
    assert 'if(CMAKE_CXX_COMPILER_ID MATCHES "^(AppleClang|Clang)$")' in cmake
    assert "add_library(tsl::avx2_clang ALIAS tsl_profile_avx2_clang)" in cmake
    assert "target_compile_definitions(tsl_profile_avx2_clang INTERFACE TSL_ENABLE_CLANG)" in cmake
    assert "add_executable(tsl_values_clang tests/values_${TSL_SELECTED_PROFILE}.cpp)" in cmake
    assert "add_dependencies(tsl_values tsl_values_clang)" in cmake
    assert "add_test(NAME values_clang COMMAND tsl_values_clang)" in cmake
    assert "&& __clang__ == 1" not in cmake


def test_clang_overlay_declares_primitive_missing_from_hardware_profile(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["insert"],
        profiles=["wasm32-simd128"],
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    by = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

    base = by["cpp/include/tsl_wasm32_simd128.hpp"]
    overlay = by["cpp/include/tsl_wasm32_simd128_clang.hpp"]
    declaration = "struct insert_impl;"
    specialization = "struct insert_impl<tsl::simd<int8_t, tsl::clang_v128>"

    assert declaration not in base
    assert declaration in overlay
    assert "inline typename ToVec::register_type insert(" in overlay
    assert specialization in overlay
    assert overlay.index(declaration) < overlay.index(specialization)


def test_base_header_declares_variant_defined_only_by_clang_overlay(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["permute_lanes"],
        profiles=["wasm32-simd128"],
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    by = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

    base = by["cpp/include/tsl_wasm32_simd128.hpp"]
    overlay = by["cpp/include/tsl_wasm32_simd128_clang.hpp"]

    assert "scalar_lanes_fallback," in base
    assert "struct permute_lanes_imm_impl_scalar_lanes_fallback;" in base
    assert "struct permute_lanes_imm_impl_scalar_lanes_fallback<" in overlay


def test_profile_name_sanitized_to_valid_identifiers(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["icelake_rockerlake-oneapi"],
    )
    by = {a.logical_path: a.content for a in result.artifacts.artifacts}
    # No raw hyphen leaks into any generated C++ or Rust source.
    for path, content in by.items():
        if path.endswith((".hpp", ".cpp", ".rs")):
            assert "icelake_rockerlake-oneapi" not in content, path
    assert "#if defined(TSL_PROFILE_ICELAKE_ROCKERLAKE_ONEAPI)" in by["cpp/include/tsl.hpp"]
    assert "cpp/include/tsl_icelake_rockerlake_oneapi.hpp" in by
    assert "pub mod tsl_icelake_rockerlake_oneapi;" in by["rust/src/lib.rs"]
    assert "icelake_rockerlake_oneapi = []" not in by["rust/Cargo.toml"]
    assert "default = []" in by["rust/Cargo.toml"]


def test_oneapi_sized_vector_is_distinct_from_generic(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["cascadelake-oneapi"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    by = {a.logical_path: a.content for a in result.artifacts.artifacts}

    cpp = by["cpp/include/tsl_cascadelake_oneapi.hpp"]
    assert "template <std::size_t LANES>\nstruct oneapi_fpga" in cpp
    assert "#include <sycl/ext/intel/ac_types/ac_int.hpp>" in cpp
    assert "using mask_type = ac_int<LANES, false>;" in cpp
    assert "using imask_type = ac_int<LANES, false>;" in cpp
    assert "struct add_impl<tsl::simd<int32_t, tsl::generic<LANES>>>" in cpp
    assert "struct add_impl<tsl::simd<int32_t, tsl::oneapi_fpga<LANES>>>" in cpp
    assert cpp.count("struct add_impl<tsl::simd<int32_t, tsl::generic<LANES>>>") == 1
    assert cpp.count("struct add_impl<tsl::simd<int32_t, tsl::oneapi_fpga<LANES>>>") == 1

    rust = by["rust/src/tsl_cascadelake_oneapi.rs"]
    assert "pub struct OneapiFpga<const LANES: usize>;" in rust
    assert "impl<const LANES: usize> AddImpl for Simd<i32, Generic<LANES>>" in rust
    assert "impl<const LANES: usize> AddImpl for Simd<i32, OneapiFpga<LANES>>" in rust
    rust_fallback = by["rust/src/tsl_target_fallback.rs"]
    assert "OneapiFpga" not in rust_fallback
    assert "impl<const LANES: usize> AddImpl for Simd<i32, Generic<LANES>>" in (
        rust_fallback
    )


def test_feature_flag_spelling(data_root: Path, machine_profiles_path: Path) -> None:
    # zen4 carries features that need real spelling: avx512_vnni -> avx512vnni, and
    # alternatives avx512_gfni -> gfni, avx512_vpclmulqdq -> vpclmulqdq.
    cmake = {
        a.logical_path: a.content
        for a in _gen(
            data_root, machine_profiles_path, primitives=["add"], profiles=["zen4"], backends=["cpp"]
        ).artifacts.artifacts
    }["cpp/CMakeLists.txt"]
    assert "-mgfni" in cmake and "-mvpclmulqdq" in cmake and "-mavx512vnni" in cmake
    # the naive (wrong) spellings must not appear
    assert "-mavx512_gfni" not in cmake
    assert "-mavx512_vnni" not in cmake
    assert 'add_library(tsl::zen4 ALIAS tsl_profile_zen4)' in cmake
    assert "target_compile_definitions(tsl_profile_zen4 INTERFACE TSL_PROFILE_ZEN4)" in cmake
    assert 'set(TSL_PROFILE "auto" CACHE STRING' in cmake
    assert 'add_library(tsl::tsl ALIAS tsl_generated)' in cmake
    assert "target_link_libraries(tsl_generated INTERFACE tsl_profile_${TSL_SELECTED_PROFILE})" in cmake
    assert "check_cxx_source_runs" in cmake
    assert '__builtin_cpu_supports("avx2")' in cmake
    assert "TSL_AUTO_ONEAPI_FPGA" not in cmake
    assert "auto-oneapi-fpga" not in cmake


def test_cpp_auto_detection_uses_cpuid_for_unsupported_clang_builtins() -> None:
    capabilities = {
        name: TargetFeatureCapability(name=name, backend_spellings={"cpp": spelling})
        for name, spelling in (
            ("rdrand", "rdrnd"),
            ("avx512_vaes", "vaes"),
            ("avx512_fp16", "avx512fp16"),
        )
    }
    profile = MachineProfile(
        name="sapphire_rapids",
        family="x86",
        features=frozenset(
            {"avx2", "avx512f", "rdrand", "avx512_vaes", "avx512_fp16"}
        ),
        alternatives={},
        feature_capabilities=capabilities,
    )

    source = _x86_profile_detection_source(profile)

    assert cpp_flags(profile) == (
        "-mavx2",
        "-mavx512fp16",
        "-mvaes",
        "-mavx512f",
        "-mrdrnd",
    )
    assert '__builtin_cpu_supports("avx2")' in source
    assert '__builtin_cpu_supports("avx512f")' in source
    assert "#include <cpuid.h>" in source
    assert "__get_cpuid(1, &tsl_cpuid_1_eax" in source
    assert "__get_cpuid_count(7, 0, &tsl_cpuid_7_0_eax" in source
    assert "(tsl_cpuid_1_ecx & (1u << 30)) != 0" in source
    assert "(tsl_cpuid_7_0_ecx & (1u << 9)) != 0" in source
    assert "(tsl_cpuid_7_0_edx & (1u << 23)) != 0" in source
    assert '__builtin_cpu_supports("rdrnd")' not in source
    assert '__builtin_cpu_supports("vaes")' not in source
    assert '__builtin_cpu_supports("avx512fp16")' not in source

    source_without_rdrand = _x86_profile_detection_source(
        MachineProfile("avx", "x86", frozenset({"avx"}), {})
    )
    assert '__builtin_cpu_supports("avx")' in source_without_rdrand
    assert "#include <cpuid.h>" not in source_without_rdrand
    assert "__get_cpuid" not in source_without_rdrand


def test_oneapi_fpga_profiles_are_opt_in_for_cmake_auto_detection(
    data_root: Path, machine_profiles_path: Path
) -> None:
    cmake = {
        a.logical_path: a.content
        for a in _gen(
            data_root,
            machine_profiles_path,
            primitives=["add"],
            profiles=["cascadelake", "cascadelake-oneapi"],
            backends=["cpp"],
        ).artifacts.artifacts
    }["cpp/CMakeLists.txt"]

    assert '"auto-oneapi-fpga"' in cmake
    assert "TSL_AUTO_ONEAPI_FPGA" not in cmake
    assert 'elseif(_TSL_REQUESTED_PROFILE STREQUAL "auto-oneapi-fpga")' in cmake
    assert '_tsl_detect_profile_gate("oneapi_fpga" _TSL_GATE_READY _TSL_GATE_REASON)' in cmake
    assert "sycl-ls" in cmake
    assert "clinfo" in cmake
    assert "aocl list-devices" in cmake
    assert "aocl diagnose" in cmake

    base_selection = 'set(TSL_SELECTED_PROFILE "cascadelake")'
    oneapi_selection = 'set(TSL_SELECTED_PROFILE "cascadelake_oneapi")'
    cpu_auto = 'if(_TSL_REQUESTED_PROFILE STREQUAL "auto")'
    fpga_auto = 'elseif(_TSL_REQUESTED_PROFILE STREQUAL "auto-oneapi-fpga")'

    assert base_selection in cmake
    assert oneapi_selection in cmake
    assert cmake.index(cpu_auto) < cmake.index(base_selection) < cmake.index(fpga_auto)
    assert cmake.index(fpga_auto) < cmake.index(oneapi_selection)
    assert cmake.index("    check_cxx_source_runs", cmake.index(fpga_auto)) < cmake.index(
        oneapi_selection
    )


def test_cpu_auto_detection_has_no_gated_profile_fallback(
    data_root: Path, machine_profiles_path: Path
) -> None:
    cmake = {
        a.logical_path: a.content
        for a in _gen(
            data_root,
            machine_profiles_path,
            primitives=["add"],
            profiles=["cascadelake-oneapi"],
            backends=["cpp"],
        ).artifacts.artifacts
    }["cpp/CMakeLists.txt"]

    assert 'set(TSL_SELECTED_PROFILE "")' in cmake
    assert "TSL_PROFILE=auto has no ungated generated profiles" in cmake
    assert "auto-oneapi-fpga" in cmake


def test_cpp_profile_flags_are_profile_family_owned() -> None:
    profile = MachineProfile(
        name="sve",
        family="aarch64",
        features=frozenset({"sve"}),
        alternatives={},
        backend_flags={"cpp": ("-march=armv8-a+sve",)},
    )
    capability = ProfileFamilyCapability(
        "aarch64",
        backends={
            "cpp": BackendProfileFamily(
                feature_flags=False,
                target="aarch64-linux-gnu",
            )
        },
    )

    assert cpp_flags(profile, capability) == ("-march=armv8-a+sve",)
    assert cpp_target(profile, capability) == "aarch64-linux-gnu"


def test_rust_profile_toolchain_is_profile_family_owned() -> None:
    profile = MachineProfile(
        name="neon",
        family="aarch64",
        features=frozenset({"neon"}),
        alternatives={},
    )
    capability = ProfileFamilyCapability(
        "aarch64",
        backends={
            "rust": BackendProfileFamily(
                feature_flags=True,
                target="aarch64-unknown-linux-musl",
                linker="rust-lld",
            )
        },
    )

    assert rust_target_features(profile, capability) == ("+neon",)
    assert rust_target(profile, capability) == "aarch64-unknown-linux-musl"
    assert rust_linker(profile, capability) == "rust-lld"
    assert rust_target_features(
        profile,
        ProfileFamilyCapability(
            "generic",
            backends={"rust": BackendProfileFamily(feature_flags=False)},
        ),
    ) == ()

    fixed_sve = MachineProfile(
        name="sve512",
        family="aarch64",
        features=frozenset({"sve"}),
        alternatives={},
        compile_modes=frozenset({"sve_vector_bits_512"}),
    )
    assert rust_target_features(fixed_sve, capability) == ("+sve",)


def test_omitted_profiles_use_all_loaded_profiles(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    profile_result = load_machine_profiles_checked(machine_profiles_path)
    assert profile_result.diagnostics == ()
    expected = sorted(slug(name) for name in profile_result.profiles)

    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        backends=["cpp"],
    )

    assert result.rendered is not None
    actual = sorted(result.rendered.verify.backends[0].profiles, key=lambda p: p.profile_name)
    assert [profile.file_stem for profile in actual] == expected
    neon_profile = next(profile for profile in actual if profile.profile_name == "neon")
    assert neon_profile.target == "aarch64-linux-gnu"
    assert neon_profile.flags == ()
    assert neon_profile.runner is not None
    assert neon_profile.runner.kind == "qemu-aarch64"
    assert neon_profile.runner.profile == "cortex-a76"
    assert "cpp/include/tsl_neon.hpp" in {
        artifact.logical_path for artifact in result.artifacts.artifacts
    }


def test_neon_profile_registers_native_simd_types(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["neon"],
        backends=["cpp", "rust"],
    )
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

    cpp = by_path["cpp/include/tsl_neon.hpp"]
    assert "namespace tsl::profiles::neon" in cpp
    assert 'inline constexpr char const* name = "neon";' in cpp
    assert 'inline constexpr char const* family = "aarch64";' in cpp
    assert "active_profile = profiles::neon::name" in cpp
    assert "#include <arm_neon.h>" in cpp
    assert "struct neon {};" in cpp
    assert "struct simd<int32_t, neon>" in cpp
    assert "using extension_type = neon;" in cpp
    assert "using with_base_type = simd<ToBase, neon>;" in cpp
    assert "using with_extension = simd<int32_t, ToExtension>;" in cpp
    assert "using register_type = int32x4_t;" in cpp
    assert "return vaddq_s32(left, right);" in cpp

    rust = by_path["rust/src/tsl_neon.rs"]
    rust_lib = by_path["rust/src/lib.rs"]
    assert "#![cfg(any(" in rust
    assert 'all(target_arch = "aarch64", target_feature = "neon")' in rust
    assert (
        'all(feature = "runtime-dispatch", target_arch = "aarch64")'
        in rust
    )
    assert (
        '#[cfg(all(not(doc), all(target_arch = "aarch64", '
        'target_feature = "neon")))]' in rust_lib
    )
    assert 'target_arch = "x86_64"' not in rust_lib
    assert 'pub const ACTIVE_PROFILE: &str = "neon";' in rust
    assert 'pub const ACTIVE_PROFILE_FAMILY: &str = "aarch64";' in rust
    assert "use core::arch::aarch64::*;" in rust
    assert "pub struct Neon;" in rust
    assert "impl SimdVector for Simd<i32, Neon>" in rust
    assert "impl StaticSimdVector for Simd<i32, Neon>" in rust
    assert "type Extension = Neon;" in rust
    assert "type WithBaseType<ToBase> = Simd<ToBase, Neon>;" in rust
    assert "type WithExtension<ToExtension> = Simd<i32, ToExtension>;" in rust
    assert "fn lane_count() -> usize { 4 }" in rust
    assert "type RegisterType = core::arch::aarch64::int32x4_t;" in rust
    assert "return core::arch::aarch64::vaddq_s32(left, right);" in rust


@pytest.mark.parametrize(("width", "lanes"), [(128, 4), (256, 8), (512, 16)])
def test_fixed_sve_profile_registers_guarded_static_cpp_simd_types(
    width: int,
    lanes: int,
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    profile = f"sve{width}"
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=[profile],
        backends=["cpp"],
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

    cpp = by_path[f"cpp/include/tsl_{profile}.hpp"]
    cmake = by_path["cpp/CMakeLists.txt"]
    dispatch = by_path["cpp/include/tsl.hpp"]
    assert cpp.startswith(
        f"#if defined(__ARM_FEATURE_SVE_BITS) && __ARM_FEATURE_SVE_BITS == {width}\n"
    )
    assert (
        f'#  error "TSL {profile} profile requires -msve-vector-bits={width}"'
        in cpp
    )
    assert f"struct {profile} {{}};" in cpp
    assert "struct sve {};" not in cpp
    assert f"struct simd<int32_t, {profile}>" in cpp
    assert (
        "using register_type = "
        f"svint32_t __attribute__((arm_sve_vector_bits({width})));"
    ) in cpp
    assert (
        "using mask_type = "
        f"svbool_t __attribute__((arm_sve_vector_bits({width})));"
    ) in cpp
    assert "static constexpr bool has_static_lane_count_v = true;" in cpp
    assert f"static constexpr std::size_t lane_count_v = {lanes};" in cpp
    assert "return svadd_s32_x(::tsl::mask_true<Vec>(), left, right);" in cpp
    assert f"#if defined(TSL_PROFILE_SVE{width})" in dispatch
    assert (
        f"target_compile_options(tsl_profile_sve{width} INTERFACE "
        "$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang,IntelLLVM>:-mcpu=a64fx> "
        f"$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang,IntelLLVM>:-msve-vector-bits={width}>)"
    ) in cmake
    assert f"__ARM_FEATURE_SVE_BITS == {width}" in cmake


def test_sve_profile_registers_scalable_cpp_simd_types(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    by_path = sve_value_artifacts

    cpp = by_path["cpp/include/tsl_sve.hpp"]
    cmake = by_path["cpp/CMakeLists.txt"]
    values = by_path["cpp/tests/values_sve.cpp"]
    test_core = by_path["cpp/include/tsl_test_core.hpp"]
    test_sve = by_path["cpp/include/tsl_test_sve.hpp"]
    assert "#include <arm_sve.h>" in cpp
    assert "struct sve {};" in cpp
    assert "struct simd<int32_t, sve>" in cpp
    assert "using register_type = svint32_t;" in cpp
    assert "using mask_type = svbool_t;" in cpp
    assert "using imask_type = svbool_t;" in cpp
    sve_i32_start = cpp.index("struct simd<int32_t, sve>")
    sve_i32_end = cpp.index("};", sve_i32_start)
    sve_i32_registration = cpp[sve_i32_start:sve_i32_end]
    assert "static constexpr bool has_static_lane_count_v = false;" in sve_i32_registration
    assert "static constexpr std::size_t lane_count_v =" not in sve_i32_registration
    assert "static constexpr std::size_t vector_element_count =" not in sve_i32_registration
    assert "static std::size_t lane_count() noexcept" in sve_i32_registration
    assert "return svcntb() / sizeof(int32_t);" in sve_i32_registration
    assert "struct simd_for<native, int32_t>" in cpp
    assert "using type = ::tsl::simd<int32_t, ::tsl::sve>;" in cpp
    inferred_i32_blocks = [
        block for block in cpp.split("template <>") if "struct simd_for<fixed<" in block
    ]
    assert inferred_i32_blocks
    assert all("::tsl::sve" not in block for block in inferred_i32_blocks)
    assert "static constexpr std::size_t vector_alignment = 4;" in cpp
    assert "static constexpr std::size_t simd_register_alignment_v = vector_alignment;" in cpp
    assert "return svadd_s32_x(::tsl::mask_true<Vec>(), left, right);" in cpp
    assert 'add_library(tsl::sve ALIAS tsl_profile_sve)' in cmake
    assert "target_compile_definitions(tsl_profile_sve INTERFACE TSL_PROFILE_SVE)" in cmake
    assert "target_compile_options(tsl_profile_sve INTERFACE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang,IntelLLVM>:-mcpu=a64fx>)" in cmake
    assert any(
        case.kind == "scalable_golden"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert any(
        case.kind == "scalable_masked"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "using Vec = tsl::simd<int32_t, tsl::sve>;" in values
    assert '#include "tsl_test_sve.hpp"' in values
    assert "svcntb() / sizeof(int32_t)" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "tsl::load<Vec, false>" in values
    assert "tsl::store<Vec, false>" in values
    assert "sve_mask_from_bits" not in values
    assert "check_sve_mask_bits" not in values
    assert "sve_mask_from_bits" not in test_core
    assert "check_sve_mask_bits" not in test_core
    assert "arm_sve.h" not in test_core
    assert "mask_bits_adapter<::tsl::simd<Base, ::tsl::sve>>" in test_sve
    assert "#include <arm_sve.h>" in test_sve


def test_sve_profile_plans_scalable_mask_result_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_result"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_equal_equal_si32_basic" in values
    assert "::tsl::test::check_mask_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::equal<Vec>(v0, v1);" in values


def test_sve_profile_plans_scalable_masked_mask_result_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_masked_mask_result"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_equal_maskz" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "::tsl::test::check_mask_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::equal_maskz<Vec>(m0, v0, v1);" in values


def test_sve_profile_plans_scalable_mask_logic_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_logic"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_mask_binary_and" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "::tsl::test::check_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::mask_binary_and<Vec>(m0, m1);" in values


def test_sve_profile_plans_scalable_mask_constant_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_constant"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_mask_true" in values
    assert "test_scalable_sve_mask_false" in values
    assert "::tsl::test::check_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::mask_true<Vec>();" in values
    assert "typename Vec::mask_type result = tsl::mask_false<Vec>();" in values


def test_sve_profile_plans_scalable_mask_conversion_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_conversion"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_to_integral" in values
    assert "test_scalable_sve_to_mask" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "::tsl::test::check_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type input = " in values
    assert "typename Vec::imask_type input = " in values
    assert "typename Vec::imask_type result = tsl::to_integral<Vec>(input);" in values
    assert "typename Vec::mask_type result = tsl::to_mask<Vec>(input);" in values


def test_sve_profile_plans_scalable_mask_to_vector_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_masked"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_to_vector" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::register_type result = tsl::to_vector<Vec>(mask);" in values
    assert "tsl::store<Vec, false>(actual.data(), result);" in values


def test_sve_profile_plans_scalable_mask_store_values(
    sve_value_project,
    sve_value_artifacts: dict[str, str],
) -> None:
    result = sve_value_project
    assert result.rendered is not None
    values = sve_value_artifacts["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_store"
        and case.scalable is not None
        and case.scalable.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_store_mask_repr" in values
    assert "::tsl::test::mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "std::vector<uint32_t> actual(1 + lanes);" in values
    assert "tsl::store_mask_repr<Vec, false, false>(" in values
    assert "reinterpret_cast<typename Vec::base_type *>(actual.data() + 1), mask);" in values

@pytest.fixture(scope="module")
def rvv_project(data_root: Path, machine_profiles_path: Path):
    return _gen(
        data_root,
        machine_profiles_path,
        primitives=["set1", "set_zero", "load", "store", "add", "sub", "mul"],
        profiles=["rvv"],
        type_tags=[
            "si8", "ui8", "si16", "ui16", "si32",
            "ui32", "si64", "ui64", "f32", "f64",
        ],
        backends=["cpp", "rust"],
    )


def test_rvv_catalog_is_scalable_lmul1_cpp_only(catalog, machine_profiles) -> None:
    extension = catalog.extensions["rvv"]
    profile = machine_profiles["rvv"]
    family = catalog.target_families.profile_family("riscv")

    assert extension.family == "rvv"
    assert extension.vector_bits_kind == "scalable"
    assert extension.runtime_lane_count["cpp"] == (
        "__riscv_vlenb() / sizeof({base_type})"
    )
    register_types = {
        "si8": ("vint8m1_t", "i8m1"),
        "ui8": ("vuint8m1_t", "u8m1"),
        "si16": ("vint16m1_t", "i16m1"),
        "ui16": ("vuint16m1_t", "u16m1"),
        "si32": ("vint32m1_t", "i32m1"),
        "ui32": ("vuint32m1_t", "u32m1"),
        "si64": ("vint64m1_t", "i64m1"),
        "ui64": ("vuint64m1_t", "u64m1"),
        "f32": ("vfloat32m1_t", "f32m1"),
        "f64": ("vfloat64m1_t", "f64m1"),
    }
    for type_tag, (register, suffix) in register_types.items():
        assert extension.direct_vector_register_type("cpp", type_tag) == register
        assert extension.compose_suffix_by_type[type_tag] == suffix
    assert extension.mask_policy.kind == "native_predicate_by_type"
    assert extension.mask_policy.spelling_for_type("cpp", "si32") == "vbool32_t"
    assert extension.mask_policy.spelling_for_type("cpp", "f64") == "vbool64_t"
    assert extension.supports_backend("cpp")
    assert not extension.supports_backend("rust")
    assert profile.supported_backends == frozenset({"cpp"})
    assert profile.supports_backend("cpp")
    assert not profile.supports_backend("rust")
    assert family is not None
    cpp = family.backend("cpp")
    assert cpp.compiler_role == "riscv-cpp"
    assert cpp.cmake_system_name == "Linux"
    assert cpp.cmake_system_processor == "riscv64"
    assert not cpp.pass_target_to_compiler


def test_rvv_core_operations_lower_exact_intrinsics_and_emits_no_rust_profile(
    rvv_project,
) -> None:
    assert not has_errors(rvv_project.diagnostics), rvv_project.diagnostics
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in rvv_project.artifacts.artifacts
    }
    header = artifacts["cpp/include/tsl_rvv.hpp"]
    integer_types = {
        "i8m1": 8,
        "u8m1": 8,
        "i16m1": 16,
        "u16m1": 16,
        "i32m1": 32,
        "u32m1": 32,
        "i64m1": 64,
        "u64m1": 64,
    }
    for suffix, width in integer_types.items():
        for stem in (
            "vmv_v_x",
            f"vle{width}_v",
            f"vse{width}_v",
            "vadd_vv",
            "vmul_vv",
            "vsub_vv",
        ):
            assert f"__riscv_{stem}_{suffix}" in header
        assert f"__riscv_vle{width}_v_{suffix}_mu" in header
        assert f"__riscv_vse{width}_v_{suffix}_m" in header
    for suffix, width in (("f32m1", 32), ("f64m1", 64)):
        for stem in (
            "vfmv_v_f",
            f"vle{width}_v",
            f"vse{width}_v",
            "vfadd_vv",
            "vfmul_vv",
            "vfsub_vv",
        ):
            assert f"__riscv_{stem}_{suffix}" in header
        assert f"__riscv_vle{width}_v_{suffix}_mu" in header
        assert f"__riscv_vse{width}_v_{suffix}_m" in header
    assert "return ::tsl::set1<Vec>(static_cast<int32_t>(0));" in header
    assert "::tsl::add<Vec>(left, right),\n" in header
    assert "::tsl::sub<Vec>(left, right),\n" in header
    assert "::tsl::mul<Vec>(factor1, factor2),\n" in header
    assert "::tsl::set_zero<Vec>()" in header
    assert header.count("return ::tsl::select<Vec>(") >= 40

    values = artifacts["cpp/tests/values_rvv.cpp"]
    scalable_kinds = {
        case.kind
        for profile in rvv_project.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
        if case.scalable is not None
        and case.scalable.source_extension == "rvv"
    }
    assert "scalable_masked_pointer_load" in scalable_kinds
    assert "scalable_masked_pointer_store" in scalable_kinds
    assert "test_scalable_rvv_load_maskz_load_ui32_mask_zero_alternating" in values
    assert "test_scalable_rvv_load_mask_load_ui32_mask_merge_alternating" in values
    assert "test_scalable_rvv_store_mask_store_ui8_store_basic" in values
    assert "test_scalable_rvv_mul_ui64_rvv_basic_rvv" in values
    assert "test_scalable_rvv_mul_si64_rvv_edge_rvv" in values
    assert "test_scalable_rvv_mul_mask_mul_si32_rvv_mask_basic_rvv" in values
    assert "test_scalable_rvv_mul_maskz_mul_si32_rvv_maskz_basic_rvv" in values
    assert "tsl::load_maskz<Vec, true>(mask, memory.data() + 0);" in values
    assert "tsl::load_mask<Vec, true>(mask, memory.data() + 0, v1);" in values
    assert "tsl::store_mask<Vec, true>(mask, actual.data() + 0, v0);" in values
    assert "static constexpr bool has_static_lane_count_v = false;" in header
    assert "__riscv_vlenb() / sizeof(int32_t)" in header
    assert "__riscv_vlenb() / sizeof(uint32_t)" in header
    assert "rust/src/tsl_rvv.rs" not in artifacts
    assert rvv_project.emitted_profiles[0].supports_backend("cpp")
    assert not rvv_project.emitted_profiles[0].supports_backend("rust")

    cpp_verify = next(
        backend for backend in rvv_project.rendered.verify.backends
        if backend.backend_id == "cpp"
    ).profiles[0]
    assert cpp_verify.compiler_role == "riscv-cpp"
    assert cpp_verify.cmake_system_name == "Linux"
    assert cpp_verify.cmake_system_processor == "riscv64"
    assert not cpp_verify.pass_target_to_compiler
    assert cpp_verify.preflight_headers == ("riscv_vector.h",)



@pytest.fixture(scope="module")
def rvv_mask_project(data_root: Path, machine_profiles_path: Path):
    return _gen(
        data_root,
        machine_profiles_path,
        primitives=[
            "mask_false",
            "mask_true",
            "mask_binary_and",
            "mask_binary_or",
            "mask_binary_xor",
            "mask_binary_not",
            "equal",
            "nequal",
            "less_than",
            "greater_than",
            "less_than_or_equal",
            "greater_than_or_equal",
            "select",
        ],
        profiles=["rvv"],
        type_tags=[
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
        ],
        backends=["cpp"],
    )


def test_rvv_native_masks_comparisons_and_select_render_exact_intrinsics(
    rvv_mask_project,
) -> None:
    assert not has_errors(rvv_mask_project.diagnostics), rvv_mask_project.diagnostics
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in rvv_mask_project.artifacts.artifacts
    }
    header = artifacts["cpp/include/tsl_rvv.hpp"]
    helper = artifacts["cpp/include/tsl_test_rvv.hpp"]
    values = artifacts["cpp/tests/values_rvv.cpp"]

    for width in (8, 16, 32, 64):
        for stem in (
            "vmclr_m",
            "vmset_m",
            "vmand_mm",
            "vmor_mm",
            "vmxor_mm",
            "vmnot_m",
        ):
            assert f"__riscv_{stem}_b{width}" in header
    integer_types = (
        ("i8m1", 8, "vmslt", "vmsle"),
        ("u8m1", 8, "vmsltu", "vmsleu"),
        ("i16m1", 16, "vmslt", "vmsle"),
        ("u16m1", 16, "vmsltu", "vmsleu"),
        ("i32m1", 32, "vmslt", "vmsle"),
        ("u32m1", 32, "vmsltu", "vmsleu"),
        ("i64m1", 64, "vmslt", "vmsle"),
        ("u64m1", 64, "vmsltu", "vmsleu"),
    )
    for suffix, width, less, less_equal in integer_types:
        assert f"__riscv_vmseq_vv_{suffix}_b{width}" in header
        assert f"__riscv_vmsne_vv_{suffix}_b{width}" in header
        assert f"__riscv_{less}_vv_{suffix}_b{width}" in header
        assert f"__riscv_{less_equal}_vv_{suffix}_b{width}" in header
        assert f"__riscv_vmerge_vvm_{suffix}" in header
    for suffix, width in (("f32m1", 32), ("f64m1", 64)):
        for stem in ("vmfeq", "vmfne", "vmflt", "vmfle"):
            assert f"__riscv_{stem}_vv_{suffix}_b{width}" in header
        assert f"__riscv_vmerge_vvm_{suffix}" in header

    assert "::tsl::less_than<Vec>(right, left)" in header
    assert "::tsl::less_than_or_equal<Vec>(right, left)" in header
    assert "#include \"tsl_test_rvv.hpp\"" in values
    assert (
        "::tsl::test::mask_from_bits<tsl::simd<uint32_t, tsl::rvv>>" in values
    )
    assert "::tsl::test::check_mask_bits<tsl::simd<float, tsl::rvv>>" in values
    assert "__riscv_vid_v_u8m1" in helper
    assert "__riscv_vcpop_m_b64" in helper
