"""Deterministic semantic and generated-tree snapshot tests."""

from __future__ import annotations

from copy import deepcopy
import dataclasses
import json
from pathlib import Path
from typing import cast

from tslc.benchmark.model import (
    BenchmarkCandidate,
    BenchmarkCandidateSet,
    BenchmarkCoverageEntry,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkIndexedLoadScenario,
    BenchmarkMaskCorrectnessCase,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkTiming,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
    BenchmarkVectorScalarScenario,
    SpecializationKey,
)
from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.lower.lowerer import LoweredSpecialization
from tslc.maintenance import _generation_snapshot_semantics as semantics_module
from tslc.maintenance._generation_snapshot_semantics import (
    serialize_artifact,
    serialize_generation_semantics,
)
from tslc.maintenance.generation_snapshot import (
    compare_snapshot_directories,
    compare_snapshot_documents,
    serialize_snapshot,
)
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify_model import (
    VerifyBackend,
    VerifyProfile,
    VerifyProject,
    VerifyRunner,
)
from tslc.pipeline import CoverageEntry, GenerationResult, SkippedEntry
from tslc.render.project import RenderedProject
from tslc.value_tests.case_components import (
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestRepresentation,
    ValueTestScalable,
    ValueTestTarget,
)
from tslc.value_tests.case_plan import ValueTestCasePlan
from tslc.value_tests.model import (
    ValueTestCoverageEntry,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
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


# --- serializer completeness ------------------------------------------------
#
# Every dataclass field of a serialized domain type must appear as a key in
# its serializer's output, except the deliberate omissions listed here.  A new
# field on e.g. ValueTestCasePlan or SpecializationKey fails this test until
# it is either serialized or explicitly allowlisted with a reason.

_DELIBERATE_OMISSIONS: dict[type, frozenset[str]] = {
    # content: artifact identity is recorded as sha256 + byte_count; embedding
    # the full generated text would duplicate the generated tree in every
    # snapshot document.
    Artifact: frozenset({"content"}),
    # span: the span start is serialized under the "location" key; end
    # positions follow the producer span migration (audit fix-plan slice 25).
    # related/help: secondary presentation of the same diagnostic identity
    # (severity/code/message/position); deliberately outside snapshot compare.
    Diagnostic: frozenset({"span", "related", "help"}),
    # artifacts: serialized separately via serialize_artifact in the snapshot
    # document.  rendered: decomposed into the verification/value_tests/
    # benchmarks records.  emitted_profiles: render intermediates whose
    # observable identity is the artifact digests.  lowering_trace: opt-in
    # debug aid, never populated by snapshot generation.
    GenerationResult: frozenset(
        {"artifacts", "rendered", "emitted_profiles", "lowering_trace"}
    ),
    # specialization: the lowered specialization is a compiler intermediate;
    # its callable identity is captured by the key and candidate body hashes.
    BenchmarkCandidateSet: frozenset({"specialization"}),
}

_LOCATION = SourceLocation(Path("tsldata/probe.tsl"), 3, 5)
_DIAGNOSTIC = Diagnostic("warning", "TSL-PROBE", "probe", location=_LOCATION)
_COVERAGE = CoverageEntry("avx2", "cpp", "add", "avx2", "si32")
_SKIPPED = SkippedEntry("avx2", "cpp", "add", "avx2", "si32", "not lowered")
_VERIFY_RUNNER = VerifyRunner("sde", "avx2")
_VERIFY_PROFILE = VerifyProfile("avx2", "avx2", runner=_VERIFY_RUNNER)
_VERIFY_BACKEND = VerifyBackend("cpp", "cpp", (_VERIFY_PROFILE,))
_VERIFY_PROJECT = VerifyProject((_VERIFY_BACKEND,))
_VALUE_TEST_CASE = ValueTestCasePlan(
    kind="mask_result",
    function_name="test_add_avx2_si32",
    case_name="default",
    call_name="add",
    type_tag="si32",
    base_spelling="int32_t",
    lanes=4,
    expectation=ValueTestExpectation(values=("1",)),
)
_VALUE_TEST_COVERAGE = ValueTestCoverageEntry("cpp", "avx2", "add", "default", "emitted")
_VALUE_TEST_PROFILE = ValueTestProfilePlan("cpp", "avx2", (_VALUE_TEST_CASE,))
_VALUE_TEST_PLAN = ValueTestProjectPlan(
    profiles=(_VALUE_TEST_PROFILE,), coverage=(_VALUE_TEST_COVERAGE,)
)
_SPECIALIZATION_KEY = SpecializationKey(
    "cpp", "avx2", "add", "add", "avx2", "si32", "v", ("v", "v"), lanes=1
)
_BENCHMARK_TIMING = BenchmarkTiming(seed=7)
_BENCHMARK_SCENARIOS = (
    BenchmarkRegisterScenario(
        "register",
        "throughput",
        _BENCHMARK_TIMING,
        ("bounded_random", "bounded_random"),
    ),
    BenchmarkVectorScalarScenario(
        "vector_scalar",
        "throughput",
        _BENCHMARK_TIMING,
        "bounded_random",
        "bounded_random",
    ),
    BenchmarkImmediateScenario(
        "immediate", "throughput", _BENCHMARK_TIMING, "bounded_random"
    ),
    BenchmarkIndexedLoadScenario("indexed_load", _BENCHMARK_TIMING, 64, 4),
    BenchmarkMaskDensityScenario("mask_density", _BENCHMARK_TIMING, 0, 2),
    BenchmarkMaskResultScenario("mask_result", _BENCHMARK_TIMING, ("bounded_random",)),
    BenchmarkReductionScenario("reduction", _BENCHMARK_TIMING, "bounded_random"),
)
_BENCHMARK_CORRECTNESS_CASES = (
    BenchmarkVectorCorrectnessCase(
        "c", (("1",), ("1",)), ("1",), "from_array", "to_array"
    ),
    BenchmarkVectorScalarCorrectnessCase(
        "c", ("1",), "2", ("3",), "from_array", "to_array"
    ),
    BenchmarkImmediateCorrectnessCase("c", ("1",), ("2",), "from_array", "to_array"),
    BenchmarkIndexedLoadCorrectnessCase(
        "c", ("1",), ("0",), ("1",), "si32", "int32_t", "from_array", "to_array"
    ),
    BenchmarkMaskCorrectnessCase("c", ("1",), "1", "to_integral"),
    BenchmarkVectorMaskCorrectnessCase("c", (("1",),), "1", "from_array", "to_integral"),
    BenchmarkReductionCorrectnessCase("c", ("1",), "1", "from_array"),
)
_BENCHMARK_CANDIDATE = BenchmarkCandidate("default", "body-hash")
_BENCHMARK_CANDIDATE_SET = BenchmarkCandidateSet(
    key=_SPECIALIZATION_KEY,
    specialization=cast(LoweredSpecialization, None),
    candidates=(_BENCHMARK_CANDIDATE,),
    correctness_cases=(_BENCHMARK_CORRECTNESS_CASES[0],),
    scenarios=(_BENCHMARK_SCENARIOS[0],),
    stable_id="stable",
)
_BENCHMARK_COVERAGE = BenchmarkCoverageEntry(
    "cpp", "avx2", "add", "add", "avx2", "si32", "v", ("v", "v"), None, (), (), "emitted"
)
_BENCHMARK_PROFILE = BenchmarkProfilePlan("cpp", "avx2", (_BENCHMARK_CANDIDATE_SET,), "m")
_BENCHMARK_PLAN = BenchmarkProjectPlan(
    profiles=(_BENCHMARK_PROFILE,), coverage=(_BENCHMARK_COVERAGE,)
)
_GENERATION_RESULT = GenerationResult(
    artifacts=ArtifactSet.create(()),
    rendered=RenderedProject(
        artifacts=ArtifactSet.create(()),
        verify=_VERIFY_PROJECT,
        value_tests=_VALUE_TEST_PLAN,
        benchmarks=_BENCHMARK_PLAN,
    ),
    diagnostics=(_DIAGNOSTIC,),
    coverage=(_COVERAGE,),
    skipped=(_SKIPPED,),
)


def _record(value: object, *path: object) -> dict[str, object]:
    for step in path:
        value = value[step]  # type: ignore[index]
    assert isinstance(value, dict), f"expected a serialized record at {path!r}"
    return value


def _serialized_records() -> list[tuple[object, dict[str, object]]]:
    """Every serialized domain value paired with its serializer's output."""

    repo_root = Path("/repo")
    semantics = serialize_generation_semantics(_GENERATION_RESULT, repo_root)
    records: list[tuple[object, dict[str, object]]] = [
        (
            Artifact("cpp/probe.hpp", "content", "text/x-c++hdr"),
            serialize_artifact(Artifact("cpp/probe.hpp", "content", "text/x-c++hdr")),
        ),
        (_LOCATION, semantics_module._serialize_location(_LOCATION, repo_root)),
        (_DIAGNOSTIC, _record(semantics, "diagnostics", 0)),
        (_COVERAGE, _record(semantics, "coverage", 0)),
        (_SKIPPED, _record(semantics, "skipped", 0)),
        (_VERIFY_PROJECT, _record(semantics, "verification")),
        (_VERIFY_BACKEND, _record(semantics, "verification", "backends", 0)),
        (
            _VERIFY_PROFILE,
            _record(semantics, "verification", "backends", 0, "profiles", 0),
        ),
        (
            _VERIFY_RUNNER,
            _record(
                semantics, "verification", "backends", 0, "profiles", 0, "runner"
            ),
        ),
        (_GENERATION_RESULT, semantics),
        (_VALUE_TEST_PLAN, _record(semantics, "value_tests")),
        (_VALUE_TEST_PROFILE, _record(semantics, "value_tests", "profiles", 0)),
        (_VALUE_TEST_COVERAGE, _record(semantics, "value_tests", "coverage", 0)),
        (
            _VALUE_TEST_CASE,
            _record(semantics, "value_tests", "profiles", 0, "cases", 0),
        ),
        (
            ValueTestInputs(),
            semantics_module._serialize_value_test_inputs(ValueTestInputs()),
        ),
        (
            ValueTestExpectation(),
            semantics_module._serialize_value_test_expectation(ValueTestExpectation()),
        ),
        (
            ValueTestInvocation(),
            semantics_module._serialize_value_test_invocation(ValueTestInvocation()),
        ),
        (
            ValueTestTarget("si32", "int32_t", 4),
            semantics_module._serialize_value_test_target(
                ValueTestTarget("si32", "int32_t", 4)
            ),
        ),
        (
            ValueTestIndex(value="1"),
            semantics_module._serialize_value_test_index(ValueTestIndex(value="1")),
        ),
        (
            ValueTestMemory(),
            semantics_module._serialize_value_test_memory(ValueTestMemory()),
        ),
        (
            ValueTestRepresentation("sse"),
            semantics_module._serialize_value_test_representation(
                ValueTestRepresentation("sse")
            ),
        ),
        (
            ValueTestScalable("sve", "{lanes}"),
            semantics_module._serialize_value_test_scalable(
                ValueTestScalable("sve", "{lanes}")
            ),
        ),
        (
            ValueTestDifferential("avx2", "from_array"),
            semantics_module._serialize_value_test_differential(
                ValueTestDifferential("avx2", "from_array")
            ),
        ),
        (_BENCHMARK_PLAN, _record(semantics, "benchmarks")),
        (_BENCHMARK_PROFILE, _record(semantics, "benchmarks", "profiles", 0)),
        (_BENCHMARK_COVERAGE, _record(semantics, "benchmarks", "coverage", 0)),
        (
            _BENCHMARK_CANDIDATE_SET,
            _record(semantics, "benchmarks", "profiles", 0, "candidate_sets", 0),
        ),
        (
            _BENCHMARK_CANDIDATE,
            _record(
                semantics,
                "benchmarks",
                "profiles",
                0,
                "candidate_sets",
                0,
                "candidates",
                0,
            ),
        ),
        (
            _SPECIALIZATION_KEY,
            semantics_module._serialize_specialization_key(_SPECIALIZATION_KEY),
        ),
        (
            _BENCHMARK_TIMING,
            _record(
                semantics_module._serialize_benchmark_scenario(
                    _BENCHMARK_SCENARIOS[0]
                ),
                "timing",
            ),
        ),
    ]
    records.extend(
        (case, semantics_module._serialize_benchmark_correctness(case))
        for case in _BENCHMARK_CORRECTNESS_CASES
    )
    records.extend(
        (scenario, semantics_module._serialize_benchmark_scenario(scenario))
        for scenario in _BENCHMARK_SCENARIOS
    )
    return records


def test_snapshot_serializers_cover_every_domain_dataclass_field() -> None:
    records = _serialized_records()
    checked_types = {type(value) for value, _ in records}
    stale_allowlist_types = set(_DELIBERATE_OMISSIONS) - checked_types
    assert not stale_allowlist_types, (
        f"allowlisted types are no longer serialized: {stale_allowlist_types}"
    )

    problems: list[str] = []
    for value, record in records:
        value_type = type(value)
        field_names = {field.name for field in dataclasses.fields(value_type)}
        allowed = _DELIBERATE_OMISSIONS.get(value_type, frozenset())
        stale_allowed = allowed - field_names
        if stale_allowed:
            problems.append(
                f"{value_type.__name__}: allowlist names unknown fields {sorted(stale_allowed)}"
            )
        no_longer_omitted = allowed & set(record)
        if no_longer_omitted:
            problems.append(
                f"{value_type.__name__}: allowlisted fields are now serialized "
                f"{sorted(no_longer_omitted)}; remove them from the allowlist"
            )
        missing = field_names - set(record) - allowed
        if missing:
            problems.append(
                f"{value_type.__name__}: fields missing from snapshot serialization "
                f"{sorted(missing)}"
            )
    assert not problems, "\n".join(problems)
