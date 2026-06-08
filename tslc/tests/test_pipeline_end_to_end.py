"""End-to-end: the pipeline emits the expected project tree and contents."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.diagnostics import has_errors


def _generate(data_root: Path):
    return generate_project(
        [data_root],
        primitives=["add", "sub"],
        extensions=["scalar", "avx2"],
        backends=["cpp", "rust"],
    )


def test_emits_expected_artifact_tree(data_root: Path) -> None:
    result = _generate(data_root)
    assert not has_errors(result.diagnostics), result.diagnostics
    paths = tuple(artifact.logical_path for artifact in result.artifacts.artifacts)
    assert paths == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/avx2.hpp",
        "cpp/include/profiles/scalar.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/avx2.rs",
        "rust/src/profiles/scalar.rs",
        "rust/tests/smoke.rs",
    )


def test_spot_check_generated_contents(data_root: Path) -> None:
    result = _generate(data_root)
    by_path = {a.logical_path: a.content for a in result.artifacts.artifacts}

    cpp_avx2 = by_path["cpp/include/profiles/avx2.hpp"]
    assert "#include <immintrin.h>" in cpp_avx2
    assert "inline __m256i add_avx2_si32(__m256i left, __m256i right)" in cpp_avx2
    assert "return _mm256_add_epi32(left, right);" in cpp_avx2

    rust_avx2 = by_path["rust/src/profiles/avx2.rs"]
    assert (
        "unsafe { core::arch::x86_64::_mm256_add_epi32(left, right) }" in rust_avx2
    )

    cpp_scalar = by_path["cpp/include/profiles/scalar.hpp"]
    assert "inline int32_t add_scalar_si32(int32_t left, int32_t right)" in cpp_scalar
    assert "return left + right;" in cpp_scalar


def test_coverage_lists_delivered_functions(data_root: Path) -> None:
    result = _generate(data_root)
    # 2 primitives x 10 types x 2 extensions x 2 backends = 80
    assert len(result.coverage) == 80
    names = {entry.function_name for entry in result.coverage}
    assert "add_avx2_si32" in names
    assert "sub_scalar_f64" in names
