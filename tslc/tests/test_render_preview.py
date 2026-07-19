"""Focused backend-rendered specialization preview tests."""

from __future__ import annotations

from pathlib import Path

import tslc._pipeline_inputs as pipeline_inputs
from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.maintenance.render_preview import render_preview
from tslc.select.selector import Selector


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


def test_preview_can_render_only_the_source_selected_implementation(
    data_root: Path,
    machine_profiles_path: Path,
    catalog,
    machine_profiles,
) -> None:
    selection = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "add",
        ("si32",),
        backend_id="cpp",
    )
    selected = next(
        item
        for item in selection.selected
        if item.extension.isa_name == "avx2"
        and item.type_tag == "si32"
        and not item.primitive.attributes
    )
    assert selected.implementation.selector_source is not None

    rendered, diagnostics = render_preview(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="avx2",
        implementation_source=selected.implementation.selector_source.start,
    )

    assert diagnostics == ()
    assert rendered is not None
    assert "struct add_impl<" in rendered
    assert "struct add_mask_impl<" not in rendered
    assert "struct add_maskz_impl<" not in rendered


def test_preview_source_filter_fails_closed_for_a_stale_site(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"

    rendered, diagnostics = render_preview(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="avx2",
        implementation_source=SourceLocation(path, 1, 1),
    )

    assert rendered is None
    assert any(
        diagnostic.code == "TSL-PREVIEW-NOT-EMITTED"
        for diagnostic in diagnostics
    )
