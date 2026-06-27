"""Backend selection, profile-name sanitization, and feature-flag spelling."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.render.cpp_project import cpp_flags
from tslc.render._common import slug


def _roots(result) -> set[str]:
    return {a.logical_path.split("/")[0] for a in result.artifacts.artifacts}


def _gen(data_root, mp, **kw):
    return generate_project([data_root], machine_profiles_path=mp, **kw)


def test_backend_selection_is_honored(data_root: Path, machine_profiles_path: Path) -> None:
    rust_only = _gen(
        data_root, machine_profiles_path, primitives=["add"], profiles=["avx2"], backends=["rust"]
    )
    assert _roots(rust_only) == {"rust"}

    cpp_only = _gen(
        data_root, machine_profiles_path, primitives=["add"], profiles=["avx2"], backends=["cpp"]
    )
    assert _roots(cpp_only) == {"cpp"}
    # verify description only covers the requested backend
    assert [b.backend_id for b in cpp_only.rendered.verify.backends] == ["cpp"]


def test_profile_name_sanitized_to_valid_identifiers(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _gen(
        data_root, machine_profiles_path, primitives=["add"], profiles=["icelake-rockerlake"]
    )
    by = {a.logical_path: a.content for a in result.artifacts.artifacts}
    # No raw hyphen leaks into any generated C++ or Rust source.
    for path, content in by.items():
        if path.endswith((".hpp", ".cpp", ".rs")):
            assert "icelake-rockerlake" not in content, path
    assert "#if defined(TSL_PROFILE_ICELAKE_ROCKERLAKE)" in by["cpp/include/tsl.hpp"]
    assert "cpp/include/tsl_icelake_rockerlake.hpp" in by
    assert "pub mod tsl_icelake_rockerlake;" in by["rust/src/lib.rs"]
    assert "icelake_rockerlake = []" in by["rust/Cargo.toml"]


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


def test_cpp_profile_flags_are_profile_owned() -> None:
    profile = MachineProfile(
        name="sve",
        family="aarch64",
        features=frozenset({"sve"}),
        alternatives={},
        cpp_flags=("-march=armv8-a+sve",),
    )

    assert cpp_flags(profile) == ("-march=armv8-a+sve",)


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
    assert neon_profile.cpp_target == "aarch64-linux-gnu"
    assert neon_profile.cpp_flags == ()
    assert neon_profile.emulator is not None
    assert neon_profile.emulator.kind == "qemu-aarch64"
    assert neon_profile.emulator.profile == "cortex-a76"
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
    assert "#include <arm_neon.h>" in cpp
    assert "struct neon {};" in cpp
    assert "struct simd<int32_t, neon>" in cpp
    assert "using register_type = int32x4_t;" in cpp
    assert "return vaddq_s32(left, right);" in cpp

    rust = by_path["rust/src/tsl_neon.rs"]
    assert "use core::arch::aarch64::*;" in rust
    assert "pub struct Neon;" in rust
    assert "impl SimdVector for Simd<i32, Neon>" in rust
    assert "type RegisterType = core::arch::aarch64::int32x4_t;" in rust
    assert "return core::arch::aarch64::vaddq_s32(left, right);" in rust


def test_sve_profile_registers_scalable_cpp_simd_types(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["add"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}

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
    assert "return svadd_s32_x(::tsl::mask_true<Vec>(), left, right);" in cpp
    assert 'if(TSL_PROFILE STREQUAL "sve")' in cmake
    assert "target_compile_options(tsl_smoke PRIVATE -mcpu=a64fx)" in cmake
    assert any(
        case.kind == "scalable_golden" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert any(
        case.kind == "scalable_masked" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "using Vec = tsl::simd<int32_t, tsl::sve>;" in values
    assert '#include "tsl_test_sve.hpp"' in values
    assert "svcntb() / sizeof(int32_t)" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "tsl::load<Vec, false>" in values
    assert "tsl::store<Vec, false>" in values
    assert "sve_mask_from_bits" not in test_core
    assert "arm_sve.h" not in test_core
    assert "sve_mask_from_bits" in test_sve
    assert "#include <arm_sve.h>" in test_sve


def test_sve_profile_plans_scalable_mask_result_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["equal"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_result" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_equal_equal_si32_basic" in values
    assert "::tsl::test::check_sve_mask_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::equal<Vec>(v0, v1);" in values


def test_sve_profile_plans_scalable_masked_mask_result_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["equal"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_masked_mask_result" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_equal_maskz" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "::tsl::test::check_sve_mask_bits<tsl::simd<int32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::equal_maskz<Vec>(m0, v0, v1);" in values


def test_sve_profile_plans_scalable_mask_logic_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["mask_binary_and"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_logic" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_mask_binary_and" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "::tsl::test::check_sve_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::mask_binary_and<Vec>(m0, m1);" in values


def test_sve_profile_plans_scalable_mask_constant_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["mask_true", "mask_false"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_constant" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_mask_true" in values
    assert "test_scalable_sve_mask_false" in values
    assert "::tsl::test::check_sve_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type result = tsl::mask_true<Vec>();" in values
    assert "typename Vec::mask_type result = tsl::mask_false<Vec>();" in values


def test_sve_profile_plans_scalable_mask_conversion_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["to_integral", "to_mask"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_conversion" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_to_integral" in values
    assert "test_scalable_sve_to_mask" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "::tsl::test::check_sve_mask_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::mask_type input = " in values
    assert "typename Vec::imask_type input = " in values
    assert "typename Vec::imask_type result = tsl::to_integral<Vec>(input);" in values
    assert "typename Vec::mask_type result = tsl::to_mask<Vec>(input);" in values


def test_sve_profile_plans_scalable_mask_to_vector_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["to_vector"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_masked" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_to_vector" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "typename Vec::register_type result = tsl::to_vector<Vec>(mask);" in values
    assert "tsl::store<Vec, false>(actual.data(), result);" in values


def test_sve_profile_plans_scalable_mask_store_values(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _gen(
        data_root,
        machine_profiles_path,
        primitives=["store_mask_repr"],
        profiles=["sve"],
        backends=["cpp"],
        test_harness=True,
    )
    assert result.rendered is not None
    by_path = {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}
    values = by_path["cpp/tests/values_sve.cpp"]

    assert any(
        case.kind == "scalable_mask_store" and case.source_extension == "sve"
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert "test_scalable_sve_store_mask_repr" in values
    assert "::tsl::test::sve_mask_from_bits<tsl::simd<uint32_t, tsl::sve>>" in values
    assert "std::vector<uint32_t> actual(1 + lanes);" in values
    assert "tsl::store_mask_repr<Vec, false, false>(" in values
    assert "reinterpret_cast<typename Vec::base_type *>(actual.data() + 1), mask);" in values
