"""Plan generated value-correctness tests from typed catalog and lowered facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests._case_conversion import FUZZ_ITERATIONS
from tslc.value_tests._pattern_base import (
    ValueTestCaseContext,
    ValueTestFuzzContext,
    unplanned_case_reason,
)
from tslc.value_tests.case_plans import compile_only_case
from tslc.value_tests.coverage import (
    CoverageIdentity,
    case_coverage,
    coverage_diagnostics,
    coverage_identity,
    coverage_key,
    merge_coverage,
)
from tslc.value_tests.harness import discover_harness_primitives
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestCoverageEntry,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)
from tslc.value_tests.patterns import ValueTestPattern, default_value_test_patterns
from tslc.value_tests.support_headers import support_headers_for_cases


@dataclass(frozen=True, slots=True)
class ValueTestBackendProfileInput:
    backend_id: str
    profile_name: str
    specializations: Mapping[str, tuple[LoweredSpecialization, ...]]


class ValueTestPlanner:
    def __init__(
        self,
        catalog: Catalog,
        backend_supports: tuple[ValueTestBackendSupport, ...],
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
        patterns: tuple[ValueTestPattern, ...] | None = None,
        fuzz: bool = False,
        fuzz_iterations: int = FUZZ_ITERATIONS,
    ) -> None:
        self._catalog = catalog
        self._backend_supports = {backend.backend_id: backend for backend in backend_supports}
        self._patterns = patterns if patterns is not None else default_value_test_patterns(support)
        self._fuzz = fuzz
        self._fuzz_iterations = fuzz_iterations

    def plan(self, profiles: tuple[ValueTestBackendProfileInput, ...]) -> ValueTestProjectPlan:
        harness = discover_harness_primitives(self._catalog)
        diagnostics = list(harness.diagnostics)
        raw_coverage: list[ValueTestCoverageEntry] = []
        coverage_locations: dict[CoverageIdentity, SourceLocation | None] = {}
        profile_plans = [
            self._plan_backend_profile(profile, harness, raw_coverage, coverage_locations)
            for profile in profiles
            if profile.backend_id in self._backend_supports
        ]
        coverage = merge_coverage(raw_coverage)
        diagnostics.extend(coverage_diagnostics(coverage, coverage_locations))
        diagnostics.extend(_duplicate_case_diagnostics(profile_plans))
        return ValueTestProjectPlan(
            profiles=tuple(profile_plans),
            diagnostics=tuple(diagnostics),
            coverage=tuple(sorted(coverage, key=coverage_key)),
        )

    def _plan_backend_profile(
        self,
        profile: ValueTestBackendProfileInput,
        harness: HarnessPrimitiveNames,
        coverage: list[ValueTestCoverageEntry],
        coverage_locations: dict[CoverageIdentity, SourceLocation | None],
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
            if primitive is None:
                continue
            fuzz_builder = getattr(pattern, "fuzz_cases", None) if self._fuzz else None
            if fuzz_builder is not None:
                fuzz_planned = fuzz_builder(
                    self._fuzz_context(backend, emitted_name, specs, harness)
                )
                cases.extend(self._supported_cases(fuzz_planned, backend))
            if not primitive.tests:
                entry = ValueTestCoverageEntry(
                    backend_id=profile.backend_id,
                    profile_name=profile.profile_name,
                    primitive_name=source_name,
                    case_name=None,
                    status="missing_authored_tests",
                    reason="selected primitive has no authored tests",
                )
                coverage.append(entry)
                coverage_locations.setdefault(coverage_identity(entry), _primitive_location(primitive))
                continue
            for index, test_case in enumerate(primitive.tests):
                if not any(spec.type_tag == test_case.type_tag for spec in specs):
                    continue
                if _case_extension_unselected(test_case, specs):
                    continue
                if _representation_case_unselected(test_case, specs):
                    continue
                case_context = self._case_context(
                    backend, emitted_name, index, test_case, specs, harness
                )
                planned: tuple[ValueTestCasePlan, ...]
                if test_case.role == "compile":
                    plan = compile_only_case(emitted_name, index, test_case, specs)
                    planned = (plan,) if plan is not None else ()
                else:
                    planned = pattern.plan_case(case_context) if pattern is not None else ()
                supported = self._supported_cases(planned, backend)
                cases.extend(supported)
                entry = case_coverage(
                    backend=backend,
                    profile_name=profile.profile_name,
                    primitive_name=source_name,
                    case_name=test_case.name,
                    planned=planned,
                    supported=supported,
                    unplanned_reason=unplanned_case_reason(pattern, planned, case_context),
                )
                coverage.append(entry)
                coverage_locations.setdefault(
                    coverage_identity(entry),
                    (
                        test_case.source.start
                        if test_case.source is not None
                        else _primitive_location(primitive)
                    ),
                )
        return ValueTestProfilePlan(
            backend_id=profile.backend_id,
            profile_name=profile.profile_name,
            cases=tuple(cases),
            support_headers=support_headers_for_cases(cases, self._catalog, profile.backend_id),
        )

    def _case_context(
        self,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        harness: HarnessPrimitiveNames,
    ) -> ValueTestCaseContext:
        return ValueTestCaseContext(
            backend, emitted_name, index, case, specs, self._catalog, harness
        )

    def _fuzz_context(
        self,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        specs: tuple[LoweredSpecialization, ...],
        harness: HarnessPrimitiveNames,
    ) -> ValueTestFuzzContext:
        return ValueTestFuzzContext(
            backend, emitted_name, specs, self._catalog, harness, self._fuzz_iterations
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


def _primitive_location(primitive: Primitive) -> SourceLocation | None:
    return primitive.source.start if primitive.source is not None else None


def _representation_case_unselected(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> bool:  # noqa: ANN001
    if case.to_extension is not None:
        return not any(
            spec.extension_name == case.extension
            and spec.type_tag == case.type_tag
            and spec.target is not None
            and spec.target.extension_isa == case.to_extension
            for spec in specs
        )
    if case.to_type is not None and case.extension is not None:
        return not any(
            spec.extension_name == case.extension
            and spec.type_tag == case.type_tag
            and spec.target is not None
            and spec.target.base_tag == case.to_type
            for spec in specs
        )
    return False


def _case_extension_unselected(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> bool:  # noqa: ANN001
    if case.extension is None:
        return False
    return not any(spec.extension_name == case.extension and spec.type_tag == case.type_tag for spec in specs)


__all__ = ("ValueTestBackendProfileInput", "ValueTestPlanner")
