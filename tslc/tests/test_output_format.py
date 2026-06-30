"""Post-generation formatting honors requested backend drivers."""

from __future__ import annotations

from pathlib import Path

from tslc.output.format import format_generated


def test_format_generated_uses_requested_backend_only(tmp_path: Path) -> None:
    cpp = tmp_path / "cpp" / "include" / "tsl.hpp"
    rust = tmp_path / "rust" / "src" / "lib.rs"
    cpp.parent.mkdir(parents=True)
    rust.parent.mkdir(parents=True)
    cpp.write_text("int main(){}\n", encoding="utf-8")
    rust.write_text("fn main(){}\n", encoding="utf-8")

    report = format_generated(
        tmp_path,
        ("rust",),
        clang_format="/definitely/missing/clang-format",
        rustfmt="/definitely/missing/rustfmt",
    )

    assert report.formatted == ()
    assert len(report.notes) == 1
    assert "rustfmt not found; skipped rust formatting" in report.notes[0]
