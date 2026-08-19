from __future__ import annotations

from pipcost.oracle import build_oracle


def test_oracle_uses_deterministic_winners_and_reports_gate() -> None:
    scenarios = {
        "scenarios": [
            {
                "scenario_id": "low",
                "rows": 1000,
                "batch_rows": 100,
                "candidate_plans": [
                    "batch_positions_u32",
                    "batch_integral_mask",
                ],
                "reference_plans": ["fused_mask"],
            },
            {
                "scenario_id": "high",
                "rows": 1000,
                "batch_rows": 100,
                "candidate_plans": [
                    "batch_positions_u32",
                    "batch_integral_mask",
                ],
                "reference_plans": ["fused_mask"],
            },
        ]
    }
    summary = {
        "run_id": "run-1",
        "raw_samples_sha256": "raw",
        "complete": True,
        "cells": [
            {
                "scenario_id": scenario,
                "plan_id": plan,
                "median_ns": cost,
                "relative_mad": 0.001,
                "observed_combined_selectivity": selectivity,
            }
            for scenario, selectivity, values in (
                (
                    "low",
                    0.01,
                    (
                        ("batch_positions_u32", 50.0),
                        ("batch_integral_mask", 100.0),
                        ("fused_mask", 10.0),
                    ),
                ),
                (
                    "high",
                    0.8,
                    (
                        ("batch_positions_u32", 120.0),
                        ("batch_integral_mask", 60.0),
                        ("fused_mask", 10.0),
                    ),
                ),
            )
            for plan, cost in values
        ],
    }
    oracle = build_oracle(
        summary,
        scenarios,
        repetitions=9,
        materiality_threshold=0.05,
        manual_threshold=0.1,
    )
    assert oracle["gate_a"]["status"] == "pass"
    assert oracle["gate_a"]["distinct_winners"] == [
        "batch_integral_mask",
        "batch_positions_u32",
    ]
    assert oracle["fixed_policies"]["manual_threshold"]["worst_regret"] == 0.0
    # The faster fused kernel is a measured control, not a representation candidate.
    assert oracle["reference_plans"]["fused_mask"]["best_relative_gain"] > 0.0


def test_missing_cells_produce_an_inconclusive_oracle() -> None:
    scenarios = {
        "scenarios": [
            {
                "scenario_id": "missing",
                "rows": 100,
                "batch_rows": 10,
                "first_selectivity": 1.0,
                "conditional_selectivity": 0.5,
                "requested_combined_selectivity": 0.5,
                "candidate_plans": ["batch_integral_mask"],
                "reference_plans": [],
            }
        ]
    }
    summary = {
        "run_id": "run-missing",
        "raw_samples_sha256": "raw",
        "complete": False,
        "cells": [],
    }
    oracle = build_oracle(
        summary,
        scenarios,
        repetitions=9,
        materiality_threshold=0.05,
        manual_threshold=0.1,
    )
    assert oracle["gate_a"]["status"] == "inconclusive"
    assert oracle["winners"] == []
