"""Plan benchmarkable implementation variants from finalized compiler facts."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re

from tslc.backend.emitted_profile import EmittedProfile
from tslc.benchmark.model import (
    BenchmarkCandidate,
    BenchmarkCandidateSet,
    BenchmarkCorrectnessCase,
    BenchmarkCoverageEntry,
    BenchmarkCoverageStatus,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkScenario,
    SpecializationKey,
)
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProjectPlan

_STABLE_ID_RE = re.compile(r"[^0-9A-Za-z_]+")
BENCHMARK_PROTOCOL_VERSION = 1


class BenchmarkPlanner:
    """Select the deliberately small first benchmark scenario family.

    Eligibility is expressed entirely through typed signature/catalog facts.
    Unsupported variant slots remain visible in coverage rather than being
    silently dropped or classified by primitive name.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._harness = discover_harness_primitives(catalog)

    def plan(
        self,
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
    ) -> BenchmarkProjectPlan:
        coverage: list[BenchmarkCoverageEntry] = []
        planned_profiles: list[BenchmarkProfilePlan] = []
        value_profiles = {
            (profile.backend_id, profile.profile_name): profile.cases
            for profile in value_tests.profiles
        }
        for emitted_profile in sorted(profiles, key=lambda item: item.profile.name):
            backend_id = "cpp"
            by_primitive = emitted_profile.specializations(backend_id)
            cases = value_profiles.get((backend_id, emitted_profile.profile.name), ())
            candidate_sets: list[BenchmarkCandidateSet] = []
            for primitive_name in sorted(by_primitive):
                for spec in sorted(
                    by_primitive[primitive_name], key=_specialization_sort_key
                ):
                    if not spec.variant_bodies:
                        continue
                    if _selector_slot_count(by_primitive[primitive_name], spec) > 1:
                        coverage.append(
                            _coverage(
                                emitted_profile,
                                spec,
                                "unsupported",
                                "overloaded selector slots require overload-specific policy identity",
                            )
                        )
                        continue
                    candidate_set, reason, missing_correctness = self._candidate_set(
                        emitted_profile,
                        by_primitive,
                        spec,
                        cases,
                    )
                    if candidate_set is None:
                        coverage.append(
                            _coverage(
                                emitted_profile,
                                spec,
                                "missing_correctness" if missing_correctness else "unsupported",
                                reason,
                            )
                        )
                        continue
                    candidate_sets.append(candidate_set)
                    coverage.append(_coverage(emitted_profile, spec, "emitted", ""))
            ordered_sets = tuple(sorted(candidate_sets, key=lambda item: item.stable_id))
            planned_profiles.append(
                BenchmarkProfilePlan(
                    backend_id=backend_id,
                    profile_name=emitted_profile.profile.name,
                    candidate_sets=ordered_sets,
                    manifest_hash=_manifest_hash(ordered_sets, emitted_profile),
                )
            )
        return BenchmarkProjectPlan(
            profiles=tuple(planned_profiles),
            # Harness-discovery diagnostics are already owned and reported by
            # ValueTestPlanner, whose typed case facts this planner consumes.
            diagnostics=(),
            coverage=tuple(sorted(coverage, key=_coverage_sort_key)),
        )

    def _candidate_set(
        self,
        profile: EmittedProfile,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
        spec: LoweredSpecialization,
        cases: tuple[ValueTestCasePlan, ...],
    ) -> tuple[BenchmarkCandidateSet | None, str, bool]:
        primitive = self._catalog.primitive(spec.source_primitive_name)
        extension = profile.extensions.get(spec.extension_name)
        reason = _unsupported_reason(spec, primitive, extension)
        if reason is not None:
            return None, reason, False
        assert primitive is not None and extension is not None
        bits = scalar_bit_width(spec.type_tag)
        assert bits is not None and extension.vector_bits > 0
        lanes = extension.vector_bits // bits
        if lanes <= 0:
            return None, "extension width does not contain a complete scalar lane", False
        from_array = self._harness.from_array
        to_array = self._harness.to_array
        if from_array is None or to_array is None:
            return None, "vector round-trip harness primitives were not discovered", True
        if from_array not in by_primitive or to_array not in by_primitive:
            return (
                None,
                "vector round-trip harness primitives are not in the emitted dependency closure",
                True,
            )
        correctness = _correctness_cases(
            cases,
            spec,
            lanes,
            from_array,
            to_array,
        )
        if not correctness:
            return None, "no authored expected-value case covers this specialization", True
        key = SpecializationKey(
            backend_id="cpp",
            profile_name=profile.profile.name,
            primitive_name=spec.primitive_name,
            source_primitive_name=spec.source_primitive_name,
            extension_name=spec.extension_name,
            type_tag=spec.type_tag,
            result_kind=spec.result_kind,
            param_kinds=spec.param_kinds,
            lanes=lanes,
        )
        candidates = (
            BenchmarkCandidate("default", _body_hash(spec.body_text)),
            *(
                BenchmarkCandidate(variant.name, _body_hash(variant.body_text))
                for variant in spec.variant_bodies
            ),
        )
        stable_id = _stable_id(key)
        seed = int(sha256(stable_id.encode("utf-8")).hexdigest()[:16], 16)
        scenarios = (
            BenchmarkScenario("throughput_independent", "throughput", seed),
            BenchmarkScenario(
                "latency_dependency_chain", "latency", seed ^ 0x9E3779B97F4A7C15
            ),
        )
        return (
            BenchmarkCandidateSet(
                key=key,
                specialization=spec,
                candidates=tuple(candidates),
                correctness_cases=correctness,
                scenarios=scenarios,
                stable_id=stable_id,
            ),
            "",
            False,
        )


