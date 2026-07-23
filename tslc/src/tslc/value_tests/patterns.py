"""Typed value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests._case_core import (
    array_to_vector_case,
    broadcast_case,
    lane_list_case,
    mask_result_case,
    reduction_case,
    scalar_result_case,
    scalar_vector_case,
    status_pointer_case,
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
from tslc.value_tests._pattern_base import CasePlanBuilder, ValueTestPattern
from tslc.value_tests._pattern_conversion import (
    _ConvertPattern,
    _ExtensionReprPattern,
    _ExtensionResultPattern,
    _LoadConvertPattern,
    _ReprCastPattern,
    _TargetImaskPattern,
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


@dataclass(frozen=True, slots=True)
class SimpleValueTestShapeCapability:
    build_case: CasePlanBuilder
    result_kind: str
    param_kinds: tuple[str, ...]
    allow_axis: bool = False
    allow_generic_params: bool = False
    differential: bool = False

    def pattern(self, support: SupportPolicy) -> _SimpleShapePattern:
        kinds = {self.result_kind, *self.param_kinds}
        unsupported = support.signature_kinds.unsupported_kinds(kinds)
        if unsupported:
            raise ValueError(
                "value-test shape uses unsupported signature kinds: "
                + ", ".join(sorted(unsupported))
            )
        return _SimpleShapePattern(
            self.build_case,
            self.result_kind,
            self.param_kinds,
            allow_axis=self.allow_axis,
            allow_generic_params=self.allow_generic_params,
            differential=self.differential,
        )


def _simple(
    build_case: CasePlanBuilder,
    result_kind: str,
    param_kinds: tuple[str, ...],
    *,
    support: SupportPolicy,
    allow_axis: bool = False,
    allow_generic_params: bool = False,
    differential: bool = False,
) -> _SimpleShapePattern:
    return SimpleValueTestShapeCapability(
        build_case,
        result_kind,
        param_kinds,
        allow_axis=allow_axis,
        allow_generic_params=allow_generic_params,
        differential=differential,
    ).pattern(support)


def default_value_test_patterns(
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[ValueTestPattern, ...]:
    return (
        _GenericGoldenPattern(),
        _VectorConstantPattern(),
        _MaskedPattern(),
        _MaskedMaskResultPattern(),
        _simple(store_case, "void", ("ptr", "v"), support=support, allow_axis=True),
        _simple(
            masked_pointer_store_case,
            "void",
            ("m", "ptr", "v"),
            support=support,
            allow_axis=True,
        ),
        _simple(memory_copy_case, "void", ("ptr", "cptr", "s", "s"), support=support),
        _PointerFreePattern(),
        _simple(status_pointer_case, "usize", ("ptr",), support=support),
        _simple(scalar_pointer_load_case, "s", ("cptr",), support=support, allow_axis=True),
        _simple(reduction_case, "s", ("v",), support=support),
        _IndexedScalarPattern(),
        _simple(
            scalar_result_case,
            "s",
            ("v", "usize"),
            support=support,
            differential=True,
        ),
        _simple(scalar_result_case, "s", ("m",), support=support),
        _simple(scalar_result_case, "s", ("s",), support=support),
        _simple(scalar_result_case, "s", ("v", "s"), support=support),
        _simple(scalar_result_case, "usize", ("m",), support=support),
        _simple(scalar_result_case, "usize", ("s",), support=support),
        _MaskConversionPattern(scalar_result_case, "im", ("m",)),
        _TargetImaskPattern(),
        _simple(
            scalar_result_case,
            "im",
            ("im", "s"),
            support=support,
            allow_generic_params=True,
        ),
        _simple(
            scalar_result_case,
            "im",
            ("im", "usize"),
            support=support,
            allow_generic_params=True,
        ),
        _simple(scalar_result_case, "im", ("im", "im"), support=support),
        _simple(
            scalar_result_case,
            "im",
            ("im", "im", "usize"),
            support=support,
        ),
        _simple(scalar_result_case, "im", ("im", "im", "im"), support=support),
        _simple(load_case, "v", ("cptr",), support=support, allow_axis=True),
        _LoadConvertPattern(),
        _simple(
            masked_pointer_load_case,
            "v",
            ("m", "cptr"),
            support=support,
            allow_axis=True,
        ),
        _simple(array_to_vector_case, "v", ("s[]",), support=support),
        _MaskLogicPattern(),
        _MaskConstantPattern(),
        _MaskConversionPattern(mask_result_case, "m", ("im",)),
        _simple(mask_result_case, "m", ("m", "v"), support=support),
        _simple(
            mask_result_case,
            "m",
            ("m", "usize", "im"),
            support=support,
            differential=True,
        ),
        _PointerLayoutShapePattern(mask_pointer_load_case, "m", ("cptr",), allow_axis=True),
        _simple(vector_to_array_case, "s[]", ("v",), support=support),
        _simple(broadcast_case, "v", ("s",), support=support),
        _simple(scalar_vector_case, "v", ("s", "s"), support=support),
        _simple(
            scalar_vector_case,
            "v",
            ("v", "s"),
            support=support,
            allow_generic_params=True,
        ),
        _simple(
            scalar_vector_case,
            "v",
            ("v", "usize", "s"),
            support=support,
            differential=True,
        ),
        _MaskedScalarVectorPattern(),
        _simple(lane_list_case, "v", (support.lane_list_kind,), support=support),
        _ImmediatePattern(support),
        _MaskToVectorPattern(),
        _MaskStorePattern(),
        _IndexedMemoryPattern(result_kind="v"),
        _IndexedMemoryPattern(result_kind="void"),
        _PointerLifetimePattern(),
        _simple(stream_case, "o", ("o", "v", "s"), support=support),
        _ConvertPattern(support),
        _ReprCastPattern(),
        _ExtensionResultPattern(),
        _ExtensionReprPattern(support),
    )


__all__ = (
    "SimpleValueTestShapeCapability",
    "ValueTestPattern",
    "default_value_test_patterns",
)
