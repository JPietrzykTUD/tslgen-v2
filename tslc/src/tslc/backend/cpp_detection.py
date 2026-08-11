"""Typed C++ profile detection and gated auto-selection capabilities."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from types import MappingProxyType

from tslc.catalog.machine_profiles import MachineProfile

CPP_PROFILE_DETECTION_KINDS = frozenset({"aarch64_hwcaps", "x86_builtin"})


@dataclass(frozen=True, slots=True)
class CppProfileAutoGate:
    """Backend-owned build probe for one source-named semantic auto gate."""

    gate_id: str
    mode_name: str
    helper_function: str
    helper_asset: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.gate_id,
                self.mode_name,
                self.helper_function,
                self.helper_asset,
            )
        ):
            raise ValueError("C++ profile auto gates require complete identities")


class CppProfileAutoGateRegistry:
    """Immutable vocabulary for C++ profile-gate probes."""

    __slots__ = ("_gates", "_by_id")

    def __init__(self, gates: Iterable[CppProfileAutoGate] = ()) -> None:
        ordered = tuple(gates)
        by_id: dict[str, CppProfileAutoGate] = {}
        duplicates: set[str] = set()
        modes: set[str] = set()
        duplicate_modes: set[str] = set()
        for gate in ordered:
            if gate.gate_id in by_id:
                duplicates.add(gate.gate_id)
            if gate.mode_name in modes:
                duplicate_modes.add(gate.mode_name)
            by_id[gate.gate_id] = gate
            modes.add(gate.mode_name)
        if duplicates:
            raise ValueError(
                "duplicate C++ profile auto-gate IDs: "
                + ", ".join(sorted(duplicates))
            )
        if duplicate_modes:
            raise ValueError(
                "duplicate C++ profile auto modes: "
                + ", ".join(sorted(duplicate_modes))
            )
        self._gates = ordered
        self._by_id = MappingProxyType(by_id)

    def __iter__(self) -> Iterator[CppProfileAutoGate]:
        return iter(self._gates)

    @property
    def gate_ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def require(self, gate_id: str) -> CppProfileAutoGate:
        return self._by_id[gate_id]


CPP_PROFILE_AUTO_GATES = CppProfileAutoGateRegistry(
    (
        CppProfileAutoGate(
            gate_id="oneapi_fpga",
            mode_name="auto-oneapi-fpga",
            helper_function="_tsl_detect_oneapi_fpga",
            helper_asset="cpp_profile_auto_helpers.cmake",
        ),
    )
)


@dataclass(frozen=True, slots=True)
class CppProfileDetectionPlan:
    """All backend-decided profile fallback and gated-auto facts."""

    fallback_profile_name: str | None
    auto_gates: tuple[CppProfileAutoGate, ...]

    @property
    def auto_choices(self) -> tuple[str, ...]:
        return tuple(gate.mode_name for gate in self.auto_gates)

    @property
    def helper_assets(self) -> tuple[str, ...]:
        return tuple(sorted({gate.helper_asset for gate in self.auto_gates}))


def cpp_profile_detection_plan(
    profiles: tuple[MachineProfile, ...],
    *,
    gate_registry: CppProfileAutoGateRegistry = CPP_PROFILE_AUTO_GATES,
) -> CppProfileDetectionPlan:
    """Resolve source gate IDs once before CMake formatting begins."""

    ungated = tuple(profile for profile in profiles if profile.auto_detect_gate is None)
    declared_fallbacks = tuple(
        profile for profile in ungated if profile.default_build_fallback
    )
    fallback = (
        declared_fallbacks[0]
        if declared_fallbacks
        else (ungated[0] if ungated else None)
    )
    gate_ids = tuple(
        sorted(
            {
                profile.auto_detect_gate
                for profile in profiles
                if profile.auto_detect_gate is not None
            }
        )
    )
    return CppProfileDetectionPlan(
        fallback_profile_name=None if fallback is None else fallback.name,
        auto_gates=tuple(gate_registry.require(gate_id) for gate_id in gate_ids),
    )


__all__ = (
    "CPP_PROFILE_AUTO_GATES",
    "CPP_PROFILE_DETECTION_KINDS",
    "CppProfileAutoGate",
    "CppProfileAutoGateRegistry",
    "CppProfileDetectionPlan",
    "cpp_profile_detection_plan",
)
