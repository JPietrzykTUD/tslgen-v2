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
    build_body_census_manifest,
    canonical_full_export,
)
from tslc_pivot.exporter import export_pivot
from tslc_pivot.model import PivotExportResult, PivotLanguage, PivotProjection


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_PATH = Path(__file__).parent / "baselines" / "full_export.json"
_BODY_BASELINE_PATH = Path(__file__).parent / "baselines" / "body_census.json"


def test_full_corpus_export_matches_exact_manifest() -> None:
    expected: dict[str, Any] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    expected_body: dict[str, Any] = json.loads(
        _BODY_BASELINE_PATH.read_text(encoding="utf-8")
    )
    run = canonical_full_export(_REPOSITORY_ROOT)
    result = export_pivot(run.request)

    assert result.diagnostics == ()
    _assert_complete_body_census(result, expected, expected_body)
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
        "documents": 186,
        "definitions": 16_620,
        "skips": 29_123,
        "nominal_definition_identities": 16_292,
        "definition_identity_collisions": {
            "groups": 328,
            "entries": 656,
            "extra_entries": 328,
            "conflicting_groups": 328,
            "exact_duplicate_only_groups": 0,
        },
        "languages": {
            "cpp": {"documents": 93, "definitions": 10_041, "skips": 19_473},
            "rust": {"documents": 93, "definitions": 6_579, "skips": 9_650},
        },
    }
    artifacts = actual["artifacts"]
    assert artifacts["ordered_content_sha256"] == (
        "78ede4c2f285414fefa5da989d135e6b24ea6609f29d2ce5a082926efcb5ccf6"
    )
    assert actual["skip_category_scheme"] == "reason-prefix-v1"
    assert actual["unclassified_skip_count"] == 0
    category_counts: Counter[str] = Counter()
    for item in actual["skips_by_language_and_category"]:
        category_counts[item["category"]] += item["count"]
    assert category_counts == {
        "callee_resolution": 304,
        "forwarded_call_arguments": 3_180,
        "local_declaration": 818,
        "residual_target_text": 7_352,
        "schema_conflict": 650,
        "signature_admissibility": 12_163,
        "specialization_admissibility": 4_656,
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
    assert sum(record[-1] for record in skip_records) == 29_123
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
        "c28f3147d5665fc22c25a39ed95b5fd8bdffa42a2f89f75bb3c3ed7c89e32dcd"
    )


def _assert_complete_body_census(
    result: PivotExportResult,
    full_export_baseline: dict[str, Any],
    body_baseline: dict[str, Any],
) -> None:
    assert tuple(census.language.value for census in result.body_censuses) == (
        "cpp",
        "rust",
    )
    assert tuple(len(census.entries) for census in result.body_censuses) == (
        10_041,
        6_579,
    )
    assert tuple(census.multi_statement_count for census in result.body_censuses) == (
        3_061,
        1_669,
    )
    assert tuple(census.category_counts for census in result.body_censuses) == (
        (
            ("call_and_local", 89),
            ("call_only", 2_962),
            ("local_only", 10),
            ("native_leaf", 4_222),
            ("synthetic_fixed", 2_758),
        ),
        (
            ("call_and_local", 5),
            ("call_only", 1_654),
            ("local_only", 10),
            ("native_leaf", 2_176),
            ("synthetic_fixed", 2_734),
        ),
    )
    assert Counter(
        entry.category.value
        for census in result.body_censuses
        for entry in census.entries
        if entry.category is not None
    ) == {
        "synthetic_fixed": 5_492,
        "native_leaf": 6_398,
        "call_only": 4_616,
        "local_only": 20,
        "call_and_local": 94,
    }
    assert sum(
        census.multi_statement_count for census in result.body_censuses
    ) == 4_730
    assert all(census.failures == () for census in result.body_censuses)
    assert all(
        body.body is not None
        for census in result.body_censuses
        for entry in census.entries
        for body in (entry.body, *entry.inlined_bodies)
    )

    projection_by_language = {
        projection.language: projection for projection in result.projections
    }
    for census in result.body_censuses:
        projection = projection_by_language[census.language]
        expected = Counter(
            (document.name, definition)
            for document in projection.documents
            for definition in document.definitions
        )
        actual = Counter(
            (entry.document, entry.definition) for entry in census.entries
        )
        assert actual == expected

    nominal_identities = Counter(
        (
            census.language,
            entry.document,
            entry.definition.isa,
            entry.definition.dtype,
            entry.definition.signature,
        )
        for census in result.body_censuses
        for entry in census.entries
    )
    collisions = tuple(count for count in nominal_identities.values() if count > 1)
    assert len(collisions) == 328
    assert sum(collisions) == 656
    assert all(count == 2 for count in collisions)
    assert all(
        "\x00" not in artifact.content for artifact in result.artifacts.artifacts
    )

    expected_definitions = Counter(
        (
            record[0],
            record[1],
            record[2],
            record[3],
            tuple(tuple(item) for item in record[4]),
            record[5],
        )
        for record in full_export_baseline["definitions"]
    )
    body_definitions = Counter(
        (
            census.language.value,
            entry.document,
            entry.definition.isa,
            entry.definition.dtype,
            entry.definition.signature,
            sha256(
                _canonical_json(list(entry.definition.direct)).encode("utf-8")
            ).hexdigest(),
        )
        for census in result.body_censuses
        for entry in census.entries
    )
    assert body_definitions == expected_definitions

    occurrences: dict[tuple[object, ...], list[int]] = {}
    for census in result.body_censuses:
        for entry in census.entries:
            key = (
                census.language,
                entry.document,
                entry.definition.isa,
                entry.definition.dtype,
                entry.definition.signature,
            )
            occurrences.setdefault(key, []).append(entry.occurrence)
    assert all(
        sorted(items) == list(range(len(items))) for items in occurrences.values()
    )
    assert sum(
        entry.occurrence == 1
        for census in result.body_censuses
        for entry in census.entries
    ) == 328

    actual_body = build_body_census_manifest(
        result,
        source_root=_REPOSITORY_ROOT,
    )
    assert actual_body == body_baseline




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
    assert sum(len(items) for items in by_identity.values()) == 16_620
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
