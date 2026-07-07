"""Conversion-oriented value-test shape patterns."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import SupportPolicy
from tslc.value_tests._case_conversion import (
    convert_case,
    extension_harness_available,
    extension_repr_case,
    load_convert_case,
    repr_cast_case,
)
from tslc.value_tests._pattern_base import _BasePattern, ValueTestCaseContext
from tslc.value_tests.model import ValueTestCasePlan

class _LoadConvertPattern(_BasePattern):
    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        return any(
            spec.result_kind == "v"
            and spec.target is not None
            and tuple(spec.param_kinds) == ("cptr+",)
            for spec in specs
        )

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = load_convert_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
            context.harness,
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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = convert_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        plan = repr_cast_case(
            context.emitted_name,
            context.index,
            context.case,
            context.specs,
            context.harness,
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

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        harness = context.harness
        if not harness.round_trip_ready:
            return ()
        specs = context.specs
        case = context.case
        if not extension_harness_available(case, specs):
            return ()
        kind = "extension_insert" if "vt" in specs[0].param_kinds else "extension_extract"
        plan = extension_repr_case(
            kind, context.emitted_name, context.index, case, specs, harness
        )
        return (plan,) if plan is not None else ()

__all__ = (
    "_LoadConvertPattern",
    "_ConvertPattern",
    "_ReprCastPattern",
    "_ExtensionReprPattern",
)
