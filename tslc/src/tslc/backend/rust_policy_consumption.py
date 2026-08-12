"""Typed join between Rust benchmark evidence and policy-selection mappings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TypeVar

from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionCoverageEntry,
    RustPolicySelectionPlan,
    RustPolicySelectionProfile,
    RustPolicySelectionStatus,
    rust_policy_selection_shape_reason,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkScenarioFamily,
    BenchmarkScenarioKind,
    BenchmarkTiming,
    SpecializationKey,
)

RustPolicyMappingRenderer = Callable[[RustPolicySelection], str]
_Value = TypeVar("_Value")


@dataclass(frozen=True, slots=True)
class RustPolicyCandidateFact:
    """One benchmark candidate identity bound to its lowered-body hash."""

    candidate_id: str
    body_hash: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.body_hash:
            raise ValueError("Rust policy candidates require an ID and body hash")


@dataclass(frozen=True, slots=True)
class RustPolicyScenarioFact:
    """The ordered scenario and timing facts consumed by policy validation."""

    scenario_id: str
    family: BenchmarkScenarioFamily
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("Rust policy scenarios require an ID")


@dataclass(frozen=True, slots=True)
class RustPolicyMappingChoice:
    """Compiler-rendered Rust mapping for one supported candidate."""

    candidate_id: str
    source: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.source.strip():
            raise ValueError("Rust policy mapping choices require an ID and source")


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionDecision:
    """One ordered policy decision with benchmark and backend-owned facts joined."""

    key: SpecializationKey
    stable_id: str
    status: RustPolicySelectionStatus
    reason: str
    candidates: tuple[RustPolicyCandidateFact, ...]
    scenarios: tuple[RustPolicyScenarioFact, ...]
    specialization_required_features: tuple[str, ...]
    mapping_choices: tuple[RustPolicyMappingChoice, ...] = ()

    def __post_init__(self) -> None:
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        mapping_ids = tuple(mapping.candidate_id for mapping in self.mapping_choices)
        if not self.stable_id:
            raise ValueError("Rust policy decisions require a stable ID")
        if not candidate_ids or candidate_ids[0] != "default":
            raise ValueError(
                "Rust policy decisions must begin with the authored default"
            )
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Rust policy decision candidate IDs must be unique")
        if not self.scenarios:
            raise ValueError("Rust policy decisions require benchmark scenarios")
        if len(set(self.specialization_required_features)) != len(
            self.specialization_required_features
        ):
            raise ValueError("Rust policy decision features must be unique")
        if self.status == "supported":
            if self.reason:
                raise ValueError("supported Rust policy decisions cannot have a reason")
            if mapping_ids != candidate_ids:
                raise ValueError(
                    "supported Rust policy decisions require one mapping per candidate"
                )
        elif self.status == "report_only":
            if not self.reason:
                raise ValueError("report-only Rust policy decisions require a reason")
            if self.mapping_choices:
                raise ValueError(
                    "report-only Rust policy decisions cannot have mappings"
                )


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionProfile:
    """Complete build-time policy inputs for one generated Rust profile."""

    backend_id: str
    profile_name: str
    profile_family: str
    manifest_hash: str
    required_features: tuple[str, ...]
    decisions: tuple[RustPolicyConsumptionDecision, ...]

    def __post_init__(self) -> None:
        if self.backend_id != "rust":
            raise ValueError(
                "Rust policy consumption requires a Rust benchmark profile"
            )
        if not self.profile_name or not self.profile_family or not self.manifest_hash:
            raise ValueError(
                "Rust policy consumption requires complete profile identity"
            )
        if len(set(self.required_features)) != len(self.required_features):
            raise ValueError("Rust policy profile features must be unique")
        keys = tuple(decision.key for decision in self.decisions)
        stable_ids = tuple(decision.stable_id for decision in self.decisions)
        if any(
            key.backend_id != self.backend_id or key.profile_name != self.profile_name
            for key in keys
        ):
            raise ValueError(
                "Rust policy decisions must match their consumption profile"
            )
        if len(set(keys)) != len(keys):
            raise ValueError("Rust policy decision keys must be unique")
        if len(set(stable_ids)) != len(stable_ids):
            raise ValueError("Rust policy decision stable IDs must be unique")


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionGap:
    """Why an eligible selection profile remains default-only."""

    profile_name: str
    reason: str

    def __post_init__(self) -> None:
        if not self.profile_name or not self.reason:
            raise ValueError("Rust policy consumption gaps require profile and reason")


@dataclass(frozen=True, slots=True)
class RustPolicyCoverageGap:
    """One policy-supported specialization without benchmark report evidence."""

    key: SpecializationKey
    candidate_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if (
            self.key.backend_id != "rust"
            or not self.candidate_ids
            or self.candidate_ids[0] != "default"
            or len(set(self.candidate_ids)) != len(self.candidate_ids)
            or not self.reason
        ):
            raise ValueError(
                "Rust policy coverage gaps require a Rust key, candidates, and reason"
            )


@dataclass(frozen=True, slots=True)
class RustPolicyCoveragePlan:
    """Exact report-to-policy evidence, including report-only-only profiles."""

    profiles: tuple[RustPolicyConsumptionProfile, ...]
    gaps: tuple[RustPolicyCoverageGap, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if len(set(names)) != len(names):
            raise ValueError("Rust policy coverage profile names must be unique")
        gap_keys = tuple(gap.key for gap in self.gaps)
        if len(set(gap_keys)) != len(gap_keys):
            raise ValueError("Rust policy coverage gap keys must be unique")

    def profile(self, profile_name: str) -> RustPolicyConsumptionProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile_name == profile_name
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionPlan:
    """Frozen semantic availability for Rust policy consumption."""

    profiles: tuple[RustPolicyConsumptionProfile, ...]
    gaps: tuple[RustPolicyConsumptionGap, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        gap_names = tuple(gap.profile_name for gap in self.gaps)
        if len(set(names)) != len(names) or len(set(gap_names)) != len(gap_names):
            raise ValueError("Rust policy consumption profile names must be unique")
        if set(names) & set(gap_names):
            raise ValueError("Rust policy profiles cannot be both consumable and gaps")

    def profile(self, profile_name: str) -> RustPolicyConsumptionProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile_name == profile_name
            ),
            None,
        )


EMPTY_RUST_POLICY_CONSUMPTION_PLAN = RustPolicyConsumptionPlan(profiles=())


def plan_rust_policy_coverage(
    benchmarks: BenchmarkProjectPlan,
    selections: RustPolicySelectionPlan,
) -> RustPolicyCoveragePlan:
    """Join every Rust report to canonical policy eligibility exactly once."""

    # Keep the renderer import local: the typed plan owns mapping facts, while
    # the Rust backend remains their only spelling authority.
    from tslc.backend.rust import RustBackend

    selection_profile_names = {
        selection_profile.profile_name for selection_profile in selections.profiles
    }
    benchmark_profile_names = tuple(
        benchmark_profile.profile_name
        for benchmark_profile in benchmarks.profiles_for("rust")
    )
    if len(set(benchmark_profile_names)) != len(benchmark_profile_names):
        raise ValueError("Rust benchmark profile names must be unique")
    foreign_benchmark_profiles = tuple(
        name for name in benchmark_profile_names if name not in selection_profile_names
    )
    if foreign_benchmark_profiles:
        names = ", ".join(repr(name) for name in foreign_benchmark_profiles)
        raise ValueError(
            "Rust benchmark profiles have no policy-selection profile: " + names
        )
    foreign_selection_profiles = tuple(
        sorted(selection_profile_names - set(benchmark_profile_names))
    )
    if foreign_selection_profiles:
        names = ", ".join(repr(name) for name in foreign_selection_profiles)
        raise ValueError(
            "Rust policy-selection profiles have no benchmark profile: " + names
        )

    selection_by_name = {
        profile.profile_name: profile for profile in selections.profiles
    }
    profiles: list[RustPolicyConsumptionProfile] = []
    for benchmark_profile in benchmarks.profiles_for("rust"):
        selection_profile = selection_by_name[benchmark_profile.profile_name]
        backend = RustBackend(policy_selection=selection_profile)
        joined = join_rust_policy_consumption_profile(
            benchmark_profile,
            selection_profile,
            render_mapping=backend.render_policy_selection_impl,
            require_supported_reports=False,
        )
        profiles.append(joined)

    benchmark_keys = {
        candidate_set.key
        for profile in benchmarks.profiles_for("rust")
        for candidate_set in profile.candidate_sets
    }
    gaps = tuple(
        RustPolicyCoverageGap(
            key=selection.key,
            candidate_ids=selection.candidate_ids,
            reason="policy-supported Rust selection lacks benchmark report evidence",
        )
        for profile in selections.profiles
        for selection in profile.selections
        if selection.key not in benchmark_keys
    )
    return RustPolicyCoveragePlan(profiles=tuple(profiles), gaps=gaps)


def plan_rust_policy_consumption(
    benchmarks: BenchmarkProjectPlan,
    selections: RustPolicySelectionPlan,
) -> RustPolicyConsumptionPlan:
    """Restrict exact policy coverage to profiles with complete mappings."""

    coverage = plan_rust_policy_coverage(benchmarks, selections)
    gaps_by_profile = {
        gap.key.profile_name for gap in coverage.gaps
    }
    coverage_by_profile = {
        profile.profile_name: profile for profile in coverage.profiles
    }
    profiles: list[RustPolicyConsumptionProfile] = []
    gaps: list[RustPolicyConsumptionGap] = []
    for selection_profile in selections.profiles:
        if not selection_profile.selections:
            continue
        if selection_profile.profile_name in gaps_by_profile:
            gaps.append(
                RustPolicyConsumptionGap(
                    profile_name=selection_profile.profile_name,
                    reason=(
                        "policy-supported Rust selections lack benchmark candidate evidence"
                    ),
                )
            )
            continue
        profiles.append(coverage_by_profile[selection_profile.profile_name])
    return RustPolicyConsumptionPlan(profiles=tuple(profiles), gaps=tuple(gaps))


def join_rust_policy_consumption_profile(
    benchmark_profile: BenchmarkProfilePlan,
    selection_profile: RustPolicySelectionProfile,
    *,
    render_mapping: RustPolicyMappingRenderer,
    require_supported_reports: bool = True,
) -> RustPolicyConsumptionProfile:
    """Join exact benchmark inventory to compiler-owned Rust mapping choices."""

    if benchmark_profile.backend_id != "rust":
        raise ValueError("Rust policy consumption requires a Rust benchmark profile")
    if benchmark_profile.profile_name != selection_profile.profile_name:
        raise ValueError(
            "Rust benchmark and policy-selection profiles do not match"
        )

    candidate_sets = _unique_by_key(
        tuple(
            (candidate_set.key, candidate_set)
            for candidate_set in benchmark_profile.candidate_sets
        ),
        "benchmark candidate-set",
    )
    coverage = _unique_by_key(
        tuple((entry.key, entry) for entry in selection_profile.coverage),
        "policy coverage",
    )
    selections = _unique_by_key(
        tuple((selection.key, selection) for selection in selection_profile.selections),
        "policy selection",
    )
    resolved_coverage: dict[SpecializationKey, RustPolicySelectionCoverageEntry] = {}
    for key, candidate_set in candidate_sets.items():
        entry = _coverage_for_candidate_set(candidate_set, coverage)
        if entry is not None:
            resolved_coverage[key] = entry
    missing_coverage = candidate_sets.keys() - resolved_coverage.keys()
    if missing_coverage:
        raise ValueError(
            "Rust benchmark candidate sets are missing policy coverage entries"
        )
    missing_benchmarks = selections.keys() - candidate_sets.keys()
    if require_supported_reports and missing_benchmarks:
        raise ValueError(
            "Rust policy selections are missing benchmark candidate evidence"
        )

    decisions: list[RustPolicyConsumptionDecision] = []
    for candidate_set in benchmark_profile.candidate_sets:
        entry = resolved_coverage[candidate_set.key]
        candidate_ids = tuple(
            candidate.variant_id for candidate in candidate_set.candidates
        )
        if candidate_ids != entry.candidate_ids:
            raise ValueError(
                "Rust benchmark and policy candidate inventories do not match for "
                f"{candidate_set.stable_id!r}"
            )

        selection = selections.get(candidate_set.key)
        mapping_choices: tuple[RustPolicyMappingChoice, ...] = ()
        if entry.status == "supported":
            if selection is None:
                raise ValueError(
                    "supported Rust policy coverage has no compiler selection"
                )
            if (
                selection.candidate_ids != candidate_ids
                or selection.specialization != candidate_set.specialization
            ):
                raise ValueError(
                    "Rust benchmark and compiler selection facts do not match for "
                    f"{candidate_set.stable_id!r}"
                )
            mapping_choices = tuple(
                RustPolicyMappingChoice(
                    candidate_id=candidate_id,
                    source=render_mapping(
                        replace(selection, selected_candidate=candidate_id)
                    ),
                )
                for candidate_id in candidate_ids
            )
        elif selection is not None:
            raise ValueError(
                "report-only Rust policy coverage has a compiler selection"
            )

        decisions.append(
            RustPolicyConsumptionDecision(
                key=candidate_set.key,
                stable_id=candidate_set.stable_id,
                status=entry.status,
                reason=entry.reason,
                candidates=tuple(
                    RustPolicyCandidateFact(
                        candidate_id=candidate.variant_id,
                        body_hash=candidate.body_hash,
                    )
                    for candidate in candidate_set.candidates
                ),
                scenarios=tuple(
                    RustPolicyScenarioFact(
                        scenario_id=scenario.scenario_id,
                        family=scenario.family,
                        kind=scenario.kind,
                        timing=scenario.timing,
                    )
                    for scenario in candidate_set.scenarios
                ),
                specialization_required_features=tuple(
                    sorted(candidate_set.specialization.required_features)
                ),
                mapping_choices=mapping_choices,
            )
        )

    return RustPolicyConsumptionProfile(
        backend_id=benchmark_profile.backend_id,
        profile_name=benchmark_profile.profile_name,
        profile_family=benchmark_profile.profile_family,
        manifest_hash=benchmark_profile.manifest_hash,
        required_features=benchmark_profile.backend_feature_spellings,
        decisions=tuple(decisions),
    )


def _coverage_for_candidate_set(
    candidate_set: BenchmarkCandidateSet,
    coverage: dict[SpecializationKey, RustPolicySelectionCoverageEntry],
) -> RustPolicySelectionCoverageEntry | None:
    """Resolve exact coverage, binding only report-only immediate slots."""

    exact = coverage.get(candidate_set.key)
    if exact is not None:
        return exact
    if (
        candidate_set.key.immediate is None
        or candidate_set.specialization.immediate is None
    ):
        return None
    unbound = coverage.get(replace(candidate_set.key, immediate=None))
    if unbound is None or unbound.status != "report_only":
        return None
    reason = rust_policy_selection_shape_reason(
        candidate_set.key,
        candidate_set.specialization,
    )
    if reason != unbound.reason:
        return None
    return replace(unbound, key=candidate_set.key)


def _unique_by_key(
    pairs: tuple[tuple[SpecializationKey, _Value], ...],
    label: str,
) -> dict[SpecializationKey, _Value]:
    by_key = dict(pairs)
    if len(by_key) != len(pairs):
        raise ValueError(f"Rust {label} keys must be unique")
    return by_key


__all__ = (
    "EMPTY_RUST_POLICY_CONSUMPTION_PLAN",
    "RustPolicyCandidateFact",
    "RustPolicyConsumptionDecision",
    "RustPolicyConsumptionGap",
    "RustPolicyConsumptionPlan",
    "RustPolicyConsumptionProfile",
    "RustPolicyCoverageGap",
    "RustPolicyCoveragePlan",
    "RustPolicyMappingChoice",
    "RustPolicyMappingRenderer",
    "RustPolicyScenarioFact",
    "join_rust_policy_consumption_profile",
    "plan_rust_policy_coverage",
    "plan_rust_policy_consumption",
)
