"""Pre-render validation for C++ backend emission facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tslc.backend.cpp_detection import CPP_PROFILE_DETECTION_KINDS
from tslc.backend.target_capability import (
    cpp_x86_register_helper,
    x86_register_bits,
)
from tslc.catalog.model import BackendCompileGuard, Extension
from tslc.diagnostics import Diagnostic, diagnostic_at

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile


@dataclass(frozen=True, slots=True)
class CppCompileGuardResolution:
    guards: tuple[BackendCompileGuard, ...]
    diagnostics: tuple[Diagnostic, ...]


def resolve_cpp_compile_guards(
    emitted_extensions: Sequence[str],
    extensions: Mapping[str, Extension],
    *,
    profile_name: str | None = None,
) -> CppCompileGuardResolution:
    """Resolve profile guards and report contradictory source facts."""

    guards: dict[str, BackendCompileGuard] = {}
    macro_values: dict[str, tuple[str, BackendCompileGuard]] = {}
    diagnostics: list[Diagnostic] = []
    profile_label = f" for profile {profile_name!r}" if profile_name is not None else ""
    for extension_name in emitted_extensions:
        extension = extensions.get(extension_name)
        metadata = None if extension is None else extension.metadata.backend.get("cpp")
        for guard in () if metadata is None else metadata.compile_guards:
            existing = guards.get(guard.name)
            if existing is not None and _guard_facts(existing) != _guard_facts(guard):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-CONFLICTING-COMPILE-GUARD",
                        message=(
                            f"conflicting C++ compile guard {guard.name!r}"
                            f"{profile_label}"
                        ),
                        source=guard.source or extension.source,
                    )
                )
                continue
            required = macro_values.get(guard.macro)
            if required is not None and required[0] != guard.equals:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-CONFLICTING-COMPILE-GUARD-VALUE",
                        message=(
                            f"conflicting C++ compile guard values for {guard.macro}"
                            f"{profile_label}: {required[0]} and {guard.equals}"
                        ),
                        source=guard.source or extension.source,
                    )
                )
                continue
            guards[guard.name] = guard
            macro_values[guard.macro] = (guard.equals, guard)
    return CppCompileGuardResolution(
        guards=tuple(guards[name] for name in sorted(guards)),
        diagnostics=tuple(diagnostics),
    )


def validate_cpp_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for profile in profiles:
        family = profile.profile_family
        detection = None if family is None else family.backend("cpp").detection
        if (
            family is not None
            and detection is not None
            and detection not in CPP_PROFILE_DETECTION_KINDS
        ):
            backend_family = family.backend("cpp")
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-CPP-UNSUPPORTED-PROFILE-DETECTION",
                    message=(
                        f"C++ profile family {family.name!r} declares unsupported "
                        f"detection strategy {detection!r}; expected one of: "
                        + ", ".join(sorted(CPP_PROFILE_DETECTION_KINDS))
                    ),
                    source=backend_family.source or family.source,
                )
            )
        emitted_extensions = profile.used_extensions("cpp")
        for extension_name in emitted_extensions:
            extension = profile.extensions.get(extension_name)
            if extension is None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-CPP-MISSING-EXTENSION",
                        message=(
                            f"C++ profile {profile.profile.name!r} emits extension "
                            f"{extension_name!r} without typed extension metadata"
                        ),
                    )
                )
                continue
            if not extension.supports_backend("cpp"):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-UNSUPPORTED-EXTENSION-EMITTED",
                        message=(
                            f"C++ profile {profile.profile.name!r} contains extension "
                            f"{extension.name!r}, which is declared unsupported"
                        ),
                        source=extension.source,
                    )
                )
                continue
            bits = x86_register_bits(extension)
            if bits is not None and cpp_x86_register_helper(extension) is None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-UNSUPPORTED-X86-WIDTH",
                        message=(
                            f"extension {extension.name!r} declares C++ support with "
                            f"unsupported x86 register width {bits}; expected 128, 256, or 512"
                        ),
                        source=extension.source,
                    )
                )
            if (
                extension.vector_bits_kind == "scalable"
                and "cpp" not in extension.runtime_lane_count
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-MISSING-RUNTIME-LANE-COUNT",
                        message=(
                            f"scalable extension {extension.name!r} declares C++ support "
                            "without a runtime_lane_count entry"
                        ),
                        source=extension.source,
                    )
                )
        diagnostics.extend(
            resolve_cpp_compile_guards(
                emitted_extensions,
                profile.extensions,
                profile_name=profile.profile.name,
            ).diagnostics
        )
    return tuple(diagnostics)


def _guard_facts(guard: BackendCompileGuard) -> tuple[str, str, str | None, str | None]:
    return (guard.macro, guard.equals, guard.hint_flag, guard.diagnostic)


__all__ = (
    "CppCompileGuardResolution",
    "resolve_cpp_compile_guards",
    "validate_cpp_profiles",
)
