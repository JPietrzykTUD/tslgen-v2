"""Typed value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests.case_plans import (
    convert_case,
    differential_cases,
    extension_harness_available,
    extension_repr_case,
    generic_golden_case,
    immediate_case,
    masked_case,
    repr_cast_case,
    simple_case,
)
from tslc.value_tests.model import HarnessPrimitiveNames, ValueTestCasePlan


class ValueTestPattern(Protocol):
    """A typed test-shape planner."""

    backend_ids: frozenset[str]

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
        backend_id: str,
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
        _MaskedPattern(),
        _SimpleShapePattern("store", "void", ("ptr", "v"), allow_axis=True),
        _SimpleShapePattern("reduction", "s", ("v",)),
        _SimpleShapePattern("load", "v", ("ptr",), allow_axis=True),
        _MaskLogicPattern(),
        _SimpleShapePattern("vector_to_array", "s[]", ("v",)),
        _SimpleShapePattern("broadcast", "v", ("s",)),
        _ImmediatePattern(support),
        _SimpleShapePattern("mask_to_vector", "v", ("m",)),
        _ConvertPattern(support),
        _ReprCastPattern(),
        _ExtensionReprPattern(support),
    )


class _BasePattern:
    backend_ids = frozenset({"cpp", "rust"})

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
        backend_id: str,
        emitted_name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        catalog: Catalog,
        harness: HarnessPrimitiveNames,
    ) -> tuple[ValueTestCasePlan, ...]:
        plan = generic_golden_case(backend_id, emitted_name, index, case, specs)
        if plan is None:
            return ()
        plans = [plan]
        if backend_id == "cpp" and harness.round_trip_ready:
            plans.extend(differential_cases(emitted_name, index, case, specs, catalog, harness))
        return tuple(plans)


class _MaskedPattern(_BasePattern):
    backend_ids = frozenset({"cpp"})

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


@dataclass(frozen=True, slots=True)
class _SimpleShapePattern(_BasePattern):
    kind: str
    result_kind: str
    param_kinds: tuple[str, ...]
    backend_ids: frozenset[str] = frozenset({"cpp"})
    allow_axis: bool = False

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        if spec.result_kind != self.result_kind or tuple(spec.param_kinds) != self.param_kinds:
            return False
        if spec.target is not None or spec.mask_policy is not None:
            return False
        if spec.immediate is not None or spec.generic_params or spec.type_params:
            return False
        if not self.allow_axis and spec.axis:
            return False
        return self.allow_axis or not spec.axis

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        plan = simple_case(
            self.kind,
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


class _MaskLogicPattern(_BasePattern):
    backend_ids = frozenset({"cpp"})

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
        plan = simple_case(
            "mask_logic",
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            kwargs["specs"],
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _ImmediatePattern(_BasePattern):
    support: SupportPolicy
    backend_ids = frozenset({"cpp"})

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
            and spec.uses_sized_vector
            and spec.target is not None
            and spec.target.uses_sized_vector
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
        )
        return (plan,) if plan is not None else ()


@dataclass(frozen=True, slots=True)
class _ExtensionReprPattern(_BasePattern):
    support: SupportPolicy
    backend_ids = frozenset({"cpp"})

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
