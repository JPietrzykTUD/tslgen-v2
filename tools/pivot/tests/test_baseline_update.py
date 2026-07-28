"""Guarded maintenance behavior for the durable PIVOT baseline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc_pivot.baseline import (
    classify_skip_reason,
    render_full_export_manifest,
    render_body_census_manifest,
    update_full_export_baseline,
    update_pivot_baselines,
    validate_full_export_baseline_update,
    validate_body_census_baseline_update,
)


_FIELDS = [
    "language",
    "document",
    "isa",
    "dtype",
    "signature",
    "direct_sha256",
]
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _definition(name: str, direct_hash: str = _HASH_A) -> list[object]:
    return ["cpp", name, "scalar", "int32", [["res", "int32_t"]], direct_hash]


def _manifest(*definitions: list[object]) -> dict[str, object]:
    return {
        "schema": "test",
        "definition_fields": list(_FIELDS),
        "definitions": list(definitions),
    }


def _body_manifest(
    semantic_digest: str = _HASH_A,
    *,
    location_digest: str = _HASH_A,
) -> dict[str, object]:
    return {
        "schema": "tslc-pivot-body-census-v2",
        "semantic_digest": semantic_digest,
        "location_digest": location_digest,
        "summary": {"entries": 1, "failures": 0},
        "languages": {},
    }




@pytest.mark.parametrize(
    ("previous", "candidate"),
    [
        (_manifest(_definition("kept")), _manifest()),
        (
            _manifest(_definition("duplicate"), _definition("duplicate")),
            _manifest(_definition("duplicate")),
        ),
        (
            _manifest(_definition("changed", _HASH_A)),
            _manifest(_definition("changed", _HASH_B)),
        ),
    ],
    ids=("removal", "reduced-multiplicity", "direct-hash-replacement"),
)
def test_baseline_guard_rejects_incompatible_inventory_changes(
    previous: dict[str, object],
    candidate: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="remove or replace"):
        validate_full_export_baseline_update(previous, candidate)


def test_baseline_guard_allows_additions_without_refreshing_old_entries() -> None:
    previous = _manifest(_definition("kept", _HASH_A))
    candidate = _manifest(
        _definition("kept", _HASH_A),
        _definition("kept", _HASH_B),
        _definition("added", _HASH_B),
    )

    validate_full_export_baseline_update(previous, candidate)


def test_baseline_guard_rejects_skip_fact_refresh_without_coverage_growth() -> None:
    previous = _manifest(_definition("kept"))
    previous["skip_semantic_inventory_sha256"] = _HASH_A
    candidate = _manifest(_definition("kept"))
    candidate["skip_semantic_inventory_sha256"] = _HASH_B

    with pytest.raises(ValueError, match="product facts changed"):
        validate_full_export_baseline_update(previous, candidate)


@pytest.mark.parametrize(
    ("field", "previous_value", "candidate_value"),
    [
        ("skip_semantic_inventory_sha256", _HASH_A, _HASH_B),
        (
            "artifacts",
            [{"path": "cpp/demo.yaml", "sha256": _HASH_A}],
            [{"path": "cpp/demo.yaml", "sha256": _HASH_B}],
        ),
        (
            "diagnostics",
            [],
            [{"code": "PIVOT-DEMO", "message": "changed"}],
        ),
    ],
    ids=("semantic-skips", "artifacts", "diagnostics"),
)
def test_baseline_guard_rejects_product_fact_changes_with_coverage_growth(
    field: str,
    previous_value: object,
    candidate_value: object,
) -> None:
    previous = _manifest(_definition("kept"))
    previous[field] = previous_value
    candidate = _manifest(_definition("kept"), _definition("added"))
    candidate[field] = candidate_value

    with pytest.raises(ValueError, match=rf"product facts changed:.*{field}"):
        validate_full_export_baseline_update(previous, candidate)


def test_baseline_guard_accepts_skip_location_only_refresh() -> None:
    previous = _manifest(_definition("kept"))
    previous["skips"] = [["same", ["demo.tsl", 1, 1, 2, 1]]]
    previous["skip_location_inventory_sha256"] = _HASH_A
    candidate = _manifest(_definition("kept"))
    candidate["skips"] = [["same", ["demo.tsl", 20, 1, 21, 1]]]
    candidate["skip_location_inventory_sha256"] = _HASH_B

    validate_full_export_baseline_update(previous, candidate)


def test_reviewed_product_fact_change_with_addition_requires_override() -> None:
    previous = _manifest(_definition("kept"))
    previous["skip_semantic_inventory_sha256"] = _HASH_A
    candidate = _manifest(_definition("kept"), _definition("added"))
    candidate["skip_semantic_inventory_sha256"] = _HASH_B

    with pytest.raises(
        ValueError,
        match="product facts changed: skip_semantic_inventory_sha256",
    ):
        validate_full_export_baseline_update(previous, candidate)

    validate_full_export_baseline_update(
        previous,
        candidate,
        allow_reviewed_incompatible_baseline=True,
    )


def test_body_census_changes_require_explicit_review() -> None:
    with pytest.raises(ValueError, match="body-census semantic facts changed"):
        validate_body_census_baseline_update(
            _body_manifest(_HASH_A),
            _body_manifest(_HASH_B),
        )

    validate_body_census_baseline_update(
        _body_manifest(_HASH_A),
        _body_manifest(_HASH_B),
        allow_reviewed_incompatible_baseline=True,
    )


def test_body_census_location_only_refresh_does_not_require_review() -> None:
    validate_body_census_baseline_update(
        _body_manifest(location_digest=_HASH_A),
        _body_manifest(location_digest=_HASH_B),
    )


def test_combined_updater_validates_all_baselines_before_writing(
    tmp_path: Path,
) -> None:
    full_path = tmp_path / "full_export.json"
    body_path = tmp_path / "body_census.json"
    full_text = render_full_export_manifest(_manifest(_definition("kept")))
    body_text = render_body_census_manifest(_body_manifest(_HASH_A))
    full_path.write_text(full_text, encoding="utf-8")
    body_path.write_text(body_text, encoding="utf-8")

    with pytest.raises(ValueError, match="body-census semantic facts changed"):
        update_pivot_baselines(
            full_path,
            _manifest(_definition("kept"), _definition("added")),
            body_path,
            _body_manifest(_HASH_B),
        )

    assert full_path.read_text(encoding="utf-8") == full_text
    assert body_path.read_text(encoding="utf-8") == body_text


def test_updater_never_overwrites_before_guard_passes(tmp_path: Path) -> None:
    path = tmp_path / "full_export.json"
    original = _manifest(_definition("kept"))
    original_text = render_full_export_manifest(original)
    path.write_text(original_text, encoding="utf-8")

    with pytest.raises(ValueError, match="remove or replace"):
        update_full_export_baseline(path, _manifest())

    assert path.read_text(encoding="utf-8") == original_text


def test_skip_categories_ignore_reason_details_but_keep_unknowns_visible() -> None:
    forwarded_prefix = (
        "PIVOT call inlining does not support forwarded immediate or generic "
        "arguments:"
    )
    assert classify_skip_reason(f"{forwarded_prefix} call A") == (
        "forwarded_call_arguments"
    )
    assert classify_skip_reason(f"{forwarded_prefix} call B") == (
        "forwarded_call_arguments"
    )
    local_reason = "PIVOT supports only var<infer> and var<const_infer> locals:"
    assert classify_skip_reason(f"{local_reason} first") == "local_declaration"
    assert classify_skip_reason(f"implementation variant demo: {local_reason} second") == (
        "local_declaration"
    )
    assert classify_skip_reason("new unsupported family") == "unclassified"


def test_renderer_keeps_each_raw_skip_group_on_one_reviewable_line() -> None:
    manifest = _manifest()
    manifest["skip_fields"] = [
        "language",
        "profile",
        "primitive",
        "extension",
        "type",
        "reason",
        "source",
        "count",
    ]
    manifest["skips"] = [
        [
            "cpp",
            "avx2",
            "demo",
            "avx2",
            "si32",
            "detail on\ntwo source lines",
            ["tsldata/demo.tsl", 2, 3, 4, 5],
            2,
        ]
    ]

    rendered = render_full_export_manifest(manifest)

    skip_line = next(
        line for line in rendered.splitlines() if line.startswith('    ["cpp"')
    )
    assert "detail on\\ntwo source lines" in skip_line
    assert skip_line.endswith(",2]")
