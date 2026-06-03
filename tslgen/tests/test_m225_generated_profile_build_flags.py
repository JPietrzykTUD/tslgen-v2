from __future__ import annotations

from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.generated_project import (
    CppTargetFeatureOption,
    GeneratedProfileSet,
    RustTargetFeature,
)
from tslgen.domain.machine_profiles import (
    FeatureFlagName,
    FeatureFlagNormalization,
    FeatureFlagNormalizationCatalog,
    FeatureFlagSpelling,
    MachineFeatureAlternative,
    MachineFeatureProfile,
    MachineFeatureProfileCatalog,
    MachineProfileFamily,
    MachineProfileName,
)
from tslgen.io.artifact_writer import ArtifactWriter
from tslgen.pipeline.build_verifier import (
    BuildCommand,
    BuildCommandEnvironment,
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
_AVX2_CPP_OPTIONS = (
    "-msse",
    "-msse2",
    "-mssse3",
    "-msse4.1",
    "-msse4.2",
    "-mavx",
    "-mavx2",
)
_AVX2_RUST_FEATURES = (
    "+sse",
    "+sse2",
    "+ssse3",
    "+sse4.1",
    "+sse4.2",
    "+avx",
    "+avx2",
)
_AVX2_RUSTFLAGS = "-C target-feature=" + ",".join(_AVX2_RUST_FEATURES)


def test_m225_profile_render_model_has_typed_target_feature_values() -> None:
    model = _model_for_profiles(("scalar", "avx2"))

    scalar = _profile(model.cpp.profiles, "scalar")
    avx2 = _profile(model.cpp.profiles, "avx2")

    assert scalar.cpp_target_feature_options == ()
    assert scalar.rust_target_features == ()
    assert tuple(str(option) for option in avx2.cpp_target_feature_options) == (
        _AVX2_CPP_OPTIONS
    )
    assert tuple(str(feature) for feature in avx2.rust_target_features) == (
        _AVX2_RUST_FEATURES
    )


def test_m225_profile_render_model_applies_alternative_spellings() -> None:
    source = SourceLocation(Path("profiles.json"), 1, 1)
    profile = MachineFeatureProfile(
        family=MachineProfileFamily("x86"),
        name=MachineProfileName("custom"),
        features=(
            FeatureFlagName("avx512_vpclmulqdq"),
            FeatureFlagName("sse4_1"),
        ),
        alternatives=(
            MachineFeatureAlternative(
                feature=FeatureFlagName("avx512_vpclmulqdq"),
                spelling=FeatureFlagSpelling("vpclmulqdq"),
            ),
        ),
        source=source,
    )

    model_result = build_generated_project_render_model(
        GeneratedProfileSet(profiles=(profile,), default_profile=profile),
        _custom_flag_catalog(),
    )

    assert model_result.diagnostics == ()
    assert model_result.model is not None
    rendered = model_result.model.cpp.profiles[0]
    assert tuple(str(option) for option in rendered.cpp_target_feature_options) == (
        "-mvpclmulqdq",
        "-msse4.1",
    )
    assert tuple(str(feature) for feature in rendered.rust_target_features) == (
        "+vpclmulqdq",
        "+sse4.1",
    )


def test_m225_non_scalar_profile_requires_flag_catalog_spellings() -> None:
    selection = select_generated_profiles(_catalog(), ("avx2",))
    assert selection.diagnostics == ()
    assert selection.profile_set is not None

    model_result = build_generated_project_render_model(selection.profile_set)

    assert model_result.model is None
    assert [diagnostic.code for diagnostic in model_result.diagnostics] == [
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
        "TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
    ]


def test_m225_generated_artifacts_contain_decided_build_flag_values() -> None:
    _, by_path = _render_profiles(("scalar", "avx2"))
    cmake = by_path["cpp/CMakeLists.txt"]
    cargo = by_path["rust/Cargo.toml"]

    assert (
        'if(TSL_PROFILE STREQUAL "scalar")\n'
        "  target_compile_definitions(tsl_generated INTERFACE TSL_PROFILE_SCALAR)\n"
        'elseif(TSL_PROFILE STREQUAL "avx2")'
    ) in cmake
    assert (
        "target_compile_options(tsl_generated INTERFACE "
        "-msse -msse2 -mssse3 -msse4.1 -msse4.2 -mavx -mavx2)"
    ) in cmake
    assert '[package.metadata.tsl.profiles."scalar"]' in cargo
    assert "target_features = []" in cargo
    assert "rustflags = []" in cargo
    assert '[package.metadata.tsl.profiles."avx2"]' in cargo
    assert (
        'target_features = ["+sse", "+sse2", "+ssse3", "+sse4.1", '
        '"+sse4.2", "+avx", "+avx2"]'
    ) in cargo
    assert (
        'rustflags = ["-C", '
        '"target-feature=+sse,+sse2,+ssse3,+sse4.1,+sse4.2,+avx,+avx2"]'
    ) in cargo


def test_m225_verifier_applies_rust_target_features_per_profile(
    tmp_path: Path,
) -> None:
    model, by_path = _render_profiles(("scalar", "avx2"))
    output_root = tmp_path / "generated"
    write_report = ArtifactWriter().write(
        _artifacts_for_content(by_path),
        output_root,
        mode="manifest-clean",
    )
    assert write_report.diagnostics == ()

    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(output_root, model, runner)

    assert report.diagnostics == ()
    rust_commands = [command for command in seen if command.backend_id == "rust"]
    assert [(command.profile_name, command.env) for command in rust_commands] == [
        ("scalar", ()),
        (
            "avx2",
            (
                BuildCommandEnvironment(
                    key="RUSTFLAGS",
                    value=_AVX2_RUSTFLAGS,
                ),
            ),
        ),
    ]


def test_m225_generated_scalar_avx2_project_builds(tmp_path: Path) -> None:
    model, artifacts = _render_artifacts(("scalar", "avx2"))
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
        ("cpp", "avx2", "configure"),
        ("cpp", "avx2", "build"),
        ("cpp", "avx2", "test"),
        ("rust", "scalar", "test"),
        ("rust", "avx2", "test"),
    ]
    assert all(result.returncode == 0 for result in report.commands)


