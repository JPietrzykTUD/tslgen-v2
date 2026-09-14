"""Pipeline facade ownership checks."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from tslc import api, pipeline
from tslc import pipeline_request
from tslc._pipeline_target_support import TargetSupportRecorder
from tslc.backend import (
    cpp_build_policy,
    cpp_profile,
    cpp_verification,
    rust_verification,
)
from tslc.backend.capability import (
    BackendCapability,
    BackendProjectConfigSpec,
    CompilerCapability,
    CompilerCapabilityRegistry,
)
from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.cpp_compiler_capabilities import CPP_COMPILER_CAPABILITIES
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    BackendHelperPlan,
    CPP_HELPER_MANIFEST,
    HelperFeature,
    PrimitiveRequirement,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.rust_capability import RUST_BACKEND
from tslc.benchmark.model import EMPTY_BENCHMARK_PROJECT_PLAN
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.catalog.semantics import (
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
)
from tslc.catalog.validation import validate_catalog
from tslc.compiler_assets import RenderAssets, load_default_render_assets
from tslc.lower.lowerer import (
    POLICY_DEFERRED_SIGNATURE_CODE,
    LoweredSpecialization,
)
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile
from tslc.project_config import load_project_config
from tslc.project_render import BackendRenderInput, ProjectRenderConfig
from tslc.render import cpp_build, cpp_project, rust_project
from tslc.render.project import render_project
from tslc.select.selector import Selector
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.target_text import LoweredBody
from tslc.target_support import TargetSupportKey, TargetSupportRealizationKey
from tslc.value_tests.model import ValueTestProjectPlan

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class _FakeRenderInput(BackendRenderInput):
    label: str = "fake"


class _OtherRenderInput(BackendRenderInput):
    pass


def test_backend_render_inputs_are_typed_frozen_and_duplicate_safe() -> None:
    value = _FakeRenderInput()
    config = ProjectRenderConfig.create((("future", value),))

    assert config.get("future", _FakeRenderInput) is value
    assert config.require("future", _FakeRenderInput) is value
    with pytest.raises(TypeError, match="must be _OtherRenderInput"):
        config.require("future", _OtherRenderInput)
    with pytest.raises(ValueError, match="requires a _FakeRenderInput"):
        config.require("missing", _FakeRenderInput)
    with pytest.raises(ValueError, match="duplicate backend render input 'future'"):
        ProjectRenderConfig.create((("future", value), ("future", value)))


def test_pipeline_facade_keeps_input_and_closure_boundaries() -> None:
    assert pipeline.generate.__module__ == "tslc.pipeline"
    assert pipeline.GenerationRequest.__module__ == "tslc.pipeline_request"
    assert pipeline._load_inputs.__module__ == "tslc._pipeline_inputs"
    assert pipeline._LoweringCache.__module__ == "tslc._pipeline_lowering_cache"
    assert (
        pipeline.ProfileGenerator.__module__
        == "tslc._pipeline_profile_generation"
    )
    assert TargetSupportRecorder.__module__ == "tslc._pipeline_target_support"
    assert pipeline._LoweredSlot.__module__ == "tslc._pipeline_closure"
    assert pipeline._prune_unresolved.__module__ == "tslc._pipeline_closure"
    assert (
        pipeline._profile_with_required_features.__module__
        == "tslc._pipeline_closure"
    )


def test_target_support_recorder_is_inert_when_disabled_and_rejects_missing_state(
) -> None:
    disabled = TargetSupportRecorder(enabled=False)
    assert not disabled.enabled
    assert disabled.trace() is None
    disabled.mark_lowered(None)

    enabled = TargetSupportRecorder(enabled=True)
    identity = (
        TargetSupportKey(
            profile="profile",
            backend="backend",
            primitive="primitive",
            signature="v:=v",
            attributes=(),
            result_target=None,
            overload=None,
            type_tag="si32",
            target_extension="extension",
            conversion_target=None,
        ),
        TargetSupportRealizationKey(
            source_extension="extension",
            selector_path=("extension", "type"),
            required_features=(),
            required_compiler_capabilities=(),
            concrete_lanes=None,
            simd_type_base_bindings=(),
            variant_names=(),
        ),
    )
    with pytest.raises(ValueError, match="no selected realization"):
        enabled.mark_lowered(identity)


def test_backend_defaults_are_resolved_at_request_construction(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pipeline_request, "registered_backend_ids", lambda: ("future",)
    )

    request = pipeline.GenerationRequest(
        source_paths=(),
        machine_profiles_path=Path("profiles.json"),
        primitives=(),
        profiles=(),
        type_tags=(),
    )

    assert request.backends == ("future",)


def test_backend_preview_presentation_is_capability_owned() -> None:
    future = replace(
        CPP_BACKEND,
        backend_id="future",
        root_path="future",
        artifact_media_type="text/future",
        preview_file_suffix="future",
    )

    assert CPP_BACKEND.preview_file_suffix == "hpp"
    assert RUST_BACKEND.preview_file_suffix == "rs"
    assert future.preview_file_suffix == "future"
    with pytest.raises(ValueError, match="backend preview file suffix"):
        replace(future, preview_file_suffix="")
    with pytest.raises(ValueError, match="backend preview file suffix"):
        replace(future, preview_file_suffix=".future")


def test_registered_backend_ids_preserve_capability_order(monkeypatch) -> None:
    from tslc.backend import registry

    monkeypatch.setattr(
        registry,
        "BACKEND_CAPABILITIES",
        (RUST_BACKEND, CPP_BACKEND),
    )

    assert registry.registered_backend_ids() == ("rust", "cpp")


def test_full_backend_inventory_detection_rejects_focused_requests() -> None:
    request = pipeline.GenerationRequest(
        source_paths=(),
        machine_profiles_path=Path("profiles.json"),
        primitives=None,
        profiles=None,
        type_tags=DEFAULT_SCALAR_TYPE_TAGS,
        backends=("rust",),
    )

    assert pipeline._request_has_complete_backend_inventory(request, "rust")
    assert pipeline._request_has_complete_backend_inventory(
        replace(
            request,
            backend_profile_scopes=(
                pipeline.BackendProfileScope("cpp", ("scalar",)),
            ),
        ),
        "rust",
    )
    focused_requests = (
        replace(request, primitives=("mul",)),
        replace(request, profiles=("sse2",)),
        replace(request, extensions=("sse",)),
        replace(request, type_tags=("si8",)),
        replace(
            request,
            backend_profile_scopes=(
                pipeline.BackendProfileScope("rust", ("sse2",)),
            ),
        ),
        replace(
            request,
            backend_compiler_capabilities=(
                pipeline.BackendCompilerCapabilitySet(
                    "rust", frozenset({"synthetic"})
                ),
            ),
        ),
    )
    assert all(
        not pipeline._request_has_complete_backend_inventory(item, "rust")
        for item in focused_requests
    )


def test_compiler_capability_vocabulary_is_backend_generic(monkeypatch) -> None:
    from tslc.backend import registry

    capability = CompilerCapability("future_feature")
    future = BackendCapability(
        backend_id="future",
        root_path="future",
        artifact_media_type="text/future",
        preview_file_suffix="future",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=_empty_backend_artifacts,
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
        compiler_capabilities=CompilerCapabilityRegistry((capability,)),
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (future,))
    monkeypatch.setattr(registry, "_BY_ID", {"future": future})

    assert future.compiler_capability("future_feature") is capability
    assert registry.registered_compiler_capabilities() == {
        "future": frozenset({"future_feature"})
    }
    assert CPP_BACKEND.compiler_capabilities is CPP_COMPILER_CAPABILITIES


def test_public_api_resolves_omitted_backends_for_each_call(monkeypatch) -> None:
    captured: list[pipeline.GenerationRequest] = []

    monkeypatch.setattr(api, "registered_backend_ids", lambda: ("future",))
    monkeypatch.setattr(api, "generate", lambda request: captured.append(request))

    api.generate_project((), machine_profiles_path=Path("profiles.json"))

    assert captured[0].backends == ("future",)


def test_public_api_promotes_compiler_capabilities_to_typed_sets(
    monkeypatch,
) -> None:
    captured: list[pipeline.GenerationRequest] = []

    monkeypatch.setattr(api, "generate", lambda request: captured.append(request))

    api.generate_project(
        (),
        machine_profiles_path=Path("profiles.json"),
        backends=("cpp",),
        compiler_capabilities={
            "cpp": ("elementwise_clzg", "elementwise_clzg"),
        },
    )

    assert captured[0].backend_compiler_capabilities == (
        pipeline.BackendCompilerCapabilitySet(
            "cpp",
            frozenset({"elementwise_clzg"}),
        ),
    )


def test_public_api_promotes_backend_profiles_to_typed_scopes(monkeypatch) -> None:
    captured: list[pipeline.GenerationRequest] = []

    monkeypatch.setattr(api, "generate", lambda request: captured.append(request))

    api.generate_project(
        (),
        machine_profiles_path=Path("profiles.json"),
        backends=("cpp", "rust"),
        backend_profiles={"rust": ("sse2", "sse", "sse2")},
    )

    assert captured[0].backend_profile_scopes == (
        pipeline.BackendProfileScope("rust", ("sse", "sse2")),
    )


def test_pipeline_uses_lowering_owned_policy_code_and_one_slot_sort_key() -> None:
    tree = ast.parse((_REPO_ROOT / "tslc/src/tslc/pipeline.py").read_text())
    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert POLICY_DEFERRED_SIGNATURE_CODE not in string_literals
    assert "_slot_result_key" in function_names
    assert "_coverage_key" not in function_names
    assert "_skipped_key" not in function_names


def test_cpp_project_renderer_has_focused_owned_modules() -> None:
    assert cpp_project.cpp_artifacts.__module__ == "tslc.render.cpp_project"
    assert cpp_profile._cpp_registration.__module__ == "tslc.backend.cpp_profile"
    assert (
        cpp_build_policy.cpp_profile_flags.__module__
        == "tslc.backend.cpp_build_policy"
    )


def test_verification_projection_is_backend_owned() -> None:
    assert (
        cpp_verification.cpp_verify_profile.__module__
        == "tslc.backend.cpp_verification"
    )
    assert (
        rust_verification.rust_verify_profile.__module__
        == "tslc.backend.rust_verification"
    )
    assert not hasattr(cpp_build, "cpp_verify_profile")
    assert not hasattr(rust_project, "rust_verify_profile")


def test_render_assets_have_one_packaged_source_of_truth() -> None:
    assets = load_default_render_assets()
    assert {
        "cpp_benchmark.cpp.tmpl",
        "cpp_dispatch.hpp.tmpl",
        "cpp_dispatch_algorithm_include.hpp",
        "cpp_dispatch_case.hpp.tmpl",
        "cpp_dispatch_overlay.hpp.tmpl",
        "cpp_documentation.hpp.tmpl",
        "cpp_profile_header.hpp.tmpl",
        "cpp_profile_metadata.hpp.tmpl",
        "cpp_primitive_tags.hpp.tmpl",
        "cpp_smoke.cpp.tmpl",
        "rust_benchmark.rs.tmpl",
        "rust_benchmark_main.rs.tmpl",
        "rust_benchmark_target.toml.tmpl",
        "rust_build.rs",
        "rust_documentation.rs.tmpl",
        "rust_facade.rs.tmpl",
        "rust_lib.rs.tmpl",
        "rust_lib_benchmark_profile.rs.tmpl",
        "rust_lib_profile.rs.tmpl",
        "rust_primitive_tags.rs.tmpl",
        "rust_profile_module.rs.tmpl",
        "rust_profile_metadata.rs.tmpl",
        "rust_readme.md.tmpl",
        "rust_smoke.rs",
        "tsl_benchmark_core.rs",
    } <= assets.files.keys()
    assert "int main(int argc, char** argv)" in assets.text(
        "cpp_benchmark.cpp.tmpl"
    )
    assert "namespace tsl::profiles::@{profile_namespace}" in assets.text(
        "cpp_profile_metadata.hpp.tmpl"
    )
    for retired_tree in (
        "supplementary/buildsystem/cpp",
        "supplementary/buildsystem/rust",
        "supplementary/helpers",
        "supplementary/templates",
    ):
        assert not any(
            path.is_file() for path in (_REPO_ROOT / retired_tree).rglob("*")
        )


def test_backend_closure_seed_primitives_are_capability_owned(catalog) -> None:
    fake_manifest = BackendHelperManifest(
        "fake",
        (
            HelperFeature(
                "read",
                (PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT),),
            ),
        ),
    )
    fake = BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        preview_file_suffix="fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=_empty_backend_artifacts,
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
        helper_manifest=fake_manifest,
    )
    fake_plan = fake.helper_plan(catalog)

    assert fake.closure_seed_primitives(catalog, fake_plan) == ("load",)
    assert CPP_BACKEND.helper_manifest is CPP_HELPER_MANIFEST
    assert RUST_BACKEND.helper_manifest is RUST_HELPER_MANIFEST
    cpp_plan = CPP_BACKEND.helper_plan(catalog)
    rust_plan = RUST_BACKEND.helper_plan(catalog)
    assert CPP_BACKEND.closure_seed_primitives(catalog, cpp_plan) == (
        "load",
        "store",
        "gather_narrow",
        "to_integral",
        "to_mask",
        "compress_store",
        "mask_population_count",
        "mask_binary_and",
    )
    assert rust_plan.closure_seed_primitives == (
        "load",
        "store",
        "set_zero",
        "to_array",
        "from_array",
        "gather_narrow",
        "compress_store",
        "mask_population_count",
        "to_integral",
        "to_mask",
    )
    assert RUST_BACKEND.closure_seed_primitives(
        catalog, rust_plan
    )[: len(rust_plan.closure_seed_primitives)] == rust_plan.closure_seed_primitives
    assert BackendHelperPlan.resolve(fake_manifest, catalog) == fake_plan


def test_fake_third_backend_resolves_its_own_helper_plan(catalog) -> None:
    manifest = BackendHelperManifest(
        "future",
        (
            HelperFeature(
                "read",
                (PrimitiveRequirement(CONTIGUOUS_VECTOR_LOAD_REQUIREMENT),),
            ),
        ),
    )
    capability = replace(CPP_BACKEND, backend_id="future", helper_manifest=manifest)

    plan = capability.helper_plan(catalog)

    assert plan.backend_id == "future"
    assert plan.closure_seed_primitives == ("load",)


def test_backend_capability_owns_optional_benchmark_planning(catalog) -> None:
    calls: list[str] = []

    def plan_benchmarks(  # noqa: ANN001
        catalog,
        profiles,
        value_tests,
        policy_inputs,
        extension_header_group,
    ):
        del catalog, profiles, value_tests, policy_inputs
        assert extension_header_group(None) is None
        calls.append("future")
        return EMPTY_BENCHMARK_PROJECT_PLAN

    future = BackendCapability(
        backend_id="future",
        root_path="future",
        artifact_media_type="text/future",
        preview_file_suffix="future",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=_empty_backend_artifacts,
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
        benchmark_plan_builder=plan_benchmarks,
    )

    planned = future.plan_benchmarks(catalog, (), ValueTestProjectPlan(profiles=()))

    assert planned is EMPTY_BENCHMARK_PROJECT_PLAN
    assert calls == ["future"]


def test_neutral_planners_do_not_branch_on_registered_backend_names() -> None:
    pipeline_tree = ast.parse(
        (_REPO_ROOT / "tslc/src/tslc/pipeline.py").read_text()
    )
    value_planner_tree = ast.parse(
        (_REPO_ROOT / "tslc/src/tslc/value_tests/planner.py").read_text()
    )
    benchmark_planner_tree = ast.parse(
        (_REPO_ROOT / "tslc/src/tslc/benchmark/planner.py").read_text()
    )

    pipeline_literals = {
        node.value
        for node in ast.walk(pipeline_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    value_planner_literals = {
        node.value
        for node in ast.walk(value_planner_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    benchmark_planner_literals = {
        node.value
        for node in ast.walk(benchmark_planner_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "cpp" not in pipeline_literals
    assert "rust" not in value_planner_literals
    assert "rust" not in benchmark_planner_literals


def test_generic_lowering_does_not_branch_on_registered_backend_names() -> None:
    lower_root = _REPO_ROOT / "tslc/src/tslc/lower"
    offenders: list[str] = []
    for path in sorted(lower_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path}:{node.lineno}:{node.value}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and node.value in {"cpp", "rust"}
        )

    assert offenders == []


def test_fake_backend_drives_config_documentation_and_artifact_media_type(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from tslc.backend import registry

    received_config: list[_FakeRenderInput] = []

    def parse_config(path: Path, value: object) -> _FakeRenderInput:
        assert path == (tmp_path / "tslc.toml").resolve()
        assert value == {"label": "configured"}
        return _FakeRenderInput("configured")

    def artifact_renderer(
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
        benchmarks: object,
        assets: RenderAssets,
        media_type: str,
        config: ProjectRenderConfig,
        policy_inputs: object,
        helper_plan: object,
    ) -> list[Artifact]:
        del profiles, value_tests, benchmarks, assets, policy_inputs, helper_plan
        received_config.append(config.require("fake", _FakeRenderInput))
        return [Artifact("fake/lib.fake", "fake\n", media_type)]

    fake = BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        preview_file_suffix="fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=artifact_renderer,
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
        project_config=BackendProjectConfigSpec(
            table_name="fake_package",
            parse=parse_config,
        ),
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})
    config_path = tmp_path / "tslc.toml"
    config_path.write_text(
        "\n".join(
            (
                "[tslc]",
                'sources = ["data"]',
                'machine_profiles = "profiles.json"',
                'backends = ["fake"]',
                "[tslc.fake_package]",
                'label = "configured"',
                "",
            )
        ),
        encoding="utf-8",
    )
    project_config = load_project_config(config_path)
    assert project_config is not None
    profile = EmittedProfile(
        MachineProfile("fake-profile", "fake", frozenset(), {}),
        {
            "fake": {
                "echo": (
                    LoweredSpecialization(
                        backend_id="fake",
                        primitive_name="echo",
                        source_primitive_name="echo",
                        extension_name="fake_ext",
                        type_tag="si32",
                        base_type_spelling="fake_i32",
                        register_spelling="source-register",
                        result_kind="v",
                        param_names=("data",),
                        param_kinds=("v",),
                        body=LoweredBody.from_text("return data;"),
                    ),
                )
            }
        },
        immediate_split_names=frozenset(),
    )

    rendered = render_project(
        (profile,),
        ("fake",),
        assets=load_default_render_assets(),
        config=project_config.render_config,
        input_digest="b" * 64,
    )
    artifacts = {
        artifact.logical_path: artifact for artifact in rendered.artifacts.artifacts
    }
    documentation = json.loads(
        artifacts["docs/specializations/specializations.json"].content
    )

    assert artifacts["fake/lib.fake"].media_type == "text/fake"
    assert received_config == [_FakeRenderInput("configured")]
    assert "fake-register" in documentation["strings"]
    assert "fake facade" in documentation["strings"]
    assert rendered.verify.input_digest == "b" * 64


def test_render_project_filters_profiles_by_backend_membership(monkeypatch) -> None:
    from tslc.backend import registry

    received: dict[str, tuple[str, ...]] = {}

    def artifact_renderer(
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
        benchmarks: object,
        assets: RenderAssets,
        media_type: str,
        config: object,
        policy_inputs: object,
        helper_plan: object,
    ) -> list[Artifact]:
        del value_tests, benchmarks, assets, media_type, config, policy_inputs
        del helper_plan
        received["render"] = tuple(profile.profile.name for profile in profiles)
        return []

    def verify_profiles(
        profiles: tuple[EmittedProfile, ...],
    ) -> tuple[VerifyProfile, ...]:
        received["verify"] = tuple(profile.profile.name for profile in profiles)
        return ()

    fake = BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        preview_file_suffix="fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=artifact_renderer,
        verify_profiles=verify_profiles,
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})
    active = EmittedProfile(
        MachineProfile("active", "fake", frozenset(), {}),
        {"fake": {}},
        immediate_split_names=frozenset(),
    )
    inactive = EmittedProfile(
        MachineProfile("inactive", "fake", frozenset(), {}),
        {},
        immediate_split_names=frozenset(),
    )

    render_project(
        (inactive, active),
        ("fake",),
        assets=load_default_render_assets(),
    )

    assert received == {"render": ("active",), "verify": ("active",)}


def test_third_backend_configuration_reaches_verify_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A backend ID remains data-driven from source validation through render."""

    from tslc.backend import registry

    source = SourceDocument(
        tmp_path / "fake.tsl",
        """target_families:
  known_extension_families [scalar]
  universal_extension_families [scalar]
  profile_families:
    fake_family:
      extension_families []
      runner_kinds []
      backends:
        fake:
          feature_flags false
          target "fake-none-elf"
          linker "fake-ld"
types:
  ints {types [si32]}
extension scalar:
  extension_name "scalar"
  family "scalar"
language fake:
  s32 {type "fake_i32"}
prim<v:=v> id(data):
  impls:
    scalar:
      ints:
        implementation:
          tsil "complete(data);"
""",
        "detail",
        "tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((source,))
    assert parsed.diagnostics == ()
    catalog_result = CatalogBuilder().build(parsed)
    assert catalog_result.catalog is not None
    assert catalog_result.diagnostics == ()
    catalog = catalog_result.catalog
    assert validate_catalog(catalog, parsed, required_backends=("fake",)) == ()

    profile_path = tmp_path / "machine_profiles.json"
    profile_path.write_text(
        '{"fake_family": [{"name": "fake-fast", '
        '"target_features": "fast", '
        '"backend_flags": {"fake": ["--fast"]}}]}\n',
        encoding="utf-8",
    )
    profiles = load_machine_profiles_checked(profile_path, catalog.target_families)
    assert profiles.diagnostics == ()
    machine_profile = profiles.profiles["fake-fast"]
    profile_family = catalog.target_families.profile_families["fake_family"]

    def verify_profiles(
        emitted: tuple[EmittedProfile, ...],
    ) -> tuple[VerifyProfile, ...]:
        return tuple(
            VerifyProfile(
                profile_name=item.profile.name,
                file_stem=item.profile.name,
                flags=item.profile.flags_for_backend("fake"),
                target=item.profile_family.backend("fake").target
                if item.profile_family is not None
                else None,
                linker=item.profile_family.backend("fake").linker
                if item.profile_family is not None
                else None,
            )
            for item in emitted
        )

    fake = BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        preview_file_suffix="fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        artifact_renderer=_empty_backend_artifacts,
        verify_profiles=verify_profiles,
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        verify_machine_profile=lambda profile, family: None,  # type: ignore[arg-type,return-value]
        toolchain_commands=lambda profile, config: None,  # type: ignore[arg-type,return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})
    emitted = EmittedProfile(
        machine_profile,
        {"fake": {}},
        profile_family=profile_family,
        immediate_split_names=frozenset(),
    )

    rendered = render_project(
        (emitted,),
        ("fake",),
        assets=load_default_render_assets(),
    )

    assert rendered.verify.backends[0].backend_id == "fake"
    assert rendered.verify.backends[0].profiles == (
        VerifyProfile(
            profile_name="fake-fast",
            file_stem="fake-fast",
            flags=("--fast",),
            target="fake-none-elf",
            linker="fake-ld",
        ),
    )


def test_rvv_is_additive_without_generic_compiler_name_branches() -> None:
    package = _REPO_ROOT / "tslc/src/tslc"
    paths = [package / "pipeline.py"]
    paths.extend(
        path
        for subtree in ("catalog", "select", "lower", "backend", "render")
        for path in sorted((package / subtree).rglob("*.py"))
    )
    offenders = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value == "rvv"
        )

    assert offenders == []


