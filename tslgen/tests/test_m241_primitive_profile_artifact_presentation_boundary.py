from __future__ import annotations

from pathlib import Path

from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering import (
    CppPrimitiveProfileInclude,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileArtifactRenderContext,
    PrimitiveProfileName,
    RenderedPrimitiveDefinitionText,
    RustPrimitiveProfileImport,
    build_generated_project_render_model,
    build_primitive_profile_template_contexts,
    render_primitive_profile_artifacts,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def test_m241_renders_cpp_profile_artifact_from_typed_profile_values() -> None:
    model = _generated_project_model("scalar")
    result = render_primitive_profile_artifacts(
        _SUPPLEMENTARY_ROOT,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("cpp"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "cpp/include/profiles/scalar.hpp"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.cpp.profiles[0],
                cpp_includes=(CppPrimitiveProfileInclude("cstdint"),),
                primitive_definitions=(
                    RenderedPrimitiveDefinitionText(
                        "inline std::int32_t add_one(std::int32_t value) {\n"
                        "  return value + 1;\n"
                        "}"
                    ),
                ),
            ),
        ),
    )

    assert result.diagnostics == ()
    by_path = _content_by_path(result.artifacts)
    content = by_path["cpp/include/profiles/scalar.hpp"]
    assert "#include <cstdint>" in content
    assert "namespace tsl::profiles::scalar {" in content
    assert 'inline constexpr const char* name = "scalar";' in content
    assert 'inline constexpr const char* family = "generic";' in content
    assert (
        "inline constexpr const char* active_profile = profiles::scalar::name;"
    ) in content
    assert (
        "inline constexpr const char* active_profile_family = "
        "profiles::scalar::family;"
    ) in content
    assert "inline std::int32_t add_one(std::int32_t value)" in content


def test_m241_renders_rust_profile_artifact_from_typed_profile_values() -> None:
    model = _generated_project_model("scalar")
    result = render_primitive_profile_artifacts(
        _SUPPLEMENTARY_ROOT,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("rust"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "rust/src/profiles/scalar.rs"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.rust.profiles[0],
                rust_imports=(RustPrimitiveProfileImport("core::mem"),),
                primitive_definitions=(
                    RenderedPrimitiveDefinitionText(
                        "pub fn add_one(value: i32) -> i32 {\n"
                        "    value + 1\n"
                        "}"
                    ),
                ),
            ),
        ),
    )

    assert result.diagnostics == ()
    by_path = _content_by_path(result.artifacts)
    content = by_path["rust/src/profiles/scalar.rs"]
    assert "use core::mem;" in content
    assert 'pub const ACTIVE_PROFILE: &str = "scalar";' in content
    assert 'pub const ACTIVE_PROFILE_FAMILY: &str = "generic";' in content
    assert "pub fn add_one(value: i32) -> i32" in content


def test_m241_missing_profile_template_is_diagnostic(tmp_path: Path) -> None:
    model = _generated_project_model("scalar")

    result = build_primitive_profile_template_contexts(
        tmp_path,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("cpp"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "cpp/include/profiles/scalar.hpp"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.cpp.profiles[0],
                cpp_includes=(CppPrimitiveProfileInclude("cstdint"),),
            ),
        ),
    )

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
        "TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
        "TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
    ]
    assert "namespace_close.hpp.in" in result.diagnostics[0].message
    assert "namespace_open.hpp.in" in result.diagnostics[1].message
    assert "system_include.hpp.in" in result.diagnostics[2].message


def test_m241_missing_rust_profile_template_is_diagnostic(tmp_path: Path) -> None:
    model = _generated_project_model("scalar")

    result = build_primitive_profile_template_contexts(
        tmp_path,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("rust"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "rust/src/profiles/scalar.rs"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.rust.profiles[0],
                rust_imports=(RustPrimitiveProfileImport("core::mem"),),
            ),
        ),
    )

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
        "TSL-PRIMITIVE-PROFILE-MISSING-TEMPLATE",
    ]
    assert "import.rs.in" in result.diagnostics[0].message
    assert "module_open.rs.in" in result.diagnostics[1].message


