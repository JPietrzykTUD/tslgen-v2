"""Full-corpus benchmark coverage audit and deterministic shape inventory."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.maintenance.benchmark_coverage import (
    audit_benchmark_coverage,
    render_benchmark_shape_inventory,
)
from tslc.pipeline import SkippedEntry
from tslc.pipeline import SkippedEntry


@pytest.fixture(scope="module")
def focused_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["scalar", "sse2", "avx2"],
        type_tags=["si8"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def test_audit_accounts_for_every_selected_variant_slot(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    assert audit.complete
    assert audit.selected_slots > 0
    assert audit.candidate_sets >= audit.selected_slots
    variant_shapes = [entry for entry in audit.shapes if entry.variant_declarations]
    assert variant_shapes
    assert all(entry.status == "benchmarked" for entry in variant_shapes)


def test_audit_rejects_a_selected_slot_without_a_workload(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    focused_benchmark_plan = focused_benchmark_result.rendered.benchmarks
    first, *rest = focused_benchmark_plan.coverage
    broken = replace(
        focused_benchmark_plan,
        coverage=(
            replace(
                first,
                status="unsupported",
                reason="focused unsupported-shape sentinel",
            ),
            *rest,
        ),
    )

    audit = audit_benchmark_coverage(
        catalog,
        broken,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    assert not audit.complete
    assert any(
        issue.kind == "coverage-gap"
        and "unsupported-shape sentinel" in issue.detail
        for issue in audit.issues
    )


def test_audit_rejects_a_lowered_variant_slot_missing_from_the_planner(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    selected = next(
        entry for entry in focused_benchmark_result.coverage if entry.variant_names
    )
    unplanned = replace(selected, extension="unplanned_extension")

    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=(*focused_benchmark_result.coverage, unplanned),
        selection_skips=focused_benchmark_result.skipped,
    )

    assert any(
        issue.kind == "selected-slot-missing-planner"
        and issue.slot is not None
        and issue.slot.extension_name == "unplanned_extension"
        for issue in audit.issues
    )


def test_audit_keeps_variant_lowering_skips_in_the_funnel(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    selected = next(
        entry for entry in focused_benchmark_result.coverage if entry.variant_names
    )
    remaining = tuple(
        entry for entry in focused_benchmark_result.coverage if entry is not selected
    )
    skipped = SkippedEntry(
        profile=selected.profile,
        backend=selected.backend,
        primitive=selected.primitive,
        extension=selected.extension,
        type_tag=selected.type_tag,
        reason="focused lowering-skip sentinel",
        source_primitive_name=selected.source_primitive_name,
        result_kind=selected.result_kind,
        param_kinds=selected.param_kinds,
        mask_policy=selected.mask_policy,
        axis=selected.axis,
        variant_names=selected.variant_names,
    )

    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=remaining,
        selection_skips=(*focused_benchmark_result.skipped, skipped),
    )

    assert any(
        issue.kind == "selected-slot-skipped"
        and "lowering-skip sentinel" in issue.detail
        for issue in audit.issues
    )


def test_audit_keeps_variant_lowering_skips_in_the_funnel(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    selected = next(
        entry for entry in focused_benchmark_result.coverage if entry.variant_names
    )
    remaining = tuple(
        entry for entry in focused_benchmark_result.coverage if entry is not selected
    )
    skipped = SkippedEntry(
        profile=selected.profile,
        backend=selected.backend,
        primitive=selected.primitive,
        extension=selected.extension,
        type_tag=selected.type_tag,
        reason="focused lowering-skip sentinel",
        source_primitive_name=selected.source_primitive_name,
        result_kind=selected.result_kind,
        param_kinds=selected.param_kinds,
        mask_policy=selected.mask_policy,
        axis=selected.axis,
        variant_names=selected.variant_names,
    )

    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=remaining,
        selection_skips=(*focused_benchmark_result.skipped, skipped),
    )

    assert any(
        issue.kind == "selected-slot-skipped"
        and "lowering-skip sentinel" in issue.detail
        for issue in audit.issues
    )


def test_shape_inventory_is_deterministic_and_marks_default_only_shapes(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    # The focused plan intentionally leaves other variant declarations inactive;
    # rendering must still inventory all source shapes and distinguish default-only
    # shapes from genuine variant coverage gaps.
    assert focused_benchmark_result.rendered is not None
    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    first = render_benchmark_shape_inventory(audit)
    second = render_benchmark_shape_inventory(audit)

    assert first == second
    assert "## Signature shapes" in first
    assert "## Special cases" in first
    assert "not applicable" in first
    assert "inactive-authored-shape" in first
    special_cases = {entry.name: entry for entry in audit.special_cases}
    for name in (
        "sized-vector implementation",
        "scalable-vector implementation",
        "opt-in compiler header implementation",
    ):
        assert special_cases[name].variant_declarations == 0
        assert special_cases[name].status == "not applicable"
