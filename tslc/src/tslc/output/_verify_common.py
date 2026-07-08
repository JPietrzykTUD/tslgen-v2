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


def runner_missing_diagnostic(config: BuildVerifierConfig) -> Diagnostic | None:
    if not config.run_value_tests:
        return None
    for kind, executable in (
        ("sde", config.sde_path),
        ("qemu-aarch64", config.qemu_aarch64_path),
        ("wasmtime", config.wasmtime_path),
    ):
        if executable is None:
            continue
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
    if not configured or not config.run_value_tests:
        return backend, ()

    profiles: list[VerifyProfile] = []
    skipped: list[str] = []
    for profile in backend.profiles:
        if profile.runner is None:
            if profile.family != "generic":
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
    configured: set[str] = set()
    if config.sde_path is not None:
        configured.add("sde")
    if config.qemu_aarch64_path is not None:
        configured.add("qemu-aarch64")
    if config.wasmtime_path is not None:
        configured.add("wasmtime")
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
    if profile.runner is None or profile.runner.kind != "qemu-aarch64":
        return ()
    return runner_prefix(profile, config)


def runner_prefix(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    runner = profile.runner
    if runner is None:
        return ()
    if runner.kind == "sde":
        if config.sde_path is None:
            return ()
        return (config.sde_path, f"-{runner.profile}", *runner.args, "--")
    if runner.kind == "qemu-aarch64":
        if config.qemu_aarch64_path is None:
            return ()
        return (config.qemu_aarch64_path, "-cpu", runner.profile, *runner.args)
    if runner.kind == "wasmtime":
        if config.wasmtime_path is None:
            return ()
        return (config.wasmtime_path, *runner.args)
    return ()


def effective_cpp_compiler(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
    profile: VerifyProfile | None = None,
) -> tuple[str, ...]:
    if config.cpp_compiler is not None:
        return config.cpp_compiler
    if profile is not None:
        return _effective_cpp_compiler_for_profile(config, profile)
    if backend is not None and backend.profiles and all(
        _is_wasm_cpp_target(candidate, config) for candidate in backend.profiles
    ):
        return ("/opt/wasi-sdk/bin/clang++",)
    if backend is not None and any(cpp_target(profile, config) for profile in backend.profiles):
        return ("clang++",)
    return _native_cpp_compiler()


def _effective_cpp_compiler_for_profile(
    config: BuildVerifierConfig,
    profile: VerifyProfile,
) -> tuple[str, ...]:
    if _is_wasm_cpp_target(profile, config):
        return ("/opt/wasi-sdk/bin/clang++",)
    if cpp_target(profile, config) is not None:
        return ("clang++",)
    if (
        config.run_value_tests
        and config.sde_path is not None
        and profile.runner is not None
        and profile.runner.kind == "sde"
    ):
        return ("c++",)
    return _native_cpp_compiler()


def _native_cpp_compiler() -> tuple[str, ...]:
    parsed = _ambient_cpp_compiler()
    if parsed:
        # The CI/devcontainer environment exposes Zig through CXX for cross
        # builds. Zig is not the native host compiler unless the caller asks for
        # it explicitly through BuildVerifierConfig/--cpp-compiler.
        if not _is_zig_driver(parsed[0]):
            return parsed
    return ("c++",)


def _is_wasm_cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> bool:
    target = cpp_target(profile, config)
    return target is not None and target.startswith("wasm32-")


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
    profile: VerifyProfile | None = None,
) -> tuple[BuildCommandEnvironment, ...]:
    compiler = effective_cpp_compiler(config, backend, profile)
    if config.cpp_compiler is None and not (
        profile is not None and cpp_target(profile, config) is not None
    ) and not (
        profile is None
        and backend is not None
        and any(cpp_target(candidate, config) for candidate in backend.profiles)
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
