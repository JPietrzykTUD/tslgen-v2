"""Frozen values shared by benchmark planning, rendering, and policy identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization

BenchmarkCoverageStatus = Literal["emitted", "unsupported", "missing_correctness"]
BenchmarkScenarioKind = Literal["throughput", "latency"]
BenchmarkScenarioFamily = Literal[
    "register",
    "vector_scalar",
    "immediate",
    "indexed_load",
    "mask_density",
    "mask_result",
    "reduction",
]
BenchmarkOperandGenerator = Literal[
    "bounded_random",
    "bounded_nonzero",
    "bounded_shift_count",
]


@dataclass(frozen=True, slots=True)
class SpecializationKey:
    """Backend-local identity of one policy-selectable specialization."""

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

    family: ClassVar[Literal["register"]] = "register"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.vector_inputs
            or not self.expected
            or not self.from_array_name
            or not self.to_array_name
        ):
            raise ValueError("vector correctness cases require complete facts")
        if any(len(values) != len(self.expected) for values in self.vector_inputs):
            raise ValueError("vector correctness operands must match the result lanes")

    def validate_key(self, key: SpecializationKey) -> None:
        lanes = key.lanes
        if (
            key.result_kind != "v"
            or not key.param_kinds
            or not all(kind == "v" for kind in key.param_kinds)
            or len(self.vector_inputs) != len(key.param_kinds)
            or lanes is None
            or len(self.expected) != lanes
        ):
            raise ValueError("register correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "vector",
            self.case_name,
            self.vector_inputs,
            self.expected,
            self.from_array_name,
            self.to_array_name,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkVectorScalarCorrectnessCase:
    """Authored vector/scalar operands and one fixed-width vector expectation."""

    case_name: str
    vector_input: tuple[str, ...]
    scalar_input: str
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str

    family: ClassVar[Literal["vector_scalar"]] = "vector_scalar"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.vector_input
            or not self.scalar_input
            or not self.expected
            or not self.from_array_name
            or not self.to_array_name
        ):
            raise ValueError("vector-scalar correctness cases require complete facts")
        if len(self.vector_input) != len(self.expected):
            raise ValueError("vector-scalar correctness lanes must match")

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or key.param_kinds != ("v", "s")
            or key.lanes is None
            or len(self.expected) != key.lanes
        ):
            raise ValueError("vector-scalar correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "vector_scalar",
            self.case_name,
            self.vector_input,
            self.scalar_input,
            self.expected,
            self.from_array_name,
            self.to_array_name,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkImmediateCorrectnessCase:
    """Authored vector expectation for one concrete compile-time immediate."""

    case_name: str
    vector_input: tuple[str, ...]
    expected: tuple[str, ...]
    from_array_name: str
    to_array_name: str

    family: ClassVar[Literal["immediate"]] = "immediate"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.vector_input
            or not self.expected
            or not self.from_array_name
            or not self.to_array_name
        ):
            raise ValueError("immediate correctness cases require complete facts")
        if len(self.vector_input) != len(self.expected):
            raise ValueError("immediate correctness lanes must match")

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or key.param_kinds != ("v", "sImm")
            or key.immediate is None
            or key.lanes is None
            or len(self.expected) != key.lanes
        ):
            raise ValueError("immediate correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "immediate",
            self.case_name,
            self.vector_input,
            self.expected,
            self.from_array_name,
            self.to_array_name,
        )


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

    family: ClassVar[Literal["indexed_load"]] = "indexed_load"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.memory_values
            or not self.index_values
            or not self.expected
            or not self.index_type_tag
            or not self.index_base_spelling
            or not self.from_array_name
            or not self.to_array_name
        ):
            raise ValueError("indexed-load correctness cases require complete facts")

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or key.param_kinds != ("cptr", "vidx", "sImm")
            or key.immediate is None
            or len(key.simd_type_base_bindings) != 1
            or key.simd_type_base_bindings[0][1] != self.index_type_tag
            or key.lanes is None
            or len(self.expected) != key.lanes
        ):
            raise ValueError("indexed-load correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "indexed_load",
            self.case_name,
            self.memory_values,
            self.index_values,
            self.expected,
            self.index_type_tag,
            self.index_base_spelling,
            self.from_array_name,
            self.to_array_name,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkMaskCorrectnessCase:
    """Authored compact-mask conversion and its representation-neutral expectation."""

    case_name: str
    mask_inputs: tuple[str, ...]
    expected_mask: str
    to_integral_name: str

    family: ClassVar[Literal["mask_density"]] = "mask_density"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.mask_inputs
            or not self.expected_mask
            or not self.to_integral_name
        ):
            raise ValueError("mask correctness cases require complete facts")

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "m"
            or key.param_kinds != ("im",)
            or key.lanes is None
            or len(self.mask_inputs) != len(key.param_kinds)
        ):
            raise ValueError("mask correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "mask",
            self.case_name,
            self.mask_inputs,
            self.expected_mask,
            self.to_integral_name,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkVectorMaskCorrectnessCase:
    """Authored vector operands and expected compact mask for a predicate result."""

    case_name: str
    vector_inputs: tuple[tuple[str, ...], ...]
    expected_mask: str
    from_array_name: str
    to_integral_name: str

    family: ClassVar[Literal["mask_result"]] = "mask_result"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.vector_inputs
            or not self.expected_mask
            or not self.from_array_name
            or not self.to_integral_name
        ):
            raise ValueError("vector-mask correctness cases require complete facts")
        lane_counts = {len(values) for values in self.vector_inputs}
        if 0 in lane_counts or len(lane_counts) != 1:
            raise ValueError("vector-mask correctness operands must share lane counts")

    def validate_key(self, key: SpecializationKey) -> None:
        lanes = key.lanes
        if (
            key.result_kind != "m"
            or not key.param_kinds
            or not all(kind == "v" for kind in key.param_kinds)
            or len(self.vector_inputs) != len(key.param_kinds)
            or lanes is None
            or len(self.vector_inputs[0]) != lanes
        ):
            raise ValueError("vector-mask correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "vector_mask",
            self.case_name,
            self.vector_inputs,
            self.expected_mask,
            self.from_array_name,
            self.to_integral_name,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkReductionCorrectnessCase:
    """Authored vector input and scalar expectation for one fixed-width reduction."""

    case_name: str
    vector_input: tuple[str, ...]
    expected: str
    from_array_name: str

    family: ClassVar[Literal["reduction"]] = "reduction"

    def __post_init__(self) -> None:
        if (
            not self.case_name
            or not self.vector_input
            or not self.expected
            or not self.from_array_name
        ):
            raise ValueError("reduction correctness cases require complete facts")

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "s"
            or key.param_kinds != ("v",)
            or key.lanes is None
            or len(self.vector_input) != key.lanes
        ):
            raise ValueError("reduction correctness does not match the specialization")

    def canonical_fields(self) -> tuple[object, ...]:
        return (
            "reduction",
            self.case_name,
            self.vector_input,
            self.expected,
            self.from_array_name,
        )


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

    family: ClassVar[Literal["register"]] = "register"
    correctness_type: ClassVar[type[BenchmarkVectorCorrectnessCase]] = (
        BenchmarkVectorCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or not key.param_kinds
            or not all(kind == "v" for kind in key.param_kinds)
            or len(self.operand_generators) != len(key.param_kinds)
        ):
            raise ValueError("register scenario operands must match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "operand_generators": self.operand_generators,
            "dependency_parameter": self.dependency_parameter,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkVectorScalarScenario:
    """A vector result from one vector and one independent scalar operand."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming
    vector_generator: BenchmarkOperandGenerator
    scalar_generator: BenchmarkOperandGenerator
    dependency_parameter: Literal[0] | None = None

    family: ClassVar[Literal["vector_scalar"]] = "vector_scalar"
    correctness_type: ClassVar[type[BenchmarkVectorScalarCorrectnessCase]] = (
        BenchmarkVectorScalarCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if key.result_kind != "v" or key.param_kinds != ("v", "s"):
            raise ValueError("vector-scalar scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "vector_generator": self.vector_generator,
            "scalar_generator": self.scalar_generator,
            "dependency_parameter": self.dependency_parameter,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkImmediateScenario:
    """One-vector workload for one concrete compile-time immediate."""

    scenario_id: str
    kind: BenchmarkScenarioKind
    timing: BenchmarkTiming
    operand_generator: BenchmarkOperandGenerator
    dependency_parameter: Literal[0] | None = None

    family: ClassVar[Literal["immediate"]] = "immediate"
    correctness_type: ClassVar[type[BenchmarkImmediateCorrectnessCase]] = (
        BenchmarkImmediateCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or key.param_kinds != ("v", "sImm")
            or key.immediate is None
        ):
            raise ValueError("immediate scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "operand_generator": self.operand_generator,
            "dependency_parameter": self.dependency_parameter,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkIndexedLoadScenario:
    """Hot-L1 independent throughput for bounded indexed memory loads."""

    scenario_id: str
    timing: BenchmarkTiming
    memory_bytes: int
    index_lanes: int
    kind: Literal["throughput"] = "throughput"

    family: ClassVar[Literal["indexed_load"]] = "indexed_load"
    correctness_type: ClassVar[type[BenchmarkIndexedLoadCorrectnessCase]] = (
        BenchmarkIndexedLoadCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "v"
            or key.param_kinds != ("cptr", "vidx", "sImm")
            or key.immediate is None
            or len(key.simd_type_base_bindings) != 1
        ):
            raise ValueError("indexed-load scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "memory_bytes": self.memory_bytes,
            "index_lanes": self.index_lanes,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkMaskDensityScenario:
    """Throughput for an integral mask input with an exact active-lane count."""

    scenario_id: str
    timing: BenchmarkTiming
    parameter_index: int
    active_lanes: int
    kind: Literal["throughput"] = "throughput"

    family: ClassVar[Literal["mask_density"]] = "mask_density"
    correctness_type: ClassVar[type[BenchmarkMaskCorrectnessCase]] = (
        BenchmarkMaskCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        lanes = key.lanes
        if (
            key.result_kind != "m"
            or key.param_kinds != ("im",)
            or lanes is None
            or self.parameter_index >= len(key.param_kinds)
            or key.param_kinds[self.parameter_index] != "im"
            or self.active_lanes > lanes
        ):
            raise ValueError("mask-density scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "parameter_index": self.parameter_index,
            "active_lanes": self.active_lanes,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkMaskResultScenario:
    """Independent throughput for vector operands producing a predicate mask."""

    scenario_id: str
    timing: BenchmarkTiming
    operand_generators: tuple[BenchmarkOperandGenerator, ...]
    kind: Literal["throughput"] = "throughput"

    family: ClassVar[Literal["mask_result"]] = "mask_result"
    correctness_type: ClassVar[type[BenchmarkVectorMaskCorrectnessCase]] = (
        BenchmarkVectorMaskCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if (
            key.result_kind != "m"
            or not key.param_kinds
            or not all(kind == "v" for kind in key.param_kinds)
            or len(self.operand_generators) != len(key.param_kinds)
        ):
            raise ValueError("mask-result scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "operand_generators": self.operand_generators,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReductionScenario:
    """Independent throughput for a single-vector, scalar-result reduction."""

    scenario_id: str
    timing: BenchmarkTiming
    operand_generator: BenchmarkOperandGenerator
    kind: Literal["throughput"] = "throughput"

    family: ClassVar[Literal["reduction"]] = "reduction"
    correctness_type: ClassVar[type[BenchmarkReductionCorrectnessCase]] = (
        BenchmarkReductionCorrectnessCase
    )

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

    def validate_key(self, key: SpecializationKey) -> None:
        if key.result_kind != "s" or key.param_kinds != ("v",):
            raise ValueError("reduction scenario does not match the specialization")

    def manifest_fields(self) -> dict[str, object]:
        return {
            "family": self.family,
            "operand_generator": self.operand_generator,
        }


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
        scenario_type = type(self.scenarios[0])
        if any(type(scenario) is not scenario_type for scenario in self.scenarios):
            raise ValueError("benchmark candidate sets require one scenario family")
        correctness_type = self.scenarios[0].correctness_type
        if any(
            not isinstance(case, correctness_type) for case in self.correctness_cases
        ):
            raise ValueError(
                f"{self.scenarios[0].family} candidate sets require matching correctness facts"
            )
        for case in self.correctness_cases:
            case.validate_key(self.key)
        for scenario in self.scenarios:
            scenario.validate_key(self.key)


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
    profile_family: str
    backend_feature_spellings: tuple[str, ...]


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
    "BenchmarkScenarioFamily",
    "BenchmarkScenarioKind",
    "BenchmarkTiming",
    "BenchmarkVectorCorrectnessCase",
    "BenchmarkVectorMaskCorrectnessCase",
    "BenchmarkVectorScalarCorrectnessCase",
    "BenchmarkVectorScalarScenario",
    "EMPTY_BENCHMARK_PROJECT_PLAN",
    "SpecializationKey",
)
