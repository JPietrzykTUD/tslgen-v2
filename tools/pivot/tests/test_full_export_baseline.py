"""Exact full-corpus coverage and content ratchet for the PIVOT exporter."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from tslc.output.artifacts import ArtifactSet
from tslc_pivot.baseline import (
    CANONICAL_FULL_EXPORT_ARGV,
    CANONICAL_FULL_EXPORT_COMMAND,
    build_full_export_manifest,
    canonical_full_export,
)
from tslc_pivot.exporter import export_pivot
from tslc_pivot.model import PivotExportResult, PivotLanguage, PivotProjection


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_PATH = Path(__file__).parent / "baselines" / "full_export.json"


def test_full_corpus_export_matches_exact_manifest() -> None:
    expected: dict[str, Any] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    run = canonical_full_export(_REPOSITORY_ROOT)
    result = export_pivot(run.request)

    assert result.diagnostics == ()
    actual = build_full_export_manifest(run, result)

    assert actual["schema"] == expected["schema"]
    assert actual["provenance"] == expected["provenance"]
    assert actual["diagnostics"] == expected["diagnostics"] == []
    assert actual["summary"] == expected["summary"]
    assert (
        actual["skips_by_language_and_reason"]
        == expected["skips_by_language_and_reason"]
    )
    assert _definitions_by_identity(actual) == _definitions_by_identity(expected)
    assert (
        actual["definition_identity_collisions"]
        == expected["definition_identity_collisions"]
    )
    assert _artifacts_by_path(actual) == _artifacts_by_path(expected)
    assert actual["artifacts"] == expected["artifacts"]
    assert actual == expected

    assert run.argv == CANONICAL_FULL_EXPORT_ARGV
    assert run.command == CANONICAL_FULL_EXPORT_COMMAND
    provenance = actual["provenance"]
    assert provenance["argv"] == list(CANONICAL_FULL_EXPORT_ARGV)
    assert provenance["command"] == CANONICAL_FULL_EXPORT_COMMAND
    assert actual["summary"] == {
        "documents": 188,
        "definitions": 17_060,
        "skips": 27_823,
        "nominal_definition_identities": 16_732,
        "definition_identity_collisions": {
            "groups": 328,
            "entries": 656,
            "extra_entries": 328,
            "conflicting_groups": 328,
            "exact_duplicate_only_groups": 0,
        },
        "languages": {
            "cpp": {"documents": 94, "definitions": 10_291, "skips": 18_568},
            "rust": {"documents": 94, "definitions": 6_769, "skips": 9_255},
        },
    }
    artifacts = actual["artifacts"]
    assert artifacts["ordered_content_sha256"] == (
        "846ffd8955e3b7860f1bc7c2980d4fc2bd8618efa259fbe1824923c3293dc747"
    )
    assert actual["skip_category_scheme"] == "reason-prefix-v1"
    assert actual["unclassified_skip_count"] == 0
    category_counts: Counter[str] = Counter()
    for item in actual["skips_by_language_and_category"]:
        category_counts[item["category"]] += item["count"]
    assert category_counts == {
        "callee_resolution": 304,
        "forwarded_call_arguments": 3_180,
        "local_declaration": 738,
        "residual_target_text": 7_172,
        "schema_conflict": 650,
        "signature_admissibility": 11_023,
        "specialization_admissibility": 4_756,
    }
    assert actual["skip_fields"] == [
        "language",
        "profile",
        "primitive",
        "extension",
        "type",
        "reason",
        "source",
        "count",
    ]
    skip_records = actual["skips"]
    assert skip_records == sorted(skip_records, key=_canonical_json)
    assert sum(record[-1] for record in skip_records) == 27_823
    assert all(len(record) == len(actual["skip_fields"]) for record in skip_records)
    assert all(
        record[6] is None
        or (isinstance(record[6], list) and len(record[6]) == 5)
        for record in skip_records
    )
    expanded_skips = [
        record[:-1]
        for record in skip_records
        for _ in range(record[-1])
    ]
    assert sha256(_canonical_json(expanded_skips).encode("utf-8")).hexdigest() == (
        actual["skip_inventory_sha256"]
    )
    assert actual["skip_inventory_sha256"] == (
        "0e51087f1ee11050507fd0f2fca2158a6a58446b7f70005b12fc941ccc9ad445"
    )


def test_manifest_rejects_inputs_changed_after_snapshot(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    source = sources / "demo.tsl"
    source.write_text("before\n", encoding="utf-8")
    (tmp_path / "profiles.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "tslc.toml").write_text(
        "[tslc]\n"
        'sources = ["sources"]\n'
        'machine_profiles = "profiles.json"\n'
        'backends = ["cpp", "rust"]\n',
        encoding="utf-8",
    )
    run = canonical_full_export(tmp_path)
    result = PivotExportResult(
        artifacts=ArtifactSet.create(()),
        projections=tuple(
            PivotProjection(language, (), ())
            for language in (PivotLanguage.CPP, PivotLanguage.RUST)
        ),
        diagnostics=(),
    )

    source.write_text("after\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after the pre-export snapshot"):
        build_full_export_manifest(run, result)


def _definitions_by_identity(manifest: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    assert manifest["definition_fields"] == [
        "language",
        "document",
        "isa",
        "dtype",
        "signature",
        "direct_sha256",
    ]
    records = manifest["definitions"]
    by_identity: dict[str, list[str]] = {}
    for item in records:
        identity = json.dumps(
            item[:5],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        direct_sha256 = item[5]
        by_identity.setdefault(identity, []).append(direct_sha256)
    assert sum(len(items) for items in by_identity.values()) == 17_060
    return {
        identity: tuple(sorted(direct_hashes))
        for identity, direct_hashes in by_identity.items()
    }


def _artifacts_by_path(manifest: dict[str, Any]) -> dict[str, str]:
    items = manifest["artifacts"]["items"]
    paths = [item["path"] for item in items]
    assert len(paths) == len(set(paths)), (
        "the full-export ratchet contains duplicate artifact paths"
    )
    return {item["path"]: item["sha256"] for item in items}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
