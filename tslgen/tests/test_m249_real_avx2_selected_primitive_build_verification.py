from __future__ import annotations

import ast
from pathlib import Path

from tslgen.domain.catalog import ExtensionCatalog, ExtensionName
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceLoader
from tslgen.pipeline import (
    SelectedPrimitiveBodyRenderEntry,
    SelectedPrimitiveProjectResult,
    build_primitive_project_artifacts_from_selected_body,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog
from tslgen.pipeline.build_verifier import (
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.syntax.parser import TslParser


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"
_LANGUAGE_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"
_TYPES_PATH = _REPO_ROOT / "tsldata" / "detail" / "types.tsl"
_EXTENSIONS_PATH = _REPO_ROOT / "tsldata" / "extensions" / "extension.tsl"
_FUNDAMENTAL_PATH = _REPO_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
_PIPELINE_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "primitive_project_pipeline.py"
)
_SELECTED_ADD_AVX2_F32 = SelectedPrimitiveBodyRenderEntry(
    primitive_name="add",
    selector_path=("avx2", "f?"),
    extension="avx2",
    type_tag="f32",
    function_name="add_avx2_f32",
    parameters=("left", "right"),
)


def test_m249_real_add_avx2_f32_generated_project_builds_cpp_and_rust(
    tmp_path: Path,
) -> None:
    result = _build_real_add_avx2_f32()

    assert result.diagnostics == ()
    assert result.model is not None
    assert result.selection is not None
    assert result.selection.primitive.name == "add"
    assert result.selection.extension == ExtensionName("avx2")
    assert result.selection.body_envelope.selector_path == ("avx2", "f?")
    assert result.selection.payload_text == "intrin_compose<add>(left, right)"

    by_path = _artifact_content_by_path(result)
    assert tuple(by_path) == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/avx2.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/avx2.rs",
        "rust/tests/smoke.rs",
    )
    assert "#include <immintrin.h>" in by_path["cpp/include/profiles/avx2.hpp"]
    assert "inline __m256 add_avx2_f32(__m256 left, __m256 right)" in (
        by_path["cpp/include/profiles/avx2.hpp"]
    )
    assert "  return _mm256_add_ps(left, right);" in (
        by_path["cpp/include/profiles/avx2.hpp"]
    )
    rust_profile = by_path["rust/src/profiles/avx2.rs"]
    assert "pub fn add_avx2_f32(" in rust_profile
    assert "left: core::arch::x86_64::__m256" in rust_profile
    assert "right: core::arch::x86_64::__m256" in rust_profile
    assert ") -> core::arch::x86_64::__m256" in rust_profile
    assert "unsafe { core::arch::x86_64::_mm256_add_ps(left, right) }" in rust_profile
    assert rust_profile.count("core::arch::x86_64::_mm256_add_ps(left, right)") == 1
    assert "core::arch::x86_64::core::arch::x86_64" not in rust_profile

    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        result.artifacts,
        output_root,
        mode="manifest-clean",
    )

    assert write_report.diagnostics == ()
    assert sorted(record.logical_path for record in write_report.written) == [
        artifact.logical_path for artifact in result.artifacts.artifacts
    ]

    report = verify_generated_project(
        output_root,
        result.model,
        policy=BuildVerificationPolicy(cxx_compiler="clang++"),
    )

    assert report.diagnostics == ()
    assert [
        (command.command.backend_id, command.command.profile_name, command.command.step)
        for command in report.commands
    ] == [
        ("cpp", "avx2", "configure"),
        ("cpp", "avx2", "build"),
        ("cpp", "avx2", "test"),
        ("rust", "avx2", "test"),
    ]
    assert all(command.returncode == 0 for command in report.commands)


def test_m249_project_pipeline_keeps_avx2_slice_generic_and_typed() -> None:
    source = _PIPELINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    for forbidden in (
        "_mm256_",
        "_mm256_add",
        "core::arch::x86_64::_mm256",
        "intrin_compose<add>",
        "real_avx2",
        "real_intrinsic",
        "tslgenold",
    ):
        assert forbidden not in source
    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )


def _build_real_add_avx2_f32() -> SelectedPrimitiveProjectResult:
    return build_primitive_project_artifacts_from_selected_body(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        extension_catalog=_extension_catalog(),
        flag_catalog=_flag_catalog(),
        requested_profiles=("avx2",),
        selected_entry=_SELECTED_ADD_AVX2_F32,
    )


def _source_documents():
    result = SourceLoader().load((_FUNDAMENTAL_PATH,))
    assert result.diagnostics == ()
    return result.documents


def _machine_profile_result():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.flag_catalog is not None
    return result


def _machine_profiles():
    return _machine_profile_result().catalog


def _flag_catalog():
    return _machine_profile_result().flag_catalog


def _backend_metadata():
    result = load_active_backend_metadata_catalog(_LANGUAGE_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _extension_catalog() -> ExtensionCatalog:
    source_result = SourceLoader().load((_TYPES_PATH, _EXTENSIONS_PATH))
    assert source_result.diagnostics == ()
    parse_result = TslParser().parse(source_result.documents)
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog.extensions


def _artifact_content_by_path(
    result: SelectedPrimitiveProjectResult,
) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