def test_lowerer_imports_region_handlers_directly() -> None:
    forbidden = ".".join(("tslc", "lower", "regions"))
    roots = (_REPO_ROOT / "tslc" / "src", _REPO_ROOT / "tslc" / "tests")
    paths = (path for root in roots for path in sorted(root.rglob("*.py")))

    assert _forbidden_imports(paths, forbidden) == []


def test_fixed_native_lowering_has_no_concrete_mask_bridge_names() -> None:
    path = _REPO_ROOT / "tslc" / "src" / "tslc" / "lower" / "fixed_native.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert {"to_integral", "to_mask"}.isdisjoint(string_literals)


def test_checked_lowering_and_rendering_have_no_concrete_helper_names() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = (
        package_root / "catalog" / "preconditions.py",
        package_root / "lower" / "implementation_bodies.py",
        package_root / "backend" / "translation.py",
        package_root / "backend" / "cpp_translation.py",
        package_root / "backend" / "checked_api.py",
        package_root / "backend" / "cpp_checked_api.py",
        package_root / "backend" / "cpp.py",
        package_root / "backend" / "rust_checked_primitives.py",
        package_root / "backend" / "rust_primitive_declarations.py",
    )
    concrete_names = {
        "equal",
        "mask_binary_and",
        "mask_false",
        "mask_population_count",
        "set_mask_lane",
        "extract_value_at",
        "set_zero",
    }
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path}:{node.lineno}: {node.value}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value in concrete_names
        )

    assert offenders == []


