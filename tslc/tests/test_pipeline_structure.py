"""Pipeline facade ownership checks."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tslc import pipeline
from tslc.backend.capability import BackendCapability
from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.rust_capability import RUST_BACKEND

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
        dialect_factory=lambda catalog: None,  # type: ignore[arg-type,return-value]
        project_artifacts=lambda profiles, assets: [],
        verify_profiles=lambda profiles: (),
        value_test_support_factory=lambda: None,  # type: ignore[return-value]
        test_artifacts=lambda plan, assets: [],
        verify_driver_factory=lambda: None,  # type: ignore[return-value]
    ).closure_seed_primitives(catalog) == ()
    assert CPP_BACKEND.closure_seed_primitives(catalog) == ("load", "store")
    assert RUST_BACKEND.closure_seed_primitives(catalog) == (
        "load",
        "store",
        "to_array",
    )

    source = inspect.getsource(pipeline)
    assert "_CPP_ALGORITHM_SUPPORT_PRIMITIVES" not in source
    assert "_RUST_ALGORITHM_SUPPORT_PRIMITIVES" not in source


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