def test_m241_semantic_and_unknown_profile_template_fields_are_diagnostics(
    tmp_path: Path,
) -> None:
    model = _generated_project_model("scalar")
    _write_cpp_profile_templates(
        tmp_path,
        namespace_open="namespace tsl::profiles::{source} {{\n{mystery}\n",
    )

    result = build_primitive_profile_template_contexts(
        tmp_path,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("cpp"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "cpp/include/profiles/scalar.hpp"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.cpp.profiles[0],
            ),
        ),
    )

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-PROFILE-SEMANTIC-FIELD",
        "TSL-PRIMITIVE-PROFILE-UNKNOWN-FIELD",
    ]
    assert "semantic field 'source'" in result.diagnostics[0].message
    assert "unsupported field 'mystery'" in result.diagnostics[1].message


def test_m241_semantic_and_unknown_rust_profile_template_fields_are_diagnostics(
    tmp_path: Path,
) -> None:
    model = _generated_project_model("scalar")
    _write_rust_profile_templates(
        tmp_path,
        module_open='pub const ACTIVE_PROFILE: &str = "{source}";\n{mystery}\n',
    )

    result = build_primitive_profile_template_contexts(
        tmp_path,
        (
            PrimitiveProfileArtifactRenderContext(
                backend_id=PrimitiveBackendId("rust"),
                logical_path=PrimitiveArtifactLogicalPath(
                    "rust/src/profiles/scalar.rs"
                ),
                profile_name=PrimitiveProfileName("scalar"),
                profile=model.rust.profiles[0],
            ),
        ),
    )

    assert result.contexts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-PRIMITIVE-PROFILE-SEMANTIC-FIELD",
        "TSL-PRIMITIVE-PROFILE-UNKNOWN-FIELD",
    ]
    assert "semantic field 'source'" in result.diagnostics[0].message
    assert "unsupported field 'mystery'" in result.diagnostics[1].message


def test_m241_accepted_paths_no_longer_hand_build_profile_wrappers() -> None:
    pipeline_source = (
        _REPO_ROOT
        / "tslgen"
        / "src"
        / "tslgen"
        / "pipeline"
        / "generated_primitive_pipeline.py"
    ).read_text(encoding="utf-8")
    m223_source = (
        _REPO_ROOT / "tslgen" / "tests" / "test_m223_first_real_generated_primitive.py"
    ).read_text(encoding="utf-8")
    m240_source = (
        _REPO_ROOT
        / "tslgen"
        / "tests"
        / "test_m240_synthetic_intrinsic_generated_project_verification.py"
    ).read_text(encoding="utf-8")

    for source in (pipeline_source, m223_source, m240_source):
        assert "RenderedNamespaceText" not in source
        assert "RenderedModuleText" not in source
        assert "RenderedIncludeLine" not in source
        assert "namespace_open=" not in source
        assert "namespace_close=" not in source
        assert "module_open=" not in source

    assert "inline constexpr const char* active_profile =" not in pipeline_source
    assert "pub const ACTIVE_PROFILE: &str =" not in pipeline_source


def _generated_project_model(profile_name: str):
    catalog_result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    selection = select_generated_profiles(catalog_result.catalog, (profile_name,))
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    model_result = build_generated_project_render_model(selection.profile_set)
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    return model_result.model


def _content_by_path(artifacts) -> dict[str, str]:
    return {artifact.logical_path: artifact.content for artifact in artifacts.artifacts}


def _write_cpp_profile_templates(
    root: Path,
    *,
    namespace_open: str,
) -> None:
    template_dir = root / "templates" / "cpp" / "primitive_profile"
    template_dir.mkdir(parents=True)
    (template_dir / "namespace_open.hpp.in").write_text(
        namespace_open,
        encoding="utf-8",
    )
    (template_dir / "namespace_close.hpp.in").write_text(
        "}}  // namespace tsl::profiles::{namespace}\n",
        encoding="utf-8",
    )


def _write_rust_profile_templates(
    root: Path,
    *,
    module_open: str,
) -> None:
    template_dir = root / "templates" / "rust" / "primitive_profile"
    template_dir.mkdir(parents=True)
    (template_dir / "module_open.rs.in").write_text(
        module_open,
        encoding="utf-8",
    )
