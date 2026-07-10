"""Pre-render validation for Rust backend emission facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.rust_const_args import RUST_CONST_ARG_WRAPPERS
from tslc.diagnostics import Diagnostic, diagnostic_at

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
