"""Candidate-only oracle, fixed-plan regret, references, and Gate A."""

from __future__ import annotations

import math
import statistics
from typing import Any


def _as_float(value: object) -> float:
    if isinstance(value, (str, int, float)):
        return float(value)
    raise ValueError(f"expected a numeric value, got {value!r}")


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.inf
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def _candidate_ids(
    scenario: dict[str, Any],
    available: set[str],
) -> set[str]:
    configured = scenario.get("candidate_plans", scenario.get("requested_plans"))
    return available if configured is None else {str(item) for item in configured}


def _reference_ids(scenario: dict[str, Any]) -> set[str]:
    return {str(item) for item in scenario.get("reference_plans", [])}


def _family_plan(
    family: str,
    scenario: dict[str, Any],
    available: set[str],
) -> str | None:
    relation_wide = int(scenario["batch_rows"]) >= max(int(scenario["rows"]), 1)
    prefix = "full" if relation_wide else "batch"
    candidates = {
        "integral": (f"{prefix}_integral_mask", "batch_integral_mask"),
        "positions": (f"{prefix}_positions_u32", "batch_positions_u32"),
    }[family]
    return next((plan for plan in candidates if plan in available), None)


def _regret_report(
    choices: dict[str, str | None],
    winners: dict[str, dict[str, object]],
    costs: dict[tuple[str, str], float],
) -> dict[str, object]:
    regrets: list[float] = []
    unsupported: list[str] = []
    for scenario_id in sorted(winners):
        plan_id = choices.get(scenario_id)
        if plan_id is None or (scenario_id, plan_id) not in costs:
            unsupported.append(scenario_id)
            continue
        best = _as_float(winners[scenario_id]["median_ns"])
        chosen = costs[(scenario_id, plan_id)]
        regrets.append(0.0 if best == 0 else chosen / best - 1.0)
    return {
        "complete": not unsupported,
        "unsupported_scenarios": unsupported,
        "median_regret": statistics.median(regrets) if regrets else math.inf,
        "p95_regret": _percentile(regrets, 0.95),
        "worst_regret": max(regrets) if regrets else math.inf,
        "best_relative_gain": -min(regrets) if regrets and min(regrets) < 0 else 0.0,
    }


