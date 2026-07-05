"""Shared helpers for build verifier driver modules."""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

from tslc.diagnostics import Diagnostic
from tslc.output.verify_model import (
    BuildCommandEnvironment,
    BuildCommandResult,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
    _normalize_compiler_executable,
)


def missing_executable(executable: str) -> str | None:
    return executable if shutil.which(executable) is None else None


def emulator_missing_diagnostic(config: BuildVerifierConfig) -> Diagnostic | None:
    if not config.run_value_tests:
        return None
    for kind, executable in (
        ("sde", config.sde_path),
        ("qemu-aarch64", config.qemu_aarch64_path),
    ):
        if executable is None:
            continue
        missing = missing_executable(executable)
        if missing is not None:
            return Diagnostic(
                severity="error",
                code="TSL-BUILD-VERIFY-EMULATOR-MISSING",
                message=f"{kind} emulator executable {missing} not found",
            )
    return None


def filter_emulator_verifiable_profiles(
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[VerifyBackend, tuple[str, ...]]:
    configured = configured_emulator_kinds(config)
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


def configured_emulator_kinds(config: BuildVerifierConfig) -> frozenset[str]:
    configured: set[str] = set()
    if config.sde_path is not None:
        configured.add("sde")
    if config.qemu_aarch64_path is not None:
        configured.add("qemu-aarch64")
    return frozenset(configured)


def cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.cpp_target or profile.cpp_target


def rust_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.rust_target or profile.rust_target


def rust_linker(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.rust_linker or profile.rust_linker


def rust_target_args(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    target = rust_target(profile, config)
    return ("--target", target) if target is not None else ()


def cmake_cross_emulator(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if profile.emulator is None or profile.emulator.kind != "qemu-aarch64":
        return ()
    return emulator_prefix(profile, config)


def emulator_prefix(
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


def effective_cpp_compiler(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
) -> tuple[str, ...]:
    if config.cpp_compiler is not None:
        return config.cpp_compiler
    if backend is not None and any(cpp_target(profile, config) for profile in backend.profiles):
        return ("clang++",)
    parsed = _ambient_cpp_compiler()
    if parsed:
        # The CI/devcontainer environment exposes Zig through CXX for cross
        # builds. Zig is not the native host compiler unless the caller asks for
        # it explicitly through BuildVerifierConfig/--cpp-compiler.
        if not _is_zig_driver(parsed[0]):
            return parsed
    return ("c++",)


def _ambient_cpp_compiler() -> tuple[str, ...]:
    ambient = os.environ.get("CXX")
    if not ambient:
        return ()
    return tuple(shlex.split(ambient))


def _is_zig_driver(executable: str) -> bool:
    return Path(executable).name == "zig"


def effective_rust_compiler(config: BuildVerifierConfig) -> str:
    if config.rust_compiler is not None:
        return config.rust_compiler
    ambient = os.environ.get("RUSTC")
    if ambient:
        normalized = _normalize_compiler_executable(ambient)
        if normalized is not None:
            return normalized
    return "rustc"


def cpp_environment(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
) -> tuple[BuildCommandEnvironment, ...]:
    compiler = effective_cpp_compiler(config, backend)
    if config.cpp_compiler is None and not (
        backend is not None and any(cpp_target(profile, config) for profile in backend.profiles)
    ):
        ambient = _ambient_cpp_compiler()
        if ambient == compiler:
            return ()
    return (
        BuildCommandEnvironment(
            key="CXX",
            value=shlex.join(compiler),
        ),
    )


def rust_environment(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[BuildCommandEnvironment, ...]:
    environment: list[BuildCommandEnvironment] = []
    if config.rust_compiler is not None:
        environment.append(BuildCommandEnvironment(key="RUSTC", value=config.rust_compiler))
    target = rust_target(profile, config)
    linker = rust_linker(profile, config)
    if target is not None and linker is not None:
        environment.append(
            BuildCommandEnvironment(
                key=f"CARGO_TARGET_{cargo_target_env(target)}_LINKER",
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


def cargo_target_env(target: str) -> str:
    return target.upper().replace("-", "_")


def command_failure_diagnostic(result: BuildCommandResult) -> Diagnostic:
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