def _unsupported_reason(
    spec: LoweredSpecialization,
    primitive: Primitive | None,
    extension: Extension | None,
) -> str | None:
    if primitive is None:
        return "source primitive is not present in the catalog"
    if primitive.cross_lane:
        return "cross-lane primitives require a dedicated benchmark scenario"
    if spec.result_kind != "v" or not spec.param_kinds or any(
        kind != "v" for kind in spec.param_kinds
    ):
        return "first benchmark slice supports vector results and vector-only operands"
    if spec.target is not None:
        return "representation changes require a dedicated benchmark scenario"
    if spec.mask_policy is not None:
        return "masked primitives require mask-density scenarios"
    if spec.axis or spec.immediate is not None or spec.generic_params or spec.type_params:
        return "axes, immediates, and generic parameters are not benchmarked yet"
    if spec.lane_list_params:
        return "lane-list primitives require a dedicated benchmark scenario"
    if spec.safety.caller_unsafe:
        return "caller-unsafe primitives are not benchmarked automatically"
    if spec.uses_sized_vector:
        return "sized vectors require a concrete benchmark lane policy"
    if extension is None or extension.vector_bits_kind != "fixed" or extension.vector_bits <= 0:
        return "only fixed-width hardware vectors are benchmarked"
    if not extension.default_test_target:
        return "extension is not enabled as a native value-test target"
    if extension.header_group_for_backend("cpp") is not None:
        return "opt-in header-group extensions are not benchmarked in the first slice"
    return None


def _correctness_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    from_array_name: str,
    to_array_name: str,
) -> tuple[BenchmarkCorrectnessCase, ...]:
    matching: list[BenchmarkCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "generic_golden"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or not case.inputs.vectors
            or len(case.inputs.vectors) != len(spec.param_kinds)
            or not case.expectation.values
        ):
            continue
        if any(len(values) != case.lanes for values in case.inputs.vectors):
            continue
        if len(case.expectation.values) != case.lanes:
            continue
        if case.case_name in seen:
            continue
        seen.add(case.case_name)
        matching.append(
            BenchmarkCorrectnessCase(
                case_name=case.case_name,
                vector_inputs=tuple(_tile(values, lanes) for values in case.inputs.vectors),
                expected=_tile(case.expectation.values, lanes),
                from_array_name=from_array_name,
                to_array_name=to_array_name,
            )
        )
    return tuple(matching)


