"""Conversion and extension-representation value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import (
    base_spelling as _base_spelling,
    convert_match as _convert_match,
    extension_repr_match as _extension_repr_match,
    function_name as _function_name,
    load_convert_match as _load_convert_match,
    repr_cast_match as _repr_cast_match,
    sanitize as _sanitize,
    scalar_inputs as _scalar_inputs,
    type_bits_for_tag as _type_bits,
    valid_generic_lanes as _valid_generic_lanes,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import HarnessPrimitiveNames, ValueTestCasePlan

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
    "load_convert_case",
    "convert_case",
    "repr_cast_case",
    "extension_repr_case",
    "differential_cases",
    "extension_harness_available",
)