def test_benchmark_modules_do_not_import_backend_registration() -> None:
    benchmark_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "benchmark"

    assert _forbidden_imports(
        sorted(benchmark_root.rglob("*.py")),
        "tslc.backend.registry",
    ) == []


def test_cycle_boundary_modules_have_no_function_local_tslc_imports() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = (
        package_root / "backend" / "capability.py",
        package_root / "backend" / "rust_policy_consumption.py",
        package_root / "backend" / "rust_policy_selection.py",
        package_root / "benchmark" / "identity.py",
        package_root / "benchmark" / "planner.py",
        package_root / "value_tests" / "identity.py",
    )

    assert _function_local_imports(paths, "tslc") == []


def test_runtime_import_graph_has_no_cross_ownership_cycles() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    graph = _runtime_import_graph(package_root)
    closure = {
        module_name: _reachable_modules(graph, module_name)
        for module_name in graph
    }
    offenders: set[tuple[str, str]] = set()
    for source in sorted(graph):
        source_owner = _pipeline_owner(source)
        if source_owner is None:
            continue
        reachable = closure[source]
        for target in reachable:
            target_owner = _pipeline_owner(target)
            if (
                target_owner is not None
                and target_owner != source_owner
                and source in closure[target]
            ):
                offenders.add(tuple(sorted((source, target))))

    assert sorted(offenders) == []


