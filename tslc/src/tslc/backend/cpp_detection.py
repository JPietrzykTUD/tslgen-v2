"""Typed C++ profile detection and gated auto-selection capabilities."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from tslc.backend.cpp_compiler_capabilities import (
    CppCompilerCapability,
    cpp_extension_header_group,
    cpp_extensions_compiler_capabilities,
)
from tslc.backend.cpp_profile import cpp_compiler_capability_condition
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.target_families import ProfileFamilyCapability


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
class CppProfileDetectionCandidate:
    """One backend-ordered profile and its complete runtime probe source."""

    profile_name: str
    auto_gate_id: str | None
    has_features: bool
    source: str | None


@dataclass(frozen=True, slots=True)
class CppProfileDetectionPlan:
    """All backend-decided profile fallback and gated-auto facts."""

    fallback_profile_name: str | None
    auto_gates: tuple[CppProfileAutoGate, ...]

    candidates: tuple[CppProfileDetectionCandidate, ...] = ()

    @property
    def auto_choices(self) -> tuple[str, ...]:
        return tuple(gate.mode_name for gate in self.auto_gates)

    @property
    def helper_assets(self) -> tuple[str, ...]:
        return tuple(sorted({gate.helper_asset for gate in self.auto_gates}))


def cpp_profile_detection_plan(
    profiles: tuple[MachineProfile, ...],
    *,
    candidates: tuple[CppProfileDetectionCandidate, ...] = (),
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
        candidates=candidates,
    )


@dataclass(frozen=True, slots=True)
class _X86CpuidProbe:
    leaf: int
    subleaf: int | None
    register: str
    bit: int


# Clang accepts these target features but rejects their spellings in
# __builtin_cpu_supports. The backend therefore owns their direct CPUID evidence.
_X86_CPUID_PROBES = {
    "rdrand": _X86CpuidProbe(leaf=1, subleaf=None, register="ecx", bit=30),
    "avx512_vaes": _X86CpuidProbe(leaf=7, subleaf=0, register="ecx", bit=9),
    "avx512_fp16": _X86CpuidProbe(leaf=7, subleaf=0, register="edx", bit=23),
}


def x86_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[CppCompilerCapability] = (),
) -> str:
    """Complete C++ runtime probe for one x86 profile."""

    cpuid_probes = {
        feature: _X86_CPUID_PROBES[feature]
        for feature in sorted(profile.features)
        if feature in _X86_CPUID_PROBES
    }
    checks = []
    for feature in sorted(profile.features):
        if feature in cpuid_probes:
            checks.append(f"tsl_cpu_has_{feature}")
        else:
            checks.append(
                f'__builtin_cpu_supports("{profile.feature_spelling(feature, "cpp")}")'
            )
    if guards:
        checks.append(cpp_compiler_capability_condition(guards))
    condition = " && ".join(checks) if checks else "1"
    target_condition = (
        "(defined(__x86_64__) || defined(__i386__)) "
        "&& (defined(__GNUC__) || defined(__clang__))"
    )
    lines: list[str] = []
    if cpuid_probes:
        lines.extend((f"#if {target_condition}", "#include <cpuid.h>", "#endif"))
    lines.extend(("int main() {", f"#if {target_condition}", "  __builtin_cpu_init();"))
    cpuid_queries = sorted(
        {(probe.leaf, probe.subleaf) for probe in cpuid_probes.values()},
        key=lambda query: (query[0], -1 if query[1] is None else query[1]),
    )
    for leaf, subleaf in cpuid_queries:
        query_name = f"tsl_cpuid_{leaf}"
        if subleaf is not None:
            query_name += f"_{subleaf}"
        registers = tuple(
            f"{query_name}_{register}"
            for register in ("eax", "ebx", "ecx", "edx")
        )
        call = "__get_cpuid" if subleaf is None else "__get_cpuid_count"
        arguments = [str(leaf)]
        if subleaf is not None:
            arguments.append(str(subleaf))
        arguments.extend(f"&{register}" for register in registers)
        lines.extend(
            (
                f"  unsigned int {', '.join(f'{register} = 0' for register in registers)};",
                f"  const bool {query_name}_available =",
                f"      {call}({', '.join(arguments)}) != 0;",
            )
        )
    for feature, probe in cpuid_probes.items():
        query_name = f"tsl_cpuid_{probe.leaf}"
        if probe.subleaf is not None:
            query_name += f"_{probe.subleaf}"
        lines.extend(
            (
                f"  const bool tsl_cpu_has_{feature} =",
                f"      {query_name}_available &&",
                f"      ({query_name}_{probe.register} & (1u << {probe.bit})) != 0;",
            )
        )
    lines.extend(
        (
            f"  return ({condition}) ? 0 : 1;",
            "#else",
            "  return 1;",
            "#endif",
            "}",
        )
    )
    return "\n".join(lines)


def aarch64_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[CppCompilerCapability] = (),
) -> str | None:
    """Complete C++ runtime probe for one AArch64 profile."""

    if "sve" in profile.features:
        guard_condition = (
            f" && {cpp_compiler_capability_condition(guards)}" if guards else ""
        )
        return "\n".join(
            (
                "#if defined(__linux__) && defined(__aarch64__)",
                "#  include <sys/auxv.h>",
                "#  include <asm/hwcap.h>",
                "#endif",
                "int main() {",
                (
                    "#if defined(__linux__) && defined(__aarch64__) "
                    f"&& defined(HWCAP_SVE){guard_condition}"
                ),
                "  return (getauxval(AT_HWCAP) & HWCAP_SVE) ? 0 : 1;",
                "#else",
                "  return 1;",
                "#endif",
                "}",
            )
        )
    if "neon" in profile.features:
        return "\n".join(
            (
                "int main() {",
                "#if defined(__aarch64__)",
                "  return 0;",
                "#else",
                "  return 1;",
                "#endif",
                "}",
            )
        )
    return None


@dataclass(frozen=True, slots=True)
class CppProfileDetectionStrategy:
    """One backend-owned runtime-detection strategy."""

    strategy_id: str
    source_builder: Callable[
        [MachineProfile, Sequence[CppCompilerCapability]], str | None
    ]

    def source(
        self,
        profile: MachineProfile,
        guards: Sequence[CppCompilerCapability],
    ) -> str | None:
        return self.source_builder(profile, guards)


class CppProfileDetectionStrategyRegistry:
    """Immutable registry for additive C++ runtime-detection strategies."""

    __slots__ = ("_strategies", "_by_id")

    def __init__(self, strategies: Iterable[CppProfileDetectionStrategy] = ()) -> None:
        ordered = tuple(strategies)
        by_id = {strategy.strategy_id: strategy for strategy in ordered}
        if len(by_id) != len(ordered):
            raise ValueError("duplicate C++ profile detection strategy IDs")
        self._strategies = ordered
        self._by_id = MappingProxyType(by_id)

    def __iter__(self) -> Iterator[CppProfileDetectionStrategy]:
        return iter(self._strategies)

    @property
    def strategy_ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def require(self, strategy_id: str) -> CppProfileDetectionStrategy:
        return self._by_id[strategy_id]


CPP_PROFILE_DETECTION_STRATEGIES = CppProfileDetectionStrategyRegistry(
    (
        CppProfileDetectionStrategy("x86_builtin", x86_profile_detection_source),
        CppProfileDetectionStrategy(
            "aarch64_hwcaps", aarch64_profile_detection_source
        ),
    )
)
CPP_PROFILE_DETECTION_KINDS = CPP_PROFILE_DETECTION_STRATEGIES.strategy_ids


def cpp_profile_detection_candidates(
    profiles: tuple[EmittedProfile, ...],
    *,
    strategy_registry: CppProfileDetectionStrategyRegistry = (
        CPP_PROFILE_DETECTION_STRATEGIES
    ),
) -> tuple[CppProfileDetectionCandidate, ...]:
    """Decide ordered runtime-probe sources before CMake formatting."""

    ordered = sorted(
        profiles,
        key=lambda emitted: (
            (
                emitted.profile_family.sort_order
                if emitted.profile_family is not None
                else ProfileFamilyCapability(emitted.profile.family).sort_order
            ),
            len(emitted.profile.features),
            emitted.profile.name,
        ),
    )
    candidates: list[CppProfileDetectionCandidate] = []
    for emitted in ordered:
        profile = emitted.profile
        family = emitted.profile_family or ProfileFamilyCapability(profile.family)
        strategy_id = family.backend("cpp").detection
        source = None
        if strategy_id is not None:
            guards = cpp_extensions_compiler_capabilities(
                tuple(
                    extension_name
                    for extension_name in used_extensions(
                        emitted.specializations("cpp")
                    )
                    if cpp_extension_header_group(
                        emitted.extensions.get(extension_name)
                    )
                    is None
                ),
                emitted.extensions,
            )
            source = strategy_registry.require(strategy_id).source(profile, guards)
        candidates.append(
            CppProfileDetectionCandidate(
                profile_name=profile.name,
                auto_gate_id=profile.auto_detect_gate,
                has_features=bool(profile.features),
                source=source,
            )
        )
    return tuple(candidates)

__all__ = (
    "CPP_PROFILE_AUTO_GATES",
    "CPP_PROFILE_DETECTION_STRATEGIES",
    "CPP_PROFILE_DETECTION_KINDS",
    "CppProfileAutoGate",
    "CppProfileAutoGateRegistry",
    "CppProfileDetectionCandidate",
    "CppProfileDetectionPlan",
    "CppProfileDetectionStrategy",
    "CppProfileDetectionStrategyRegistry",
    "aarch64_profile_detection_source",
    "cpp_profile_detection_candidates",
    "cpp_profile_detection_plan",
    "x86_profile_detection_source",
)
