"""Paired benchmark execution and immutable run publication."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Any, cast

from pipcost import SCHEMA_VERSION, __version__
from pipcost.build import (
    BuildEvidence,
    build_benchmark,
    check_build,
    list_plans,
    load_build,
)
from pipcost.config import ExperimentConfig
from pipcost.domain import Scenario
from pipcost.host import host_record, native_profile_report
from pipcost.matrix import (
    candidate_plan_ids,
    expand_scenarios,
    reference_plan_ids,
    requested_plan_ids,
)
from pipcost.oracle import build_oracle
from pipcost.records import (
    digest_file,
    digest_json,
    digest_tree,
    write_json,
    write_jsonl,
)
from pipcost.reduce import reduce_run
from pipcost.tsl_project import (
    generate_tsl_project,
    load_generation,
    resolve_tsl_source,
)
from pipcost.workspace import WorkspacePaths


def _ensure_build(
    paths: WorkspacePaths,
    config: ExperimentConfig,
) -> BuildEvidence:
    try:
        load_generation(
            paths,
            profile=config.profile,
            simd_lanes=config.simd_lanes,
            tsl_ref=config.tsl_ref,
        )
    except FileNotFoundError:
        generate_tsl_project(
            paths,
            profile=config.profile,
            simd_lanes=config.simd_lanes,
            tsl_ref=config.tsl_ref,
        )
    try:
        return load_build(
            paths,
            profile=config.profile,
            simd_lanes=config.simd_lanes,
            compiler=config.compiler,
            tsl_ref=config.tsl_ref,
        )
    except FileNotFoundError:
        return build_benchmark(
            paths,
            profile=config.profile,
            simd_lanes=config.simd_lanes,
            compiler=config.compiler,
            tsl_ref=config.tsl_ref,
        )


def _binary_command(
    build: BuildEvidence,
    scenario: Scenario,
    plan_id: str,
    *,
    warmups: int,
    inner_iterations: int,
) -> list[str]:
    return [
        str(build.executable),
        "--plan",
        plan_id,
        "--rows",
        str(scenario.rows),
        "--batch-rows",
        str(scenario.batch_rows),
        "--first-selectivity",
        repr(scenario.first_selectivity),
        "--conditional-selectivity",
        repr(scenario.conditional_selectivity),
        "--pattern",
        scenario.pattern,
        "--seed",
        str(scenario.seed),
        "--warmups",
        str(warmups),
        "--inner-iterations",
        str(inner_iterations),
    ]


def _invoke(
    build: BuildEvidence,
    scenario: Scenario,
    plan_id: str,
    *,
    warmups: int,
    inner_iterations: int,
) -> dict[str, Any]:
    command = _binary_command(
        build,
        scenario,
        plan_id,
        warmups=warmups,
        inner_iterations=inner_iterations,
    )
    completed = subprocess.run(
        command,
        cwd=build.build_root,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        value = cast(dict[str, Any], json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"benchmark returned invalid JSON: {completed.stderr.strip()}"
        ) from exc
    if completed.returncode != 0 or value.get("status") != "ok":
        raise RuntimeError(
            str(value.get("reason", value.get("status", completed.stderr.strip())))
        )
    return value


def _inner_iterations(
    build: BuildEvidence,
    scenario: Scenario,
    plan_id: str,
    config: ExperimentConfig,
) -> int:
    calibration = _invoke(
        build,
        scenario,
        plan_id,
        warmups=config.warmups,
        inner_iterations=1,
    )
    elapsed = max(int(calibration["elapsed_ns"]), 1)
    return min(
        10_000_000,
        max(1, math.ceil(config.minimum_sample_ns / elapsed)),
    )


def deterministic_plan_order(
    plan_ids: tuple[str, ...],
    *,
    run_seed: int,
    scenario_id: str,
    paired_block: int,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            plan_ids,
            key=lambda plan_id: (
                sha256(
                    f"{run_seed}:{scenario_id}:{paired_block}:{plan_id}".encode()
                ).digest(),
                plan_id,
            ),
        )
    )


def _run_id(config: ExperimentConfig) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    entropy = digest_json(
        {
            "config": config.digest,
            "time_ns": time.time_ns(),
            "pid": Path("/proc/self").resolve().name
            if Path("/proc/self").exists()
            else 0,
        }
    )[:10]
    return f"{stamp}-{config.name}-{entropy}"


def run_experiment(
    paths: WorkspacePaths,
    config: ExperimentConfig,
) -> dict[str, object]:
    source = resolve_tsl_source(paths, config.tsl_ref)
    machine_profiles = (
        source.snapshot_root
        / "supplementary"
        / "buildsystem"
        / "machine_profiles.json"
    )
    native = native_profile_report(machine_profiles, config.profile)
    if not native["native"]:
        raw_missing = native.get("missing_features")
        if not isinstance(raw_missing, list):
            raise RuntimeError("native profile report has no missing-feature list")
        missing = [str(item) for item in raw_missing]
        raise RuntimeError(
            f"profile {config.profile!r} is not native: "
            f"missing {', '.join(missing)}"
        )
    build = _ensure_build(paths, config)
    check = check_build(build, validate_vectorization=True)
    plan_manifest = list_plans(build)
    plans_by_id = {
        str(item["plan_id"]): item for item in plan_manifest["plans"]
    }
    scenarios = expand_scenarios(config)
    for scenario in scenarios:
        for plan_id in requested_plan_ids(config, scenario):
            plan = plans_by_id.get(plan_id)
            if plan is None:
                raise ValueError(f"config requests unknown plan {plan_id!r}")
            if not plan["supported"]:
                raise ValueError(
                    f"config requests unsupported plan {plan_id!r}: "
                    f"{plan['skip_reason']}"
                )

    run_id = _run_id(config)
    run_dir = paths.output_path("runs", run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    prototype_digest, prototype_files = digest_tree(paths.prototype_root)
    run_record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "pipcost_version": __version__,
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "raw_complete",
        "query_version": "filter-filter-sum-v1",
        "generator_version": "splitmix64-exact-selectivity-v1",
        "config_path": str(config.source_path),
        "config_digest": config.digest,
        "prototype_digest": prototype_digest,
        "prototype_files": [
            {"path": path, "sha256": digest}
            for path, digest in prototype_files
        ],
        "tsl_ref": config.tsl_ref,
        "profile": config.profile,
        "simd_lanes": config.simd_lanes,
        "repetitions": config.repetitions,
        "warmups": config.warmups,
        "minimum_sample_ns": config.minimum_sample_ns,
        "run_seed": config.run_seed,
        "materiality_threshold": config.materiality_threshold,
        "manual_threshold": config.manual_threshold,
        "build_id": build.build_id,
        "check": check,
    }
    scenario_records = [
        {
            "scenario_id": scenario.scenario_id,
            **scenario.to_record(),
            "requested_combined_selectivity": (
                scenario.requested_combined_selectivity
            ),
            "candidate_plans": list(candidate_plan_ids(config, scenario)),
            "reference_plans": list(reference_plan_ids(config, scenario)),
            "requested_plans": list(requested_plan_ids(config, scenario)),
        }
        for scenario in scenarios
    ]
    generation = load_generation(
        paths,
        profile=config.profile,
        simd_lanes=config.simd_lanes,
        tsl_ref=config.tsl_ref,
    )
    write_json(run_dir / "run.json", run_record)
    write_json(run_dir / "host.json", {**host_record(), "native_profile": native})
    write_json(
        run_dir / "build.json",
        {
            "generation": generation.manifest,
            "build": build.manifest,
        },
    )
    write_json(run_dir / "scenarios.json", {"scenarios": scenario_records})
    write_json(run_dir / "plans.json", plan_manifest)

    calibrated: dict[tuple[str, str], int] = {}
    samples: list[dict[str, object]] = []
    for scenario in scenarios:
        plan_ids = requested_plan_ids(config, scenario)
        for plan_id in plan_ids:
            calibrated[(scenario.scenario_id, plan_id)] = _inner_iterations(
                build, scenario, plan_id, config
            )
        for block in range(config.repetitions):
            order = deterministic_plan_order(
                plan_ids,
                run_seed=config.run_seed,
                scenario_id=scenario.scenario_id,
                paired_block=block,
            )
            for order_index, plan_id in enumerate(order):
                inner_iterations = calibrated[
                    (scenario.scenario_id, plan_id)
                ]
                sample: dict[str, object] = {
                    "run_id": run_id,
                    "scenario_id": scenario.scenario_id,
                    "plan_id": plan_id,
                    "paired_block": block,
                    "repetition": block,
                    "plan_order": order_index,
                    "inner_iterations": inner_iterations,
                    "rows": scenario.rows,
                }
                try:
                    observed = _invoke(
                        build,
                        scenario,
                        plan_id,
                        warmups=0,
                        inner_iterations=inner_iterations,
                    )
                    sample.update(observed)
                except RuntimeError as exc:
                    sample.update({"status": "failed", "reason": str(exc)})
                sample["sample_id"] = (
                    f"sample-{digest_json(sample)[:20]}"
                )
                samples.append(sample)
    write_jsonl(run_dir / "samples.jsonl", samples)
    summary = reduce_run(run_dir, require_complete=False)
    oracle = build_oracle(
        summary,
        {"scenarios": scenario_records},
        repetitions=config.repetitions,
        materiality_threshold=config.materiality_threshold,
        manual_threshold=config.manual_threshold,
    )
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "oracle.json", oracle)
    complete = {
        "schema_version": 1,
        "run_id": run_id,
        "published_utc": datetime.now(timezone.utc).isoformat(),
        "files": {
            name: digest_file(run_dir / name)
            for name in (
                "run.json",
                "host.json",
                "build.json",
                "scenarios.json",
                "plans.json",
                "samples.jsonl",
                "summary.json",
                "oracle.json",
            )
        },
    }
    write_json(run_dir / "COMPLETE", complete)
    return {
        "schema_version": 1,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "samples": len(samples),
        "summary_complete": summary["complete"],
        "gate_a": oracle["gate_a"],
    }
