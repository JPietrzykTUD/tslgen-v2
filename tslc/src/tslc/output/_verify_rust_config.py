"""Rust toolchain configuration for generated-project verification."""

from __future__ import annotations

import os

from tslc.output.verify_model import (
    BuildCommandEnvironment,
    BuildVerifierConfig,
    ToolchainCommands,
    VerifyProfile,
    _normalize_compiler_executable,
)


def rust_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.toolchain("rust").target or profile.target


def rust_linker(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.toolchain("rust").linker or profile.linker


def rust_toolchain_commands(
    profile: VerifyProfile, config: BuildVerifierConfig
) -> ToolchainCommands:
    return ToolchainCommands(
        compiler=(effective_rust_compiler(config),),
        target=rust_target(profile, config),
        linker=rust_linker(profile, config),
    )


def rust_target_args(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    target = rust_target(profile, config)
    return ("--target", target) if target is not None else ()


def effective_rust_compiler(config: BuildVerifierConfig) -> str:
    configured = config.toolchain("rust").compiler
    if configured is not None:
        return configured[0]
    ambient = os.environ.get("RUSTC")
    if ambient:
        normalized = _normalize_compiler_executable(ambient)
        if normalized is not None:
            return normalized
    return "rustc"


def rust_environment(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[BuildCommandEnvironment, ...]:
    environment: list[BuildCommandEnvironment] = []
    configured_compiler = config.toolchain("rust").compiler
    if configured_compiler is not None:
        environment.append(
            BuildCommandEnvironment(key="RUSTC", value=configured_compiler[0])
        )
    target = rust_target(profile, config)
    linker = rust_linker(profile, config)
    if target is not None and linker is not None:
        environment.append(
            BuildCommandEnvironment(
                key=f"CARGO_TARGET_{cargo_target_env(target)}_LINKER",
                value=linker,
            )
        )
    if profile.target_features:
        joined = ",".join(profile.target_features)
        environment.append(
            BuildCommandEnvironment(
                key="RUSTFLAGS",
                value=f"-C target-feature={joined}",
            )
        )
    return tuple(environment)


def cargo_target_env(target: str) -> str:
    return target.upper().replace("-", "_")


__all__ = (
    "effective_rust_compiler",
    "rust_environment",
    "rust_linker",
    "rust_target",
    "rust_target_args",
    "rust_toolchain_commands",
)
