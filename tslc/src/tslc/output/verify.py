"""After-write build verification for the generated C++ and Rust projects.

The subprocess machinery is ported from the proven ``tslgen`` verifier, but it is
driven by a small, explicit project description instead of a heavy render model.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

from tslc.backend.registry import backend_capability
from tslc.diagnostics import Diagnostic
from tslc.output.verify_drivers import (
    command_failure_diagnostic,
    filter_runner_verifiable_profiles,
    missing_verify_tool,
    runner_missing_diagnostic,
)
from tslc.output.verification_attestation import write_verification_attestation
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandEnvironment,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerificationReport,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyCompileFailure,
    VerifyProfile,
    VerifyProject,
    VerifyRunner,
)


def run_subprocess_build_command(command: BuildCommand) -> BuildCommandResult:
    try:
        completed = subprocess.run(  # noqa: S603 - argv is generated, not shell text.
            command.argv,
            cwd=command.cwd,
            input="",
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            env=_subprocess_env(command),
            timeout=command.timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        timeout_detail = (
            f"verification command timed out after {command.timeout_seconds} seconds"
        )
        stderr = _timeout_stream(error.stderr).rstrip()
        return BuildCommandResult(
            command=command,
            returncode=124,
            stdout=_timeout_stream(error.stdout),
            stderr=f"{stderr}\n{timeout_detail}".lstrip(),
        )
    return BuildCommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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

    runner_missing = runner_missing_diagnostic(config)
    if runner_missing is not None:
        return _finalize_report(
            root,
            project,
            commands=(),
            diagnostics=(runner_missing,),
            skipped=(),
        )

    for backend in project.backends:
        try:
            driver = backend_capability(backend.backend_id).verify_driver()
        except ValueError:
            skipped.append(f"{backend.backend_id}: unsupported backend verification")
            continue
        missing = missing_verify_tool(driver)
        if missing is not None:
            skipped.append(f"{backend.backend_id}: {missing} not found")
            continue
        backend, profile_skips = filter_runner_verifiable_profiles(backend, config)
        skipped.extend(profile_skips)
        if not backend.profiles:
            continue
        prep = driver.prepare_backend(root, backend, config, runner)
        results.extend(prep.commands)
        diagnostics.extend(prep.diagnostics)
        skipped.extend(prep.skipped)
        prepared = prep.backend
        if prepared is None or not prepared.profiles:
            continue
        profiles_by_name = {
            profile.profile_name: profile for profile in prepared.profiles
        }
        for group in driver.command_groups(root, prepared, config):
            for command in group:
                result = runner(command)
                results.append(result)
                if not result.matches_expectation:
                    diagnostics.append(_command_expectation_diagnostic(result))
                    break
                if command.expected_failure_marker is not None:
                    continue
                follow_up = driver.after_successful_command(
                    result,
                    profiles_by_name,
                    config,
                    runner,
                )
                results.extend(follow_up.commands)
                diagnostics.extend(follow_up.diagnostics)

    return _finalize_report(
        root,
        project,
        commands=tuple(results),
        diagnostics=tuple(diagnostics),
        skipped=tuple(skipped),
    )


def _finalize_report(
    root: Path,
    project: VerifyProject,
    *,
    commands: tuple[BuildCommandResult, ...],
    diagnostics: tuple[Diagnostic, ...],
    skipped: tuple[str, ...],
) -> BuildVerificationReport:
    if project.input_digest is None:
        return BuildVerificationReport(
            commands=commands,
            diagnostics=diagnostics,
            skipped=skipped,
        )
    attestation_path, attestation_diagnostic = write_verification_attestation(
        root,
        input_digest=project.input_digest,
        commands=commands,
        diagnostics=diagnostics,
        skipped=skipped,
    )
    if attestation_diagnostic is not None:
        diagnostics = (*diagnostics, attestation_diagnostic)
    return BuildVerificationReport(
        commands=commands,
        diagnostics=diagnostics,
        skipped=skipped,
        attestation_path=attestation_path,
    )


def _command_expectation_diagnostic(result: BuildCommandResult) -> Diagnostic:
    marker = result.command.expected_failure_marker
    if marker is None:
        return command_failure_diagnostic(result)
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    if result.returncode == 0:
        message = (
            f"expected compilation to fail with marker {marker!r}, but command "
            f"succeeded: {command_text}"
        )
    else:
        suffix = f": {detail}" if detail else ""
        message = (
            f"compilation failed without expected marker {marker!r}: "
            f"{command_text}{suffix}"
        )
    return Diagnostic(
        severity=result.command.severity_on_failure,
        code="TSL-BUILD-VERIFY-EXPECTED-COMPILE-FAILURE",
        message=message,
    )


def _subprocess_env(command: BuildCommand) -> dict[str, str] | None:
    environment = dict(os.environ)
    # Zig defaults to ~/.cache/zig, which can be read-only in sandboxed or CI
    # environments. Keep verifier-owned caches under the command root so build
    # verification does not write to /tmp or the user's home directory. ``BuildCommand.env``
    # can override this for a deliberately constructed command.
    zig_local_cache, zig_global_cache = _zig_cache_dirs(command.cwd)
    environment["ZIG_LOCAL_CACHE_DIR"] = str(zig_local_cache)
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(zig_global_cache)
    wasmtime_home, xdg_cache_home = _runtime_cache_dirs(command.cwd)
    environment["WASMTIME_HOME"] = str(wasmtime_home)
    environment["XDG_CACHE_HOME"] = str(xdg_cache_home)
    for item in command.env:
        environment[item.key] = item.value
    try:
        driver = backend_capability(command.backend_id).verify_driver()
    except ValueError:
        pass
    else:
        driver.prepare_command_environment(command, environment)
    return environment


def _runtime_cache_dirs(command_root: Path) -> tuple[Path, Path]:
    base = command_root.resolve() / ".tslctmp" / "runtime"
    return base / "wasmtime-home", base / "xdg-cache"


def _zig_cache_dirs(command_root: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(str(command_root.resolve()).encode("utf-8")).hexdigest()[:16]
    root = command_root.resolve() / ".tslctmp" / "zig-cache" / digest
    local = root / "local"
    global_ = root / "global"
    local.mkdir(parents=True, exist_ok=True)
    global_.mkdir(parents=True, exist_ok=True)
    return local, global_
