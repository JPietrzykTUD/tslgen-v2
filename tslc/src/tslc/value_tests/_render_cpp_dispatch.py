"""Dispatch C++ value-test cases to focused renderers."""

from __future__ import annotations

from tslc.value_tests.lane_model import (
    render_mask_case,
    render_mask_conversion,
    render_value_case,
)
from tslc.value_tests.model import (
    ValueTestCasePlan,
)
from tslc.value_tests._render_cpp_core import (
    _array_to_vector,
    _broadcast,
    _compile_only,
    _immediate,
    _lane_list,
    _mask_to_vector,
    _reduction,
    _runtime_failure,
    _scalable_mask_count,
    _scalable_runtime_failure,
    _scalar_result,
    _scalar_vector,
    _status_pointer,
    _vector_to_array,
)
from tslc.value_tests._render_cpp_conversion import (
    _convert,
    _differential,
    _differential_fuzz,
    _extension_extract,
    _extension_insert,
    _extension_result,
    _load_convert,
    _lane_convert,
    _repr_cast,
    _scalable_repr_cast,
    _target_imask,
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
    _scalable_mask_store,
    _scalable_masked_pointer_load,
    _scalable_masked_pointer_store,
    _scalar_pointer_load,
    _store,
    _stream,
)
from tslc.value_tests.renderer_capability import ValueTestRendererCapability

# Every value-result case (golden/masked) and every mask-result case (comparison, mask logic,
# masked comparison, mask constant) — fixed or scalable — shares the lane-model renderers; the
# lane model picked from the case data supplies the only parts that differ.
CPP_VALUE_TEST_RENDERER = ValueTestRendererCapability(
    backend_id="cpp",
    supports_differential=True,
    isolated_case_kinds=frozenset({"compile_failure"}),
    unobservable_runtime_failure_reason=(
        "the generated C++ toolchain does not provide the exception unwinding "
        "required to observe the runtime-failure marker"
    ),
    case_renderers={
        "array_to_vector": _array_to_vector,
        "broadcast": _broadcast,
        "compile_only": _compile_only,
        "convert": _convert,
        "differential": _differential,
        "differential_fuzz": _differential_fuzz,
        "extension_extract": _extension_extract,
        "extension_insert": _extension_insert,
        "extension_result": _extension_result,
        "generic_golden": render_value_case,
        "immediate": _immediate,
        "indexed_load": _indexed_load,
        "indexed_store": _indexed_store,
        "lane_list": _lane_list,
        "load": _load,
        "load_convert": _load_convert,
        "lane_convert": _lane_convert,
        "mask_logic": render_mask_case,
        "mask_pointer_load": _mask_pointer_load,
        "mask_result": render_mask_case,
        "mask_store": _mask_store,
        "mask_to_vector": _mask_to_vector,
        "masked": render_value_case,
        "masked_pointer_load": _masked_pointer_load,
        "masked_pointer_store": _masked_pointer_store,
        "memory_copy": _memory_copy,
        "pointer_free": _pointer_free,
        "pointer_lifetime": _pointer_lifetime,
        "reduction": _reduction,
        "runtime_failure": _runtime_failure,
        "repr_cast": _repr_cast,
        "scalar_pointer_load": _scalar_pointer_load,
        "scalar_result": _scalar_result,
        "scalar_vector": _scalar_vector,
        "scalable_golden": render_value_case,
        "scalable_immediate": render_value_case,
        "scalable_repr_cast": _scalable_repr_cast,
        "scalable_scalar_vector": render_value_case,
        "scalable_mask_constant": render_mask_case,
        "scalable_mask_conversion": render_mask_conversion,
        "scalable_mask_count": _scalable_mask_count,
        "scalable_mask_logic": render_mask_case,
        "scalable_mask_result": render_mask_case,
        "scalable_runtime_failure": _scalable_runtime_failure,
        "scalable_mask_store": _scalable_mask_store,
        "scalable_masked_pointer_load": _scalable_masked_pointer_load,
        "scalable_masked_pointer_store": _scalable_masked_pointer_store,
        "scalable_masked_mask_result": render_mask_case,
        "scalable_masked": render_value_case,
        "scalable_masked_immediate": render_value_case,
        "store": _store,
        "target_imask": _target_imask,
        "status_pointer": _status_pointer,
        "stream": _stream,
        "vector_to_array": _vector_to_array,
    },
)


def render_cpp_case(case: ValueTestCasePlan) -> str:
    return CPP_VALUE_TEST_RENDERER.render_case(case)


__all__ = ("CPP_VALUE_TEST_RENDERER", "render_cpp_case")
