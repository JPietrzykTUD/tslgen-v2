"""Frozen values shared by benchmark planning, rendering, and policy identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization

BenchmarkCoverageStatus = Literal["emitted", "unsupported", "missing_correctness"]
BenchmarkScenarioKind = Literal["throughput", "latency"]
BenchmarkOperandGenerator = Literal["bounded_random"]


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
class BenchmarkVectorCorrectnessCase:
    """Authored operands and expectation, tiled for one fixed-width vector."""

    case_name: str
    vector_inputs: tuple[tuple[str, ...], ...]
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkMaskCorrectnessCase:
    """Authored compact-mask conversion and its representation-neutral expectation."""

    case_name: str
    mask_inputs: tuple[str, ...]
    expected_mask: str
    to_integral_name: str


BenchmarkCorrectnessCase = (
    BenchmarkVectorCorrectnessCase | BenchmarkMaskCorrectnessCase
)


@dataclass(frozen=True, slots=True)
class BenchmarkTiming:
    """Measurement protocol shared by fully resolved workload scenarios."""

    seed: int
    batch_size: int = 256
    rounds: int = 9
    minimum_sample_ns: int = 20_000_000

    def __post_init__(self) -> None:
        if not 0 <= self.seed <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("benchmark seed must fit an unsigned 64-bit value")
        if self.batch_size <= 0 or self.batch_size & (self.batch_size - 1):
            raise ValueError("benchmark batch_size must be a positive power of two")
        if self.rounds < 3:
            raise ValueError("benchmark scenarios require at least three rounds")
        if self.minimum_sample_ns <= 0:
            raise ValueError("benchmark minimum_sample_ns must be positive")

    def canonical_fields(self) -> tuple[int, int, int, int]:
        return (self.seed, self.batch_size, self.rounds, self.minimum_sample_ns)


@dataclass(frozen=True, slots=True)
class BenchmarkRegisterScenario:
    """One exact pure-register workload; no call wiring is left to rendering."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming
    operand_generators: tuple[BenchmarkOperandGenerator, ...]
    dependency_parameter: int | None = None

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.operand_generators:
            raise ValueError("register benchmark scenarios require an id and operands")
        if self.kind == "latency" and self.dependency_parameter is None:
            raise ValueError("latency scenarios require a dependency parameter")
        if self.kind == "throughput" and self.dependency_parameter is not None:
            raise ValueError("throughput scenarios cannot carry a dependency parameter")
        if self.dependency_parameter is not None and not (
            0 <= self.dependency_parameter < len(self.operand_generators)
        ):
            raise ValueError("benchmark dependency parameter is out of range")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "register",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.operand_generators,
            self.dependency_parameter,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkMaskDensityScenario:
    """Throughput for an integral mask input with an exact active-lane count."""

    scenario_id: str
    timing: BenchmarkTiming
    parameter_index: int
    active_lanes: int
    kind: Literal["throughput"] = "throughput"

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("mask-density benchmark scenarios require an id")
        if self.parameter_index < 0 or self.active_lanes <= 0:
            raise ValueError("mask-density scenario facts must be positive")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "mask_density",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.parameter_index,
            self.active_lanes,
        )


BenchmarkScenario = BenchmarkRegisterScenario | BenchmarkMaskDensityScenario


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
        if not self.correctness_cases or not self.scenarios:
            raise ValueError("benchmark candidate sets require correctness and scenarios")
        ids = tuple(candidate.variant_id for candidate in self.candidates)
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate benchmark candidate IDs: {ids!r}")
        if isinstance(self.scenarios[0], BenchmarkRegisterScenario):
            register_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkRegisterScenario)
            )
            if len(register_scenarios) != len(self.scenarios) or not all(
                isinstance(case, BenchmarkVectorCorrectnessCase)
                for case in self.correctness_cases
            ):
                raise ValueError("register candidate sets require register-only facts")
            if any(
                len(scenario.operand_generators) != len(self.key.param_kinds)
                for scenario in register_scenarios
            ):
                raise ValueError("register scenario operands must match the specialization")
            return
        mask_scenarios = tuple(
            scenario
            for scenario in self.scenarios
            if isinstance(scenario, BenchmarkMaskDensityScenario)
        )
        if len(mask_scenarios) != len(self.scenarios) or not all(
            isinstance(case, BenchmarkMaskCorrectnessCase)
            for case in self.correctness_cases
        ):
            raise ValueError("mask-density candidate sets require mask-only facts")
        lanes = self.key.lanes
        if lanes is None or any(
            scenario.parameter_index >= len(self.key.param_kinds)
            or self.key.param_kinds[scenario.parameter_index] != "im"
            or scenario.active_lanes > lanes
            for scenario in mask_scenarios
        ):
            raise ValueError("mask-density scenario does not match the specialization")


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
    "BenchmarkMaskCorrectnessCase",
    "BenchmarkMaskDensityScenario",
    "BenchmarkOperandGenerator",
    "BenchmarkCoverageEntry",
    "BenchmarkCoverageStatus",
    "BenchmarkProfilePlan",
    "BenchmarkProjectPlan",
    "BenchmarkRegisterScenario",
    "BenchmarkScenario",
    "BenchmarkScenarioKind",
    "BenchmarkTiming",
    "BenchmarkVectorCorrectnessCase",
    "EMPTY_BENCHMARK_PROJECT_PLAN",
    "SpecializationKey",
)
