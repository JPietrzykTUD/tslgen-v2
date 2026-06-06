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


_CPP_CMAKE_TEMPLATE = "buildsystem/cpp/templates/generated_project_CMakeLists.txt.in"
_RUST_CARGO_TEMPLATE = "buildsystem/rust/templates/generated_project_Cargo.toml.in"
_CPP_PUBLIC_HEADER_TEMPLATE = "templates/cpp/generated_project/public_header.hpp.in"
_CPP_PUBLIC_HEADER_FIRST_PROFILE_CASE_TEMPLATE = (
    "templates/cpp/generated_project/public_header_first_profile_case.hpp.in"
)
_CPP_PUBLIC_HEADER_NEXT_PROFILE_CASE_TEMPLATE = (
    "templates/cpp/generated_project/public_header_next_profile_case.hpp.in"
)
_CPP_PROFILE_HEADER_TEMPLATE = "templates/cpp/generated_project/profile_header.hpp.in"
_CPP_SMOKE_TEST_TEMPLATE = "templates/cpp/generated_project/smoke.cpp.in"
_RUST_PUBLIC_LIB_TEMPLATE = "templates/rust/generated_project/lib.rs.in"
_RUST_FEATURE_CONDITION_TEMPLATE = (
    "templates/rust/generated_project/lib_feature_condition.rs.in"
)
_RUST_CONFLICT_NO_PROFILE_TEMPLATE = (
    "templates/rust/generated_project/lib_conflict_no_profile.rs.in"
)
_RUST_CONFLICT_PAIR_TEMPLATE = (
    "templates/rust/generated_project/lib_conflict_pair.rs.in"
)
_RUST_PROFILE_MODULE_DECL_TEMPLATE = (
    "templates/rust/generated_project/lib_profile_module_decl.rs.in"
)
_RUST_PROFILE_REEXPORT_TEMPLATE = (
    "templates/rust/generated_project/lib_profile_reexport.rs.in"
)
_RUST_PROFILE_MODULE_TEMPLATE = "templates/rust/generated_project/profile_module.rs.in"
_RUST_SMOKE_TEST_TEMPLATE = "templates/rust/generated_project/smoke.rs.in"

_GENERATED_PROJECT_TEMPLATE_PATHS = (
    _CPP_CMAKE_TEMPLATE,
    _RUST_CARGO_TEMPLATE,
    _CPP_PUBLIC_HEADER_TEMPLATE,
    _CPP_PUBLIC_HEADER_FIRST_PROFILE_CASE_TEMPLATE,
    _CPP_PUBLIC_HEADER_NEXT_PROFILE_CASE_TEMPLATE,
    _CPP_PROFILE_HEADER_TEMPLATE,
    _CPP_SMOKE_TEST_TEMPLATE,
    _RUST_PUBLIC_LIB_TEMPLATE,
    _RUST_FEATURE_CONDITION_TEMPLATE,
    _RUST_CONFLICT_NO_PROFILE_TEMPLATE,
    _RUST_CONFLICT_PAIR_TEMPLATE,
    _RUST_PROFILE_MODULE_DECL_TEMPLATE,
    _RUST_PROFILE_REEXPORT_TEMPLATE,
    _RUST_PROFILE_MODULE_TEMPLATE,
    _RUST_SMOKE_TEST_TEMPLATE,
)

_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "allowed_profiles",
        "cpp_profile_cases",
        "default_profile",
        "default_rust_feature",
        "feature_entries",
        "family",
        "feature_conditions",
        "file_stem",
        "conflict_checks",
        "cpp_macro",
        "crate_name",
        "left_rust_feature",
        "namespace",
        "package_name",
        "profile_include_cases",
        "project_name",
        "profile_metadata_entries",
        "profile_module_declarations",
        "profile_name",
        "profile_reexports",
        "right_rust_feature",
        "rust_feature",
        "rust_module",
    }
)

