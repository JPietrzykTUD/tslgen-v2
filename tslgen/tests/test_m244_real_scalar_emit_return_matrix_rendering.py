from __future__ import annotations

import ast
from pathlib import Path

from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceLoader
from tslgen.pipeline import (
    SelectedPrimitiveProjectResult,
    SelectedPrimitiveBodyRenderEntry,
    build_primitive_project_artifacts_from_selected_bodies,
)
from tslgen.pipeline.backend_metadata import load_active_backend_metadata_catalog
from tslgen.pipeline.build_verifier import (
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"
_LANGUAGE_ROOT = _REPO_ROOT / "tsldata" / "detail" / "lang"
_FUNDAMENTAL_PATH = _REPO_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
_PRIMITIVE_PROJECT_PIPELINE = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "primitive_project_pipeline.py"
)
_TYPE_TAGS = (
    "si8",
    "si16",
    "si32",
    "si64",
    "ui8",
    "ui16",
    "ui32",
    "ui64",
    "f32",
    "f64",
)
_FUNCTION_NAMES = tuple(
    f"{primitive}_scalar_{type_tag}"
    for primitive in ("add", "sub")
    for type_tag in _TYPE_TAGS
)
_SELECTED_MATRIX = tuple(
    SelectedPrimitiveBodyRenderEntry(
        primitive_name=primitive,
        selector_path=("scalar", "arith"),
        type_tag=type_tag,
        function_name=f"{primitive}_scalar_{type_tag}",
        parameters=("left", "right"),
    )
    for primitive in ("add", "sub")
    for type_tag in _TYPE_TAGS
)


def test_m244_real_add_sub_scalar_matrix_renders_cpp_and_rust() -> None:
    result = _build_real_scalar_matrix()

    assert result.diagnostics == ()
    assert len(result.selections) == 20
    assert tuple(selection.function_name for selection in result.selections) == (
        _FUNCTION_NAMES
    )
    assert {selection.primitive.name for selection in result.selections} == {
        "add",
        "sub",
    }
    assert {str(selection.type_tag) for selection in result.selections} == set(_TYPE_TAGS)
    assert {
        selection.body_envelope.selector_path for selection in result.selections
    } == {("scalar", "arith")}
    assert {
        selection.payload_text
        for selection in result.selections
        if selection.primitive.name == "add"
    } == {"left + right"}
    assert {
        selection.payload_text
        for selection in result.selections
        if selection.primitive.name == "sub"
    } == {"left - right"}

    assert tuple(
        (plan.logical_path.text, len(plan.primitives)) for plan in result.render_plans
    ) == (
        ("cpp/include/profiles/scalar.hpp", 20),
        ("rust/src/profiles/scalar.rs", 20),
    )

    by_path = _artifact_content_by_path(result)
    cpp_profile = by_path["cpp/include/profiles/scalar.hpp"]
    rust_profile = by_path["rust/src/profiles/scalar.rs"]
    for function_name in _FUNCTION_NAMES:
        assert cpp_profile.count(function_name) == 1
        assert rust_profile.count(function_name) == 1

    assert "inline int8_t add_scalar_si8(int8_t left, int8_t right)" in cpp_profile
    assert "inline uint64_t add_scalar_ui64(uint64_t left, uint64_t right)" in (
        cpp_profile
    )
    assert "inline float sub_scalar_f32(float left, float right)" in cpp_profile
    assert "inline double sub_scalar_f64(double left, double right)" in cpp_profile
    assert "pub fn add_scalar_si8(left: i8, right: i8) -> i8" in rust_profile
    assert "pub fn add_scalar_ui64(left: u64, right: u64) -> u64" in rust_profile
    assert "pub fn sub_scalar_f32(left: f32, right: f32) -> f32" in rust_profile
    assert "pub fn sub_scalar_f64(left: f64, right: f64) -> f64" in rust_profile
    assert "  return left + right;" in cpp_profile
    assert "  return left - right;" in cpp_profile
    assert "    left + right" in rust_profile
    assert "    left - right" in rust_profile


def test_m244_matrix_artifacts_are_deterministic_and_build(
    tmp_path: Path,
) -> None:
    first = _build_real_scalar_matrix()
    second = _build_real_scalar_matrix()

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
    assert first.model is not None

    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        first.artifacts,
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()
    assert sorted(record.logical_path for record in write_report.written) == [
        artifact.logical_path for artifact in first.artifacts.artifacts
    ]

    report = verify_generated_project(
        output_root,
        first.model,
        policy=BuildVerificationPolicy(cxx_compiler="clang++"),
    )

    assert report.diagnostics == ()
    assert [
        (command.command.backend_id, command.command.profile_name, command.command.step)
        for command in report.commands
    ] == [
        ("cpp", "scalar", "configure"),
        ("cpp", "scalar", "build"),
        ("cpp", "scalar", "test"),
        ("rust", "scalar", "test"),
    ]
    assert all(command.returncode == 0 for command in report.commands)


def test_m244_duplicate_selected_function_names_are_diagnostics() -> None:
    duplicate = SelectedPrimitiveBodyRenderEntry(
        primitive_name="add",
        selector_path=("scalar", "arith"),
        type_tag="si32",
        function_name="add_scalar_si32",
        parameters=("left", "right"),
    )
    result = build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        selected_entries=(duplicate, duplicate),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-REAL-SCALAR-EMIT-RETURN-DUPLICATE-FUNCTION",
        "TSL-REAL-SCALAR-EMIT-RETURN-DUPLICATE-PRIMITIVE",
    ]


def test_m244_unsupported_selected_matrix_entry_is_diagnostic() -> None:
    result = build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        selected_entries=(
            SelectedPrimitiveBodyRenderEntry(
                primitive_name="add",
                selector_path=("[generic, oneAPIfpga, oneAPIfpgaRTL]", "arith"),
                type_tag="si32",
                function_name="add_scalar_si32",
                parameters=("left", "right"),
            ),
        ),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-BODY",
    ]


def test_m244_matrix_path_does_not_use_tiny_parser_or_operator_shortcut() -> None:
    source = _PRIMITIVE_PROJECT_PIPELINE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "tslgen.syntax.parser" not in imported_modules
    assert "TslParser" not in called_names
    assert "TslParser" not in called_attributes
    assert "body add(left, right)" not in source
    assert "_SCALAR_TYPE_SPELLINGS" not in source
    assert "_BINARY_OPERATION_SPELLINGS" not in source
    assert "LoweredBinaryOperationExpression" not in source
    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )
    assert '"frozen/' not in source
    assert '"tslgenold/' not in source


def test_m244_public_pipeline_imports_are_stable() -> None:
    from tslgen.pipeline import (  # noqa: PLC0415
        SelectedPrimitiveBodyRenderEntry,
        build_primitive_project_artifacts_from_selected_bodies,
    )

    assert SelectedPrimitiveBodyRenderEntry.__name__ == "SelectedPrimitiveBodyRenderEntry"
    assert callable(build_primitive_project_artifacts_from_selected_bodies)


def _build_real_scalar_matrix() -> SelectedPrimitiveProjectResult:
    return build_primitive_project_artifacts_from_selected_bodies(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        selected_entries=_SELECTED_MATRIX,
    )


def _source_documents():
    result = SourceLoader().load((_FUNDAMENTAL_PATH,))
    assert result.diagnostics == ()
    return result.documents


def _machine_profiles():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _backend_metadata():
    result = load_active_backend_metadata_catalog(_LANGUAGE_ROOT)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _artifact_content_by_path(
    result: SelectedPrimitiveProjectResult,
) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
