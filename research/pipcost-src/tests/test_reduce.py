from __future__ import annotations

from pathlib import Path

import pytest

from pipcost.records import write_json, write_jsonl
from pipcost.reduce import reduce_run


def _raw_run(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    write_json(run / "run.json", {"run_id": "run-1", "repetitions": 3})
    write_json(
        run / "scenarios.json",
        {
            "scenarios": [
                {"scenario_id": "s1", "requested_plans": ["a", "b"]}
            ]
        },
    )
    samples = []
    for block in range(3):
        for plan, elapsed in (("a", 100 + block), ("b", 120 + block)):
            samples.append(
                {
                    "scenario_id": "s1",
                    "plan_id": plan,
                    "paired_block": block,
                    "status": "ok",
                    "elapsed_ns": elapsed * 2,
                    "inner_iterations": 2,
                    "observed_combined_selectivity": 0.5,
                    "data_digest": "same-data",
                    "sum": 41,
                }
            )
    write_jsonl(run / "samples.jsonl", samples)
    write_json(run / "COMPLETE", {"run_id": "run-1"})
    return run


def test_reduction_checks_inventory_and_calculates_robust_statistics(
    tmp_path: Path,
) -> None:
    summary = reduce_run(_raw_run(tmp_path))
    assert summary["complete"] is True
    assert summary["expected_samples"] == 6
    assert [cell["median_ns"] for cell in summary["cells"]] == [101.0, 121.0]
    assert [cell["mad_ns"] for cell in summary["cells"]] == [1.0, 1.0]


def test_incomplete_run_is_rejected(tmp_path: Path) -> None:
    run = _raw_run(tmp_path)
    (run / "COMPLETE").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        reduce_run(run)


def test_duplicate_samples_are_visible(tmp_path: Path) -> None:
    run = _raw_run(tmp_path)
    lines = (run / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    (run / "samples.jsonl").write_text(
        "\n".join([*lines, lines[0]]) + "\n", encoding="utf-8"
    )
    summary = reduce_run(run)
    assert summary["complete"] is False
    assert summary["duplicates"]
