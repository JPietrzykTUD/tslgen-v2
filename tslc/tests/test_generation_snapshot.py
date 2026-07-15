"""Deterministic semantic and generated-tree snapshot tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from tslc.maintenance.generation_snapshot import (
    compare_snapshot_directories,
    compare_snapshot_documents,
    serialize_snapshot,
)


def _document() -> dict[str, object]:
    return {
        "version": 1,
        "case": "focused",
        "request": {"profiles": ["avx2"], "backends": ["cpp"]},
        "input_manifest": [
            {
                "logical_path": "tsldata/probe.tsl",
                "sha256": "input-digest",
                "byte_count": 10,
            }
        ],
        "input_manifest_digest": "all-inputs",
        "compiler_provenance": {"python_files_digest": "compiler-a"},
        "artifacts": [
            {
                "logical_path": "cpp/probe.hpp",
                "sha256": "artifact-digest",
                "byte_count": 6,
                "media_type": "text/x-c++hdr",
                "metadata": [],
            }
        ],
        "generated_files": [
            {
                "logical_path": "cpp/probe.hpp",
                "sha256": "artifact-digest",
                "byte_count": 6,
            }
        ],
        "semantics": {
            "diagnostics": [
                {
                    "severity": "info",
                    "code": "TSL-PROBE",
                    "message": "probe",
                    "location": {
                        "path": "tsldata/probe.tsl",
                        "line": 3,
                        "column": 5,
                    },
                }
            ],
            "coverage": [
                {
                    "profile": "avx2",
                    "backend": "cpp",
                    "primitive": "probe",
                    "extension": "avx2",
                    "type_tag": "si32",
                }
            ],
            "skipped": [],
            "verification": {
                "backends": [
                    {
                        "backend_id": "cpp",
                        "root_path": "cpp",
                        "profiles": [{"profile_name": "avx2"}],
                    }
                ]
            },
            "value_tests": {"profiles": [], "diagnostics": [], "coverage": []},
            "benchmarks": {"profiles": [], "diagnostics": [], "coverage": []},
            "counts": {"artifacts": 1, "coverage": 1, "skipped": 0},
        },
    }


def test_snapshot_serialization_is_deterministic() -> None:
    document = _document()

    first = serialize_snapshot(document)
    second = serialize_snapshot(deepcopy(document))

    assert first == second
    assert first.endswith("\n")
    assert json.loads(first) == document


def test_compiler_provenance_is_not_a_frozen_input() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    candidate["compiler_provenance"] = {"python_files_digest": "compiler-b"}

    assert compare_snapshot_documents(baseline, candidate) == ()


def test_input_mismatch_is_reported_before_output_mismatch() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    candidate["input_manifest_digest"] = "different-inputs"
    candidate["semantics"] = {"coverage": []}

    differences = compare_snapshot_documents(baseline, candidate)

    assert len(differences) == 1
    assert differences[0].startswith("input_manifest_digest")


def test_coverage_mismatch_is_detected() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    semantics = candidate["semantics"]
    assert isinstance(semantics, dict)
    semantics["coverage"] = []

    differences = compare_snapshot_documents(baseline, candidate)

    assert any("semantics.coverage" in difference for difference in differences)


def test_skip_mismatch_is_detected() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    semantics = candidate["semantics"]
    assert isinstance(semantics, dict)
    semantics["skipped"] = [{"reason": "different"}]

    differences = compare_snapshot_documents(baseline, candidate)

    assert any("semantics.skipped" in difference for difference in differences)


def test_diagnostic_location_mismatch_is_detected() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    semantics = candidate["semantics"]
    assert isinstance(semantics, dict)
    diagnostics = semantics["diagnostics"]
    assert isinstance(diagnostics, list)
    diagnostic = diagnostics[0]
    assert isinstance(diagnostic, dict)
    location = diagnostic["location"]
    assert isinstance(location, dict)
    location["line"] = 4

    differences = compare_snapshot_documents(baseline, candidate)

    assert any("location.line" in difference for difference in differences)


def test_verification_plan_mismatch_is_detected() -> None:
    baseline = _document()
    candidate = deepcopy(baseline)
    semantics = candidate["semantics"]
    assert isinstance(semantics, dict)
    semantics["verification"] = {"backends": []}

    differences = compare_snapshot_documents(baseline, candidate)

    assert any("semantics.verification" in difference for difference in differences)


def test_generated_artifact_content_mismatch_is_detected(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    for root, content in ((baseline, "before"), (candidate, "after!")):
        generated = root / "generated" / "cpp"
        generated.mkdir(parents=True)
        (generated / "probe.hpp").write_text(content, encoding="utf-8")
        (root / "snapshot.json").write_text(
            serialize_snapshot(_document()),
            encoding="utf-8",
        )

    comparison = compare_snapshot_directories(baseline, candidate)

    assert not comparison.matches
    assert any("generated_tree" in difference for difference in comparison.differences)
