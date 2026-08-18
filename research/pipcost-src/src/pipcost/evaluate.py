"""Held-out evaluation over optimizer candidates, not reference plans."""

from __future__ import annotations

import math
import statistics
from typing import Any

from pipcost.cost_model import predict
from pipcost.records import digest_json


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.inf
    return ordered[max(0, math.ceil(len(ordered) * percentile) - 1)]


def _as_float(value: object) -> float:
    if isinstance(value, (str, int, float)):
        return float(value)
    raise ValueError(f"expected a numeric value, got {value!r}")


def _regret(chosen: float, oracle: float) -> float:
    return 0.0 if oracle == 0 else chosen / oracle - 1.0


def _baseline_report(
    regrets: list[float],
    unsupported: list[str],
    held_out_count: int,
) -> dict[str, object]:
    complete = len(regrets) == held_out_count and not unsupported and held_out_count > 0
    return {
        "complete": complete,
        "unsupported_scenarios": sorted(unsupported),
        "median_regret": statistics.median(regrets) if regrets else math.inf,
        "p95_regret": _percentile(regrets, 0.95),
        "worst_regret": max(regrets) if regrets else math.inf,
    }


def _candidate_ids(
    scenario: dict[str, Any],
    measured: set[str],
) -> set[str]:
    configured = scenario.get("candidate_plans", scenario.get("requested_plans"))
    return measured if configured is None else {str(item) for item in configured}


def _manual_plan(
    scenario: dict[str, Any],
    candidates: set[str],
    observed: float,
    threshold: float,
) -> str | None:
    relation_wide = int(scenario["batch_rows"]) >= max(int(scenario["rows"]), 1)
    prefix = "full" if relation_wide else "batch"
    if observed < threshold:
        choices = (f"{prefix}_positions_u32", "batch_positions_u32")
    else:
        choices = (f"{prefix}_integral_mask", "batch_integral_mask")
    return next((plan for plan in choices if plan in candidates), None)


