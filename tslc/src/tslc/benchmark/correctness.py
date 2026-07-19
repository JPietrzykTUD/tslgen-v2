"""Promote authored value-test facts into benchmark correctness cases."""

from __future__ import annotations

from tslc.benchmark.model import (
    BenchmarkImmediateCorrectnessCase,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkMaskCorrectnessCase,
    BenchmarkReductionCorrectnessCase,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
)
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.lane_math import tile
from tslc.value_tests.literals import token_truthy
from tslc.value_tests.model import ValueTestCasePlan


def vector_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    from_array_name: str,
    to_array_name: str,
) -> tuple[BenchmarkVectorCorrectnessCase, ...]:
    matching: list[BenchmarkVectorCorrectnessCase] = []
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
            BenchmarkVectorCorrectnessCase(
                case_name=case.case_name,
                vector_inputs=tuple(tile(values, lanes) for values in case.inputs.vectors),
                expected=tile(case.expectation.values, lanes),
                from_array_name=from_array_name,
                to_array_name=to_array_name,
            )
        )
    return tuple(matching)


def vector_scalar_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    from_array_name: str,
    to_array_name: str,
) -> tuple[BenchmarkVectorScalarCorrectnessCase, ...]:
    matching: list[BenchmarkVectorScalarCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "scalar_vector"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.invocation.param_kinds != ("v", "s")
            or len(case.inputs.vectors) != 1
            or len(case.inputs.vectors[0]) != case.lanes
            or len(case.inputs.scalars) != 1
            or len(case.expectation.values) != case.lanes
            or case.case_name in seen
        ):
            continue
        seen.add(case.case_name)
        matching.append(
            BenchmarkVectorScalarCorrectnessCase(
                case_name=case.case_name,
                vector_input=tile(case.inputs.vectors[0], lanes),
                scalar_input=case.inputs.scalars[0],
                expected=tile(case.expectation.values, lanes),
                from_array_name=from_array_name,
                to_array_name=to_array_name,
            )
        )
    return tuple(matching)


def immediate_values(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
) -> tuple[str, ...]:
    values = {
        case.invocation.immediate
        for case in cases
        if case.kind == "immediate"
        and case.call_name == spec.primitive_name
        and case.type_tag == spec.type_tag
        and case.invocation.param_kinds == ("v", "sImm")
        and case.invocation.immediate is not None
    }
    return tuple(sorted(values, key=immediate_sort_key))


def immediate_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value, 0))
    except ValueError:
        return (1, value)


def immediate_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    immediate_value: str,
    from_array_name: str,
    to_array_name: str,
) -> tuple[BenchmarkImmediateCorrectnessCase, ...]:
    matching: list[BenchmarkImmediateCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "immediate"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.invocation.param_kinds != ("v", "sImm")
            or case.invocation.immediate != immediate_value
            or len(case.inputs.vectors) != 1
            or len(case.inputs.vectors[0]) != case.lanes
            or len(case.expectation.values) != case.lanes
            or case.case_name in seen
        ):
            continue
        seen.add(case.case_name)
        matching.append(
            BenchmarkImmediateCorrectnessCase(
                case_name=case.case_name,
                vector_input=tile(case.inputs.vectors[0], lanes),
                expected=tile(case.expectation.values, lanes),
                from_array_name=from_array_name,
                to_array_name=to_array_name,
            )
        )
    return tuple(matching)


