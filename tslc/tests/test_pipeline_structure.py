"""Pipeline facade ownership checks."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from pathlib import Path

from tslc import pipeline
from tslc.backend.capability import BackendCapability
from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    CPP_HELPER_MANIFEST,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.rust_capability import RUST_BACKEND
from tslc.catalog.machine_profiles import MachineProfile
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.render import cpp_build, cpp_profile_header, cpp_project
from tslc.render.project import render_project
from tslc.target_text import LoweredBody

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pipeline_facade_keeps_input_and_closure_boundaries() -> None:
    assert pipeline.generate.__module__ == "tslc.pipeline"
    assert pipeline._load_inputs.__module__ == "tslc._pipeline_inputs"
    assert pipeline._LoweredSlot.__module__ == "tslc._pipeline_closure"
    assert pipeline._prune_unresolved.__module__ == "tslc._pipeline_closure"
    assert (
        pipeline._propagate_transitive_call_facts.__module__
        == "tslc._pipeline_closure"
    )
    assert pipeline._profile_with_required_features.__module__ == "tslc._pipeline_closure"


def test_cpp_project_renderer_has_focused_owned_modules() -> None:
    assert cpp_project.cpp_artifacts.__module__ == "tslc.render.cpp_project"
    assert cpp_profile_header._cpp_registration.__module__ == (
        "tslc.render.cpp_profile_header"
    )
    assert cpp_build.cpp_flags.__module__ == "tslc.render.cpp_build"


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

    rendered = render_project((profile,), ("fake",), assets=RenderAssets({}))
    artifacts = {
        artifact.logical_path: artifact for artifact in rendered.artifacts.artifacts
    }
    documentation = json.loads(
        artifacts["docs/specializations/specializations.json"].content
    )

    assert artifacts["fake/lib.fake"].media_type == "text/fake"
    assert "fake-register" in documentation["strings"]
    assert "fake facade" in documentation["strings"]


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
