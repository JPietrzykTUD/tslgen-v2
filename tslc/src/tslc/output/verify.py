"""After-write build verification for the generated C++ and Rust projects.

The subprocess machinery is ported from the proven ``tslgen`` verifier, but it is
driven by a small, explicit project description instead of a heavy render model.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

from tslc.diagnostics import Diagnostic
from tslc.output.verify_drivers import (
    command_failure_diagnostic,
    emulator_missing_diagnostic,
    filter_emulator_verifiable_profiles,
    missing_verify_tool,
)
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandEnvironment,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerificationReport,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyEmulator,
    VerifyProfile,
    VerifyProject,
)


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

    emulator_missing = emulator_missing_diagnostic(config)
    if emulator_missing is not None:
        return BuildVerificationReport(
            commands=(),
            diagnostics=(emulator_missing,),
            skipped=(),
    )

    for backend in project.backends:
        try:
            from tslc.backend.registry import backend_capability

            driver = backend_capability(backend.backend_id).verify_driver()
        except ValueError:
            skipped.append(f"{backend.backend_id}: unsupported backend verification")
            continue
        missing = missing_verify_tool(driver)
        if missing is not None:
            skipped.append(f"{backend.backend_id}: {missing} not found")
            continue
        backend, profile_skips = filter_emulator_verifiable_profiles(backend, config)
        skipped.extend(profile_skips)
        if not backend.profiles:
            continue
        prepared = driver.prepare_backend(
            root,
            backend,
            config,
            runner,
            results,
            diagnostics,
            skipped,
        )
        if prepared is None or not prepared.profiles:
            continue
        profiles_by_name = {
            profile.profile_name: profile for profile in prepared.profiles
        }
        for group in driver.command_groups(root, prepared, config):
            for command in group:
                result = runner(command)
                results.append(result)
                if result.returncode != 0:
                    diagnostics.append(command_failure_diagnostic(result))
                    break
                driver.after_successful_command(
                    result,
                    profiles_by_name,
                    config,
                    runner,
                    results,
                    diagnostics,
                )

    return BuildVerificationReport(
        commands=tuple(results),
        diagnostics=tuple(diagnostics),
        skipped=tuple(skipped),
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
    for item in command.env:
        environment[item.key] = item.value
    return environment


def _zig_cache_dirs(command_root: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(str(command_root.resolve()).encode("utf-8")).hexdigest()[:16]
    root = command_root.resolve() / ".tslctmp" / "zig-cache" / digest
    local = root / "local"
    global_ = root / "global"
    local.mkdir(parents=True, exist_ok=True)
    global_.mkdir(parents=True, exist_ok=True)
    return local, global_