def test_generic_lsp_backend_selection_has_no_concrete_backend_literals() -> None:
    lsp_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "lsp"
    paths = (
        lsp_root / "backend_selection.py",
        lsp_root / "primitive_explorer.py",
        lsp_root / "specialization_context.py",
    )
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path}:{node.lineno}: {node.value}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value in {"cpp", "rust"}
        )

    assert offenders == []


def test_pre_lowering_packages_do_not_import_lowering() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = (
        path
        for package_name in ("syntax", "catalog", "ir")
        for path in sorted((package_root / package_name).rglob("*.py"))
    )

    assert _forbidden_imports(paths, "tslc.lower") == []


def test_lowering_does_not_import_project_rendering() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "lower"

    assert _forbidden_imports(
        sorted(package_root.rglob("*.py")), "tslc.render"
    ) == []


def test_shared_configuration_and_api_do_not_import_rust_modules() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = tuple(
        package_root / name
        for name in (
            "api.py",
            "cli.py",
            "generation_command.py",
            "project_config.py",
            "project_render.py",
        )
    )

    assert _forbidden_imports(paths, "tslc.backend.rust") == []


def test_compiler_owned_packages_do_not_import_maintenance() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = [
        path
        for package_name in (
            "backend",
            "benchmark",
            "catalog",
            "ir",
            "lower",
            "lsp",
            "output",
            "render",
            "select",
            "syntax",
            "value_tests",
        )
        for path in sorted((package_root / package_name).rglob("*.py"))
    ]
    paths.extend(
        path
        for pattern in (
            "_pipeline*.py",
            "api.py",
            "authoring*.py",
            "compiler_assets.py",
            "generation_command.py",
            "pipeline*.py",
            "project*.py",
            "sources.py",
        )
        for path in sorted(package_root.glob(pattern))
    )

    assert _forbidden_imports(paths, "tslc.maintenance") == []


