from __future__ import annotations

from collections.abc import Iterable
import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result


_RUST_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_RUST_KEYWORDS = frozenset(
    {
        "Self",
        "abstract",
        "as",
        "async",
        "await",
        "become",
        "box",
        "break",
        "const",
        "continue",
        "crate",
        "do",
        "dyn",
        "else",
        "enum",
        "extern",
        "false",
        "final",
        "fn",
        "for",
        "gen",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "macro",
        "match",
        "mod",
        "move",
        "mut",
        "override",
        "priv",
        "pub",
        "ref",
        "return",
        "self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "try",
        "type",
        "typeof",
        "unsafe",
        "unsized",
        "use",
        "virtual",
        "where",
        "while",
        "yield",
    }
)


def rust_production_function_name(
    primitive_name: str,
    type_tag: str,
    *,
    location: SourceLocation | None = None,
) -> Result[str]:
    """Return the current Rust production signature function name.

    The Milestone 31 contract performs no raw-identifier conversion,
    sanitization, or mangling. The derived name must already be a valid Rust
    identifier for this narrow signature slice.
    """

    function_name = f"{primitive_name}_{type_tag}"
    if _is_rust_identifier(function_name):
        return Result.ok(function_name)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-RUST-RENDER-DECLARATION-FUNCTION-NAME",
                "Rust production declaration function name "
                f"{function_name!r} derived from primitive {primitive_name!r} "
                f"and type tag {type_tag!r} is not a valid Rust identifier",
                location=location,
            ),
        )
    )


def rust_production_parameter_names(
    parameter_names: Iterable[str],
    *,
    location: SourceLocation | None = None,
) -> Result[tuple[str, ...]]:
    names = tuple(parameter_names)
    invalid_names = tuple(name for name in names if not _is_rust_identifier(name))
    if not invalid_names:
        return Result.ok(names)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-RUST-RENDER-DECLARATION-PARAMETER-NAME",
                "Rust production declaration parameter name(s) must be valid "
                f"Rust identifiers; invalid name(s): "
                f"{', '.join(repr(name) for name in invalid_names)}",
                location=location,
            ),
        )
    )


def _is_rust_identifier(value: str) -> bool:
    return (
        _RUST_IDENTIFIER_RE.fullmatch(value) is not None
        and value not in _RUST_KEYWORDS
        and value != "_"
    )
