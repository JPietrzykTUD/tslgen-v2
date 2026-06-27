"""Memory-oriented value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_memory import (
    indexed_load_case,
    indexed_store_case,
    mask_store_case,
    pointer_free_case,
    pointer_lifetime_case,
)
from tslc.value_tests._case_scalable_memory import scalable_mask_store_cases
from tslc.value_tests._pattern_base import (
    _BasePattern,
    PointerLayoutCasePlanBuilder,
)
from tslc.value_tests.model import ValueTestCasePlan

@dataclass(frozen=True, slots=True)
class _PointerLayoutShapePattern(_BasePattern):
    build_case: PointerLayoutCasePlanBuilder
    result_kind: str
    param_kinds: tuple[str, ...]
    allow_axis: bool = False
    allow_generic_params: bool = False

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        if spec.result_kind != self.result_kind or tuple(spec.param_kinds) != self.param_kinds:
            return False
        if spec.target is not None or spec.mask_policy is not None:
            return False
        if spec.immediate is not None or spec.type_params:
            return False
        if spec.generic_params and not self.allow_generic_params:
            return False
        if not self.allow_axis and spec.axis:
            return False
        return self.allow_axis or not spec.axis

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        specs = kwargs["specs"]
        primitive = self.source_primitive(
            kwargs["catalog"],
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return ()
        plan = self.build_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            specs,
            primitive,
        )
        return (plan,) if plan is not None else ()


class _MaskStorePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "void"
            and tuple(spec.param_kinds) == ("ptr", "m")
            and spec.target is None
            and spec.mask_policy is None
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        specs = kwargs["specs"]
        primitive = self.source_primitive(
            kwargs["catalog"],
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return ()
        plan = mask_store_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            specs,
            primitive,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_mask_store_cases(
                kwargs["emitted_name"],
                kwargs["index"],
                kwargs["case"],
                specs,
                kwargs["catalog"],
                kwargs["harness"],
                kwargs["backend"],
                primitive,
            )
        )
        return tuple(plans)

class _PointerFreePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return spec.result_kind == "void" and tuple(spec.param_kinds) == ("ptr",)

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = pointer_free_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()

class _PointerLifetimePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return spec.result_kind == "ptr" and all(kind == "usize" for kind in spec.param_kinds)

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = pointer_lifetime_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()

@dataclass(frozen=True, slots=True)
class _IndexedMemoryPattern(_BasePattern):
    result_kind: str

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == self.result_kind
            and "vidx" in spec.param_kinds
            and spec.immediate is not None
            and spec.target is None
        )

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        if spec.mask_policy is not None:
            for primitive in catalog.primitives_named(source_name, unmasked=False):
                if primitive.attributes.get("mask") == spec.mask_policy:
                    return primitive
        return super().source_primitive(catalog, source_name, spec)

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        build = indexed_load_case if self.result_kind == "v" else indexed_store_case
        plan = build(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()

__all__ = (
    "_PointerLayoutShapePattern",
    "_MaskStorePattern",
    "_PointerFreePattern",
    "_PointerLifetimePattern",
    "_IndexedMemoryPattern",
)
