"""Typed value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests.case_plans import (
    array_to_vector_case,
    broadcast_case,
    convert_case,
    differential_cases,
    extension_harness_available,
    extension_repr_case,
    generic_golden_case,
    immediate_case,
    indexed_load_case,
    indexed_store_case,
    lane_list_case,
    load_convert_case,
    load_case,
    mask_pointer_load_case,
    mask_logic_case,
    mask_result_case,
    mask_store_case,
    mask_to_vector_case,
    masked_case,
    masked_pointer_load_case,
    masked_pointer_store_case,
    memory_copy_case,
    pointer_free_case,
    pointer_lifetime_case,
    repr_cast_case,
    reduction_case,
    scalar_pointer_load_case,
    scalar_result_case,
    scalar_vector_case,
    store_case,
    stream_case,
    vector_to_array_case,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
)


class CasePlanBuilder(Protocol):
    def __call__(
        self,
        name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
    ) -> ValueTestCasePlan | None:
        ...


class ValueTestPattern(Protocol):
    """A typed test-shape planner."""

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        ...

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        ...

    def plan_case(
        self,
        *,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        catalog: Catalog,
        harness: HarnessPrimitiveNames,
    ) -> tuple[ValueTestCasePlan, ...]:
        ...


def default_value_test_patterns(
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[ValueTestPattern, ...]:
    return (
        _GenericGoldenPattern(),
        _VectorConstantPattern(),
        _MaskedPattern(),
        _SimpleShapePattern(store_case, "void", ("ptr", "v"), allow_axis=True),
        _SimpleShapePattern(masked_pointer_store_case, "void", ("m", "ptr", "v"), allow_axis=True),
        _SimpleShapePattern(memory_copy_case, "void", ("ptr", "ptr", "s", "s")),
        _PointerFreePattern(),
        _SimpleShapePattern(scalar_pointer_load_case, "s", ("ptr",), allow_axis=True),
        _SimpleShapePattern(reduction_case, "s", ("v",)),
        _IndexedScalarPattern(),
        _SimpleShapePattern(scalar_result_case, "s", ("m",)),
        _SimpleShapePattern(scalar_result_case, "s", ("s",)),
        _SimpleShapePattern(scalar_result_case, "s", ("v", "s")),
        _SimpleShapePattern(scalar_result_case, "usize", ("m",)),
        _SimpleShapePattern(scalar_result_case, "im", ("m",)),
        _SimpleShapePattern(
            scalar_result_case,
            "im",
            ("im", "s"),
            allow_generic_params=True,
        ),
        _SimpleShapePattern(scalar_result_case, "im", ("im", "im")),
        _SimpleShapePattern(scalar_result_case, "im", ("im", "im", "im")),
        _SimpleShapePattern(load_case, "v", ("ptr",), allow_axis=True),
        _LoadConvertPattern(),
        _SimpleShapePattern(masked_pointer_load_case, "v", ("m", "ptr"), allow_axis=True),
        _SimpleShapePattern(array_to_vector_case, "v", ("s[]",)),
        _MaskLogicPattern(),
        _SimpleShapePattern(mask_result_case, "m", ()),
        _SimpleShapePattern(mask_result_case, "m", ("im",)),
        _SimpleShapePattern(mask_result_case, "m", ("m", "v")),
        _SimpleShapePattern(mask_pointer_load_case, "m", ("ptr",), allow_axis=True),
        _SimpleShapePattern(vector_to_array_case, "s[]", ("v",)),
        _SimpleShapePattern(broadcast_case, "v", ("s",)),
        _SimpleShapePattern(scalar_vector_case, "v", ("s", "s")),
        _MaskedScalarVectorPattern(),
        _SimpleShapePattern(lane_list_case, "v", (support.lane_list_kind,)),
        _ImmediatePattern(support),
        _SimpleShapePattern(mask_to_vector_case, "v", ("m",)),
        _SimpleShapePattern(mask_store_case, "void", ("ptr", "m"), allow_axis=True),
        _IndexedMemoryPattern(result_kind="v"),
        _IndexedMemoryPattern(result_kind="void"),
        _PointerLifetimePattern(),
        _SimpleShapePattern(stream_case, "o", ("o", "v", "s")),
        _ConvertPattern(support),
        _ReprCastPattern(),
        _ExtensionReprPattern(support),
    )


class _BasePattern:
    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        return catalog.primitive(source_name, unmasked=True)


class _GenericGoldenPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind in ("v", "m")
            and bool(spec.param_kinds)
            and all(kind == "v" for kind in spec.param_kinds)
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(
        self,
        *,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        catalog: Catalog,
        harness: HarnessPrimitiveNames,
    ) -> tuple[ValueTestCasePlan, ...]:
        plan = generic_golden_case(emitted_name, index, case, specs)
        if plan is None:
            return ()
        plans = [plan]
        if backend.supports_differential and harness.round_trip_ready:
            plans.extend(differential_cases(emitted_name, index, case, specs, catalog, harness))
        return tuple(plans)


class _MaskedPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and spec.mask_policy in ("zero", "pass_through")
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
            if primitive.attributes.get("mask") == spec.mask_policy:
                return primitive
        return None

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = masked_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


class _VectorConstantPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and not spec.param_kinds
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = generic_golden_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _SimpleShapePattern(_BasePattern):
    build_case: CasePlanBuilder
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
        plan = self.build_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


class _IndexedScalarPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "s"
            and tuple(spec.param_kinds) == ("v",)
            and spec.target is None
            and spec.mask_policy is None
            and spec.immediate is None
            and bool(spec.generic_params)
            and not spec.type_params
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = scalar_result_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


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

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = mask_logic_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


class _MaskedScalarVectorPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and tuple(spec.param_kinds) == ("m", "v", "s")
            and spec.target is None
            and spec.mask_policy in {"zero", "pass_through"}
            and spec.immediate is None
            and not spec.axis
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
            if primitive.attributes.get("mask") == spec.mask_policy:
                return primitive
        return None

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = scalar_vector_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


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


class _LoadConvertPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return any(
            spec.result_kind == "v"
            and spec.target is not None
            and tuple(spec.param_kinds) == ("ptr+",)
            for spec in specs
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = load_convert_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
            kwargs["harness"],
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


@dataclass(frozen=True, slots=True)
class _ImmediatePattern(_BasePattern):
    support: SupportPolicy

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and spec.immediate is not None
            and self.support.immediate_kind in spec.param_kinds
            and all(kind in ("v", self.support.immediate_kind) for kind in spec.param_kinds)
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and not spec.type_params
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = immediate_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _ConvertPattern(_BasePattern):
    support: SupportPolicy

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return any(
            spec.result_kind == "v"
            and spec.target is not None
            and spec.target.uses_sized_vector
            and spec.immediate is not None
            and tuple(spec.param_kinds) == ("v", self.support.immediate_kind)
            for spec in specs
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = convert_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


class _ReprCastPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return any(
            spec.result_kind == "v"
            and spec.target is not None
            and spec.target.base_tag != spec.type_tag
            and spec.immediate is None
            and tuple(spec.param_kinds) == ("v",)
            for spec in specs
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = repr_cast_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
            kwargs["harness"],
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _ExtensionReprPattern(_BasePattern):
    support: SupportPolicy

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return any(
            spec.result_kind == "v"
            and spec.target is not None
            and not spec.target.uses_sized_vector
            and spec.immediate is not None
            and spec.target.base_tag == spec.type_tag
            and self.support.immediate_kind in spec.param_kinds
            for spec in specs
        )

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        harness = kwargs["harness"]
        if not harness.round_trip_ready:
            return ()
        specs = kwargs["specs"]
        case = kwargs["case"]
        if not extension_harness_available(case, specs):
            return ()
        kind = "extension_insert" if "vt" in specs[0].param_kinds else "extension_extract"
        plan = extension_repr_case(kind, kwargs["emitted_name"], kwargs["index"], case, specs, harness)
        return (plan,) if plan is not None else ()


__all__ = ("ValueTestPattern", "default_value_test_patterns")
