"""Target spellings for the language-neutral checked-API error vocabulary."""

from __future__ import annotations

from tslc.catalog.preconditions import PreconditionErrorKind


def cpp_precondition_error(
    error: PreconditionErrorKind,
    *,
    qualified: bool = True,
) -> str:
    prefix = "::tsl::precondition_error::" if qualified else ""
    return f"{prefix}{error.value}"


def rust_precondition_error(
    error: PreconditionErrorKind,
    *,
    prefix: str = "PreconditionError::",
) -> str:
    variant = "".join(part.capitalize() for part in error.value.split("_"))
    return f"{prefix}{variant}"


__all__ = ("cpp_precondition_error", "rust_precondition_error")
