"""Pre-render validation for C++ backend emission facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.cpp_compiler_capabilities import (
    CppCompilerCapability,
    cpp_compiler_capability,
    cpp_extension_header_group,
)
from tslc.backend.cpp_detection import (
    CPP_PROFILE_AUTO_GATES,
    CPP_PROFILE_DETECTION_KINDS,
)
from tslc.backend.target_capability import (
    cpp_width_indexed_register_helper,
    width_indexed_register_bits,
)
from tslc.catalog.model import Extension
from tslc.diagnostics import Diagnostic, diagnostic_at

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile


def validate_cpp_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for profile in profiles:
        auto_gate = profile.profile.auto_detect_gate
        if (
            auto_gate is not None
            and auto_gate not in CPP_PROFILE_AUTO_GATES.gate_ids
        ):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-CPP-UNSUPPORTED-AUTO-DETECT-GATE",
                    message=(
                        f"C++ profile {profile.profile.name!r} declares unsupported "
                        f"auto-detection gate {auto_gate!r}; expected one of: "
                        + ", ".join(sorted(CPP_PROFILE_AUTO_GATES.gate_ids))
                    ),
                )
            )
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
            capabilities: list[CppCompilerCapability] = []
            for capability_id in (
                ()
                if (metadata := extension.metadata.backend.get("cpp")) is None
                else metadata.compiler_capabilities
            ):
                try:
                    capabilities.append(cpp_compiler_capability(capability_id))
                except KeyError:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-BACKEND-CPP-UNKNOWN-COMPILER-CAPABILITY",
                            message=(
                                f"extension {extension.name!r} requires unknown C++ "
                                f"compiler capability {capability_id!r}"
                            ),
                            source=extension.source,
                        )
                    )
            header_groups = {
                capability.header_group
                for capability in capabilities
                if capability.header_group is not None
            }
            if len(header_groups) > 1:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-INCOMPATIBLE-HEADER-GROUPS",
                        message=(
                            f"extension {extension.name!r} requires incompatible C++ "
                            f"header groups {sorted(header_groups)}"
                        ),
                        source=extension.source,
                    )
                )
            if (
                extension.mask_policy.kind == "exact_lane_bitmask"
                and extension.mask_policy.spelling("cpp") is None
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-CPP-MISSING-MASK-SPELLING",
                        message=(
                            "mask_type_policy kind 'exact_lane_bitmask' requires "
                            "backend_spelling.cpp when C++ is supported"
                        ),
                        source=extension.mask_policy.source or extension.source,
                    )
                )
            bits = width_indexed_register_bits(extension)
            if (
                bits is not None
                and cpp_width_indexed_register_helper(extension) is None
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code=(
                            "TSL-BACKEND-CPP-UNSUPPORTED-"
                            "WIDTH-INDEXED-REGISTER-WIDTH"
                        ),
                        message=(
                            f"extension {extension.name!r} declares C++ support with "
                            "unsupported width-indexed register width "
                            f"{bits}; expected 128, 256, or 512"
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
    return tuple(diagnostics)


__all__ = (
    "validate_cpp_profiles",
)
