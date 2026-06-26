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
