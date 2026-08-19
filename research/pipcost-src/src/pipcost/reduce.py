"""Deterministic raw-sample validation and reduction."""

from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
import statistics
from typing import Any

from pipcost.records import digest_file, read_json, read_jsonl


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile of no values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _cell(
    scenario_id: str,
    plan_id: str,
    samples: list[dict[str, Any]],
) -> dict[str, object]:
    values = [
        float(item["elapsed_ns"]) / int(item["inner_iterations"])
        for item in samples
    ]
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    observed = {
        float(item["observed_combined_selectivity"]) for item in samples
    }
    data_digests = {str(item["data_digest"]) for item in samples}
    sums = {int(item["sum"]) for item in samples}
    if len(observed) != 1 or len(data_digests) != 1 or len(sums) != 1:
        raise ValueError(
            f"inconsistent scenario evidence for {scenario_id}/{plan_id}"
        )
    return {
        "scenario_id": scenario_id,
        "plan_id": plan_id,
        "samples": len(samples),
        "median_ns": median,
        "minimum_ns": min(values),
        "maximum_ns": max(values),
        "mad_ns": statistics.median(deviations),
        "p05_ns": _percentile(values, 0.05),
        "p95_ns": _percentile(values, 0.95),
        "relative_mad": 0.0 if median == 0 else statistics.median(deviations) / median,
        "observed_combined_selectivity": observed.pop(),
        "data_digest": data_digests.pop(),
        "sum": sums.pop(),
    }


def reduce_run(
    run_dir: Path,
    *,
    require_complete: bool = True,
) -> dict[str, object]:
    if require_complete and not (run_dir / "COMPLETE").is_file():
        raise ValueError(f"run is incomplete: {run_dir}")
    run = read_json(run_dir / "run.json")
    scenarios_value = read_json(run_dir / "scenarios.json")
    scenario_records = scenarios_value["scenarios"]
    samples = read_jsonl(run_dir / "samples.jsonl")

    expected = {
        (str(scenario["scenario_id"]), str(plan_id), block)
        for scenario in scenario_records
        for plan_id in scenario["requested_plans"]
        for block in range(int(run["repetitions"]))
    }
    seen: set[tuple[str, str, int]] = set()
    duplicates: list[tuple[str, str, int]] = []
    foreign: list[tuple[str, str, int]] = []
    failures: list[dict[str, object]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        key = (
            str(sample["scenario_id"]),
            str(sample["plan_id"]),
            int(sample["paired_block"]),
        )
        if key in seen:
            duplicates.append(key)
            continue
        seen.add(key)
        if key not in expected:
            foreign.append(key)
            continue
        if sample.get("status") != "ok":
            failures.append(
                {
                    "scenario_id": key[0],
                    "plan_id": key[1],
                    "paired_block": key[2],
                    "reason": sample.get("reason", "unknown failure"),
                }
            )
            continue
        grouped[(key[0], key[1])].append(sample)

    missing = sorted(expected - seen)
    cells = [
        _cell(scenario_id, plan_id, values)
        for (scenario_id, plan_id), values in sorted(grouped.items())
        if len(values) == int(run["repetitions"])
    ]
    incomplete_cells = sorted(
        {
            (scenario_id, plan_id)
            for scenario_id, plan_id, _ in expected
            if len(grouped.get((scenario_id, plan_id), []))
            != int(run["repetitions"])
        }
    )
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "raw_samples_sha256": digest_file(run_dir / "samples.jsonl"),
        "expected_samples": len(expected),
        "observed_samples": len(samples),
        "complete": not missing
        and not duplicates
        and not foreign
        and not failures
        and not incomplete_cells,
        "missing": [
            {"scenario_id": item[0], "plan_id": item[1], "paired_block": item[2]}
            for item in missing
        ],
        "duplicates": [
            {"scenario_id": item[0], "plan_id": item[1], "paired_block": item[2]}
            for item in sorted(duplicates)
        ],
        "foreign": [
            {"scenario_id": item[0], "plan_id": item[1], "paired_block": item[2]}
            for item in sorted(foreign)
        ],
        "failures": failures,
        "incomplete_cells": [
            {"scenario_id": item[0], "plan_id": item[1]}
            for item in incomplete_cells
        ],
        "cells": cells,
    }
