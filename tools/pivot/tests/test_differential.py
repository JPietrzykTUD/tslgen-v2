"""Focused classification tests for structured-vs-legacy evidence."""

from __future__ import annotations

from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc_pivot.differential import compare_pivot_projections
from tslc_pivot.model import (
    PivotDefinition,
    PivotDifferentialKind,
    PivotDocument,
    PivotLanguage,
    PivotSkip,
)


def test_collision_multiplicity_is_exact_but_direct_order_is_still_compared() -> None:
    first = _definition("res = first;")
    second = _definition("res = second;")
    legacy = (_document(first, second),)
    structured = (_document(second, first),)

    report = compare_pivot_projections(
        PivotLanguage.CPP,
        legacy,
        (),
        structured,
        (),
    )

    assert report.exact_shared_definition_count == 2
    assert report.direct_mismatch_count == 0
    assert not report.document_order_equal
    assert not report.yaml_artifacts_equal
    assert tuple(difference.kind for difference in report.differences) == (
        PivotDifferentialKind.DOCUMENT_ORDER,
        PivotDifferentialKind.YAML_ARTIFACT,
    )


def test_changed_direct_is_not_hidden_by_a_nominal_identity_match() -> None:
    report = compare_pivot_projections(
        PivotLanguage.CPP,
        (_document(_definition("res = old;")),),
        (),
        (_document(_definition("res = new;")),),
        (),
    )

    assert report.exact_shared_definition_count == 0
    assert report.direct_mismatch_count == 1
    assert report.legacy_only_definition_count == 0
    assert report.structured_only_definition_count == 0
    assert any(
        difference.kind is PivotDifferentialKind.DIRECT_MISMATCH
        for difference in report.differences
    )


def test_skip_source_and_reason_differences_are_classified_separately() -> None:
    legacy = (
        _skip("cast", 10),
        _skip("control", 20),
    )
    structured = (
        _skip("cast", 11),
        _skip("block", 21),
    )

    report = compare_pivot_projections(
        PivotLanguage.CPP,
        (),
        legacy,
        (),
        structured,
    )

    assert report.exact_shared_skip_count == 0
    assert report.skip_source_mismatch_count == 1
    assert report.skip_reason_mismatch_count == 1
    assert report.legacy_only_skip_count == 0
    assert report.structured_only_skip_count == 0


def _definition(statement: str) -> PivotDefinition:
    return PivotDefinition(
        isa="scalar",
        dtype="int32",
        signature=(("value", "int32_t"), ("res", "int32_t")),
        direct=(statement,),
    )


def _document(*definitions: PivotDefinition) -> PivotDocument:
    return PivotDocument("demo", ("value",), "res", definitions)


def _skip(reason: str, line: int) -> PivotSkip:
    return PivotSkip(
        PivotLanguage.CPP,
        "scalar",
        "demo",
        "scalar",
        "si32",
        reason,
        SourceSpan(Path("demo.tsl"), line, 1, line, 2),
    )
