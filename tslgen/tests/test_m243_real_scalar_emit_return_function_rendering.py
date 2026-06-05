from __future__ import annotations

import ast
from pathlib import Path

from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceLoader
from tslgen.pipeline import (
    RealScalarEmitReturnGeneratedProjectResult,
    build_real_scalar_emit_return_generated_project_artifacts,
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
_REAL_SCALAR_PIPELINE = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline" / "real_scalar_pipeline.py"
)


def test_m243_real_scalar_add_from_fundamental_tsl_renders_cpp_and_rust() -> None:
    result = _build_real_scalar_add()

    assert result.diagnostics == ()
    assert result.selection is not None
    assert result.selection.primitive.name == "add"
    assert result.selection.primitive.signature == "v:=(v,v)"
    assert result.selection.primitive.parameters == ("left", "right")
    assert result.selection.body_envelope.selector_path == ("scalar", "arith")
    assert result.selection.payload_text == "left + right"
    assert result.selection.function_name == "add_scalar_si32"
    assert tuple(plan.logical_path.text for plan in result.render_plans) == (
        "cpp/include/profiles/scalar.hpp",
        "rust/src/profiles/scalar.rs",
    )

    by_path = _artifact_content_by_path(result)
    assert tuple(by_path) == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/scalar.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/scalar.rs",
        "rust/tests/smoke.rs",
    )
    assert "inline int32_t add_scalar_si32(int32_t left, int32_t right)" in (
        by_path["cpp/include/profiles/scalar.hpp"]
    )
    assert "  return left + right;" in by_path["cpp/include/profiles/scalar.hpp"]
    assert "pub fn add_scalar_si32(left: i32, right: i32) -> i32" in (
        by_path["rust/src/profiles/scalar.rs"]
    )
    assert "    left + right" in by_path["rust/src/profiles/scalar.rs"]
    assert "body add(left, right)" not in by_path["cpp/include/profiles/scalar.hpp"]
    assert "body add(left, right)" not in by_path["rust/src/profiles/scalar.rs"]


def test_m243_real_scalar_add_generated_project_is_deterministic_and_builds(
    tmp_path: Path,
) -> None:
    first = _build_real_scalar_add()
    second = _build_real_scalar_add()

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


def test_m243_rejects_real_non_single_return_body() -> None:
    result = build_real_scalar_emit_return_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
        selector_path=("[generic, oneAPIfpga, oneAPIfpgaRTL]", "arith"),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-REAL-SCALAR-EMIT-RETURN-UNSUPPORTED-BODY",
    ]
    assert "exact single `emit_return(PAYLOAD);`" in result.diagnostics[0].message


def test_m243_missing_backend_metadata_does_not_fall_back_to_local_type_tables() -> None:
    result = build_real_scalar_emit_return_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=None,
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-BACKEND-TYPE-SPELLING-MISSING-METADATA",
        "TSL-BACKEND-TYPE-SPELLING-MISSING-METADATA",
    ]


def test_m243_real_path_does_not_use_tiny_parser_or_operator_shortcut() -> None:
    source = _REAL_SCALAR_PIPELINE.read_text(encoding="utf-8")
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
    assert "std::int32_t" not in source
    assert "return left + right" not in source
    assert "pub fn add_scalar_si32" not in source


def test_m243_public_pipeline_imports_are_stable() -> None:
    from tslgen.pipeline import (  # noqa: PLC0415
        RealScalarEmitReturnGeneratedProjectResult,
        RealScalarEmitReturnSelection,
        build_real_scalar_emit_return_generated_project_artifacts,
    )

    assert RealScalarEmitReturnGeneratedProjectResult.__name__ == (
        "RealScalarEmitReturnGeneratedProjectResult"
    )
    assert RealScalarEmitReturnSelection.__name__ == "RealScalarEmitReturnSelection"
    assert callable(build_real_scalar_emit_return_generated_project_artifacts)


def _build_real_scalar_add() -> RealScalarEmitReturnGeneratedProjectResult:
    return build_real_scalar_emit_return_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=_source_documents(),
        machine_profiles=_machine_profiles(),
        backend_metadata=_backend_metadata(),
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
    result: RealScalarEmitReturnGeneratedProjectResult,
) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