def test_generation_pipeline_does_not_discover_or_reopen_tsldata() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    paths = (
        package_root / "pipeline.py",
        *sorted(package_root.glob("_pipeline*.py")),
    )
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "tsldata" in node.value.lower()
        )

    assert offenders == []
    assert _forbidden_imports(paths, "tslc.maintenance._repo_context") == []


def test_backend_semantics_do_not_import_project_rendering() -> None:
    """Only registry composition adapters may point from backend to render."""

    package_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "backend"
    paths = (
        path
        for path in sorted(package_root.glob("*.py"))
        if path.name not in {"cpp_capability.py", "rust_capability.py"}
    )

    assert _forbidden_imports(paths, "tslc.render") == []


def test_render_modules_import_no_private_backend_names() -> None:
    """render/ formats backend-decided models; `_`-private backend names stay backend-internal."""

    render_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "render"
    offenders: list[str] = []
    for path in sorted(render_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    f"{path}:{node.lineno}: {alias.name}"
                    for alias in node.names
                    if _is_forbidden_import(alias.name, "tslc.backend")
                    and any(part.startswith("_") for part in alias.name.split("."))
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if not _is_forbidden_import(node.module, "tslc.backend"):
                    continue
                offenders.extend(
                    f"{path}:{node.lineno}: {alias.name}"
                    for alias in node.names
                    if alias.name.startswith("_")
                    or any(part.startswith("_") for part in node.module.split("."))
                )

    assert offenders == []


def test_renderers_do_not_own_backend_helper_admission() -> None:
    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    render_paths = sorted((package_root / "render").rglob("*.py"))

    assert _forbidden_imports(render_paths, "tslc.backend.helper_requirements") == []
    for old_module in (
        "cpp_profile_header.py",
        "rust_algorithm.py",
        "rust_facades.py",
        "rust_vectors.py",
    ):
        assert not (package_root / "render" / old_module).exists()


def test_backend_fact_modules_have_no_function_local_imports() -> None:
    backend_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "backend"
    paths = (
        backend_root / "emitted_profile.py",
        backend_root / "cpp_validation.py",
        backend_root / "rust_validation.py",
        backend_root / "capability.py",
        backend_root / "cpp_capability.py",
        backend_root / "rust_capability.py",
        _REPO_ROOT / "tslc" / "src" / "tslc" / "output" / "verify_drivers.py",
    )

    assert _function_local_imports(paths, "tslc") == []


def test_support_policy_does_not_import_backend_registration() -> None:
    path = _REPO_ROOT / "tslc" / "src" / "tslc" / "support_policy.py"

    assert _forbidden_imports((path,), "tslc.backend") == []


def test_project_renderer_does_not_finalize_or_plan_semantics() -> None:
    path = _REPO_ROOT / "tslc" / "src" / "tslc" / "render" / "project.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    referenced_names = {
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(tree)
        if isinstance(node, (ast.Name, ast.Attribute))
    }

    assert _forbidden_imports((path,), "tslc.catalog") == []
    assert _forbidden_imports((path,), "tslc.value_tests.planner") == []
    assert _forbidden_imports((path,), "tslc.backend.emitted_names") == []
    assert {
        "Catalog",
        "ValueTestPlanner",
        "finalize_emitted_names",
        "value_test_warnings",
    }.isdisjoint(referenced_names)


