from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from tslgen.api import (
    PipelineResult,
    coverage_report,
    coverage_report_html,
    coverage_report_json,
    run_pipeline,
    write_artifacts,
)
from tslgen.config.cli_adapter import (
    CliConfig,
    CoverageReportFormat,
    parse_cli_invocation,
)
from tslgen.config.hardware import HardwareFlagProvider, detect_proc_cpuinfo_flags
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.artifacts import ArtifactSet, artifact_digest_map
from tslgen.io.write_report import ArtifactWriteReport


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

    config_result = parse_cli_invocation(
        args,
        hardware_flags_provider=hardware_flags_provider,
    )
    if not config_result.is_ok:
        _write_diagnostics(errors, config_result.diagnostics)
        return 2
    cli_config = config_result.unwrap()

    result = run_pipeline(cli_config.pipeline_config)
    if result.diagnostics:
        _write_diagnostics(errors, result.diagnostics)

    if cli_config.coverage_report_format is not None:
        _write_coverage_report(output, result, cli_config.coverage_report_format)

    if not result.is_ok:
        return 1

    if cli_config.output_root is not None:
        write_report = _write_pipeline_artifacts(cli_config, result.artifacts)
        if write_report.diagnostics:
            _write_diagnostics(errors, write_report.diagnostics)
        if cli_config.coverage_report_format is None:
            _write_write_report(output, write_report)
        return 0 if write_report.is_ok else 1

    if result.artifacts is not None and cli_config.coverage_report_format is None:
        _write_artifact_digests(output, result.artifacts)
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


def _write_coverage_report(
    stream: TextIO,
    result: PipelineResult,
    report_format: CoverageReportFormat,
) -> None:
    report = coverage_report(result)
    if report_format == "json":
        print(coverage_report_json(report), end="", file=stream)
    else:
        print(coverage_report_html(report), end="", file=stream)


def _write_pipeline_artifacts(
    cli_config: CliConfig,
    artifacts: ArtifactSet | None,
) -> ArtifactWriteReport:
    if artifacts is None:
        diagnostic = Diagnostic.error(
            "TSL-CLI-WRITE-NO-ARTIFACTS",
            "--output-root was requested but the pipeline produced no artifacts",
        )
        assert cli_config.output_root is not None
        return ArtifactWriteReport(
            output_root=Path(cli_config.output_root),
            dry_run=cli_config.write_dry_run,
            skip_unchanged=cli_config.write_skip_unchanged,
            records=(),
            report_diagnostics=(diagnostic,),
        )
    assert cli_config.output_root is not None
    return write_artifacts(
        artifacts,
        cli_config.output_root,
        dry_run=cli_config.write_dry_run,
        skip_unchanged=cli_config.write_skip_unchanged,
    )


def _write_artifact_digests(stream: TextIO, artifacts: ArtifactSet) -> None:
    for logical_path, digest in artifact_digest_map(artifacts).items():
        print(f"{logical_path} {digest}", file=stream)


def _write_write_report(stream: TextIO, report: ArtifactWriteReport) -> None:
    for record in report.records:
        print(
            f"{record.status} {record.logical_path.as_posix()} {record.digest}",
            file=stream,
        )


def _format_location(location: SourceLocation | None) -> str:
    if location is None:
        return ""
    return (
        f"{location.path.as_posix()}:{location.line}:"
        f"{location.column}"
    )


if __name__ == "__main__":
    raise SystemExit(run())