def indexed_load_bindings(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    type_parameter = spec.type_params[0].name
    bindings = {
        (
            case.invocation.immediate,
            ((type_parameter, case.index.type_tag),),
        )
        for case in cases
        if case.kind == "indexed_load"
        and case.call_name == spec.primitive_name
        and case.type_tag == spec.type_tag
        and case.invocation.param_kinds == ("cptr", "vidx", "sImm")
        and case.invocation.immediate is not None
        and case.index is not None
        and case.index.type_tag is not None
    }
    return tuple(
        sorted(
            bindings,
            key=lambda binding: (
                immediate_sort_key(binding[0]),
                binding[1],
            ),
        )
    )


def indexed_load_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    index_lanes: int,
    immediate_value: str,
    index_type_tag: str,
    from_array_name: str,
    to_array_name: str,
) -> tuple[BenchmarkIndexedLoadCorrectnessCase, ...]:
    matching: list[BenchmarkIndexedLoadCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        case_index = case.index
        if (
            case.kind != "indexed_load"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.invocation.param_kinds != ("cptr", "vidx", "sImm")
            or case.invocation.immediate != immediate_value
            or case_index is None
            or case_index.type_tag != index_type_tag
            or case_index.base_spelling is None
            or len(case.inputs.vectors) != 2
            or not case.expectation.values
            or case.case_name in seen
        ):
            continue
        authored_index_lanes = case_index.lanes or len(case.inputs.vectors[1])
        if (
            authored_index_lanes <= 0
            or authored_index_lanes > len(case.expectation.values)
            or index_lanes > lanes
        ):
            continue
        loaded = case.expectation.values[:authored_index_lanes]
        inactive = case.expectation.values[authored_index_lanes:]
        if lanes > index_lanes and not inactive:
            continue
        expected = tile(loaded, index_lanes) + tile(inactive, lanes - index_lanes)
        seen.add(case.case_name)
        matching.append(
            BenchmarkIndexedLoadCorrectnessCase(
                case_name=case.case_name,
                memory_values=case.inputs.vectors[0],
                index_values=tile(case.inputs.vectors[1], index_lanes),
                expected=expected,
                index_type_tag=index_type_tag,
                index_base_spelling=case_index.base_spelling,
                from_array_name=from_array_name,
                to_array_name=to_array_name,
            )
        )
    return tuple(matching)


def reduction_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    from_array_name: str,
) -> tuple[BenchmarkReductionCorrectnessCase, ...]:
    matching: list[BenchmarkReductionCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "reduction"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.lanes != lanes
            or case.invocation.result_kind != "s"
            or case.invocation.param_kinds != ("v",)
            or len(case.inputs.vectors) != 1
            or len(case.inputs.vectors[0]) != lanes
            or len(case.expectation.values) != 1
            or case.case_name in seen
        ):
            continue
        seen.add(case.case_name)
        matching.append(
            BenchmarkReductionCorrectnessCase(
                case_name=case.case_name,
                vector_input=case.inputs.vectors[0],
                expected=case.expectation.values[0],
                from_array_name=from_array_name,
            )
        )
    return tuple(matching)


def vector_mask_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    from_array_name: str,
    to_integral_name: str,
) -> tuple[BenchmarkVectorMaskCorrectnessCase, ...]:
    matching: list[BenchmarkVectorMaskCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "generic_golden"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.lanes != lanes
            or case.invocation.result_kind != "m"
            or case.invocation.param_kinds != spec.param_kinds
            or len(case.inputs.vectors) != len(spec.param_kinds)
            or any(len(values) != lanes for values in case.inputs.vectors)
            or len(case.expectation.values) != lanes
            or case.case_name in seen
        ):
            continue
        expected_mask = sum(
            1 << lane
            for lane, value in enumerate(case.expectation.values)
            if token_truthy(value)
        )
        seen.add(case.case_name)
        matching.append(
            BenchmarkVectorMaskCorrectnessCase(
                case_name=case.case_name,
                vector_inputs=case.inputs.vectors,
                expected_mask=str(expected_mask),
                from_array_name=from_array_name,
                to_integral_name=to_integral_name,
            )
        )
    return tuple(matching)


def mask_cases(
    cases: tuple[ValueTestCasePlan, ...],
    spec: LoweredSpecialization,
    lanes: int,
    to_integral_name: str,
) -> tuple[BenchmarkMaskCorrectnessCase, ...]:
    matching: list[BenchmarkMaskCorrectnessCase] = []
    seen: set[str] = set()
    for case in cases:
        if (
            case.kind != "mask_result"
            or case.call_name != spec.primitive_name
            or case.type_tag != spec.type_tag
            or case.lanes != lanes
            or case.invocation.result_kind != "m"
            or case.invocation.param_kinds != ("im",)
            or len(case.inputs.masks) != 1
            or len(case.expectation.values) != 1
            or case.case_name in seen
        ):
            continue
        seen.add(case.case_name)
        matching.append(
            BenchmarkMaskCorrectnessCase(
                case_name=case.case_name,
                mask_inputs=case.inputs.masks,
                expected_mask=case.expectation.values[0],
                to_integral_name=to_integral_name,
            )
        )
    return tuple(matching)


__all__ = (
    "immediate_cases",
    "immediate_values",
    "indexed_load_bindings",
    "indexed_load_cases",
    "mask_cases",
    "reduction_cases",
    "vector_cases",
    "vector_mask_cases",
    "vector_scalar_cases",
)
