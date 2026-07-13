"""Frozen values shared by benchmark planning, rendering, and policy identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization

BenchmarkCoverageStatus = Literal["emitted", "unsupported", "missing_correctness"]
BenchmarkScenarioKind = Literal["throughput", "latency"]
BenchmarkOperandGenerator = Literal[
    "bounded_random",
    "bounded_nonzero",
    "bounded_shift_count",
]


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
    overload_parameter_positions: tuple[int, ...] = ()
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
            self.overload_parameter_positions,
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
class BenchmarkVectorScalarCorrectnessCase:
    """Authored vector/scalar operands and one fixed-width vector expectation."""

    case_name: str
    vector_input: tuple[str, ...]
    scalar_input: str
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkImmediateCorrectnessCase:
    """Authored vector expectation for one concrete compile-time immediate."""

    case_name: str
    vector_input: tuple[str, ...]
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkIndexedLoadCorrectnessCase:
    """Authored memory, index, and result facts for an indexed load."""

    case_name: str
    memory_values: tuple[str, ...]
    index_values: tuple[str, ...]
    expected: tuple[str, ...]
    index_type_tag: str
    index_base_spelling: str
    from_array_name: str
    to_array_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkMaskCorrectnessCase:
    """Authored compact-mask conversion and its representation-neutral expectation."""

    case_name: str
    mask_inputs: tuple[str, ...]
    expected_mask: str
    to_integral_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkVectorMaskCorrectnessCase:
    """Authored vector operands and expected compact mask for a predicate result."""

    case_name: str
    vector_inputs: tuple[tuple[str, ...], ...]
    expected_mask: str
    from_array_name: str
    to_integral_name: str


@dataclass(frozen=True, slots=True)
class BenchmarkReductionCorrectnessCase:
    """Authored vector input and scalar expectation for one fixed-width reduction."""

    case_name: str
    vector_input: tuple[str, ...]
    expected: str
    from_array_name: str


BenchmarkCorrectnessCase = (
    BenchmarkVectorCorrectnessCase
    | BenchmarkVectorScalarCorrectnessCase
    | BenchmarkImmediateCorrectnessCase
    | BenchmarkIndexedLoadCorrectnessCase
    | BenchmarkMaskCorrectnessCase
    | BenchmarkVectorMaskCorrectnessCase
    | BenchmarkReductionCorrectnessCase
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
class BenchmarkVectorScalarScenario:
    """A vector result from one vector and one independent scalar operand."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming
    vector_generator: BenchmarkOperandGenerator
    scalar_generator: BenchmarkOperandGenerator
    dependency_parameter: Literal[0] | None = None

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("vector-scalar benchmark scenarios require an id")
        if self.kind == "latency" and self.dependency_parameter != 0:
            raise ValueError("vector-scalar latency must chain the vector operand")
        if self.kind == "throughput" and self.dependency_parameter is not None:
            raise ValueError("vector-scalar throughput cannot carry a dependency")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "vector_scalar",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.vector_generator,
            self.scalar_generator,
            self.dependency_parameter,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkImmediateScenario:
    """One-vector workload for one concrete compile-time immediate."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming
    operand_generator: BenchmarkOperandGenerator
    dependency_parameter: Literal[0] | None = None

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("immediate benchmark scenarios require an id")
        if self.kind == "latency" and self.dependency_parameter != 0:
            raise ValueError("immediate latency must chain the vector operand")
        if self.kind == "throughput" and self.dependency_parameter is not None:
            raise ValueError("immediate throughput cannot carry a dependency")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "immediate",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.operand_generator,
            self.dependency_parameter,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkIndexedLoadScenario:
    """Hot-L1 independent throughput for bounded indexed memory loads."""

    scenario_id: str
    timing: BenchmarkTiming
    memory_bytes: int
    index_lanes: int
    kind: Literal["throughput"] = "throughput"

    def __post_init__(self) -> None:
        if not self.scenario_id or self.memory_bytes <= 0 or self.index_lanes <= 0:
            raise ValueError("indexed-load scenarios require positive workload facts")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "indexed_load",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.memory_bytes,
            self.index_lanes,
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


@dataclass(frozen=True, slots=True)
class BenchmarkMaskResultScenario:
    """Independent throughput for vector operands producing a predicate mask."""

    scenario_id: str
    timing: BenchmarkTiming
    operand_generators: tuple[BenchmarkOperandGenerator, ...]
    kind: Literal["throughput"] = "throughput"

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.operand_generators:
            raise ValueError("mask-result benchmark scenarios require an id and operands")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "mask_result",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.operand_generators,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkReductionScenario:
    """Independent throughput for a single-vector, scalar-result reduction."""

    scenario_id: str
    timing: BenchmarkTiming
    operand_generator: BenchmarkOperandGenerator
    kind: Literal["throughput"] = "throughput"

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("reduction benchmark scenarios require an id")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "reduction",
            self.scenario_id,
            self.kind,
            self.timing.canonical_fields(),
            self.operand_generator,
        )


BenchmarkScenario = (
    BenchmarkRegisterScenario
    | BenchmarkVectorScalarScenario
    | BenchmarkImmediateScenario
    | BenchmarkIndexedLoadScenario
    | BenchmarkMaskDensityScenario
    | BenchmarkMaskResultScenario
    | BenchmarkReductionScenario
)


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
        if isinstance(self.scenarios[0], BenchmarkVectorScalarScenario):
            vector_scalar_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkVectorScalarScenario)
            )
            if (
                len(vector_scalar_scenarios) != len(self.scenarios)
                or not all(
                    isinstance(case, BenchmarkVectorScalarCorrectnessCase)
                    for case in self.correctness_cases
                )
                or self.key.result_kind != "v"
                or self.key.param_kinds != ("v", "s")
            ):
                raise ValueError(
                    "vector-scalar candidate sets require vector/scalar facts"
                )
            return
        if isinstance(self.scenarios[0], BenchmarkImmediateScenario):
            immediate_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkImmediateScenario)
            )
            if (
                len(immediate_scenarios) != len(self.scenarios)
                or not all(
                    isinstance(case, BenchmarkImmediateCorrectnessCase)
                    for case in self.correctness_cases
                )
                or self.key.result_kind != "v"
                or self.key.param_kinds != ("v", "sImm")
                or self.key.immediate is None
            ):
                raise ValueError("immediate candidate sets require immediate-only facts")
            return
        if isinstance(self.scenarios[0], BenchmarkIndexedLoadScenario):
            indexed_load_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkIndexedLoadScenario)
            )
            if (
                len(indexed_load_scenarios) != len(self.scenarios)
                or not all(
                    isinstance(case, BenchmarkIndexedLoadCorrectnessCase)
                    for case in self.correctness_cases
                )
                or self.key.result_kind != "v"
                or self.key.param_kinds != ("cptr", "vidx", "sImm")
                or self.key.immediate is None
                or len(self.key.simd_type_base_bindings) != 1
            ):
                raise ValueError("indexed-load candidate sets require indexed-load facts")
            return
        if isinstance(self.scenarios[0], BenchmarkMaskResultScenario):
            mask_result_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkMaskResultScenario)
            )
            if (
                len(mask_result_scenarios) != len(self.scenarios)
                or not all(
                    isinstance(case, BenchmarkVectorMaskCorrectnessCase)
                    for case in self.correctness_cases
                )
                or self.key.result_kind != "m"
                or not self.key.param_kinds
                or not all(kind == "v" for kind in self.key.param_kinds)
                or any(
                    len(scenario.operand_generators) != len(self.key.param_kinds)
                    for scenario in mask_result_scenarios
                )
            ):
                raise ValueError("mask-result candidate sets require vector-to-mask facts")
            return
        if isinstance(self.scenarios[0], BenchmarkReductionScenario):
            reduction_scenarios = tuple(
                scenario
                for scenario in self.scenarios
                if isinstance(scenario, BenchmarkReductionScenario)
            )
            if (
                len(reduction_scenarios) != len(self.scenarios)
                or not all(
                    isinstance(case, BenchmarkReductionCorrectnessCase)
                    for case in self.correctness_cases
                )
                or self.key.result_kind != "s"
                or self.key.param_kinds != ("v",)
            ):
                raise ValueError("reduction candidate sets require reduction-only facts")
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
    source_primitive_name: str
    extension_name: str
    type_tag: str
    result_kind: str
    param_kinds: tuple[str, ...]
    mask_policy: str | None
    axis: tuple[tuple[str, str], ...]
    variant_names: tuple[str, ...]
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
    "BenchmarkImmediateCorrectnessCase",
    "BenchmarkImmediateScenario",
    "BenchmarkIndexedLoadCorrectnessCase",
    "BenchmarkIndexedLoadScenario",
    "BenchmarkMaskCorrectnessCase",
    "BenchmarkMaskDensityScenario",
    "BenchmarkMaskResultScenario",
    "BenchmarkOperandGenerator",
    "BenchmarkCoverageEntry",
    "BenchmarkCoverageStatus",
    "BenchmarkProfilePlan",
    "BenchmarkProjectPlan",
    "BenchmarkRegisterScenario",
    "BenchmarkReductionCorrectnessCase",
    "BenchmarkReductionScenario",
    "BenchmarkScenario",
    "BenchmarkScenarioKind",
    "BenchmarkTiming",
    "BenchmarkVectorCorrectnessCase",
    "BenchmarkVectorMaskCorrectnessCase",
    "BenchmarkVectorScalarCorrectnessCase",
    "BenchmarkVectorScalarScenario",
    "EMPTY_BENCHMARK_PROJECT_PLAN",
    "SpecializationKey",
)
