"""Post-generation formatting honors requested backend drivers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tslc.backend.capability import GeneratedFormatSpec
from tslc.backend.cpp_capability import CPP_BACKEND
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


def test_fake_backend_owns_its_generated_formatter(monkeypatch, tmp_path: Path) -> None:
    from tslc.backend import registry

    source = tmp_path / "fake" / "src" / "lib.fake"
    source.parent.mkdir(parents=True)
    source.write_text("fake source\n", encoding="utf-8")
    fake = replace(
        CPP_BACKEND,
        backend_id="fake",
        generated_format=GeneratedFormatSpec(
            executable="fakefmt",
            label="fake",
            patterns=("fake/**/*.fake",),
            args=("--write",),
        ),
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})

    report = format_generated(
        tmp_path,
        ("fake",),
        formatter_tools={"fakefmt": "/definitely/missing/fakefmt"},
    )

    assert report.formatted == ()
    assert report.notes == (
        "/definitely/missing/fakefmt not found; skipped fake formatting (1 files)",
    )
