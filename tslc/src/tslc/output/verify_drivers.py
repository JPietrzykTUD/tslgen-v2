"""Typed verifier backend-driver capability surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from tslc.diagnostics import Diagnostic
from tslc.output._verify_common import (
    command_failure_diagnostic,
    missing_executable,
)
from tslc.output._verify_runners import (
    filter_runner_verifiable_profiles,
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
PrepareCommandEnvironment = Callable[[BuildCommand, dict[str, str]], None]


def _keep_command_environment(
    command: BuildCommand, environment: dict[str, str]
) -> None:
    del command, environment


@dataclass(frozen=True, slots=True)
class VerifyBackendDriver:
    backend_id: str
    required_tools: tuple[str, ...]
    prepare_backend: PrepareBackend
    command_groups: CommandGroups
    after_successful_command: AfterCommand
    prepare_command_environment: PrepareCommandEnvironment = _keep_command_environment


def missing_verify_tool(driver: VerifyBackendDriver) -> str | None:
    for tool in driver.required_tools:
        if missing_executable(tool) is not None:
            return tool
    return None


__all__ = [
    "AfterCommand",
    "CommandGroups",
    "PrepareBackend",
    "PrepareCommandEnvironment",
    "VerifyBackendDriver",
    "command_failure_diagnostic",
    "filter_runner_verifiable_profiles",
    "missing_verify_tool",
    "runner_missing_diagnostic",
]
