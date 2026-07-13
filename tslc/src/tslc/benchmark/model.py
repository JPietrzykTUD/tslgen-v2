"""Frozen values shared by benchmark planning, rendering, and policy identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization

BenchmarkCoverageStatus = Literal["emitted", "unsupported", "missing_correctness"]
BenchmarkScenarioKind = Literal["throughput", "latency"]


@dataclass(frozen=True, slots=True)
class SpecializationKey:
    """Backend-neutral identity of one policy-selectable specialization."""

    backend_id: str
    profile_name: str
    primitive_name: str
    source_primitive_name: str
    extension_name: str
    type_tag: str
    result_kind: str
    param_kinds: tuple[str, ...]
    target_type_tag: str | None = None
    target_extension_name: str | None = None
    axis: tuple[tuple[str, str], ...] = ()
    immediate: str | None = None
    generic_values: tuple[tuple[str, str], ...] = ()
    simd_type_base_bindings: tuple[tuple[str, str], ...] = ()
    lanes: int | None = None
    header_group: str | None = None

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            self.backend_id,
            self.profile_name,
            self.primitive_name,
            self.source_primitive_name,
            self.extension_name,
            self.type_tag,
            self.result_kind,
            self.param_kinds,
            self.target_type_tag,
            self.target_extension_name,
            self.axis,
            self.immediate,
            self.generic_values,
            self.simd_type_base_bindings,
            self.lanes,
            self.header_group,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkCandidate:
    """The authored default or one named implementation variant."""

    variant_id: str
    body_hash: str

    @property
    def is_default(self) -> bool:
        return self.variant_id == "default"


@dataclass(frozen=True, slots=True)
class BenchmarkCorrectnessCase:
    """Authored operands and expectation, tiled for one fixed-width vector."""

    case_name: str
    vector_inputs: tuple[tuple[str, ...], ...]
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """A deterministic timed workload, separate from correctness examples."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    seed: int
    batch_size: int = 256
    rounds: int = 9
    minimum_sample_ns: int = 20_000_000

    def __post_init__(self) -> None:
        if self.batch_size <= 0 or self.batch_size & (self.batch_size - 1):
            raise ValueError("benchmark batch_size must be a positive power of two")
        if self.rounds < 3:
            raise ValueError("benchmark scenarios require at least three rounds")
        if self.minimum_sample_ns <= 0:
            raise ValueError("benchmark minimum_sample_ns must be positive")


@dataclass(frozen=True, slots=True)
class BenchmarkCandidateSet:
    """One specialization, its callable bodies, and its benchmark protocol."""

    key: SpecializationKey
    specialization: LoweredSpecialization
    candidates: tuple[BenchmarkCandidate, ...]
    correctness_cases: tuple[BenchmarkCorrectnessCase, ...]
    scenarios: tuple[BenchmarkScenario, ...]
    stable_id: str

    def __post_init__(self) -> None:
        if not self.candidates or not self.candidates[0].is_default:
            raise ValueError("benchmark candidate sets must begin with default")
        ids = tuple(candidate.variant_id for candidate in self.candidates)
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate benchmark candidate IDs: {ids!r}")


@dataclass(frozen=True, slots=True)
class BenchmarkCoverageEntry:
    backend_id: str
    profile_name: str
    primitive_name: str
    extension_name: str
    type_tag: str
    status: BenchmarkCoverageStatus
    reason: str = ""


@dataclass(frozen=True, slots=True)
class BenchmarkProfilePlan:
    backend_id: str
    profile_name: str
    candidate_sets: tuple[BenchmarkCandidateSet, ...]
    manifest_hash: str


@dataclass(frozen=True, slots=True)
class BenchmarkProjectPlan:
    profiles: tuple[BenchmarkProfilePlan, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    coverage: tuple[BenchmarkCoverageEntry, ...] = ()

    def profiles_for(self, backend_id: str) -> tuple[BenchmarkProfilePlan, ...]:
        return tuple(profile for profile in self.profiles if profile.backend_id == backend_id)

    def profile(self, backend_id: str, profile_name: str) -> BenchmarkProfilePlan | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.backend_id == backend_id and profile.profile_name == profile_name
            ),
            None,
        )


EMPTY_BENCHMARK_PROJECT_PLAN = BenchmarkProjectPlan(profiles=())


__all__ = (
    "BenchmarkCandidate",
    "BenchmarkCandidateSet",
    "BenchmarkCorrectnessCase",
    "BenchmarkCoverageEntry",
    "BenchmarkCoverageStatus",
    "BenchmarkProfilePlan",
    "BenchmarkProjectPlan",
    "BenchmarkScenario",
    "BenchmarkScenarioKind",
    "EMPTY_BENCHMARK_PROJECT_PLAN",
    "SpecializationKey",
)
