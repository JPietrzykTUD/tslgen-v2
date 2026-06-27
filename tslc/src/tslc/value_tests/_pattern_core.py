"""Core value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import SupportPolicy
from tslc.value_tests._case_conversion import differential_cases, differential_fuzz_cases
from tslc.value_tests._case_core import (
    generic_golden_case,
    immediate_case,
    masked_case,
    scalar_result_case,
    scalar_vector_case,
)
from tslc.value_tests._case_scalable import (
    scalable_golden_cases,
    scalable_masked_cases,
)
from tslc.value_tests._case_scalable_masks import scalable_mask_result_cases
from tslc.value_tests._pattern_base import _BasePattern, CasePlanBuilder
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
)

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
        plans.extend(
            scalable_golden_cases(
                emitted_name,
                index,
                case,
                specs,
                catalog,
                harness,
                backend,
            )
        )
        plans.extend(
            scalable_mask_result_cases(
                emitted_name,
                index,
                case,
                specs,
                catalog,
                harness,
                backend,
            )
        )
        if backend.supports_differential and harness.round_trip_ready:
            plans.extend(differential_cases(emitted_name, index, case, specs, catalog, harness))
        return tuple(plans)

    def fuzz_cases(
        self,
        *,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        specs: tuple[LoweredSpecialization, ...],
        catalog: Catalog,
        harness: HarnessPrimitiveNames,
        iterations: int,
    ) -> tuple[ValueTestCasePlan, ...]:
        """Random-input differential cases for this primitive — independent of authored tests, so
        even an untested all-vector primitive gets a runtime hardware-vs-generic sweep."""

        if not (backend.supports_differential and harness.round_trip_ready):
            return ()
        return tuple(
            differential_fuzz_cases(emitted_name, specs, catalog, harness, iterations)
        )

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
        plan = masked_case(
            emitted_name,
            index,
            case,
            specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_masked_cases(
                emitted_name,
                index,
                case,
                specs,
                catalog,
                harness,
                backend,
            )
        )
        return tuple(plans)


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
        return bool(self._matching_specs(specs))

    def plan_case(self, **kwargs) -> tuple[ValueTestCasePlan, ...]:  # noqa: ANN003
        specs = self._matching_specs(kwargs["specs"])
        if not specs:
            return ()
        plan = self.build_case(
            kwargs["emitted_name"],
            kwargs["index"],
            kwargs["case"],
            specs,
        )
        return (plan,) if plan is not None else ()

    def _matching_specs(
        self,
        specs: tuple[LoweredSpecialization, ...],
    ) -> tuple[LoweredSpecialization, ...]:
        return tuple(spec for spec in specs if self._matches_spec(spec))

    def _matches_spec(self, spec: LoweredSpecialization) -> bool:
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

__all__ = (
    "_GenericGoldenPattern",
    "_MaskedPattern",
    "_VectorConstantPattern",
    "_SimpleShapePattern",
    "_IndexedScalarPattern",
    "_MaskedScalarVectorPattern",
    "_ImmediatePattern",
)
