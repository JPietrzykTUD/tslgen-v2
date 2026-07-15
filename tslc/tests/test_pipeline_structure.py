"""Pipeline facade ownership checks."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from pathlib import Path

from tslc import pipeline
from tslc.backend import cpp_profile
from tslc.backend.capability import BackendCapability
from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    CPP_HELPER_MANIFEST,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.rust_capability import RUST_BACKEND
from tslc.benchmark.model import EMPTY_BENCHMARK_PROJECT_PLAN
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.validation import validate_catalog
from tslc.compiler_assets import RenderAssets, load_default_render_assets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile
from tslc.render import cpp_build, cpp_project
from tslc.render.project import render_project
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.target_text import LoweredBody
from tslc.value_tests.model import ValueTestProjectPlan

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pipeline_facade_keeps_input_and_closure_boundaries() -> None:
    assert pipeline.generate.__module__ == "tslc.pipeline"
    assert pipeline._load_inputs.__module__ == "tslc._pipeline_inputs"
    assert pipeline._LoweringCache.__module__ == "tslc._pipeline_lowering_cache"
    assert pipeline._LoweredSlot.__module__ == "tslc._pipeline_closure"
    assert pipeline._prune_unresolved.__module__ == "tslc._pipeline_closure"
    assert pipeline._profile_with_required_features.__module__ == "tslc._pipeline_closure"


def test_cpp_project_renderer_has_focused_owned_modules() -> None:
    assert cpp_project.cpp_artifacts.__module__ == "tslc.render.cpp_project"
    assert cpp_profile._cpp_registration.__module__ == "tslc.backend.cpp_profile"
    assert cpp_build.cpp_flags.__module__ == "tslc.render.cpp_build"


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
        "rust_documentation.rs.tmpl",
        "rust_lib.rs.tmpl",
        "rust_lib_profile.rs.tmpl",
        "rust_primitive_tags.rs.tmpl",
        "rust_profile_module.rs.tmpl",
        "rust_profile_metadata.rs.tmpl",
        "rust_smoke.rs",
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


def test_backend_closure_seed_primitives_are_capability_owned() -> None:
    class FakeCatalog:
        def __init__(self, names: set[str]) -> None:
            self.names = names

        def primitives_named(self, name: str, *, unmasked: bool) -> tuple[str, ...]:
            del unmasked
            return (name,) if name in self.names else ()

    catalog = FakeCatalog({"load", "store", "to_array"})
    assert BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        project_renderer=lambda profiles, assets, media_type: [],
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        test_renderer=lambda plan, assets, media_type: [],
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
    ).closure_seed_primitives(catalog) == ()
    assert CPP_BACKEND.helper_manifest is CPP_HELPER_MANIFEST
    assert RUST_BACKEND.helper_manifest is RUST_HELPER_MANIFEST
    assert CPP_BACKEND.closure_seed_primitives(catalog) == ("load", "store")
    assert RUST_BACKEND.closure_seed_primitives(catalog) == (
        "load",
        "store",
        "to_array",
    )


def test_backend_capability_owns_optional_benchmark_planning(catalog) -> None:
    calls: list[str] = []

    def plan_benchmarks(catalog, profiles, value_tests):  # noqa: ANN001
        del catalog, profiles, value_tests
        calls.append("future")
        return EMPTY_BENCHMARK_PROJECT_PLAN

    future = BackendCapability(
        backend_id="future",
        root_path="future",
        artifact_media_type="text/future",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        project_renderer=lambda profiles, assets, media_type: [],
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        test_renderer=lambda plan, assets, media_type: [],
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
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

    assert "cpp" not in pipeline_literals
    assert "rust" not in value_planner_literals


def test_fake_backend_drives_documentation_and_artifact_media_type(monkeypatch) -> None:
    from tslc.backend import registry

    def project_renderer(
        profiles: tuple[EmittedProfile, ...],
        assets: RenderAssets,
        media_type: str,
    ) -> list[Artifact]:
        del profiles, assets
        return [Artifact("fake/lib.fake", "fake\n", media_type)]

    fake = BackendCapability(
        backend_id="fake",
        root_path="fake",
        artifact_media_type="text/fake",
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        project_renderer=project_renderer,
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        test_renderer=lambda plan, assets, media_type: [],
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
        documentation_formatter_factory=_FakeDocumentationFormatter,
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})
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
    )
    artifacts = {
        artifact.logical_path: artifact for artifact in rendered.artifacts.artifacts
    }
    documentation = json.loads(
        artifacts["docs/specializations/specializations.json"].content
    )

    assert artifacts["fake/lib.fake"].media_type == "text/fake"
    assert "fake-register" in documentation["strings"]
    assert "fake facade" in documentation["strings"]


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
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        project_renderer=lambda profiles, assets, media_type: [],
        verify_profiles=verify_profiles,
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        test_renderer=lambda plan, assets, media_type: [],
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
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


def test_lowerer_imports_region_handlers_directly() -> None:
    forbidden = ".".join(("tslc", "lower", "regions"))
    roots = (_REPO_ROOT / "tslc" / "src", _REPO_ROOT / "tslc" / "tests")
    paths = (path for root in roots for path in sorted(root.rglob("*.py")))

    assert _forbidden_imports(paths, forbidden) == []


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


def test_backend_semantics_do_not_import_project_rendering() -> None:
    """Only registry composition adapters may point from backend to render."""

    package_root = _REPO_ROOT / "tslc" / "src" / "tslc" / "backend"
    paths = (
        path
        for path in sorted(package_root.glob("*.py"))
        if path.name not in {"cpp_capability.py", "rust_capability.py"}
    )

    assert _forbidden_imports(paths, "tslc.render") == []


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
