"""Reporting helpers for the redesigned pipeline."""

from .coverage import (
    BackendCoverageRow,
    DiagnosticCount,
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    SelectionCoverageSummary,
    build_coverage_report,
    coverage_report_from_pipeline_result,
    coverage_report_to_json,
)

__all__ = [
    "BackendCoverageRow",
    "DiagnosticCount",
    "PipelineCoverageReport",
    "PrimitiveCoverageRow",
    "SelectionCoverageSummary",
    "build_coverage_report",
    "coverage_report_from_pipeline_result",
    "coverage_report_to_json",
]
