"""Typed value-test shape patterns."""

from __future__ import annotations

from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests._case_core import (
    array_to_vector_case,
    broadcast_case,
    lane_list_case,
    mask_result_case,
    reduction_case,
    scalar_result_case,
    scalar_vector_case,
    vector_to_array_case,
)
from tslc.value_tests._case_memory import (
    load_case,
    mask_pointer_load_case,
    masked_pointer_load_case,
    masked_pointer_store_case,
    memory_copy_case,
    scalar_pointer_load_case,
    store_case,
    stream_case,
)
from tslc.value_tests._pattern_base import ValueTestPattern
from tslc.value_tests._pattern_conversion import (
    _ConvertPattern,
    _ExtensionReprPattern,
    _LoadConvertPattern,
    _ReprCastPattern,
)
from tslc.value_tests._pattern_core import (
    _GenericGoldenPattern,
    _ImmediatePattern,
    _IndexedScalarPattern,
    _MaskedPattern,
    _MaskedScalarVectorPattern,
    _SimpleShapePattern,
    _VectorConstantPattern,
)
from tslc.value_tests._pattern_masks import (
    _MaskConstantPattern,
    _MaskConversionPattern,
    _MaskLogicPattern,
    _MaskToVectorPattern,
    _MaskedMaskResultPattern,
)
from tslc.value_tests._pattern_memory import (
    _IndexedMemoryPattern,
    _MaskStorePattern,
    _PointerFreePattern,
    _PointerLayoutShapePattern,
    _PointerLifetimePattern,
)


def default_value_test_patterns(
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[ValueTestPattern, ...]:
    return (
        _GenericGoldenPattern(),
        _VectorConstantPattern(),
        _MaskedPattern(),
        _MaskedMaskResultPattern(),
        _SimpleShapePattern(store_case, "void", ("ptr", "v"), allow_axis=True),
        _SimpleShapePattern(masked_pointer_store_case, "void", ("m", "ptr", "v"), allow_axis=True),
        _SimpleShapePattern(memory_copy_case, "void", ("ptr", "cptr", "s", "s")),
        _PointerFreePattern(),
        _SimpleShapePattern(scalar_pointer_load_case, "s", ("cptr",), allow_axis=True),
        _SimpleShapePattern(reduction_case, "s", ("v",)),
        _IndexedScalarPattern(),
        _SimpleShapePattern(scalar_result_case, "s", ("m",)),
        _SimpleShapePattern(scalar_result_case, "s", ("s",)),
        _SimpleShapePattern(scalar_result_case, "s", ("v", "s")),
        _SimpleShapePattern(scalar_result_case, "usize", ("m",)),
        _MaskConversionPattern(scalar_result_case, "im", ("m",)),
        _SimpleShapePattern(
            scalar_result_case,
            "im",
            ("im", "s"),
            allow_generic_params=True,
        ),
        _SimpleShapePattern(scalar_result_case, "im", ("im", "im")),
        _SimpleShapePattern(scalar_result_case, "im", ("im", "im", "im")),
        _SimpleShapePattern(load_case, "v", ("cptr",), allow_axis=True),
        _LoadConvertPattern(),
        _SimpleShapePattern(masked_pointer_load_case, "v", ("m", "cptr"), allow_axis=True),
        _SimpleShapePattern(array_to_vector_case, "v", ("s[]",)),
        _MaskLogicPattern(),
        _MaskConstantPattern(),
        _MaskConversionPattern(mask_result_case, "m", ("im",)),
        _SimpleShapePattern(mask_result_case, "m", ("m", "v")),
        _PointerLayoutShapePattern(mask_pointer_load_case, "m", ("cptr",), allow_axis=True),
        _SimpleShapePattern(vector_to_array_case, "s[]", ("v",)),
        _SimpleShapePattern(broadcast_case, "v", ("s",)),
        _SimpleShapePattern(scalar_vector_case, "v", ("s", "s")),
        _MaskedScalarVectorPattern(),
        _SimpleShapePattern(lane_list_case, "v", (support.lane_list_kind,)),
        _ImmediatePattern(support),
        _MaskToVectorPattern(),
        _MaskStorePattern(),
        _IndexedMemoryPattern(result_kind="v"),
        _IndexedMemoryPattern(result_kind="void"),
        _PointerLifetimePattern(),
        _SimpleShapePattern(stream_case, "o", ("o", "v", "s")),
        _ConvertPattern(support),
        _ReprCastPattern(),
        _ExtensionReprPattern(support),
    )


__all__ = ("ValueTestPattern", "default_value_test_patterns")
