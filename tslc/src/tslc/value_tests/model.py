"""Typed value-test plans consumed by backend test renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic

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
class ValueTestCasePlan:
    """One backend-specific generated value-test function, before text rendering."""

    kind: str
    function_name: str
    case_name: str
    call_name: str
    type_tag: str
    base_spelling: str
    lanes: int
    vector_inputs: tuple[tuple[str, ...], ...] = ()
    expected: tuple[str, ...] = ()
    expected_type_tag: str | None = None
    result_kind: str | None = None
    param_kinds: tuple[str, ...] = ()
    mask_inputs: tuple[str, ...] = ()
    scalar_input: str | None = None
    axis_args: tuple[str, ...] = ()
    immediate_value: str | None = None
    generic_defaults: tuple[str, ...] = ()
    target_base_spelling: str | None = None
    target_lanes: int | None = None
    source_extension: str | None = None
    target_extension: str | None = None
    index_value: str | None = None
    hardware_extension: str | None = None
    from_array_name: str | None = None
    to_array_name: str | None = None
    to_integral_name: str | None = None
    load_name: str | None = None
    store_name: str | None = None
    runtime_lanes_expr: str | None = None
    mask_from_bits_exprs: tuple[str, ...] = ()
    mask_check_expr: str | None = None
    buffer_offset: int = 0
    buffer_length: int | None = None
    source_offset: int = 0
    scalar_inputs: tuple[str, ...] = ()
    text_expected: str | None = None
    # Differential-fuzz cases (kind="differential_fuzz") carry no authored inputs: the emitted code
    # loops `fuzz_iterations` PRNG-seeded random inputs through hardware-vs-generic at runtime.
    fuzz_seed: int | None = None
    fuzz_iterations: int = 0


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
        return tuple(profile for profile in self.profiles if profile.backend_id == backend_id)


__all__ = (
    "ValueTestBackendSupport",
    "ValueTestCoverageEntry",
    "ValueTestCoverageStatus",
    "ValueTestParityEntry",
    "HarnessPrimitiveNames",
    "ValueTestCasePlan",
    "ValueTestProfilePlan",
    "ValueTestProjectPlan",
)