def _tile(values: tuple[str, ...], lanes: int) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(values[index % len(values)] for index in range(lanes))


def _stable_id(key: SpecializationKey) -> str:
    readable = _STABLE_ID_RE.sub(
        "_",
        "_".join(
            (
                key.profile_name,
                key.primitive_name,
                key.extension_name,
                key.type_tag,
            )
        ),
    ).strip("_")
    digest = sha256(repr(key.canonical_fields()).encode("utf-8")).hexdigest()[:12]
    return f"{readable}_{digest}"


def _manifest_hash(
    candidate_sets: tuple[BenchmarkCandidateSet, ...],
    profile: EmittedProfile,
) -> str:
    payload = {
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "profile": {
            "name": profile.profile.name,
            "family": profile.profile.family,
            "features": sorted(profile.profile.features),
            "feature_spellings": sorted(profile.profile.alternatives.items()),
            "compile_modes": sorted(profile.profile.compile_modes),
            "cpp_flags": profile.profile.flags_for_backend("cpp"),
        },
        "candidate_sets": [
            {
                "key": candidate_set.key.canonical_fields(),
                "stable_id": candidate_set.stable_id,
                "candidates": [
                    (candidate.variant_id, candidate.body_hash)
                    for candidate in candidate_set.candidates
                ],
                "scenarios": [
                    (
                        scenario.scenario_id,
                        scenario.kind,
                        scenario.seed,
                        scenario.batch_size,
                        scenario.rounds,
                        scenario.minimum_sample_ns,
                    )
                    for scenario in candidate_set.scenarios
                ],
                "correctness": [
                    (
                        case.case_name,
                        case.vector_inputs,
                        case.expected,
                        case.from_array_name,
                        case.to_array_name,
                    )
                    for case in candidate_set.correctness_cases
                ],
                "required_features": sorted(
                    candidate_set.specialization.required_features
                ),
            }
            for candidate_set in candidate_sets
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _body_hash(body: str) -> str:
    return sha256(body.encode("utf-8")).hexdigest()


def _specialization_sort_key(spec: LoweredSpecialization) -> tuple[object, ...]:
    return (
        spec.primitive_name,
        spec.extension_name,
        spec.type_tag,
        spec.axis,
        spec.immediate or (),
        spec.lane_parameter or "",
    )


def _selector_slot_count(
    specializations: tuple[LoweredSpecialization, ...],
    selected: LoweredSpecialization,
) -> int:
    selected_key = _selector_slot_key(selected)
    return sum(
        _selector_slot_key(spec) == selected_key for spec in specializations
    )


def _selector_slot_key(spec: LoweredSpecialization) -> tuple[object, ...]:
    return (
        spec.extension_name,
        spec.type_tag,
        spec.target.vector_spelling if spec.target is not None else None,
        spec.axis,
        spec.immediate,
        spec.generic_params,
        tuple(
            (param.name, param.base_type_binding)
            for param in spec.type_params
        ),
        spec.lane_parameter,
    )


def _coverage(
    profile: EmittedProfile,
    spec: LoweredSpecialization,
    status: BenchmarkCoverageStatus,
    reason: str,
) -> BenchmarkCoverageEntry:
    return BenchmarkCoverageEntry(
        backend_id="cpp",
        profile_name=profile.profile.name,
        primitive_name=spec.primitive_name,
        extension_name=spec.extension_name,
        type_tag=spec.type_tag,
        status=status,
        reason=reason,
    )


def _coverage_sort_key(entry: BenchmarkCoverageEntry) -> tuple[str, ...]:
    return (
        entry.backend_id,
        entry.profile_name,
        entry.primitive_name,
        entry.extension_name,
        entry.type_tag,
        entry.status,
        entry.reason,
    )


__all__ = ("BENCHMARK_PROTOCOL_VERSION", "BenchmarkPlanner")
