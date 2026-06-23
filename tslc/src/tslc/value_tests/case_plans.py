"""Build render-ready value-test case plans from typed test facts."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
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


def simple_case(
    kind: str,
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    if base_spelling is None:
        return None
    if kind == "store":
        vector_inputs = _vector_inputs(case)
        offset = case.offset or 0
        if len(vector_inputs) != 1 or len(case.expected) < offset + case.lanes:
            return None
        return _plan(
            kind,
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
    if kind == "load":
        vector_inputs = _vector_inputs(case)
        offset = case.offset or 0
        if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
            return None
        if len(case.expected) != case.lanes:
            return None
        return _plan(
            kind,
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
    if kind == "reduction":
        vector_inputs = _vector_inputs(case)
        if len(vector_inputs) != 1 or len(case.expected) != 1:
            return None
        return _plan(kind, name, index, case, specs, base_spelling, vector_inputs=vector_inputs)
    if kind == "mask_logic":
        mask_inputs = _mask_inputs(case)
        if len(case.expected) != 1 or len(mask_inputs) != len(specs[0].param_kinds):
            return None
        return _plan(kind, name, index, case, specs, base_spelling, mask_inputs=mask_inputs)
    if kind == "vector_to_array":
        vector_inputs = _vector_inputs(case)
        if len(vector_inputs) != 1 or len(case.expected) != case.lanes:
            return None
        return _plan(kind, name, index, case, specs, base_spelling, vector_inputs=vector_inputs)
    if kind == "broadcast":
        scalar_inputs = _mask_inputs(case)
        if len(scalar_inputs) != 1 or len(case.expected) != case.lanes:
            return None
        return _plan(kind, name, index, case, specs, base_spelling, scalar_input=scalar_inputs[0])
    if kind == "lane_list":
        vector_inputs = _vector_inputs(case)
        if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
            return None
        if len(case.expected) != case.lanes:
            return None
        return _plan(kind, name, index, case, specs, base_spelling, vector_inputs=vector_inputs)
    if kind == "mask_to_vector":
        mask_inputs = _mask_inputs(case)
        if len(mask_inputs) != 1 or len(case.expected) != case.lanes:
            return None
        return _plan(kind, name, index, case, specs, base_spelling, mask_inputs=mask_inputs)
    return None


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
    imm_inputs = _mask_inputs(case)
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
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None:
        return None
    match = _repr_cast_match(case, specs)
    if match is None or match.target is None:
        return None
    vector_inputs = _vector_inputs(case)
    if (
        case.lanes is None
        or len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != case.lanes
    ):
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
        target_lanes=case.lanes,
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
    imm_inputs = _mask_inputs(case)
    if len(imm_inputs) != 1:
        return None
    if kind == "extension_extract":
        if len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
            return None
    else:
        if len(vector_inputs) != 2 or len(vector_inputs[1]) != case.lanes:
            return None
    return ValueTestCasePlan(
        kind=kind,
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes or 0,
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
        if spec.uses_sized_vector or spec.extension_name == "scalar":
            continue
        if spec.type_tag != case.type_tag:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits != case.lanes * type_bits:
            continue
        emitted.append(
            ValueTestCasePlan(
                kind="differential",
                function_name=(
                    f"test_{name}_diff_{spec.extension_name}_{index}_{_sanitize(case.name)}"
                ),
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


def _plan(
    kind: str,
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    base_spelling: str,
    *,
    vector_inputs: tuple[tuple[str, ...], ...] = (),
    mask_inputs: tuple[str, ...] = (),
    scalar_input: str | None = None,
    expected: tuple[str, ...] | None = None,
    axis_args: tuple[str, ...] = (),
    buffer_offset: int = 0,
    buffer_length: int | None = None,
) -> ValueTestCasePlan:
    return ValueTestCasePlan(
        kind=kind,
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=base_spelling,
        lanes=case.lanes or 0,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        scalar_input=scalar_input,
        expected=case.expected if expected is None else expected,
        param_kinds=specs[0].param_kinds,
        axis_args=axis_args,
        buffer_offset=buffer_offset,
        buffer_length=buffer_length,
    )


def _convert_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_type is None or case.lanes is None:
        return None
    return next(
        (
            spec
            for spec in specs
            if spec.type_tag == case.type_tag
            and spec.target is not None
            and spec.target.base_tag == case.to_type
            and spec.lane_parameter == str(case.lanes)
            and spec.target.lane_parameter is not None
        ),
        None,
    )


def _repr_cast_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_type is None or case.lanes is None:
        return None
    return next(
        (
            spec
            for spec in specs
            if spec.uses_sized_vector
            and spec.type_tag == case.type_tag
            and spec.target is not None
            and spec.target.base_tag == case.to_type
        ),
        None,
    )


def _extension_repr_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_extension is None or case.lanes is None:
        return None
    return next(
        (
            spec
            for spec in specs
            if spec.type_tag == case.type_tag
            and spec.extension_name == case.extension
            and spec.target is not None
            and spec.target.extension_isa == case.to_extension
        ),
        None,
    )


def _axis_args(spec: LoweredSpecialization, case: TestCase) -> tuple[str, ...]:
    return tuple(case.attrs.get(axis_name, value) for axis_name, value in spec.axis)


def _vector_inputs(case: TestCase) -> tuple[tuple[str, ...], ...]:
    return tuple(arg.values for arg in case.inputs if arg.kind == "vector")


def _mask_inputs(case: TestCase) -> tuple[str, ...]:
    return tuple(
        arg.mask_bits
        for arg in case.inputs
        if arg.kind == "mask" and arg.mask_bits is not None
    )


def _type_bits(type_tag: str) -> int | None:
    digits = "".join(c for c in type_tag if c.isdigit())
    return int(digits) if digits else None


def _base_spelling(
    specs: tuple[LoweredSpecialization, ...],
    type_tag: str,
) -> str | None:
    for spec in specs:
        if spec.type_tag == type_tag:
            return spec.base_type_spelling
    return None


def _immediate_value(token: str, immediate: tuple[str, str] | None) -> str:
    if immediate is None:
        return token
    spelling = immediate[1]
    digits = "".join(c for c in spelling if c.isdigit())
    if not digits:
        return token
    try:
        value = int(token)
    except ValueError:
        return token
    bits = int(digits)
    value %= 1 << bits
    if not spelling.lstrip().startswith("u") and value >= (1 << (bits - 1)):
        value -= 1 << bits
    return str(value)


def _function_name(name: str, index: int, case: TestCase) -> str:
    return f"test_{name}_{index}_{_sanitize(case.name)}"


def _sanitize(text_value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text_value)


__all__ = (
    "convert_case",
    "differential_cases",
    "extension_harness_available",
    "extension_repr_case",
    "generic_golden_case",
    "immediate_case",
    "masked_case",
    "repr_cast_case",
    "simple_case",
)
