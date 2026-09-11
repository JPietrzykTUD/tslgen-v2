#!/usr/bin/env python3
"""Measure generated C++ and Rust support-file compile cost without networking."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "34e8980b"
CPP_PROFILES: Mapping[str, tuple[str, str]] = {
    "scalar": ("TSL_PROFILE_SCALAR", "tsl_scalar.hpp"),
    "avx2": ("TSL_PROFILE_AVX2", "tsl_avx2.hpp"),
}
CPP_WORKLOADS = ("core", "primitives", "algorithms")
RUST_TASKS = ("check", "release_build", "rustdoc", "downstream_consumer")


class MeasurementError(RuntimeError):
    """A required generated input or local tool invocation failed."""


@dataclass(frozen=True, slots=True)
class TimingSample:
    wall_seconds: float
    cpu_seconds: float


@dataclass(frozen=True, slots=True)
class TimingSummary:
    wall_median_seconds: float
    wall_min_seconds: float
    wall_max_seconds: float
    cpu_median_seconds: float
    samples: tuple[TimingSample, ...]


@dataclass(frozen=True, slots=True)
class TimingComparison:
    baseline_wall_seconds: float
    candidate_wall_seconds: float
    baseline_cpu_seconds: float
    candidate_cpu_seconds: float
    delta_seconds: float
    delta_percent: float
    cpu_delta_percent: float
    observed_spread_seconds: float
    classification: str


@dataclass(frozen=True, slots=True)
class RustToolchain:
    label: str
    command_prefix: tuple[str, ...]
    environment: Mapping[str, str]
    rustc_version: str
    cargo_version: str


def summarize_timings(samples: Sequence[TimingSample]) -> TimingSummary:
    if not samples:
        raise ValueError("at least one timing sample is required")
    wall = tuple(sample.wall_seconds for sample in samples)
    cpu = tuple(sample.cpu_seconds for sample in samples)
    return TimingSummary(
        wall_median_seconds=statistics.median(wall),
        wall_min_seconds=min(wall),
        wall_max_seconds=max(wall),
        cpu_median_seconds=statistics.median(cpu),
        samples=tuple(samples),
    )


def compare_timings(
    baseline: TimingSummary,
    candidate: TimingSummary,
) -> TimingComparison:
    delta = candidate.wall_median_seconds - baseline.wall_median_seconds
    delta_percent = (
        100.0 * delta / baseline.wall_median_seconds
        if baseline.wall_median_seconds
        else 0.0
    )
    cpu_delta_percent = (
        100.0
        * (candidate.cpu_median_seconds - baseline.cpu_median_seconds)
        / baseline.cpu_median_seconds
        if baseline.cpu_median_seconds
        else 0.0
    )
    spread = max(
        baseline.wall_max_seconds - baseline.wall_min_seconds,
        candidate.wall_max_seconds - candidate.wall_min_seconds,
    )
    if abs(delta) <= spread:
        classification = "within_observed_spread"
    elif delta > 0:
        classification = "regression_outside_observed_spread"
    else:
        classification = "improvement_outside_observed_spread"
    return TimingComparison(
        baseline_wall_seconds=baseline.wall_median_seconds,
        candidate_wall_seconds=candidate.wall_median_seconds,
        baseline_cpu_seconds=baseline.cpu_median_seconds,
        candidate_cpu_seconds=candidate.cpu_median_seconds,
        delta_seconds=delta,
        delta_percent=delta_percent,
        cpu_delta_percent=cpu_delta_percent,
        observed_spread_seconds=spread,
        classification=classification,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validate_generated_project(root: Path) -> None:
    required = (
        root / ".tslc-manifest.json",
        root / "cpp" / "include" / "tsl_core.hpp",
        root / "cpp" / "include" / "tsl_scalar.hpp",
        root / "cpp" / "include" / "tsl_avx2.hpp",
        root / "cpp" / "include" / "tsl_algorithm.hpp",
        root / "rust" / "Cargo.toml",
        root / "rust" / "src" / "lib.rs",
    )
    missing = tuple(path for path in required if not path.is_file())
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise MeasurementError(f"generated project is incomplete: {joined}")


def _require_scratch_path(path: Path, repo_root: Path) -> None:
    scratch = (repo_root / "tslctmp").resolve()
    resolved = path.resolve()
    if resolved == scratch or scratch not in resolved.parents:
        raise MeasurementError(f"scratch output must be below {scratch}: {resolved}")


def _command_version(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=None if environment is None else dict(environment),
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise MeasurementError(f"command failed ({' '.join(command)}): {detail}")
    return completed.stdout.splitlines()[0].strip()


def _run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=None if environment is None else dict(environment),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr + completed.stdout).strip()
        raise MeasurementError(
            f"command failed ({' '.join(command)}):\n{detail[-8000:]}"
        )


def _timed_command(
    command: Sequence[str],
    *,
    cwd: Path,
    log_path: Path,
    environment: Mapping[str, str] | None = None,
) -> TimingSample:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=None if environment is None else dict(environment),
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime + after.ru_stime) - (
        before.ru_utime + before.ru_stime
    )
    if completed.returncode != 0:
        detail = log_path.read_text(encoding="utf-8", errors="replace")
        raise MeasurementError(
            f"command failed ({' '.join(command)}):\n{detail[-8000:]}"
        )
    return TimingSample(wall_seconds=wall, cpu_seconds=cpu)


def _cpp_source(workload: str, profile_header: str) -> str:
    if workload == "core":
        includes = "#include <tsl_core.hpp>"
    elif workload == "primitives":
        includes = f"#include <{profile_header}>"
    elif workload == "algorithms":
        includes = (
            f"#include <{profile_header}>\n"
            "#include <tsl_algorithm.hpp>"
        )
    else:
        raise ValueError(f"unknown C++ workload: {workload}")
    return f"{includes}\nint main() {{ return 0; }}\n"


def _cpp_command(
    compiler: str,
    source: Path,
    include_root: Path,
    macro: str,
    profile: str,
    *extra: str,
) -> tuple[str, ...]:
    flags = [
        compiler,
        "-std=c++17",
        "-O0",
        f"-D{macro}",
        f"-I{include_root}",
    ]
    if profile == "avx2":
        flags.append("-mavx2")
    return (*flags, *extra, str(source))


def _preprocessed_volume(command: Sequence[str], *, cwd: Path) -> tuple[int, int]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    stdout = process.stdout
    byte_count = 0
    line_count = 0
    for chunk in iter(lambda: stdout.read(1024 * 1024), b""):
        byte_count += len(chunk)
        line_count += chunk.count(b"\n")
    assert process.stderr is not None
    error = process.stderr.read().decode("utf-8", errors="replace")
    returncode = process.wait()
    if returncode != 0:
        raise MeasurementError(
            f"preprocessor failed ({' '.join(command)}):\n{error[-8000:]}"
        )
    return byte_count, line_count


def _clang_token_records(command: Sequence[str], *, cwd: Path) -> int:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stderr is not None
    records = sum(1 for line in process.stderr if line.strip())
    returncode = process.wait()
    if returncode != 0:
        raise MeasurementError(
            f"Clang token inventory failed ({' '.join(command)})"
        )
    return records


def _available_cpp_compilers() -> tuple[tuple[str, str, str], ...]:
    available = []
    for label, executable in (("gcc", "g++"), ("clang", "clang++")):
        path = shutil.which(executable)
        if path is not None:
            available.append((label, path, _command_version((path, "--version"))))
    if not available:
        raise MeasurementError("neither g++ nor clang++ is available")
    return tuple(available)


def _measure_cpp(
    projects: Mapping[str, Path],
    *,
    work_root: Path,
    repetitions: int,
) -> dict[str, Any]:
    compilers = _available_cpp_compilers()
    sources = work_root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    volumes: list[dict[str, object]] = []
    token_records: list[dict[str, object]] = []
    samples: dict[tuple[str, str, str, str], list[TimingSample]] = {}

    for profile, (macro, profile_header) in CPP_PROFILES.items():
        for workload in CPP_WORKLOADS:
            source = sources / f"{profile}-{workload}.cpp"
            source.write_text(
                _cpp_source(workload, profile_header),
                encoding="utf-8",
            )
            for revision, root in projects.items():
                include_root = root / "cpp" / "include"
                for compiler_label, compiler, _ in compilers:
                    command = _cpp_command(
                        compiler,
                        source,
                        include_root,
                        macro,
                        profile,
                        "-E",
                        "-P",
                    )
                    byte_count, line_count = _preprocessed_volume(
                        command,
                        cwd=work_root,
                    )
                    volumes.append(
                        {
                            "revision": revision,
                            "compiler": compiler_label,
                            "profile": profile,
                            "workload": workload,
                            "bytes": byte_count,
                            "lines": line_count,
                        }
                    )

            clang = next(
                (item[1] for item in compilers if item[0] == "clang"),
                None,
            )
            if clang is not None:
                for revision, root in projects.items():
                    include_root = root / "cpp" / "include"
                    command = _cpp_command(
                        clang,
                        source,
                        include_root,
                        macro,
                        profile,
                        "-fsyntax-only",
                        "-Xclang",
                        "-dump-tokens",
                    )
                    token_records.append(
                        {
                            "revision": revision,
                            "profile": profile,
                            "workload": workload,
                            "clang_token_records": _clang_token_records(
                                command,
                                cwd=work_root,
                            ),
                        }
                    )

    for compiler_label, compiler, _ in compilers:
        for profile, (macro, profile_header) in CPP_PROFILES.items():
            for workload in CPP_WORKLOADS:
                source = sources / f"{profile}-{workload}.cpp"
                for repetition in range(repetitions):
                    order = tuple(projects)
                    if repetition % 2:
                        order = tuple(reversed(order))
                    for revision in order:
                        output = work_root / "object" / "measure.o"
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.unlink(missing_ok=True)
                        command = _cpp_command(
                            compiler,
                            source,
                            projects[revision] / "cpp" / "include",
                            macro,
                            profile,
                            "-c",
                            "-o",
                            str(output),
                        )
                        key = (revision, compiler_label, profile, workload)
                        samples.setdefault(key, []).append(
                            _timed_command(
                                command,
                                cwd=work_root,
                                log_path=work_root / "cpp-command.log",
                            )
                        )

    timings = []
    comparisons = []
    for key, values in sorted(samples.items()):
        revision, compiler_label, profile, workload = key
        timings.append(
            {
                "revision": revision,
                "compiler": compiler_label,
                "profile": profile,
                "workload": workload,
                **asdict(summarize_timings(values)),
            }
        )
    for compiler_label, _, _ in compilers:
        for profile in CPP_PROFILES:
            for workload in CPP_WORKLOADS:
                baseline = summarize_timings(
                    samples[("baseline", compiler_label, profile, workload)]
                )
                candidate = summarize_timings(
                    samples[("candidate", compiler_label, profile, workload)]
                )
                comparisons.append(
                    {
                        "compiler": compiler_label,
                        "profile": profile,
                        "workload": workload,
                        **asdict(compare_timings(baseline, candidate)),
                    }
                )
    return {
        "tools": {
            label: {"path": path, "version": version}
            for label, path, version in compilers
        },
        "preprocessed_volume": volumes,
        "clang_token_records": token_records,
        "timings": timings,
        "comparisons": comparisons,
    }


def _rust_environment(rustup_home: Path | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["CARGO_NET_OFFLINE"] = "true"
    if rustup_home is not None:
        environment["RUSTUP_HOME"] = str(rustup_home.resolve())
    return environment


def _rust_toolchain(
    label: str,
    name: str,
    *,
    rustup_home: Path | None = None,
) -> RustToolchain | None:
    rustup = shutil.which("rustup")
    if rustup is None:
        return None
    environment = _rust_environment(rustup_home)
    prefix = (rustup, "run", name)
    try:
        rustc_version = _command_version(
            (*prefix, "rustc", "--version"),
            environment=environment,
        )
        cargo_version = _command_version(
            (*prefix, "cargo", "--version"),
            environment=environment,
        )
    except MeasurementError:
        return None
    return RustToolchain(
        label=label,
        command_prefix=prefix,
        environment=environment,
        rustc_version=rustc_version,
        cargo_version=cargo_version,
    )


def _write_consumer(root: Path, generated_root: Path) -> Path:
    source_root = root / "src"
    source_root.mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text(
        """[package]
