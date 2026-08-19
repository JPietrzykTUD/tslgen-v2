"""Backend-aware toolchain and runner diagnostics."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import replace
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any

from tslc._cli_options import merge_toolchains, parse_assignments, split_csv
from tslc.authoring import check_catalog
from tslc.backend.registry import backend_capabilities
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.output.verify import run_subprocess_build_command
from tslc.output.verify_model import (
    BackendToolchain,
    BuildCommandRunner,
    BuildVerifierConfig,
    ToolchainCommands,
    VerifyBackend,
    VerifyProfile,
)
from tslc.project_config import ProjectConfig, load_project_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc doctor",
        description="Probe configured backend toolchains, targets, formatters, and runners.",
    )
    parser.add_argument("--config", help="path to tslc.toml (discovered by default)")
    parser.add_argument("--sources", nargs="+", help="complete corpus roots")
    parser.add_argument("--machine-profiles", help="path to machine_profiles.json")
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--profiles", help="comma-separated profile names")
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--backends", help="comma-separated backend names")
    parser.add_argument("--compiler", action="append", default=[], metavar="BACKEND=COMMAND")
    parser.add_argument("--target", action="append", default=[], metavar="BACKEND=TRIPLE")
    parser.add_argument("--linker", action="append", default=[], metavar="BACKEND=EXECUTABLE")
    parser.add_argument("--runner", action="append", default=[], metavar="KIND=EXECUTABLE")
    parser.add_argument("--run", action="store_true", help="require selected profiles to be runnable")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--work-root", default=None, help="compiler-preflight scratch root")
    args = parser.parse_args(argv)
    try:
        config = load_project_config(args.config)
        settings = _settings(args, config)
    except ValueError as exc:
        parser.error(str(exc))
    report = diagnose(
        sources=settings.sources,
        machine_profiles=settings.machine_profiles,
        backends=settings.backends,
        profiles=tuple(args.profile) or (split_csv(args.profiles) if args.profiles else None),
        work_root=settings.work_root,
        toolchains=settings.toolchains,
        runner_paths=settings.runner_paths,
        tool_paths=settings.tool_paths,
        run_value_tests=args.run,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_text(report))
    failed = any(
        not profile["build_ready"] or (args.run and not profile["run_ready"])
        for backend in report["backends"]
        for profile in backend["profiles"]
    )
    return 1 if report["diagnostics"] or failed else 0


class _Settings:
    def __init__(
        self,
        *,
        sources: tuple[Path, ...],
        machine_profiles: Path,
        backends: tuple[str, ...],
        work_root: Path,
        toolchains: Mapping[str, BackendToolchain],
        runner_paths: Mapping[str, str],
        tool_paths: Mapping[str, str],
    ) -> None:
        self.sources = sources
        self.machine_profiles = machine_profiles
        self.backends = backends
        self.work_root = work_root
        self.toolchains = toolchains
        self.runner_paths = runner_paths
        self.tool_paths = tool_paths


def _settings(args: argparse.Namespace, project: ProjectConfig | None) -> _Settings:
    sources = (
        tuple(Path(value) for value in args.sources)
        if args.sources
        else project.sources
        if project is not None
        else ()
    )
    profiles = (
        Path(args.machine_profiles)
        if args.machine_profiles
        else project.machine_profiles
        if project is not None
        else None
    )
    if not sources or profiles is None:
        raise ValueError(
            "doctor requires sources and machine profiles; configure tslc.toml or pass both"
        )
    backends = tuple(args.backend) or (
        split_csv(args.backends)
        if args.backends
        else project.backends
        if project is not None
        else ("cpp", "rust")
    )
    base_toolchains = merge_toolchains(
        project.toolchains if project is not None else {},
        parse_assignments(args.compiler, "--compiler"),
        parse_assignments(args.target, "--target"),
        parse_assignments(args.linker, "--linker"),
    )
    runners = dict(project.runner_paths) if project is not None else {}
    runners.update(parse_assignments(args.runner, "--runner"))
    tools = dict(project.tool_paths) if project is not None else {}
    if args.work_root:
        work_root = Path(args.work_root)
    elif project is not None:
        work_root = project.path.parent / "tslctmp" / "doctor"
    else:
        work_root = Path("tslctmp/doctor")
    return _Settings(
        sources=sources,
        machine_profiles=profiles,
        backends=backends,
        work_root=work_root,
        toolchains=base_toolchains,
        runner_paths=runners,
        tool_paths=tools,
    )


def diagnose(
    *,
    sources: tuple[Path, ...],
    machine_profiles: Path,
    backends: tuple[str, ...],
    profiles: tuple[str, ...] | None,
    work_root: Path,
    toolchains: Mapping[str, BackendToolchain] | None = None,
    runner_paths: Mapping[str, str] | None = None,
    tool_paths: Mapping[str, str] | None = None,
    runner: BuildCommandRunner = run_subprocess_build_command,
    run_value_tests: bool = False,
) -> dict[str, Any]:
    checked = check_catalog(sources, backends=backends)
    diagnostics = [f"{item.code}: {item.message}" for item in checked.diagnostics]
    if checked.catalog is None or has_errors(checked.diagnostics):
        return {"status": "error", "diagnostics": diagnostics, "backends": []}
    loaded = load_machine_profiles_checked(
        machine_profiles, checked.catalog.target_families
    )
    diagnostics.extend(f"{item.code}: {item.message}" for item in loaded.diagnostics)
    if has_errors(loaded.diagnostics):
        return {"status": "error", "diagnostics": diagnostics, "backends": []}
    selected_names = profiles or tuple(sorted(loaded.profiles))
    unknown = sorted(set(selected_names) - set(loaded.profiles))
    if unknown:
        diagnostics.append(f"unknown machine profile(s): {', '.join(unknown)}")
    machine_profiles_by_name = [
        loaded.profiles[name] for name in selected_names if name in loaded.profiles
    ]
    config = BuildVerifierConfig.create(
        toolchains=toolchains,
        runner_paths=runner_paths,
        tool_paths=tool_paths,
        run_value_tests=run_value_tests,
    )
    backend_reports: list[dict[str, Any]] = []
    work_root.mkdir(parents=True, exist_ok=True)
    for capability in backend_capabilities(backends):
        verify_profiles = tuple(
            replace(
                projected,
                preflight_headers=_profile_preflight_headers(
                    checked.catalog, profile, capability.backend_id
                ),
            )
            for profile in machine_profiles_by_name
            if profile.supports_backend(capability.backend_id)
            if (
                projected := capability.verify_machine_profile(
                    profile,
                    checked.catalog.target_families.profile_family(profile.family),
                )
            )
            is not None
        )
        backend = VerifyBackend(
            backend_id=capability.backend_id,
            root_path=capability.root_path,
            profiles=verify_profiles,
        )
        driver = capability.verify_driver()
        missing_tools = [tool for tool in driver.required_tools if shutil.which(tool) is None]
        prep = driver.prepare_backend(work_root, backend, config, runner)
        command_results = list(prep.commands)
        preflight_diagnostics = list(prep.diagnostics)
        skipped = list(prep.skipped)
        prepared = prep.backend
        prepared_profiles = (
            {item.profile_name: item for item in prepared.profiles}
            if prepared is not None
            else {}
        )
        profile_reports = [
            _profile_report(
                item,
                capability.toolchain_commands(
                    prepared_profiles.get(item.profile_name, item),
                    config,
                ),
                config,
                prepared=item.profile_name in prepared_profiles,
                missing_backend_tools=missing_tools,
                skipped=skipped,
            )
            for item in verify_profiles
        ]
        formatter = capability.generated_format
        backend_reports.append(
            {
                "id": capability.backend_id,
                "required_tools": [
                    _tool(tool) for tool in driver.required_tools
                ],
                "formatter": None if formatter is None else _tool(formatter.executable),
                "profiles": profile_reports,
                "preflight_commands": [
                    {
                        "profile": item.command.profile_name,
                        "argv": list(item.command.argv),
                        "returncode": item.returncode,
                    }
                    for item in command_results
                ],
                "preflight_skips": skipped,
                "diagnostics": [
                    f"{item.code}: {item.message}" for item in preflight_diagnostics
                ],
            }
        )
    build_failed = any(
        not profile["build_ready"]
        for backend in backend_reports
        for profile in backend["profiles"]
    )
    return {
        "status": "error" if diagnostics or build_failed else "ok",
        "work_root": str(work_root.resolve()),
        "diagnostics": diagnostics,
        "backends": backend_reports,
    }


def _profile_preflight_headers(
    catalog: Catalog,
    profile: MachineProfile,
    backend_id: str,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                header
                for extension in catalog.extensions.values()
                if extension.supports_backend(backend_id)
                if extension.family not in (
                    catalog.target_families.universal_extension_families
                )
                if catalog.target_families.extension_targets_profile(
                    extension.family, profile.family
                )
                for header in extension.headers_for_backend(backend_id)
            }
        )
    )


def _profile_report(
    profile: VerifyProfile,
    commands: ToolchainCommands,
    config: BuildVerifierConfig,
    *,
    prepared: bool,
    missing_backend_tools: list[str],
    skipped: list[str],
) -> dict[str, Any]:
    compiler = commands.compiler
    target = commands.target
    linker = commands.linker
    compiler_tool = _tool(compiler[0], compiler)
    missing = [f"{tool} not found" for tool in missing_backend_tools]
    if not compiler_tool["available"]:
        missing.append(f"compiler {compiler[0]} not found")
    if not prepared:
        relevant = [
            message
            for message in skipped
            if f"profile {profile.profile_name}" in message
            or "preflight failed" in message
            or "compiler" in message
        ]
        missing.extend(relevant or ["compiler/target preflight did not pass"])
    build_ready = prepared and not missing_backend_tools
    runner = profile.runner
    native = profile.native_without_runner
    runner_tool: dict[str, Any] | None = None
    if runner is not None:
        path = config.runner_path(runner.kind)
        runner_tool = {
            "kind": runner.kind,
            "profile": runner.profile,
            "configured": path,
            "tool": None if path is None else _tool(path),
        }
        if path is None:
            missing.append(f"runner {runner.kind} is not configured")
        elif runner_tool["tool"] is not None and not runner_tool["tool"]["available"]:
            missing.append(f"runner {runner.kind} executable {path} not found")
    elif not native:
        missing.append("profile has no native-run or runner capability")
    run_capable = native or bool(
        runner_tool is not None
        and runner_tool["tool"] is not None
        and runner_tool["tool"]["available"]
    )
    return {
        "name": profile.profile_name,
        "family": profile.family,
        "compiler": compiler_tool,
        "target": target,
        "linker": None if linker is None else _tool(linker),
        "runner": runner_tool,
        "native_run": native,
        "build_ready": build_ready,
        "run_ready": build_ready and run_capable,
        "missing": list(dict.fromkeys(missing)),
    }


def _tool(executable: str, command: tuple[str, ...] | None = None) -> dict[str, object]:
    resolved = shutil.which(executable)
    available = resolved is not None
    return {
        "command": shlex.join(command or (executable,)),
        "path": resolved,
        "available": available,
        "version": _version(command or (executable,)) if available else None,
    }


def _version(command: tuple[str, ...]) -> str | None:
    try:
        completed = subprocess.run(
            (*command, "--version"),
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = completed.stdout.strip() or completed.stderr.strip()
    return text.splitlines()[0] if text else None


def _format_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    for diagnostic in report["diagnostics"]:
        lines.append(f"error: {diagnostic}")
    for backend in report["backends"]:
        lines.append(f"{backend['id']}:")
        for tool in backend["required_tools"]:
            lines.append(_tool_line("build tool", tool))
        if backend["formatter"] is not None:
            lines.append(_tool_line("formatter", backend["formatter"]))
        for profile in backend["profiles"]:
            state = "build-ready" if profile["build_ready"] else "cannot build"
            run = "native" if profile["native_run"] else "runner-ready" if profile["run_ready"] else "cannot run"
            lines.append(f"  {profile['name']}: {state}; {run}")
            lines.append(_tool_line("compiler", profile["compiler"], indent="    "))
            lines.append(f"    target: {profile['target'] or 'native'}")
            if profile["linker"] is not None:
                lines.append(_tool_line("linker", profile["linker"], indent="    "))
            if profile["runner"] is not None:
                runner = profile["runner"]
                if runner["tool"] is None:
                    lines.append(f"    runner: {runner['kind']} (not configured)")
                else:
                    lines.append(_tool_line(f"runner {runner['kind']}", runner["tool"], indent="    "))
            for missing in profile["missing"]:
                lines.append(f"    missing: {missing}")
    return "\n".join(lines) if lines else "no profiles selected"


def _tool_line(label: str, tool: dict[str, object], *, indent: str = "  ") -> str:
    if not tool["available"]:
        return f"{indent}{label}: {tool['command']} (not found)"
    version = f" — {tool['version']}" if tool["version"] else ""
    return f"{indent}{label}: {tool['command']} ({tool['path']}){version}"


if __name__ == "__main__":
    raise SystemExit(main())
