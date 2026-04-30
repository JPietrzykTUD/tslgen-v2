from __future__ import annotations

from pathlib import Path
import sys
from unittest import TestCase

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tslgen.core.diagnostics import Diagnostic, DiagnosticSeverity  # noqa: E402


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def fixture_path(*parts: str) -> Path:
    return FIXTURE_ROOT.joinpath(*parts)


def assert_diagnostic(
    test_case: TestCase,
    diagnostic: Diagnostic,
    *,
    code: str,
    severity: DiagnosticSeverity,
    path: str | None = None,
    line: int | None = None,
    column: int | None = None,
) -> None:
    test_case.assertEqual(diagnostic.code, code)
    test_case.assertEqual(diagnostic.severity, severity)
    if path is not None or line is not None or column is not None:
        test_case.assertIsNotNone(diagnostic.location)
        location = diagnostic.location
        assert location is not None
    else:
        location = None

    if path is not None:
        assert location is not None
        test_case.assertEqual(location.path.as_posix(), path)
    if line is not None:
        assert location is not None
        test_case.assertEqual(location.line, line)
    if column is not None:
        assert location is not None
        test_case.assertEqual(location.column, column)
