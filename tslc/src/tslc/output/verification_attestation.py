"""Versioned run evidence for one exact generated-project identity."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from tslc.diagnostics import Diagnostic, diagnostic_json
from tslc.output.verify_model import BuildCommandResult

ATTESTATION_LOGICAL_PATH = ".tslctmp/verification/attestation.json"
ATTESTATION_SCHEMA_VERSION = 1
_ARTIFACT_MANIFEST_LOGICAL_PATH = ".tslc-manifest.json"


def write_verification_attestation(
    output_root: Path,
    *,
    input_digest: str,
    commands: Sequence[BuildCommandResult],
    diagnostics: Sequence[Diagnostic],
    skipped: Sequence[str],
    recorded_at_utc: datetime | None = None,
) -> tuple[Path | None, Diagnostic | None]:
    """Write mutable run evidence separately from deterministic artifacts."""

    root = output_root.resolve()
    artifact_manifest = root / _ARTIFACT_MANIFEST_LOGICAL_PATH
    try:
        artifact_manifest_bytes = artifact_manifest.read_bytes()
    except OSError as error:
        return None, Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-ATTESTATION-IDENTITY",
            message=(
                "could not read generated artifact manifest for verification "
                f"attestation: {error}"
            ),
        )

    recorded_at = recorded_at_utc or datetime.now(timezone.utc)
    payload = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "identity": {
            "input_digest": input_digest,
            "artifact_manifest": {
                "logical_path": _ARTIFACT_MANIFEST_LOGICAL_PATH,
                "sha256": sha256(artifact_manifest_bytes).hexdigest(),
            },
        },
        "run": {
            "recorded_at_utc": recorded_at.astimezone(timezone.utc).isoformat(),
            "outcome": _run_outcome(commands, diagnostics, skipped),
            "commands": [_command_record(result) for result in commands],
            "skipped": list(skipped),
            "diagnostics": [diagnostic_json(item) for item in diagnostics],
        },
    }
    target = root.joinpath(*Path(ATTESTATION_LOGICAL_PATH).parts)
    temporary = target.with_suffix(".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError as error:
        return None, Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-ATTESTATION-WRITE",
            message=f"could not write verification attestation {target}: {error}",
        )
    return target, None


def _run_outcome(
    commands: Sequence[BuildCommandResult],
    diagnostics: Sequence[Diagnostic],
    skipped: Sequence[str],
) -> str:
    if any(not result.matches_expectation for result in commands) or any(
        item.severity in {"error", "warning"} for item in diagnostics
    ):
        return "failed"
    if skipped:
        return "incomplete"
    return "passed"


def _command_record(result: BuildCommandResult) -> dict[str, object]:
    command = result.command
    variant = command.runner_variant
    return {
        "backend": command.backend_id,
        "profile": command.profile_name,
        "step": command.step,
        "argv": list(command.argv),
        "cwd": str(command.cwd.resolve()),
        "environment": [
            {"key": item.key, "value": item.value} for item in command.env
        ],
        "expected_failure_marker": command.expected_failure_marker,
        "runner": (
            None
            if variant is None
            else {
                "kind": command.runner_kind,
                "name": variant.name,
                "profile": variant.profile,
                "args": list(variant.args),
                "vector_bits": variant.vector_bits,
            }
        ),
        "timeout_seconds": command.timeout_seconds,
        "result": {
            "returncode": result.returncode,
            "matches_expectation": result.matches_expectation,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    }


__all__ = (
    "ATTESTATION_LOGICAL_PATH",
    "ATTESTATION_SCHEMA_VERSION",
    "write_verification_attestation",
)