def test_authoring_tools_use_public_selector_and_selector_path_boundaries() -> None:
    """LSP and maintenance projections consume selection facts through the
    public Selector surface and never re-open catalog promotion internals."""

    package_root = _REPO_ROOT / "tslc" / "src" / "tslc"
    selector_private = {
        name
        for name in vars(Selector)
        if name.startswith("_") and not name.startswith("__")
    }
    private_import_sources = ("tslc.select", "tslc.catalog")
    offenders: list[str] = []
    for tree_name in ("lsp", "maintenance"):
        for path in sorted((package_root / tree_name).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr in selector_private
                ):
                    offenders.append(
                        f"{path}:{node.lineno}: accesses Selector.{node.attr}"
                    )
                elif isinstance(node, ast.Import):
                    offenders.extend(
                        f"{path}:{node.lineno}: imports {alias.name}"
                        for alias in node.names
                        if any(
                            _is_forbidden_import(alias.name, source)
                            for source in private_import_sources
                        )
                        and any(
                            part.startswith("_") for part in alias.name.split(".")
                        )
                    )
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    if not any(
                        _is_forbidden_import(node.module, source)
                        for source in private_import_sources
                    ):
                        continue
                    offenders.extend(
                        f"{path}:{node.lineno}: imports {alias.name} from {node.module}"
                        for alias in node.names
                        if alias.name.startswith("_")
                        or any(
                            part.startswith("_") for part in node.module.split(".")
                        )
                    )

    assert offenders == []


