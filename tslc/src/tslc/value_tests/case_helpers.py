"""Shared helpers for building value-test case plans."""

from __future__ import annotations

from tslc.catalog.model import TestCase
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.model import ValueTestCasePlan


def plan_case(
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
    scalar_inputs: tuple[str, ...] = (),
    expected: tuple[str, ...] | None = None,
    axis_args: tuple[str, ...] = (),
    buffer_offset: int = 0,
    buffer_length: int | None = None,
    source_offset: int = 0,
    text_expected: str | None = None,
    immediate_value: str | None = None,
    generic_defaults: tuple[str, ...] = (),
    result_kind: str | None = None,
    expected_type_tag: str | None = None,
    target_base_spelling: str | None = None,
    target_lanes: int | None = None,
    lanes: int | None = None,
) -> ValueTestCasePlan:
    return ValueTestCasePlan(
        kind=kind,
        function_name=function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=base_spelling,
        lanes=lanes if lanes is not None else case.lanes or 0,
        vector_inputs=vector_inputs,
        mask_inputs=mask_inputs,
        scalar_input=scalar_input,
        scalar_inputs=scalar_inputs,
        expected=case.expected if expected is None else expected,
        expected_type_tag=expected_type_tag,
        result_kind=specs[0].result_kind if result_kind is None else result_kind,
        param_kinds=specs[0].param_kinds,
        axis_args=axis_args,
        buffer_offset=buffer_offset,
        buffer_length=buffer_length,
        source_offset=source_offset,
        text_expected=text_expected,
        index_value=str(case.index) if case.index is not None else None,
        immediate_value=immediate_value,
        generic_defaults=generic_defaults,
        target_base_spelling=target_base_spelling,
        target_lanes=target_lanes,
    )


def convert_match(
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


def repr_cast_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_type is None or case.lanes is None:
        return None
    if case.extension is not None:
        return next(
            (
                spec
                for spec in specs
                if spec.extension_name == case.extension
                and spec.type_tag == case.type_tag
                and spec.target is not None
                and spec.target.base_tag == case.to_type
            ),
            None,
        )
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


def load_convert_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_type is None:
        return None
    if case.extension is not None:
        return next(
            (
                spec
                for spec in specs
                if spec.extension_name == case.extension
                and spec.type_tag == case.type_tag
                and spec.target is not None
                and spec.target.base_tag == case.to_type
                and tuple(spec.param_kinds) == ("cptr+",)
            ),
            None,
        )
    return next(
        (
            spec
            for spec in specs
            if spec.uses_sized_vector
            and spec.type_tag == case.type_tag
            and spec.target is not None
            and spec.target.base_tag == case.to_type
            and tuple(spec.param_kinds) == ("cptr+",)
        ),
        None,
    )


def extension_repr_match(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> LoweredSpecialization | None:
    if case.to_extension is None:
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


def args_match(case: TestCase, param_kinds: tuple[str, ...]) -> bool:
    vector_count = sum(
        1
        for kind in param_kinds
        if kind in {"v", "vt", "ptr", "cptr", "ptr+", "cptr+", "vidx", "s[]"}
    )
    mask_count = sum(1 for kind in param_kinds if kind in {"m", "im"})
    scalar_count = sum(1 for kind in param_kinds if kind in {"s", "sImm", "usize"})
    if len(vector_inputs(case)) != vector_count:
        return False
    if len(mask_inputs(case)) != mask_count:
        return False
    return len(scalar_inputs(case)) == scalar_count


def axis_args(spec: LoweredSpecialization, case: TestCase) -> tuple[str, ...]:
    return tuple(case.attrs.get(axis_name, value) for axis_name, value in spec.axis)


def vector_inputs(case: TestCase) -> tuple[tuple[str, ...], ...]:
    return tuple(arg.values for arg in case.inputs if arg.kind == "vector")


def mask_inputs(case: TestCase) -> tuple[str, ...]:
    return tuple(
        arg.mask_bits
        for arg in case.inputs
        if arg.kind == "mask" and arg.mask_bits is not None
    )


def maskish_inputs(case: TestCase) -> tuple[str, ...]:
    return mask_inputs(case) or scalar_inputs(case)


def scalar_inputs(case: TestCase) -> tuple[str, ...]:
    return tuple(
        arg.scalar for arg in case.inputs if arg.kind == "scalar" and arg.scalar is not None
    )


def effective_lanes(case: TestCase) -> int | None:
    return case.lanes or inferred_mask_lanes(case)


def inferred_mask_lanes(case: TestCase) -> int | None:
    for token in (*mask_inputs(case), *scalar_inputs(case), *case.expected[:1]):
        lanes = integer_bit_length(token)
        if lanes is not None:
            return lanes
    return None


def integer_bit_length(token: str) -> int | None:
    try:
        value = int(token.strip().strip('"'), 0)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value.bit_length()


def valid_generic_lanes(type_tag: str, lanes: int) -> int:
    type_bits = type_bits_for_tag(type_tag)
    if type_bits is None:
        return lanes
    type_bytes = max(type_bits // 8, 1)
    register_bytes = lanes * type_bytes
    if register_bytes % 16 == 0:
        return lanes
    return lanes + ((16 - (register_bytes % 16)) // type_bytes)


def type_bits_for_tag(type_tag: str) -> int | None:
    return scalar_bit_width(type_tag)


def base_spelling(
    specs: tuple[LoweredSpecialization, ...],
    type_tag: str,
) -> str | None:
    for spec in specs:
        if spec.type_tag == type_tag:
            return spec.base_type_spelling
    return None


def immediate_value(token: str, immediate: tuple[str, str] | None) -> str:
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


def function_name(name: str, index: int, case: TestCase) -> str:
    del name
    del index
    return f"test_{sanitize(case.name)}"


def sanitize(text_value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text_value)


__all__ = (
    "args_match",
    "axis_args",
    "base_spelling",
    "convert_match",
    "effective_lanes",
    "extension_repr_match",
    "function_name",
    "immediate_value",
    "inferred_mask_lanes",
    "load_convert_match",
    "mask_inputs",
    "maskish_inputs",
    "plan_case",
    "repr_cast_match",
    "sanitize",
    "scalar_inputs",
    "valid_generic_lanes",
    "vector_inputs",
)
