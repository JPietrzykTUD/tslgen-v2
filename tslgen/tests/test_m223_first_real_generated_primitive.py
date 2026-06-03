from __future__ import annotations

from pathlib import Path

from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.pipeline.build_verifier import (
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering import (
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    PrimitiveRenderPlan,
    PrimitiveRenderPlanPrimitiveId,
    PrimitiveRenderPlanRecord,
    PrimitiveRenderSortKey,
    RenderedIncludeLine,
    RenderedNamespaceText,
    RenderedPrimitiveDefinitionText,
    adapt_primitive_render_plans,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_primitive_templates,
    scalar_profile_replacement_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def test_m223_renders_tiny_cpp_and_rust_primitive_profile_artifacts() -> None:
    artifacts = _render_tiny_primitive_artifacts()

    by_path = {artifact.logical_path: artifact.content for artifact in artifacts.artifacts}

    assert tuple(by_path) == (
        "cpp/include/profiles/scalar.hpp",
        "rust/src/profiles/scalar.rs",
    )
    assert "inline constexpr const char* active_profile = \"scalar\";" in by_path[
        "cpp/include/profiles/scalar.hpp"
    ]
    assert "inline std::int32_t add_one(std::int32_t value)" in by_path[
        "cpp/include/profiles/scalar.hpp"
    ]
    assert "pub const ACTIVE_PROFILE: &str = \"scalar\";" in by_path[
        "rust/src/profiles/scalar.rs"
    ]
    assert "pub fn add_one(value: i32) -> i32" in by_path[
        "rust/src/profiles/scalar.rs"
    ]


def test_m223_composes_skeleton_and_primitive_artifacts_deterministically() -> None:
    _, skeleton = _render_scalar_skeleton()
    primitives = _render_tiny_primitive_artifacts()

    first = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )
    second = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )

    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
    by_path = {
        artifact.logical_path: artifact.content
        for artifact in first.artifacts.artifacts
    }
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
    assert '#include "profiles/scalar.hpp"' in by_path["cpp/include/tsl.hpp"]
    assert 'pub mod scalar;' in by_path["rust/src/lib.rs"]
    assert "add_one" in by_path["cpp/include/profiles/scalar.hpp"]
    assert "add_one" in by_path["rust/src/profiles/scalar.rs"]


def test_m223_allows_only_selected_profile_replacement_paths() -> None:
    _, skeleton = _render_scalar_skeleton()
    primitives = ArtifactSet.create(
        (
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "primitive scalar profile replacement\n",
                "text/x-c++hdr",
                "cpp",
            ),
            _artifact(
                "rust/src/profiles/scalar.rs",
                "primitive scalar profile replacement\n",
                "text/x-rust",
                "rust",
            ),
        )
    )

    result = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )

    assert result.diagnostics == ()
    by_path = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
    assert by_path["cpp/include/profiles/scalar.hpp"] == (
        "primitive scalar profile replacement\n"
    )
    assert by_path["rust/src/profiles/scalar.rs"] == (
        "primitive scalar profile replacement\n"
    )


def test_m223_unrelated_duplicate_logical_path_is_diagnostic() -> None:
    _, skeleton = _render_scalar_skeleton()
    primitives = ArtifactSet.create(
        (
            _artifact(
                "cpp/include/tsl.hpp",
                "not an allowed primitive replacement\n",
                "text/x-c++hdr",
                "cpp",
            ),
        )
    )

    result = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-LOGICAL-PATH",
    ]
    assert "cpp/include/tsl.hpp" in result.diagnostics[0].message


def test_m223_duplicate_primitive_artifact_is_diagnostic() -> None:
    _, skeleton = _render_scalar_skeleton()
    primitives = ArtifactSet.create(
        (
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "first\n",
                "text/x-c++hdr",
                "cpp",
            ),
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "second\n",
                "text/x-c++hdr",
                "cpp",
            ),
        )
    )

    result = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-PRIMITIVE-ARTIFACT",
    ]
    assert "cpp/include/profiles/scalar.hpp" in result.diagnostics[0].message


def test_m223_duplicate_skeleton_artifact_is_diagnostic() -> None:
    skeleton = ArtifactSet.create(
        (
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "first skeleton placeholder\n",
                "text/x-c++hdr",
                "cpp",
            ),
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "second skeleton placeholder\n",
                "text/x-c++hdr",
                "cpp",
            ),
        )
    )
    primitives = ArtifactSet.create(
        (
            _artifact(
                "cpp/include/profiles/scalar.hpp",
                "primitive scalar profile replacement\n",
                "text/x-c++hdr",
                "cpp",
            ),
        )
    )

    result = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-SKELETON-ARTIFACT",
    ]
    assert "cpp/include/profiles/scalar.hpp" in result.diagnostics[0].message


