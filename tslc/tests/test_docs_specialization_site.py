"""Specialization explorer schema and UI source guard tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tslc.api import generate_project


@pytest.fixture(scope="module")
def docs_specialization_result(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "mul",
            "hadd",
            "count_matches",
            "load",
            "store",
            "cast",
            "reinterpret",
            "less_than",
            "unequal_zero",
            "mask_true",
            "mask_binary_not",
            "mask_binary_and",
            "mask_population_count",
        ],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake", "neon", "sve"],
    )


@pytest.fixture(scope="module")
def docs_specialization_artifacts(docs_specialization_result) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in docs_specialization_result.artifacts.artifacts
    }


def test_specialization_explorer_data_contains_all_selected_specializations(
    docs_specialization_result,
    docs_specialization_artifacts: dict[str, str],
) -> None:
    payload = json.loads(
        docs_specialization_artifacts["docs/specializations/specializations.json"]
    )
    records = _decode_specialization_records(payload)
    strings = payload["strings"]

    assert payload["schema_version"] == 10
    assert "profiles" in payload
    assert "target_classes" in payload
    assert "backends" in payload
    assert "types" in payload
    assert "expressions" in payload
    assert "implementation_state" in payload["columns"]
    assert "target_class" in payload["columns"]
    assert "width_label" in payload["columns"]
    assert "extension_rank" in payload["columns"]
    assert "compiler_set" in payload["columns"]
    assert {strings[index] for index in payload["compilers"]} == {
        "AppleClang",
        "Clang",
    }
    assert sum(record["count"] for record in records) == len(
        docs_specialization_result.coverage
    )
    primitive_docs = {strings[row[0]]: row for row in payload["primitives"]}
    add_doc = primitive_docs["add"]
    add_signature = strings[add_doc[5]]
    add_expressions = {
        strings[row[0]]: {
            "label": strings[row[1]],
            "facade": strings[row[2]],
            "example": strings[row[3]],
        }
        for row in payload["expressions"][add_doc[6]]
    }
    add_cpp_facade = add_expressions["cpp"]["facade"]
    add_rust_facade = add_expressions["rust"]["facade"]
    add_cpp = add_expressions["cpp"]["example"]
    add_rust = add_expressions["rust"]["example"]
    assert add_signature == "(SIMD register, SIMD register) => SIMD register"
    assert add_cpp_facade == "tsl::add<Vec>(left, right) -> typename Vec::register_type"
    assert add_rust_facade == "add::<S>(left, right) -> S::RegisterType"
    assert "using Vec = tsl::simd<" in add_cpp
    assert "tsl::dataparallel::native" in add_cpp
    assert "tsl::dataparallel::fixed<" in add_cpp
    assert "tsl::dataparallel::generic<" in add_cpp
    assert "auto result = tsl::add<Vec>(left, right);" in add_cpp
    assert "use explicit extension identifier for the vector type" in add_cpp
    assert 'using "native" facade to select the available extension' in add_cpp
    assert "auto result = tsl::add<NativeVec>(left, right);" in add_cpp
    assert "auto result = tsl::add<FixedVec>(left, right);" in add_cpp
    assert "auto result = tsl::add<GenericVec>(left, right);" in add_cpp
    assert "type S = Simd<" in add_rust
    assert "dataparallel::Native" in add_rust
    assert "dataparallel::Fixed<" in add_rust
    assert "dataparallel::Generic<" in add_rust
    assert "let result = add::<S>(left, right);" in add_rust
    assert "type Profile = profile::algo::Profile;" in add_rust
    assert "<dataparallel::Fixed<8> as VectorFor<Profile, Value>>::Vec" in add_rust
    assert "let result = add::<NativeVec>(left, right);" in add_rust
    assert "let result = add::<FixedVec>(left, right);" in add_rust
    assert "let result = add::<GenericVec>(left, right);" in add_rust
    assert "VectorFor<profile::algo::Profile, Value>" not in add_rust
    load_doc = primitive_docs["load"]
    assert strings[load_doc[5]] == "(const pointer) => SIMD register"
    load_expressions = {
        strings[row[0]]: {
            "facade": strings[row[2]],
            "example": strings[row[3]],
        }
        for row in payload["expressions"][load_doc[6]]
    }
    assert "/* aligned */" in load_expressions["cpp"]["facade"]
    assert "/* aligned */" in load_expressions["cpp"]["example"]
    assert "/* aligned */" in load_expressions["rust"]["facade"]
    assert "/* aligned */" in load_expressions["rust"]["example"]
    assert any(
        record["backend"] == "cpp"
        and record["profile"] == "avx2"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
        and record["family"] == "x86"
        and record["target_class"] == "x86_256_bit"
        and record["type_tag"] == "si32"
        and record["register_type"] == "__m256i"
        and record["required_features"] == ["avx", "avx2"]
        and record["implementation_state"] == "native"
        and record["width_label"] == "256-bit"
        for record in records
    )
    profile_rows = {
        strings[row[0]]: {
            "family": strings[row[1]],
            "features": [strings[index] for index in payload["features"][row[2]]],
            "group_label": strings[row[6]],
            "summary": strings[row[8]],
            "tooltip": strings[row[9]],
            "sort_key": strings[row[10]],
        }
        for row in payload["profiles"]
    }
    assert {"avx512f", "avx512vl"} <= set(profile_rows["skylake"]["features"])
    assert profile_rows["skylake"]["family"] == "x86"
    assert profile_rows["skylake"]["group_label"] == "x86"
    assert profile_rows["skylake"]["summary"].startswith("x86 class")
    assert "Features: " in profile_rows["skylake"]["tooltip"]
    backend_rows = {
        strings[row[0]]: {"label": strings[row[1]], "rank": strings[row[2]]}
        for row in payload["backends"]
    }
    assert set(backend_rows) == {"cpp", "rust"}
    type_rows = {
        strings[row[0]]: {"short": strings[row[1]], "label": strings[row[2]]}
        for row in payload["types"]
    }
    assert type_rows["si32"] == {"short": "i32", "label": "signed int32"}
    target_class_rows = {
        strings[row[0]]: {
            "label": strings[row[1]],
            "family": strings[row[2]],
            "width": strings[row[3]],
            "sort_key": strings[row[4]],
        }
        for row in payload["target_classes"]
    }
    assert target_class_rows["x86_256_bit"] == {
        "label": "x86 256-bit",
        "family": "x86",
        "width": "256-bit",
        "sort_key": "10:0256:x86:256-bit",
    }
    assert target_class_rows["aarch64_128_bit"] == {
        "label": "aarch64 128-bit",
        "family": "aarch64",
        "width": "128-bit",
        "sort_key": "20:0128:aarch64:128-bit",
    }
    assert target_class_rows["aarch64_sve"] == {
        "label": "aarch64 SVE",
        "family": "aarch64",
        "width": "SVE",
        "sort_key": "20:9998:aarch64:SVE",
    }
    assert not any(key.startswith("arm_") for key in target_class_rows)
    assert any(
        record["profile"] == "skylake"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
        and record["type_tag"] == "si32"
        and record["required_features"] == ["avx", "avx2"]
        for record in records
    )
    assert any(
        record["backend"] == "cpp"
        and record["extension"] == "clang_v256"
        and record["compiler_ids"] == ["AppleClang", "Clang"]
        for record in records
    )
    assert any(
        record["profile"] == "skylake"
        and record["primitive"] == "add"
        and record["extension"] == "avx512"
        and record["type_tag"] == "si32"
        and record["required_features"] == ["avx512f"]
        for record in records
    )


def test_specialization_explorer_react_source_keeps_expected_views() -> None:
    app_source = (
        Path(__file__).parents[2]
        / "supplementary/docs/site/specializations/react/src/App.jsx"
    ).read_text(encoding="utf-8")

    assert 'import React, { useEffect, useMemo, useState } from "react";' in app_source
    assert "const [filtersOpen, setFiltersOpen] = useState(false);" in app_source
    assert "setActiveCell(null);" in app_source
    assert "function PrimitiveBrowser" in app_source
    assert "function PrimitiveHero" in app_source
    assert "function TypeHeatmap" in app_source
    assert "function Drilldown" in app_source
    assert "function ProfileRollup" in app_source
    assert "function DeveloperModeToggle" in app_source
    assert "developerToggle" in app_source
    assert "VITE_TSLC_GIT_BRANCH" in app_source
    assert "VITE_TSLC_GIT_HASH" in app_source
    assert "docMeta" in app_source
    assert 'src="../_static/tsl_repo_logo_wide.png"' in app_source
    assert 'className="brandLogo"' in app_source
    assert "signature: strings[signature]" in app_source
    assert "selectedBackend" in app_source
    assert "function LanguageSelector" in app_source
    assert "Expression language" in app_source
    assert "Callable facade" in app_source
    assert "facade: strings[facade]" in app_source
    assert "example: strings[example]" in app_source
    assert "facadeCode" in app_source
    assert "Target class x type heatmap" in app_source
    assert "Rows are architecture and vector-width classes. Columns are data types." in app_source
    assert "short dash repeats" in app_source
    assert "targetClassTooltip(targetClass)" in app_source
    assert "function profileFeatureTooltip" in app_source
    assert 'record.implementation_state === "native"' in app_source
    assert 'state: "yes", label: "nat"' in app_source
    assert 'state: "mixed", label: "part"' in app_source
    assert 'state: "no", label: "∅"' in app_source
    assert 'state: "degraded", label: "fb"' in app_source
    assert 'state: "degraded", label: "cmp"' in app_source
    assert "legendDegraded" in app_source
    assert '<details className="expressionBox">' in app_source
    assert "call example" in app_source
    assert "Expression" in app_source
    assert '<CodeBlock code={primitive.semantics} className="syntaxCode" />' in app_source
    assert "function CodeBlock" in app_source
    assert "function highlightCode" in app_source
    assert "codeTokenClass" in app_source
    assert (
        app_source.index("<PrimitiveHero")
        < app_source.index("<PrimitiveStatus")
        < app_source.index("<ProfileRollup")
        < app_source.index("<TypeHeatmap")
    )
    assert 'get("dev") === "1"' in app_source
    assert 'url.searchParams.set("dev", "1")' in app_source
    assert "TSL Primitive Specialization Reference" in app_source
    assert "Primitive support without misleading profile shortcuts" not in app_source
    assert "Profile capabilities and compiler availability are shown separately" in app_source
    assert "function typeLabel" in app_source
    assert "function targetWidthForRecord" not in app_source
    assert "record.target_class === targetClass.key" in app_source
    assert "activeCell?.targetClass === targetClass.key" in app_source
    assert "function targetClassSortKey" in app_source
    assert "function implementationTargetRank" in app_source
    assert "profileCapabilityGroup" not in app_source
    assert "implementation_state" in app_source
    assert "Selected implementation requirements are shown in the drilldown" in app_source
    assert "enabledRequirements" in app_source
    assert "enabledProfiles" in app_source
    assert "enabledCompilers" in app_source
    assert "recordCompilerVisible" in app_source
    assert "supportedCompilerRows" in app_source
    assert "compiler_ids.length > 0 || enabledProfiles" in app_source
    assert 'title="Compilers"' in app_source
    assert "function ProfileChipGroups" in app_source
    assert "function profileFilterGroups" in app_source
    assert "function profileSortKey" in app_source
    assert "function requirementsForProfiles" in app_source
    assert "function profileClassSummary" in app_source
    assert "setEnabledRequirements(requirementsForProfiles" in app_source
    assert "implementationState" in app_source
    assert "const BACKENDS" not in app_source
    assert "const TYPE_ORDER" not in app_source
    assert "X86_PROFILE_CLASSES" not in app_source
    assert "profileClassFromBaselines" not in app_source
    assert "implementationExtensionGroup" not in app_source
    assert "featureRankKey" not in app_source
    assert "extensionRank(" not in app_source
    assert "familyRank(" not in app_source
    assert "targetWidthForRecord" not in app_source
    assert "expressions?.cpp" not in app_source
    assert "expressions?.rust" not in app_source
    assert "expression.code" not in app_source
    assert "AVX" not in app_source
    assert "SSE" not in app_source
    assert "NEON" not in app_source
    assert "SVE" not in app_source
    assert "enabledFamilies" in app_source
    assert 'title="Profile"' in app_source
    assert 'title="Requirements"' in app_source
    assert 'title="Families"' in app_source
    assert 'typeTag !== "ptr"' not in app_source
    assert "enabledTargets" not in app_source
    assert "setEnabledTargets" not in app_source
    assert "SupportMatrix" not in app_source
    assert "supportMatrix" not in app_source
    assert "3D support matrix" not in app_source
    assert "getSupportValue" not in app_source

    styles = (
        Path(__file__).parents[2]
        / "supplementary/docs/site/specializations/react/src/styles.css"
    ).read_text(encoding="utf-8")
    assert "--primary: #2b608b;" in styles
    assert "--accent: #009ba4;" in styles
    assert "--highlight: #bccf00;" in styles
    assert "--focus: #84cfed;" in styles
    assert ".brandLogo" in styles
    assert ".syntaxCode .codeToken.keyword" in styles
    assert ".syntaxCode .codeToken.comment" in styles
    assert ".syntaxCode .codeToken.type" in styles


def _decode_specialization_records(payload: dict) -> list[dict]:
    strings = payload["strings"]
    feature_sets = [
        [strings[index] for index in feature_set]
        for feature_set in payload["features"]
    ]
    compiler_sets = [
        [strings[index] for index in compiler_set]
        for compiler_set in payload["compiler_sets"]
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
                    "target_class": strings[payload["target_classes"][row[4]][0]],
                    "type_tag": strings[row[5]],
                    "register_type": strings[row[6]],
                    "required_features": feature_sets[row[7]],
                    "safety": safeties[row[8]],
                    "implementation_state": strings[row[9]],
                    "width_label": strings[row[10]],
                    "width_rank": strings[row[11]],
                    "extension_group": strings[row[12]],
                    "extension_rank": strings[row[13]],
                    "family_rank": strings[row[14]],
                    "compiler_ids": compiler_sets[row[15]],
                    "count": row[16] if len(row) > 16 else 1,
                }
            )
    return records
