"""Exact stable declarations owned by the static Rust substrate."""

from __future__ import annotations

from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_public_declarations import RustPublicDeclaration
from tslc.catalog.preconditions import PreconditionErrorKind


def rust_precondition_error_declaration() -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity="crate::tsl_core::PreconditionError#definition",
        name="PreconditionError",
        owner="crate::tsl_core",
        reachability=("crate", "tsl_core"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TYPE,
        overload="checked-error-enum",
        visibility="pub",
        attributes=(
            "#[derive(Clone, Copy, Debug, Eq, PartialEq)]",
            "#[non_exhaustive]",
        ),
        type_form="enum",
        enumerators=tuple(
            rust_precondition_error(error, prefix="")
            for error in PreconditionErrorKind
        ),
    )


def rust_static_declaration_holes() -> dict[str, str]:
    declaration = rust_precondition_error_declaration()
    return {
        "precondition_error_declaration": "\n".join(
            (*declaration.attributes, declaration.render_head())
        ),
        **{
            f"precondition_error_variant_{error.value}": spelling
            for error, spelling in zip(
                PreconditionErrorKind,
                declaration.enumerators,
                strict=True,
            )
        },
    }


__all__ = (
    "rust_precondition_error_declaration",
    "rust_static_declaration_holes",
)