_SEMANTIC_TEMPLATE_FIELDS = frozenset(
    {
        "backend_metadata_key",
        "backend_translation_key",
        "dependency",
        "dependency_rules",
        "extension",
        "fallback",
        "feature_gate",
        "intrinsic",
        "intrinsic_name",
        "lowering_request",
        "overload",
        "primitive",
        "primitive_name",
        "primitive_selector",
        "selector",
        "source",
        "source_payload",
        "tsil",
        "type",
        "type_spelling",
        "type_tag",
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

    templates, template_diagnostics = _load_templates(
        supplementary_root,
        _GENERATED_PROJECT_TEMPLATE_PATHS,
    )
    diagnostics.extend(template_diagnostics)
    if diagnostics:
        return GeneratedProjectRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    cpp_values = _cpp_template_values(model.cpp)
    rust_values = _rust_template_values(model.rust)
    cpp_content, cpp_diagnostics = _render_template(
        _CPP_CMAKE_TEMPLATE,
        templates[_CPP_CMAKE_TEMPLATE],
        cpp_values,
    )
    rust_content, rust_diagnostics = _render_template(
        _RUST_CARGO_TEMPLATE,
        templates[_RUST_CARGO_TEMPLATE],
        rust_values,
    )
    diagnostics.extend(cpp_diagnostics)
    diagnostics.extend(rust_diagnostics)
    if diagnostics:
        return GeneratedProjectRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    assert cpp_content is not None
    assert rust_content is not None
    artifacts.append(
        _artifact(
            "cpp/CMakeLists.txt",
            cpp_content,
            "text/x-cmake",
            model.cpp.backend_id,
        )
    )
    artifacts.append(
        _artifact(
            "rust/Cargo.toml",
            rust_content,
            "text/toml",
            model.rust.backend_id,
        )
    )
    cpp_artifacts, cpp_artifact_diagnostics = _cpp_artifacts(model.cpp, templates)
    rust_artifacts, rust_artifact_diagnostics = _rust_artifacts(model.rust, templates)
    diagnostics.extend(cpp_artifact_diagnostics)
    diagnostics.extend(rust_artifact_diagnostics)
    if diagnostics:
        return GeneratedProjectRenderResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )
    artifacts.extend(cpp_artifacts)
    artifacts.extend(rust_artifacts)

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


def _cpp_artifacts(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[tuple[Artifact, ...], tuple[Diagnostic, ...]]:
    artifacts: list[Artifact] = []
    diagnostics: list[Diagnostic] = []

    public_header_values, public_header_value_diagnostics = _cpp_public_header_values(
        project,
        templates,
    )
    diagnostics.extend(public_header_value_diagnostics)
    public_header: str | None = None
    public_header_diagnostics: tuple[Diagnostic, ...] = ()
    if not public_header_value_diagnostics:
        public_header, public_header_diagnostics = _render_template(
            _CPP_PUBLIC_HEADER_TEMPLATE,
            templates[_CPP_PUBLIC_HEADER_TEMPLATE],
            public_header_values,
        )
    smoke_test, smoke_test_diagnostics = _render_template(
        _CPP_SMOKE_TEST_TEMPLATE,
        templates[_CPP_SMOKE_TEST_TEMPLATE],
        {},
    )
    diagnostics.extend(public_header_diagnostics)
    diagnostics.extend(smoke_test_diagnostics)
    if public_header is not None:
        artifacts.append(
            _artifact(
                "cpp/include/tsl.hpp",
                public_header,
                "text/x-c++hdr",
                project.backend_id,
            )
        )
    if smoke_test is not None:
        artifacts.append(
            _artifact(
                "cpp/tests/smoke.cpp",
                smoke_test,
                "text/x-c++src",
                project.backend_id,
            )
        )

    for profile in project.profiles:
        profile_header, profile_diagnostics = _render_template(
            _CPP_PROFILE_HEADER_TEMPLATE,
            templates[_CPP_PROFILE_HEADER_TEMPLATE],
            _cpp_profile_header_values(profile),
        )
        diagnostics.extend(profile_diagnostics)
        if profile_header is not None:
            artifacts.append(
                _artifact(
                    f"cpp/include/profiles/{profile.file_stem}.hpp",
                    profile_header,
                    "text/x-c++hdr",
                    project.backend_id,
                    str(profile.profile_name),
                )
            )
    return tuple(artifacts), tuple(diagnostics)


def _rust_artifacts(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[tuple[Artifact, ...], tuple[Diagnostic, ...]]:
    artifacts: list[Artifact] = []
    diagnostics: list[Diagnostic] = []

    public_lib_values, public_lib_value_diagnostics = _rust_public_lib_values(
        project,
        templates,
    )
    diagnostics.extend(public_lib_value_diagnostics)
    public_lib: str | None = None
    public_lib_diagnostics: tuple[Diagnostic, ...] = ()
    if not public_lib_value_diagnostics:
        public_lib, public_lib_diagnostics = _render_template(
            _RUST_PUBLIC_LIB_TEMPLATE,
            templates[_RUST_PUBLIC_LIB_TEMPLATE],
            public_lib_values,
        )
    smoke_test, smoke_test_diagnostics = _render_template(
        _RUST_SMOKE_TEST_TEMPLATE,
        templates[_RUST_SMOKE_TEST_TEMPLATE],
        _rust_smoke_test_values(project.project_name),
    )
    diagnostics.extend(public_lib_diagnostics)
    diagnostics.extend(smoke_test_diagnostics)
    if public_lib is not None:
        artifacts.append(
            _artifact(
                "rust/src/lib.rs",
                public_lib,
                "text/x-rust",
                project.backend_id,
            )
        )
    if smoke_test is not None:
        artifacts.append(
            _artifact(
                "rust/tests/smoke.rs",
                smoke_test,
                "text/x-rust",
                project.backend_id,
            )
        )

    for profile in project.profiles:
        profile_module, profile_diagnostics = _render_template(
            _RUST_PROFILE_MODULE_TEMPLATE,
            templates[_RUST_PROFILE_MODULE_TEMPLATE],
            _profile_template_values(profile),
        )
        diagnostics.extend(profile_diagnostics)
        if profile_module is not None:
            artifacts.append(
                _artifact(
                    f"rust/src/profiles/{profile.file_stem}.rs",
                    profile_module,
                    "text/x-rust",
                    project.backend_id,
                    str(profile.profile_name),
                )
            )
    return tuple(artifacts), tuple(diagnostics)


def _cpp_public_header_values(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[dict[str, str], tuple[Diagnostic, ...]]:
    include_cases, diagnostics = _cpp_profile_include_cases(project, templates)
    return {"profile_include_cases": include_cases}, diagnostics


def _cpp_profile_include_cases(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[str, tuple[Diagnostic, ...]]:
    cases: list[str] = []
    diagnostics: list[Diagnostic] = []
    for index, profile in enumerate(project.profiles):
        template_path = (
            _CPP_PUBLIC_HEADER_FIRST_PROFILE_CASE_TEMPLATE
            if index == 0
            else _CPP_PUBLIC_HEADER_NEXT_PROFILE_CASE_TEMPLATE
        )
        rendered, fragment_diagnostics = _render_template(
            template_path,
            templates[template_path],
            {
                "cpp_macro": str(profile.cpp_macro),
                "file_stem": str(profile.file_stem),
            },
        )
        if fragment_diagnostics:
            diagnostics.extend(fragment_diagnostics)
            continue
        assert rendered is not None
        cases.append(rendered.rstrip())
    return "\n".join(cases), tuple(diagnostics)


def _cpp_profile_header_values(profile: BackendProfileRenderModel) -> dict[str, str]:
    return {
        **_profile_template_values(profile),
        "namespace": _cpp_identifier(str(profile.file_stem)),
    }


def _rust_public_lib_values(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[dict[str, str], tuple[Diagnostic, ...]]:
    conflict_checks, conflict_diagnostics = _rust_conflict_checks(
        project.profiles,
        templates,
    )
    declarations, declaration_diagnostics = _rust_profile_module_declarations(
        project,
        templates,
    )
    reexports, reexport_diagnostics = _rust_profile_reexports(project, templates)
    diagnostics = (
        *conflict_diagnostics,
        *declaration_diagnostics,
        *reexport_diagnostics,
    )
    return {
        "conflict_checks": conflict_checks,
        "profile_module_declarations": declarations,
        "profile_reexports": reexports,
    }, diagnostics


def _rust_conflict_checks(
    profiles: tuple[BackendProfileRenderModel, ...],
    templates: dict[str, str],
) -> tuple[str, tuple[Diagnostic, ...]]:
    rendered: list[str] = []
    diagnostics: list[Diagnostic] = []
    feature_conditions, feature_condition_diagnostics = _rust_feature_conditions(
        profiles,
        templates,
    )
    diagnostics.extend(feature_condition_diagnostics)
    no_profile, no_profile_diagnostics = _render_template(
        _RUST_CONFLICT_NO_PROFILE_TEMPLATE,
        templates[_RUST_CONFLICT_NO_PROFILE_TEMPLATE],
        {"feature_conditions": feature_conditions},
    )
    if no_profile_diagnostics:
        diagnostics.extend(no_profile_diagnostics)
    else:
        assert no_profile is not None
        rendered.append(no_profile.rstrip())
    for left_index, left in enumerate(profiles):
        for right in profiles[left_index + 1 :]:
            pair, pair_diagnostics = _render_template(
                _RUST_CONFLICT_PAIR_TEMPLATE,
                templates[_RUST_CONFLICT_PAIR_TEMPLATE],
                {
                    "left_rust_feature": str(left.rust_feature),
                    "right_rust_feature": str(right.rust_feature),
                },
            )
            if pair_diagnostics:
                diagnostics.extend(pair_diagnostics)
            else:
                assert pair is not None
                rendered.append(pair.rstrip())
    return "\n\n".join(rendered), tuple(diagnostics)


def _rust_feature_conditions(
    profiles: tuple[BackendProfileRenderModel, ...],
    templates: dict[str, str],
) -> tuple[str, tuple[Diagnostic, ...]]:
    rendered: list[str] = []
    diagnostics: list[Diagnostic] = []
    for profile in profiles:
        condition, condition_diagnostics = _render_template(
            _RUST_FEATURE_CONDITION_TEMPLATE,
            templates[_RUST_FEATURE_CONDITION_TEMPLATE],
            _rust_profile_template_values(profile),
        )
        if condition_diagnostics:
            diagnostics.extend(condition_diagnostics)
        else:
            assert condition is not None
            rendered.append(condition.rstrip())
    return ", ".join(rendered), tuple(diagnostics)


def _rust_profile_module_declarations(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[str, tuple[Diagnostic, ...]]:
    rendered: list[str] = []
    diagnostics: list[Diagnostic] = []
    for profile in project.profiles:
        module, module_diagnostics = _render_template(
            _RUST_PROFILE_MODULE_DECL_TEMPLATE,
            templates[_RUST_PROFILE_MODULE_DECL_TEMPLATE],
            _rust_profile_template_values(profile),
        )
        if module_diagnostics:
            diagnostics.extend(module_diagnostics)
        else:
            assert module is not None
            rendered.append(module.rstrip())
    return "\n".join(rendered), tuple(diagnostics)


def _rust_profile_reexports(
    project: BackendProjectRenderModel,
    templates: dict[str, str],
) -> tuple[str, tuple[Diagnostic, ...]]:
    rendered: list[str] = []
    diagnostics: list[Diagnostic] = []
    for profile in project.profiles:
        reexport, reexport_diagnostics = _render_template(
            _RUST_PROFILE_REEXPORT_TEMPLATE,
            templates[_RUST_PROFILE_REEXPORT_TEMPLATE],
            _rust_profile_template_values(profile),
        )
        if reexport_diagnostics:
            diagnostics.extend(reexport_diagnostics)
        else:
            assert reexport is not None
            rendered.append(reexport.rstrip())
    return "\n\n".join(rendered), tuple(diagnostics)


def _rust_profile_template_values(profile: BackendProfileRenderModel) -> dict[str, str]:
    return {
        **_profile_template_values(profile),
        "rust_feature": str(profile.rust_feature),
        "rust_module": str(profile.rust_module),
    }


def _profile_template_values(profile: BackendProfileRenderModel) -> dict[str, str]:
    return {
        "family": str(profile.family),
        "file_stem": str(profile.file_stem),
        "profile_name": str(profile.profile_name),
    }


def _rust_smoke_test_values(package_name: str) -> dict[str, str]:
    return {"crate_name": package_name.replace("-", "_")}


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


def _load_templates(
    root: Path,
    relative_paths: tuple[str, ...],
) -> tuple[dict[str, str], tuple[Diagnostic, ...]]:
    templates: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    for relative_path in relative_paths:
        template_text, template_diagnostics = _load_template(root, relative_path)
        diagnostics.extend(template_diagnostics)
        if template_text is not None:
            templates[relative_path] = template_text
    return templates, tuple(diagnostics)


def _render_template(
    template_path: str,
    template_text: str,
    values: dict[str, str],
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    diagnostics = _template_diagnostics(template_path, template_text, values)
    if diagnostics:
        return None, diagnostics
    return template_text.format_map(values), ()


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
        if root_name in _SEMANTIC_TEMPLATE_FIELDS:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROJECT-TEMPLATE-SEMANTIC-FIELD",
                    message=(
                        f"generated project template {template_path!r} "
                        f"references semantic field {root_name!r}"
                    ),
                )
            )
            continue
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
            str(entry.spelling) != str(feature),
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
