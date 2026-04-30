from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from tslgen.api import run_pipeline
from tslgen.config.cli_adapter import parse_cli_config
from tslgen.config.hardware import HardwareFlagProvider, detect_proc_cpuinfo_flags
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.artifacts import artifact_digest_map


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    hardware_flags_provider: HardwareFlagProvider = detect_proc_cpuinfo_flags,
) -> int:
    output = stdout if stdout is not None else sys.stdout
    errors = stderr if stderr is not None else sys.stderr
    args = tuple(sys.argv[1:] if argv is None else argv)

    config_result = parse_cli_config(
        args,
        hardware_flags_provider=hardware_flags_provider,
    )
    if not config_result.is_ok:
        _write_diagnostics(errors, config_result.diagnostics)
        return 2

    result = run_pipeline(config_result.unwrap())
    if result.diagnostics:
        _write_diagnostics(errors, result.diagnostics)
    if not result.is_ok:
        return 1

    if result.artifacts is not None:
        for logical_path, digest in artifact_digest_map(result.artifacts).items():
            print(f"{logical_path} {digest}", file=output)
    return 0


def format_diagnostic(diagnostic: Diagnostic) -> str:
    location = _format_location(diagnostic.location)
    prefix = f"{location}: " if location else ""
    return (
        f"{prefix}{diagnostic.severity}: {diagnostic.code}: "
        f"{diagnostic.message}"
    )


def _write_diagnostics(stream: TextIO, diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        print(format_diagnostic(diagnostic), file=stream)


def _format_location(location: SourceLocation | None) -> str:
    if location is None:
        return ""
    return (
        f"{location.path.as_posix()}:{location.line}:"
        f"{location.column}"
    )


if __name__ == "__main__":
    raise SystemExit(run())
