"""Build render-ready value-test case plans from typed test facts."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.catalog.scalar_types import unsigned_of
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    axis_args as _axis_args,
    base_spelling as _base_spelling,
    convert_match as _convert_match,
    effective_lanes as _effective_lanes,
    extension_repr_match as _extension_repr_match,
    function_name as _function_name,
    immediate_value as _immediate_value,
    inferred_mask_lanes as _inferred_mask_lanes,
    load_convert_match as _load_convert_match,
    mask_inputs as _mask_inputs,
    maskish_inputs as _maskish_inputs,
    plan_case as _plan,
    repr_cast_match as _repr_cast_match,
    sanitize as _sanitize,
    scalar_inputs as _scalar_inputs,
    type_bits_for_tag as _type_bits,
    valid_generic_lanes as _valid_generic_lanes,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import HarnessPrimitiveNames, ValueTestCasePlan


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


def store_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    offset = case.offset or 0
    if len(vector_inputs) != 1 or len(case.expected) < offset + (case.lanes or 0):
        return None
    return _plan(
        "store",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        expected=case.expected,
        axis_args=_axis_args(specs[0], case),
        buffer_offset=offset,
        buffer_length=len(case.expected),
    )


def load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    offset = case.offset or 0
    if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
        return None
    if len(case.expected) != case.lanes:
        return None
    return _plan(
        "load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        expected=case.expected,
        axis_args=_axis_args(specs[0], case),
        buffer_offset=offset,
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


def scalar_pointer_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1:
        return None
    lanes = _valid_generic_lanes(case.type_tag, case.lanes or len(vector_inputs[0]))
    return _plan(
        "scalar_pointer_load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        axis_args=_axis_args(specs[0], case),
        buffer_offset=case.offset or 0,
        buffer_length=len(vector_inputs[0]),
        lanes=lanes,
    )


def mask_pointer_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1:
        return None
    lanes = _valid_generic_lanes(case.type_tag, case.lanes or len(vector_inputs[0]))
    return _plan(
        "mask_pointer_load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        axis_args=_axis_args(specs[0], case),
        buffer_offset=case.offset or 0,
        buffer_length=len(vector_inputs[0]),
        lanes=lanes,
    )


def mask_store_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    lanes = _effective_lanes(case)
    mask_inputs = _maskish_inputs(case)
    if len(mask_inputs) != 1 or not case.expected:
        return None
    packed = case.attrs.get("packed") == "true"
    expected_type_tag = None
    target_base_spelling = None
    if not packed:
        expected_type_tag = unsigned_of(case.type_tag)
        target_base_spelling = _base_spelling(specs, expected_type_tag)
        if target_base_spelling is None:
            return None
    return _plan(
        "mask_store",
        name,
        index,
        case,
        specs,
        base_spelling,
        mask_inputs=mask_inputs,
        expected=case.expected,
        result_kind="packed" if packed else None,
        target_base_spelling=target_base_spelling,
        expected_type_tag=expected_type_tag,
        axis_args=_axis_args(specs[0], case),
        buffer_offset=case.offset or 0,
        buffer_length=len(case.expected),
        lanes=lanes,
    )


def masked_pointer_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != case.lanes:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _maskish_inputs(case)
    if len(vector_inputs) != 1 or len(mask_inputs) != 1:
        return None
    return _plan(
        "masked_pointer_load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        expected=case.expected,
        axis_args=_axis_args(specs[0], case),
    )


def masked_pointer_store_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _maskish_inputs(case)
    if len(vector_inputs) != 1 or len(mask_inputs) != 1:
        return None
    return _plan(
        "masked_pointer_store",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        expected=case.expected,
        axis_args=_axis_args(specs[0], case),
        buffer_length=len(case.expected),
    )


def memory_copy_case(
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
    if len(vector_inputs) != 1 or len(scalar_inputs) != 1:
        return None
    return _plan(
        "memory_copy",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        scalar_inputs=scalar_inputs,
        expected=case.expected,
        buffer_offset=case.dst_offset or 0,
        buffer_length=len(case.expected),
        source_offset=case.src_offset or 0,
    )


def pointer_lifetime_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.type_tag != "ptr" or len(case.expected) != 1:
        return None
    scalar_inputs = _scalar_inputs(case)
    if len(scalar_inputs) != len(specs[0].param_kinds):
        return None
    return ValueTestCasePlan(
        kind="pointer_lifetime",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=specs[0].base_type_spelling,
        lanes=case.lanes or 1,
        result_kind=specs[0].result_kind,
        param_kinds=specs[0].param_kinds,
        scalar_inputs=scalar_inputs,
        expected=case.expected,
    )


def pointer_free_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.type_tag != "ptr" or len(case.expected) != 1:
        return None
    scalar_inputs = _scalar_inputs(case)
    if len(scalar_inputs) != 1:
        return None
    return ValueTestCasePlan(
        kind="pointer_free",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=specs[0].base_type_spelling,
        lanes=case.lanes or 1,
        result_kind=specs[0].result_kind,
        param_kinds=specs[0].param_kinds,
        scalar_inputs=scalar_inputs,
        expected=case.expected,
        target_base_spelling=str(case.alignment) if case.alignment is not None else None,
    )


def load_convert_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames | None = None,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None or case.to_type is None:
        return None
    match = _load_convert_match(case, specs)
    if match is None or match.target is None:
        return None
    if case.extension is not None and (harness is None or harness.to_array is None):
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1 or len(case.expected) == 0:
        return None
    source_lanes = _valid_generic_lanes(case.type_tag, len(vector_inputs[0]))
    return ValueTestCasePlan(
        kind="load_convert",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=source_lanes,
        vector_inputs=vector_inputs,
        expected=case.expected,
        expected_type_tag=case.to_type,
        target_base_spelling=match.target.base_spelling,
        target_lanes=len(case.expected),
        result_kind=match.result_kind,
        param_kinds=match.param_kinds,
        source_extension=match.extension_name if case.extension is not None else None,
        target_extension=match.target.extension_isa if case.extension is not None else None,
        to_array_name=harness.to_array if case.extension is not None and harness else None,
    )


def indexed_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or case.scale is None:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    expected_len = len(case.expected)
    if len(vector_inputs) not in (2, 3) or expected_len == 0:
        return None
    return _plan(
        "indexed_load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        expected=case.expected,
        immediate_value=str(case.scale),
        target_lanes=expected_len,
    )


def indexed_store_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or case.scale is None:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    if len(vector_inputs) != 2 or not case.expected:
        return None
    return _plan(
        "indexed_store",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        expected=case.expected,
        immediate_value=str(case.scale),
        buffer_length=len(case.expected),
    )


def stream_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    vector_inputs = _vector_inputs(case)
    scalar_inputs = _scalar_inputs(case)
    if len(vector_inputs) != 1 or len(scalar_inputs) != 1:
        return None
    return _plan(
        "stream",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        scalar_inputs=scalar_inputs,
        text_expected=case.expected[0],
    )


def _ordinary_base_spelling(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> str | None:
    if _effective_lanes(case) is None:
        return None
    return _base_spelling(specs, case.type_tag)


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


def convert_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.index is None or case.expected_rule is not None:
        return None
    match = _convert_match(case, specs)
    if match is None or match.target is None or match.target.lane_parameter is None:
        return None
    vector_inputs = _vector_inputs(case)
    out_lanes = int(match.target.lane_parameter)
    if (
        len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != out_lanes
    ):
        return None
    return ValueTestCasePlan(
        kind="convert",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes or 0,
        vector_inputs=vector_inputs,
        expected=case.expected,
        expected_type_tag=case.to_type,
        target_base_spelling=match.target.base_spelling,
        target_lanes=out_lanes,
        index_value=str(case.index),
    )


def repr_cast_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames | None = None,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None:
        return None
    match = _repr_cast_match(case, specs)
    if match is None or match.target is None:
        return None
    if case.extension is not None and (
        harness is None or not harness.round_trip_ready
    ):
        return None
    vector_inputs = _vector_inputs(case)
    if case.lanes is None or len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
        return None
    target_lanes = len(case.expected)
    if target_lanes == 0:
        return None
    return ValueTestCasePlan(
        kind="repr_cast",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes,
        vector_inputs=vector_inputs,
        expected=case.expected,
        expected_type_tag=case.to_type,
        target_base_spelling=match.target.base_spelling,
        target_lanes=target_lanes,
        source_extension=match.extension_name if case.extension is not None else None,
        target_extension=match.target.extension_isa if case.extension is not None else None,
        from_array_name=harness.from_array if case.extension is not None and harness else None,
        to_array_name=harness.to_array if case.extension is not None and harness else None,
    )


def extension_repr_case(
    kind: str,
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None:
        return None
    match = _extension_repr_match(case, specs)
    if match is None:
        return None
    vector_inputs = _vector_inputs(case)
    imm_inputs = _scalar_inputs(case)
    if len(imm_inputs) != 1:
        return None
    if kind == "extension_extract":
        lanes = case.lanes or (len(vector_inputs[0]) if vector_inputs else None)
        if lanes is None or len(vector_inputs) != 1 or len(vector_inputs[0]) != lanes:
            return None
    else:
        lanes = case.lanes or (len(vector_inputs[1]) if len(vector_inputs) > 1 else None)
        if lanes is None or len(vector_inputs) != 2 or len(vector_inputs[1]) != lanes:
            return None
    return ValueTestCasePlan(
        kind=kind,
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=lanes,
        vector_inputs=vector_inputs,
        expected=case.expected,
        source_extension=case.extension,
        target_extension=case.to_extension,
        index_value=imm_inputs[0],
        from_array_name=harness.from_array,
        to_array_name=harness.to_array,
    )


def differential_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
) -> list[ValueTestCasePlan]:
    if case.lanes is None or case.expected_rule is not None:
        return []
    base_spelling = _base_spelling(specs, case.type_tag)
    type_bits = _type_bits(case.type_tag)
    vector_inputs = _vector_inputs(case)
    if base_spelling is None or type_bits is None:
        return []
    if len(vector_inputs) != len(specs[0].param_kinds):
        return []
    if specs[0].result_kind == "m" and harness.to_integral is None:
        return []
    emitted: list[ValueTestCasePlan] = []
    for spec in specs:
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or spec.uses_sized_vector or extension.vector_bits <= 0:
            continue
        if spec.type_tag != case.type_tag:
            continue
        if extension.vector_bits != case.lanes * type_bits:
            continue
        emitted.append(
            ValueTestCasePlan(
                kind="differential",
                function_name=f"test_diff_{spec.extension_name}_{_sanitize(case.name)}",
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=base_spelling,
                lanes=case.lanes,
                vector_inputs=vector_inputs,
                result_kind=specs[0].result_kind,
                param_kinds=specs[0].param_kinds,
                hardware_extension=spec.extension_name,
                from_array_name=harness.from_array,
                to_array_name=harness.to_array,
                to_integral_name=harness.to_integral,
            )
        )
    return emitted


def extension_harness_available(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> bool:
    return _extension_repr_match(case, specs) is not None


__all__ = (
    "array_to_vector_case",
    "broadcast_case",
    "compile_only_case",
    "convert_case",
    "differential_cases",
    "extension_harness_available",
    "extension_repr_case",
    "generic_golden_case",
    "immediate_case",
    "indexed_load_case",
    "indexed_store_case",
    "lane_list_case",
    "load_convert_case",
    "load_case",
    "mask_logic_case",
    "mask_pointer_load_case",
    "mask_result_case",
    "mask_store_case",
    "mask_to_vector_case",
    "masked_case",
    "masked_pointer_load_case",
    "masked_pointer_store_case",
    "memory_copy_case",
    "pointer_free_case",
    "pointer_lifetime_case",
    "reduction_case",
    "repr_cast_case",
    "scalar_pointer_load_case",
    "scalar_result_case",
    "scalar_vector_case",
    "store_case",
    "stream_case",
    "vector_to_array_case",
)
