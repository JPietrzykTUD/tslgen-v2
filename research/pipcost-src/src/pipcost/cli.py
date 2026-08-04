"""PIPCost command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from pipcost.build import (
    build_benchmark,
    check_build,
    load_build,
)
from pipcost.config import ExperimentConfig
from pipcost.cost_model import fit_model
from pipcost.evaluate import evaluate_model
from pipcost.host import (
    compiler_record,
    host_record,
    native_profile_report,
    tslc_doctor,
)
from pipcost.oracle import build_oracle
from pipcost.records import (
    canonical_json,
    read_json,
    write_json,
)
from pipcost.reduce import reduce_run
from pipcost.runner import run_experiment
from pipcost.tsl_project import (
    DEFAULT_TSL_REF,
    generate_tsl_project,
    resolve_tsl_source,
)
from pipcost.workspace import WorkspacePaths, require_below


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scratch-root",
        help="output root below workspace tslctmp/pipcost",
    )


def _target(parser: argparse.ArgumentParser, *, compiler: bool = False) -> None:
    parser.add_argument("--tsl-ref", default=DEFAULT_TSL_REF)
    parser.add_argument("--profile", default="avx2")
    parser.add_argument("--simd-lanes", type=int, default=8)
    if compiler:
        parser.add_argument("--compiler", default="c++")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipcost",
        description="Representation-aware SIMD pipeline cost-model prototype.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="inspect native/toolchain readiness")
    _common(doctor)
    _target(doctor, compiler=True)

    generate = subparsers.add_parser("generate", help="generate the selected TSL project")
    _common(generate)
    _target(generate)

    build = subparsers.add_parser("build", help="build the benchmark and kernel tests")
    _common(build)
    _target(build, compiler=True)

    check = subparsers.add_parser("check", help="run generated kernel correctness checks")
    _common(check)
    _target(check, compiler=True)
    check.add_argument(
        "--disassemble",
        action="store_true",
        help="capture build-specific disassembly under the scratch build",
    )

    run = subparsers.add_parser("run", help="execute one immutable experiment config")
    _common(run)
    run.add_argument("--config", required=True)

    summarize = subparsers.add_parser(
        "summarize", help="validate and reproduce an existing run summary"
    )
    _common(summarize)
    summarize.add_argument("--run", required=True)

    fit = subparsers.add_parser("fit", help="fit a bounded model from training cells")
    _common(fit)
    fit.add_argument("--run", required=True)
    fit.add_argument(
        "--allow-inconclusive",
        action="store_true",
        help="fit despite Gate A not passing (diagnostic use only)",
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="evaluate a fitted model on held-out cells"
    )
    _common(evaluate)
    evaluate.add_argument("--run", required=True)
    evaluate.add_argument("--model", required=True)
    return parser


def _run_dir(paths: WorkspacePaths, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute() and len(candidate.parts) == 1:
        candidate = paths.output_path("runs", value)
    elif not candidate.is_absolute():
        candidate = paths.root / candidate
    return require_below(candidate, paths.output_path("runs"), label="run path")


def _summaries(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = reduce_run(run_dir)
    run = read_json(run_dir / "run.json")
    scenarios = read_json(run_dir / "scenarios.json")
    oracle = build_oracle(
        summary,
        scenarios,
        repetitions=int(run["repetitions"]),
        materiality_threshold=float(run["materiality_threshold"]),
        manual_threshold=float(run["manual_threshold"]),
    )
    existing_summary = read_json(run_dir / "summary.json")
    existing_oracle = read_json(run_dir / "oracle.json")
    if canonical_json(summary) != canonical_json(existing_summary):
        raise RuntimeError("recomputed summary differs from the published run")
    if canonical_json(oracle) != canonical_json(existing_oracle):
        raise RuntimeError("recomputed oracle differs from the published run")
    return summary, oracle


def _doctor(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    source = resolve_tsl_source(paths, args.tsl_ref)
    machine_profiles = (
        source.snapshot_root
        / "supplementary"
        / "buildsystem"
        / "machine_profiles.json"
    )
    compiler = compiler_record(args.compiler)
    report = tslc_doctor(
        paths,
        source_root=source.snapshot_root,
        profile=args.profile,
        compiler=args.compiler,
    )
    native = native_profile_report(machine_profiles, args.profile)
    return {
        "schema_version": 1,
        "status": (
            "ok"
            if compiler["available"]
            and native["native"]
            and report["returncode"] == 0
            else "error"
        ),
        "scratch_root": str(paths.scratch_root),
        "tsl_release": {
            "requested_ref": args.tsl_ref,
            "commit": source.commit,
            "source_digest": source.manifest["source_digest"],
        },
        "compiler": compiler,
        "native_profile": native,
        "host": host_record(),
        "tslc_doctor": report,
    }


def _generate(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    evidence = generate_tsl_project(
        paths,
        profile=args.profile,
        simd_lanes=args.simd_lanes,
        tsl_ref=args.tsl_ref,
    )
    return {
        "schema_version": 1,
        "status": "ok",
        "generation_id": evidence.generation_id,
        "output_root": str(evidence.output_root),
        "artifact_manifest_digest": evidence.manifest[
            "artifact_manifest_digest"
        ],
        "coverage_entries": len(evidence.manifest["coverage"]),
        "skipped_entries": len(evidence.manifest["skipped"]),
    }


def _build(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    evidence = build_benchmark(
        paths,
        profile=args.profile,
        simd_lanes=args.simd_lanes,
        compiler=args.compiler,
        tsl_ref=args.tsl_ref,
    )
    return {
        "schema_version": 1,
        "status": "ok",
        "build_id": evidence.build_id,
        "build_root": str(evidence.build_root),
        "executable": str(evidence.executable),
        "executable_sha256": evidence.manifest["executable_sha256"],
    }


def _check(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    build = load_build(
        paths,
        profile=args.profile,
        simd_lanes=args.simd_lanes,
        compiler=args.compiler,
        tsl_ref=args.tsl_ref,
    )
    return check_build(
        build,
        validate_vectorization=args.disassemble,
    )


def _fit(
    args: argparse.Namespace,
    paths: WorkspacePaths,
) -> dict[str, object]:
    run_dir = _run_dir(paths, args.run)
    summary, oracle = _summaries(run_dir)
    if oracle["gate_a"]["status"] != "pass" and not args.allow_inconclusive:
        raise RuntimeError(
            "Scientific Gate A did not pass; use --allow-inconclusive only "
            "for diagnostic model fitting"
        )
    model = fit_model(summary, read_json(run_dir / "scenarios.json"))
    model_path = paths.output_path("models", f"{model['model_id']}.json")
    if model_path.exists():
        if canonical_json(read_json(model_path)) != canonical_json(model):
            raise RuntimeError(f"model identity collision at {model_path}")
    else:
        write_json(model_path, model)
    groups = model.get("groups")
    if not isinstance(groups, list):
        raise RuntimeError("fitted model did not contain a group list")
    return {
        "schema_version": 1,
        "status": "ok",
        "gate_a": oracle["gate_a"],
        "model_id": model["model_id"],
        "model_path": str(model_path),
        "training_groups": len(groups),
    }


def _evaluate(
    args: argparse.Namespace,
    paths: WorkspacePaths,
) -> dict[str, object]:
    run_dir = _run_dir(paths, args.run)
    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = paths.root / model_path
    model_path = require_below(
        model_path, paths.scratch_root, label="model path"
    )
    model = read_json(model_path)
    summary, oracle = _summaries(run_dir)
    run = read_json(run_dir / "run.json")
    evaluation = evaluate_model(
        model,
        summary,
        oracle,
        read_json(run_dir / "scenarios.json"),
        materiality_threshold=float(run["materiality_threshold"]),
        manual_threshold=float(run["manual_threshold"]),
    )
    output = paths.output_path(
        "evaluations", f"{evaluation['evaluation_id']}.json"
    )
    if output.exists():
        if canonical_json(read_json(output)) != canonical_json(evaluation):
            raise RuntimeError(f"evaluation identity collision at {output}")
    else:
        write_json(output, evaluation)
    return {
        "schema_version": 1,
        "status": "ok",
        "evaluation_id": evaluation["evaluation_id"],
        "evaluation_path": str(output),
        "gate_b": evaluation["gate_b"],
        "top1_accuracy": evaluation["top1_accuracy"],
        "median_regret": evaluation["median_regret"],
        "p95_regret": evaluation["p95_regret"],
        "worst_regret": evaluation["worst_regret"],
    }


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    paths = WorkspacePaths.create(args.scratch_root)
    if args.command == "doctor":
        return _doctor(args, paths)
    if args.command == "generate":
        return _generate(args, paths)
    if args.command == "build":
        return _build(args, paths)
    if args.command == "check":
        return _check(args, paths)
    if args.command == "run":
        config = ExperimentConfig.load(args.config)
        return run_experiment(paths, config)
    if args.command == "summarize":
        run_dir = _run_dir(paths, args.run)
        summary, oracle = _summaries(run_dir)
        return {
            "schema_version": 1,
            "status": "ok",
            "run_id": summary["run_id"],
            "complete": summary["complete"],
            "cells": len(summary["cells"]),
            "gate_a": oracle["gate_a"],
        }
    if args.command == "fit":
        return _fit(args, paths)
    if args.command == "evaluate":
        return _evaluate(args, paths)
    raise AssertionError(f"unhandled command {args.command!r}")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _dispatch(args)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {"schema_version": 1, "status": "error", "message": str(exc)},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status", "ok") == "ok" else 1


__all__ = ["main"]
