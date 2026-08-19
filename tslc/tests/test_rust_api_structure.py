"""Architecture guards for the focused Rust facade planner modules."""

from __future__ import annotations

import ast
from pathlib import Path


_BACKEND_ROOT = (
    Path(__file__).parents[1] / "src" / "tslc" / "backend"
)
_CHILD_MODULES = (
    "rust_api_candidates.py",
    "rust_api_comprehensive.py",
    "rust_api_curated.py",
    "rust_api_surface.py",
)


def test_rust_facade_child_planners_do_not_import_the_orchestrator() -> None:
    for name in _CHILD_MODULES:
        source = (_BACKEND_ROOT / name).read_text(encoding="utf-8")
        assert "rust_api_planner" not in source


def test_rust_facade_plan_validation_is_a_focused_module() -> None:
    model_source = (_BACKEND_ROOT / "rust_api_model.py").read_text(
        encoding="utf-8"
    )
    model_tree = ast.parse(model_source)
    plan_class = next(
        node
        for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RustFacadePlan"
    )
    post_init = next(
        node
        for node in plan_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__post_init__"
    )
    assert any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "validate_rust_facade_plan"
        for node in post_init.body
    )

    validation_tree = ast.parse(
        (_BACKEND_ROOT / "rust_api_model_validation.py").read_text(
            encoding="utf-8"
        )
    )
    runtime_imports = {
        node.module
        for node in validation_tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert "tslc.backend.rust_api_model" not in runtime_imports
    assert "tslc.backend.rust_api_arms" not in runtime_imports

    planner_source = (_BACKEND_ROOT / "rust_api_planner.py").read_text(
        encoding="utf-8"
    )
    assert "rust_api_model_validation" not in planner_source

    definitions = {
        node.name
        for node in validation_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "validate_rust_facade_plan",
        "_validate_comprehensive_methods",
        "_validate_curated_methods",
        "_validate_bit_conversions",
        "_validate_trait_implementations",
    } <= definitions


def test_rust_facade_orchestrator_contains_only_public_api_and_pipeline() -> None:
    source = (_BACKEND_ROOT / "rust_api_planner.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }

    assert definitions == {
        "RustFacadePlanningError",
        "plan_rust_facade",
        "validate_rust_facade",
        "validate_rust_facade_plan",
        "rust_facade_closure_seed_primitives",
        "_plan_rust_facade",
    }
    for module in _CHILD_MODULES:
        assert module.removesuffix(".py") in source
