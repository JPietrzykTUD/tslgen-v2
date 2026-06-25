"""Dispatch C++ value-test cases to focused renderers."""

from __future__ import annotations

from collections.abc import Callable

from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests._render_cpp_core import (
    _array_to_vector,
    _broadcast,
    _compile_only,
    _generic_golden,
    _immediate,
    _lane_list,
    _mask_logic,
    _mask_result,
    _mask_to_vector,
    _masked,
    _reduction,
    _scalar_result,
    _scalar_vector,
    _vector_to_array,
)
from tslc.value_tests._render_cpp_conversion import (
    _convert,
    _differential,
    _extension_extract,
    _extension_insert,
    _load_convert,
    _repr_cast,
)
from tslc.value_tests._render_cpp_memory import (
    _indexed_load,
    _indexed_store,
    _load,
    _mask_pointer_load,
    _mask_store,
    _masked_pointer_load,
    _masked_pointer_store,
    _memory_copy,
    _pointer_free,
    _pointer_lifetime,
    _scalar_pointer_load,
    _store,
    _stream,
)

CppCaseRenderer = Callable[[ValueTestCasePlan], str]

CPP_CASE_RENDERERS: dict[str, CppCaseRenderer] = {
    "array_to_vector": _array_to_vector,
    "broadcast": _broadcast,
    "compile_only": _compile_only,
    "convert": _convert,
    "differential": _differential,
    "extension_extract": _extension_extract,
    "extension_insert": _extension_insert,
    "generic_golden": _generic_golden,
    "immediate": _immediate,
    "indexed_load": _indexed_load,
    "indexed_store": _indexed_store,
    "lane_list": _lane_list,
    "load": _load,
    "load_convert": _load_convert,
    "mask_logic": _mask_logic,
    "mask_pointer_load": _mask_pointer_load,
    "mask_result": _mask_result,
    "mask_store": _mask_store,
    "mask_to_vector": _mask_to_vector,
    "masked": _masked,
    "masked_pointer_load": _masked_pointer_load,
    "masked_pointer_store": _masked_pointer_store,
    "memory_copy": _memory_copy,
    "pointer_free": _pointer_free,
    "pointer_lifetime": _pointer_lifetime,
    "reduction": _reduction,
    "repr_cast": _repr_cast,
    "scalar_pointer_load": _scalar_pointer_load,
    "scalar_result": _scalar_result,
    "scalar_vector": _scalar_vector,
    "store": _store,
    "stream": _stream,
    "vector_to_array": _vector_to_array,
}


def render_cpp_case(case: ValueTestCasePlan) -> str:
    renderer = CPP_CASE_RENDERERS.get(case.kind)
    if renderer is None:
        raise ValueError(f"unsupported C++ value-test case kind {case.kind!r}")
    return renderer(case)


__all__ = ("CPP_CASE_RENDERERS", "render_cpp_case")
