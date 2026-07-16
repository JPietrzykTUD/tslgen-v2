"""Public typed plans for value-test planning and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic
from tslc.value_tests.case_capabilities import (
    DEFAULT_VALUE_TEST_CASE_CAPABILITIES,
    DEFAULT_VALUE_TEST_CASE_KINDS,
)
from tslc.value_tests.case_components import (
    IndexStyle,
    MemoryStorage,
    ValueTestCaseCapability,
    ValueTestCaseRequirements,
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestFact,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestRepresentation,
    ValueTestScalable,
    ValueTestTarget,
)
from tslc.value_tests.case_plan import ValueTestCasePlan

ValueTestCoverageStatus = Literal[
    "emitted",
    "compile_only_emitted",
    "missing_authored_tests",
    "authored_unplanned",
    "backend_unsupported",
]


@dataclass(frozen=True, slots=True)
class HarnessPrimitiveNames:
    """Source-owned primitive names used by generated value-test harness code."""

    from_array: str | None
    to_array: str | None
    to_integral: str | None
    load: str | None = None
    store: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def round_trip_ready(self) -> bool:
        return self.from_array is not None and self.to_array is not None


@dataclass(frozen=True, slots=True)
class ValueTestCoverageEntry:
    """Planning outcome for one authored value-test case or primitive test gap."""

    backend_id: str
    profile_name: str
    primitive_name: str
    case_name: str | None
    status: ValueTestCoverageStatus
    reason: str = ""
    case_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ValueTestParityEntry:
    """Per-backend planning outcomes for one authored value-test identity."""

    profile_name: str
    primitive_name: str
    case_name: str | None
    backend_statuses: tuple[ValueTestCoverageEntry, ...]

    def status_for(self, backend_id: str) -> ValueTestCoverageStatus | None:
        for entry in self.backend_statuses:
            if entry.backend_id == backend_id:
                return entry.status
        return None


@dataclass(frozen=True, slots=True)
class ValueTestBackendSupport:
    """Value-test case kinds one backend renderer can consume."""

    backend_id: str
    case_kinds: frozenset[str]
    supports_differential: bool = False
    overload_inference_placeholders: int = 0


@dataclass(frozen=True, slots=True)
class ValueTestProfilePlan:
    backend_id: str
    profile_name: str
    cases: tuple[ValueTestCasePlan, ...]
    support_headers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValueTestProjectPlan:
    profiles: tuple[ValueTestProfilePlan, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    coverage: tuple[ValueTestCoverageEntry, ...] = ()

    def profiles_for(self, backend_id: str) -> tuple[ValueTestProfilePlan, ...]:
        return tuple(
            profile for profile in self.profiles if profile.backend_id == backend_id
        )


__all__ = (
    "DEFAULT_VALUE_TEST_CASE_CAPABILITIES",
    "DEFAULT_VALUE_TEST_CASE_KINDS",
    "HarnessPrimitiveNames",
    "IndexStyle",
    "MemoryStorage",
    "ValueTestBackendSupport",
    "ValueTestCaseCapability",
    "ValueTestCasePlan",
    "ValueTestCaseRequirements",
    "ValueTestCoverageEntry",
    "ValueTestCoverageStatus",
    "ValueTestDifferential",
    "ValueTestExpectation",
    "ValueTestFact",
    "ValueTestIndex",
    "ValueTestInputs",
    "ValueTestInvocation",
    "ValueTestMemory",
    "ValueTestParityEntry",
    "ValueTestProfilePlan",
    "ValueTestProjectPlan",
    "ValueTestRepresentation",
    "ValueTestScalable",
    "ValueTestTarget",
)
