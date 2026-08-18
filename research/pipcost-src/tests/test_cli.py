from __future__ import annotations

from pathlib import Path

from pipcost.cli import main
from pipcost.runner import deterministic_plan_order
from pipcost.workspace import WorkspacePaths
from tslc.backend.registry import registered_backend_ids


def test_import_does_not_mutate_compiler_backend_registry() -> None:
    before = registered_backend_ids()
    __import__("pipcost")
    assert registered_backend_ids() == before


def test_scratch_root_must_remain_in_owned_tree(tmp_path: Path) -> None:
    forbidden = WorkspacePaths.create().prototype_root / "not-scratch"
    assert main(["generate", "--scratch-root", str(forbidden)]) == 2
    assert not forbidden.exists()


def test_default_scratch_root_is_repository_owned() -> None:
    paths = WorkspacePaths.create()
    assert paths.scratch_root == paths.root / "tslctmp" / "pipcost"
    assert paths.output_path("runs", "one").is_relative_to(paths.scratch_root)


def test_paired_plan_order_is_deterministic_and_varies_by_block() -> None:
    plans = ("a", "b", "c", "d", "e")
    first = deterministic_plan_order(
        plans, run_seed=7, scenario_id="scenario", paired_block=0
    )
    assert first == deterministic_plan_order(
        plans, run_seed=7, scenario_id="scenario", paired_block=0
    )
    assert first != deterministic_plan_order(
        plans, run_seed=7, scenario_id="scenario", paired_block=1
    )
    assert sorted(first) == sorted(plans)
