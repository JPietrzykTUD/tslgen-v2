"""End-to-end: the generated project uses the template/trait specialization layout."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.diagnostics import has_errors


def _generate(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )


def test_artifact_layout(data_root: Path, machine_profiles_path: Path) -> None:
    result = _generate(data_root, machine_profiles_path)
    assert not has_errors(result.diagnostics), result.diagnostics
    paths = {a.logical_path for a in result.artifacts.artifacts}
    # static cores, per-profile headers, top-level dispatch, per-profile smokes.
    assert {
        "cpp/include/tsl_core.hpp",
        "cpp/include/tsl_x86_traits.hpp",
        "cpp/include/tsl.hpp",
        "cpp/include/tsl_avx2.hpp",
        "cpp/include/tsl_scalar.hpp",
        "cpp/tests/smoke_avx2.cpp",
        "rust/src/tsl_core.rs",
        "rust/src/tsl_avx2.rs",
        "rust/src/lib.rs",
    } <= paths


def test_cpp_specialization_structure(data_root: Path, machine_profiles_path: Path) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    avx2 = by["cpp/include/tsl_avx2.hpp"]
    # primary template, the avx2 si32 specialization, an sse specialization in the
    # same profile header, and the generic wrapper.
    assert "template <class Vec>\nstruct add_impl;" in avx2
    assert "struct add_impl<tsl::simd<int32_t, tsl::avx2>>" in avx2
    assert "return _mm256_add_epi32(left, right);" in avx2
    assert "struct add_impl<tsl::simd<int32_t, tsl::sse>>" in avx2
    assert "return _mm_add_epi32(left, right);" in avx2
    assert "inline typename Vec::register_type add(" in avx2
    # hadd is scalar-returning (s:=v) and picks the f64 body.
    assert "inline typename Vec::base_type hadd(" in avx2
    assert "struct hadd_impl<tsl::simd<double, tsl::avx2>>" in avx2


def test_rust_specialization_structure(data_root: Path, machine_profiles_path: Path) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    avx2 = by["rust/src/tsl_avx2.rs"]
    assert "pub trait AddImpl: SimdVector {" in avx2
    assert "impl AddImpl for Simd<i32, Avx2> {" in avx2
    assert "unsafe { return core::arch::x86_64::_mm256_add_epi32(left, right); }" in avx2
    assert "impl AddImpl for Simd<i32, Sse> {" in avx2
    assert "pub fn add<S: AddImpl>(" in avx2


def test_avx_profile_falls_back_to_sse_for_integers(
    data_root: Path, machine_profiles_path: Path
) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    avx = by["cpp/include/tsl_avx.hpp"]
    # avx lacks the avx2 flag, so 256-bit integer add is NOT specialized...
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" not in avx
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in avx
    # ...but 256-bit float add only needs `avx`, so it IS present.
    assert "add_impl<tsl::simd<float, tsl::avx2>>" in avx


def test_skylake_uses_vl_and_avx512_not_base(
    data_root: Path, machine_profiles_path: Path
) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    sky = by["cpp/include/tsl_skylake.hpp"]
    # avx512vl present -> the avx512vl-aware bodies are selected, but they are
    # emitted under the *ISA* names (avx2/sse), never the internal `_vl` tags.
    assert "_vl" not in sky
    assert "add_impl<tsl::simd<int32_t, tsl::avx512>>" in sky
    assert "return _mm512_add_epi32(left, right);" in sky
    # avx2 here is the avx2_vl-selected body (inherits avx2's), emitted as avx2.
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" in sky
    assert "return _mm256_add_epi32(left, right);" in sky
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in sky


def test_coverage_counts_specializations(data_root: Path, machine_profiles_path: Path) -> None:
    result = _generate(data_root, machine_profiles_path)
    keys = {(c.profile, c.extension, c.primitive, c.type_tag) for c in result.coverage}
    assert ("avx2", "avx2", "add", "si32") in keys
    assert ("avx2", "avx2", "hadd", "f64") in keys
    assert ("scalar", "scalar", "add", "f64") in keys
