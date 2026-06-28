"""Source loading returns diagnostics for filesystem boundary failures."""

from __future__ import annotations

from pathlib import Path

from tslc.sources import SourceLoader


def test_invalid_utf8_source_reports_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "bad.tsl"
    path.write_bytes(b"\xff")

    result = SourceLoader().load((path,))

    assert result.documents == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-SOURCE-READ-FAILED"
    assert "UTF-8" in diagnostic.message
    assert diagnostic.location is not None
    assert diagnostic.location.path == path.resolve()
