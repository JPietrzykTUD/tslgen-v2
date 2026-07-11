"""Backend-neutral executable and command-result verification helpers."""

from __future__ import annotations

import shutil

from tslc.diagnostics import Diagnostic
from tslc.output.verify_model import BuildCommandResult


def missing_executable(executable: str) -> str | None:
    return executable if shutil.which(executable) is None else None


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