def test_m225_duplicate_and_unknown_profile_selection_remain_diagnostic() -> None:
    selection = select_generated_profiles(_catalog(), ("avx2", "avx2", "missing"))

    assert selection.profile_set is None
    assert [diagnostic.code for diagnostic in selection.diagnostics] == [
        "TSL-GENERATED-PROFILE-SELECTION-DUPLICATE-PROFILE",
        "TSL-GENERATED-PROFILE-SELECTION-UNKNOWN-PROFILE",
    ]


def test_m225_public_typed_build_flag_imports_are_stable() -> None:
    assert CppTargetFeatureOption("-mavx2") == "-mavx2"
    assert RustTargetFeature("+avx2") == "+avx2"
    assert BuildCommandEnvironment(key="RUSTFLAGS", value="value").key == "RUSTFLAGS"


def _load_profiles():
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None
    assert result.flag_catalog is not None
    return result.catalog, result.flag_catalog


def _catalog() -> MachineFeatureProfileCatalog:
    catalog, _ = _load_profiles()
    return catalog


def _model_for_profiles(
    profiles: tuple[str, ...],
):
    selection = select_generated_profiles(_catalog(), profiles)
    assert selection.diagnostics == ()
    assert selection.profile_set is not None
    _, flag_catalog = _load_profiles()
    model_result = build_generated_project_render_model(
        selection.profile_set,
        flag_catalog,
    )
    assert model_result.diagnostics == ()
    assert model_result.model is not None
    return model_result.model


def _render_artifacts(
    profiles: tuple[str, ...],
):
    model = _model_for_profiles(profiles)
    render_result = render_generated_project_skeleton(_SUPPLEMENTARY_ROOT, model)
    assert render_result.diagnostics == ()
    return model, render_result.artifacts


def _render_profiles(
    profiles: tuple[str, ...],
):
    model, artifacts = _render_artifacts(profiles)
    return model, {
        artifact.logical_path: artifact.content for artifact in artifacts.artifacts
    }


def _artifacts_for_content(by_path: dict[str, str]):
    _, artifacts = _render_artifacts(("scalar", "avx2"))
    expected = {artifact.logical_path: artifact.content for artifact in artifacts.artifacts}
    assert by_path == expected
    return artifacts


def _profile(profiles, name: str):
    for profile in profiles:
        if profile.profile_name == MachineProfileName(name):
            return profile
    raise AssertionError(f"missing profile {name!r}")


def _custom_flag_catalog() -> FeatureFlagNormalizationCatalog:
    return FeatureFlagNormalizationCatalog(
        entries=(
            FeatureFlagNormalization(
                spelling=FeatureFlagSpelling("sse4.1"),
                normalized=FeatureFlagName("sse4_1"),
                source=SourceLocation(Path("flags.tsl"), 1, 1),
            ),
        )
    )
