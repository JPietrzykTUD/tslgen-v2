"""Plan generated value-correctness tests from typed catalog and lowered facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.lowerer import varying_positions
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.value_tests._case_conversion import FUZZ_ITERATIONS
from tslc.value_tests._pattern_base import (
    ValueTestCaseContext,
    ValueTestFuzzContext,
    unplanned_case_reason,
)
from tslc.value_tests.case_capabilities import DEFAULT_VALUE_TEST_CASE_REQUIREMENTS
from tslc.value_tests.case_plans import compile_only_case, runtime_failure_case
from tslc.value_tests.coverage import (
    CoverageIdentity,
    ValueTestCaseDrop,
    ValueTestCaseDropCause,
    case_coverage,
    coverage_diagnostics,
    coverage_identity,
    coverage_key,
    dropped_fuzz_coverage,
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
        coverage_locations: dict[CoverageIdentity, SourceSpan | None] = {}
        profile_plans = [
            self._plan_backend_profile(
                profile,
                harness,
                raw_coverage,
                coverage_locations,
                diagnostics,
            )
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
        coverage_locations: dict[CoverageIdentity, SourceSpan | None],
        diagnostics: list[Diagnostic],
    ) -> ValueTestProfilePlan:
        backend = self._backend_supports[profile.backend_id]
        cases: list[ValueTestCasePlan] = []
        for emitted_name in sorted(profile.specializations):
            emitted_specs = profile.specializations[emitted_name]
            inferred_type_args = (
                backend.overload_inference_placeholders
                if varying_positions(emitted_specs)
                else 0
            )
            for specs in _value_test_spec_groups(emitted_specs):
                pattern = self._pattern_for(specs)
                source_name = specs[0].source_primitive_name
                primitive = (
                    pattern.source_primitive(self._catalog, source_name, specs[0])
                    if pattern is not None
                    else self._catalog.primitive(source_name, unmasked=False)
                )
                if primitive is None:
                    continue
                if self._fuzz and pattern is not None:
                    fuzz_planned = pattern.fuzz_cases(
                        self._fuzz_context(
                            backend, emitted_name, specs, harness, primitive
                        )
                    )
                    fuzz_supported, fuzz_drops = self._supported_cases(
                        fuzz_planned,
                        backend,
                        profile.specializations,
                        diagnostics,
                    )
                    cases.extend(fuzz_supported)
                    for drop in fuzz_drops:
                        entry = dropped_fuzz_coverage(
                            backend=backend,
                            profile_name=profile.profile_name,
                            primitive_name=source_name,
                            drop=drop,
                        )
                        coverage.append(entry)
                        coverage_locations.setdefault(
                            coverage_identity(entry), _primitive_span(primitive)
                        )
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
                    coverage_locations.setdefault(
                        coverage_identity(entry), _primitive_span(primitive)
                    )
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
                    elif test_case.role == "runtime_failure":
                        plan = runtime_failure_case(
                            emitted_name, index, test_case, specs
                        )
                        planned = (plan,) if plan is not None else ()
                    elif test_case.role == "compile_failure":
                        # Slice 5 lowers these into negative-compilation units.
                        planned = ()
                    else:
                        planned = (
                            pattern.plan_case(case_context) if pattern is not None else ()
                        )
                    if inferred_type_args:
                        planned = tuple(
                            replace(
                                case,
                                invocation=replace(
                                    case.invocation,
                                    inferred_type_args=inferred_type_args,
                                ),
                            )
                            for case in planned
                        )
                    supported, drops = self._supported_cases(
                        planned,
                        backend,
                        profile.specializations,
                        diagnostics,
                    )
                    cases.extend(supported)
                    entry = case_coverage(
                        backend=backend,
                        profile_name=profile.profile_name,
                        primitive_name=source_name,
                        case_name=test_case.name,
                        planned=planned,
                        supported=supported,
                        drops=drops,
                        unplanned_reason=unplanned_case_reason(
                            pattern, planned, case_context
                        ),
                    )
                    coverage.append(entry)
                    coverage_locations.setdefault(
                        coverage_identity(entry),
                        (
                            test_case.source
                            if test_case.source is not None
                            else _primitive_span(primitive)
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
        primitive: Primitive,
    ) -> ValueTestFuzzContext:
        return ValueTestFuzzContext(
            backend,
            emitted_name,
            specs,
            self._catalog,
            harness,
            self._fuzz_iterations,
            primitive,
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
        specializations: Mapping[str, tuple[LoweredSpecialization, ...]],
        diagnostics: list[Diagnostic],
    ) -> tuple[tuple[ValueTestCasePlan, ...], tuple[ValueTestCaseDrop, ...]]:
        """Split planned cases into renderable cases and typed per-case drops."""

        supported: list[ValueTestCasePlan] = []
        drops: list[ValueTestCaseDrop] = []
        for case in cases:
            if case.kind not in backend.case_kinds:
                cause: ValueTestCaseDropCause = (
                    "fuzz_unsupported"
                    if DEFAULT_VALUE_TEST_CASE_REQUIREMENTS[case.kind].fuzz_case
                    else "renderer_unsupported"
                )
                drops.append(ValueTestCaseDrop(case, cause))
                continue
            missing_helpers = _missing_differential_helpers(case, specializations)
            if missing_helpers:
                assert case.differential is not None
                drops.append(
                    ValueTestCaseDrop(
                        case,
                        "differential_harness_missing",
                        detail=(
                            "differential harness primitive(s) "
                            + ", ".join(repr(name) for name in missing_helpers)
                            + " are not selected for extension "
                            + repr(case.differential.hardware_extension)
                            + f" and type {case.type_tag!r} in this profile"
                        ),
                    )
                )
                continue
            resolved = self._with_header_group(case, backend.backend_id, diagnostics)
            if isinstance(resolved, ValueTestCaseDrop):
                drops.append(resolved)
                continue
            supported.append(resolved)
        return tuple(supported), tuple(drops)

    def _with_header_group(
        self,
        case: ValueTestCasePlan,
        backend_id: str,
        diagnostics: list[Diagnostic],
    ) -> ValueTestCasePlan | ValueTestCaseDrop:
        extension_names: set[str] = set()
        if case.differential is not None:
            extension_names.add(case.differential.hardware_extension)
        if case.representation is not None:
            if case.representation.source_extension is not None:
                extension_names.add(case.representation.source_extension)
            if case.representation.target_extension is not None:
                extension_names.add(case.representation.target_extension)
        groups = {
            metadata.header_group
            for name in extension_names
            if (extension := self._catalog.extensions.get(name)) is not None
            if (metadata := extension.metadata.backend.get(backend_id)) is not None
            if metadata.header_group is not None
        }
        if len(groups) > 1:
            extensions = tuple(
                self._catalog.extensions[name]
                for name in sorted(extension_names)
                if name in self._catalog.extensions
            )
            source = next(
                (extension.source for extension in extensions if extension.source is not None),
                None,
            )
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-VALUE-TEST-INCOMPATIBLE-HEADER-GROUPS",
                    message=(
                        f"{backend_id} value-test case {case.function_name!r} spans "
                        f"incompatible header groups {sorted(groups)} through extensions "
                        f"{sorted(extension_names)}"
                    ),
                    span=source,
                )
            )
            return ValueTestCaseDrop(
                case,
                "header_group_conflict",
                detail=(
                    f"case spans incompatible generated header groups "
                    f"{sorted(groups)} through extensions {sorted(extension_names)}"
                ),
            )
        compiler_features = tuple(
            sorted(
                {
                    feature
                    for name in extension_names
                    if (extension := self._catalog.extensions.get(name)) is not None
                    if (metadata := extension.metadata.backend.get(backend_id)) is not None
                    for feature in metadata.compiler_features
                }
            )
        )
        return replace(
            case,
            header_group=next(iter(groups), None),
            required_compiler_features=compiler_features,
        )


def _missing_differential_helpers(
    case: ValueTestCasePlan,
    specializations: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> tuple[str, ...]:
    """Harness helper names the profile closure does not provide for this case."""

    differential = case.differential
    if differential is None:
        return ()
    if case.invocation.result_kind == "m":
        result_role, result_helper = "to_integral", differential.to_integral_name
    else:
        result_role, result_helper = "to_array", differential.to_array_name
    missing: list[str] = []
    for role, helper_name in (
        ("from_array", differential.from_array_name),
        (result_role, result_helper),
        *(
            (("to_mask", differential.to_mask_name),)
            if "m" in case.invocation.param_kinds
            else ()
        ),
    ):
        if helper_name is None:
            missing.append(role)
            continue
        if not any(
            spec.extension_name == differential.hardware_extension
            and spec.type_tag == case.type_tag
            for spec in specializations.get(helper_name, ())
        ):
            missing.append(helper_name)
    return tuple(missing)


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


def _value_test_spec_groups(
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[tuple[LoweredSpecialization, ...], ...]:
    """Keep overload signatures independent while retaining their type/profile matrix."""

    groups: dict[
        tuple[
            str,
            str,
            tuple[str, ...],
            str,
            str,
            tuple[str, ...],
            tuple[str, ...],
        ],
        list[LoweredSpecialization],
    ] = {}
    for spec in specs:
        key = (
            spec.source_primitive_name,
            spec.result_kind,
            spec.param_kinds,
            spec.mask_policy or "",
            spec.immediate[0] if spec.immediate is not None else "",
            tuple(name for name, _type, _default in spec.generic_params),
            tuple(param.name for param in spec.type_params),
        )
        groups.setdefault(key, []).append(spec)
    return tuple(tuple(groups[key]) for key in sorted(groups))


def _primitive_span(primitive: Primitive) -> SourceSpan | None:
    return primitive.source


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
