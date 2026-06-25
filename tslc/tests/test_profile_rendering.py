"""Backend selection, profile-name sanitization, and feature-flag spelling."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.catalog.machine_profiles import load_machine_profiles_checked
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
    assert "cpp/include/tsl_neon.hpp" in {
        artifact.logical_path for artifact in result.artifacts.artifacts
    }
