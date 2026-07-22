"""Explicit semantic-record serializers for generation snapshots."""

from __future__ import annotations

from pathlib import Path

from tslc.benchmark.model import (
    BenchmarkCorrectnessCase,
    BenchmarkCoverageEntry,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkIndexedLoadScenario,
    BenchmarkMaskCorrectnessCase,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkScenario,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
    BenchmarkVectorScalarScenario,
    SpecializationKey,
)
from tslc.diagnostics import Diagnostic, SourceLocation, SourceSpan
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import (
    VerifyBackend,
    VerifyProfile,
    VerifyProject,
    VerifyRunner,
)
from tslc.pipeline import CoverageEntry, GenerationResult, SkippedEntry
from tslc.value_tests.case_components import (
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestFailure,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestRepresentation,
    ValueTestScalable,
    ValueTestTarget,
)
from tslc.value_tests.case_plan import ValueTestCasePlan
from tslc.value_tests.model import ValueTestCoverageEntry


def serialize_artifact(artifact: Artifact) -> dict[str, object]:
    return {
        "logical_path": artifact.logical_path,
        "sha256": artifact.digest,
        "byte_count": len(artifact.content.encode("utf-8")),
        "media_type": artifact.media_type,
        "metadata": [
            {"key": item.key, "value": item.value}
            for item in sorted(artifact.metadata, key=lambda value: (value.key, value.value))
        ],
    }


def serialize_generation_semantics(
    result: GenerationResult,
    repo_root: Path,
) -> dict[str, object]:
    rendered = result.rendered
    value_tests = rendered.value_tests if rendered is not None else None
    benchmarks = rendered.benchmarks if rendered is not None else None
    verification = rendered.verify if rendered is not None else VerifyProject(backends=())
    return {
        "diagnostics": [
            _serialize_diagnostic(item, repo_root) for item in result.diagnostics
        ],
        "coverage": [_serialize_coverage(item) for item in result.coverage],
        "skipped": [_serialize_skipped(item, repo_root) for item in result.skipped],
        "verification": _serialize_verify_project(verification),
        "value_tests": (
            {
                "profiles": [
                    {
                        "backend_id": profile.backend_id,
                        "profile_name": profile.profile_name,
                        "support_headers": profile.support_headers,
                        "cases": [_serialize_value_test_case(item) for item in profile.cases],
                    }
                    for profile in value_tests.profiles
                ],
                "diagnostics": [
                    _serialize_diagnostic(item, repo_root)
                    for item in value_tests.diagnostics
                ],
                "coverage": [
                    _serialize_value_test_coverage(item) for item in value_tests.coverage
                ],
            }
            if value_tests is not None
            else {"profiles": [], "diagnostics": [], "coverage": []}
        ),
        "benchmarks": (
            {
                "profiles": [
                    {
                        "backend_id": profile.backend_id,
                        "profile_name": profile.profile_name,
                        "manifest_hash": profile.manifest_hash,
                        "profile_family": profile.profile_family,
                        "backend_feature_spellings": profile.backend_feature_spellings,
                        "candidate_sets": [
                            {
                                "stable_id": item.stable_id,
                                "key": _serialize_specialization_key(item.key),
                                "candidates": [
                                    {
                                        "variant_id": candidate.variant_id,
                                        "body_hash": candidate.body_hash,
                                    }
                                    for candidate in item.candidates
                                ],
                                "correctness_cases": [
                                    _serialize_benchmark_correctness(case_item)
                                    for case_item in item.correctness_cases
                                ],
                                "scenarios": [
                                    _serialize_benchmark_scenario(scenario)
                                    for scenario in item.scenarios
                                ],
                            }
                            for item in profile.candidate_sets
                        ],
                    }
                    for profile in benchmarks.profiles
                ],
                "diagnostics": [
                    _serialize_diagnostic(item, repo_root)
                    for item in benchmarks.diagnostics
                ],
                "coverage": [
                    _serialize_benchmark_coverage(item) for item in benchmarks.coverage
                ],
            }
            if benchmarks is not None
            else {"profiles": [], "diagnostics": [], "coverage": []}
        ),
        "counts": {
            "artifacts": len(result.artifacts.artifacts),
            "diagnostics": len(result.diagnostics),
            "coverage": len(result.coverage),
            "skipped": len(result.skipped),
            "value_test_profiles": len(value_tests.profiles) if value_tests else 0,
            "benchmark_profiles": len(benchmarks.profiles) if benchmarks else 0,
        },
    }


