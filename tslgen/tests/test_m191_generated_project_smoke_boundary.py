from __future__ import annotations

import json
from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.machine_profiles import (
    MachineFeatureProfile,
    MachineFeatureProfileCatalog,
    MachineProfileFamily,
    MachineProfileName,
)
from tslgen.io.artifact_writer import ArtifactWriter, manifest_logical_path
from tslgen.pipeline.build_verifier import (
    BuildCommand,
    BuildCommandResult,
    BuildVerificationPolicy,
    verify_generated_project,
)
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.pipeline.machine_profiles import load_machine_feature_profile_catalog
from tslgen.rendering.generated_project import (
    build_generated_project_render_model,
    render_generated_project_skeleton,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPLEMENTARY_ROOT = _REPO_ROOT / "supplementary"
_PROFILE_PATH = _SUPPLEMENTARY_ROOT / "buildsystem" / "machine_profiles.json"
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"


def _catalog() -> MachineFeatureProfileCatalog:
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _render_default_scalar_project():
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


def test_m191_profile_selection_defaults_to_scalar_and_supports_all() -> None:
    catalog = _catalog()

    default_selection = select_generated_profiles(catalog)
    assert default_selection.diagnostics == ()
    assert default_selection.profile_set is not None
    assert default_selection.profile_set.profile_names == (MachineProfileName("scalar"),)
    assert default_selection.profile_set.default_profile.name == MachineProfileName(
        "scalar"
    )

    all_selection = select_generated_profiles(catalog, ("all",))
    assert all_selection.diagnostics == ()
    assert all_selection.profile_set is not None
    assert all_selection.profile_set.profile_names == tuple(
        profile.name for profile in catalog.profiles
    )
    assert all_selection.profile_set.default_profile.name == MachineProfileName("scalar")


def test_m191_profile_selection_keeps_explicit_order_and_reports_errors() -> None:
    catalog = _catalog()

    selection = select_generated_profiles(catalog, ("avx2", "sse2"))
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    assert selection.profile_set.profile_names == (
        MachineProfileName("avx2"),
        MachineProfileName("sse2"),
    )
    assert selection.profile_set.default_profile.name == MachineProfileName("avx2")

    invalid = select_generated_profiles(catalog, ("all", "scalar", "missing"))
    assert invalid.profile_set is None
    assert [diagnostic.code for diagnostic in invalid.diagnostics] == [
        "TSL-GENERATED-PROFILE-SELECTION-ALL-MUST-STAND-ALONE",
        "TSL-GENERATED-PROFILE-SELECTION-UNKNOWN-PROFILE",
    ]


def test_m191_profile_selection_reports_ambiguous_names() -> None:
    source = SourceLocation(Path("profiles.json"), 1, 1)
    catalog = MachineFeatureProfileCatalog(
        profiles=(
            MachineFeatureProfile(
                family=MachineProfileFamily("left"),
                name=MachineProfileName("shared"),
                features=(),
                alternatives=(),
                source=source,
            ),
            MachineFeatureProfile(
                family=MachineProfileFamily("right"),
                name=MachineProfileName("shared"),
                features=(),
                alternatives=(),
                source=source,
            ),
        )
    )

    selection = select_generated_profiles(catalog, ("shared",))

    assert selection.profile_set is None
    assert [diagnostic.code for diagnostic in selection.diagnostics] == [
        "TSL-GENERATED-PROFILE-SELECTION-AMBIGUOUS-PROFILE",
    ]
    assert "left" in selection.diagnostics[0].message
    assert "right" in selection.diagnostics[0].message


def test_m191_rendered_project_skeleton_uses_profile_layout() -> None:
    selection = select_generated_profiles(_catalog(), ("scalar", "avx2"))
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
    by_path = {
        artifact.logical_path: artifact.content
        for artifact in render_result.artifacts.artifacts
    }
    assert tuple(by_path) == (
        "cpp/CMakeLists.txt",
        "cpp/include/profiles/avx2.hpp",
        "cpp/include/profiles/scalar.hpp",
        "cpp/include/tsl.hpp",
        "cpp/tests/smoke.cpp",
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/profiles/avx2.rs",
        "rust/src/profiles/scalar.rs",
        "rust/tests/smoke.rs",
    )
    assert 'set(TSL_PROFILE "scalar" CACHE STRING "Selected TSL profile")' in by_path[
        "cpp/CMakeLists.txt"
    ]
    assert 'set_property(CACHE TSL_PROFILE PROPERTY STRINGS "scalar" "avx2")' in by_path[
        "cpp/CMakeLists.txt"
    ]
    assert "target_compile_definitions(tsl_generated INTERFACE TSL_PROFILE_AVX2)" in by_path[
        "cpp/CMakeLists.txt"
    ]
    assert '#include "profiles/scalar.hpp"' in by_path["cpp/include/tsl.hpp"]
    assert '#include "profiles/avx2.hpp"' in by_path["cpp/include/tsl.hpp"]
    assert "profile_scalar = []" in by_path["rust/Cargo.toml"]
    assert "profile_avx2 = []" in by_path["rust/Cargo.toml"]
    assert 'default = ["profile_scalar"]' in by_path["rust/Cargo.toml"]
    assert 'compile_error!("exactly one TSL profile feature must be enabled");' in by_path[
        "rust/src/lib.rs"
    ]


def test_m191_manifest_clean_removes_stale_owned_files_and_preserves_unknown(
    tmp_path: Path,
) -> None:
    _, artifacts = _render_default_scalar_project()
    output_root = tmp_path / "generated"
    writer = ArtifactWriter()

    first_report = writer.write(artifacts, output_root, mode="manifest-clean")
    assert first_report.diagnostics == ()
    unknown_file = output_root / "user-notes.txt"
    unknown_file.write_text("keep me\n", encoding="utf-8")
    stale_path = output_root / "cpp" / "include" / "profiles" / "scalar.hpp"
    assert stale_path.is_file()

    second_artifacts = artifacts.__class__.create(
        tuple(
            artifact
            for artifact in artifacts.artifacts
            if artifact.logical_path != "cpp/include/profiles/scalar.hpp"
        )
    )
    second_report = writer.write(second_artifacts, output_root, mode="manifest-clean")

    assert second_report.diagnostics == ()
    assert [record.logical_path for record in second_report.removed] == [
        "cpp/include/profiles/scalar.hpp",
    ]
    assert not stale_path.exists()
    assert unknown_file.read_text(encoding="utf-8") == "keep me\n"
    manifest = json.loads(
        (output_root / manifest_logical_path()).read_text(encoding="utf-8")
    )
    assert "cpp/include/profiles/scalar.hpp" not in {
        item["logical_path"] for item in manifest["artifacts"]
    }


def test_m191_real_scalar_generated_project_smoke_builds(tmp_path: Path) -> None:
    model, artifacts = _render_default_scalar_project()
    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(artifacts, output_root, mode="manifest-clean")
    assert write_report.diagnostics == ()

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


def test_m191_verifier_checks_every_selected_profile_with_injected_runner(
    tmp_path: Path,
) -> None:
    selection = select_generated_profiles(_catalog(), ("scalar", "avx2"))
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
    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        render_result.artifacts,
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()

    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(output_root, model_result.model, runner)

    assert report.diagnostics == ()
    assert report.commands == tuple(
        BuildCommandResult(command=command, returncode=0) for command in seen
    )
    assert [
        (command.backend_id, command.profile_name, command.step)
        for command in seen
    ] == [
        ("cpp", "scalar", "configure"),
        ("cpp", "scalar", "build"),
        ("cpp", "scalar", "test"),
        ("cpp", "avx2", "configure"),
        ("cpp", "avx2", "build"),
        ("cpp", "avx2", "test"),
        ("rust", "scalar", "test"),
        ("rust", "avx2", "test"),
    ]


def test_m191_verifier_continues_after_one_profile_fails(tmp_path: Path) -> None:
    selection = select_generated_profiles(_catalog(), ("scalar", "avx2"))
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
    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        render_result.artifacts,
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()

    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if (
            command.backend_id == "cpp"
            and command.profile_name == "scalar"
            and command.step == "configure"
        ):
            return BuildCommandResult(
                command=command,
                returncode=1,
                stderr="configure failed",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(output_root, model_result.model, runner)

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-COMMAND-FAILED",
    ]
    assert [
        (command.backend_id, command.profile_name, command.step)
        for command in seen
    ] == [
        ("cpp", "scalar", "configure"),
        ("cpp", "avx2", "configure"),
        ("cpp", "avx2", "build"),
        ("cpp", "avx2", "test"),
        ("rust", "scalar", "test"),
        ("rust", "avx2", "test"),
    ]
