"""Guarded maintenance behavior for the durable PIVOT baseline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc_pivot.baseline import (
    classify_skip_reason,
    render_full_export_manifest,
    update_full_export_baseline,
    validate_full_export_baseline_update,
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


def test_reviewed_incompatibility_override_is_explicit() -> None:
    validate_full_export_baseline_update(
        _manifest(_definition("removed")),
        _manifest(),
        allow_reviewed_incompatible_baseline=True,
    )


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
