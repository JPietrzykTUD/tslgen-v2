"""After-write build verification for the generated C++ and Rust projects.

The subprocess machinery is ported from the proven ``tslgen`` verifier, but it is
driven by a small, explicit project description instead of a heavy render model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from collections.abc import Sequence
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
class BuildVerifierConfig:
    """Optional toolchain configuration for after-write verification."""

    # None means: use the ambient CXX setting when present, otherwise try `c++`.
    # A tuple pins the compiler command, e.g. ("/usr/bin/c++",) or ("zig", "c++").
    cpp_compiler: tuple[str, ...] | None = None
    # None means: use the ambient RUSTC setting when present, otherwise try `rustc`.
    # Cargo expects RUSTC to name the compiler executable; use RUSTFLAGS for flags.
    rust_compiler: str | None = None
    # Build + run the generated value-correctness tests (the `tsl_values` binary under ctest).
    # OFF by default: the ordinary build-verify only compiles the library substrate
    # (`tsl_smoke`), so adding value testing to the standard gate does not double every
    # project's build cost. The dedicated value-test gate opts in.
    run_value_tests: bool = False

    @classmethod
    def create(
        cls,
        *,
        cpp_compiler: str | Sequence[str] | None = None,
        rust_compiler: str | None = None,
        run_value_tests: bool = False,
    ) -> "BuildVerifierConfig":
        return cls(
            cpp_compiler=_normalize_compiler_command(cpp_compiler),
            rust_compiler=_normalize_compiler_executable(rust_compiler),
            run_value_tests=run_value_tests,
        )


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
    # Diagnostic severity if this command fails. Configure/build failures are hard errors;
    # value-test failures are reported as warnings (report-then-promote) so a not-yet-correct
    # path surfaces without failing the build gate during scale-up.
    severity_on_failure: str = "error"


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
    *,
    config: BuildVerifierConfig | None = None,
) -> BuildVerificationReport:
    """Configure/build/test every generated backend profile.

    A backend whose required toolchain is missing is skipped (recorded), not
    failed, so the pipeline stays usable on partial toolchains.
    """

    root = output_root.resolve()
    config = config or BuildVerifierConfig()
    results: list[BuildCommandResult] = []
    diagnostics: list[Diagnostic] = []
    skipped: list[str] = []

    for backend in project.backends:
        missing = _missing_tool(backend.backend_id)
        if missing is not None:
            skipped.append(f"{backend.backend_id}: {missing} not found")
            continue
        if backend.backend_id == "cpp":
            compiler = _effective_cpp_compiler(config)
            missing_compiler = _missing_executable(compiler[0])
            if missing_compiler is not None:
                skipped.append(f"cpp: C++ compiler {missing_compiler} not found")
                continue
            preflight = _cpp_preflight_command(root, backend, compiler)
            if isinstance(preflight, Diagnostic):
                diagnostics.append(preflight)
                continue
            result = runner(preflight)
            results.append(result)
            if result.returncode != 0:
                skipped.append(_cpp_preflight_skip(result))
                continue
        if backend.backend_id == "rust":
            compiler = _effective_rust_compiler(config)
            missing_compiler = _missing_executable(compiler)
            if missing_compiler is not None:
                skipped.append(f"rust: Rust compiler {missing_compiler} not found")
                continue
            preflight = _rust_preflight_command(root, backend, compiler)
            if isinstance(preflight, Diagnostic):
                diagnostics.append(preflight)
                continue
            result = runner(preflight)
            results.append(result)
            if result.returncode != 0:
                skipped.append(_rust_preflight_skip(result))
                continue
        for group in _command_groups(root, backend, config):
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
        if _missing_executable(tool) is not None:
            return tool
    return None


def _missing_executable(executable: str) -> str | None:
    return executable if shutil.which(executable) is None else None


def _command_groups(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], ...]:
    if backend.backend_id == "cpp":
        return _cpp_command_groups(root, backend, config)
    if backend.backend_id == "rust":
        return _rust_command_groups(root, backend, config)
    return ()


def _cpp_command_groups(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    env = _cpp_environment(config)
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        build_dir = project_root / "build" / profile.file_stem
        commands = [
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
                env=env,
            ),
            # Build only the substrate-compile target by default; the heavy value-test binary
            # is built (and run) only when value testing is requested, so the standard gate
            # keeps its single-target cost.
            BuildCommand(
                backend_id="cpp",
                profile_name=profile.profile_name,
                step="build",
                argv=("cmake", "--build", str(build_dir), "--target", "tsl_smoke"),
                cwd=root,
                env=env,
            ),
        ]
        if config.run_value_tests:
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="build-values",
                    argv=("cmake", "--build", str(build_dir), "--target", "tsl_values"),
                    cwd=root,
                    env=env,
                    severity_on_failure="warning",
                )
            )
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="test",
                    argv=("ctest", "--test-dir", str(build_dir), "--output-on-failure"),
                    cwd=root,
                    env=env,
                    severity_on_failure="warning",
                )
            )
        groups.append(tuple(commands))
    return tuple(groups)


def _rust_command_groups(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    manifest = project_root / "Cargo.toml"
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        # Value testing adds the opt-in `value_tests` feature (so `cargo test` compiles+runs the
        # generated value tests); without it `tests/values.rs` is cfg'd empty. A value-mode
        # failure is reported as a warning (report-then-promote), like the C++ ctest step.
        features = profile.profile_name
        severity = "error"
        if config.run_value_tests:
            features = f"{profile.profile_name},value_tests"
            severity = "warning"
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
                        features,
                    ),
                    cwd=root,
                    env=_rust_environment(profile, config),
                    severity_on_failure=severity,
                ),
            )
        )
    return tuple(groups)


def _rust_environment(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[BuildCommandEnvironment, ...]:
    environment: list[BuildCommandEnvironment] = []
    if config.rust_compiler is not None:
        environment.append(BuildCommandEnvironment(key="RUSTC", value=config.rust_compiler))
    if not profile.rust_target_features:
        return tuple(environment)
    joined = ",".join(profile.rust_target_features)
    environment.append(BuildCommandEnvironment(key="RUSTFLAGS", value=f"-C target-feature={joined}"))
    return tuple(environment)


def _normalize_compiler_command(compiler: str | Sequence[str] | None) -> tuple[str, ...] | None:
    if compiler is None:
        return None
    if isinstance(compiler, str):
        normalized = tuple(shlex.split(compiler))
    else:
        normalized = tuple(str(part) for part in compiler)
    return normalized or None


def _normalize_compiler_executable(compiler: str | None) -> str | None:
    if compiler is None:
        return None
    normalized = compiler.strip()
    return normalized or None


def _effective_cpp_compiler(config: BuildVerifierConfig) -> tuple[str, ...]:
    if config.cpp_compiler is not None:
        return config.cpp_compiler
    ambient = os.environ.get("CXX")
    if ambient:
        parsed = tuple(shlex.split(ambient))
        if parsed:
            return parsed
    return ("c++",)


def _effective_rust_compiler(config: BuildVerifierConfig) -> str:
    if config.rust_compiler is not None:
        return config.rust_compiler
    ambient = os.environ.get("RUSTC")
    if ambient:
        normalized = _normalize_compiler_executable(ambient)
        if normalized is not None:
            return normalized
    return "rustc"


def _cpp_environment(config: BuildVerifierConfig) -> tuple[BuildCommandEnvironment, ...]:
    if config.cpp_compiler is None:
        return ()
    return (BuildCommandEnvironment(key="CXX", value=shlex.join(config.cpp_compiler)),)


def _cpp_preflight_command(
    root: Path,
    backend: VerifyBackend,
    compiler: tuple[str, ...],
) -> BuildCommand | Diagnostic:
    project_root = root / backend.root_path
    preflight_dir = project_root / "build" / "_compiler_preflight"
    source_path = preflight_dir / "tslc_compiler_check.cpp"
    object_path = preflight_dir / "tslc_compiler_check.o"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text("int main() { return 0; }\n", encoding="utf-8")
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=f"could not write C++ compiler preflight source under {preflight_dir}: {exc}",
        )

    return BuildCommand(
        backend_id="cpp",
        profile_name="_toolchain",
        step="preflight",
        argv=(
            *compiler,
            "-x",
            "c++",
            "-std=c++17",
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ),
        cwd=root,
    )


def _rust_preflight_command(
    root: Path,
    backend: VerifyBackend,
    compiler: str,
) -> BuildCommand | Diagnostic:
    project_root = root / backend.root_path
    preflight_dir = project_root / "target" / "_compiler_preflight"
    source_path = preflight_dir / "tslc_compiler_check.rs"
    binary_path = preflight_dir / "tslc_compiler_check"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text("fn main() {}\n", encoding="utf-8")
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=f"could not write Rust compiler preflight source under {preflight_dir}: {exc}",
        )

    return BuildCommand(
        backend_id="rust",
        profile_name="_toolchain",
        step="preflight",
        argv=(
            compiler,
            "--edition=2021",
            str(source_path),
            "-o",
            str(binary_path),
        ),
        cwd=root,
    )


def _cpp_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        "cpp: C++ compiler preflight failed with exit code "
        f"{result.returncode}: {command_text}{suffix}"
    )


def _rust_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        "rust: Rust compiler preflight failed with exit code "
        f"{result.returncode}: {command_text}{suffix}"
    )


def _command_diagnostic(result: BuildCommandResult) -> Diagnostic:
    command = result.command
    command_text = " ".join(command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return Diagnostic(
        severity=command.severity_on_failure,
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
