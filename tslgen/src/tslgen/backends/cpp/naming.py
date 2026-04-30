from __future__ import annotations

from collections.abc import Iterable
import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result


_CPP_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_CPP_KEYWORDS = frozenset(
    {
        "alignas",
        "alignof",
        "and",
        "and_eq",
        "asm",
        "auto",
        "bitand",
        "bitor",
        "bool",
        "break",
        "case",
        "catch",
        "char",
        "char8_t",
        "char16_t",
        "char32_t",
        "class",
        "compl",
        "concept",
        "const",
        "consteval",
        "constexpr",
        "constinit",
        "const_cast",
        "continue",
        "co_await",
        "co_return",
        "co_yield",
        "decltype",
        "default",
        "delete",
        "do",
        "double",
        "dynamic_cast",
        "else",
        "enum",
        "explicit",
        "export",
        "extern",
        "false",
        "float",
        "for",
        "friend",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "mutable",
        "namespace",
        "new",
        "noexcept",
        "not",
        "not_eq",
        "nullptr",
        "operator",
        "or",
        "or_eq",
        "private",
        "protected",
        "public",
        "register",
        "reinterpret_cast",
        "requires",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "static_assert",
        "static_cast",
        "struct",
        "switch",
        "template",
        "this",
        "thread_local",
        "throw",
        "true",
        "try",
        "typedef",
        "typeid",
        "typename",
        "union",
        "unsigned",
        "using",
        "virtual",
        "void",
        "volatile",
        "wchar_t",
        "while",
        "xor",
        "xor_eq",
    }
)


def cpp_production_function_name(
    primitive_name: str,
    type_tag: str,
    *,
    location: SourceLocation | None = None,
) -> Result[str]:
    """Return the current production declaration function name.

    The Milestone 26 contract is intentionally conservative: no sanitization is
    performed, and the final derived name must already be a valid C++ identifier.
    """

    function_name = f"{primitive_name}_{type_tag}"
    if _is_cpp_identifier(function_name):
        return Result.ok(function_name)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-CPP-RENDER-DECLARATION-FUNCTION-NAME",
                "C++ production declaration function name "
                f"{function_name!r} derived from primitive {primitive_name!r} "
                f"and type tag {type_tag!r} is not a valid C++ identifier",
                location=location,
            ),
        )
    )


def cpp_production_parameter_names(
    parameter_names: Iterable[str],
    *,
    location: SourceLocation | None = None,
) -> Result[tuple[str, ...]]:
    names = tuple(parameter_names)
    invalid_names = tuple(name for name in names if not _is_cpp_identifier(name))
    if not invalid_names:
        return Result.ok(names)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-CPP-RENDER-DECLARATION-PARAMETER-NAME",
                "C++ production declaration parameter name(s) must be valid "
                f"C++ identifiers; invalid name(s): "
                f"{', '.join(repr(name) for name in invalid_names)}",
                location=location,
            ),
        )
    )


def _is_cpp_identifier(value: str) -> bool:
    return _CPP_IDENTIFIER_RE.fullmatch(value) is not None and value not in _CPP_KEYWORDS