def test_primitive_explorer_does_not_walk_extension_chains_itself() -> None:
    """Slot candidate discovery belongs to the selector; the explorer must not
    re-implement it with a second `catalog.extension_chain` walk."""

    path = (
        _REPO_ROOT / "tslc" / "src" / "tslc" / "lsp" / "primitive_explorer.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    chain_walks = [
        f"{path}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "extension_chain"
    ]

    assert chain_walks == []


def test_architecture_documents_match_current_pipeline_vocabulary() -> None:
    charter = (_REPO_ROOT / "tslc" / "CHARTER.md").read_text(encoding="utf-8")
    readme = (_REPO_ROOT / "tslc" / "README.md").read_text(encoding="utf-8")
    description = (_REPO_ROOT / "tslc" / "DESCRIPTION.md").read_text(
        encoding="utf-8"
    )

    assert "LoweredFunction" not in charter + readme + description
    assert "LoweredSpecialization" in charter
    assert "ir/region_registry.py" in description
    assert "`helper`" in description
    assert "`select_expr`" in description
    assert "backend/emitted_profile.py" in description
    assert "prebuilt value-test plans" in description


def _is_forbidden_import(module_name: str, forbidden: str) -> bool:
    return module_name == forbidden or module_name.startswith(f"{forbidden}.")


