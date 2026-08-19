"""Mask-specific value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive, PrimitiveMaskMode
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_core import (
    mask_logic_case,
    masked_mask_result_case,
    mask_result_case,
    mask_to_vector_case,
)
from tslc.value_tests._case_scalable import scalable_masked_cases
from tslc.value_tests._case_scalable_masks import (
    scalable_mask_constant_cases,
    scalable_mask_conversion_cases,
    scalable_mask_logic_cases,
    scalable_masked_mask_result_cases,
)
from tslc.value_tests._pattern_base import (
    _BasePattern,
    CasePlanBuilder,
    ValueTestCaseContext,
)
from tslc.value_tests.model import ValueTestCasePlan


class _MaskedMaskResultPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "m"
            and spec.mask_policy in (PrimitiveMaskMode.ZERO, PrimitiveMaskMode.PASS_THROUGH)
            and spec.param_kinds.count("m") == 1
            and all(kind in ("m", "v") for kind in spec.param_kinds)
            and spec.target is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        for primitive in catalog.primitives_named(source_name, unmasked=False):
            if primitive.mask_mode == spec.mask_policy:
                return primitive
        return None

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = masked_mask_result_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_masked_mask_result_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        return tuple(plans)


class _MaskLogicPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "m"
            and len(spec.param_kinds) >= 1
            and all(kind == "m" for kind in spec.param_kinds)
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = mask_logic_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_mask_logic_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        return tuple(plans)


class _MaskConstantPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "m"
            and not spec.param_kinds
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = mask_result_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_mask_constant_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        return tuple(plans)


@dataclass(frozen=True, slots=True)
class _MaskConversionPattern(_BasePattern):
    fixed_case_builder: CasePlanBuilder
    result_kind: str
    param_kinds: tuple[str, ...]

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == self.result_kind
            and spec.param_kinds == self.param_kinds
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = self.fixed_case_builder(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_mask_conversion_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        return tuple(plans)


class _MaskToVectorPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and spec.param_kinds == ("m",)
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = mask_to_vector_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_masked_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        return tuple(plans)


__all__ = (
    "_MaskConstantPattern",
    "_MaskConversionPattern",
    "_MaskLogicPattern",
    "_MaskToVectorPattern",
    "_MaskedMaskResultPattern",
)
