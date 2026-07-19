"""Pre-render validation for Rust backend emission facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.rust_const_args import RUST_CONST_ARG_WRAPPERS
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.lower.lowerer import varying_positions

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile


def validate_rust_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for profile in profiles:
        by_primitive = profile.specializations("rust")
        for extension_name in profile.used_extensions("rust"):
            extension = profile.extensions.get(extension_name)
            if extension is None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-RUST-MISSING-EXTENSION",
                        message=(
                            f"Rust profile {profile.profile.name!r} emits extension "
                            f"{extension_name!r} without typed extension metadata"
                        ),
                    )
                )
            elif not extension.supports_backend("rust"):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-RUST-UNSUPPORTED-EXTENSION-EMITTED",
                        message=(
                            f"Rust profile {profile.profile.name!r} contains extension "
                            f"{extension.name!r}, which is declared unsupported"
                        ),
                        source=extension.source,
                    )
                )
        for primitive_name, specializations in by_primitive.items():
            positions = varying_positions(specializations)
            if len(positions) > 1:
                # Rust overload wrappers dispatch exactly one varying argument
                # position through an arg-trait; reject anything wider before
                # rendering instead of silently emitting a wrapper that ignores
                # the remaining varying positions. C++ handles the general case.
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD",
                        message=(
                            f"Rust primitive {primitive_name!r} in profile "
                            f"{profile.profile.name!r} overloads at parameter "
                            f"positions {', '.join(str(i) for i in positions)}; "
                            "the Rust backend dispatches exactly one varying "
                            "argument position"
                        ),
                        source=specializations[0].source,
                    )
                )
            for specialization in specializations:
                const_types = (
                    *((specialization.immediate[1],) if specialization.immediate else ()),
                    *(item[1] for item in specialization.generic_params),
                )
                unsupported = tuple(
                    sorted(set(const_types) - RUST_CONST_ARG_WRAPPERS.keys())
                )
                if unsupported:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-BACKEND-RUST-UNSUPPORTED-CONST-ARG-TYPE",
                            message=(
                                f"Rust primitive {primitive_name!r} in profile "
                                f"{profile.profile.name!r} uses unsupported const argument "
                                f"type(s): {', '.join(unsupported)}"
                            ),
                            source=specialization.source,
                        )
                    )
    return tuple(diagnostics)


__all__ = ("validate_rust_profiles",)