def test_m223_manifest_clean_writes_and_verifies_real_scalar_project(
    tmp_path: Path,
) -> None:
    model, artifacts = _composed_tiny_project_artifacts()
    output_root = tmp_path / "generated"

    write_report = ArtifactWriter().write(
        artifacts,
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()
    assert sorted(record.logical_path for record in write_report.written) == [
        artifact.logical_path for artifact in artifacts.artifacts
    ]

    report = verify_generated_project(
        output_root,
        model,
        policy=BuildVerificationPolicy(cxx_compiler="clang++"),
    )

    assert report.diagnostics == ()
    assert [
        (result.command.backend_id, result.command.profile_name, result.command.step)
        for result in report.commands
    ] == [
        ("cpp", "scalar", "configure"),
        ("cpp", "scalar", "build"),
        ("cpp", "scalar", "test"),
        ("rust", "scalar", "test"),
    ]
    assert all(result.returncode == 0 for result in report.commands)


def test_m223_public_rendering_imports_are_stable() -> None:
    from tslgen.rendering import (  # noqa: PLC0415
        GeneratedPrimitiveProjectCompositionResult,
        compose_generated_primitive_project_artifacts,
        scalar_profile_replacement_policy,
    )

    assert GeneratedPrimitiveProjectCompositionResult.__name__ == (
        "GeneratedPrimitiveProjectCompositionResult"
    )
    assert callable(compose_generated_primitive_project_artifacts)
    assert callable(scalar_profile_replacement_policy)


def _composed_tiny_project_artifacts():
    model, skeleton = _render_scalar_skeleton()
    primitives = _render_tiny_primitive_artifacts()
    composition = compose_generated_primitive_project_artifacts(
        skeleton,
        primitives,
        scalar_profile_replacement_policy(),
    )
    assert composition.diagnostics == ()
    return model, composition.artifacts


def _render_scalar_skeleton():
    selection = select_generated_profiles(_catalog())
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    model_result = build_generated_project_render_model(selection.profile_set)
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    render_result = render_generated_project_skeleton(
        _SUPPLEMENTARY_ROOT,
        model_result.model,
    )
    assert render_result.diagnostics == ()
    return model_result.model, render_result.artifacts


def _render_tiny_primitive_artifacts() -> ArtifactSet:
    plan_result = adapt_primitive_render_plans(
        (_tiny_cpp_scalar_plan(), _tiny_rust_scalar_plan())
    )
    assert plan_result.diagnostics == ()
    render_result = render_primitive_templates(
        _SUPPLEMENTARY_ROOT,
        plan_result.contexts,
    )
    assert render_result.diagnostics == ()
    return render_result.artifacts


def _tiny_cpp_scalar_plan() -> PrimitiveRenderPlan:
    return PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("cpp"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("cpp/include/profiles/scalar.hpp"),
        includes=(RenderedIncludeLine("#include <cstdint>"),),
        namespace_open=RenderedNamespaceText("namespace tsl {"),
        namespace_close=RenderedNamespaceText("}  // namespace tsl"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("add_one.si32"),
                presentation_sort_key=PrimitiveRenderSortKey("add_one.si32"),
                definitions=(
                    RenderedPrimitiveDefinitionText(
                        'inline constexpr const char* active_profile = "scalar";\n'
                        "inline constexpr const char* active_profile_family = "
                        '"generic";\n'
                        "inline std::int32_t add_one(std::int32_t value) {\n"
                        "  return value + 1;\n"
                        "}"
                    ),
                ),
            ),
        ),
    )


def _tiny_rust_scalar_plan() -> PrimitiveRenderPlan:
    return PrimitiveRenderPlan(
        backend_id=PrimitiveBackendId("rust"),
        profile_name=PrimitiveProfileName("scalar"),
        logical_path=PrimitiveArtifactLogicalPath("rust/src/profiles/scalar.rs"),
        primitives=(
            PrimitiveRenderPlanRecord(
                primitive_id=PrimitiveRenderPlanPrimitiveId("add_one.si32"),
                presentation_sort_key=PrimitiveRenderSortKey("add_one.si32"),
                definitions=(
                    RenderedPrimitiveDefinitionText(
                        'pub const ACTIVE_PROFILE: &str = "scalar";\n'
                        'pub const ACTIVE_PROFILE_FAMILY: &str = "generic";\n'
                        "pub fn add_one(value: i32) -> i32 {\n"
                        "    value + 1\n"
                        "}"
                    ),
                ),
            ),
        ),
    )


def _catalog():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _artifact(
    logical_path: str,
    content: str,
    media_type: str,
    backend_id: str,
) -> Artifact:
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
        metadata=(ArtifactMetadata("backend", backend_id),),
    )
