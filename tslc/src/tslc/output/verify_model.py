"""Typed model values for generated-project verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
import shlex
from types import MappingProxyType
from typing import Protocol

from tslc.diagnostics import Diagnostic, Severity


@dataclass(frozen=True, slots=True)
class VerifyRunnerVariant:
    """One exact runner configuration used to execute a built artifact."""

    name: str
    profile: str
    args: tuple[str, ...] = ()
    vector_bits: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "profile", self.profile.strip())
        object.__setattr__(self, "args", tuple(self.args))
        _require_runner_variant(self.name, self.profile, self.vector_bits)


@dataclass(frozen=True, slots=True)
class VerifyRunner:
    kind: str  # Validated against the profile family's declared runner kinds.
    profile: str
    args: tuple[str, ...] = ()
    name: str = "default"
    vector_bits: int | None = None
    variants: tuple[VerifyRunnerVariant, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", self.kind.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "profile", self.profile.strip())
        if not self.kind.strip():
            raise ValueError("runner kind must be non-empty")
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "variants", tuple(self.variants))
        _require_runner_variant(self.name, self.profile, self.vector_bits)
        names = tuple(execution.name for execution in self.executions)
        if len(set(names)) != len(names):
            raise ValueError("runner execution names must be unique")

    @property
    def executions(self) -> tuple[VerifyRunnerVariant, ...]:
        return (
            VerifyRunnerVariant(
                name=self.name,
                profile=self.profile,
                args=self.args,
                vector_bits=self.vector_bits,
            ),
            *self.variants,
        )


def _require_runner_variant(
    name: str,
    profile: str,
    vector_bits: int | None,
) -> None:
    if len(name.split()) != 1:
        raise ValueError("runner execution name must be one token")
    if not profile.strip() or profile.strip().startswith("-"):
        raise ValueError("runner profile must be non-empty and must not start with '-'")
    if vector_bits is not None and (
        isinstance(vector_bits, bool)
        or not isinstance(vector_bits, int)
        or vector_bits <= 0
    ):
        raise ValueError("runner vector_bits must be a positive integer")


@dataclass(frozen=True, slots=True)
class VerifyCompileFailure:
    """One isolated target that must fail compilation for an exact marker."""

    target_name: str
    marker: str


@dataclass(frozen=True, slots=True)
class VerifyProfile:
    profile_name: str
    file_stem: str
    family: str = "generic"
    native_without_runner: bool = False
    compile_modes: frozenset[str] = frozenset()
    flags: tuple[str, ...] = ()
    target_features: tuple[str, ...] = ()
    target: str | None = None
    linker: str | None = None
    compiler_role: str | None = None
    cmake_system_name: str | None = None
    cmake_system_processor: str | None = None
    pass_target_to_compiler: bool = True
    preflight_headers: tuple[str, ...] = ()
    # Optional runner profile used to run value tests for this profile.
    runner: VerifyRunner | None = None
    compile_failures: tuple[VerifyCompileFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class VerifyBackend:
    backend_id: str
    root_path: str
    profiles: tuple[VerifyProfile, ...]


@dataclass(frozen=True, slots=True)
class VerifyProject:
    backends: tuple[VerifyBackend, ...]
    input_digest: str | None = None


@dataclass(frozen=True, slots=True)
class BackendToolchain:
    """Caller-supplied toolchain overrides for one registered backend."""

    compiler: tuple[str, ...] | None = None
    target: str | None = None
    linker: str | None = None
    compiler_capabilities: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        compiler: str | Sequence[str] | None = None,
        target: str | None = None,
        linker: str | None = None,
        compiler_capabilities: Sequence[str] = (),
    ) -> "BackendToolchain":
        return cls(
            compiler=_normalize_compiler_command(compiler),
            target=_normalize_compiler_executable(target),
            linker=_normalize_compiler_executable(linker),
            compiler_capabilities=_normalize_capabilities(compiler_capabilities),
        )


@dataclass(frozen=True, slots=True)
class ToolchainCommands:
    """The effective compiler invocation, target, and linker for one verify profile."""

    compiler: tuple[str, ...]
    target: str | None
    linker: str | None


@dataclass(frozen=True, slots=True)
class BuildVerifierConfig:
    """Backend-keyed toolchain and runner configuration for verification."""

    toolchains: Mapping[str, BackendToolchain] = field(default_factory=dict)
    runner_paths: Mapping[str, str] = field(default_factory=dict)
    tool_paths: Mapping[str, str] = field(default_factory=dict)
    run_value_tests: bool = False
    run_quality_checks: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "toolchains",
            MappingProxyType(dict(sorted(self.toolchains.items()))),
        )
        object.__setattr__(
            self,
            "runner_paths",
            MappingProxyType(dict(sorted(self.runner_paths.items()))),
        )
        object.__setattr__(
            self,
            "tool_paths",
            MappingProxyType(dict(sorted(self.tool_paths.items()))),
        )

    @classmethod
    def create(
        cls,
        *,
        toolchains: Mapping[str, BackendToolchain] | None = None,
        runner_paths: Mapping[str, str] | None = None,
        tool_paths: Mapping[str, str] | None = None,
        run_value_tests: bool = False,
        run_quality_checks: bool = False,
    ) -> "BuildVerifierConfig":
        return cls(
            toolchains=toolchains or {},
            runner_paths={
                kind: normalized
                for kind, path in (runner_paths or {}).items()
                if (normalized := _normalize_compiler_executable(path)) is not None
            },
            tool_paths={
                role: normalized
                for role, path in (tool_paths or {}).items()
                if (normalized := _normalize_compiler_executable(path)) is not None
            },
            run_value_tests=run_value_tests,
            run_quality_checks=run_quality_checks,
        )

    def toolchain(self, backend_id: str) -> BackendToolchain:
        return self.toolchains.get(backend_id, BackendToolchain())

    def runner_path(self, kind: str) -> str | None:
        return self.runner_paths.get(kind)

    def tool_path(self, role: str) -> str | None:
        return self.tool_paths.get(role)


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
    severity_on_failure: Severity = "error"
    expected_failure_marker: str | None = None
    runner_kind: str | None = None
    runner_variant: VerifyRunnerVariant | None = None
    timeout_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class BuildCommandResult:
    command: BuildCommand
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def matches_expectation(self) -> bool:
        marker = self.command.expected_failure_marker
        if marker is None:
            return self.returncode == 0
        return self.returncode != 0 and marker in f"{self.stdout}\n{self.stderr}"


@dataclass(frozen=True, slots=True)
class BuildVerificationReport:
    commands: tuple[BuildCommandResult, ...]
    diagnostics: tuple[Diagnostic, ...]
    skipped: tuple[str, ...] = field(default=())
    attestation_path: Path | None = None


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


def _normalize_capabilities(capabilities: Sequence[str]) -> tuple[str, ...]:
    normalized = {
        str(capability).strip()
        for capability in capabilities
        if str(capability).strip()
    }
    return tuple(sorted(normalized))


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
    "BackendToolchain",
    "ToolchainCommands",
    "VerifyBackend",
    "VerifyCompileFailure",
    "VerifyProfile",
    "VerifyProject",
    "VerifyRunner",
    "VerifyRunnerVariant",
]
