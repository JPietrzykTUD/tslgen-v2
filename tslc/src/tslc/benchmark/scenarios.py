"""Construct renderer-ready timing scenarios from typed primitive facts."""

from __future__ import annotations

from tslc.benchmark.model import (
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadScenario,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkOperandGenerator,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkTiming,
    BenchmarkVectorScalarScenario,
)
from tslc.catalog.model import Primitive
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.lane_math import SEED_MIX_64


def register_scenarios(
    primitive: Primitive,
    spec: LoweredSpecialization,
    seed: int,
) -> tuple[BenchmarkRegisterScenario, ...]:
    generators = tuple(
        _operand_generator(primitive, parameter) for parameter in spec.param_names
    )
    scenarios = [
        BenchmarkRegisterScenario(
            scenario_id="throughput_independent",
            kind="throughput",
            timing=BenchmarkTiming(seed),
            operand_generators=generators,
        )
    ]
    dependency: int | None = None
    if primitive.benchmark.latency_chain is not None:
        dependency = primitive.parameters.index(primitive.benchmark.latency_chain)
    elif len(spec.param_kinds) == 1:
        dependency = 0
    if dependency is not None:
        scenarios.append(
            BenchmarkRegisterScenario(
                scenario_id="latency_dependency_chain",
                kind="latency",
                timing=BenchmarkTiming(seed ^ SEED_MIX_64),
                operand_generators=generators,
                dependency_parameter=dependency,
            )
        )
    return tuple(scenarios)


def vector_scalar_scenarios(
    primitive: Primitive,
    spec: LoweredSpecialization,
    seed: int,
) -> tuple[BenchmarkVectorScalarScenario, ...]:
    vector_generator = _operand_generator(primitive, spec.param_names[0])
    scalar_generator = _operand_generator(primitive, spec.param_names[1])
    scenarios = [
        BenchmarkVectorScalarScenario(
            scenario_id="throughput_independent",
            kind="throughput",
            timing=BenchmarkTiming(seed),
            vector_generator=vector_generator,
            scalar_generator=scalar_generator,
        )
    ]
    if primitive.benchmark.latency_chain == primitive.parameters[0]:
        scenarios.append(
            BenchmarkVectorScalarScenario(
                scenario_id="latency_dependency_chain",
                kind="latency",
                timing=BenchmarkTiming(seed ^ SEED_MIX_64),
                vector_generator=vector_generator,
                scalar_generator=scalar_generator,
                dependency_parameter=0,
            )
        )
    return tuple(scenarios)


def immediate_scenarios(
    primitive: Primitive,
    spec: LoweredSpecialization,
    seed: int,
) -> tuple[BenchmarkImmediateScenario, ...]:
    generator = _operand_generator(primitive, spec.param_names[0])
    return (
        BenchmarkImmediateScenario(
            scenario_id="throughput_independent",
            kind="throughput",
            timing=BenchmarkTiming(seed),
            operand_generator=generator,
        ),
        BenchmarkImmediateScenario(
            scenario_id="latency_dependency_chain",
            kind="latency",
            timing=BenchmarkTiming(seed ^ SEED_MIX_64),
            operand_generator=generator,
            dependency_parameter=0,
        ),
    )


def indexed_load_scenarios(
    index_lanes: int,
    seed: int,
) -> tuple[BenchmarkIndexedLoadScenario, ...]:
    return (
        BenchmarkIndexedLoadScenario(
            scenario_id="throughput_hot_l1",
            timing=BenchmarkTiming(seed),
            memory_bytes=4096,
            index_lanes=index_lanes,
        ),
    )


def mask_density_scenarios(
    lanes: int,
    seed: int,
) -> tuple[BenchmarkMaskDensityScenario, ...]:
    requested = (
        ("mask_sparse", 1),
        ("mask_balanced", max(1, lanes // 2)),
        ("mask_dense", max(1, lanes - 1)),
    )
    scenarios: list[BenchmarkMaskDensityScenario] = []
    seen_active_lanes: set[int] = set()
    for index, (scenario_id, active_lanes) in enumerate(requested):
        if active_lanes in seen_active_lanes:
            continue
        seen_active_lanes.add(active_lanes)
        scenarios.append(
            BenchmarkMaskDensityScenario(
                scenario_id=scenario_id,
                timing=BenchmarkTiming(
                    (seed ^ ((index + 1) * SEED_MIX_64))
                    & 0xFFFFFFFFFFFFFFFF
                ),
                parameter_index=0,
                active_lanes=active_lanes,
            )
        )
    return tuple(scenarios)


def mask_result_scenarios(
    primitive: Primitive,
    spec: LoweredSpecialization,
    seed: int,
) -> tuple[BenchmarkMaskResultScenario, ...]:
    return (
        BenchmarkMaskResultScenario(
            scenario_id="throughput_independent",
            timing=BenchmarkTiming(seed),
            operand_generators=tuple(
                _operand_generator(primitive, parameter)
                for parameter in spec.param_names
            ),
        ),
    )


def reduction_scenarios(seed: int) -> tuple[BenchmarkReductionScenario, ...]:
    return (
        BenchmarkReductionScenario(
            scenario_id="throughput_independent",
            timing=BenchmarkTiming(seed),
            operand_generator="bounded_random",
        ),
    )


def _operand_generator(
    primitive: Primitive,
    parameter: str,
) -> BenchmarkOperandGenerator:
    for operand in primitive.benchmark.operand_domains:
        if operand.parameter != parameter:
            continue
        if operand.domain == "nonzero":
            return "bounded_nonzero"
        if operand.domain == "shift_count":
            return "bounded_shift_count"
    return "bounded_random"


__all__ = (
    "immediate_scenarios",
    "indexed_load_scenarios",
    "mask_density_scenarios",
    "mask_result_scenarios",
    "reduction_scenarios",
    "register_scenarios",
    "vector_scalar_scenarios",
)
