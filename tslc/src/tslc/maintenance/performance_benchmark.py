"""Run reproducible fresh-process compiler performance measurements."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import resource
from statistics import median
import subprocess
import sys
import time

from tslc._pipeline_inputs import _load_inputs
from tslc._pipeline_lowering_cache import _LoweringCacheInfo
from tslc.api import _ARITH_TYPE_TAGS, _expand_sources
from tslc.authoring import check_catalog
from tslc.ir.scan import _cached_scan
from tslc.lower._query_model import _cached_parse_query
from tslc.maintenance.generation_snapshot import input_manifest_digest
from tslc.pipeline import GenerationRequest, GenerationResult, _GenerationSession


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_DATA_ROOT = _REPO_ROOT / "tsldata"
_PROFILES_PATH = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
_SCRATCH_ROOT = _REPO_ROOT / "tslctmp"
_MODULE_NAME = "tslc.maintenance.performance_benchmark"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    kind: str
    primitives: tuple[str, ...] | None = None
    profiles: tuple[str, ...] | None = None
    type_tags: tuple[str, ...] = _ARITH_TYPE_TAGS
    backends: tuple[str, ...] = ("cpp", "rust")


BENCHMARK_CASES: dict[str, BenchmarkCase] = {
    case.name: case
    for case in (
        BenchmarkCase("check", "check"),
        BenchmarkCase("focused", "generate", primitives=("add",), profiles=("avx2",)),
        BenchmarkCase("avx2-full-corpus", "generate", profiles=("avx2",)),
        BenchmarkCase(
            "lowering-reuse",
            "generate",
            profiles=("skylake", "cascadelake"),
        ),
        BenchmarkCase("full", "generate"),
    )
}


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    case: str
    wall_seconds: float
    cpu_seconds: float
    peak_rss_kib: int
    diagnostics: int
    coverage: int
    skipped: int
    artifacts: int
    scan_cache_hits: int = 0
    scan_cache_misses: int = 0
    scan_cache_size: int = 0
    scan_cache_capacity: int = 0
    lowering_cache_hits: int = 0
    lowering_cache_misses: int = 0
    lowering_cache_size: int = 0
    query_parse_cache_hits: int = 0
    query_parse_cache_misses: int = 0
    query_parse_cache_size: int = 0
    query_parse_cache_capacity: int = 0


def run_sample(case: BenchmarkCase) -> BenchmarkSample:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    lowering_cache_hits = 0
    lowering_cache_misses = 0
    lowering_cache_size = 0
    if case.kind == "check":
        check_result = check_catalog([_DATA_ROOT], backends=case.backends)
        diagnostics = len(check_result.diagnostics)
        coverage = 0
        skipped = 0
        artifacts = 0
    else:
        generation_result, cache_info = _run_generation(case)
        lowering_cache_hits = cache_info.hits
        lowering_cache_misses = cache_info.misses
        lowering_cache_size = cache_info.size
        diagnostics = len(generation_result.diagnostics)
        coverage = len(generation_result.coverage)
        skipped = len(generation_result.skipped)
        artifacts = len(generation_result.artifacts.artifacts)
    scan_cache = _cached_scan.cache_info()
    query_parse_cache = _cached_parse_query.cache_info()
    return BenchmarkSample(
        case=case.name,
        wall_seconds=time.perf_counter() - start_wall,
        cpu_seconds=time.process_time() - start_cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        diagnostics=diagnostics,
        coverage=coverage,
        skipped=skipped,
        artifacts=artifacts,
        scan_cache_hits=scan_cache.hits,
        scan_cache_misses=scan_cache.misses,
        scan_cache_size=scan_cache.currsize,
        scan_cache_capacity=scan_cache.maxsize or 0,
        lowering_cache_hits=lowering_cache_hits,
        lowering_cache_misses=lowering_cache_misses,
        lowering_cache_size=lowering_cache_size,
        query_parse_cache_hits=query_parse_cache.hits,
        query_parse_cache_misses=query_parse_cache.misses,
        query_parse_cache_size=query_parse_cache.currsize,
        query_parse_cache_capacity=query_parse_cache.maxsize or 0,
    )


def _run_generation(
    case: BenchmarkCase,
) -> tuple[GenerationResult, _LoweringCacheInfo]:
    request = GenerationRequest(
        source_paths=_expand_sources((_DATA_ROOT,)),
        machine_profiles_path=_PROFILES_PATH,
        primitives=case.primitives,
        profiles=case.profiles,
        type_tags=case.type_tags,
        backends=case.backends,
        render_artifacts=False,
    )
    inputs, diagnostics = _load_inputs(request)
    if inputs is None:
        raise RuntimeError("benchmark generation inputs failed to load")
    session = _GenerationSession(request, inputs, diagnostics)
    result = session.run()
    return result, session.lowering_cache.info()


def run_fresh_samples(case: BenchmarkCase, count: int) -> tuple[BenchmarkSample, ...]:
    if count <= 0:
        raise ValueError("sample count must be positive")
    samples: list[BenchmarkSample] = []
    for _ in range(count):
        completed = subprocess.run(
            [sys.executable, "-m", _MODULE_NAME, "worker", case.name],
            cwd=_REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"benchmark worker failed: {detail}")
        payload = json.loads(completed.stdout)
        samples.append(BenchmarkSample(**payload))
    return tuple(samples)


def benchmark_report(case: BenchmarkCase, samples: tuple[BenchmarkSample, ...]) -> dict[str, object]:
    return {
        "version": 1,
        "case": case.name,
        "request": {
            "kind": case.kind,
            "primitives": case.primitives,
            "profiles": case.profiles,
            "type_tags": case.type_tags,
            "backends": case.backends,
            "render_artifacts": False,
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "cpu": _cpu_model(),
            "logical_cpus": os.cpu_count(),
            "input_manifest_digest": input_manifest_digest(),
        },
        "samples": [asdict(sample) for sample in samples],
        "median": {
            "wall_seconds": median(sample.wall_seconds for sample in samples),
            "cpu_seconds": median(sample.cpu_seconds for sample in samples),
            "peak_rss_kib": median(sample.peak_rss_kib for sample in samples),
        },
    }


def _cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def _write_report(path: Path, report: dict[str, object]) -> None:
    output = path.resolve()
    try:
        output.relative_to(_SCRATCH_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"benchmark output must be under {_SCRATCH_ROOT}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _worker_command(case_name: str) -> int:
    sample = run_sample(BENCHMARK_CASES[case_name])
    print(json.dumps(asdict(sample), sort_keys=True))
    return 0


def _run_command(args: argparse.Namespace) -> int:
    case = BENCHMARK_CASES[args.case]
    try:
        samples = run_fresh_samples(case, args.samples)
        report = benchmark_report(case, samples)
        if args.output is not None:
            _write_report(Path(args.output), report)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run sequential fresh-process samples")
    run_parser.add_argument("--case", choices=sorted(BENCHMARK_CASES), required=True)
    run_parser.add_argument("--samples", type=int, required=True)
    run_parser.add_argument("--output")
    worker_parser = subparsers.add_parser("worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("case", choices=sorted(BENCHMARK_CASES))
    args = parser.parse_args(argv)
    if args.command == "worker":
        return _worker_command(args.case)
    return _run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "BENCHMARK_CASES",
    "BenchmarkCase",
    "BenchmarkSample",
    "benchmark_report",
    "main",
    "run_fresh_samples",
    "run_sample",
)
