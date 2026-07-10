"""Thin CLI: parse options, run the pipeline, write, optionally verify, exit."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors
from tslc.output.verify import BuildVerificationReport
from tslc.output.verify_model import BackendToolchain
from tslc.pipeline import GenerationResult

if TYPE_CHECKING:
    from tslc.output.summary import ProfileValueTestSummary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tslc", description="Compile TSL data to C++/Rust.")
    parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="explicit .tsl source paths or directories (dirs load all .tsl beneath them)",
    )
    parser.add_argument(
        "--machine-profiles",
        required=True,
        help="path to machine_profiles.json",
    )
    parser.add_argument(
        "--primitives",
        default=None,
        help="comma-separated primitive names; omit to generate every catalog primitive",
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help=(
            "comma-separated machine profile names; omit to generate every "
            "loaded machine profile"
        ),
    )
    parser.add_argument(
        "--types",
        default="si8,si16,si32,si64,ui8,ui16,ui32,ui64,f32,f64",
        help="comma-separated type tags",
    )
    parser.add_argument("--backends", default="cpp,rust", help="comma-separated backends")
    parser.add_argument(
        "--generation-mode",
        choices=("partial", "strict"),
        default="partial",
        help="partial records unsupported selected slots as coverage skips; strict fails on them",
    )
    parser.add_argument("--output-root", default=None, help="write artifacts under this root")
    parser.add_argument("--verify", action="store_true", help="build-verify after writing")
    parser.add_argument(
        "--test",
        action="store_true",
        help="build and run generated value tests (implies --verify)",
    )
    parser.add_argument(
        "--fuzz",
        action="store_true",
        help="emit and run differential-fuzz value tests (hardware vs the generic scalar "
        "reference over random inputs); implies --test",
    )
    parser.add_argument(
        "--compiler",
        action="append",
        default=[],
        metavar="BACKEND=COMMAND",
        help="backend compiler command override; repeat for multiple backends",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="BACKEND=TRIPLE",
        help="backend target triple override; repeat for multiple backends",
    )
    parser.add_argument(
        "--linker",
        action="append",
        default=[],
        metavar="BACKEND=EXECUTABLE",
        help="backend linker override; repeat for multiple backends",
    )
    parser.add_argument(
        "--runner",
        action="append",
        default=[],
        metavar="KIND=EXECUTABLE",
        help="value-test runner path; repeat for multiple runner kinds",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="print a behavior-coverage report"
    )
    parser.add_argument(
        "--value-test-warnings",
        action="store_true",
        help="warn when authored value-test cases cannot be planned for a backend/profile",
    )
    parser.add_argument(
        "--format",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run clang-format/rustfmt over the written artifacts (best-effort; "
        "skipped if the formatter is unavailable). Use --no-format to disable.",
    )
    parser.add_argument(
        "--summary-file",
        default=None,
        help="append a Markdown generation/verification summary to this path",
    )
    args = parser.parse_args(argv)
    try:
        toolchains = _toolchain_overrides(
            _assignments(args.compiler, "--compiler"),
            _assignments(args.target, "--target"),
            _assignments(args.linker, "--linker"),
        )
        runner_paths = _assignments(args.runner, "--runner")
    except ValueError as exc:
        parser.error(str(exc))

    # Fuzzing only matters once the value tests are built and run, and it needs the test harness
    # (round-trip primitives) pulled into the closure — so --fuzz implies --test.
    if args.fuzz:
        args.test = True

    if args.test and args.output_root is None:
        print(
            "[error] --test requires --output-root so generated artifacts can "
            "be written before value-test verification",
            file=sys.stderr,
        )
        return 1

    generate_kwargs = {
        "machine_profiles_path": args.machine_profiles,
        "type_tags": _split(args.types),
        "backends": _split(args.backends),
        "generation_mode": args.generation_mode,
        "test_harness": args.test,
        "value_test_warnings": args.value_test_warnings or args.test,
        "value_test_fuzz": args.fuzz,
    }
    if args.profiles is not None:
        generate_kwargs["profiles"] = _split(args.profiles)
    if args.primitives is not None:
        generate_kwargs["primitives"] = _split(args.primitives)

    result = generate_project(
        [Path(path) for path in args.sources],
        **generate_kwargs,
    )
    verify_report: BuildVerificationReport | None = None
    summary_written = False

    def write_summary_once() -> None:
        nonlocal summary_written
        if summary_written:
            return
        summary_written = True
        _write_summary_file(args.summary_file, result, verify_report, args.test)

    for diagnostic in result.diagnostics:
        location = f" {diagnostic.location.path}:{diagnostic.location.line}" if diagnostic.location else ""
        print(f"[{diagnostic.severity}] {diagnostic.code}{location}: {diagnostic.message}", file=sys.stderr)

    print(
        f"generated {len(result.coverage)} specializations across "
        f"{len(result.artifacts.artifacts)} artifacts"
    )

    if args.coverage:
        from tslc.coverage import format_coverage_report

        print(format_coverage_report(result))

    if has_errors(result.diagnostics):
        write_summary_once()
        return 1

    if args.output_root is not None:
        write_report = write_artifacts(result.artifacts, args.output_root)
        for diagnostic in write_report.diagnostics:
            print(f"[write] {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
        if has_errors(write_report.diagnostics):
            write_summary_once()
            return 1
        print(f"wrote {len(write_report.written)} files under {write_report.output_root}")

        if args.format:
            from tslc.output.format import format_generated

            format_report = format_generated(args.output_root, tuple(_split(args.backends)))
            for note in format_report.notes:
                print(f"[format-skip] {note}", file=sys.stderr)
            if format_report.formatted:
                print(f"formatted {', '.join(format_report.formatted)}")

        if (args.verify or args.test) and result.rendered is not None:
            if args.test:
                runners = _configured_runner_labels(runner_paths)
                if runners:
                    print(
                        "building and running generated value tests through "
                        + ", ".join(runners)
                    )
                else:
                    print("building and running generated value tests")
            verify_report = verify_project(
                args.output_root,
                result.rendered.verify,
                toolchains=toolchains,
                runner_paths=runner_paths,
                run_value_tests=args.test,
            )
            for note in verify_report.skipped:
                print(f"[verify-skip] {note}", file=sys.stderr)
            for diagnostic in verify_report.diagnostics:
                print(f"[verify] {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
            if args.test:
                _print_test_output(verify_report)
            incomplete_value_tests = (
                _incomplete_value_test_profiles(result, verify_report)
                if args.test
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
                args.test
                and (
                    verify_report.diagnostics
                    or verify_report.skipped
                    or incomplete_value_tests
                )
            ):
                return 1
            verified = "build/test-verified" if args.test else "build-verified"
            print(f"{verified} {len(verify_report.commands)} commands")

    write_summary_once()
    return 0


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _assignments(values: list[str], option: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for value in values:
        key, separator, setting = value.partition("=")
        key = key.strip()
        setting = setting.strip()
        if not separator or not key or not setting:
            raise ValueError(f"{option} expects NAME=VALUE, got {value!r}")
        if key in assignments:
            raise ValueError(f"{option} repeats name {key!r}")
        assignments[key] = setting
    return assignments


def _toolchain_overrides(
    compilers: dict[str, str],
    targets: dict[str, str],
    linkers: dict[str, str],
) -> dict[str, BackendToolchain]:
    return {
        backend_id: BackendToolchain.create(
            compiler=compilers.get(backend_id),
            target=targets.get(backend_id),
            linker=linkers.get(backend_id),
        )
        for backend_id in sorted(compilers.keys() | targets.keys() | linkers.keys())
    }


def _configured_runner_labels(runner_paths: dict[str, str]) -> list[str]:
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


if __name__ == "__main__":
    raise SystemExit(main())
