"""Typed model values for generated-project verification."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
import shlex
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
    # C++ extra compile flags (e.g. ("-mavx2",)); Rust target features (e.g. ("+avx2",)).
    cpp_flags: tuple[str, ...] = ()
    cpp_target: str | None = None
    rust_target_features: tuple[str, ...] = ()
    rust_target: str | None = None
    rust_linker: str | None = None
    # Optional emulator profile used to run value tests for this profile.
    emulator: VerifyEmulator | None = None


@dataclass(frozen=True, slots=True)
class VerifyBackend:
    backend_id: str
    root_path: str
    profiles: tuple[VerifyProfile, ...]


@dataclass(frozen=True, slots=True)
class VerifyProject:
    backends: tuple[VerifyBackend, ...]


@dataclass(frozen=True, slots=True)
class BuildVerifierConfig:
    """Optional toolchain configuration for after-write verification."""

    cpp_compiler: tuple[str, ...] | None = None
    rust_compiler: str | None = None
    run_value_tests: bool = False
    sde_path: str | None = None
    qemu_aarch64_path: str | None = None
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


__all__ = [
    "BuildCommand",
    "BuildCommandEnvironment",
    "BuildCommandResult",
    "BuildCommandRunner",
    "BuildVerificationReport",
    "BuildVerifierConfig",
    "VerifyBackend",
    "VerifyEmulator",
    "VerifyProfile",
    "VerifyProject",
]