def build_oracle(
    summary: dict[str, Any],
    scenarios_manifest: dict[str, Any],
    *,
    repetitions: int,
    materiality_threshold: float,
    manual_threshold: float,
    tie_tolerance: float = 0.005,
) -> dict[str, object]:
    scenarios = {
        str(item["scenario_id"]): item for item in scenarios_manifest["scenarios"]
    }
    all_cells: dict[str, list[dict[str, Any]]] = {}
    costs: dict[tuple[str, str], float] = {}
    for cell in summary["cells"]:
        scenario_id = str(cell["scenario_id"])
        all_cells.setdefault(scenario_id, []).append(cell)
        costs[(scenario_id, str(cell["plan_id"]))] = float(cell["median_ns"])

    candidate_cells: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, scenario in scenarios.items():
        cells = all_cells.get(scenario_id, [])
        available = {str(cell["plan_id"]) for cell in cells}
        candidates = _candidate_ids(scenario, available)
        candidate_cells[scenario_id] = [
            cell for cell in cells if str(cell["plan_id"]) in candidates
        ]

    winners: dict[str, dict[str, object]] = {}
    stable = True
    for scenario_id, cells in sorted(candidate_cells.items()):
        if not cells:
            continue
        ordered = sorted(
            cells,
            key=lambda item: (float(item["median_ns"]), str(item["plan_id"])),
        )
        best_cost = float(ordered[0]["median_ns"])
        tied = [
            item
            for item in ordered
            if float(item["median_ns"]) <= best_cost * (1.0 + tie_tolerance)
        ]
        winner = min(tied, key=lambda item: str(item["plan_id"]))
        second = next(
            (item for item in ordered if item["plan_id"] != winner["plan_id"]),
            None,
        )
        margin = (
            math.inf
            if second is None or best_cost == 0
            else float(second["median_ns"]) / best_cost - 1.0
        )
        noise = float(winner["relative_mad"])
        if second is not None:
            noise = max(noise, float(second["relative_mad"]))
        stable = stable and (second is None or margin > 2.0 * noise)
        winners[scenario_id] = {
            "scenario_id": scenario_id,
            "plan_id": winner["plan_id"],
            "median_ns": winner["median_ns"],
            "tied_plan_ids": sorted(str(item["plan_id"]) for item in tied),
            "second_place_margin": margin,
            "noise_floor": noise,
        }

    candidate_union = sorted({
        plan_id
        for scenario_id, scenario in scenarios.items()
        for plan_id in _candidate_ids(
            scenario,
            {str(cell["plan_id"]) for cell in all_cells.get(scenario_id, [])},
        )
    })
    fixed_choices = {
        f"always_{plan_id}": {
            scenario_id: (
                plan_id
                if plan_id in _candidate_ids(
                    scenario,
                    {str(cell["plan_id"]) for cell in all_cells.get(scenario_id, [])},
                )
                else None
            )
            for scenario_id, scenario in sorted(scenarios.items())
        }
        for plan_id in candidate_union
    }
    policies = {
        name: _regret_report(choices, winners, costs)
        for name, choices in sorted(fixed_choices.items())
    }

    threshold_choices: dict[str, str | None] = {}
    for scenario_id, scenario in sorted(scenarios.items()):
        cells = candidate_cells.get(scenario_id, [])
        available = {str(cell["plan_id"]) for cell in cells}
        if cells:
            combined = _as_float(cells[0]["observed_combined_selectivity"])
        else:
            combined = _as_float(
                scenario.get(
                    "requested_combined_selectivity",
                    _as_float(scenario.get("first_selectivity", 0.0))
                    * _as_float(scenario.get("conditional_selectivity", 0.0)),
                )
            )
        family = "positions" if combined < manual_threshold else "integral"
        threshold_choices[scenario_id] = _family_plan(family, scenario, available)
    policies["manual_threshold"] = _regret_report(
        threshold_choices, winners, costs
    )

    reference_union = sorted({
        plan_id for scenario in scenarios.values() for plan_id in _reference_ids(scenario)
    })
    references = {
        plan_id: {
            "role": "measured_reference_not_optimizer_candidate",
            "relative_to": "candidate_oracle",
            **_regret_report(
                {
                    scenario_id: (
                        plan_id if plan_id in _reference_ids(scenario) else None
                    )
                    for scenario_id, scenario in sorted(scenarios.items())
                },
                winners,
                costs,
            ),
        }
        for plan_id in reference_union
    }

    finite_fixed = [
        _as_float(report["worst_regret"])
        for name, report in policies.items()
        if name.startswith("always_")
        and report["complete"]
        and math.isfinite(_as_float(report["worst_regret"]))
    ]
    best_fixed_worst = min(finite_fixed) if finite_fixed else math.inf
    distinct_winners = sorted({str(item["plan_id"]) for item in winners.values()})
    reliable = (
        bool(summary["complete"])
        and repetitions >= 5
        and len(winners) == len(scenarios)
        and stable
    )
    plan_space = (
        len(distinct_winners) >= 2
        and best_fixed_worst >= materiality_threshold
    )
    if reliable and plan_space:
        gate_status = "pass"
        reason = "multiple stable candidate winners make the best fixed candidate materially suboptimal"
    elif reliable:
        gate_status = "fail"
        reason = "no material, stable candidate plan-selection problem was observed"
    else:
        gate_status = "inconclusive"
        reason = (
            "Gate A requires complete candidate cells, at least five paired "
            "repetitions, and rankings separated from observed noise"
        )

    return {
        "schema_version": 2,
        "run_id": summary["run_id"],
        "raw_samples_sha256": summary["raw_samples_sha256"],
        "tie_tolerance": tie_tolerance,
        "materiality_threshold": materiality_threshold,
        "candidate_plan_ids": candidate_union,
        "winners": [winners[key] for key in sorted(winners)],
        "fixed_policies": policies,
        "reference_plans": references,
        "gate_a": {
            "status": gate_status,
            "reason": reason,
            "reliable": reliable,
            "stable_rankings": stable,
            "distinct_winners": distinct_winners,
            "best_fixed_worst_regret": best_fixed_worst,
        },
    }
