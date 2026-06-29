"""End-to-end: the generated project uses the template/trait specialization layout."""

from __future__ import annotations

import json
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


def test_rust_specialization_structure(data_root: Path, machine_profiles_path: Path) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    avx2 = by["rust/src/tsl_avx2.rs"]
    assert "pub trait AddImpl: SimdVector {" in avx2
    assert "impl AddImpl for Simd<i32, Avx2> {" in avx2
    assert "unsafe { return core::arch::x86_64::_mm256_add_epi32(left, right); }" in avx2
    assert "impl AddImpl for Simd<i32, Sse> {" in avx2
    assert "pub fn add<S: AddImpl>(" in avx2
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
    data_root: Path, machine_profiles_path: Path
) -> None:
    by = {
        a.logical_path: a.content
        for a in _generate(data_root, machine_profiles_path).artifacts.artifacts
    }
    facade = by["cpp/docs/input/tsl_api_docs.hpp"]

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
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _generate(data_root, machine_profiles_path)
    by = {a.logical_path: a.content for a in result.artifacts.artifacts}
    payload = json.loads(by["docs/specializations/specializations.json"])
    records = _decode_specialization_records(payload)

    assert payload["schema_version"] == 2
    assert sum(record["count"] for record in records) == len(result.coverage)
    assert any(
        record["backend"] == "cpp"
        and record["profile"] == "avx2"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
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
    assert "<SupportMatrix" in app_source
    assert app_source.index("<PrimitiveDocumentation") < app_source.index("<SupportMatrix")
    assert "3D support matrix" in app_source
    assert "function typeLabel" in app_source
    assert "function targetWidthForRecord" in app_source
    assert "function uniqueMatrixTargets" in app_source
    assert "record.matrixTargetKey === target.key" in app_source
    assert "getSupportValue" not in app_source


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


def test_cast_lowers_integer_reductions(data_root: Path, machine_profiles_path: Path) -> None:
    by = {a.logical_path: a.content for a in _generate(data_root, machine_profiles_path).artifacts.artifacts}
    sky_cpp = by["cpp/include/tsl_skylake.hpp"]
    sky_rust = by["rust/src/tsl_skylake.rs"]
    # hadd's avx512 integer reduction casts the result to the base type:
    # cast<static>(type<generation>(base::in), intrin<reduce_add, build[...]>(vec)).
    assert "static_cast<int32_t>(_mm512_reduce_add_epi32(vec))" in sky_cpp
    assert "(core::arch::x86_64::_mm512_reduce_add_epi32(vec)) as i32" in sky_rust


def test_coverage_counts_specializations(data_root: Path, machine_profiles_path: Path) -> None:
    result = _generate(data_root, machine_profiles_path)
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
                    "type_tag": strings[row[3]],
                    "register_type": strings[row[4]],
                    "required_features": feature_sets[row[5]],
                    "safety": safeties[row[6]],
                    "count": row[7] if len(row) > 7 else 1,
                }
            )
    return records
