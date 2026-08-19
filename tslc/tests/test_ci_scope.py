"""Conservative path scoping for GitHub Actions."""

from __future__ import annotations

from dataclasses import fields
import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def test_test_only_change_selects_changed_tests_and_clang_overlay() -> None:
    module = _scope_module()
    scope = module.classify_paths(
        (
            "tslc/tests/test_build_verify.py",
            "tslc/tests/test_lower_register_paths.py",
        )
    )

    assert scope.python_tests
    assert not scope.python_full
    assert not scope.python_type_check
    assert scope.changed_python_tests == (
        "tslc/tests/test_build_verify.py",
        "tslc/tests/test_lower_register_paths.py",
    )
    assert scope.clang_overlay
    assert not scope.generated_profiles
    assert not scope.benchmarks
    assert not scope.pivot
    assert not scope.coverage
    assert not scope.editor_tests
    assert not scope.editor_runtime


def test_compiler_change_selects_every_dependent_product_gate() -> None:
    scope = _scope_module().classify_paths(("tslc/src/tslc/pipeline.py",))

    assert scope.python_tests
    assert scope.python_full
    assert scope.python_type_check
    assert scope.pivot
    assert scope.coverage
    assert scope.editor_tests
    assert scope.editor_runtime
    assert scope.generated_profiles
    assert scope.clang_overlay
    assert scope.benchmarks
    assert scope.package
    assert scope.docs


def test_editor_test_change_does_not_package_every_runtime() -> None:
    scope = _scope_module().classify_paths(("tslc/tests/test_lsp_protocol.py",))

    assert scope.python_tests
    assert scope.editor_tests
    assert not scope.editor_runtime
    assert not scope.generated_profiles


def test_unknown_future_path_fails_closed_to_full_ci() -> None:
    module = _scope_module()
    scope = module.classify_paths(("new-product/source.py",))

    assert scope == module.CiScope.full()
    assert module.classify_paths(()) == module.CiScope.full()


def test_ci_workflow_change_runs_all_gates() -> None:
    module = _scope_module()
    scope = module.classify_paths((".github/workflows/python.yml",))

    assert scope == module.CiScope.full()


def test_python_test_helper_change_runs_the_full_python_suite() -> None:
    scope = _scope_module().classify_paths(
        ("tslc/tests/_select_lower_core_support.py",)
    )

    assert scope.python_tests
    assert scope.python_full
    assert not scope.generated_profiles


def test_unknown_compiler_subtree_fails_closed_to_full_ci() -> None:
    module = _scope_module()
    scope = module.classify_paths(("tslc/new_projection/source.py",))

    assert scope == module.CiScope.full()


def test_independent_products_select_only_their_owned_gates() -> None:
    module = _scope_module()
    cases = (
        ("docs/ci.md", {"docs"}),
        ("tools/pivot/src/tslc_pivot/app.py", {"pivot"}),
        (
            "editors/vscode-tsl/src/extension.ts",
            {"editor_tests", "editor_runtime"},
        ),
        ("examples/cpp/CMakeLists.txt", {"package"}),
        ("coverage/baseline.json", {"coverage"}),
    )

    for path, expected in cases:
        scope = module.classify_paths((path,))
        enabled = {
            field.name
            for field in fields(scope)
            if getattr(scope, field.name) is True
        }
        assert enabled == expected, path


def test_ci_image_reference_is_content_addressed(tmp_path: Path) -> None:
    module = _scope_module()
    for relative in module.CI_IMAGE_INPUTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative.as_posix()}\n", encoding="utf-8")

    first = module.ci_image_reference("Owner/Repo", tmp_path)
    (tmp_path / ".devcontainer/ci-image-revision").write_text("2\n", encoding="utf-8")
    second = module.ci_image_reference("Owner/Repo", tmp_path)

    assert first.startswith("ghcr.io/owner/repo-tslc-ci:env-")
    assert second.startswith("ghcr.io/owner/repo-tslc-ci:env-")
    assert first != second


def _scope_module() -> ModuleType:
    path = Path(".github/scripts/ci_scope.py")
    spec = importlib.util.spec_from_file_location("tslc_ci_scope", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