name = "tsl-support-compile-cost-consumer"
version = "0.0.0"
edition = "2021"

[dependencies]
tsl = { path = "@PATH@", default-features = false }
""".replace("@PATH@", (generated_root / "rust").resolve().as_posix()),
        encoding="utf-8",
    )
    (source_root / "main.rs").write_text(
        """fn main() {
    let error = tsl::PreconditionError::IndexOutOfBounds;
    let _ = core::mem::discriminant(&error);
}
""",
        encoding="utf-8",
    )
    return root / "Cargo.toml"


def _rust_command(
    toolchain: RustToolchain,
    task: str,
    *,
    generated_root: Path,
    consumer_manifest: Path,
    target_root: Path,
) -> tuple[str, ...]:
    cargo = (*toolchain.command_prefix, "cargo")
    arguments: tuple[str, ...]
    if task == "check":
        arguments = (
            "check",
            "--quiet",
            "--no-default-features",
            "--manifest-path",
            str(generated_root / "rust" / "Cargo.toml"),
        )
    elif task == "release_build":
        arguments = (
            "build",
            "--quiet",
            "--release",
            "--no-default-features",
            "--manifest-path",
            str(generated_root / "rust" / "Cargo.toml"),
        )
    elif task == "rustdoc":
        arguments = (
            "doc",
            "--quiet",
            "--no-deps",
            "--no-default-features",
            "--manifest-path",
            str(generated_root / "rust" / "Cargo.toml"),
        )
    elif task == "downstream_consumer":
        arguments = (
            "build",
            "--quiet",
            "--manifest-path",
            str(consumer_manifest),
        )
    else:
        raise ValueError(f"unknown Rust measurement task: {task}")
    return (*cargo, *arguments, "--target-dir", str(target_root))


def _measure_rust(
    projects: Mapping[str, Path],
    *,
    work_root: Path,
    repetitions: int,
    msrv_rustup_home: Path,
) -> dict[str, Any]:
    candidates = (
        _rust_toolchain("msrv", "1.89.0", rustup_home=msrv_rustup_home),
        _rust_toolchain("stable", "stable"),
    )
    toolchains = tuple(item for item in candidates if item is not None)
    if not toolchains:
        raise MeasurementError("neither Rust 1.89.0 nor stable is available")
    skipped = tuple(
        label
        for label, candidate in zip(("msrv", "stable"), candidates, strict=True)
        if candidate is None
    )
    consumers = {
        revision: _write_consumer(
            work_root / "consumers" / revision,
            root,
        )
        for revision, root in projects.items()
    }
    samples: dict[tuple[str, str, str], list[TimingSample]] = {}
    target_root = work_root / "target"
    for toolchain in toolchains:
        for task in RUST_TASKS:
            for repetition in range(repetitions):
                order = tuple(projects)
                if repetition % 2:
                    order = tuple(reversed(order))
                for revision in order:
                    shutil.rmtree(target_root, ignore_errors=True)
                    command = _rust_command(
                        toolchain,
                        task,
                        generated_root=projects[revision],
                        consumer_manifest=consumers[revision],
                        target_root=target_root,
                    )
                    key = (revision, toolchain.label, task)
                    samples.setdefault(key, []).append(
                        _timed_command(
                            command,
                            cwd=work_root,
                            environment=toolchain.environment,
                            log_path=work_root / "rust-command.log",
                        )
                    )
    shutil.rmtree(target_root, ignore_errors=True)

    timings = []
    comparisons = []
    for key, values in sorted(samples.items()):
        revision, toolchain_label, task = key
        timings.append(
            {
                "revision": revision,
                "toolchain": toolchain_label,
                "task": task,
                **asdict(summarize_timings(values)),
            }
        )
    for toolchain in toolchains:
        for task in RUST_TASKS:
            baseline = summarize_timings(
                samples[("baseline", toolchain.label, task)]
            )
            candidate = summarize_timings(
                samples[("candidate", toolchain.label, task)]
            )
            comparisons.append(
                {
                    "toolchain": toolchain.label,
                    "task": task,
                    **asdict(compare_timings(baseline, candidate)),
                }
            )
    return {
        "tools": {
            toolchain.label: {
                "rustc_version": toolchain.rustc_version,
                "cargo_version": toolchain.cargo_version,
            }
            for toolchain in toolchains
        },
        "skipped_toolchains": skipped,
        "timings": timings,
        "comparisons": comparisons,
    }


def _format_seconds(value: object) -> str:
    if not isinstance(value, (int, float)):
        raise TypeError("timing value must be numeric")
    return f"{float(value):.3f}"


def _format_percent(value: object) -> str:
    if not isinstance(value, (int, float)):
        raise TypeError("percentage value must be numeric")
    return f"{float(value):+.1f}%"


def render_markdown(result: Mapping[str, Any]) -> str:
    provenance = result["provenance"]
    cpp = result["cpp"]
    rust = result["rust"]
    assert isinstance(provenance, Mapping)
    assert isinstance(cpp, Mapping)
    assert isinstance(rust, Mapping)
    lines = [
        "# TSL v1 support-file compile-cost evidence",
        "",
        f"Capture date: {provenance['captured_at_utc']}",
        "",
        "Status: final Slice 13 measurement; informational and non-gating",
        "",
        "## Scope and method",
        "",
        "The repository-local, non-networked measurement script is",
        "[`supplementary/benchmarks/measure_support_compile_cost.py`](../supplementary/benchmarks/measure_support_compile_cost.py).",
        "It compares the frozen Slice 0 scalar/AVX2 project with a freshly",
        "generated scalar/AVX2 project. Baseline and candidate clean builds are",
        "interleaved; every C++ object and Cargo target directory is removed",
        "before its sample. Wall and child CPU times are recorded for every",
        f"sample; tables report medians over {result['repetitions']} repetitions.",
        "Cargo is forced offline and incremental compilation is disabled.",
        "",
        "Absolute timings are not release gates: this host is not a stable",
        "runner and no cross-host noise band has been established. The observed",
        "spread is the larger within-revision min/max span for the paired run.",
        "A classification outside that spread is a review signal, not an",
        "automatic performance claim.",
        "",
        "## Provenance",
        "",
        f"- Baseline revision: `{provenance['baseline']['revision']}`",
        f"- Candidate revision: `{provenance['candidate']['revision']}`",
        f"- Baseline manifest SHA-256: `{provenance['baseline']['manifest_sha256']}`",
        f"- Candidate manifest SHA-256: `{provenance['candidate']['manifest_sha256']}`",
        f"- Host: `{provenance['host']['platform']}`; `{provenance['host']['machine']}`; {provenance['host']['cpu_count']} logical CPUs",
        f"- Python: `{provenance['host']['python']}`",
        "",
        "Tool versions:",
        "",
    ]
    cpp_tools = cpp["tools"]
    assert isinstance(cpp_tools, Mapping)
    for label, details in sorted(cpp_tools.items()):
        assert isinstance(details, Mapping)
        lines.append(f"- {label}: `{details['version']}`")
    rust_tools = rust["tools"]
    assert isinstance(rust_tools, Mapping)
    for label, details in sorted(rust_tools.items()):
        assert isinstance(details, Mapping)
        lines.append(
            f"- Rust {label}: `{details['rustc_version']}`; `{details['cargo_version']}`"
        )
    skipped = rust["skipped_toolchains"]
    if skipped:
        lines.append(f"- Unavailable Rust toolchains: `{', '.join(skipped)}`")

    lines.extend(
        [
            "",
            "## C++ preprocessing volume",
            "",
            "Each workload is a no-op translation unit. `core` includes",
            "`tsl_core.hpp`; `primitives` includes the selected profile header;",
            "`algorithms` adds `tsl_algorithm.hpp`. Bytes and lines are each",
            "compiler's `-E -P` output. Token records come from Clang's own",
            "`-dump-tokens` output; the script does not implement a C++ lexer.",
            "",
            "| Revision | Compiler | Profile | Workload | Preprocessed bytes | Lines | Clang token records |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    token_lookup = {
        (item["revision"], item["profile"], item["workload"]): item[
            "clang_token_records"
        ]
        for item in cpp["clang_token_records"]
    }
    for item in cpp["preprocessed_volume"]:
        token_count = token_lookup.get(
            (item["revision"], item["profile"], item["workload"]),
            "unavailable",
        )
        lines.append(
            f"| {item['revision']} | {item['compiler']} | {item['profile']} | "
            f"{item['workload']} | {item['bytes']} | {item['lines']} | "
            f"{token_count} |"
        )

    lines.extend(
        [
            "",
            "## C++ clean compile timing",
            "",
            "| Compiler | Profile | Workload | Baseline/final median wall (s) | Wall delta | Baseline/final median CPU (s) | CPU delta | Observed wall spread (s) | Classification |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for item in cpp["comparisons"]:
        lines.append(
            f"| {item['compiler']} | {item['profile']} | {item['workload']} | "
            f"{_format_seconds(item['baseline_wall_seconds'])} / "
            f"{_format_seconds(item['candidate_wall_seconds'])} | "
            f"{_format_percent(item['delta_percent'])} | "
            f"{_format_seconds(item['baseline_cpu_seconds'])} / "
            f"{_format_seconds(item['candidate_cpu_seconds'])} | "
            f"{_format_percent(item['cpu_delta_percent'])} | "
            f"{_format_seconds(item['observed_spread_seconds'])} | "
            f"{item['classification']} |"
        )

    lines.extend(
        [
            "",
            "## Rust clean build timing",
            "",
            "`check`, release build, Rustdoc, and a minimal path-dependent",
            "consumer each start from an empty target directory. The consumer",
            "imports one public error type; Cargo still compiles the generated",
            "library module graph, so this is packaging evidence rather than a",
            "claim about selective Rust imports.",
            "",
            "| Toolchain | Task | Baseline/final median wall (s) | Wall delta | Baseline/final median CPU (s) | CPU delta | Observed wall spread (s) | Classification |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for item in rust["comparisons"]:
        lines.append(
            f"| {item['toolchain']} | {item['task']} | "
            f"{_format_seconds(item['baseline_wall_seconds'])} / "
            f"{_format_seconds(item['candidate_wall_seconds'])} | "
            f"{_format_percent(item['delta_percent'])} | "
            f"{_format_seconds(item['baseline_cpu_seconds'])} / "
            f"{_format_seconds(item['candidate_cpu_seconds'])} | "
            f"{_format_percent(item['cpu_delta_percent'])} | "
            f"{_format_seconds(item['observed_spread_seconds'])} | "
            f"{item['classification']} |"
        )
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "From the repository root, retain or regenerate the Slice 0 project",
            "at the recorded baseline revision, then run:",
            "",
            "```bash",
            "python supplementary/benchmarks/measure_support_compile_cost.py \\",
            "  --baseline-root ./tslctmp/support-file-baseline-snapshot/generated \\",
            "  --markdown-output research/tsl-v1-support-file-compile-cost.md",
            "```",
            "",
            "The complete per-repetition JSON remains under",
            "`./tslctmp/support-file-compile-cost/results.json`; it is scratch",
            "evidence and is not committed. Regeneration replaces the measured",
            "tables; review the new signals and update the human conclusion",
            "before committing the report.",
            "",
        ]
    )
    return "\n".join(lines)


def _generate_candidate(repo_root: Path, candidate_root: Path) -> None:
    _require_scratch_path(candidate_root, repo_root)
    shutil.rmtree(candidate_root, ignore_errors=True)
    _run_checked(
        (
            str(repo_root / "dev.sh"),
            "generate",
            "--profiles",
            "scalar,avx2",
            "--backends",
            "cpp,rust",
            "--output-root",
            str(candidate_root),
        ),
        cwd=repo_root,
    )


def _revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def measure(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    baseline_root = args.baseline_root.resolve()
    candidate_root = args.candidate_root.resolve()
    work_root = args.work_root.resolve()
    json_output = args.json_output.resolve()
    _require_scratch_path(work_root, repo_root)
    _require_scratch_path(json_output, repo_root)
    if args.repetitions < 2:
        raise MeasurementError("at least two repetitions are required")
    if not args.skip_generate:
        _generate_candidate(repo_root, candidate_root)
    _validate_generated_project(baseline_root)
    _validate_generated_project(candidate_root)
    shutil.rmtree(work_root, ignore_errors=True)
    work_root.mkdir(parents=True)
    projects = {"baseline": baseline_root, "candidate": candidate_root}
    result: dict[str, Any] = {
        "schema_version": 1,
        "repetitions": args.repetitions,
        "provenance": {
            "captured_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "baseline": {
                "revision": args.baseline_revision,
                "root": _display_path(baseline_root, repo_root),
                "manifest_sha256": _sha256(baseline_root / ".tslc-manifest.json"),
            },
            "candidate": {
                "revision": args.candidate_revision or _revision(repo_root),
                "root": _display_path(candidate_root, repo_root),
                "manifest_sha256": _sha256(candidate_root / ".tslc-manifest.json"),
            },
            "host": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "cpu_count": os.cpu_count(),
                "python": platform.python_version(),
            },
        },
    }
    result["cpp"] = _measure_cpp(
        projects,
        work_root=work_root / "cpp",
        repetitions=args.repetitions,
    )
    result["rust"] = _measure_rust(
        projects,
        work_root=work_root / "rust",
        repetitions=args.repetitions,
        msrv_rustup_home=args.msrv_rustup_home,
    )
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_output is not None:
        markdown_output = args.markdown_output.resolve()
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--baseline-root",
        type=Path,
        default=REPO_ROOT / "tslctmp/support-file-baseline-snapshot/generated",
    )
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=REPO_ROOT / "tslctmp/support-file-compile-cost/generated",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=REPO_ROOT / "tslctmp/support-file-compile-cost/work",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=REPO_ROOT / "tslctmp/support-file-compile-cost/results.json",
    )
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--baseline-revision", default=BASELINE_REVISION)
    parser.add_argument("--candidate-revision")
    parser.add_argument(
        "--msrv-rustup-home",
        type=Path,
        default=REPO_ROOT / "tslctmp/rustup-slice11",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="measure an already generated candidate root",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        measure(args)
    except MeasurementError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
