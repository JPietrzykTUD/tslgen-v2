from __future__ import annotations

import pytest

from pipcost.cost_model import fit_model, predict
from pipcost.evaluate import evaluate_model


def _fixtures() -> tuple[dict, dict, dict]:
    scenarios = {
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "split": split,
                "profile": "avx2",
                "simd_lanes": 8,
                "pattern": "random",
                "rows": 100,
                "batch_rows": 10,
                "candidate_plans": ["positions", "mask"],
                "reference_plans": ["fused"],
            }
            for scenario_id, split in (
                ("train-low", "training"),
                ("train-high", "training"),
                ("held", "held_out"),
            )
        ]
    }
    cells = []
    for scenario_id, selectivity, costs in (
        ("train-low", 0.1, {"positions": 10.0, "mask": 30.0}),
        ("train-high", 0.5, {"positions": 50.0, "mask": 20.0}),
        ("held", 0.3, {"positions": 31.0, "mask": 24.0}),
    ):
        costs["fused"] = 5.0
        for plan_id, cost in costs.items():
            cells.append(
                {
                    "scenario_id": scenario_id,
                    "plan_id": plan_id,
                    "median_ns": cost,
                    "observed_combined_selectivity": selectivity,
                }
            )
    summary = {
        "run_id": "run-1",
        "raw_samples_sha256": "raw",
        "complete": True,
        "cells": cells,
    }
    oracle = {
        "winners": [
            {
                "scenario_id": "held",
                "plan_id": "mask",
                "median_ns": 24.0,
                "tied_plan_ids": ["mask"],
            }
        ],
        "fixed_policies": {},
    }
    return scenarios, summary, oracle


def test_model_uses_training_only_and_explains_interpolation() -> None:
    scenarios, summary, _ = _fixtures()
    model = fit_model(summary, scenarios)
    assert all(
        "held" not in point["scenario_ids"]
        for group in model["groups"]
        for point in group["points"]
    )
    assert all(group["plan_id"] != "fused" for group in model["groups"])
    prediction = predict(
        model,
        profile="avx2",
        simd_lanes=8,
        plan_id="mask",
        pattern="random",
        rows=100,
        batch_rows=10,
        observed_combined_selectivity=0.3,
    )
    assert prediction is not None
    assert prediction.predicted_ns == 25.0
    assert prediction.explanation["kind"] == "bounded_interpolation"


def test_model_refuses_extrapolation() -> None:
    scenarios, summary, _ = _fixtures()
    model = fit_model(summary, scenarios)
    assert (
        predict(
            model,
            profile="avx2",
            simd_lanes=8,
            plan_id="mask",
            pattern="random",
            rows=100,
            batch_rows=10,
            observed_combined_selectivity=0.9,
        )
        is None
    )


def test_held_out_evaluation_selects_lowest_predicted_plan() -> None:
    scenarios, summary, oracle = _fixtures()
    model = fit_model(summary, scenarios)
    evaluation = evaluate_model(
        model,
        summary,
        oracle,
        scenarios,
        materiality_threshold=0.05,
    )
    assert evaluation["complete_decisions"] == 1
    assert evaluation["top1_accuracy"] == 1.0
    assert evaluation["median_regret"] == 0.0


def test_model_fitting_refuses_an_incomplete_inventory() -> None:
    scenarios, summary, _ = _fixtures()
    summary["complete"] = False
    with pytest.raises(ValueError, match="complete raw-sample inventory"):
        fit_model(summary, scenarios)


def test_evaluation_rejects_a_model_from_different_raw_samples() -> None:
    scenarios, summary, oracle = _fixtures()
    model = fit_model(summary, scenarios)
    model["raw_samples_sha256"] = "different"
    with pytest.raises(ValueError, match="different raw samples"):
        evaluate_model(
            model,
            summary,
            oracle,
            scenarios,
            materiality_threshold=0.05,
        )


def test_repeated_seed_coordinates_are_aggregated_not_overwritten() -> None:
    scenarios, summary, _ = _fixtures()
    scenarios["scenarios"].append(
        {
            "scenario_id": "train-low-second-seed",
            "split": "training",
            "profile": "avx2",
            "simd_lanes": 8,
            "pattern": "random",
            "rows": 100,
            "batch_rows": 10,
            "candidate_plans": ["positions", "mask"],
            "reference_plans": ["fused"],
        }
    )
    summary["cells"].append(
        {
            "scenario_id": "train-low-second-seed",
            "plan_id": "mask",
            "median_ns": 50.0,
            "observed_combined_selectivity": 0.1,
        }
    )
    model = fit_model(summary, scenarios)
    mask_group = next(
        group for group in model["groups"] if group["plan_id"] == "mask"
    )
    low_point = next(
        point
        for point in mask_group["points"]
        if point["observed_combined_selectivity"] == 0.1
    )
    assert low_point["scenario_ids"] == [
        "train-low",
        "train-low-second-seed",
    ]
    assert low_point["cost_ns"] == 40.0
