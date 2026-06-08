"""After-write build verification for the generated C++ and Rust projects.

The subprocess machinery is ported from the proven ``tslgen`` verifier, but it is
driven by a small, explicit project description instead of a heavy render model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
from typing import Protocol

from tslc.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class VerifyProfile:
    profile_name: str
    file_stem: str
    # C++ extra compile flags (e.g. ("-mavx2", "-mavx")); Rust target features (e.g. ("+avx2",)).
    cpp_flags: tuple[str, ...] = ()
    rust_target_features: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerifyBackend:
    backend_id: str  # "cpp" | "rust"
    root_path: str  # relative to output root, e.g. "cpp"
    profiles: tuple[VerifyProfile, ...]


@dataclass(frozen=True, slots=True)
class VerifyProject:
    backends: tuple[VerifyBackend, ...]


@dataclass(frozen=True, slots=True)
class BuildCommandEnvironment:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class BuildCommand:
    backend_id: str
    profile_name: str
    step: str
    argv: tuple[str, ...]
    cwd: Path
    env: tuple[BuildCommandEnvironment, ...] = ()


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
    skipped: tuple[str, ...] = field(default=())


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
        env=_subprocess_env(command),
    )
    return BuildCommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def verify_generated_project(
    output_root: Path,
    project: VerifyProject,
    runner: BuildCommandRunner = run_subprocess_build_command,
) -> BuildVerificationReport:
    """Configure/build/test every generated backend profile.

    A backend whose required toolchain is missing is skipped (recorded), not
    failed, so the pipeline stays usable on partial toolchains.
    """

    root = output_root.resolve()
    results: list[BuildCommandResult] = []
    diagnostics: list[Diagnostic] = []
    skipped: list[str] = []

    for backend in project.backends:
        missing = _missing_tool(backend.backend_id)
        if missing is not None:
            skipped.append(f"{backend.backend_id}: {missing} not found")
            continue
        for group in _command_groups(root, backend):
            for command in group:
                result = runner(command)
                results.append(result)
                if result.returncode != 0:
                    diagnostics.append(_command_diagnostic(result))
                    break

    return BuildVerificationReport(
        commands=tuple(results),
        diagnostics=tuple(diagnostics),
        skipped=tuple(skipped),
    )


def _missing_tool(backend_id: str) -> str | None:
    needed = {"cpp": ("cmake",), "rust": ("cargo",)}.get(backend_id, ())
    for tool in needed:
        if shutil.which(tool) is None:
            return tool
    return None


def _command_groups(root: Path, backend: VerifyBackend) -> tuple[tuple[BuildCommand, ...], ...]:
    if backend.backend_id == "cpp":
        return _cpp_command_groups(root, backend)
    if backend.backend_id == "rust":
        return _rust_command_groups(root, backend)
    return ()


def _cpp_command_groups(root: Path, backend: VerifyBackend) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        build_dir = project_root / "build" / profile.file_stem
        groups.append(
            (
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="configure",
                    argv=(
                        "cmake",
                        "-S",
                        str(project_root),
                        "-B",
                        str(build_dir),
                        f"-DTSL_PROFILE={profile.profile_name}",
                    ),
                    cwd=root,
                ),
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="build",
                    argv=("cmake", "--build", str(build_dir)),
                    cwd=root,
                ),
            )
        )
    return tuple(groups)


def _rust_command_groups(root: Path, backend: VerifyBackend) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    manifest = project_root / "Cargo.toml"
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        groups.append(
            (
                BuildCommand(
                    backend_id="rust",
                    profile_name=profile.profile_name,
                    step="test",
                    argv=(
                        "cargo",
                        "test",
                        "--manifest-path",
                        str(manifest),
                        "--no-default-features",
                        "--features",
                        profile.profile_name,
                    ),
                    cwd=root,
                    env=_rust_profile_environment(profile),
                ),
            )
        )
    return tuple(groups)


def _rust_profile_environment(profile: VerifyProfile) -> tuple[BuildCommandEnvironment, ...]:
    if not profile.rust_target_features:
        return ()
    joined = ",".join(profile.rust_target_features)
    return (BuildCommandEnvironment(key="RUSTFLAGS", value=f"-C target-feature={joined}"),)


def _command_diagnostic(result: BuildCommandResult) -> Diagnostic:
    command = result.command
    command_text = " ".join(command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return Diagnostic(
        severity="error",
        code="TSL-BUILD-VERIFY-COMMAND-FAILED",
        message=(
            f"{command.backend_id} profile {command.profile_name} {command.step} "
            f"command failed with exit code {result.returncode}: {command_text}{suffix}"
        ),
    )


def _subprocess_env(command: BuildCommand) -> dict[str, str] | None:
    if not command.env:
        return None
    environment = dict(os.environ)
    for item in command.env:
        environment[item.key] = item.value
    return environment
