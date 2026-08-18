"""C++ toolchain configuration for generated-project verification."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil

from tslc.output._verify_runners import is_cmake_cross_emulator, runner_prefix
from tslc.output.verify_model import (
    BuildCommandEnvironment,
    BuildVerifierConfig,
    ToolchainCommands,
    VerifyBackend,
    VerifyProfile,
)

_AARCH64_GNU_CPP_COMPILER = "aarch64-linux-gnu-g++"
_AARCH64_GNU_CPP_DRIVER_PREFIXES = ("aarch64-linux-gnu-",)
_CPP_COMPILER_ROLE_DEFAULTS = {"oneapi-cpp": "icpx"}


def cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.toolchain("cpp").target or profile.target


def cpp_linker(config: BuildVerifierConfig) -> str | None:
    return config.toolchain("cpp").linker


def cpp_toolchain_commands(
    profile: VerifyProfile, config: BuildVerifierConfig
) -> ToolchainCommands:
    return ToolchainCommands(
        compiler=effective_cpp_compiler(config, profile=profile),
        target=cpp_target(profile, config),
        linker=cpp_linker(config),
    )


def cmake_cross_emulator(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if (
        profile.runner is None
        or not is_cmake_cross_emulator(profile.runner.kind)
    ):
        return ()
    return runner_prefix(profile, config)


def effective_cpp_compiler(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
    profile: VerifyProfile | None = None,
) -> tuple[str, ...]:
    configured_compiler = config.toolchain("cpp").compiler
    if configured_compiler is not None:
        return configured_compiler
    if profile is not None:
        return _effective_cpp_compiler_for_profile(config, profile)
    if backend is not None and backend.profiles and all(
        _is_wasm_cpp_target(candidate, config) for candidate in backend.profiles
    ):
        return (config.tool_path("wasi-cpp") or "clang++",)
    compiler_roles = {
        candidate.compiler_role
        for candidate in (() if backend is None else backend.profiles)
    }
    if len(compiler_roles) == 1 and None not in compiler_roles:
        role = next(iter(compiler_roles))
        assert role is not None
        return (_compiler_for_role(role, config),)
    if backend is not None and backend.profiles and all(
        _is_default_aarch64_gnu_cpp_target(candidate, config)
        for candidate in backend.profiles
    ):
        compiler = _aarch64_gnu_cpp_compiler()
        if compiler is not None:
            return compiler
    if backend is not None and any(
        cpp_target(candidate, config) for candidate in backend.profiles
    ):
        return ("clang++",)
    return _native_cpp_compiler()


def _effective_cpp_compiler_for_profile(
    config: BuildVerifierConfig,
    profile: VerifyProfile,
) -> tuple[str, ...]:
    if profile.compiler_role is not None:
        return (_compiler_for_role(profile.compiler_role, config),)
    if _is_wasm_cpp_target(profile, config):
        return (config.tool_path("wasi-cpp") or "clang++",)
    if _is_default_aarch64_gnu_cpp_target(profile, config):
        compiler = _aarch64_gnu_cpp_compiler()
        if compiler is not None:
            return compiler
    if cpp_target(profile, config) is not None:
        return ("clang++",)
    if (
        config.run_value_tests
        and config.runner_path("sde") is not None
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
        # it explicitly through BuildVerifierConfig/--compiler cpp=COMMAND.
        if not _is_zig_driver(parsed[0]):
            return parsed
    return ("c++",)


def _is_wasm_cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> bool:
    target = cpp_target(profile, config)
    return target is not None and target.startswith("wasm32-")


def _is_default_aarch64_gnu_cpp_target(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> bool:
    target = cpp_target(profile, config)
    return (
        target is not None
        and target.startswith("aarch64-linux-gnu")
        and profile.runner is not None
        and profile.runner.kind == "qemu-aarch64"
    )


def _aarch64_gnu_cpp_compiler() -> tuple[str, ...] | None:
    if shutil.which(_AARCH64_GNU_CPP_COMPILER) is None:
        return None
    return (_AARCH64_GNU_CPP_COMPILER,)


def cpp_compiler_accepts_explicit_target(compiler: tuple[str, ...]) -> bool:
    if not compiler:
        return True
    executable = Path(compiler[0]).name
    return not executable.startswith(_AARCH64_GNU_CPP_DRIVER_PREFIXES)


def _compiler_for_role(role: str, config: BuildVerifierConfig) -> str:
    return (
        config.tool_path(role)
        or _CPP_COMPILER_ROLE_DEFAULTS.get(role)
        or role
    )


def _ambient_cpp_compiler() -> tuple[str, ...]:
    ambient = os.environ.get("CXX")
    if not ambient:
        return ()
    return tuple(shlex.split(ambient))


def _is_zig_driver(executable: str) -> bool:
    return Path(executable).name == "zig"


def cpp_environment(
    config: BuildVerifierConfig,
    backend: VerifyBackend | None = None,
    profile: VerifyProfile | None = None,
) -> tuple[BuildCommandEnvironment, ...]:
    compiler = effective_cpp_compiler(config, backend, profile)
    if config.toolchain("cpp").compiler is None and not (
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


__all__ = (
    "cmake_cross_emulator",
    "cpp_compiler_accepts_explicit_target",
    "cpp_environment",
    "cpp_linker",
    "cpp_target",
    "cpp_toolchain_commands",
    "effective_cpp_compiler",
)
