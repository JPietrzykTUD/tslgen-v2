"""Core value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive, PrimitiveMaskMode
from tslc.catalog.scalar_types import normalize_scalar_tag
from tslc.catalog.signatures import parse_signature
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
    scalable_immediate_cases,
    scalable_masked_cases,
    scalable_scalar_vector_cases,
)
from tslc.value_tests._case_scalable_masks import (
    scalable_mask_count_cases,
    scalable_mask_result_cases,
)
from tslc.value_tests._pattern_base import (
    _BasePattern,
    CasePlanBuilder,
    ValueTestCaseContext,
    ValueTestFuzzContext,
)
from tslc.value_tests.model import (
    ValueTestCasePlan,
)

class _GenericGoldenPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind in ("v", "m")
            and bool(spec.param_kinds)
            and all(kind in ("v", "vidx") for kind in spec.param_kinds)
            and spec.param_kinds.count("vidx") <= 1
            and spec.target is None
            and spec.mask_policy is None
            and not spec.axis
            and spec.immediate is None
            and (
                not spec.type_params
                or (
                    spec.param_kinds.count("vidx") == 1
                    and len(spec.type_params) == 1
                )
            )
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        index_base_spelling = None
        if "vidx" in context.specs[0].param_kinds and context.case.index_type is not None:
            index_base_spelling = context.catalog.type_spellings.get(
                context.backend.backend_id, {}
            ).get(normalize_scalar_tag(context.case.index_type))
        plan = generic_golden_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
            index_base_spelling,
        )
        if plan is None:
            return ()
        plans = [plan]
        plans.extend(
            scalable_golden_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        plans.extend(
            scalable_mask_result_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        if (
            "vidx" not in context.specs[0].param_kinds
            and context.backend.supports_differential
            and context.harness.round_trip_ready
        ):
            plans.extend(
                differential_cases(
                    context.emitted_name,
                    context.index,
                    context.case,
                    context.specs,
                    context.catalog,
                    context.harness,
                    context.backend.backend_id,
                )
            )
        return tuple(plans)

    def fuzz_cases(self, context: ValueTestFuzzContext) -> tuple[ValueTestCasePlan, ...]:
        """Random-input differential cases for this primitive — independent of authored tests, so
        even an untested all-vector primitive gets a runtime hardware-vs-generic sweep."""

        if (
            "vidx" in context.specs[0].param_kinds
            or not (context.backend.supports_differential and context.harness.round_trip_ready)
        ):
            return ()
        return tuple(
            differential_fuzz_cases(
                context.emitted_name,
                context.specs,
                context.catalog,
                context.harness,
                context.backend.backend_id,
                primitive=context.primitive,
                iterations=context.iterations,
            )
        )

class _MaskedPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and spec.mask_policy in (PrimitiveMaskMode.ZERO, PrimitiveMaskMode.PASS_THROUGH)
            and spec.param_kinds.count("m") == 1
            and all(kind in ("m", "v", "vidx") for kind in spec.param_kinds)
            and spec.param_kinds.count("vidx") <= 1
            and spec.target is None
            and not spec.axis
            and spec.immediate is None
            and not spec.generic_params
            and (
                not spec.type_params
                or (
                    spec.param_kinds.count("vidx") == 1
                    and len(spec.type_params) == 1
                )
            )
        )

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        for primitive in catalog.primitives_named(source_name, unmasked=False):
            shape = parse_signature(primitive.signature)
            if (
                primitive.mask_mode == spec.mask_policy
                and shape is not None
                and shape.result_kind == spec.result_kind
                and shape.param_kinds == spec.param_kinds
            ):
                return primitive
        return None

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        index_base_spelling = None
        if "vidx" in context.specs[0].param_kinds and context.case.index_type is not None:
            index_base_spelling = context.catalog.type_spellings.get(
                context.backend.backend_id, {}
            ).get(normalize_scalar_tag(context.case.index_type))
        plan = masked_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
            index_base_spelling,
        )
        plans = [plan] if plan is not None else []
        if "vidx" not in context.specs[0].param_kinds:
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
            if (
                context.backend.supports_differential
                and context.harness.round_trip_ready
            ):
                plans.extend(
                    differential_cases(
                        context.emitted_name,
                        context.index,
                        context.case,
                        context.specs,
                        context.catalog,
                        context.harness,
                        context.backend.backend_id,
                    )
                )
        return tuple(plans)

    def fuzz_cases(self, context: ValueTestFuzzContext) -> tuple[ValueTestCasePlan, ...]:
        if not (
            context.backend.supports_differential
            and context.harness.round_trip_ready
        ):
            return ()
        return tuple(
            differential_fuzz_cases(
                context.emitted_name,
                context.specs,
                context.catalog,
                context.harness,
                context.backend.backend_id,
                primitive=context.primitive,
                iterations=context.iterations,
            )
        )


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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = generic_golden_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        return (plan,) if plan is not None else ()

@dataclass(frozen=True, slots=True)
class _SimpleShapePattern(_BasePattern):
    build_case: CasePlanBuilder
    result_kind: str
    param_kinds: tuple[str, ...]
    allow_axis: bool = False
    allow_generic_params: bool = False
    differential: bool = False

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return bool(self._matching_specs(specs))

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        specs = self._matching_specs(context.specs)
        if not specs:
            return ()
        plan = self.build_case(
            context.emitted_name,
            context.index,
            context.case,
            specs,
        )
        plans = [plan] if plan is not None else []
        if self.result_kind == "v" and "s" in self.param_kinds:
            plans.extend(
                scalable_scalar_vector_cases(
                    context.emitted_name,
                    context.index,
                    context.case,
                    specs,
                    context.catalog,
                    context.harness,
                    context.backend,
                )
            )
        if (
            self.differential
            and context.backend.supports_differential
            and context.harness.round_trip_ready
        ):
            plans.extend(
                differential_cases(
                    context.emitted_name,
                    context.index,
                    context.case,
                    specs,
                    context.catalog,
                    context.harness,
                    context.backend.backend_id,
                )
            )
        return tuple(plans)

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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = scalar_result_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        return (plan,) if plan is not None else ()


class _MaskCountPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "usize"
            and tuple(spec.param_kinds) == ("m",)
            and spec.target is None
            and spec.mask_policy is None
            and spec.immediate is None
            and not spec.axis
            and not spec.generic_params
            and not spec.type_params
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plans: list[ValueTestCasePlan] = []
        case_extension = (
            context.catalog.extensions.get(context.case.extension)
            if context.case.extension is not None
            else None
        )
        if case_extension is None or case_extension.vector_bits_kind != "scalable":
            fixed = scalar_result_case(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
            )
            if fixed is not None:
                plans.append(fixed)
        plans.extend(
            scalable_mask_count_cases(
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

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        del context
        return (
            "scalable mask-count value tests require expected_rule 'popcnt', "
            "one non-negative mask input, and its matching authored-lane count"
        )


class _MaskedScalarVectorPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and tuple(spec.param_kinds) == ("m", "v", "s")
            and spec.target is None
            and spec.mask_policy in {PrimitiveMaskMode.ZERO, PrimitiveMaskMode.PASS_THROUGH}
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
            if primitive.mask_mode == spec.mask_policy:
                return primitive
        return None

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = scalar_vector_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_scalar_vector_cases(
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
class _ImmediatePattern(_BasePattern):
    support: SupportPolicy

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        spec = specs[0]
        return (
            spec.result_kind == "v"
            and spec.immediate is not None
            and self.support.immediate_kind in spec.param_kinds
            and all(
                kind in ("m", "v", self.support.immediate_kind)
                for kind in spec.param_kinds
            )
            and spec.param_kinds.count("m") <= 1
            and spec.target is None
            and spec.mask_policy in (None, PrimitiveMaskMode.ZERO, PrimitiveMaskMode.PASS_THROUGH)
            and not spec.axis
            and not spec.type_params
        )

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        for primitive in catalog.primitives_named(source_name, unmasked=False):
            shape = parse_signature(primitive.signature)
            if (
                shape is not None
                and shape.result_kind == spec.result_kind
                and shape.param_kinds == spec.param_kinds
                and primitive.mask_mode == spec.mask_policy
            ):
                return primitive
        return None

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = immediate_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
        )
        plans = [plan] if plan is not None else []
        plans.extend(
            scalable_immediate_cases(
                context.emitted_name,
                context.index,
                context.case,
                context.specs,
                context.catalog,
                context.harness,
                context.backend,
            )
        )
        if (
            context.backend.supports_differential
            and context.harness.round_trip_ready
        ):
            plans.extend(
                differential_cases(
                    context.emitted_name,
                    context.index,
                    context.case,
                    context.specs,
                    context.catalog,
                    context.harness,
                    context.backend.backend_id,
                )
            )
        return tuple(plans)

__all__ = (
    "_GenericGoldenPattern",
    "_MaskedPattern",
    "_VectorConstantPattern",
    "_SimpleShapePattern",
    "_IndexedScalarPattern",
    "_MaskCountPattern",
    "_MaskedScalarVectorPattern",
    "_ImmediatePattern",
)
