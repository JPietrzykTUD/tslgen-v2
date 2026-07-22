"""Core value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import TestCase
from tslc.catalog.scalar_types import scalar_bit_width_or_default
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_common import ordinary_base_spelling as _ordinary_base_spelling
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    base_spelling as _base_spelling,
    effective_lanes as _effective_lanes,
    immediate_value as _immediate_value,
    mask_inputs as _mask_inputs,
    plan_case as _plan,
    scalar_inputs as _scalar_inputs,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.literals import token_truthy
from tslc.value_tests.model import ValueTestCasePlan, ValueTestFailure

def generic_golden_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    index_base_spelling: str | None = None,
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = _vector_inputs(case)
    if base_spelling is None or len(vector_inputs) != len(specs[0].param_kinds):
        return None
    has_index_vector = "vidx" in specs[0].param_kinds
    if has_index_vector and (case.index_type is None or index_base_spelling is None):
        return None
    if len(case.expected) != case.lanes:
        return None
    generic_defaults = tuple(default for _name, _type, default in specs[0].generic_params)
    return _plan(
        "generic_golden",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        expected=case.expected,
        generic_defaults=generic_defaults,
        index_type_tag=case.index_type if has_index_vector else None,
        index_base_spelling=index_base_spelling if has_index_vector else None,
        index_lanes=case.lanes if has_index_vector else None,
    )


def masked_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    index_base_spelling: str | None = None,
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    mask_inputs = _mask_inputs(case)
    vector_inputs = _vector_inputs(case)
    if base_spelling is None or len(case.expected) != case.lanes:
        return None
    has_index_vector = "vidx" in specs[0].param_kinds
    if has_index_vector and (case.index_type is None or index_base_spelling is None):
        return None
    vector_param_count = sum(kind in {"v", "vidx"} for kind in specs[0].param_kinds)
    if len(mask_inputs) != 1 or len(vector_inputs) != vector_param_count:
        return None
    return _plan(
        "masked",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        expected=case.expected,
        mask_inputs=mask_inputs,
        index_type_tag=case.index_type if has_index_vector else None,
        index_base_spelling=index_base_spelling if has_index_vector else None,
        index_lanes=case.lanes if has_index_vector else None,
    )

def reduction_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1 or len(case.expected) != 1:
        return None
    return _plan("reduction", name, index, case, specs, base_spelling, vector_inputs=vector_inputs)

def mask_logic_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    mask_inputs = _mask_inputs(case)
    if len(case.expected) != 1 or len(mask_inputs) != len(specs[0].param_kinds):
        return None
    return _plan("mask_logic", name, index, case, specs, base_spelling, mask_inputs=mask_inputs)

def vector_to_array_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    return _plan(
        "vector_to_array", name, index, case, specs, base_spelling, vector_inputs=vector_inputs
    )

def broadcast_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    scalar_inputs = _scalar_inputs(case)
    if len(scalar_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    return _plan(
        "broadcast", name, index, case, specs, base_spelling, scalar_input=scalar_inputs[0]
    )

def lane_list_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    scalar_inputs = _scalar_inputs(case)
    if vector_inputs:
        if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
            return None
        lane_values = vector_inputs[0]
    else:
        if len(scalar_inputs) != case.lanes:
            return None
        lane_values = scalar_inputs
    if len(case.expected) != case.lanes:
        return None
    return _plan(
        "lane_list",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=(lane_values,),
    )

def mask_to_vector_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    mask_inputs = _mask_inputs(case)
    if len(mask_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    return _plan(
        "mask_to_vector", name, index, case, specs, base_spelling, mask_inputs=mask_inputs
    )

def compile_only_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.role != "compile":
        return None
    base_spelling = _base_spelling(specs, case.type_tag) or specs[0].base_type_spelling
    if case.lanes is None:
        return None
    return _plan(
        "compile_only",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        scalar_inputs=_scalar_inputs(case),
    )


def runtime_failure_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.role != "runtime_failure" or case.failure is None or case.lanes is None:
        return None
    if not _args_match(case, specs[0].param_kinds):
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    if base_spelling is None:
        return None
    return _plan(
        "runtime_failure",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        scalar_inputs=_scalar_inputs(case),
        failure=ValueTestFailure(reason=case.failure),
    )


def compile_failure_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.role != "compile_failure" or case.failure is None or case.lanes is None:
        return None
    if not _args_match(case, specs[0].param_kinds):
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    immediate_inputs = _scalar_inputs(case)
    if base_spelling is None or len(immediate_inputs) != 1:
        return None
    return _plan(
        "compile_failure",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        expected=(),
        immediate_value=_immediate_value(immediate_inputs[0], specs[0].immediate),
        failure=ValueTestFailure(reason=case.failure, phase="compile"),
    )


def status_pointer_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    """Plan a status-returning operation that conditionally writes one pointee."""

    scalar_inputs = _scalar_inputs(case)
    base_spelling = _base_spelling(specs, case.type_tag)
    if (
        case.expected_rule != "status_pointer"
        or base_spelling is None
        or len(scalar_inputs) != 1
        or case.expected
    ):
        return None
    return _plan(
        "status_pointer",
        name,
        index,
        case,
        specs,
        base_spelling,
        scalar_inputs=scalar_inputs,
        lanes=1,
    )

def array_to_vector_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
        return None
    if len(case.expected) != case.lanes:
        return None
    return _plan(
        "array_to_vector",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
    )

def scalar_result_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    lanes = _scalar_result_lanes(case, vector_inputs, mask_inputs)
    if not _args_match(case, specs[0].param_kinds):
        return None
    generic_defaults: tuple[str, ...] = ()
    if case.index is None:
        generic_defaults = tuple(default for _name, _type, default in specs[0].generic_params)
    return _plan(
        "scalar_result",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        scalar_inputs=_scalar_inputs(case),
        lanes=lanes,
        generic_defaults=generic_defaults,
    )


def _scalar_result_lanes(
    case: TestCase,
    vector_inputs: tuple[tuple[str, ...], ...],
    mask_inputs: tuple[str, ...],
) -> int | None:
    lanes = _effective_lanes(case)
    if vector_inputs or not mask_inputs or lanes is None:
        return lanes
    minimum_generic_lanes = max(1, 128 // scalar_bit_width_or_default(case.type_tag))
    return max(lanes, minimum_generic_lanes)


def mask_result_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    lanes = _effective_lanes(case)
    if not _args_match(case, specs[0].param_kinds):
        return None
    return _plan(
        "mask_result",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        scalar_inputs=_scalar_inputs(case),
        lanes=lanes,
    )

def masked_mask_result_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if (
        base_spelling is None
        or case.lanes is None
        or case.expected_rule is not None
        or len(case.expected) != case.lanes
    ):
        return None
    if not _args_match(case, specs[0].param_kinds):
        return None
    expected_bits = 0
    for lane, token in enumerate(case.expected):
        if token_truthy(token):
            expected_bits |= 1 << lane
    return _plan(
        "mask_result",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        expected=(str(expected_bits),),
        lanes=case.lanes,
    )

def scalar_vector_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != case.lanes:
        return None
    if not _args_match(case, specs[0].param_kinds):
        return None
    generic_defaults: tuple[str, ...] = ()
    if case.index is None:
        generic_defaults = tuple(
            default for _name, _type, default in specs[0].generic_params
        )
    return _plan(
        "scalar_vector",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=_vector_inputs(case),
        mask_inputs=_mask_inputs(case),
        scalar_inputs=_scalar_inputs(case),
        generic_defaults=generic_defaults,
    )

def immediate_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    imm_inputs = _scalar_inputs(case)
    if base_spelling is None or len(imm_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    if (
        len(vector_inputs) != specs[0].param_kinds.count("v")
        or len(mask_inputs) != specs[0].param_kinds.count("m")
    ):
        return None
    return _plan(
        "immediate",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        expected=case.expected,
        immediate_value=_immediate_value(imm_inputs[0], specs[0].immediate),
        generic_defaults=tuple(default for _name, _type, default in specs[0].generic_params),
    )

__all__ = (
    "generic_golden_case",
    "masked_case",
    "reduction_case",
    "mask_logic_case",
    "vector_to_array_case",
    "broadcast_case",
    "lane_list_case",
    "mask_to_vector_case",
    "compile_only_case",
    "compile_failure_case",
    "runtime_failure_case",
    "array_to_vector_case",
    "scalar_result_case",
    "masked_mask_result_case",
    "mask_result_case",
    "scalar_vector_case",
    "status_pointer_case",
    "immediate_case",
)