def _serialize_location(
    location: SourceLocation | None,
    repo_root: Path,
) -> dict[str, object] | None:
    if location is None:
        return None
    return {
        "path": _relative_path(location.path, repo_root),
        "line": location.line,
        "column": location.column,
    }


def _serialize_span(
    span: SourceSpan | None,
    repo_root: Path,
) -> dict[str, object] | None:
    if span is None:
        return None
    return {
        "path": _relative_path(span.path, repo_root),
        "line": span.line,
        "column": span.column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def _serialize_diagnostic(
    diagnostic: Diagnostic,
    repo_root: Path,
) -> dict[str, object]:
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "span": _serialize_span(diagnostic.span, repo_root),
    }


def _serialize_coverage(entry: CoverageEntry) -> dict[str, object]:
    return {
        "profile": entry.profile,
        "backend": entry.backend,
        "primitive": entry.primitive,
        "extension": entry.extension,
        "type_tag": entry.type_tag,
        "source_primitive_name": entry.source_primitive_name,
        "result_kind": entry.result_kind,
        "param_kinds": entry.param_kinds,
        "mask_policy": entry.mask_policy,
        "axis": entry.axis,
        "variant_names": entry.variant_names,
    }


def _serialize_skipped(entry: SkippedEntry, repo_root: Path) -> dict[str, object]:
    record = _serialize_coverage(
        CoverageEntry(
            profile=entry.profile,
            backend=entry.backend,
            primitive=entry.primitive,
            extension=entry.extension,
            type_tag=entry.type_tag,
            source_primitive_name=entry.source_primitive_name,
            result_kind=entry.result_kind,
            param_kinds=entry.param_kinds,
            mask_policy=entry.mask_policy,
            axis=entry.axis,
            variant_names=entry.variant_names,
        )
    )
    record.update(
        {
            "status": entry.status,
            "reason": entry.reason,
            "diagnostics": [
                _serialize_diagnostic(item, repo_root) for item in entry.diagnostics
            ],
        }
    )
    return record


def _serialize_verify_project(project: VerifyProject) -> dict[str, object]:
    return {"backends": [_serialize_verify_backend(item) for item in project.backends]}


def _serialize_verify_backend(backend: VerifyBackend) -> dict[str, object]:
    return {
        "backend_id": backend.backend_id,
        "root_path": backend.root_path,
        "profiles": [_serialize_verify_profile(item) for item in backend.profiles],
    }


def _serialize_verify_profile(profile: VerifyProfile) -> dict[str, object]:
    return {
        "profile_name": profile.profile_name,
        "file_stem": profile.file_stem,
        "family": profile.family,
        "native_without_runner": profile.native_without_runner,
        "compile_modes": tuple(sorted(profile.compile_modes)),
        "flags": profile.flags,
        "target_features": profile.target_features,
        "target": profile.target,
        "linker": profile.linker,
        "runner": _serialize_verify_runner(profile.runner),
        "compile_failures": tuple(
            {
                "target_name": failure.target_name,
                "marker": failure.marker,
            }
            for failure in profile.compile_failures
        ),
    }


def _serialize_verify_runner(runner: VerifyRunner | None) -> dict[str, object] | None:
    if runner is None:
        return None
    return {"kind": runner.kind, "profile": runner.profile, "args": runner.args}


def _serialize_value_test_coverage(entry: ValueTestCoverageEntry) -> dict[str, object]:
    return {
        "backend_id": entry.backend_id,
        "profile_name": entry.profile_name,
        "primitive_name": entry.primitive_name,
        "case_name": entry.case_name,
        "status": entry.status,
        "reason": entry.reason,
        "case_kind": entry.case_kind,
    }


def _serialize_value_test_case(case: ValueTestCasePlan) -> dict[str, object]:
    return {
        "kind": case.kind,
        "function_name": case.function_name,
        "case_name": case.case_name,
        "call_name": case.call_name,
        "type_tag": case.type_tag,
        "base_spelling": case.base_spelling,
        "lanes": case.lanes,
        "inputs": _serialize_value_test_inputs(case.inputs),
        "expectation": _serialize_value_test_expectation(case.expectation),
        "failure": _serialize_value_test_failure(case.failure),
        "invocation": _serialize_value_test_invocation(case.invocation),
        "target": _serialize_value_test_target(case.target),
        "index": _serialize_value_test_index(case.index),
        "memory": _serialize_value_test_memory(case.memory),
        "representation": _serialize_value_test_representation(case.representation),
        "scalable": _serialize_value_test_scalable(case.scalable),
        "differential": _serialize_value_test_differential(case.differential),
        "header_group": case.header_group,
        "required_compiler_features": case.required_compiler_features,
    }


