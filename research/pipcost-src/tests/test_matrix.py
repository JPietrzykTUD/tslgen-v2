from __future__ import annotations

from pathlib import Path

from pipcost.config import ExperimentConfig
from pipcost.matrix import (
    candidate_plan_ids,
    expand_scenarios,
    reference_plan_ids,
    requested_plan_ids,
)


ROOT = Path(__file__).resolve().parents[3]


def test_scenario_expansion_is_sorted_and_deterministic() -> None:
    config = ExperimentConfig.load(
        ROOT / "research" / "pipcost-src" / "configs" / "smoke.json"
    )
    first = expand_scenarios(config)
    second = expand_scenarios(config)
    assert first == second
    assert [item.scenario_id for item in first] == sorted(
        item.scenario_id for item in first
    )
    # rows=7 makes explicit batch 7 and the full-relation endpoint identical.
    assert len(first) == 8 * 3 * 3 - 3
    assert candidate_plan_ids(config, first[0]) == tuple(
        sorted(config.studies[0].candidate_plans)
    )
    assert reference_plan_ids(config, first[0]) == tuple(
        sorted(config.studies[0].reference_plans)
    )
    assert requested_plan_ids(config, first[0]) == tuple(
        sorted(config.studies[0].requested_plans)
    )


def test_full_batch_resolves_to_at_least_one_row() -> None:
    config = ExperimentConfig.load(
        ROOT / "research" / "pipcost-src" / "configs" / "smoke.json"
    )
    scenarios = expand_scenarios(config)
    zero_row_batches = {
        item.batch_rows for item in scenarios if item.rows == 0
    }
    assert 1 in zero_row_batches
    assert all(value > 0 for value in zero_row_batches)
