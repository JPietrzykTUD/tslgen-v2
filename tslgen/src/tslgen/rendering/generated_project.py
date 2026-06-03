"""Profile-aware generated-project skeleton rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Callable

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.generated_project import (
    BackendProfileRenderModel,
    BackendProjectRenderModel,
    CppProfileMacro,
    CppTargetFeatureOption,
    GeneratedProjectModelResult,
    GeneratedProjectRenderModel,
    GeneratedProfileSet,
    ProfileFileStem,
    RustProfileFeature,
    RustProfileModule,
    RustTargetFeature,
)
from tslgen.domain.machine_profiles import (
    FeatureFlagName,
    FeatureFlagNormalizationCatalog,
    MachineFeatureProfile,
    MachineProfileName,
)
from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet


@dataclass(frozen=True, slots=True)
class GeneratedProjectRenderResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...] = ()


_CPP_TEMPLATE = "buildsystem/cpp/templates/generated_project_CMakeLists.txt.in"
_RUST_TEMPLATE = "buildsystem/rust/templates/generated_project_Cargo.toml.in"

_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "allowed_profiles",
        "cpp_profile_cases",
        "default_profile",
        "default_rust_feature",
        "feature_entries",
        "package_name",
        "project_name",
        "profile_metadata_entries",
    }
)


def build_generated_project_render_model(
    profile_set: GeneratedProfileSet,
    flag_catalog: FeatureFlagNormalizationCatalog | None = None,
) -> GeneratedProjectModelResult:
    """Create already-decided C++ and Rust skeleton render models."""

    profiles, diagnostics = _profile_render_models(profile_set, flag_catalog)
    if diagnostics:
        return GeneratedProjectModelResult(model=None, diagnostics=diagnostics)
    diagnostics = _profile_identifier_diagnostics(profiles)
    if diagnostics:
        return GeneratedProjectModelResult(model=None, diagnostics=diagnostics)

    cpp = BackendProjectRenderModel(
        backend_id="cpp",
        project_name="tsl_generated_cpp",
        root_path="cpp",
        public_entry_path="cpp/include/tsl.hpp",
        smoke_test_path="cpp/tests/smoke.cpp",
        profiles=profiles,
        default_profile=profile_set.default_profile.name,
    )
    rust = BackendProjectRenderModel(
        backend_id="rust",
        project_name="tsl_generated",
        root_path="rust",
        public_entry_path="rust/src/lib.rs",
        smoke_test_path="rust/tests/smoke.rs",
        profiles=profiles,
        default_profile=profile_set.default_profile.name,
    )
    return GeneratedProjectModelResult(
        model=GeneratedProjectRenderModel(cpp=cpp, rust=rust)
    )


def render_generated_project_skeleton(
    supplementary_root: Path,
    model: GeneratedProjectRenderModel,
) -> GeneratedProjectRenderResult:
    """Render profile-aware C++ and Rust skeleton artifacts."""

    artifacts: list[Artifact] = []
    diagnostics: list[Diagnostic] = []

    cpp_template, cpp_diagnostics = _load_template(supplementary_root, _CPP_TEMPLATE)
    diagnostics.extend(cpp_diagnostics)
    rust_template, rust_diagnostics = _load_template(supplementary_root, _RUST_TEMPLATE)
    diagnostics.extend(rust_diagnostics)
    if diagnostics:
        return GeneratedProjectRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    assert cpp_template is not None
    assert rust_template is not None
    cpp_values = _cpp_template_values(model.cpp)
    rust_values = _rust_template_values(model.rust)
    diagnostics.extend(_template_diagnostics(_CPP_TEMPLATE, cpp_template, cpp_values))
    diagnostics.extend(_template_diagnostics(_RUST_TEMPLATE, rust_template, rust_values))
    if diagnostics:
        return GeneratedProjectRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    artifacts.append(
        _artifact(
            "cpp/CMakeLists.txt",
            cpp_template.format_map(cpp_values),
            "text/x-cmake",
            model.cpp.backend_id,
        )
    )
    artifacts.append(
        _artifact(
            "rust/Cargo.toml",
            rust_template.format_map(rust_values),
            "text/toml",
            model.rust.backend_id,
        )
    )
    artifacts.extend(_cpp_artifacts(model.cpp))
    artifacts.extend(_rust_artifacts(model.rust))

    return GeneratedProjectRenderResult(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        diagnostics=(),
    )


def _profile_render_models(
    profile_set: GeneratedProfileSet,
    flag_catalog: FeatureFlagNormalizationCatalog | None,
) -> tuple[tuple[BackendProfileRenderModel, ...], tuple[Diagnostic, ...]]:
    profiles: list[BackendProfileRenderModel] = []
    diagnostics: list[Diagnostic] = []
    for profile in profile_set.profiles:
        rendered, rendered_diagnostics = _profile_render_model(profile, flag_catalog)
        diagnostics.extend(rendered_diagnostics)
        if rendered is not None:
            profiles.append(rendered)
    return tuple(profiles), _sort_diagnostics(diagnostics)


def _profile_render_model(
    profile: MachineFeatureProfile,
    flag_catalog: FeatureFlagNormalizationCatalog | None,
) -> tuple[BackendProfileRenderModel | None, tuple[Diagnostic, ...]]:
    stem = _sanitize_file_stem(str(profile.name))
    feature_spellings, diagnostics = _build_feature_spellings(profile, flag_catalog)
    if diagnostics:
        return None, diagnostics
    return BackendProfileRenderModel(
        family=profile.family,
        profile_name=profile.name,
        features=profile.features,
        alternatives=profile.alternatives,
        file_stem=ProfileFileStem(stem),
        cpp_macro=CppProfileMacro(f"TSL_PROFILE_{stem.upper()}"),
        cpp_target_feature_options=tuple(
            CppTargetFeatureOption(f"-m{spelling}") for spelling in feature_spellings
        ),
        rust_feature=RustProfileFeature(f"profile_{stem}"),
        rust_module=RustProfileModule(stem),
        rust_target_features=tuple(
            RustTargetFeature(f"+{spelling}") for spelling in feature_spellings
        ),
    ), ()


def _profile_identifier_diagnostics(
    profiles: tuple[BackendProfileRenderModel, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(
        _duplicate_field_diagnostics(
            profiles,
            "file stem",
            lambda profile: str(profile.file_stem),
            "TSL-GENERATED-PROJECT-DUPLICATE-PROFILE-FILE-STEM",
        )
    )
    diagnostics.extend(
        _duplicate_field_diagnostics(
            profiles,
            "C++ macro",
            lambda profile: str(profile.cpp_macro),
            "TSL-GENERATED-PROJECT-DUPLICATE-CPP-PROFILE-MACRO",
        )
    )
    diagnostics.extend(
        _duplicate_field_diagnostics(
            profiles,
            "Rust feature",
            lambda profile: str(profile.rust_feature),
            "TSL-GENERATED-PROJECT-DUPLICATE-RUST-PROFILE-FEATURE",
        )
    )
    diagnostics.extend(
        _duplicate_field_diagnostics(
            profiles,
            "Rust module",
            lambda profile: str(profile.rust_module),
            "TSL-GENERATED-PROJECT-DUPLICATE-RUST-PROFILE-MODULE",
        )
    )
    return _sort_diagnostics(diagnostics)


def _duplicate_field_diagnostics(
    profiles: tuple[BackendProfileRenderModel, ...],
    label: str,
    value_of: Callable[[BackendProfileRenderModel], str],
    code: str,
) -> tuple[Diagnostic, ...]:
    values: dict[str, list[str]] = {}
    for profile in profiles:
        value = value_of(profile)
        values.setdefault(value, []).append(str(profile.profile_name))
    return tuple(
        Diagnostic(
            severity="error",
            code=code,
            message=(
                f"generated profile {label} {value!r} is shared by "
                f"{', '.join(sorted(names))}"
            ),
        )
        for value, names in values.items()
        if len(names) > 1
    )


def _cpp_template_values(project: BackendProjectRenderModel) -> dict[str, str]:
    return {
        "allowed_profiles": " ".join(
            f'"{profile.profile_name}"' for profile in project.profiles
        ),
        "cpp_profile_cases": _cpp_profile_cases(project),
        "default_profile": str(project.default_profile),
        "project_name": project.project_name,
    }


def _rust_template_values(project: BackendProjectRenderModel) -> dict[str, str]:
    default = _profile_by_name(project, project.default_profile)
    return {
        "default_rust_feature": str(default.rust_feature),
        "feature_entries": "\n".join(
            f'{profile.rust_feature} = []' for profile in project.profiles
        ),
        "package_name": project.project_name,
        "profile_metadata_entries": _rust_profile_metadata_entries(project),
    }


def _cpp_profile_cases(project: BackendProjectRenderModel) -> str:
    lines: list[str] = []
    for index, profile in enumerate(project.profiles):
        keyword = "if" if index == 0 else "elseif"
        lines.extend(
            (
                f'{keyword}(TSL_PROFILE STREQUAL "{profile.profile_name}")',
                f"  target_compile_definitions(tsl_generated INTERFACE {profile.cpp_macro})",
            )
        )
        if profile.cpp_target_feature_options:
            options = " ".join(
                str(option) for option in profile.cpp_target_feature_options
            )
            lines.append(f"  target_compile_options(tsl_generated INTERFACE {options})")
    lines.extend(
        (
            "else()",
            '  message(FATAL_ERROR "Unsupported TSL_PROFILE ${TSL_PROFILE}")',
            "endif()",
        )
    )
    return "\n".join(lines)


def _rust_profile_metadata_entries(project: BackendProjectRenderModel) -> str:
    lines: list[str] = []
    for index, profile in enumerate(project.profiles):
        if index > 0:
            lines.append("")
        lines.extend(
            (
                "[package.metadata.tsl.profiles."
                f'"{_toml_escape(str(profile.profile_name))}"]',
                f"target_features = {_toml_string_array(profile.rust_target_features)}",
                "rustflags = "
                f"{_toml_string_array(_rust_target_feature_rustflags(profile))}",
            )
        )
    return "\n".join(lines)


def _cpp_artifacts(project: BackendProjectRenderModel) -> tuple[Artifact, ...]:
    artifacts = [
        _artifact(
            "cpp/include/tsl.hpp",
            _cpp_public_header(project),
            "text/x-c++hdr",
            project.backend_id,
        ),
        _artifact(
            "cpp/tests/smoke.cpp",
            _cpp_smoke_test(),
            "text/x-c++src",
            project.backend_id,
        ),
    ]
    for profile in project.profiles:
        artifacts.append(
            _artifact(
                f"cpp/include/profiles/{profile.file_stem}.hpp",
                _cpp_profile_header(profile),
                "text/x-c++hdr",
                project.backend_id,
                str(profile.profile_name),
            )
        )
    return tuple(artifacts)


def _rust_artifacts(project: BackendProjectRenderModel) -> tuple[Artifact, ...]:
    artifacts = [
        _artifact(
            "rust/src/lib.rs",
            _rust_public_lib(project),
            "text/x-rust",
            project.backend_id,
        ),
        _artifact(
            "rust/tests/smoke.rs",
            _rust_smoke_test(project.project_name),
            "text/x-rust",
            project.backend_id,
        ),
    ]
    for profile in project.profiles:
        artifacts.append(
            _artifact(
                f"rust/src/profiles/{profile.file_stem}.rs",
                _rust_profile_module(profile),
                "text/x-rust",
                project.backend_id,
                str(profile.profile_name),
            )
        )
    return tuple(artifacts)


def _cpp_public_header(project: BackendProjectRenderModel) -> str:
    lines = ["#pragma once", ""]
    for index, profile in enumerate(project.profiles):
        directive = "#if" if index == 0 else "#elif"
        lines.append(f"{directive} defined({profile.cpp_macro})")
        lines.append(f'#include "profiles/{profile.file_stem}.hpp"')
    lines.extend(
        (
            "#else",
            '#error "No supported TSL profile selected"',
            "#endif",
            "",
        )
    )
    return "\n".join(lines)


def _cpp_profile_header(profile: BackendProfileRenderModel) -> str:
    namespace = _cpp_identifier(str(profile.file_stem))
    return "\n".join(
        (
            "#pragma once",
            "",
            f"namespace tsl::profiles::{namespace} {{",
            "",
            f'inline constexpr const char* name = "{profile.profile_name}";',
            f'inline constexpr const char* family = "{profile.family}";',
            "",
            f"}}  // namespace tsl::profiles::{namespace}",
            "",
            "namespace tsl {",
            "",
            f"inline constexpr const char* active_profile = profiles::{namespace}::name;",
            f"inline constexpr const char* active_profile_family = profiles::{namespace}::family;",
            "",
            "}  // namespace tsl",
            "",
        )
    )


def _cpp_smoke_test() -> str:
    return "\n".join(
        (
            "#include <tsl.hpp>",
            "",
            "int main() {",
            "  return tsl::active_profile[0] == '\\0';",
            "}",
            "",
        )
    )


def _rust_public_lib(project: BackendProjectRenderModel) -> str:
    conflict_lines = _rust_conflict_checks(project.profiles)
    module_lines = [
        "pub mod profiles {",
        *(
            f'    #[cfg(feature = "{profile.rust_feature}")]\n'
            f"    pub mod {profile.rust_module};"
            for profile in project.profiles
        ),
        "}",
        "",
    ]
    reexport_lines = [
        f'#[cfg(feature = "{profile.rust_feature}")]\n'
        f"pub use profiles::{profile.rust_module}::*;"
        for profile in project.profiles
    ]
    return "\n".join(
        (
            *conflict_lines,
            *module_lines,
            *reexport_lines,
            "",
        )
    )


def _rust_conflict_checks(
    profiles: tuple[BackendProfileRenderModel, ...],
) -> tuple[str, ...]:
    feature_conditions = tuple(
        f'feature = "{profile.rust_feature}"' for profile in profiles
    )
    lines = [
        f"#[cfg(not(any({', '.join(feature_conditions)})))]",
        'compile_error!("exactly one TSL profile feature must be enabled");',
        "",
    ]
    for left_index, left in enumerate(profiles):
        for right in profiles[left_index + 1 :]:
            lines.extend(
                (
                    f'#[cfg(all(feature = "{left.rust_feature}", '
                    f'feature = "{right.rust_feature}"))]',
                    'compile_error!("exactly one TSL profile feature must be enabled");',
                    "",
                )
            )
    return tuple(lines)


def _rust_profile_module(profile: BackendProfileRenderModel) -> str:
    return "\n".join(
        (
            f'pub const ACTIVE_PROFILE: &str = "{profile.profile_name}";',
            f'pub const ACTIVE_PROFILE_FAMILY: &str = "{profile.family}";',
            "",
        )
    )


def _rust_smoke_test(package_name: str) -> str:
    crate_name = package_name.replace("-", "_")
    return "\n".join(
        (
            "#[test]",
            "fn smoke_active_profile_is_selected() {",
            f"    assert!(!{crate_name}::ACTIVE_PROFILE.is_empty());",
            "}",
            "",
        )
    )


def _load_template(
    root: Path,
    relative_path: str,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    path = root / relative_path
    if not path.is_file():
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROJECT-MISSING-TEMPLATE",
                    message=f"missing generated project template {relative_path!r}",
                ),
            ),
        )
    return path.read_text(encoding="utf-8"), ()


def _template_diagnostics(
    template_path: str,
    template_text: str,
    values: dict[str, str],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for _, field_name, _, _ in Formatter().parse(template_text):
        if field_name is None:
            continue
        root_name = field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        if root_name != field_name:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROJECT-TEMPLATE-UNSUPPORTED-FIELD-SHAPE",
                    message=(
                        f"generated project template {template_path!r} uses "
                        f"unsupported field shape {field_name!r}"
                    ),
                )
            )
            continue
        if root_name not in _ALLOWED_TEMPLATE_FIELDS or root_name not in values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROJECT-TEMPLATE-UNKNOWN-FIELD",
                    message=(
                        f"generated project template {template_path!r} "
                        f"references unsupported field {root_name!r}"
                    ),
                )
            )
    return tuple(diagnostics)


def _artifact(
    logical_path: str,
    content: str,
    media_type: str,
    backend_id: str,
    profile_name: str | None = None,
) -> Artifact:
    metadata = [ArtifactMetadata("backend", backend_id)]
    if profile_name is not None:
        metadata.append(ArtifactMetadata("profile", profile_name))
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
        metadata=tuple(metadata),
    )


def _profile_by_name(
    project: BackendProjectRenderModel,
    name: MachineProfileName,
) -> BackendProfileRenderModel:
    for profile in project.profiles:
        if profile.profile_name == name:
            return profile
    raise ValueError(f"profile {name!r} is not in project {project.backend_id!r}")


def _build_feature_spellings(
    profile: MachineFeatureProfile,
    flag_catalog: FeatureFlagNormalizationCatalog | None,
) -> tuple[tuple[str, ...], tuple[Diagnostic, ...]]:
    spellings: list[str] = []
    diagnostics: list[Diagnostic] = []
    for feature in profile.features:
        spelling, diagnostic = _build_feature_spelling(profile, feature, flag_catalog)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        assert spelling is not None
        spellings.append(spelling)
    return tuple(spellings), tuple(diagnostics)


def _build_feature_spelling(
    profile: MachineFeatureProfile,
    feature: FeatureFlagName,
    flag_catalog: FeatureFlagNormalizationCatalog | None,
) -> tuple[str | None, Diagnostic | None]:
    for alternative in profile.alternatives:
        if alternative.feature == feature:
            return str(alternative.spelling), None
    if flag_catalog is None:
        return None, Diagnostic(
            severity="error",
            code="TSL-GENERATED-PROJECT-MISSING-FLAG-CATALOG",
            message=(
                f"generated profile {str(profile.name)!r} requires feature "
                f"spelling data for {str(feature)!r}"
            ),
            location=profile.source,
        )

    matches = tuple(
        entry for entry in flag_catalog.entries if entry.normalized == feature
    )
    if not matches:
        return None, Diagnostic(
            severity="error",
            code="TSL-GENERATED-PROJECT-MISSING-FLAG-SPELLING",
            message=(
                f"generated profile {str(profile.name)!r} feature "
                f"{str(feature)!r} has no spelling in the feature flag catalog"
            ),
            location=profile.source,
        )
    selected = min(
        matches,
        key=lambda entry: (
            str(entry.source.path),
            entry.source.line,
            entry.source.column,
            str(entry.spelling),
        ),
    )
    return str(selected.spelling), None


def _rust_target_feature_rustflags(
    profile: BackendProfileRenderModel,
) -> tuple[str, ...]:
    if not profile.rust_target_features:
        return ()
    target_features = ",".join(str(feature) for feature in profile.rust_target_features)
    return ("-C", f"target-feature={target_features}")


def _toml_string_array(values: tuple[object, ...]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(f'"{_toml_escape(str(value))}"' for value in values) + "]"


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _sanitize_file_stem(value: str) -> str:
    chars: list[str] = []
    previous_was_separator = False
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    result = "".join(chars).strip("_")
    if not result:
        return "profile"
    if result[0].isdigit():
        return f"profile_{result}"
    return result


def _cpp_identifier(value: str) -> str:
    result = _sanitize_file_stem(value)
    if result[0].isdigit():
        return f"profile_{result}"
    return result


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
