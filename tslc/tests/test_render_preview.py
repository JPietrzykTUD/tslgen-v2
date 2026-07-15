"""Focused backend-rendered specialization preview tests."""

from __future__ import annotations

from pathlib import Path

import tslc._pipeline_inputs as pipeline_inputs
from tslc.diagnostics import Diagnostic
from tslc.maintenance.render_preview import render_preview


def _preview(
    data_root: Path,
    machine_profiles_path: Path,
    *,
    backend: str,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    return render_preview(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend=backend,
        extension="avx2",
    )


def test_cpp_preview_uses_backend_renderer_without_render_assets(
    data_root: Path,
    machine_profiles_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pipeline_inputs,
        "load_default_render_assets",
        lambda: (_ for _ in ()).throw(AssertionError("preview loaded render assets")),
    )

    rendered, diagnostics = _preview(
        data_root, machine_profiles_path, backend="cpp"
    )

    assert diagnostics == ()
    assert rendered is not None
    assert "tslc rendered specialization preview" in rendered
    assert "input snapshot: sha256:" in rendered
    assert "namespace detail::primitives" in rendered
    assert "_mm256_add_epi32" in rendered
    assert "VERDICT: COMPILES" not in rendered


def test_rust_preview_uses_backend_renderer(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    rendered, diagnostics = _preview(
        data_root, machine_profiles_path, backend="rust"
    )

    assert diagnostics == ()
    assert rendered is not None
    assert "tslc rendered specialization preview" in rendered
    assert "trait AddImpl" in rendered
    assert "_mm256_add_epi32" in rendered


def test_preview_reports_a_slot_that_is_not_emitted(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    rendered, diagnostics = render_preview(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="not-an-extension",
    )

    assert rendered is None
    assert any(
        diagnostic.code == "TSL-PREVIEW-NOT-EMITTED"
        for diagnostic in diagnostics
    )
