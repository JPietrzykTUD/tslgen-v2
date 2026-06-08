from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"
IMPLEMENTATION_BODY_PATTERN = re.compile(r"\bImplementationBody\b")


def test_m254_8_lowerer_and_primitive_calls_do_not_expose_implementation_body() -> None:
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")
    primitive_calls_text = (
        SRC / "lowering" / "primitive_calls.py"
    ).read_text(encoding="utf-8")

    assert "ImplementationBody" not in lowerer_text
    assert "body: ImplementationBody" not in lowerer_text
    assert "ImplementationBody(" not in lowerer_text
    assert "_selected_with_body" not in lowerer_text
    assert "_implementation_body_token_view" not in lowerer_text

    assert "ImplementationBody" not in primitive_calls_text
    assert "body: ImplementationBody" not in primitive_calls_text
    assert "unsupported_primitive_call_diagnostics(" not in primitive_calls_text


def test_m254_8_lowerer_uses_explicit_token_views_for_branch_bodies() -> None:
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")

    assert "_SelectedBodyTokenView" in lowerer_text
    assert "_lower_direct_body_view" in lowerer_text
    assert "selected_branch.tokens" in lowerer_text
    assert "selected_branch.source" in lowerer_text
    assert "compatibility_body_token_result_from_fragment_sequence" in lowerer_text
    assert "unsupported_primitive_call_diagnostics_from_body_tokens" in lowerer_text


def test_m254_8_remaining_production_implementation_body_references_are_classified() -> None:
    allowed_files = {
        SRC / "domain" / "catalog.py",
        SRC / "pipeline" / "catalog_builder.py",
        SRC / "pipeline" / "primitive_project_pipeline.py",
        SRC / "lowering" / "source_body_fragments.py",
    }
    actual_files = {
        path
        for path in SRC.rglob("*.py")
        if IMPLEMENTATION_BODY_PATTERN.search(path.read_text(encoding="utf-8"))
    }

    assert actual_files == allowed_files


def test_m254_8_guardrails_against_scanner_and_fixture_drift() -> None:
    module_text = "\n".join(
        (
            (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8"),
            (SRC / "lowering" / "primitive_calls.py").read_text(encoding="utf-8"),
        )
    )

    forbidden = (
        "emit_return +",
        "call +",
        "real_scalar_pipeline",
        "real_avx2_pipeline",
        "SourceBodyLexicalRegionScanner(",
        "frozen.",
        "tslgenold",
    )

    assert not any(text in module_text for text in forbidden)
