"""End-to-end: the generated project uses the template/trait specialization layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.diagnostics import has_errors


def _generate(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )


@pytest.fixture(scope="module")
def specialization_result(data_root: Path, machine_profiles_path: Path):
    return _generate(data_root, machine_profiles_path)


@pytest.fixture(scope="module")
def specialization_artifacts(specialization_result) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in specialization_result.artifacts.artifacts
    }


def test_artifact_layout(specialization_result) -> None:
    result = specialization_result
    assert not has_errors(result.diagnostics), result.diagnostics
    paths = {a.logical_path for a in result.artifacts.artifacts}
    # static cores, per-profile headers, top-level dispatch, per-profile smokes.
    assert {
        "cpp/include/tsl_core.hpp",
        "cpp/include/tsl_inferred_simd.hpp",
        "cpp/include/tsl_algorithm.hpp",
        "cpp/include/tsl_x86_traits.hpp",
        "cpp/include/tsl.hpp",
        "cpp/include/tsl_avx2.hpp",
        "cpp/include/tsl_scalar.hpp",
        "cpp/docs/input/tsl_api_docs.hpp",
        "docs/specializations/specializations.json",
        "cpp/tests/smoke_avx2.cpp",
        "rust/src/tsl_core.rs",
        "rust/src/tsl_avx2.rs",
        "rust/src/lib.rs",
    } <= paths
    assert "docs/specializations/index.html" not in paths
    assert "docs/specializations/app.js" not in paths
    assert "docs/specializations/styles.css" not in paths


def test_cpp_core_vectors_expose_metadata_constants(
    specialization_artifacts: dict[str, str]
) -> None:
    core = specialization_artifacts["cpp/include/tsl_core.hpp"]

    assert "static constexpr bool has_static_lane_count_v = true;" in core
    assert "static constexpr std::size_t lane_count_v = 1;" in core
    assert "static constexpr std::size_t lane_count_v = LANES;" in core
    assert "static constexpr std::size_t lane_count() noexcept" in core
    assert "static constexpr std::size_t simd_register_alignment_v = alignof(T);" in core
    assert (
        "static constexpr std::size_t simd_register_alignment_v = alignof(register_type);"
        in core
    )


def test_cpp_inferred_simd_helper_has_generic_fallback(
    specialization_artifacts: dict[str, str]
) -> None:
    helper = specialization_artifacts["cpp/include/tsl_inferred_simd.hpp"]

    assert "template <class T, std::size_t ParallelN>" in helper
    assert "using type = ::tsl::simd<T, ::tsl::generic<ParallelN>>;" in helper
    assert "struct inferred_simd<T, 1>" in helper
    assert "using type = ::tsl::simd<T, ::tsl::scalar>;" in helper
    assert "struct native_simd" in helper
    assert "using native_simd_t = typename detail::native_simd" in helper
    assert "using inferred_simd_t = typename detail::inferred_simd" in helper
    assert "tsl::avx2" not in helper
    assert "tsl::sse" not in helper


def test_cpp_algorithm_helper_is_shipped_through_dispatch_header(
    specialization_artifacts: dict[str, str]
) -> None:
    helper = specialization_artifacts["cpp/include/tsl_algorithm.hpp"]
    dispatch = specialization_artifacts["cpp/include/tsl.hpp"]
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]

    assert "namespace tsl::algo" in helper
    assert "template <class Vec>\nstruct vector_tag" in helper
    assert "namespace parallelism" in helper
    assert "struct native" in helper
    assert "struct fixed" in helper
    assert "parallelism::fixed<N> requires N > 0" in helper
    assert "vector_for_parallelism<parallelism::native" in helper
    assert "class Alignment = alignment::detect" in helper
    assert "void transform_unary(Op&& op" in helper
    assert "std::size_t ParallelN" in helper
    assert "transform_unary<parallelism::fixed<ParallelN>, Alignment>" in helper
    assert "void transform_binary(" in helper
    assert "transform_binary_loop" in helper
    assert "transform_binary<parallelism::fixed<ParallelN>, Alignment>" in helper
    assert '#include "tsl_algorithm.hpp"' in dispatch
    assert "inline typename Vec::register_type load(" in avx2
    assert "inline void store(" in avx2


def test_cpp_specialization_structure(specialization_artifacts: dict[str, str]) -> None:
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]
    # primary template, the avx2 si32 specialization, an sse specialization in the
    # same profile header, and the generic wrapper.
    assert "template <class Vec>\nstruct add_impl;" in avx2
    assert (
        "static constexpr std::size_t lane_count_v = 256 / (sizeof(T) * 8);"
        in avx2
    )
    assert "struct add_impl<tsl::simd<int32_t, tsl::avx2>>" in avx2
    assert "return _mm256_add_epi32(left, right);" in avx2
    assert "struct add_impl<tsl::simd<int32_t, tsl::sse>>" in avx2
    assert "return _mm_add_epi32(left, right);" in avx2
    assert "inline typename Vec::register_type add(" in avx2
    assert "@brief [Example: sse + si8]: Add packed 8-bit integers" in avx2
    assert "@par Semantics" in avx2
    assert "@par API" in avx2
    assert "- Template parameters: Vec selects the SIMD vector type" in avx2
    assert "- Returns: SIMD register (typename Vec::register_type)" in avx2
    assert "- Parameters: left: SIMD register; right: SIMD register" in avx2
    assert "@par Specialization" in avx2
    assert "- Extension: avx2" in avx2
    assert "- Element type: int32_t" in avx2
    assert "- Register type: __m256i" in avx2
    assert "- Context:" not in avx2
    assert "- Result kind:" not in avx2
    assert "- Parameter kinds:" not in avx2
    # hadd is scalar-returning (s:=v) and picks the f64 body.
    assert "inline typename Vec::base_type hadd(" in avx2
    assert "struct hadd_impl<tsl::simd<double, tsl::avx2>>" in avx2


def test_cpp_profile_specializes_inferred_simd_from_registered_vectors(
    specialization_artifacts: dict[str, str]
) -> None:
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]

    assert "struct inferred_simd<int32_t, 1>" in avx2
    assert "using type = ::tsl::simd<int32_t, ::tsl::scalar>;" in avx2
    assert "struct inferred_simd<int32_t, 4>" in avx2
    assert "using type = ::tsl::simd<int32_t, ::tsl::sse>;" in avx2
    assert "struct inferred_simd<int32_t, 8>" in avx2
    assert "using type = ::tsl::simd<int32_t, ::tsl::avx2>;" in avx2
    assert "struct inferred_simd<float, 4>" in avx2
    assert "using type = ::tsl::simd<float, ::tsl::sse>;" in avx2
    assert "struct inferred_simd<float, 8>" in avx2
    assert "using type = ::tsl::simd<float, ::tsl::avx2>;" in avx2
    assert "struct native_simd<int32_t>" in avx2
    assert (
        "struct native_simd<int32_t> {\n"
        "    using type = ::tsl::simd<int32_t, ::tsl::avx2>;"
        in avx2
    )
    assert "struct native_simd<float>" in avx2
    assert (
        "struct native_simd<float> {\n"
        "    using type = ::tsl::simd<float, ::tsl::avx2>;"
        in avx2
    )


def test_rust_specialization_structure(specialization_artifacts: dict[str, str]) -> None:
    avx2 = specialization_artifacts["rust/src/tsl_avx2.rs"]
    core = specialization_artifacts["rust/src/tsl_core.rs"]

    assert "pub trait StaticSimdVector: SimdVector" in core
    assert "fn lane_count() -> usize;" in core
    assert "const ELEMENT_COUNT: usize;" in core
    assert "const ELEMENT_COUNT: usize = 1;" in core
    assert "const ELEMENT_COUNT: usize = LANES;" in core
    assert "const ALIGN: usize;" in core
    assert "const ALIGN: usize = core::mem::align_of::<T>();" in core
    assert (
        "const ALIGN: usize = core::mem::align_of::<array_type<T, LANES>>();"
        in core
    )
    assert "pub trait AddImpl: StaticSimdVector {" in avx2
    assert "impl AddImpl for Simd<i32, Avx2> {" in avx2
    assert "impl StaticSimdVector for Simd<i32, Avx2>" in avx2
    assert "const ELEMENT_COUNT: usize = 8;" in avx2
    assert "fn lane_count() -> usize { 8 }" in avx2
    assert "const ALIGN: usize = 32;" in avx2
    assert "unsafe { return core::arch::x86_64::_mm256_add_epi32(left, right); }" in avx2
    assert "impl AddImpl for Simd<i32, Sse> {" in avx2
    assert "pub mod detail {\n    pub mod primitives {" in avx2
    assert "pub fn add<S: detail::primitives::AddImpl>(" in avx2
    assert '/// [Example: sse + si8]: Add packed 8-bit integers' in avx2
    assert "/// # Semantics" in avx2
    assert "/// # API" in avx2
    assert "/// - Type parameters: S selects the SIMD vector type" in avx2
    assert "/// - Returns: SIMD register (S::RegisterType)" in avx2
    assert "/// - Parameters: left: SIMD register; right: SIMD register" in avx2
    assert "/// # Specialization" in avx2
    assert "/// - Extension: avx2" in avx2
    assert "/// - Element type: i32" in avx2
    assert "/// - Register type: core::arch::x86_64::__m256i" in avx2
    assert "/// - Context:" not in avx2
    assert "/// - Result kind:" not in avx2
    assert "/// - Parameter kinds:" not in avx2


def test_cpp_documentation_facade_contains_api_declarations_only(
    specialization_artifacts: dict[str, str],
) -> None:
    facade = specialization_artifacts["cpp/docs/input/tsl_api_docs.hpp"]

    assert "namespace tsl {" in facade
    assert "template <class Vec>" in facade
    assert "typename Vec::register_type add(" in facade
    assert "return _mm256_add_epi32" not in facade
    assert '#include "tsl_avx2.hpp"' not in facade
    assert '#include "tsl.hpp"' not in facade
    assert "namespace specializations" not in facade
    assert "void doc_avx2_add_avx2_si32_" not in facade
    assert "- Profile: avx2" not in facade


def test_specialization_explorer_data_contains_all_selected_specializations(
    specialization_result,
    specialization_artifacts: dict[str, str],
) -> None:
    payload = json.loads(specialization_artifacts["docs/specializations/specializations.json"])
    records = _decode_specialization_records(payload)

    assert payload["schema_version"] == 3
    assert sum(record["count"] for record in records) == len(specialization_result.coverage)
    assert any(
        record["backend"] == "cpp"
        and record["profile"] == "avx2"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
        and record["family"] == "x86"
        and record["type_tag"] == "si32"
        and record["register_type"] == "__m256i"
        and record["required_features"] == ["avx", "avx2"]
        for record in records
    )
    app_source = (
        Path(__file__).parents[2]
        / "supplementary/docs/site/specializations/react/src/App.jsx"
    ).read_text(encoding="utf-8")
    assert 'import React, { useEffect, useMemo, useState } from "react";' in app_source
    assert "const [filtersOpen, setFiltersOpen] = useState(false);" in app_source
    assert "current === primitive.name ? null : primitive.name" in app_source
    assert "☰" in app_source
    assert "←" in app_source
    assert "▾" in app_source
    assert "▸" in app_source
    assert "function PrimitiveList" in app_source
    assert "<SpecializationSummary" in app_source
    assert "<SpecializationInventory" in app_source
    assert (
        app_source.index("<PrimitiveDocumentation")
        < app_source.index("<SpecializationSummary")
        < app_source.index("<SpecializationInventory")
    )
    assert "SIMD Specialization Inventory" in app_source
    assert "function typeLabel" in app_source
    assert "function targetWidthForRecord" in app_source
    assert "function groupInventory" in app_source
    assert "function aggregateInventoryRows" in app_source
    assert "record.displayTargetKey" in app_source
    assert "enabledRequirements" in app_source
    assert "enabledFamilies" in app_source
    assert 'title="Requirements"' in app_source
    assert 'title="Families"' in app_source
    assert 'typeTag !== "ptr"' in app_source
    assert "enabledTargets" not in app_source
    assert "setEnabledTargets" not in app_source
    assert "SupportMatrix" not in app_source
    assert "supportMatrix" not in app_source
    assert "3D support matrix" not in app_source
    assert "getSupportValue" not in app_source


def test_avx_profile_falls_back_to_sse_for_integers(
    specialization_artifacts: dict[str, str],
) -> None:
    avx = specialization_artifacts["cpp/include/tsl_avx.hpp"]
    # avx lacks the avx2 flag, so 256-bit integer add is NOT specialized...
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" not in avx
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in avx
    # ...but 256-bit float add only needs `avx`, so it IS present.
    assert "add_impl<tsl::simd<float, tsl::avx2>>" in avx


def test_skylake_uses_vl_and_avx512_not_base(
    specialization_artifacts: dict[str, str],
) -> None:
    sky = specialization_artifacts["cpp/include/tsl_skylake.hpp"]
    # avx512vl present -> the avx512vl-aware bodies are selected, but they are
    # emitted under the *ISA* names (avx2/sse), never the internal `_vl` tags.
    assert "_vl" not in sky
    assert "add_impl<tsl::simd<int32_t, tsl::avx512>>" in sky
    assert "return _mm512_add_epi32(left, right);" in sky
    # avx2 here is the avx2_vl-selected body (inherits avx2's), emitted as avx2.
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" in sky
    assert "return _mm256_add_epi32(left, right);" in sky
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in sky


def test_cast_lowers_integer_reductions(specialization_artifacts: dict[str, str]) -> None:
    sky_cpp = specialization_artifacts["cpp/include/tsl_skylake.hpp"]
    sky_rust = specialization_artifacts["rust/src/tsl_skylake.rs"]
    # hadd's avx512 integer reduction casts the result to the base type:
    # cast<static>(type(base::in), intrin<reduce_add, build[...]>(vec)).
    assert "static_cast<int32_t>(_mm512_reduce_add_epi32(vec))" in sky_cpp
    assert "(core::arch::x86_64::_mm512_reduce_add_epi32(vec)) as i32" in sky_rust


def test_coverage_counts_specializations(specialization_result) -> None:
    result = specialization_result
    keys = {(c.profile, c.extension, c.primitive, c.type_tag) for c in result.coverage}
    assert ("avx2", "avx2", "add", "si32") in keys
    assert ("avx2", "avx2", "hadd", "f64") in keys
    assert ("scalar", "scalar", "add", "f64") in keys


def _decode_specialization_records(payload: dict) -> list[dict]:
    strings = payload["strings"]
    feature_sets = [
        [strings[index] for index in feature_set]
        for feature_set in payload["features"]
    ]
    safeties = [
        {
            "caller_unsafe": caller,
            "internal_unsafe": internal,
            "reasons": [strings[index] for index in reasons],
        }
        for caller, internal, reasons in payload["safeties"]
    ]
    records: list[dict] = []
    for primitive, rows in payload["specialization_groups"]:
        for row in rows:
            records.append(
                {
                    "primitive": strings[primitive],
                    "backend": strings[row[0]],
                    "profile": strings[row[1]],
                    "extension": strings[row[2]],
                    "family": strings[row[3]],
                    "type_tag": strings[row[4]],
                    "register_type": strings[row[5]],
                    "required_features": feature_sets[row[6]],
                    "safety": safeties[row[7]],
                    "count": row[8] if len(row) > 8 else 1,
                }
            )
    return records
