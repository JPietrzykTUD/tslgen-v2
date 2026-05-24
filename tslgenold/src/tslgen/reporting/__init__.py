"""Reporting helpers for the redesigned pipeline."""

from .coverage import (
    BackendCoverageRow,
    DiagnosticCount,
    LegacyCoverageRowAdapterRequest,
    LegacyCoverageSelectedRowFact,
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    SelectionCoverageSummary,
    adapt_legacy_coverage_row,
    build_coverage_report,
    coverage_report_from_pipeline_result,
    coverage_report_to_json,
    legacy_coverage_row_to_json,
    selected_legacy_coverage_request,
    selected_legacy_coverage_row_to_json,
)

__all__ = [
    "BackendCoverageRow",
    "DiagnosticCount",
    "LegacyCoverageRowAdapterRequest",
    "LegacyCoverageSelectedRowFact",
    "PipelineCoverageReport",
    "PrimitiveCoverageRow",
    "SelectionCoverageSummary",
    "adapt_legacy_coverage_row",
    "build_coverage_report",
    "coverage_report_from_pipeline_result",
    "coverage_report_to_json",
    "legacy_coverage_row_to_json",
    "selected_legacy_coverage_request",
    "selected_legacy_coverage_row_to_json",
]
