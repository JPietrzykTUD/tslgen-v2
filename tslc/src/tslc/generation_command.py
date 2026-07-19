"""Generate/build/test command core: typed settings in, exit code out.

`cli.py` owns argparse construction, routing, and legacy flat-generation
compatibility; this module owns the command behavior so it can be driven
directly in tests without a parser or process exit.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tslc.diagnostics import format_diagnostic, has_errors
from tslc.output.verify_model import BackendToolchain, BuildVerificationReport
from tslc.output.writer import ArtifactWriteReport
from tslc.pipeline import GenerationResult

if TYPE_CHECKING:
    from tslc.output.summary import ProfileValueTestSummary


@dataclass(frozen=True, slots=True)
class GenerationCommandSettings:
    """Fully resolved generate/build/test options, independent of argparse."""

    sources: tuple[Path, ...]
    machine_profiles: Path
    type_tags: tuple[str, ...]
    backends: tuple[str, ...]
    generation_mode: str
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    output_root: str | Path | None
    verify: bool
    run_value_tests: bool
    fuzz: bool
    coverage: bool
    value_test_warnings: bool
    format_artifacts: bool
    summary_file: str | None
    toolchains: Mapping[str, BackendToolchain]
    runner_paths: Mapping[str, str]
    tool_paths: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class GenerationPipeline:
    """Pipeline seam: generation, artifact writing, and verification entry points."""

    generate: Callable[..., GenerationResult]
    write: Callable[..., ArtifactWriteReport]
    verify: Callable[..., BuildVerificationReport]


def run_generation_command(
    settings: GenerationCommandSettings,
    pipeline: GenerationPipeline,
) -> int:
    """Generate, write, optionally verify/test, and report; return the exit code."""
    if settings.run_value_tests and settings.output_root is None:
        print(
            "[error] --test requires --output-root so generated artifacts can "
            "be written before value-test verification",
            file=sys.stderr,
        )
        return 1

    generate_kwargs: dict[str, object] = {
        "machine_profiles_path": settings.machine_profiles,
        "type_tags": list(settings.type_tags),
        "backends": list(settings.backends),
        "generation_mode": settings.generation_mode,
        "test_harness": settings.run_value_tests,
        "value_test_warnings": settings.value_test_warnings or settings.run_value_tests,
        "value_test_fuzz": settings.fuzz,
    }
    if settings.profiles is not None:
        generate_kwargs["profiles"] = list(settings.profiles)
    if settings.primitives is not None:
        generate_kwargs["primitives"] = list(settings.primitives)

    result = pipeline.generate(settings.sources, **generate_kwargs)
    verify_report: BuildVerificationReport | None = None
    summary_written = False

    def write_summary_once() -> None:
        nonlocal summary_written
        if summary_written:
            return
        summary_written = True
        _write_summary_file(
            settings.summary_file, result, verify_report, settings.run_value_tests
        )

    for diagnostic in result.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)

    print(
        f"generated {len(result.coverage)} specializations across "
        f"{len(result.artifacts.artifacts)} artifacts"
    )

    if settings.coverage:
        from tslc.coverage import format_coverage_report

        print(format_coverage_report(result))

    if has_errors(result.diagnostics):
        write_summary_once()
        return 1

    if settings.output_root is not None:
        write_report = pipeline.write(result.artifacts, settings.output_root)
        for diagnostic in write_report.diagnostics:
            print(format_diagnostic(diagnostic), file=sys.stderr)
        if has_errors(write_report.diagnostics):
            write_summary_once()
            return 1
        print(f"wrote {len(write_report.written)} files under {write_report.output_root}")

        if settings.format_artifacts:
            from tslc.output.format import format_generated

            format_report = format_generated(settings.output_root, tuple(settings.backends))
            for note in format_report.notes:
                print(f"[format-skip] {note}", file=sys.stderr)
            if format_report.formatted:
                print(f"formatted {', '.join(format_report.formatted)}")

        if (settings.verify or settings.run_value_tests) and result.rendered is not None:
            if settings.run_value_tests:
                runners = _configured_runner_labels(settings.runner_paths)
                if runners:
                    print(
                        "building and running generated value tests through "
                        + ", ".join(runners)
                    )
                else:
                    print("building and running generated value tests")
            verify_report = pipeline.verify(
                settings.output_root,
                result.rendered.verify,
                toolchains=settings.toolchains,
                runner_paths=settings.runner_paths,
                tool_paths=settings.tool_paths,
                run_value_tests=settings.run_value_tests,
            )
            for note in verify_report.skipped:
                print(f"[verify-skip] {note}", file=sys.stderr)
            for diagnostic in verify_report.diagnostics:
                print(format_diagnostic(diagnostic), file=sys.stderr)
            if settings.run_value_tests:
                _print_test_output(verify_report)
            incomplete_value_tests = (
                _incomplete_value_test_profiles(result, verify_report)
                if settings.run_value_tests
                else ()
            )
            for profile in incomplete_value_tests:
                print(
                    "[verify-incomplete] "
                    f"{profile.backend_id} profile {profile.profile_name} "
                    f"{profile.failed_or_blocked_cases}/{profile.planned_cases} "
                    f"planned value-test cases {profile.status}",
                    file=sys.stderr,
                )
            write_summary_once()
            if has_errors(verify_report.diagnostics) or (
                settings.run_value_tests
                and (
                    verify_report.diagnostics
                    or verify_report.skipped
                    or incomplete_value_tests
                )
            ):
                return 1
            verified = "build/test-verified" if settings.run_value_tests else "build-verified"
            print(f"{verified} {len(verify_report.commands)} commands")

    write_summary_once()
    return 0


def _configured_runner_labels(runner_paths: Mapping[str, str]) -> list[str]:
    return [f"{kind}: {path}" for kind, path in sorted(runner_paths.items())]


def _print_test_output(report: BuildVerificationReport) -> None:
    for result in report.commands:
        if result.command.step != "test":
            continue
        command = result.command
        print(
            f"[test-output] {command.backend_id} {command.profile_name}: "
            f"{shlex.join(command.argv)}"
        )
        _print_captured_stream("stdout", result.stdout)
        _print_captured_stream("stderr", result.stderr)


def _print_captured_stream(label: str, text: str) -> None:
    stripped = text.strip()
    if stripped:
        print(f"[{label}]")
        print(stripped)


def _incomplete_value_test_profiles(
    result: GenerationResult,
    verify_report: BuildVerificationReport,
) -> tuple["ProfileValueTestSummary", ...]:
    if result.rendered is None:
        return ()
    test_plan = getattr(result.rendered, "value_tests", None)
    if test_plan is None:
        return ()
    from tslc.output.summary import value_test_profile_summaries

    return tuple(
        profile
        for profile in value_test_profile_summaries(
            test_plan,
            verify_report,
            run_value_tests=True,
        )
        if profile.planned_cases > 0 and profile.status != "passed"
    )


def _write_summary_file(
    summary_file: str | None,
    result: GenerationResult,
    verify_report: BuildVerificationReport | None,
    run_value_tests: bool,
) -> None:
    if summary_file is None:
        return
    from tslc.output.summary import (
        append_markdown_summary,
        render_value_test_markdown_summary,
    )

    test_plan = result.rendered.value_tests if result.rendered is not None else None
    append_markdown_summary(
        summary_file,
        render_value_test_markdown_summary(
            test_plan,
            verify_report,
            run_value_tests=run_value_tests,
        ),
    )
    print(f"wrote Markdown summary to {summary_file}")
