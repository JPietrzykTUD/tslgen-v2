"""Typed value-test plans consumed by backend test renderers."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class HarnessPrimitiveNames:
    """Source-owned primitive names used by generated value-test harness code."""

    from_array: str | None
    to_array: str | None
    to_integral: str | None
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
    buffer_offset: int = 0
    buffer_length: int | None = None


@dataclass(frozen=True, slots=True)
class ValueTestProfilePlan:
    backend_id: str
    profile_name: str
    cases: tuple[ValueTestCasePlan, ...]


@dataclass(frozen=True, slots=True)
class ValueTestProjectPlan:
    cpp_profiles: tuple[ValueTestProfilePlan, ...]
    rust_profiles: tuple[ValueTestProfilePlan, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


__all__ = (
    "HarnessPrimitiveNames",
    "ValueTestCasePlan",
    "ValueTestProfilePlan",
    "ValueTestProjectPlan",
)