def evaluate_model(
    model: dict[str, Any],
    summary: dict[str, Any],
    oracle: dict[str, Any],
    scenarios_manifest: dict[str, Any],
    *,
    materiality_threshold: float,
    manual_threshold: float = 0.1,
) -> dict[str, object]:
    if model.get("run_id") != summary.get("run_id"):
        raise ValueError("model and held-out summary name different runs")
    if model.get("raw_samples_sha256") != summary.get("raw_samples_sha256"):
        raise ValueError("model and held-out summary name different raw samples")

    scenarios = {
        str(item["scenario_id"]): item for item in scenarios_manifest["scenarios"]
    }
    cells: dict[str, list[dict[str, Any]]] = {}
    for cell in summary["cells"]:
        cells.setdefault(str(cell["scenario_id"]), []).append(cell)
    winners = {
        str(item["scenario_id"]): item for item in oracle["winners"]
    }
    held_out = {
        scenario_id: scenario
        for scenario_id, scenario in scenarios.items()
        if scenario["split"] == "held_out"
    }
    candidate_union = sorted({
        plan_id
        for scenario_id, scenario in held_out.items()
        for plan_id in _candidate_ids(
            scenario,
            {str(item["plan_id"]) for item in cells.get(scenario_id, [])},
        )
    })
    baseline_regrets: dict[str, list[float]] = {
        **{f"always_{plan_id}": [] for plan_id in candidate_union},
        "manual_threshold": [],
    }
    baseline_unsupported: dict[str, list[str]] = {
        name: [] for name in baseline_regrets
    }

    decisions: list[dict[str, object]] = []
    regrets: list[float] = []
    correct = 0
    for scenario_id, scenario in sorted(held_out.items()):
        scenario_cells = cells.get(scenario_id, [])
        observed = (
            float(scenario_cells[0]["observed_combined_selectivity"])
            if scenario_cells
            else float(scenario["first_selectivity"])
            * float(scenario["conditional_selectivity"])
        )
        measured = {
            str(item["plan_id"]): float(item["median_ns"])
            for item in scenario_cells
        }
        candidates = _candidate_ids(scenario, set(measured))
        candidate_measured = {
            plan_id: value
            for plan_id, value in measured.items()
            if plan_id in candidates
        }
        winner = winners.get(scenario_id)
        if winner is not None:
            oracle_cost = float(winner["median_ns"])
            for plan_id in candidate_union:
                policy = f"always_{plan_id}"
                if plan_id not in candidate_measured:
                    baseline_unsupported[policy].append(scenario_id)
                else:
                    baseline_regrets[policy].append(
                        _regret(candidate_measured[plan_id], oracle_cost)
                    )
            manual = _manual_plan(
                scenario, set(candidate_measured), observed, manual_threshold
            )
            if manual is None:
                baseline_unsupported["manual_threshold"].append(scenario_id)
            else:
                baseline_regrets["manual_threshold"].append(
                    _regret(candidate_measured[manual], oracle_cost)
                )
        else:
            for policy in baseline_unsupported:
                baseline_unsupported[policy].append(scenario_id)

        predictions = [
            prediction
            for cell in scenario_cells
            if str(cell["plan_id"]) in candidates
            and (
                prediction := predict(
                    model,
                    profile=str(scenario["profile"]),
                    simd_lanes=int(scenario["simd_lanes"]),
                    plan_id=str(cell["plan_id"]),
                    pattern=str(scenario["pattern"]),
                    rows=int(scenario["rows"]),
                    batch_rows=int(scenario["batch_rows"]),
                    observed_combined_selectivity=observed,
                )
            )
            is not None
        ]
        if not predictions or winner is None:
            decisions.append({
                "scenario_id": scenario_id,
                "status": "unsupported",
                "reason": "no bounded candidate prediction or measured candidate oracle",
            })
            continue
        selected = min(predictions, key=lambda item: (item.predicted_ns, item.plan_id))
        if selected.plan_id not in candidate_measured:
            decisions.append({
                "scenario_id": scenario_id,
                "status": "unsupported",
                "reason": "selected candidate has no held-out measurement",
            })
            continue
        oracle_cost = float(winner["median_ns"])
        regret = _regret(candidate_measured[selected.plan_id], oracle_cost)
        regrets.append(regret)
        is_correct = selected.plan_id in winner["tied_plan_ids"]
        correct += int(is_correct)
        decisions.append({
            "scenario_id": scenario_id,
            "status": "ok",
            "selected_plan_id": selected.plan_id,
            "oracle_plan_id": winner["plan_id"],
            "oracle_tied_plan_ids": winner["tied_plan_ids"],
            "correct": is_correct,
            "measured_selected_ns": candidate_measured[selected.plan_id],
            "oracle_ns": oracle_cost,
            "regret": regret,
            "prediction": {
                "predicted_ns": selected.predicted_ns,
                "explanation": selected.explanation,
            },
        })

    held_out_count = len(held_out)
    baselines = {
        policy: _baseline_report(
            baseline_regrets[policy],
            baseline_unsupported[policy],
            held_out_count,
        )
        for policy in sorted(baseline_regrets)
    }
    complete_baselines = [
        (name, report)
        for name, report in baselines.items()
        if report["complete"]
        and math.isfinite(_as_float(report["median_regret"]))
    ]
    best_baseline = min(
        complete_baselines,
        key=lambda item: (_as_float(item[1]["median_regret"]), item[0]),
        default=None,
    )
    best_baseline_name = None if best_baseline is None else best_baseline[0]
    best_baseline_median = (
        math.inf
        if best_baseline is None
        else _as_float(best_baseline[1]["median_regret"])
    )
    complete = len(regrets) == held_out_count and held_out_count > 0
    median_regret = statistics.median(regrets) if regrets else math.inf
    improves = (
        best_baseline is not None
        and best_baseline_median - median_regret >= materiality_threshold
    )
    if not complete or best_baseline is None:
        gate_status = "inconclusive"
        gate_reason = "held-out candidate decisions or baselines are incomplete"
    elif improves:
        gate_status = "pass"
        gate_reason = "model materially improves over the best held-out candidate baseline"
    else:
        gate_status = "fail"
        gate_reason = "model does not materially improve over the best held-out candidate baseline"

    result: dict[str, object] = {
        "schema_version": 2,
        "model_id": model["model_id"],
        "run_id": summary["run_id"],
        "raw_samples_sha256": summary["raw_samples_sha256"],
        "held_out_scenarios": held_out_count,
        "complete_decisions": len(regrets),
        "top1_accuracy": (correct / held_out_count) if held_out_count else 0.0,
        "median_regret": median_regret,
        "p95_regret": _percentile(regrets, 0.95),
        "worst_regret": max(regrets) if regrets else math.inf,
        "held_out_baselines": baselines,
        "best_baseline": best_baseline_name,
        "best_baseline_median_regret": best_baseline_median,
        "decisions": decisions,
        "gate_b": {"status": gate_status, "reason": gate_reason},
    }
    result["evaluation_id"] = f"evaluation-{digest_json(result)[:16]}"
    return result
