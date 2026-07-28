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
