"""Plan benchmarkable implementation variants from finalized compiler facts."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re

from tslc.backend.emitted_profile import EmittedProfile
from tslc.benchmark.correctness import (
    immediate_cases as _immediate_correctness_cases,
    immediate_values as _immediate_values,
    indexed_load_bindings as _indexed_load_bindings,
    indexed_load_cases as _indexed_load_correctness_cases,
    mask_cases as _mask_correctness_cases,
    reduction_cases as _reduction_correctness_cases,
    vector_cases as _vector_correctness_cases,
    vector_mask_cases as _vector_mask_correctness_cases,
    vector_scalar_cases as _vector_scalar_correctness_cases,
)
from tslc.benchmark.model import (
    BenchmarkCandidate,
    BenchmarkCandidateSet,
    BenchmarkCorrectnessCase,
    BenchmarkCoverageEntry,
    BenchmarkCoverageStatus,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkMaskCorrectnessCase,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkReductionCorrectnessCase,
    BenchmarkScenario,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
    SpecializationKey,
)
from tslc.benchmark.scenarios import (
    immediate_scenarios,
    indexed_load_scenarios,
    mask_density_scenarios,
    mask_result_scenarios,
    reduction_scenarios,
    register_scenarios,
    vector_scalar_scenarios,
)
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.catalog.signatures import parse_signature
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProjectPlan

_STABLE_ID_RE = re.compile(r"[^0-9A-Za-z_]+")
BENCHMARK_PROTOCOL_VERSION = 1


class CppBenchmarkPlanner:
    """Plan typed benchmark scenarios for authored implementation variants.

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
                    bindings: tuple[
                        tuple[str | None, tuple[tuple[str, str], ...]], ...
                    ] = ((None, ()),)
                    if spec.type_params and _is_indexed_load_shape(spec):
                        bindings = _indexed_load_bindings(cases, spec)
                    elif spec.immediate is not None:
                        bindings = tuple(
                            (value, ()) for value in _immediate_values(cases, spec)
                        )
                    candidate_sets_for_spec: list[BenchmarkCandidateSet] = []
                    reason = "no authored immediate case covers this specialization"
                    missing_correctness = spec.immediate is not None
                    for immediate_value, type_bindings in bindings:
                        candidate_set, reason, missing_correctness = self._candidate_set(
                            emitted_profile,
                            by_primitive,
                            spec,
                            cases,
                            immediate_value=immediate_value,
                            simd_type_base_bindings=type_bindings,
                        )
                        if candidate_set is not None:
                            candidate_sets_for_spec.append(candidate_set)
                    if not candidate_sets_for_spec:
                        coverage.append(
                            _coverage(
                                emitted_profile,
                                spec,
                                "missing_correctness" if missing_correctness else "unsupported",
                                reason,
                            )
                        )
                        continue
                    candidate_sets.extend(candidate_sets_for_spec)
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
        *,
        immediate_value: str | None,
        simd_type_base_bindings: tuple[tuple[str, str], ...],
    ) -> tuple[BenchmarkCandidateSet | None, str, bool]:
        primitive = _source_primitive(self._catalog, spec)
        extension = profile.extensions.get(spec.extension_name)
        reason = _common_unsupported_reason(spec, primitive, extension)
        if reason is not None:
            return None, reason, False
        assert primitive is not None and extension is not None
        bits = scalar_bit_width(spec.type_tag)
        assert bits is not None and extension.vector_bits > 0
        lanes = extension.vector_bits // bits
        if lanes <= 0:
            return None, "extension width does not contain a complete scalar lane", False
        key = SpecializationKey(
            backend_id="cpp",
            profile_name=profile.profile.name,
            primitive_name=spec.primitive_name,
            source_primitive_name=spec.source_primitive_name,
            extension_name=spec.extension_name,
            type_tag=spec.type_tag,
            result_kind=spec.result_kind,
            param_kinds=spec.param_kinds,
            immediate=immediate_value,
            simd_type_base_bindings=simd_type_base_bindings,
            generic_values=tuple(
                (name, default) for name, _type, default in spec.generic_params
            ),
            overload_parameter_positions=varying_positions(
                by_primitive[spec.primitive_name]
            ),
            lanes=lanes,
        )
        stable_id = _stable_id(key)
        seed = int(sha256(stable_id.encode("utf-8")).hexdigest()[:16], 16)
        correctness: tuple[BenchmarkCorrectnessCase, ...]
        scenarios: tuple[BenchmarkScenario, ...]
        if _is_indexed_load_shape(spec):
            if immediate_value is None or len(simd_type_base_bindings) != 1:
                return None, "no concrete indexed-load binding was planned", True
            try:
                scale = int(immediate_value, 0)
            except ValueError:
                return None, "indexed-load scale is not a concrete integer", False
            if scale != bits // 8:
                return (
                    None,
                    "indexed-load benchmark requires an element-sized scale",
                    False,
                )
            from_array = self._harness.from_array
            to_array = self._harness.to_array
            if from_array is None or to_array is None:
                return None, "indexed-load harness primitives were not discovered", True
            if from_array not in by_primitive or to_array not in by_primitive:
                return (
                    None,
                    "indexed-load harness primitives are not in the emitted dependency closure",
                    True,
                )
            index_type_tag = simd_type_base_bindings[0][1]
            index_bits = scalar_bit_width(index_type_tag)
            if index_bits is None or extension.vector_bits % index_bits:
                return None, "indexed-load type does not have a fixed lane count", False
            if not all(
                _has_vector_specialization(
                    by_primitive,
                    primitive_name,
                    spec.extension_name,
                    index_type_tag,
                )
                for primitive_name in (from_array, to_array)
            ):
                return (
                    None,
                    "indexed-load SIMD-type harness specializations are not in the emitted closure",
                    True,
                )
            index_lanes = extension.vector_bits // index_bits
            correctness = _indexed_load_correctness_cases(
                cases,
                spec,
                lanes,
                index_lanes,
                immediate_value,
                index_type_tag,
                from_array,
                to_array,
            )
            scenarios = indexed_load_scenarios(index_lanes, seed)
        elif spec.result_kind == "v" and spec.param_kinds == ("v", "sImm"):
            if immediate_value is None:
                return None, "no concrete immediate value was planned", True
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
            correctness = _immediate_correctness_cases(
                cases,
                spec,
                lanes,
                immediate_value,
                from_array,
                to_array,
            )
            scenarios = immediate_scenarios(primitive, spec, seed)
        elif spec.result_kind == "v" and spec.param_kinds == ("v", "s"):
            if primitive.cross_lane:
                return (
                    None,
                    "cross-lane vector results require a dedicated benchmark scenario",
                    False,
                )
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
            correctness = _vector_scalar_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_array,
            )
            scenarios = vector_scalar_scenarios(primitive, spec, seed)
        elif spec.result_kind == "v" and spec.param_kinds and all(
            kind == "v" for kind in spec.param_kinds
        ):
            if primitive.cross_lane:
                return (
                    None,
                    "cross-lane vector results require a dedicated benchmark scenario",
                    False,
                )
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
            correctness = _vector_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_array,
            )
            scenarios = register_scenarios(primitive, spec, seed)
        elif spec.result_kind == "m" and spec.param_kinds and all(
            kind == "v" for kind in spec.param_kinds
        ):
            from_array = self._harness.from_array
            to_integral = self._harness.to_integral
            if from_array is None or to_integral is None:
                return (
                    None,
                    "vector-to-mask harness primitives were not discovered",
                    True,
                )
            if from_array not in by_primitive or to_integral not in by_primitive:
                return (
                    None,
                    "vector-to-mask harness primitives are not in the emitted dependency closure",
                    True,
                )
            correctness = _vector_mask_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_integral,
            )
            scenarios = mask_result_scenarios(primitive, spec, seed)
        elif spec.result_kind == "s" and spec.param_kinds == ("v",):
            from_array = self._harness.from_array
            if from_array is None:
                return None, "vector construction harness primitive was not discovered", True
            if from_array not in by_primitive:
                return (
                    None,
                    "vector construction harness primitive is not in the emitted dependency closure",
                    True,
                )
            correctness = _reduction_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
            )
            scenarios = reduction_scenarios(seed)
        elif spec.result_kind == "m" and spec.param_kinds == ("im",):
            to_integral = self._harness.to_integral
            if to_integral is None:
                return None, "mask round-trip harness primitive was not discovered", True
            if to_integral not in by_primitive:
                return (
                    None,
                    "mask round-trip harness primitive is not in the emitted dependency closure",
                    True,
                )
            correctness = _mask_correctness_cases(cases, spec, lanes, to_integral)
            scenarios = mask_density_scenarios(lanes, seed)
        else:
            return (
                None,
                "no typed benchmark scenario supports this result and parameter shape",
                False,
            )
        if not correctness:
            return None, "no authored expected-value case covers this specialization", True
        candidates = (
            BenchmarkCandidate("default", _body_hash(spec.body_text)),
            *(
                BenchmarkCandidate(variant.name, _body_hash(variant.body_text))
                for variant in spec.variant_bodies
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


def _common_unsupported_reason(
    spec: LoweredSpecialization,
    primitive: Primitive | None,
    extension: Extension | None,
) -> str | None:
    if primitive is None:
        return "source primitive is not present in the catalog"
    if primitive.cross_lane and not (
        (spec.result_kind == "s" and spec.param_kinds == ("v",))
        or _is_indexed_load_shape(spec)
    ):
        return "cross-lane primitives require a dedicated benchmark scenario"
    if spec.target is not None:
        return "representation changes require a dedicated benchmark scenario"
    if spec.mask_policy is not None:
        return "masked primitives require mask-density scenarios"
    if spec.axis or (spec.type_params and not _is_indexed_load_shape(spec)):
        return "axes and SIMD-type parameters are not benchmarked yet"
    if spec.immediate is not None and not (
        (spec.result_kind == "v" and spec.param_kinds == ("v", "sImm"))
        or _is_indexed_load_shape(spec)
    ):
        return "this immediate result and parameter shape is not benchmarked yet"
    if spec.lane_list_params:
        return "lane-list primitives require a dedicated benchmark scenario"
    if spec.safety.caller_unsafe and not _is_indexed_load_shape(spec):
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


def _is_indexed_load_shape(spec: LoweredSpecialization) -> bool:
    return (
        spec.result_kind == "v"
        and spec.param_kinds == ("cptr", "vidx", "sImm")
        and spec.immediate is not None
        and len(spec.type_params) == 1
        and spec.target is None
    )


def _has_vector_specialization(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    primitive_name: str,
    extension_name: str,
    type_tag: str,
) -> bool:
    return any(
        candidate.extension_name == extension_name
        and candidate.type_tag == type_tag
        for candidate in by_primitive.get(primitive_name, ())
    )


def _source_primitive(
    catalog: Catalog,
    spec: LoweredSpecialization,
) -> Primitive | None:
    for primitive in catalog.primitives_named(spec.source_primitive_name):
        shape = parse_signature(primitive.signature)
        if (
            shape is not None
            and shape.result_kind == spec.result_kind
            and shape.param_kinds == spec.param_kinds
            and primitive.attributes.get("mask") == spec.mask_policy
        ):
            return primitive
    return None


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
                    scenario.canonical_fields()
                    for scenario in candidate_set.scenarios
                ],
                "correctness": [
                    _correctness_canonical_fields(case)
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


def _correctness_canonical_fields(
    case: (
        BenchmarkVectorCorrectnessCase
        | BenchmarkImmediateCorrectnessCase
        | BenchmarkIndexedLoadCorrectnessCase
        | BenchmarkMaskCorrectnessCase
        | BenchmarkVectorMaskCorrectnessCase
        | BenchmarkVectorScalarCorrectnessCase
        | BenchmarkReductionCorrectnessCase
    ),
) -> tuple[object, ...]:
    if isinstance(case, BenchmarkVectorCorrectnessCase):
        return (
            "vector",
            case.case_name,
            case.vector_inputs,
            case.expected,
            case.from_array_name,
            case.to_array_name,
        )
    if isinstance(case, BenchmarkImmediateCorrectnessCase):
        return (
            "immediate",
            case.case_name,
            case.vector_input,
            case.expected,
            case.from_array_name,
            case.to_array_name,
        )
    if isinstance(case, BenchmarkIndexedLoadCorrectnessCase):
        return (
            "indexed_load",
            case.case_name,
            case.memory_values,
            case.index_values,
            case.expected,
            case.index_type_tag,
            case.index_base_spelling,
            case.from_array_name,
            case.to_array_name,
        )
    if isinstance(case, BenchmarkVectorScalarCorrectnessCase):
        return (
            "vector_scalar",
            case.case_name,
            case.vector_input,
            case.scalar_input,
            case.expected,
            case.from_array_name,
            case.to_array_name,
        )
    if isinstance(case, BenchmarkReductionCorrectnessCase):
        return (
            "reduction",
            case.case_name,
            case.vector_input,
            case.expected,
            case.from_array_name,
        )
    if isinstance(case, BenchmarkVectorMaskCorrectnessCase):
        return (
            "vector_mask",
            case.case_name,
            case.vector_inputs,
            case.expected_mask,
            case.from_array_name,
            case.to_integral_name,
        )
    return (
        "mask",
        case.case_name,
        case.mask_inputs,
        case.expected_mask,
        case.to_integral_name,
    )


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
        spec.param_kinds,
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
        source_primitive_name=spec.source_primitive_name,
        extension_name=spec.extension_name,
        type_tag=spec.type_tag,
        result_kind=spec.result_kind,
        param_kinds=spec.param_kinds,
        mask_policy=spec.mask_policy,
        axis=spec.axis,
        variant_names=spec.variant_names,
        status=status,
        reason=reason,
    )


def _coverage_sort_key(entry: BenchmarkCoverageEntry) -> tuple[str, ...]:
    return (
        entry.backend_id,
        entry.profile_name,
        entry.primitive_name,
        entry.source_primitive_name,
        entry.extension_name,
        entry.type_tag,
        entry.result_kind,
        ",".join(entry.param_kinds),
        entry.mask_policy or "",
        ",".join(f"{name}={value}" for name, value in entry.axis),
        ",".join(entry.variant_names),
        entry.status,
        entry.reason,
    )


__all__ = ("BENCHMARK_PROTOCOL_VERSION", "CppBenchmarkPlanner")
