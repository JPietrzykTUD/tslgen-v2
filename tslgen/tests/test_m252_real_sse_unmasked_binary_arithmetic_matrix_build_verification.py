from __future__ import annotations

import ast
from pathlib import Path

from tslgen.domain.catalog import ExtensionCatalog, TypeTag
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
_INTEGER_TYPE_TAGS = ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64")
_FLOAT_TYPE_TAGS = ("f32", "f64")
_SIGNED_INTEGER_SUFFIX_BY_TYPE_TAG = {
    "si8": "epi8",
    "ui8": "epi8",
    "si16": "epi16",
    "ui16": "epi16",
    "si32": "epi32",
    "ui32": "epi32",
    "si64": "epi64",
    "ui64": "epi64",
}
_FLOAT_SUFFIX_BY_TYPE_TAG = {
    "f32": "ps",
    "f64": "pd",
}
_REGISTER_TYPE_BY_TYPE_TAG = {
    "f32": ("__m128", "core::arch::x86_64::__m128"),
    "f64": ("__m128d", "core::arch::x86_64::__m128d"),
    **{
        type_tag: ("__m128i", "core::arch::x86_64::__m128i")
        for type_tag in _INTEGER_TYPE_TAGS
    },
}
_SELECTED_SSE_UNMASKED_BINARY_ARITHMETIC_MATRIX = tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name=primitive_name,
        selector_path=("sse", "?i?"),
        extension="sse",
        type_tag=type_tag,
        function_name=f"{primitive_name}_sse_{type_tag}",
        parameters=("left", "right"),
    )
    for primitive_name in ("add", "sub")
    for type_tag in _INTEGER_TYPE_TAGS
) + tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name=primitive_name,
        selector_path=("sse", type_tag),
        extension="sse",
        type_tag=type_tag,
        function_name=f"{primitive_name}_sse_{type_tag}",
        parameters=("left", "right"),
    )
    for primitive_name in ("add", "sub")
    for type_tag in _FLOAT_TYPE_TAGS
)


def test_m252_real_sse_unmasked_binary_arithmetic_matrix_renders_typed_calls() -> None:
    result = _build_real_sse_unmasked_binary_arithmetic_matrix()

    assert result.diagnostics == ()
    assert result.model is not None
    assert len(result.selections) == len(_SELECTED_SSE_UNMASKED_BINARY_ARITHMETIC_MATRIX)
    assert {selection.primitive.name for selection in result.selections} == {"add", "sub"}
    assert {selection.body_envelope.selector_path for selection in result.selections} == {
        ("sse", "?i?"),
        ("sse", "f32"),
        ("sse", "f64"),
    }
    assert {selection.type_tag for selection in result.selections} == {
        TypeTag(type_tag) for type_tag in (*_INTEGER_TYPE_TAGS, *_FLOAT_TYPE_TAGS)
    }

    by_path = _artifact_content_by_path(result)
    assert tuple(by_path) == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/sse2.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/sse2.rs",
        "rust/tests/smoke.rs",
    )

    cpp_profile = by_path["cpp/include/profiles/sse2.hpp"]
    rust_profile = by_path["rust/src/profiles/sse2.rs"]
    assert "#include <immintrin.h>" in cpp_profile

    for primitive_name in ("add", "sub"):
        for type_tag, suffix in _SIGNED_INTEGER_SUFFIX_BY_TYPE_TAG.items():
            _assert_cpp_function(
                cpp_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type="__m128i",
                call=f"_mm_{primitive_name}_{suffix}(left, right)",
            )
            _assert_rust_function(
                rust_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type="core::arch::x86_64::__m128i",
                call=f"core::arch::x86_64::_mm_{primitive_name}_{suffix}(left, right)",
            )

        for type_tag, suffix in _FLOAT_SUFFIX_BY_TYPE_TAG.items():
            cpp_register, rust_register = _REGISTER_TYPE_BY_TYPE_TAG[type_tag]
            _assert_cpp_function(
                cpp_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type=cpp_register,
                call=f"_mm_{primitive_name}_{suffix}(left, right)",
            )
            _assert_rust_function(
                rust_profile,
                primitive_name=primitive_name,
                type_tag=type_tag,
                register_type=rust_register,
                call=f"core::arch::x86_64::_mm_{primitive_name}_{suffix}(left, right)",
            )

    for width in ("8", "16", "32", "64"):
        assert f"_mm_add_epu{width}" not in cpp_profile
        assert f"_mm_sub_epu{width}" not in cpp_profile
        assert f"core::arch::x86_64::_mm_add_epu{width}" not in rust_profile
        assert f"core::arch::x86_64::_mm_sub_epu{width}" not in rust_profile

    assert "?i?" not in cpp_profile
    assert "sse_?i?" not in cpp_profile
    assert "?i?" not in rust_profile
    assert "sse_?i?" not in rust_profile
    assert "core::arch::x86_64::core::arch::x86_64" not in rust_profile


def test_m252_real_sse_unmasked_binary_arithmetic_matrix_is_deterministic() -> None:
    first = _build_real_sse_unmasked_binary_arithmetic_matrix()
    second = _build_real_sse_unmasked_binary_arithmetic_matrix()

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m252_real_sse_unmasked_binary_arithmetic_matrix_builds_cpp_and_rust(
    tmp_path: Path,
) -> None:
    result = _build_real_sse_unmasked_binary_arithmetic_matrix()

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
        ("cpp", "sse2", "configure"),
        ("cpp", "sse2", "build"),
        ("cpp", "sse2", "test"),
        ("rust", "sse2", "test"),
    ]
    assert all(command.returncode == 0 for command in report.commands)


def test_m252_project_pipeline_keeps_sse_slice_generic_and_typed() -> None:
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
        "_mm_",
        "_mm_add",
        "_mm_sub",
        "core::arch::x86_64::_mm",
        "base::signed_of",
        "intrin_compose<add",
        "intrin_compose<sub",
        "real_sse",
        "real_add",
        "real_sub",
        "binary_arithmetic",
        "tslgenold",
    ):
        assert forbidden not in source
    for suffix in (
        "epi8",
        "epi16",
        "epi32",
        "epi64",
        "epu8",
        "epu16",
        "epu32",
        "epu64",
        '"ps"',
        '"pd"',
    ):
        assert suffix not in source
    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )


def _build_real_sse_unmasked_binary_arithmetic_matrix() -> SelectedPrimitiveProjectResult:
    return build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        extension_catalog=_extension_catalog(),
        flag_catalog=_flag_catalog(),
        requested_profiles=("sse2",),
        selected_entries=_SELECTED_SSE_UNMASKED_BINARY_ARITHMETIC_MATRIX,
    )


def _assert_cpp_function(
    source: str,
    *,
    primitive_name: str,
    type_tag: str,
    register_type: str,
    call: str,
) -> None:
    assert (
        f"inline {register_type} {primitive_name}_sse_{type_tag}"
        f"({register_type} left, {register_type} right) {{\n"
        f"  return {call};\n"
        "}"
    ) in source


def _assert_rust_function(
    source: str,
    *,
    primitive_name: str,
    type_tag: str,
    register_type: str,
    call: str,
) -> None:
    function = _function_text(source, f"{primitive_name}_sse_{type_tag}")
    assert f"left: {register_type}" in function
    assert f"right: {register_type}" in function
    assert f") -> {register_type}" in function
    assert f"unsafe {{ {call} }}" in function


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
