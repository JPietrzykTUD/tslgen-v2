"""Plan generated value-correctness tests from typed catalog and lowered facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestCasePlan,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)
from tslc.value_tests.patterns import ValueTestPattern, default_value_test_patterns

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


class ValueTestPlanner:
    """Create typed value-test plans from finalized profile render data."""

    def __init__(
        self,
        catalog: Catalog,
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
        patterns: tuple[ValueTestPattern, ...] | None = None,
    ) -> None:
        self._catalog = catalog
        self._patterns = patterns if patterns is not None else default_value_test_patterns(support)

    def plan(self, profiles: tuple["ProfileRender", ...]) -> ValueTestProjectPlan:
        harness = discover_harness_primitives(self._catalog)
        diagnostics = list(harness.diagnostics)
        cpp_profiles = [
            self._plan_backend_profile("cpp", profile.profile.name, profile.cpp, harness, diagnostics)
            for profile in profiles
        ]
        rust_profiles = [
            self._plan_backend_profile("rust", profile.profile.name, profile.rust, harness, diagnostics)
            for profile in profiles
        ]
        diagnostics.extend(_duplicate_case_diagnostics(cpp_profiles + rust_profiles))
        return ValueTestProjectPlan(
            cpp_profiles=tuple(cpp_profiles),
            rust_profiles=tuple(rust_profiles),
            diagnostics=tuple(diagnostics),
        )

    def _plan_backend_profile(
        self,
        backend_id: str,
        profile_name: str,
        by_name: dict[str, tuple[LoweredSpecialization, ...]],
        harness: HarnessPrimitiveNames,
        diagnostics: list[Diagnostic],
    ) -> ValueTestProfilePlan:
        cases: list[ValueTestCasePlan] = []
        for emitted_name in sorted(by_name):
            specs = by_name[emitted_name]
            if not specs:
                continue
            pattern = self._pattern_for(backend_id, specs)
            source_name = specs[0].source_primitive_name
            primitive = (
                pattern.source_primitive(self._catalog, source_name, specs[0])
                if pattern is not None
                else self._catalog.primitive(source_name, unmasked=False)
            )
            if primitive is None or not primitive.tests:
                continue
            before = len(cases)
            if pattern is not None:
                for index, test_case in enumerate(primitive.tests):
                    cases.extend(
                        pattern.plan_case(
                            backend_id=backend_id,
                            emitted_name=emitted_name,
                            index=index,
                            case=test_case,
                            specs=specs,
                            catalog=self._catalog,
                            harness=harness,
                        )
                    )
            if len(cases) == before:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="TSL-VALUE-TEST-UNSUPPORTED-SHAPE",
                        message=(
                            f"no {backend_id} value-test plan for primitive "
                            f"{source_name!r} in profile {profile_name!r}"
                        ),
                        location=primitive.source.start if primitive.source is not None else None,
                    )
                )
        return ValueTestProfilePlan(
            backend_id=backend_id,
            profile_name=profile_name,
            cases=tuple(cases),
        )

    def _pattern_for(
        self,
        backend_id: str,
        specs: tuple[LoweredSpecialization, ...],
    ) -> ValueTestPattern | None:
        for pattern in self._patterns:
            if backend_id in pattern.backend_ids and pattern.matches(specs):
                return pattern
        return None


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


__all__ = ("ValueTestPlanner",)
