"""Plan generated value-correctness tests from typed catalog and lowered facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)
from tslc.value_tests.patterns import ValueTestPattern, default_value_test_patterns


@dataclass(frozen=True, slots=True)
class ValueTestBackendProfileInput:
    """Finalized lowered specializations for one backend/profile pair."""

    backend_id: str
    profile_name: str
    specializations: Mapping[str, tuple[LoweredSpecialization, ...]]


class ValueTestPlanner:
    """Create typed value-test plans from finalized profile render data."""

    def __init__(
        self,
        catalog: Catalog,
        backend_supports: tuple[ValueTestBackendSupport, ...],
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
        patterns: tuple[ValueTestPattern, ...] | None = None,
    ) -> None:
        self._catalog = catalog
        self._backend_supports = {backend.backend_id: backend for backend in backend_supports}
        self._patterns = patterns if patterns is not None else default_value_test_patterns(support)

    def plan(self, profiles: tuple[ValueTestBackendProfileInput, ...]) -> ValueTestProjectPlan:
        harness = discover_harness_primitives(self._catalog)
        diagnostics = list(harness.diagnostics)
        profile_plans = [
            self._plan_backend_profile(profile, harness, diagnostics)
            for profile in profiles
            if profile.backend_id in self._backend_supports
        ]
        diagnostics.extend(_duplicate_case_diagnostics(profile_plans))
        return ValueTestProjectPlan(
            profiles=tuple(profile_plans),
            diagnostics=tuple(diagnostics),
        )

    def _plan_backend_profile(
        self,
        profile: ValueTestBackendProfileInput,
        harness: HarnessPrimitiveNames,
        diagnostics: list[Diagnostic],
    ) -> ValueTestProfilePlan:
        backend = self._backend_supports[profile.backend_id]
        cases: list[ValueTestCasePlan] = []
        for emitted_name in sorted(profile.specializations):
            specs = profile.specializations[emitted_name]
            if not specs:
                continue
            pattern = self._pattern_for(specs)
            source_name = specs[0].source_primitive_name
            primitive = (
                pattern.source_primitive(self._catalog, source_name, specs[0])
                if pattern is not None
                else self._catalog.primitive(source_name, unmasked=False)
            )
            if primitive is None or not primitive.tests:
                continue
            for index, test_case in enumerate(primitive.tests):
                planned = (
                    pattern.plan_case(
                        backend=backend,
                        emitted_name=emitted_name,
                        index=index,
                        case=test_case,
                        specs=specs,
                        catalog=self._catalog,
                        harness=harness,
                    )
                    if pattern is not None
                    else ()
                )
                supported = self._supported_cases(planned, backend)
                cases.extend(supported)
                if not supported:
                    diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            code="TSL-VALUE-TEST-UNSUPPORTED-CASE",
                            message=(
                                f"no {profile.backend_id} value-test plan for case "
                                f"{test_case.name!r} of primitive {source_name!r} "
                                f"in profile {profile.profile_name!r}"
                            ),
                            location=(
                                test_case.source.start
                                if test_case.source is not None
                                else (
                                    primitive.source.start
                                    if primitive.source is not None
                                    else None
                                )
                            ),
                        )
                    )
        return ValueTestProfilePlan(
            backend_id=profile.backend_id,
            profile_name=profile.profile_name,
            cases=tuple(cases),
        )

    def _pattern_for(self, specs: tuple[LoweredSpecialization, ...]) -> ValueTestPattern | None:
        for pattern in self._patterns:
            if pattern.matches(specs):
                return pattern
        return None

    def _supported_cases(
        self,
        cases: tuple[ValueTestCasePlan, ...],
        backend: ValueTestBackendSupport,
    ) -> tuple[ValueTestCasePlan, ...]:
        return tuple(case for case in cases if case.kind in backend.case_kinds)


def _duplicate_case_diagnostics(
    profile_plans: list[ValueTestProfilePlan],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for profile in profile_plans:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for case in profile.cases:
            if case.function_name in seen:
                duplicates.add(case.function_name)
            seen.add(case.function_name)
        for name in sorted(duplicates):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-VALUE-TEST-DUPLICATE-FUNCTION",
                    message=(
                        f"duplicate {profile.backend_id} value-test function {name!r} "
                        f"in profile {profile.profile_name!r}"
                    ),
                )
            )
    return tuple(diagnostics)


__all__ = ("ValueTestBackendProfileInput", "ValueTestPlanner")
