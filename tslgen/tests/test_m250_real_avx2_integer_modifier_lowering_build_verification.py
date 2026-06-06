from __future__ import annotations

import ast
from pathlib import Path

from tslgen.domain.catalog import ExtensionCatalog, ExtensionName, TypeTag
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceLoader
from tslgen.pipeline import (
    SelectedPrimitiveBodyRenderEntry,
    SelectedPrimitiveProjectResult,
    build_primitive_project_artifacts_from_selected_bodies,
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
_FUNDAMENTAL_PATH = (
    _REPO_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
)
_PIPELINE_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "primitive_project_pipeline.py"
)
_TYPE_TAGS = ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64")
_SIGNED_SUFFIXES = {
    "8": "epi8",
    "16": "epi16",
    "32": "epi32",
    "64": "epi64",
}
_SIGNED_SUFFIX_BY_TYPE_TAG = {
    "si8": "epi8",
    "ui8": "epi8",
    "si16": "epi16",
    "ui16": "epi16",
    "si32": "epi32",
    "ui32": "epi32",
    "si64": "epi64",
    "ui64": "epi64",
}
_SELECTED_ADD_AVX2_INTEGER_MATRIX = tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name="add",
        selector_path=("avx2", "?i?"),
        extension="avx2",
        type_tag=type_tag,
        function_name=f"add_avx2_{type_tag}",
        parameters=("left", "right"),
    )
    for type_tag in _TYPE_TAGS
)


def test_m250_real_add_avx2_integer_matrix_uses_lowered_source_suffix_modifier() -> None:
    result = _build_real_add_avx2_integer_matrix()

    assert result.diagnostics == ()
    assert result.model is not None
    assert len(result.selections) == len(_TYPE_TAGS)
    assert {selection.primitive.name for selection in result.selections} == {"add"}
    assert {selection.extension for selection in result.selections} == {
        ExtensionName("avx2")
    }
    assert {selection.body_envelope.selector_path for selection in result.selections} == {
        ("avx2", "?i?")
    }
    assert {selection.type_tag for selection in result.selections} == {
        TypeTag(type_tag) for type_tag in _TYPE_TAGS
    }
    assert all("base::signed_of" in selection.payload_text for selection in result.selections)

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

    cpp_profile = by_path["cpp/include/profiles/avx2.hpp"]
    assert "#include <immintrin.h>" in cpp_profile
    rust_profile = by_path["rust/src/profiles/avx2.rs"]
    for type_tag, suffix in _SIGNED_SUFFIX_BY_TYPE_TAG.items():
        assert (
            f"inline __m256i add_avx2_{type_tag}(__m256i left, __m256i right) {{\n"
            f"  return _mm256_add_{suffix}(left, right);\n"
            "}"
        ) in cpp_profile
        assert f"pub fn add_avx2_{type_tag}(" in rust_profile
        assert (
            f"unsafe {{ core::arch::x86_64::_mm256_add_{suffix}(left, right) }}"
        ) in _function_text(rust_profile, f"add_avx2_{type_tag}")
        assert "?i?" not in cpp_profile
        assert "?i?" not in rust_profile

    for width, suffix in _SIGNED_SUFFIXES.items():
        cpp_call = f"_mm256_add_{suffix}(left, right)"
        rust_call = f"core::arch::x86_64::_mm256_add_{suffix}(left, right)"
        assert cpp_profile.count(cpp_call) == 2
        assert rust_profile.count(rust_call) == 2
        assert rust_profile.count(f"unsafe {{ {rust_call} }}") == 2
        assert f"_mm256_add_epu{width}" not in cpp_profile
        assert f"core::arch::x86_64::_mm256_add_epu{width}" not in rust_profile

    assert "core::arch::x86_64::core::arch::x86_64" not in rust_profile


def test_m250_real_add_avx2_integer_matrix_is_deterministic() -> None:
    first = _build_real_add_avx2_integer_matrix()
    second = _build_real_add_avx2_integer_matrix()

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m250_real_add_avx2_integer_matrix_generated_project_builds_cpp_and_rust(
    tmp_path: Path,
) -> None:
    result = _build_real_add_avx2_integer_matrix()

    assert result.diagnostics == ()
    assert result.model is not None

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


def test_m250_project_pipeline_keeps_integer_modifier_slice_generic_and_typed() -> None:
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
        "base::signed_of",
        "intrin_compose<add,",
        "real_avx2",
        "integer_modifier",
        "tslgenold",
    ):
        assert forbidden not in source
    for suffix in ("epi8", "epi16", "epi32", "epi64", "epu8", "epu16", "epu32", "epu64"):
        assert suffix not in source
    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )


def _build_real_add_avx2_integer_matrix() -> SelectedPrimitiveProjectResult:
    return build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        extension_catalog=_extension_catalog(),
        flag_catalog=_flag_catalog(),
        requested_profiles=("avx2",),
        selected_entries=_SELECTED_ADD_AVX2_INTEGER_MATRIX,
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
    return {artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts}


def _function_text(source: str, function_name: str) -> str:
    start = source.index(f"pub fn {function_name}(")
    next_function = source.find("\npub fn ", start + 1)
    if next_function == -1:
        return source[start:]
    return source[start:next_function]
