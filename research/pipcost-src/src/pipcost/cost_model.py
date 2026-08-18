"""Transparent bounded lookup/interpolation model."""

from __future__ import annotations

from itertools import product
import math
import statistics
from typing import Any

from pipcost.domain import Prediction
from pipcost.records import digest_json

_COORDINATES = ("rows", "batch_rows", "observed_combined_selectivity")


def _bracket(values: list[float], target: float) -> tuple[float, float] | None:
    if target < values[0] or target > values[-1]:
        return None
    lower = max(value for value in values if value <= target)
    upper = min(value for value in values if value >= target)
    return lower, upper


def _weighted_corners(
    points: dict[tuple[float, float, float], float],
    target: tuple[float, float, float],
) -> tuple[float, list[dict[str, object]]] | None:
    brackets: list[tuple[float, float]] = []
    for dimension in range(3):
        values = sorted({coordinate[dimension] for coordinate in points})
        bracket = _bracket(values, target[dimension])
        if bracket is None:
            return None
        brackets.append(bracket)

    corners = sorted(set(product(*[(low, high) for low, high in brackets])))
    if any(corner not in points for corner in corners):
        return None
    weighted = 0.0
    explanation: list[dict[str, object]] = []
    for corner in corners:
        weight = 1.0
        for dimension, (low, high) in enumerate(brackets):
            if low == high:
                continue
            if corner[dimension] == low:
                weight *= (high - target[dimension]) / (high - low)
            else:
                weight *= (target[dimension] - low) / (high - low)
        corner_key = (
            float(corner[0]),
            float(corner[1]),
            float(corner[2]),
        )
        value = points[corner_key]
        weighted += weight * value
        explanation.append(
            {
                "coordinates": list(corner),
                "cost_ns": value,
                "weight": weight,
            }
        )
    return weighted, explanation


def fit_model(
    summary: dict[str, Any],
    scenarios_manifest: dict[str, Any],
) -> dict[str, object]:
    if summary.get("complete") is not True:
        raise ValueError("cost-model fitting requires a complete raw-sample inventory")
    scenarios = {
        str(item["scenario_id"]): item for item in scenarios_manifest["scenarios"]
    }
    groups: dict[
        tuple[str, int, str, str],
        dict[tuple[int, int, float], list[tuple[str, float]]],
    ] = {}
    for cell in summary["cells"]:
        scenario = scenarios[str(cell["scenario_id"])]
        if scenario["split"] != "training":
            continue
        candidates = scenario.get("candidate_plans")
        if candidates is not None and str(cell["plan_id"]) not in {
            str(item) for item in candidates
        }:
            continue
        key = (
            str(scenario["profile"]),
            int(scenario["simd_lanes"]),
            str(cell["plan_id"]),
            str(scenario["pattern"]),
        )
        coordinate = (
            int(scenario["rows"]),
            int(scenario["batch_rows"]),
            float(cell["observed_combined_selectivity"]),
        )
        groups.setdefault(key, {}).setdefault(coordinate, []).append(
            (str(cell["scenario_id"]), float(cell["median_ns"]))
        )
    if not groups:
        raise ValueError("no complete training cells are available")
    serialized_groups = [
        {
            "profile": key[0],
            "simd_lanes": key[1],
            "plan_id": key[2],
            "pattern": key[3],
            "points": [
                {
                    "scenario_ids": sorted(
                        scenario_id for scenario_id, _ in samples
                    ),
                    "rows": coordinate[0],
                    "batch_rows": coordinate[1],
                    "observed_combined_selectivity": coordinate[2],
                    "cost_ns": statistics.median(
                        cost for _, cost in samples
                    ),
                }
                for coordinate, samples in sorted(points.items())
            ],
        }
        for key, points in sorted(groups.items())
    ]
    model: dict[str, object] = {
        "schema_version": 1,
        "kind": "bounded_multilinear_lookup",
        "run_id": summary["run_id"],
        "raw_samples_sha256": summary["raw_samples_sha256"],
        "coordinates": list(_COORDINATES),
        "groups": serialized_groups,
    }
    model["model_id"] = f"model-{digest_json(model)[:16]}"
    return model


def predict(
    model: dict[str, Any],
    *,
    profile: str,
    simd_lanes: int,
    plan_id: str,
    pattern: str,
    rows: int,
    batch_rows: int,
    observed_combined_selectivity: float,
) -> Prediction | None:
    group = next(
        (
            item
            for item in model["groups"]
            if item["profile"] == profile
            and int(item["simd_lanes"]) == simd_lanes
            and item["plan_id"] == plan_id
            and item["pattern"] == pattern
        ),
        None,
    )
    if group is None:
        return None
    points = {
        (
            float(item["rows"]),
            float(item["batch_rows"]),
            float(item["observed_combined_selectivity"]),
        ): float(item["cost_ns"])
        for item in group["points"]
    }
    target = (
        float(rows),
        float(batch_rows),
        float(observed_combined_selectivity),
    )
    result = _weighted_corners(points, target)
    if result is None:
        return None
    value, corners = result
    if not math.isfinite(value):
        return None
    return Prediction(
        plan_id=plan_id,
        predicted_ns=value,
        explanation={
            "kind": "exact" if len(corners) == 1 else "bounded_interpolation",
            "target": list(target),
            "corners": corners,
        },
    )
