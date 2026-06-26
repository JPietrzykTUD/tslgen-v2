"""After-write build verification for the generated C++ and Rust projects.

The subprocess machinery is ported from the proven ``tslgen`` verifier, but it is
driven by a small, explicit project description instead of a heavy render model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from typing import Protocol

from tslc.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class VerifyEmulator:
    kind: str  # "sde" | "qemu-aarch64"
    profile: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerifyProfile:
    profile_name: str
    file_stem: str
    family: str = "generic"
    # C++ extra compile flags (e.g. ("-mavx2", "-mavx")); Rust target features (e.g. ("+avx2",)).
    cpp_flags: tuple[str, ...] = ()
    cpp_target: str | None = None
    rust_target_features: tuple[str, ...] = ()
    rust_target: str | None = None
    rust_linker: str | None = None
    # Optional emulator profile used to run value tests for this profile.
    emulator: VerifyEmulator | None = None


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
    # Optional Intel SDE executable. Profiles opt in with VerifyProfile.emulator.
    sde_path: str | None = None
    # Optional QEMU user-mode executable for aarch64 profile value tests.
    qemu_aarch64_path: str | None = None
    # Optional target overrides. Profile-derived targets are used when unset.
    cpp_target: str | None = None
    rust_target: str | None = None
    rust_linker: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cpp_compiler: str | Sequence[str] | None = None,
        rust_compiler: str | None = None,
        run_value_tests: bool = False,
        sde_path: str | None = None,
        qemu_aarch64_path: str | None = None,
        cpp_target: str | None = None,
        rust_target: str | None = None,
        rust_linker: str | None = None,
    ) -> "BuildVerifierConfig":
        normalized_sde_path = _normalize_compiler_executable(sde_path)
        normalized_qemu_aarch64_path = _normalize_compiler_executable(qemu_aarch64_path)
        normalized_cpp_compiler = _normalize_compiler_command(cpp_compiler)
        if normalized_cpp_compiler is None and normalized_sde_path is not None and run_value_tests:
            # SDE profile tests execute binaries for low-ISA chips. An ambient CXX
            # such as `zig c++` can inject runtime helpers that use newer
            # instructions than the requested chip, so pin the verifier default
            # unless the caller explicitly chose a compiler.
            normalized_cpp_compiler = ("c++",)
        return cls(
            cpp_compiler=normalized_cpp_compiler,
            rust_compiler=_normalize_compiler_executable(rust_compiler),
            run_value_tests=run_value_tests,
            sde_path=normalized_sde_path,
            qemu_aarch64_path=normalized_qemu_aarch64_path,
            cpp_target=_normalize_compiler_executable(cpp_target),
            rust_target=_normalize_compiler_executable(rust_target),
            rust_linker=_normalize_compiler_executable(rust_linker),
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
        stdin=subprocess.DEVNULL,
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

    emulator_missing = _emulator_missing_diagnostic(config)
    if emulator_missing is not None:
        return BuildVerificationReport(
            commands=(),
            diagnostics=(emulator_missing,),
            skipped=(),
        )

    for backend in project.backends:
        missing = _missing_tool(backend.backend_id)
        if missing is not None:
            skipped.append(f"{backend.backend_id}: {missing} not found")
            continue
        backend, profile_skips = _filter_emulator_verifiable_profiles(backend, config)
        skipped.extend(profile_skips)
        if not backend.profiles:
            continue
        profiles_by_name = {profile.profile_name: profile for profile in backend.profiles}
        if backend.backend_id == "cpp":
            compiler = _effective_cpp_compiler(config, backend)
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
            target_profiles: list[VerifyProfile] = []
            for profile in backend.profiles:
                target_preflight = _cpp_target_preflight_command(
                    root,
                    backend,
                    profile,
                    config,
                    compiler,
                )
                if target_preflight is None:
                    target_profiles.append(profile)
                    continue
                if isinstance(target_preflight, Diagnostic):
                    diagnostics.append(target_preflight)
                    continue
                result = runner(target_preflight)
                results.append(result)
                if result.returncode != 0:
                    skipped.append(_cpp_target_preflight_skip(result))
                    continue
                target_profiles.append(profile)
            backend = VerifyBackend(
                backend_id=backend.backend_id,
                root_path=backend.root_path,
                profiles=tuple(target_profiles),
            )
            profiles_by_name = {profile.profile_name: profile for profile in backend.profiles}
            if not backend.profiles:
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
                if command.backend_id == "rust" and command.step == "build-tests":
                    profile = profiles_by_name[command.profile_name]
                    followups, followup_diagnostics = _rust_emulated_test_commands(
                        result,
                        profile,
                        config,
                    )
                    diagnostics.extend(followup_diagnostics)
                    for followup in followups:
                        followup_result = runner(followup)
                        results.append(followup_result)
                        if followup_result.returncode != 0:
                            diagnostics.append(_command_diagnostic(followup_result))
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


def _emulator_missing_diagnostic(config: BuildVerifierConfig) -> Diagnostic | None:
    if not config.run_value_tests:
        return None
    for kind, executable in (
        ("sde", config.sde_path),
        ("qemu-aarch64", config.qemu_aarch64_path),
    ):
        if executable is None:
            continue
        missing = _missing_executable(executable)
        if missing is not None:
            return Diagnostic(
                severity="error",
                code="TSL-BUILD-VERIFY-EMULATOR-MISSING",
                message=f"{kind} emulator executable {missing} not found",
            )
    return None


def _filter_emulator_verifiable_profiles(
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[VerifyBackend, tuple[str, ...]]:
    configured = _configured_emulator_kinds(config)
    if not configured or not config.run_value_tests:
        return backend, ()

    profiles: list[VerifyProfile] = []
    skipped: list[str] = []
    for profile in backend.profiles:
        if profile.emulator is None:
            if profile.family != "generic":
                skipped.append(
                    f"{backend.backend_id}: profile {profile.profile_name} has no "
                    "emulator metadata; value-test verification skipped"
                )
            else:
                profiles.append(profile)
            continue
        if profile.emulator.kind not in configured:
            skipped.append(
                f"{backend.backend_id}: profile {profile.profile_name} requires "
                f"{profile.emulator.kind}, but that emulator is not configured; "
                "value-test verification skipped"
            )
            continue
        profiles.append(profile)
    return (
        VerifyBackend(
            backend_id=backend.backend_id,
            root_path=backend.root_path,
            profiles=tuple(profiles),
        ),
        tuple(skipped),
    )


def _configured_emulator_kinds(config: BuildVerifierConfig) -> frozenset[str]:
    configured: set[str] = set()
    if config.sde_path is not None:
        configured.add("sde")
    if config.qemu_aarch64_path is not None:
        configured.add("qemu-aarch64")
    return frozenset(configured)


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
    env = _cpp_environment(config, backend)
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        build_dir = project_root / "build" / profile.file_stem
        configure_args = _cpp_configure_args(project_root, build_dir, profile, config)
        commands: list[BuildCommand] = []
        if config.run_value_tests and _configured_emulator_kinds(config):
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="clean",
                    argv=("cmake", "-E", "rm", "-rf", str(build_dir)),
                    cwd=root,
                    env=env,
                )
            )
        commands.extend(
            [
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="configure",
                    argv=configure_args,
                    cwd=root,
                    env=env,
                ),
                # Build only the substrate-compile target by default; the heavy
                # value-test binary is built (and run) only when value testing is
                # requested, so the standard gate keeps its single-target cost.
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="build",
                    argv=("cmake", "--build", str(build_dir), "--target", "tsl_smoke"),
                    cwd=root,
                    env=env,
                ),
            ]
        )
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
                    argv=(
                        *_ctest_prefix(profile, config),
                        "ctest",
                        "--test-dir",
                        str(build_dir),
                        "--output-on-failure",
                    ),
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
        target_dir = project_root / "target" / profile.file_stem
        # Value testing adds the opt-in `value_tests` feature (so `cargo test` compiles+runs the
        # generated value tests); without it `tests/values.rs` is cfg'd empty. A value-mode
        # failure is reported as a warning (report-then-promote), like the C++ ctest step.
        features = profile.profile_name
        severity = "error"
        step = "test"
        extra_args: tuple[str, ...] = ()
        if config.run_value_tests:
            features = f"{profile.profile_name},value_tests"
            severity = "warning"
            if _emulator_prefix(profile, config):
                step = "build-tests"
                extra_args = ("--no-run", "--message-format=json")
        target_args = _rust_target_args(profile, config)
        groups.append(
            (
                BuildCommand(
                    backend_id="rust",
                    profile_name=profile.profile_name,
                    step=step,
                    argv=(
                        "cargo",
                        "test",
                        "--manifest-path",
                        str(manifest),
                        "--no-default-features",
                        "--features",
                        features,
                        *target_args,
                        "--target-dir",
                        str(target_dir),
                        *extra_args,
                    ),
                    cwd=root,
                    env=_rust_environment(profile, config),
                    severity_on_failure=severity,
                ),
            )
        )
    return tuple(groups)


def _cpp_configure_args(
    project_root: Path,
    build_dir: Path,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    args = [
        "cmake",
        "-S",
        str(project_root),
        "-B",
        str(build_dir),
        f"-DTSL_PROFILE={profile.profile_name}",
    ]
    target = _cpp_target(profile, config)
    if target is not None:
        args.extend(
            (
                "-DCMAKE_SYSTEM_NAME=Linux",
                "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
                "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
                f"-DCMAKE_CXX_COMPILER_TARGET={target}",
            )
        )
    cross_emulator = _cmake_cross_emulator(profile, config)
    if cross_emulator:
        args.append(f"-DCMAKE_CROSSCOMPILING_EMULATOR={';'.join(cross_emulator)}")
    return tuple(args)


def _cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.cpp_target or profile.cpp_target


def _rust_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.rust_target or profile.rust_target


def _rust_linker(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.rust_linker or profile.rust_linker


def _rust_target_args(profile: VerifyProfile, config: BuildVerifierConfig) -> tuple[str, ...]:
    target = _rust_target(profile, config)
    return ("--target", target) if target is not None else ()


def _ctest_prefix(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if profile.emulator is None or profile.emulator.kind != "sde":
        return ()
    return _emulator_prefix(profile, config)


def _cmake_cross_emulator(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if profile.emulator is None or profile.emulator.kind != "qemu-aarch64":
        return ()
    prefix = _emulator_prefix(profile, config)
    return prefix


def _emulator_prefix(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    emulator = profile.emulator
    if emulator is None:
        return ()
    if emulator.kind == "sde":
        if config.sde_path is None:
            return ()
        return (config.sde_path, f"-{emulator.profile}", *emulator.args, "--")
    if emulator.kind == "qemu-aarch64":
        if config.qemu_aarch64_path is None:
            return ()
        return (config.qemu_aarch64_path, "-cpu", emulator.profile, *emulator.args)
    return ()


def _rust_emulated_test_commands(
    result: BuildCommandResult,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], tuple[Diagnostic, ...]]:
    prefix = _emulator_prefix(profile, config)
    if not prefix:
        return (), ()

    executables = _rust_test_executables(result.stdout)
    if not executables:
        return (
            (),
            (
                Diagnostic(
                    severity=result.command.severity_on_failure,
                    code="TSL-BUILD-VERIFY-NO-RUST-TEST-BINARIES",
                    message=(
                        f"rust profile {profile.profile_name} value-test build produced "
                        "no runnable test binaries"
                    ),
                ),
            ),
        )

    return (
        tuple(
            BuildCommand(
                backend_id="rust",
                profile_name=profile.profile_name,
                step="test",
                argv=(*prefix, executable),
                cwd=result.command.cwd,
                severity_on_failure=result.command.severity_on_failure,
            )
            for executable in executables
        ),
        (),
    )


def _rust_test_executables(stdout: str) -> tuple[str, ...]:
    executables: list[str] = []
    seen: set[str] = set()
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("reason") != "compiler-artifact":
            continue
        executable = data.get("executable")
        if not isinstance(executable, str) or not executable:
            continue
        if executable not in seen:
            seen.add(executable)
            executables.append(executable)
    return tuple(executables)


def _rust_environment(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[BuildCommandEnvironment, ...]:
    environment: list[BuildCommandEnvironment] = []
    if config.rust_compiler is not None:
        environment.append(BuildCommandEnvironment(key="RUSTC", value=config.rust_compiler))
    target = _rust_target(profile, config)
    linker = _rust_linker(profile, config)
    if target is not None and linker is not None:
        environment.append(
            BuildCommandEnvironment(
                key=f"CARGO_TARGET_{_cargo_target_env(target)}_LINKER",
                value=linker,
            )
        )
    if profile.rust_target_features:
        joined = ",".join(profile.rust_target_features)
        environment.append(
            BuildCommandEnvironment(
                key="RUSTFLAGS",
                value=f"-C target-feature={joined}",
            )
        )
    return tuple(environment)


def _cargo_target_env(target: str) -> str:
    return target.upper().replace("-", "_")


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


def _effective_cpp_compiler(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
) -> tuple[str, ...]:
    if config.cpp_compiler is not None:
        return config.cpp_compiler
    if backend is not None and any(_cpp_target(profile, config) for profile in backend.profiles):
        return ("clang++",)
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


def _cpp_environment(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
) -> tuple[BuildCommandEnvironment, ...]:
    if config.cpp_compiler is None and not (
        backend is not None and any(_cpp_target(profile, config) for profile in backend.profiles)
    ):
        return ()
    return (
        BuildCommandEnvironment(
            key="CXX",
            value=shlex.join(_effective_cpp_compiler(config, backend)),
        ),
    )


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


def _cpp_target_preflight_command(
    root: Path,
    backend: VerifyBackend,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
    compiler: tuple[str, ...],
) -> BuildCommand | Diagnostic | None:
    target = _cpp_target(profile, config)
    if target is None:
        return None

    project_root = root / backend.root_path
    preflight_dir = project_root / "build" / "_compiler_preflight" / profile.file_stem
    source_path = preflight_dir / "tslc_target_check.cpp"
    object_path = preflight_dir / "tslc_target_check.o"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                (
                    "#include <array>",
                    "#if defined(__aarch64__)",
                    "#include <arm_neon.h>",
                    "#endif",
                    "int main() { std::array<int, 1> value{}; return value[0]; }",
                    "",
                )
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=(
                "could not write C++ target preflight source for profile "
                f"{profile.profile_name} under {preflight_dir}: {exc}"
            ),
        )

    return BuildCommand(
        backend_id="cpp",
        profile_name=profile.profile_name,
        step="target-preflight",
        argv=(
            *compiler,
            f"--target={target}",
            "-x",
            "c++",
            "-std=c++17",
            *profile.cpp_flags,
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ),
        cwd=root,
        env=_cpp_environment(config, backend),
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


def _cpp_target_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        f"cpp: profile {result.command.profile_name} target preflight failed "
        f"with exit code {result.returncode}: {command_text}{suffix}"
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
    environment = dict(os.environ)
    # Zig defaults to ~/.cache/zig, which can be read-only in sandboxed or CI
    # environments. On this workspace mount, Zig can also fail to discover libc
    # when its cache is under the generated project tree, so keep verifier-owned
    # caches in /tmp while still isolating them by command root. ``BuildCommand.env``
    # can override this for a deliberately constructed command.
    zig_local_cache, zig_global_cache = _zig_cache_dirs(command.cwd)
    environment["ZIG_LOCAL_CACHE_DIR"] = str(zig_local_cache)
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(zig_global_cache)
    for item in command.env:
        environment[item.key] = item.value
    return environment


def _zig_cache_dirs(command_root: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(str(command_root.resolve()).encode("utf-8")).hexdigest()[:16]
    root = Path(tempfile.gettempdir()) / "tslc-zig-cache" / digest
    local = root / "local"
    global_ = root / "global"
    local.mkdir(parents=True, exist_ok=True)
    global_.mkdir(parents=True, exist_ok=True)
    return local, global_
