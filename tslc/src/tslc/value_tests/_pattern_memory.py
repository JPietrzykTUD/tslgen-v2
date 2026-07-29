"""Memory-oriented value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.scalar_types import normalize_scalar_tag
from tslc.catalog.signatures import parse_signature
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_memory import (
    indexed_load_case,
    indexed_store_case,
    mask_store_case,
    masked_pointer_load_case,
    masked_pointer_store_case,
    pointer_free_case,
    pointer_lifetime_case,
)
from tslc.value_tests._case_scalable_memory import (
    scalable_mask_store_cases,
    scalable_masked_pointer_load_cases,
    scalable_masked_pointer_store_cases,
)
from tslc.value_tests._pattern_base import (
    _BasePattern,
    PointerLayoutCasePlanBuilder,
    ValueTestCaseContext,
)
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.param_layouts import unsupported_param_layout_reason


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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        specs = context.specs
        primitive = self.source_primitive(
            context.catalog,
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return ()
        plan = self.build_case(
            context.emitted_name,
            context.index,
            context.case,
            specs,
            primitive,
        )
        return (plan,) if plan is not None else ()

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        specs = context.specs
        primitive = self.source_primitive(
            context.catalog,
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return None
        return unsupported_param_layout_reason(primitive, "ptr", context.case, specs)


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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        specs = context.specs
        primitive = self.source_primitive(
            context.catalog,
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return ()
        plan = mask_store_case(
            context.emitted_name,
            context.index,
            context.case,
            specs,
            primitive,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_mask_store_cases(
                context.emitted_name,
                context.index,
                context.case,
                specs,
                context.catalog,
                context.harness,
                context.backend,
                primitive,
            )
        )
        return tuple(plans)

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        specs = context.specs
        primitive = self.source_primitive(
            context.catalog,
            specs[0].source_primitive_name,
            specs[0],
        )
        if primitive is None:
            return None
        return unsupported_param_layout_reason(primitive, "ptr", context.case, specs)


def _masked_source_primitive(
    catalog: Catalog,
    source_name: str,
    spec: LoweredSpecialization,
) -> Primitive | None:
    for primitive in catalog.primitives_named(source_name, unmasked=False):
        shape = parse_signature(primitive.signature)
        if (
            primitive.attributes.get("mask") == spec.mask_policy
            and shape is not None
            and shape.result_kind == spec.result_kind
            and shape.param_kinds == spec.param_kinds
        ):
            return primitive
    return None


class _MaskedPointerLoadPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and tuple(spec.param_kinds) in {
                ("m", "cptr"),
                ("m", "cptr", "v"),
            }
            and spec.mask_policy in {"zero", "pass_through"}
            and spec.target is None
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
        return _masked_source_primitive(catalog, source_name, spec)

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = masked_pointer_load_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_masked_pointer_load_cases(
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


class _MaskedPointerStorePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "void"
            and tuple(spec.param_kinds) == ("m", "ptr", "v")
            and spec.mask_policy == "pass_through"
            and spec.target is None
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
        return _masked_source_primitive(catalog, source_name, spec)

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = masked_pointer_store_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_masked_pointer_store_cases(
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


class _PointerFreePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return spec.result_kind == "void" and tuple(spec.param_kinds) == ("ptr",)

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = pointer_free_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        return (plan,) if plan is not None else ()


class _PointerLifetimePattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return spec.result_kind == "ptr" and all(kind == "usize" for kind in spec.param_kinds)

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = pointer_lifetime_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _IndexedMemoryPattern(_BasePattern):
    result_kind: str

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == self.result_kind
            and (
                "vidx" in spec.param_kinds
                or tuple(spec.param_kinds) == ("cptr", "cptr", "sImm")
            )
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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        build = indexed_load_case if self.result_kind == "v" else indexed_store_case
        index_base_spelling = _index_base_spelling(
            context.catalog,
            context.backend.backend_id,
            context.case.index_type,
        )
        plan = build(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
            index_base_spelling,
        )
        return (plan,) if plan is not None else ()


def _index_base_spelling(
    catalog: Catalog,
    backend_id: str,
    type_tag: str | None,
) -> str | None:
    if type_tag is None:
        return None
    return catalog.type_spellings.get(backend_id, {}).get(normalize_scalar_tag(type_tag))

__all__ = (
    "_PointerLayoutShapePattern",
    "_MaskStorePattern",
    "_MaskedPointerLoadPattern",
    "_MaskedPointerStorePattern",
    "_PointerFreePattern",
    "_PointerLifetimePattern",
    "_IndexedMemoryPattern",
)
