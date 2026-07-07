"""Typed verifier backend-driver capability surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from tslc.diagnostics import Diagnostic
from tslc.output._verify_common import (
    command_failure_diagnostic,
    filter_runner_verifiable_profiles,
    missing_executable,
    runner_missing_diagnostic,
)
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
)

PrepareBackend = Callable[
    [
        Path,
        VerifyBackend,
        BuildVerifierConfig,
        BuildCommandRunner,
        list[BuildCommandResult],
        list[Diagnostic],
        list[str],
    ],
    VerifyBackend | None,
]
CommandGroups = Callable[
    [Path, VerifyBackend, BuildVerifierConfig],
    tuple[tuple[BuildCommand, ...], ...],
]
AfterCommand = Callable[
    [
        BuildCommandResult,
        Mapping[str, VerifyProfile],
        BuildVerifierConfig,
        BuildCommandRunner,
        list[BuildCommandResult],
        list[Diagnostic],
    ],
    None,
]


@dataclass(frozen=True, slots=True)
class VerifyBackendDriver:
    backend_id: str
    required_tools: tuple[str, ...]
    prepare_backend: PrepareBackend
    command_groups: CommandGroups
    after_successful_command: AfterCommand


def cpp_verify_driver() -> VerifyBackendDriver:
    from tslc.output._verify_cpp import create_cpp_verify_driver

    return create_cpp_verify_driver()


def rust_verify_driver() -> VerifyBackendDriver:
    from tslc.output._verify_rust import create_rust_verify_driver

    return create_rust_verify_driver()


def missing_verify_tool(driver: VerifyBackendDriver) -> str | None:
    for tool in driver.required_tools:
        if missing_executable(tool) is not None:
            return tool
    return None


__all__ = [
    "AfterCommand",
    "CommandGroups",
    "PrepareBackend",
    "VerifyBackendDriver",
    "command_failure_diagnostic",
    "cpp_verify_driver",
    "filter_runner_verifiable_profiles",
    "missing_verify_tool",
    "runner_missing_diagnostic",
    "rust_verify_driver",
]
