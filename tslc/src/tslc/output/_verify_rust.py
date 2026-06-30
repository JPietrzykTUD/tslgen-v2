"""Rust build verifier driver."""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Mapping

from tslc.diagnostics import Diagnostic
from tslc.output._verify_common import (
    command_failure_diagnostic,
    effective_rust_compiler,
    emulator_prefix,
    missing_executable,
    rust_environment,
    rust_target,
    rust_target_args,
)
from tslc.output.verify_drivers import VerifyBackendDriver
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
)


def create_rust_verify_driver() -> VerifyBackendDriver:
    return VerifyBackendDriver(
        backend_id="rust",
        required_tools=("cargo",),
        prepare_backend=_prepare_rust_backend,
        command_groups=_rust_command_groups,
        after_successful_command=_after_rust_command,
    )


def _prepare_rust_backend(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
    results: list[BuildCommandResult],
    diagnostics: list[Diagnostic],
    skipped: list[str],
) -> VerifyBackend | None:
    compiler = effective_rust_compiler(config)
    missing_compiler = missing_executable(compiler)
    if missing_compiler is not None:
        skipped.append(f"rust: Rust compiler {missing_compiler} not found")
        return None
    preflight = _rust_preflight_command(root, backend, compiler)
    if isinstance(preflight, Diagnostic):
        diagnostics.append(preflight)
        return None
    result = runner(preflight)
    results.append(result)
    if result.returncode != 0:
        skipped.append(_rust_preflight_skip(result))
        return None
    return backend


def _after_rust_command(
    result: BuildCommandResult,
    profiles_by_name: Mapping[str, VerifyProfile],
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
    results: list[BuildCommandResult],
    diagnostics: list[Diagnostic],
) -> None:
    if result.command.step != "build-tests":
        return
    profile = profiles_by_name[result.command.profile_name]
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
            diagnostics.append(command_failure_diagnostic(followup_result))
            break


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
        # Build verification still uses `cargo test` so generated test targets
        # compile. Cross-target builds cannot execute those binaries natively, so
        # they use --no-run unless value-test mode has an emulator follow-up.
        features = profile.profile_name
        severity = "error"
        step = "test"
        extra_args: tuple[str, ...] = ()
        if not config.run_value_tests and rust_target(profile, config) is not None:
            step = "build-tests"
            extra_args = ("--no-run",)
        if config.run_value_tests:
            # Value testing adds the opt-in `value_tests` feature (so `cargo test`
            # compiles+runs the generated value tests); without it `tests/values.rs`
            # is cfg'd empty. A value-mode failure is reported as a warning
            # (report-then-promote), like the C++ ctest step.
            features = f"{profile.profile_name},value_tests"
            severity = "warning"
            if emulator_prefix(profile, config):
                step = "build-tests"
                extra_args = ("--no-run", "--message-format=json")
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
                        *rust_target_args(profile, config),
                        "--target-dir",
                        str(target_dir),
                        *extra_args,
                    ),
                    cwd=root,
                    env=rust_environment(profile, config),
                    severity_on_failure=severity,
                ),
            )
        )
    return tuple(groups)


def _rust_emulated_test_commands(
    result: BuildCommandResult,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], tuple[Diagnostic, ...]]:
    prefix = emulator_prefix(profile, config)
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


def _rust_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        "rust: Rust compiler preflight failed with exit code "
        f"{result.returncode}: {command_text}{suffix}"
    )
