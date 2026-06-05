from __future__ import annotations

import importlib.util
from pathlib import Path

import tslgen.pipeline as pipeline


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_ROOT = _REPO_ROOT / "tslgen" / "src" / "tslgen" / "pipeline"
_PRIMITIVE_PROJECT_PIPELINE = _PIPELINE_ROOT / "primitive_project_pipeline.py"
_GENERATED_PRIMITIVE_PIPELINE = _PIPELINE_ROOT / "generated_primitive_pipeline.py"
_RETIRED_REAL_SCALAR_PIPELINE = _PIPELINE_ROOT / "real_scalar_pipeline.py"


def test_m244_5_real_primitive_project_pipeline_uses_generic_module() -> None:
    assert _PRIMITIVE_PROJECT_PIPELINE.exists()
    assert not _RETIRED_REAL_SCALAR_PIPELINE.exists()
    assert importlib.util.find_spec("tslgen.pipeline.real_scalar_pipeline") is None


def test_m244_5_public_pipeline_exports_use_generic_real_project_names() -> None:
    exported = set(pipeline.__all__)

    assert {
        "SelectedPrimitiveBodyRenderEntry",
        "SelectedPrimitiveBodyRenderSelection",
        "SelectedPrimitiveProjectResult",
        "build_primitive_project_artifacts_from_selected_body",
        "build_primitive_project_artifacts_from_selected_bodies",
    } <= exported

    assert not any("RealScalar" in name for name in exported)
    assert not any("real_scalar" in name for name in exported)
    assert "DEFAULT_SELECTED_PRIMITIVE_BODY_RENDER_ENTRIES" not in exported


def test_m244_5_real_project_pipeline_has_no_fixture_owned_public_defaults() -> None:
    source = _PRIMITIVE_PROJECT_PIPELINE.read_text(encoding="utf-8")

    assert "DEFAULT_SELECTED_PRIMITIVE_BODY_RENDER_ENTRIES" not in source
    assert "_DEFAULT_MATRIX" not in source
    assert 'primitive_name: str = "add"' not in source
    assert 'selector_path: tuple[str, ...] = ("scalar", "arith")' not in source
    assert 'type_tag: str = "si32"' not in source
    assert "build_real_scalar" not in source
    assert "RealScalar" not in source


def test_m244_5_tiny_generated_pipeline_is_labelled_regression_only() -> None:
    source = _GENERATED_PRIMITIVE_PIPELINE.read_text(encoding="utf-8")

    assert "M224 tiny/regression-only" in source
    assert "not the real selected primitive project generation pipeline" in source


def test_m244_5_no_sibling_fixture_pipeline_names_exist() -> None:
    forbidden_names = {
        "real_scalar_pipeline.py",
        "real_avx2_pipeline.py",
        "real_neon_pipeline.py",
        "real_sse_pipeline.py",
        "real_add_pipeline.py",
        "real_sub_pipeline.py",
        "emit_return_pipeline.py",
    }

    assert forbidden_names.isdisjoint({path.name for path in _PIPELINE_ROOT.glob("*.py")})