def _serialize_value_test_inputs(value: ValueTestInputs) -> dict[str, object]:
    return {
        "vectors": value.vectors,
        "masks": value.masks,
        "scalar": value.scalar,
        "scalars": value.scalars,
    }


def _serialize_value_test_expectation(value: ValueTestExpectation) -> dict[str, object]:
    return {"values": value.values, "text": value.text}


def _serialize_value_test_failure(
    value: ValueTestFailure | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {"reason": value.reason.value, "phase": value.phase}


def _serialize_value_test_invocation(value: ValueTestInvocation) -> dict[str, object]:
    return {
        "result_kind": value.result_kind,
        "param_kinds": value.param_kinds,
        "axis_args": value.axis_args,
        "immediate": value.immediate,
        "generic_defaults": value.generic_defaults,
        "inferred_type_args": value.inferred_type_args,
    }


def _serialize_value_test_target(value: ValueTestTarget | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "type_tag": value.type_tag,
        "base_spelling": value.base_spelling,
        "lanes": value.lanes,
    }


def _serialize_value_test_index(value: ValueTestIndex | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "value": value.value,
        "type_tag": value.type_tag,
        "base_spelling": value.base_spelling,
        "lanes": value.lanes,
        "style": value.style,
    }


def _serialize_value_test_memory(value: ValueTestMemory | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "buffer_offset": value.buffer_offset,
        "buffer_length": value.buffer_length,
        "source_offset": value.source_offset,
        "alignment": value.alignment,
        "storage": value.storage,
    }


def _serialize_value_test_representation(
    value: ValueTestRepresentation | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "source_extension": value.source_extension,
        "target_extension": value.target_extension,
        "from_array_name": value.from_array_name,
        "to_array_name": value.to_array_name,
    }


def _serialize_value_test_scalable(
    value: ValueTestScalable | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "source_extension": value.source_extension,
        "runtime_lanes_template": value.runtime_lanes_template,
        "mask_from_bits_template": value.mask_from_bits_template,
        "mask_check_template": value.mask_check_template,
        "mask_bits": value.mask_bits,
        "expected_mask_bits": value.expected_mask_bits,
        "load_name": value.load_name,
        "store_name": value.store_name,
    }


def _serialize_value_test_differential(
    value: ValueTestDifferential | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "hardware_extension": value.hardware_extension,
        "from_array_name": value.from_array_name,
        "to_array_name": value.to_array_name,
        "to_integral_name": value.to_integral_name,
        "to_mask_name": value.to_mask_name,
        "mask_from_bits_template": value.mask_from_bits_template,
        "nonzero_argument_index": value.nonzero_argument_index,
        "fuzz_seed": value.fuzz_seed,
        "fuzz_iterations": value.fuzz_iterations,
    }


def _serialize_specialization_key(key: SpecializationKey) -> dict[str, object]:
    return {
        "backend_id": key.backend_id,
        "profile_name": key.profile_name,
        "primitive_name": key.primitive_name,
        "source_primitive_name": key.source_primitive_name,
        "extension_name": key.extension_name,
        "type_tag": key.type_tag,
        "result_kind": key.result_kind,
        "param_kinds": key.param_kinds,
        "target_type_tag": key.target_type_tag,
        "target_extension_name": key.target_extension_name,
        "axis": key.axis,
        "immediate": key.immediate,
        "generic_values": key.generic_values,
        "simd_type_base_bindings": key.simd_type_base_bindings,
        "overload_parameter_positions": key.overload_parameter_positions,
        "lanes": key.lanes,
        "header_group": key.header_group,
    }


def _serialize_benchmark_coverage(entry: BenchmarkCoverageEntry) -> dict[str, object]:
    return {
        "backend_id": entry.backend_id,
        "profile_name": entry.profile_name,
        "primitive_name": entry.primitive_name,
        "source_primitive_name": entry.source_primitive_name,
        "extension_name": entry.extension_name,
        "type_tag": entry.type_tag,
        "result_kind": entry.result_kind,
        "param_kinds": entry.param_kinds,
        "mask_policy": entry.mask_policy,
        "axis": entry.axis,
        "variant_names": entry.variant_names,
        "status": entry.status,
        "reason": entry.reason,
    }


def _serialize_benchmark_correctness(
    case: BenchmarkCorrectnessCase,
) -> dict[str, object]:
    if isinstance(case, BenchmarkVectorCorrectnessCase):
        return {
            "kind": "vector",
            "case_name": case.case_name,
            "vector_inputs": case.vector_inputs,
            "expected": case.expected,
            "from_array_name": case.from_array_name,
            "to_array_name": case.to_array_name,
        }
    if isinstance(case, BenchmarkVectorScalarCorrectnessCase):
        return {
            "kind": "vector_scalar",
            "case_name": case.case_name,
            "vector_input": case.vector_input,
            "scalar_input": case.scalar_input,
            "expected": case.expected,
            "from_array_name": case.from_array_name,
            "to_array_name": case.to_array_name,
        }
    if isinstance(case, BenchmarkImmediateCorrectnessCase):
        return {
            "kind": "immediate",
            "case_name": case.case_name,
            "vector_input": case.vector_input,
            "expected": case.expected,
            "from_array_name": case.from_array_name,
            "to_array_name": case.to_array_name,
        }
    if isinstance(case, BenchmarkIndexedLoadCorrectnessCase):
        return {
            "kind": "indexed_load",
            "case_name": case.case_name,
            "memory_values": case.memory_values,
            "index_values": case.index_values,
            "expected": case.expected,
            "index_type_tag": case.index_type_tag,
            "index_base_spelling": case.index_base_spelling,
            "from_array_name": case.from_array_name,
            "to_array_name": case.to_array_name,
        }
    if isinstance(case, BenchmarkMaskCorrectnessCase):
        return {
            "kind": "mask",
            "case_name": case.case_name,
            "mask_inputs": case.mask_inputs,
            "expected_mask": case.expected_mask,
            "to_integral_name": case.to_integral_name,
        }
    if isinstance(case, BenchmarkVectorMaskCorrectnessCase):
        return {
            "kind": "vector_mask",
            "case_name": case.case_name,
            "vector_inputs": case.vector_inputs,
            "expected_mask": case.expected_mask,
            "from_array_name": case.from_array_name,
            "to_integral_name": case.to_integral_name,
        }
    if isinstance(case, BenchmarkReductionCorrectnessCase):
        return {
            "kind": "reduction",
            "case_name": case.case_name,
            "vector_input": case.vector_input,
            "expected": case.expected,
            "from_array_name": case.from_array_name,
        }
    raise TypeError(f"unsupported benchmark correctness case {type(case).__name__}")


def _serialize_benchmark_scenario(scenario: BenchmarkScenario) -> dict[str, object]:
    timing = {
        "seed": scenario.timing.seed,
        "batch_size": scenario.timing.batch_size,
        "rounds": scenario.timing.rounds,
        "minimum_sample_ns": scenario.timing.minimum_sample_ns,
    }
    common: dict[str, object] = {
        "scenario_id": scenario.scenario_id,
        "kind": scenario.kind,
        "timing": timing,
    }
    if isinstance(scenario, BenchmarkRegisterScenario):
        common.update(
            {
                "shape": "register",
                "operand_generators": scenario.operand_generators,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkVectorScalarScenario):
        common.update(
            {
                "shape": "vector_scalar",
                "vector_generator": scenario.vector_generator,
                "scalar_generator": scenario.scalar_generator,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkImmediateScenario):
        common.update(
            {
                "shape": "immediate",
                "operand_generator": scenario.operand_generator,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkIndexedLoadScenario):
        common.update(
            {
                "shape": "indexed_load",
                "memory_bytes": scenario.memory_bytes,
                "index_lanes": scenario.index_lanes,
            }
        )
    elif isinstance(scenario, BenchmarkMaskDensityScenario):
        common.update(
            {
                "shape": "mask_density",
                "parameter_index": scenario.parameter_index,
                "active_lanes": scenario.active_lanes,
            }
        )
    elif isinstance(scenario, BenchmarkMaskResultScenario):
        common.update(
            {
                "shape": "mask_result",
                "operand_generators": scenario.operand_generators,
            }
        )
    elif isinstance(scenario, BenchmarkReductionScenario):
        common.update(
            {"shape": "reduction", "operand_generator": scenario.operand_generator}
        )
    else:
        raise TypeError(f"unsupported benchmark scenario {type(scenario).__name__}")
    return common


def _relative_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


__all__ = ("serialize_artifact", "serialize_generation_semantics")