def _forbidden_imports(paths: Iterable[Path], forbidden: str) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    f"{path}:{node.lineno}"
                    for alias in node.names
                    if _is_forbidden_import(alias.name, forbidden)
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if _is_forbidden_import(node.module, forbidden):
                    offenders.append(f"{path}:{node.lineno}")
    return offenders


def _function_local_imports(paths: Iterable[Path], prefix: str) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        for function in functions:
            for node in ast.walk(function):
                if isinstance(node, ast.Import):
                    offenders.extend(
                        f"{path}:{node.lineno}"
                        for alias in node.names
                        if _is_forbidden_import(alias.name, prefix)
                    )
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    if _is_forbidden_import(node.module, prefix):
                        offenders.append(f"{path}:{node.lineno}")
    return sorted(set(offenders))


def _runtime_import_graph(package_root: Path) -> dict[str, set[str]]:
    paths_by_module = {
        _python_module_name(path, package_root): path
        for path in package_root.rglob("*.py")
    }
    known_modules = frozenset(paths_by_module)
    graph: dict[str, set[str]] = {}
    for module_name, path in paths_by_module.items():
        package_name = (
            module_name
            if path.name == "__init__.py"
            else module_name.rpartition(".")[0]
        )
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        collector = _RuntimeImportCollector(package_name, known_modules)
        collector.visit(tree)
        graph[module_name] = collector.imports
    return graph


def _python_module_name(path: Path, package_root: Path) -> str:
    parts = path.relative_to(package_root.parent).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


class _RuntimeImportCollector(ast.NodeVisitor):
    def __init__(
        self,
        package_name: str,
        known_modules: frozenset[str],
    ) -> None:
        self._package_name = package_name
        self._known_modules = known_modules
        self.imports: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update(
            alias.name for alias in node.names if alias.name in self._known_modules
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = node.module or ""
        if node.level:
            package_parts = self._package_name.split(".")
            retained = len(package_parts) - node.level + 1
            prefix = ".".join(package_parts[:retained])
            base = ".".join(part for part in (prefix, base) if part)
        for alias in node.names:
            candidate = f"{base}.{alias.name}" if base else alias.name
            if candidate in self._known_modules:
                self.imports.add(candidate)
            elif base in self._known_modules:
                self.imports.add(base)


def _reachable_modules(
    graph: Mapping[str, set[str]],
    source: str,
) -> set[str]:
    reachable: set[str] = set()
    pending = list(graph[source])
    while pending:
        module_name = pending.pop()
        if module_name in reachable:
            continue
        reachable.add(module_name)
        pending.extend(graph.get(module_name, ()))
    return reachable


def _pipeline_owner(module_name: str) -> str | None:
    return next(
        (
            owner
            for owner in ("backend", "benchmark", "render", "value_tests")
            if module_name == f"tslc.{owner}"
            or module_name.startswith(f"tslc.{owner}.")
        ),
        None,
    )


def _empty_backend_artifacts(
    profiles: tuple[EmittedProfile, ...],
    value_tests: ValueTestProjectPlan,
    benchmarks: object,
    assets: RenderAssets,
    media_type: str,
    config: object,
    policy_inputs: object,
    helper_plan: object,
) -> list[Artifact]:
    del profiles, value_tests, benchmarks, assets, media_type, config, policy_inputs
    del helper_plan
    return []


class _FakeDocumentationFormatter:
    backend_id = "fake"

    def register_type(self, spec: LoweredSpecialization) -> str:
        del spec
        return "fake-register"

    def facade(self, doc) -> str:  # noqa: ANN001
        del doc
        return "fake facade"

    def expression(self, doc) -> str:  # noqa: ANN001
        del doc
        return "fake expression"
