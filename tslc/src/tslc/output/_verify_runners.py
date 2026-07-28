"""Runner selection and command prefixes shared by verifier drivers."""

from __future__ import annotations

from pathlib import Path

from tslc.diagnostics import Diagnostic
from tslc.output._verify_common import missing_executable
from tslc.output.verify_model import BuildVerifierConfig, VerifyBackend, VerifyProfile

_AARCH64_QEMU_SYSROOT = Path("/usr/aarch64-linux-gnu")


def runner_missing_diagnostic(config: BuildVerifierConfig) -> Diagnostic | None:
    if not config.run_value_tests:
        return None
    for kind, executable in config.runner_paths.items():
        missing = missing_executable(executable)
        if missing is not None:
            return Diagnostic(
                severity="error",
                code="TSL-BUILD-VERIFY-RUNNER-MISSING",
                message=f"{kind} runner executable {missing} not found",
            )
    return None


def filter_runner_verifiable_profiles(
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[VerifyBackend, tuple[str, ...]]:
    configured = configured_runner_kinds(config)
    if not config.run_value_tests:
        return backend, ()

    profiles: list[VerifyProfile] = []
    skipped: list[str] = []
    for profile in backend.profiles:
        if profile.runner is None:
            if not profile.native_without_runner:
                skipped.append(
                    f"{backend.backend_id}: profile {profile.profile_name} has no "
                    "runner metadata; value-test verification skipped"
                )
            else:
                profiles.append(profile)
            continue
        if profile.runner.kind not in configured:
            skipped.append(
                f"{backend.backend_id}: profile {profile.profile_name} requires "
                f"{profile.runner.kind}, but that runner is not configured; "
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


def configured_runner_kinds(config: BuildVerifierConfig) -> frozenset[str]:
    return frozenset(config.runner_paths)


def runner_prefix(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    runner = profile.runner
    if runner is None:
        return ()
    executable = config.runner_path(runner.kind)
    if executable is None:
        return ()
    if runner.kind == "sde":
        return (executable, f"-{runner.profile}", *runner.args, "--")
    if runner.kind == "qemu-aarch64":
        return (
            executable,
            *_qemu_aarch64_sysroot_args(runner.args),
            "-cpu",
            runner.profile,
            *runner.args,
        )
    if runner.kind == "wasmtime":
        return (executable, *runner.args)
    return ()


def _qemu_aarch64_sysroot_args(
    runner_args: tuple[str, ...],
) -> tuple[str, ...]:
    if any(arg == "-L" or arg.startswith("-L") for arg in runner_args):
        return ()
    loader = _AARCH64_QEMU_SYSROOT / "lib" / "ld-linux-aarch64.so.1"
    if not loader.is_file():
        return ()
    return ("-L", str(_AARCH64_QEMU_SYSROOT))


__all__ = (
    "configured_runner_kinds",
    "filter_runner_verifiable_profiles",
    "runner_missing_diagnostic",
    "runner_prefix",
)
