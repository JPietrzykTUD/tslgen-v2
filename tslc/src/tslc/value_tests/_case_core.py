"""Core value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_common import ordinary_base_spelling as _ordinary_base_spelling
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    axis_args as _axis_args,
    base_spelling as _base_spelling,
    effective_lanes as _effective_lanes,
    function_name as _function_name,
    immediate_value as _immediate_value,
    mask_inputs as _mask_inputs,
    plan_case as _plan,
    scalar_inputs as _scalar_inputs,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import ValueTestCasePlan

def generic_golden_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = _vector_inputs(case)
    if base_spelling is None or len(vector_inputs) != len(specs[0].param_kinds):
        return None
    if len(case.expected) != case.lanes:
        return None
    return ValueTestCasePlan(
        kind="generic_golden",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=base_spelling,
        lanes=case.lanes,
        vector_inputs=vector_inputs,
        expected=case.expected,
        result_kind=specs[0].result_kind,
        param_kinds=specs[0].param_kinds,
    )

def masked_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    mask_inputs = _mask_inputs(case)
    vector_inputs = _vector_inputs(case)
    if base_spelling is None or len(case.expected) != case.lanes:
        return None
    if len(mask_inputs) != 1 or len(vector_inputs) != specs[0].param_kinds.count("v"):
        return None
    return ValueTestCasePlan(
        kind="masked",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=base_spelling,
        lanes=case.lanes,
        vector_inputs=vector_inputs,
        expected=case.expected,
        param_kinds=specs[0].param_kinds,
        mask_inputs=mask_inputs,
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
    lanes = _effective_lanes(case)
    if not _args_match(case, specs[0].param_kinds):
        return None
    return _plan(
        "scalar_result",
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
    imm_inputs = _scalar_inputs(case)
    if base_spelling is None or len(imm_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    if len(vector_inputs) != specs[0].param_kinds.count("v"):
        return None
    return ValueTestCasePlan(
        kind="immediate",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=base_spelling,
        lanes=case.lanes,
        vector_inputs=vector_inputs,
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
    "array_to_vector_case",
    "scalar_result_case",
    "mask_result_case",
    "scalar_vector_case",
    "immediate_case",
)
