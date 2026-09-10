"""Frozen evidence for the TSL v1 checked-API contract."""

from __future__ import annotations

from dataclasses import replace

from tslc.maintenance import _repo_context
from tslc.maintenance.checked_api_census import (
    _classify_runtime_site,
    _nearest_owner,
    build_census,
    canonical_baseline_path,
    canonical_report_path,
    render_markdown,
    serialize,
)


def test_runtime_site_owner_uses_typed_template_hole_identity() -> None:
    source = "@{core_simd_lane}\n    assert!(index < N);"

    assert _nearest_owner(
        source,
        source.index("assert!"),
        python_source=False,
        template_owners={"core_simd_lane": "lane"},
    ) == "lane"


def test_runtime_site_classification_does_not_leak_from_adjacent_context() -> None:
    statement = (
        'assert_eq!(left.len(), right.len(), "requires equal length");'
    )
    context = statement + ' assert!(output.len() >= left.len(), "enough output slots");'

    assert (
        _classify_runtime_site(
            "tslc/src/tslc/backend/assets/tsl_algorithm_consume.rs",
            "assert_eq",
            statement,
            context,
        )
        == "algorithm_equal_extents"
    )


def test_census_matches_reviewed_baseline_and_report() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None

    census = build_census(context)

    assert serialize(census) == canonical_baseline_path(context).read_text(
        encoding="utf-8"
    )
    assert render_markdown(census, context) == canonical_report_path(context).read_text(
        encoding="utf-8"
    )
    assert len(census.runtime_sites) == 156
    assert len(census.caller_unsafe_paths) == 33
    assert sum(gap.caller_unsafe_required for gap in census.metadata_gaps) == 26


def test_runtime_line_numbers_are_report_locations_not_baseline_identities() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None
    census = build_census(context)
    first = census.runtime_sites[0]
    moved = replace(
        census,
        runtime_sites=(replace(first, line=first.line + 1), *census.runtime_sites[1:]),
    )

    assert serialize(moved) == serialize(census)
    assert render_markdown(moved, context) != render_markdown(census, context)
