"""Plan benchmarkable implementation variants from finalized compiler facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json

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
from tslc.benchmark.identity import (
    benchmark_slot_identity_hash,
    implementation_body_hash,
    specialization_key,
    specialization_stable_id,
)
from tslc.benchmark.model import (
    BenchmarkCandidate,
    BenchmarkCandidateSet,
    BenchmarkCorrectnessCase,
    BenchmarkCoverageEntry,
    BenchmarkCoverageStatus,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkScenario,
    BenchmarkScenarioFamily,
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
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.catalog.signatures import parse_signature
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.lane_math import tiling_preserves_lane_semantics, whole_lanes
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProjectPlan

BENCHMARK_PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class BenchmarkProfileContext:
    """Exact machine-profile facts admitted by a backend benchmark pilot."""

    profile_name: str
    profile_family: str
    features: frozenset[str]
    backend_feature_spellings: tuple[str, ...]
    compile_modes: frozenset[str]
    backend_flags: tuple[str, ...]

    @classmethod
    def from_profile(
        cls,
        profile: MachineProfile,
        backend_id: str,
    ) -> BenchmarkProfileContext:
        return cls(
            profile_name=profile.name,
            profile_family=profile.family,
            features=profile.features,
            backend_feature_spellings=tuple(
                profile.feature_spelling(feature, backend_id)
                for feature in sorted(profile.features)
            ),
            compile_modes=profile.compile_modes,
            backend_flags=profile.flags_for_backend(backend_id),
        )


class BenchmarkPlanner:
    """Plan typed benchmark scenarios for one generated backend.

    Eligibility is expressed entirely through typed signature/catalog facts.
    Unsupported variant slots remain visible in coverage rather than being
    silently dropped or classified by primitive name.
    """

    def __init__(
        self,
        catalog: Catalog,
        *,
        backend_id: str,
        supported_scenario_families: frozenset[BenchmarkScenarioFamily] | None = None,
        supported_profile_contexts: frozenset[BenchmarkProfileContext] | None = None,
    ) -> None:
        if not backend_id:
            raise ValueError("benchmark planner requires a backend ID")
        self._catalog = catalog
        self._backend_id = backend_id
        self._supported_scenario_families = supported_scenario_families
        self._supported_profile_contexts = supported_profile_contexts
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
            backend_id = self._backend_id
            profile_support_reason = _profile_support_reason(
                emitted_profile.profile,
                backend_id,
                self._supported_profile_contexts,
            )
            by_primitive = emitted_profile.specializations(backend_id)
            cases = value_profiles.get((backend_id, emitted_profile.profile.name), ())
            candidate_sets: list[BenchmarkCandidateSet] = []
            for primitive_name in sorted(by_primitive):
                for spec in sorted(
                    by_primitive[primitive_name], key=_specialization_sort_key
                ):
                    if not spec.variant_bodies:
                        continue
                    if profile_support_reason is not None:
                        coverage.append(
                            _coverage(
                                emitted_profile,
                                spec,
                                backend_id,
                                "unsupported",
                                profile_support_reason,
                            )
                        )
                        continue
                    if _selector_slot_count(by_primitive[primitive_name], spec) > 1:
                        coverage.append(
                            _coverage(
                                emitted_profile,
                                spec,
                                backend_id,
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
                                backend_id,
                                "missing_correctness" if missing_correctness else "unsupported",
                                reason,
                            )
                        )
                        continue
                    candidate_sets.extend(candidate_sets_for_spec)
                    coverage.append(
                        _coverage(emitted_profile, spec, backend_id, "emitted", "")
                    )
            ordered_sets = tuple(sorted(candidate_sets, key=lambda item: item.stable_id))
            planned_profiles.append(
                BenchmarkProfilePlan(
                    backend_id=backend_id,
                    profile_name=emitted_profile.profile.name,
                    candidate_sets=ordered_sets,
                    manifest_hash=_manifest_hash(
                        ordered_sets, emitted_profile, backend_id
                    ),
                    profile_family=emitted_profile.profile.family,
                    backend_feature_spellings=tuple(
                        emitted_profile.profile.feature_spelling(feature, backend_id)
                        for feature in sorted(emitted_profile.profile.features)
                    ),
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
        reason = _common_unsupported_reason(
            spec, primitive, extension, self._backend_id
        )
        if reason is not None:
            return None, reason, False
        assert primitive is not None and extension is not None
        bits = scalar_bit_width(spec.type_tag)
        assert bits is not None and extension.vector_bits > 0
        key = specialization_key(
            backend_id=self._backend_id,
            profile=profile,
            specialization=spec,
            primitive_specializations=by_primitive[spec.primitive_name],
            immediate_value=immediate_value,
            simd_type_base_bindings=simd_type_base_bindings,
        )
        if key.lanes is None:
            return None, "extension width does not contain a complete scalar lane", False
        lanes = key.lanes
        scenario_family = _scenario_family(spec)
        if scenario_family is None:
            return (
                None,
                "no typed benchmark scenario supports this result and parameter shape",
                False,
            )
        if (
            self._supported_scenario_families is not None
            and scenario_family not in self._supported_scenario_families
        ):
            return (
                None,
                "backend benchmark support does not include the "
                f"{scenario_family!r} scenario family",
                False,
            )
        stable_id = specialization_stable_id(key)
        seed = int(sha256(stable_id.encode("utf-8")).hexdigest()[:16], 16)
        correctness: tuple[BenchmarkCorrectnessCase, ...]
        scenarios: tuple[BenchmarkScenario, ...]
        if scenario_family == "indexed_load":
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
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array, self._harness.to_array),
                missing_reason="indexed-load harness primitives were not discovered",
                closure_reason=(
                    "indexed-load harness primitives are not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            from_array, to_array = harness
            index_type_tag = simd_type_base_bindings[0][1]
            index_lanes = whole_lanes(extension.vector_bits, index_type_tag)
            if index_lanes is None:
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
        elif scenario_family == "immediate":
            if immediate_value is None:
                return None, "no concrete immediate value was planned", True
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array, self._harness.to_array),
                missing_reason="vector round-trip harness primitives were not discovered",
                closure_reason=(
                    "vector round-trip harness primitives are not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            from_array, to_array = harness
            correctness = _immediate_correctness_cases(
                cases,
                spec,
                lanes,
                immediate_value,
                from_array,
                to_array,
                allow_tiling=tiling_preserves_lane_semantics(primitive),
            )
            scenarios = immediate_scenarios(primitive, spec, seed)
        elif scenario_family == "vector_scalar":
            if not tiling_preserves_lane_semantics(primitive):
                return (
                    None,
                    "cross-lane vector results require a dedicated benchmark scenario",
                    False,
                )
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array, self._harness.to_array),
                missing_reason="vector round-trip harness primitives were not discovered",
                closure_reason=(
                    "vector round-trip harness primitives are not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            from_array, to_array = harness
            correctness = _vector_scalar_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_array,
            )
            scenarios = vector_scalar_scenarios(primitive, spec, seed)
        elif scenario_family == "register":
            if not tiling_preserves_lane_semantics(primitive):
                return (
                    None,
                    "cross-lane vector results require a dedicated benchmark scenario",
                    False,
                )
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array, self._harness.to_array),
                missing_reason="vector round-trip harness primitives were not discovered",
                closure_reason=(
                    "vector round-trip harness primitives are not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            from_array, to_array = harness
            correctness = _vector_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_array,
            )
            scenarios = register_scenarios(primitive, spec, seed)
        elif scenario_family == "mask_result":
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array, self._harness.to_integral),
                missing_reason="vector-to-mask harness primitives were not discovered",
                closure_reason=(
                    "vector-to-mask harness primitives are not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            from_array, to_integral = harness
            correctness = _vector_mask_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
                to_integral,
            )
            scenarios = mask_result_scenarios(primitive, spec, seed)
        elif scenario_family == "reduction":
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.from_array,),
                missing_reason="vector construction harness primitive was not discovered",
                closure_reason=(
                    "vector construction harness primitive is not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            (from_array,) = harness
            correctness = _reduction_correctness_cases(
                cases,
                spec,
                lanes,
                from_array,
            )
            scenarios = reduction_scenarios(seed)
        elif scenario_family == "mask_density":
            harness, harness_reason = _require_harness(
                by_primitive,
                (self._harness.to_integral,),
                missing_reason="mask round-trip harness primitive was not discovered",
                closure_reason=(
                    "mask round-trip harness primitive is not in the emitted dependency closure"
                ),
            )
            if harness is None:
                return None, harness_reason, True
            (to_integral,) = harness
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
            BenchmarkCandidate("default", implementation_body_hash(spec.body_text)),
            *(
                BenchmarkCandidate(
                    variant.name, implementation_body_hash(variant.body_text)
                )
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


def _require_harness(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    names: tuple[str | None, ...],
    *,
    missing_reason: str,
    closure_reason: str,
) -> tuple[tuple[str, ...] | None, str]:
    if any(name is None for name in names):
        return None, missing_reason
    resolved = tuple(name for name in names if name is not None)
    if any(name not in by_primitive for name in resolved):
        return None, closure_reason
    return resolved, ""


def _profile_support_reason(
    profile: MachineProfile,
    backend_id: str,
    supported: frozenset[BenchmarkProfileContext] | None,
) -> str | None:
    if supported is None:
        return None
    context = BenchmarkProfileContext.from_profile(profile, backend_id)
    if context in supported:
        return None
    if not any(item.profile_family == context.profile_family for item in supported):
        return (
            "backend benchmark support does not include the "
            f"{context.profile_family!r} profile family"
        )
    if not any(
        item.profile_family == context.profile_family
        and item.profile_name == context.profile_name
        for item in supported
    ):
        return (
            "backend benchmark support does not include profile "
            f"{context.profile_name!r}"
        )
    return (
        "backend benchmark support requires the canonical feature/build context "
        f"for profile {context.profile_name!r}"
    )


def _common_unsupported_reason(
    spec: LoweredSpecialization,
    primitive: Primitive | None,
    extension: Extension | None,
    backend_id: str,
) -> str | None:
    if primitive is None:
        return "source primitive is not present in the catalog"
    if not tiling_preserves_lane_semantics(primitive) and not (
        (spec.result_kind == "s" and spec.param_kinds == ("v",))
        or (spec.result_kind == "v" and spec.param_kinds == ("v", "sImm"))
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
    if extension.header_group_for_backend(backend_id) is not None:
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


def _scenario_family(
    spec: LoweredSpecialization,
) -> BenchmarkScenarioFamily | None:
    if _is_indexed_load_shape(spec):
        return "indexed_load"
    if spec.result_kind == "v" and spec.param_kinds == ("v", "sImm"):
        return "immediate"
    if spec.result_kind == "v" and spec.param_kinds == ("v", "s"):
        return "vector_scalar"
    if (
        spec.result_kind == "v"
        and spec.param_kinds
        and all(kind == "v" for kind in spec.param_kinds)
    ):
        return "register"
    if (
        spec.result_kind == "m"
        and spec.param_kinds
        and all(kind == "v" for kind in spec.param_kinds)
    ):
        return "mask_result"
    if spec.result_kind == "s" and spec.param_kinds == ("v",):
        return "reduction"
    if spec.result_kind == "m" and spec.param_kinds == ("im",):
        return "mask_density"
    return None


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


def _manifest_hash(
    candidate_sets: tuple[BenchmarkCandidateSet, ...],
    profile: EmittedProfile,
    backend_id: str,
) -> str:
    payload = {
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "profile": {
            "name": profile.profile.name,
            "family": profile.profile.family,
            "features": sorted(profile.profile.features),
            "feature_spellings": sorted(
                profile.profile.feature_spellings(backend_id).items()
            ),
            "compile_modes": sorted(profile.profile.compile_modes),
            f"{backend_id}_flags": profile.profile.flags_for_backend(backend_id),
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
                    case.canonical_fields()
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
    backend_id: str,
    status: BenchmarkCoverageStatus,
    reason: str,
) -> BenchmarkCoverageEntry:
    return BenchmarkCoverageEntry(
        backend_id=backend_id,
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
        slot_hash=(
            benchmark_slot_identity_hash(profile.profile.name, spec)
            if backend_id == "rust"
            else ""
        ),
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
        entry.slot_hash,
        entry.status,
        entry.reason,
    )


__all__ = (
    "BENCHMARK_PROTOCOL_VERSION",
    "BenchmarkPlanner",
    "BenchmarkProfileContext",
)
