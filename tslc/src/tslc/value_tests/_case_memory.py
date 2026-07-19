"""Memory-oriented value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_common import ordinary_base_spelling as _ordinary_base_spelling
from tslc.value_tests.case_components import IndexStyle
from tslc.value_tests.case_helpers import (
    axis_args as _axis_args,
    effective_lanes as _effective_lanes,
    function_name as _function_name,
    maskish_inputs as _maskish_inputs,
    plan_case as _plan,
    scalar_inputs as _scalar_inputs,
    valid_generic_lanes as _valid_generic_lanes,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import (
    ValueTestCasePlan,
    ValueTestExpectation,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
)
from tslc.value_tests.param_layouts import resolve_param_layout

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
    primitive: Primitive,
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or len(case.expected) != 1:
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1:
        return None
    lanes = _valid_generic_lanes(case.type_tag, case.lanes or len(vector_inputs[0]))
    target_base_spelling = None
    expected_type_tag = None
    if case.attrs.get("packed") == "false":
        layout = resolve_param_layout(primitive, "ptr", case, specs)
        if layout is None:
            return None
        target_base_spelling = layout.base_spelling
        expected_type_tag = layout.type_tag
    return _plan(
        "mask_pointer_load",
        name,
        index,
        case,
        specs,
        base_spelling,
        vector_inputs=vector_inputs,
        target_base_spelling=target_base_spelling,
        expected_type_tag=expected_type_tag,
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
    primitive: Primitive,
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
        layout = resolve_param_layout(primitive, "ptr", case, specs)
        if layout is None:
            return None
        expected_type_tag = layout.type_tag
        target_base_spelling = layout.base_spelling
    return _plan(
        "mask_store",
        name,
        index,
        case,
        specs,
        base_spelling,
        mask_inputs=mask_inputs,
        expected=case.expected,
        storage="packed" if packed else "unpacked",
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
        inputs=ValueTestInputs(scalars=scalar_inputs),
        expectation=ValueTestExpectation(values=case.expected),
        invocation=ValueTestInvocation(
            result_kind=specs[0].result_kind,
            param_kinds=specs[0].param_kinds,
        ),
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
        inputs=ValueTestInputs(scalars=scalar_inputs),
        expectation=ValueTestExpectation(values=case.expected),
        invocation=ValueTestInvocation(
            result_kind=specs[0].result_kind,
            param_kinds=specs[0].param_kinds,
        ),
        memory=(
            ValueTestMemory(alignment=case.alignment)
            if case.alignment is not None
            else None
        ),
    )

def indexed_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    index_base_spelling: str | None = None,
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or case.scale is None:
        return None
    vector_inputs = _vector_inputs(case)
    # Indexed-memory source cases author the mask literal after the vector-shaped
    # pointer/index/source operands. Test promotion therefore preserves it as a
    # scalar token; accept that established source shape just as the other masked
    # memory planners do.
    mask_inputs = _maskish_inputs(case)
    expected_len = len(case.expected)
    if len(vector_inputs) not in (2, 3) or expected_len == 0:
        return None
    if case.index_type is not None and index_base_spelling is None:
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
        index_type_tag=case.index_type,
        index_base_spelling=index_base_spelling,
        index_lanes=len(vector_inputs[1]),
        index_style=_index_style(specs),
    )

def indexed_store_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    index_base_spelling: str | None = None,
) -> ValueTestCasePlan | None:
    base_spelling = _ordinary_base_spelling(case, specs)
    if base_spelling is None or case.scale is None:
        return None
    vector_inputs = _vector_inputs(case)
    mask_inputs = _maskish_inputs(case)
    if len(vector_inputs) != 2 or not case.expected:
        return None
    if case.index_type is not None and index_base_spelling is None:
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
        index_type_tag=case.index_type,
        index_base_spelling=index_base_spelling,
        index_lanes=len(vector_inputs[1]),
        index_style=_index_style(specs),
    )


def _index_style(specs: tuple[LoweredSpecialization, ...]) -> IndexStyle:
    """Indexed-memory calls either load the authored indices into an index
    register or forward them as a raw pointer; the signature decides once."""

    if tuple(specs[0].param_kinds) == ("cptr", "cptr", "sImm"):
        return "pointer"
    return "register"

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

__all__ = (
    "store_case",
    "load_case",
    "scalar_pointer_load_case",
    "mask_pointer_load_case",
    "mask_store_case",
    "masked_pointer_load_case",
    "masked_pointer_store_case",
    "memory_copy_case",
    "pointer_lifetime_case",
    "pointer_free_case",
    "indexed_load_case",
    "indexed_store_case",
    "stream_case",
)
