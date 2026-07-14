"""Thin CLI: parse options, run the pipeline, write, optionally verify, exit."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors
from tslc.output.verify import BuildVerificationReport
from tslc.output.verify_model import BackendToolchain
from tslc.pipeline import GenerationResult
from tslc.project_config import ProjectConfig, load_project_config

if TYPE_CHECKING:
    from tslc.output.summary import ProfileValueTestSummary


_COMMANDS = (
    "generate",
    "check",
    "build",
    "test",
    "explain",
    "inspect",
    "list",
    "show",
    "audit",
    "coverage",
    "doctor",
)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Preserve the original flat generation surface for scripts that already use it.
    if arguments and arguments[0].startswith("-") and arguments[0] not in ("-h", "--help"):
        return _generation_main(arguments, use_project_config=False)
    if not arguments or arguments[0] in ("-h", "--help"):
        _root_parser().parse_args(arguments)
        return 0
    command, rest = arguments[0], arguments[1:]
    if command == "generate":
        return _generation_main(rest, use_project_config=True, command="generate")
    if command == "build":
        return _generation_main(rest, use_project_config=True, command="build")
    if command == "test":
        return _generation_main(rest, use_project_config=True, command="test")
    if command == "check":
        from tslc.check_cli import main as check_main

        return check_main(rest)
    if command in ("list", "show"):
        from tslc.catalog_cli import main as catalog_main

        return catalog_main(_catalog_arguments(command, rest))
    if command == "doctor":
        from tslc.doctor import main as doctor_main

        return doctor_main(rest)
    if command == "explain":
        from tslc.maintenance.explain import main as explain_main

        return _run_configured_maintenance(explain_main, rest)
    if command == "inspect":
        from tslc.maintenance.stage_dump import main as inspect_main

        return _run_configured_maintenance(inspect_main, rest)
    if command == "audit":
        return _maintenance_group("audit", rest)
    if command == "coverage":
        return _maintenance_group("coverage", rest)
    parser = _root_parser()
    parser.error(f"unknown command {command!r}")


def _root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tslc",
        description="Validate, inspect, compile, and verify TSL source data.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    descriptions = {
        "generate": "render configured generated projects",
        "check": "validate the corpus without rendering",
        "build": "generate and build-verify",
        "test": "generate, build, and run value tests",
        "explain": "explain one selection/lowering slot",
        "inspect": "dump a compiler pipeline stage",
        "list": "list catalog entries",
        "show": "describe one catalog entry",
        "audit": "run source metadata audits",
        "coverage": "run coverage maintenance tools",
        "doctor": "probe configured toolchains and runners",
    }
    for name in _COMMANDS:
        subparsers.add_parser(name, help=descriptions[name], add_help=False)
    return parser


def _generation_main(
    argv: list[str],
    *,
    use_project_config: bool,
    command: str = "generate",
) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc" if not use_project_config else f"tslc {command}",
        description="Compile TSL data to C++/Rust.",
    )
    if use_project_config:
        parser.add_argument("--config", help="path to tslc.toml (discovered by default)")
    parser.add_argument(
        "--sources",
        nargs="+",
        required=not use_project_config,
        help="explicit .tsl source paths or directories (dirs load all .tsl beneath them)",
    )
    parser.add_argument(
        "--machine-profiles",
        required=not use_project_config,
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
    parser.add_argument(
        "--backends",
        default=None if use_project_config else "cpp,rust",
        help="comma-separated backends",
    )
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
        project = (
            load_project_config(args.config) if use_project_config else None
        )
        sources, machine_profiles, configured_backends, output_root = (
            _generation_settings(args, project, command)
        )
        toolchains = _merge_toolchains(
            project.toolchains if project is not None else {},
            _assignments(args.compiler, "--compiler"),
            _assignments(args.target, "--target"),
            _assignments(args.linker, "--linker"),
        )
        runner_paths = dict(project.runner_paths) if project is not None else {}
        runner_paths.update(_assignments(args.runner, "--runner"))
    except ValueError as exc:
        parser.error(str(exc))

    if command == "build":
        args.verify = True
    elif command == "test":
        args.test = True
    args.output_root = output_root

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
        "machine_profiles_path": machine_profiles,
        "type_tags": _split(args.types),
        "backends": configured_backends,
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
        sources,
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

            format_report = format_generated(args.output_root, tuple(configured_backends))
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


def _merge_toolchains(
    configured: Mapping[str, BackendToolchain],
    compilers: dict[str, str],
    targets: dict[str, str],
    linkers: dict[str, str],
) -> dict[str, BackendToolchain]:
    base = dict(configured)
    for backend_id in sorted(compilers.keys() | targets.keys() | linkers.keys()):
        previous = base.get(backend_id, BackendToolchain())
        base[backend_id] = BackendToolchain.create(
            compiler=compilers.get(backend_id) or previous.compiler,
            target=targets.get(backend_id) or previous.target,
            linker=linkers.get(backend_id) or previous.linker,
        )
    return base


def _generation_settings(
    args: argparse.Namespace,
    project: ProjectConfig | None,
    command: str,
) -> tuple[tuple[Path, ...], Path, list[str], str | Path | None]:
    sources = (
        tuple(Path(path) for path in args.sources)
        if args.sources
        else project.sources
        if project is not None
        else ()
    )
    machine_profiles = (
        Path(args.machine_profiles)
        if args.machine_profiles
        else project.machine_profiles
        if project is not None
        else None
    )
    if not sources or machine_profiles is None:
        raise ValueError(
            "sources and machine profiles are not configured; pass --sources and "
            "--machine-profiles or create tslc.toml"
        )
    backends = (
        _split(args.backends)
        if args.backends is not None
        else list(project.backends)
        if project is not None
        else ["cpp", "rust"]
    )
    output_root: str | Path | None = (
        args.output_root
        if args.output_root is not None
        else project.output_root
        if project is not None
        else None
    )
    if command in ("build", "test") and output_root is None:
        raise ValueError(
            f"tslc {command} requires --output-root or tslc.output_root in tslc.toml"
        )
    return sources, machine_profiles, backends, output_root


def _catalog_arguments(command: str, arguments: list[str]) -> list[str]:
    return [command, *arguments]


def _configured_maintenance_arguments(arguments: list[str]) -> list[str]:
    if "-h" in arguments or "--help" in arguments:
        return arguments
    values = list(arguments)
    config_path: str | None = None
    if "--config" in values:
        index = values.index("--config")
        if index + 1 >= len(values):
            raise ValueError("--config expects a path")
        config_path = values[index + 1]
        del values[index : index + 2]
    try:
        project = load_project_config(config_path)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if project is None:
        return values
    if "--sources" not in values:
        if len(project.sources) != 1:
            raise ValueError(
                "this inspector accepts one --sources root; pass it explicitly"
            )
        values.extend(("--sources", str(project.sources[0])))
    if "--machine-profiles" not in values:
        values.extend(("--machine-profiles", str(project.machine_profiles)))
    return values


def _run_configured_maintenance(
    command: Callable[[list[str] | None], int],
    arguments: list[str],
) -> int:
    try:
        configured = _configured_maintenance_arguments(arguments)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return command(configured)


def _maintenance_group(group: str, arguments: list[str]) -> int:
    if not arguments or arguments[0] in ("-h", "--help"):
        choices = "metadata" if group == "audit" else "ratchet, inventory"
        print(f"usage: tslc {group} {{{choices.replace(', ', ',')}}} [options]")
        return 0
    action, rest = arguments[0], arguments[1:]
    if group == "audit" and action == "metadata":
        from tslc.maintenance.metadata_audit import main as metadata_main

        return _run_configured_maintenance(metadata_main, rest)
    if group == "coverage" and action == "ratchet":
        from tslc.maintenance.coverage_ratchet import main as ratchet_main

        return _run_configured_maintenance(ratchet_main, rest)
    if group == "coverage" and action == "inventory":
        from tslc.maintenance.coverage_inventory import main as inventory_main

        return inventory_main(rest)
    print(f"unknown tslc {group} command {action!r}", file=sys.stderr)
    return 2


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
