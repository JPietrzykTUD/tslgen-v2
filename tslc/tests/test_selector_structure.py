"""Architecture guards for selector planning and candidate evaluation."""

from __future__ import annotations

import ast
from pathlib import Path


_SELECT_ROOT = Path(__file__).parents[1] / "src" / "tslc" / "select"


def test_selector_delegates_candidate_evaluation_and_ranking() -> None:
    selector_source = (_SELECT_ROOT / "selector.py").read_text(encoding="utf-8")
    selector_tree = ast.parse(selector_source)
    selector_class = next(
        node
        for node in selector_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Selector"
    )
    selector_methods = {
        node.name
        for node in selector_class.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_best_bodies" not in selector_methods
    assert "_fixed_width_fallback" not in selector_methods

    candidates_source = (_SELECT_ROOT / "candidates.py").read_text(
        encoding="utf-8"
    )
    candidates_tree = ast.parse(candidates_source)
    candidate_functions = {
        node.name
        for node in candidates_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "best_bodies",
        "evaluate_candidates",
        "fixed_width_fallback",
    } <= candidate_functions
    assert "from tslc.select.selector import" not in candidates_source


def test_selector_delegates_deterministic_slot_planning() -> None:
    selector_source = (_SELECT_ROOT / "selector.py").read_text(encoding="utf-8")
    selector_tree = ast.parse(selector_source)
    selector_class = next(
        node
        for node in selector_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Selector"
    )
    selector_methods = {
        node.name
        for node in selector_class.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_selection_slots" not in selector_methods
    assert "_monomorphized_lanes" not in selector_methods

    slots_source = (_SELECT_ROOT / "slots.py").read_text(encoding="utf-8")
    slots_tree = ast.parse(slots_source)
    slot_functions = {
        node.name
        for node in slots_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "monomorphized_lanes",
        "selection_slots",
        "simd_type_base_binding_sets",
    } <= slot_functions
    assert "from tslc.select.selector import" not in slots_source
    assert "SelectedImplementation" not in slots_source
