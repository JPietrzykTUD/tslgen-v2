from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import Target
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.io.sources import SourceDocument
from tslgen.lowering import LoweredBinaryOperationExpression
from tslgen.pipeline import (
    ParsedTinyGeneratedProjectResult,
    build_parsed_tiny_generated_project_artifacts,
)
from tslgen.pipeline.build_verifier import (
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def test_m224_parsed_source_drives_cpp_and_rust_profile_artifacts(
    tmp_path: Path,
) -> None:
    result = _pipeline_result(tmp_path)

    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.model is not None
    assert {selected.target.backend for selected in result.selected} == {"cpp", "rust"}
    assert {
        function.signature.primitive_name
        for function in result.lowered_functions.functions
    } == {"add"}
    assert all(
        isinstance(
            function.body.return_statement.expression,
            LoweredBinaryOperationExpression,
        )
        for function in result.lowered_functions.functions
    )
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
    assert "inline std::int32_t add_scalar_si32" in by_path[
        "cpp/include/profiles/scalar.hpp"
    ]
    assert "return left + right;" in by_path["cpp/include/profiles/scalar.hpp"]
    assert "pub fn add_scalar_si32(left: i32, right: i32) -> i32" in by_path[
        "rust/src/profiles/scalar.rs"
    ]
    assert "    left + right" in by_path["rust/src/profiles/scalar.rs"]
    assert "add_one" not in by_path["cpp/include/profiles/scalar.hpp"]
    assert "add_one" not in by_path["rust/src/profiles/scalar.rs"]


def test_m224_composed_artifacts_are_deterministic(tmp_path: Path) -> None:
    first = _pipeline_result(tmp_path)
    second = _pipeline_result(tmp_path)

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()


def test_m224_manifest_clean_write_and_verify_generated_projects(
    tmp_path: Path,
) -> None:
    result = _pipeline_result(tmp_path)
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
        ("cpp", "scalar", "configure"),
        ("cpp", "scalar", "build"),
        ("cpp", "scalar", "test"),
        ("rust", "scalar", "test"),
    ]
    assert all(command.returncode == 0 for command in report.commands)


def test_m224_parse_diagnostics_stop_before_rendering(tmp_path: Path) -> None:
    result = build_parsed_tiny_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=(
            _source_document(
                tmp_path,
                "broken.tsl",
                "not a supported tiny source form\n",
            ),
        ),
        targets=_targets("si32"),
        machine_profiles=_catalog(),
    )

    assert result.artifacts.artifacts == ()
    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PARSE-UNSUPPORTED-FORM",
    ]


def test_m224_unsupported_lowered_render_fact_is_diagnostic(
    tmp_path: Path,
) -> None:
    result = build_parsed_tiny_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=(_tiny_add_document(tmp_path, type_tag="si8"),),
        targets=_targets("si8"),
        machine_profiles=_catalog(),
    )

    assert result.artifacts.artifacts == ()
    assert result.catalog is not None
    assert len(result.lowered_functions.functions) == 2
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-TYPE",
        "TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-TYPE",
    ]


def test_m224_public_pipeline_imports_are_stable() -> None:
    from tslgen.pipeline import (  # noqa: PLC0415
        ParsedTinyGeneratedProjectResult,
        SelectedLoweredFunction,
        build_parsed_tiny_generated_project_artifacts,
    )

    assert ParsedTinyGeneratedProjectResult.__name__ == (
        "ParsedTinyGeneratedProjectResult"
    )
    assert SelectedLoweredFunction.__name__ == "SelectedLoweredFunction"
    assert callable(build_parsed_tiny_generated_project_artifacts)


def _pipeline_result(tmp_path: Path) -> ParsedTinyGeneratedProjectResult:
    result = build_parsed_tiny_generated_project_artifacts(
        supplementary_root=_SUPPLEMENTARY_ROOT,
        source_documents=(_tiny_add_document(tmp_path),),
        targets=_targets("si32"),
        machine_profiles=_catalog(),
    )
    return result


def _tiny_add_document(
    tmp_path: Path,
    *,
    type_tag: str = "si32",
) -> SourceDocument:
    return _source_document(
        tmp_path,
        f"add_{type_tag}.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                f"  implementation scalar {type_tag}:",
                "    body add(left, right)",
                "",
            )
        ),
    )


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _targets(type_tag: str) -> tuple[Target, ...]:
    return (
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag=type_tag,
        ),
        Target(
            backend="rust",
            primitive_name="add",
            extension="scalar",
            type_tag=type_tag,
        ),
    )


def _catalog():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _artifact_content_by_path(
    result: ParsedTinyGeneratedProjectResult,
) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
