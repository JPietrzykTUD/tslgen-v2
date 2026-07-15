"""Isolated PIVOT YAML export support.

PIVOT is an explicit corpus projection, not a registered generated backend.
Ordinary C++/Rust generation never imports or invokes this package.
"""

from tslc.pivot.exporter import PivotExportRequest, export_pivot
from tslc.pivot.model import (
    PivotDefinition,
    PivotDocument,
    PivotExportResult,
    PivotSkip,
)

__all__ = (
    "PivotDefinition",
    "PivotDocument",
    "PivotExportRequest",
    "PivotExportResult",
    "PivotSkip",
    "export_pivot",
)
