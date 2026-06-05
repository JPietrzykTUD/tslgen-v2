from __future__ import annotations

import inspect
from pathlib import Path

from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering import generated_project as generated_project_module
from tslgen.rendering.generated_project import (
    build_generated_project_render_model,
    render_generated_project_skeleton,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def test_m238_source_skeleton_artifacts_render_from_supplementary_templates() -> None:
    _, by_path = _render_profiles(("scalar", "avx2"))

    assert '#include "profiles/scalar.hpp"' in by_path["cpp/include/tsl.hpp"]
    assert '#include "profiles/avx2.hpp"' in by_path["cpp/include/tsl.hpp"]
    assert "namespace tsl::profiles::scalar {" in by_path[
        "cpp/include/profiles/scalar.hpp"
    ]
    assert 'inline constexpr const char* name = "avx2";' in by_path[
        "cpp/include/profiles/avx2.hpp"
    ]
    assert "return tsl::active_profile[0] == '\\0';" in by_path[
        "cpp/tests/smoke.cpp"
    ]
    assert 'pub mod scalar;' in by_path["rust/src/lib.rs"]
    assert 'pub mod avx2;' in by_path["rust/src/lib.rs"]
    assert 'pub const ACTIVE_PROFILE: &str = "scalar";' in by_path[
        "rust/src/profiles/scalar.rs"
    ]
    assert 'pub const ACTIVE_PROFILE_FAMILY: &str = "x86";' in by_path[
        "rust/src/profiles/avx2.rs"
    ]
    assert "smoke_active_profile_is_selected" in by_path["rust/tests/smoke.rs"]


def test_m238_source_template_edits_drive_rendered_artifacts(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    smoke_template = root / "templates" / "cpp" / "generated_project" / "smoke.cpp.in"
    smoke_template.write_text(
        "#include <tsl.hpp>\n\n"
        "int main() {{\n"
        "  return 0;\n"
        "}}\n"
        "// m238-template-sentinel\n",
        encoding="utf-8",
    )

    _, by_path = _render_profiles(("scalar",), root)

    assert "// m238-template-sentinel" in by_path["cpp/tests/smoke.cpp"]


def test_m238_generated_source_artifacts_are_deterministic() -> None:
    first, _ = _render_profiles(("scalar", "avx2"))
    second, _ = _render_profiles(("scalar", "avx2"))

    assert first.digest_manifest() == second.digest_manifest()


def test_m238_missing_cpp_source_template_is_diagnostic(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    (
        root
        / "templates"
        / "cpp"
        / "generated_project"
        / "profile_header.hpp.in"
    ).unlink()

    result = render_generated_project_skeleton(root, _model_for_profiles(("scalar",)))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PROJECT-MISSING-TEMPLATE",
    ]
    assert "templates/cpp/generated_project/profile_header.hpp.in" in (
        result.diagnostics[0].message
    )


def test_m238_missing_rust_source_template_is_diagnostic(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    (
        root
        / "templates"
        / "rust"
        / "generated_project"
        / "profile_module.rs.in"
    ).unlink()

    result = render_generated_project_skeleton(root, _model_for_profiles(("scalar",)))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PROJECT-MISSING-TEMPLATE",
    ]
    assert "templates/rust/generated_project/profile_module.rs.in" in (
        result.diagnostics[0].message
    )


def test_m238_unknown_source_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    profile_template = (
        root
        / "templates"
        / "cpp"
        / "generated_project"
        / "profile_header.hpp.in"
    )
    profile_template.write_text("{project_name}\n", encoding="utf-8")

    result = render_generated_project_skeleton(root, _model_for_profiles(("scalar",)))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PROJECT-TEMPLATE-UNKNOWN-FIELD",
    ]
    assert "project_name" in result.diagnostics[0].message


def test_m238_compound_source_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    public_case_template = (
        root
        / "templates"
        / "cpp"
        / "generated_project"
        / "public_header_first_profile_case.hpp.in"
    )
    public_case_template.write_text("{cpp_macro[0]}\n", encoding="utf-8")

    result = render_generated_project_skeleton(root, _model_for_profiles(("scalar",)))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PROJECT-TEMPLATE-UNSUPPORTED-FIELD-SHAPE",
    ]
    assert "cpp_macro[0]" in result.diagnostics[0].message


def test_m238_semantic_source_template_field_is_diagnostic(tmp_path: Path) -> None:
    root = _copied_supplementary_templates(tmp_path)
    profile_template = (
        root
        / "templates"
        / "rust"
        / "generated_project"
        / "profile_module.rs.in"
    )
    profile_template.write_text("{tsil}\n{primitive_name}\n", encoding="utf-8")

    result = render_generated_project_skeleton(root, _model_for_profiles(("scalar",)))

    assert result.artifacts.artifacts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-GENERATED-PROJECT-TEMPLATE-SEMANTIC-FIELD",
        "TSL-GENERATED-PROJECT-TEMPLATE-SEMANTIC-FIELD",
    ]
    assert "primitive_name" in result.diagnostics[0].message
    assert "tsil" in result.diagnostics[1].message


def test_m238_whole_source_assembly_helpers_are_not_retained() -> None:
    source = inspect.getsource(generated_project_module)

    assert "def _cpp_public_header(" not in source
    assert "def _cpp_profile_header(" not in source
    assert "def _cpp_smoke_test(" not in source
    assert "def _rust_public_lib(" not in source
    assert "def _rust_profile_module(" not in source
    assert "def _rust_smoke_test(" not in source


def _render_profiles(
    profiles: tuple[str, ...],
    supplementary_root: Path = _SUPPLEMENTARY_ROOT,
):
    model = _model_for_profiles(profiles)
    render_result = render_generated_project_skeleton(supplementary_root, model)
    assert render_result.diagnostics == ()
    return render_result.artifacts, {
        artifact.logical_path: artifact.content
        for artifact in render_result.artifacts.artifacts
    }


def _model_for_profiles(profiles: tuple[str, ...]):
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.flag_catalog is not None
    selection = select_generated_profiles(result.catalog, profiles)
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    model_result = build_generated_project_render_model(
        selection.profile_set,
        result.flag_catalog,
    )
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    return model_result.model


def _copied_supplementary_templates(tmp_path: Path) -> Path:
    root = tmp_path / "supplementary"
    for relative_path in generated_project_module._GENERATED_PROJECT_TEMPLATE_PATHS:
        source = _SUPPLEMENTARY_ROOT / relative_path
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return root
