"""Pipeline facade ownership checks."""

from __future__ import annotations

import ast
from pathlib import Path

from tslc import pipeline

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


def test_lowerer_imports_region_handlers_directly() -> None:
    forbidden = ".".join(("tslc", "lower", "regions"))
    offenders: list[str] = []

    for root in (_REPO_ROOT / "tslc" / "src", _REPO_ROOT / "tslc" / "tests"):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _is_forbidden_import(alias.name, forbidden):
                            offenders.append(f"{path}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    if _is_forbidden_import(node.module, forbidden):
                        offenders.append(f"{path}:{node.lineno}")

    assert offenders == []


def _is_forbidden_import(module_name: str, forbidden: str) -> bool:
    return module_name == forbidden or module_name.startswith(f"{forbidden}.")
