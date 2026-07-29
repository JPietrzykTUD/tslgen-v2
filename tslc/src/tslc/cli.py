"""Thin CLI: route installed commands, keep legacy flat generation, own process exit."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from tslc._cli_options import merge_toolchains, parse_assignments, split_csv
from tslc.api import generate_project, verify_project, write_artifacts
from tslc.backend.rust_package import DEFAULT_RUST_PACKAGE_CONFIG
from tslc.generation_command import (
    GenerationCommandSettings,
    GenerationPipeline,
    run_generation_command,
)
from tslc.project_config import ProjectConfig, load_project_config
from tslc.version import package_version

_COMMANDS = (
    "generate",
    "check",
    "build",
    "test",
    "explain",
    "preview",
    "analyze",
    "inspect",
    "list",
    "show",
    "audit",
    "coverage",
    "doctor",
    "lsp",
)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Preserve the original flat generation surface for scripts that already use it.
    if arguments and arguments[0].startswith("-") and arguments[0] not in (
        "-h",
        "--help",
        "--version",
    ):
        return _generation_main(arguments, use_project_config=False)
    if not arguments or arguments[0] in ("-h", "--help", "--version"):
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
    if command == "lsp":
        from tslc.lsp_cli import main as lsp_main

        return lsp_main(rest)
    if command == "explain":
        from tslc.maintenance.explain import main as explain_main

        return _run_configured_maintenance(explain_main, rest)
    if command == "preview":
        from tslc.maintenance.render_preview import main as preview_main

        return _run_configured_maintenance(preview_main, rest)
    if command == "analyze":
        from tslc.maintenance.analyze_specialization import main as analyze_main

        return _run_configured_maintenance(analyze_main, rest)
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    descriptions = {
        "generate": "render configured generated projects",
        "check": "validate the corpus without rendering",
        "build": "generate and build-verify",
        "test": "generate, build, and run value tests",
        "explain": "explain one selection/lowering slot",
        "preview": "render one specialization fragment",
        "analyze": "analyze one specialization and its active call closure",
        "inspect": "dump a compiler pipeline stage",
        "list": "list catalog entries",
        "show": "describe one catalog entry",
        "audit": "run source metadata audits",
        "coverage": "run coverage maintenance tools",
        "doctor": "probe configured toolchains and runners",
        "lsp": "run the editor-neutral language server",
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
    parser = _generation_parser(use_project_config=use_project_config, command=command)
    args = parser.parse_args(argv)
    try:
        project = (
            load_project_config(args.config) if use_project_config else None
        )
        settings = _generation_command_settings(args, project, command)
    except ValueError as exc:
        parser.error(str(exc))
    pipeline = GenerationPipeline(
        generate=generate_project,
        write=write_artifacts,
        verify=verify_project,
    )
    return run_generation_command(settings, pipeline)


def _generation_parser(
    *,
    use_project_config: bool,
    command: str,
) -> argparse.ArgumentParser:
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
        "--backend-profiles",
        action="append",
        default=[],
        metavar="BACKEND=PROFILE,...",
        help=(
            "restrict one backend to a comma-separated subset of the requested "
            "machine profiles; repeat for multiple backends"
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
    return parser


def _generation_command_settings(
    args: argparse.Namespace,
    project: ProjectConfig | None,
    command: str,
) -> GenerationCommandSettings:
    sources, machine_profiles, backends, output_root = _generation_settings(
        args, project, command
    )
    toolchains = merge_toolchains(
        project.toolchains if project is not None else {},
        parse_assignments(args.compiler, "--compiler"),
        parse_assignments(args.target, "--target"),
        parse_assignments(args.linker, "--linker"),
    )
    backend_profiles = {
        backend_id: split_csv(value)
        for backend_id, value in parse_assignments(
            args.backend_profiles, "--backend-profiles"
        ).items()
    }
    if any(not profiles for profiles in backend_profiles.values()):
        raise ValueError("--backend-profiles requires at least one profile per backend")
    runner_paths = dict(project.runner_paths) if project is not None else {}
    runner_paths.update(parse_assignments(args.runner, "--runner"))
    tool_paths = dict(project.tool_paths) if project is not None else {}
    # `tslc build` implies verification; `tslc test` and --fuzz imply value tests
    # (fuzzing needs the test harness pulled into the closure to run at all).
    return GenerationCommandSettings(
        sources=sources,
        machine_profiles=machine_profiles,
        type_tags=split_csv(args.types),
        backends=tuple(backends),
        generation_mode=args.generation_mode,
        primitives=split_csv(args.primitives) if args.primitives is not None else None,
        profiles=split_csv(args.profiles) if args.profiles is not None else None,
        backend_profiles=backend_profiles,
        output_root=output_root,
        verify=args.verify or command == "build",
        run_value_tests=args.test or command == "test" or args.fuzz,
        fuzz=args.fuzz,
        coverage=args.coverage,
        value_test_warnings=args.value_test_warnings,
        format_artifacts=args.format,
        summary_file=args.summary_file,
        toolchains=toolchains,
        runner_paths=runner_paths,
        tool_paths=tool_paths,
        rust_package=(
            project.rust_package
            if project is not None
            else DEFAULT_RUST_PACKAGE_CONFIG
        ),
    )


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
        list(split_csv(args.backends))
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


if __name__ == "__main__":
    raise SystemExit(main())
