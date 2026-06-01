"""After-write build verification for generated project skeletons."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Protocol

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.generated_project import (
    BackendProjectRenderModel,
    GeneratedProjectRenderModel,
)


@dataclass(frozen=True, slots=True)
class BuildCommand:
    backend_id: str
    profile_name: str
    step: str
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True, slots=True)
class BuildCommandResult:
    command: BuildCommand
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class BuildVerificationReport:
    commands: tuple[BuildCommandResult, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BuildVerificationPolicy:
    cxx_compiler: str | None = None


class BuildCommandRunner(Protocol):
    def __call__(self, command: BuildCommand) -> BuildCommandResult:
        """Run one build-verification command."""


def run_subprocess_build_command(command: BuildCommand) -> BuildCommandResult:
    completed = subprocess.run(  # noqa: S603 - argv is generated, not shell text.
        command.argv,
        cwd=command.cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return BuildCommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def verify_generated_project(
    output_root: Path,
    model: GeneratedProjectRenderModel,
    runner: BuildCommandRunner = run_subprocess_build_command,
    policy: BuildVerificationPolicy = BuildVerificationPolicy(),
) -> BuildVerificationReport:
    """Run build smoke verification for every generated backend profile."""

    root = output_root.resolve()
    diagnostics = _project_diagnostics(root, model)
    if diagnostics:
        return BuildVerificationReport(commands=(), diagnostics=diagnostics)

    results: list[BuildCommandResult] = []
    result_diagnostics: list[Diagnostic] = []
    for command_group in _verification_command_groups(root, model, policy):
        for command in command_group:
            result = runner(command)
            results.append(result)
            if result.returncode != 0:
                result_diagnostics.append(_command_diagnostic(result))
                break

    return BuildVerificationReport(
        commands=tuple(results),
        diagnostics=tuple(result_diagnostics),
    )


def _verification_command_groups(
    root: Path,
    model: GeneratedProjectRenderModel,
    policy: BuildVerificationPolicy,
) -> tuple[tuple[BuildCommand, ...], ...]:
    return _cpp_command_groups(root, model.cpp, policy) + _rust_command_groups(
        root,
        model.rust,
    )


def _cpp_command_groups(
    root: Path,
    project: BackendProjectRenderModel,
    policy: BuildVerificationPolicy,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / project.root_path
    command_groups: list[tuple[BuildCommand, ...]] = []
    for profile in project.profiles:
        profile_name = str(profile.profile_name)
        build_dir = project_root / "build" / str(profile.file_stem)
        compiler_args = (
            (f"-DCMAKE_CXX_COMPILER={policy.cxx_compiler}",)
            if policy.cxx_compiler is not None
            else ()
        )
        command_groups.append(
            (
                BuildCommand(
                    backend_id=project.backend_id,
                    profile_name=profile_name,
                    step="configure",
                    argv=(
                        "cmake",
                        "-S",
                        str(project_root),
                        "-B",
                        str(build_dir),
                        f"-DTSL_PROFILE={profile.profile_name}",
                        *compiler_args,
                    ),
                    cwd=root,
                ),
                BuildCommand(
                    backend_id=project.backend_id,
                    profile_name=profile_name,
                    step="build",
                    argv=("cmake", "--build", str(build_dir)),
                    cwd=root,
                ),
                BuildCommand(
                    backend_id=project.backend_id,
                    profile_name=profile_name,
                    step="test",
                    argv=(
                        "ctest",
                        "--test-dir",
                        str(build_dir),
                        "--output-on-failure",
                    ),
                    cwd=root,
                ),
            )
        )
    return tuple(command_groups)


def _rust_command_groups(
    root: Path,
    project: BackendProjectRenderModel,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / project.root_path
    manifest = project_root / "Cargo.toml"
    return tuple(
        (
            BuildCommand(
                backend_id=project.backend_id,
                profile_name=str(profile.profile_name),
                step="test",
                argv=(
                    "cargo",
                    "test",
                    "--manifest-path",
                    str(manifest),
                    "--no-default-features",
                    "--features",
                    str(profile.rust_feature),
                ),
                cwd=root,
            ),
        )
        for profile in project.profiles
    )


def _project_diagnostics(
    root: Path,
    model: GeneratedProjectRenderModel,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for project in model.projects:
        project_root = root / project.root_path
        if not project_root.is_dir():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BUILD-VERIFY-MISSING-PROJECT",
                    message=(
                        f"generated {project.backend_id!r} project does not "
                        f"exist at {project_root}"
                    ),
                )
            )
            continue
        public_entry = root / project.public_entry_path
        if not public_entry.is_file():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BUILD-VERIFY-MISSING-PUBLIC-ENTRY",
                    message=(
                        f"generated {project.backend_id!r} public entry does "
                        f"not exist at {public_entry}"
                    ),
                )
            )
        smoke_test = root / project.smoke_test_path
        if not smoke_test.is_file():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BUILD-VERIFY-MISSING-SMOKE-TEST",
                    message=(
                        f"generated {project.backend_id!r} smoke test does "
                        f"not exist at {smoke_test}"
                    ),
                )
            )
        for profile in project.profiles:
            profile_file = root / project.root_path / _profile_relative_path(
                project.backend_id,
                str(profile.file_stem),
            )
            if not profile_file.is_file():
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-BUILD-VERIFY-MISSING-PROFILE-FILE",
                        message=(
                            f"generated {project.backend_id!r} profile "
                            f"{profile.profile_name!r} does not exist at "
                            f"{profile_file}"
                        ),
                    )
                )
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))


def _profile_relative_path(backend_id: str, stem: str) -> Path:
    if backend_id == "cpp":
        return Path("include") / "profiles" / f"{stem}.hpp"
    if backend_id == "rust":
        return Path("src") / "profiles" / f"{stem}.rs"
    return Path("profiles") / stem


def _command_diagnostic(result: BuildCommandResult) -> Diagnostic:
    command = result.command
    command_text = " ".join(command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return Diagnostic(
        severity="error",
        code="TSL-BUILD-VERIFY-COMMAND-FAILED",
        message=(
            f"{command.backend_id} profile {command.profile_name} "
            f"{command.step} command failed with exit code "
            f"{result.returncode}: {command_text}{suffix}"
        ),
    )
