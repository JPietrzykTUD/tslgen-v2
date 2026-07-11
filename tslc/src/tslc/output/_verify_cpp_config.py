"""C++ toolchain configuration for generated-project verification."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil

from tslc.output._verify_runners import runner_prefix
from tslc.output.verify_model import (
    BuildCommandEnvironment,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
)

_ONEAPI_CPP_COMPILER = "/opt/intel/oneapi/compiler/2025.0/bin/icpx"
_AARCH64_GNU_CPP_COMPILER = "aarch64-linux-gnu-g++"
_AARCH64_GNU_CPP_DRIVER_PREFIXES = ("aarch64-linux-gnu-",)


def cpp_target(profile: VerifyProfile, config: BuildVerifierConfig) -> str | None:
    return config.toolchain("cpp").target or profile.target


def cmake_cross_emulator(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if profile.runner is None or profile.runner.kind != "qemu-aarch64":
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
        return ("/opt/wasi-sdk/bin/clang++",)
    if backend is not None and backend.profiles and all(
        _needs_oneapi_cpp_compiler(candidate) for candidate in backend.profiles
    ):
        return (_ONEAPI_CPP_COMPILER,)
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
    if _is_wasm_cpp_target(profile, config):
        return ("/opt/wasi-sdk/bin/clang++",)
    if _is_default_aarch64_gnu_cpp_target(profile, config):
        compiler = _aarch64_gnu_cpp_compiler()
        if compiler is not None:
            return compiler
    if cpp_target(profile, config) is not None:
        return ("clang++",)
    if _needs_oneapi_cpp_compiler(profile):
        return (_ONEAPI_CPP_COMPILER,)
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


def _needs_oneapi_cpp_compiler(profile: VerifyProfile) -> bool:
    return "oneapi_fpga" in profile.compile_modes


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
    "cpp_target",
    "effective_cpp_compiler",
)
