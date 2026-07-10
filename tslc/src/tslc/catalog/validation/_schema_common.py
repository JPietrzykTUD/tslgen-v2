"""Shared helpers for parsed-source schema validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence

from tslc.catalog.validation.source_spans import source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedTslAttribute,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
)

KNOWN_BOOLEAN_VALUES = frozenset({"true", "false"})


def validate_known_fields(
    fields: Sequence[ParsedTslField],
    allowed: frozenset[str],
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for field in fields:
        if field.key.text not in allowed:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-FIELD",
                    message=f"unknown field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                )
            )


def validate_backend_key_fields(
    fields: Sequence[ParsedTslField],
    backend_ids: Collection[str],
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for field in fields:
        if field.key.text not in backend_ids:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-BACKEND",
                    message=f"unknown backend field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                )
            )


def diagnose_duplicate_fields(
    fields: Sequence[ParsedTslField],
    diagnostics: list[Diagnostic],
    *,
    label: str,
    code: str = "TSL-CATALOG-DUPLICATE-FIELD",
) -> None:
    counts = Counter(field.key.text for field in fields)
    seen: set[str] = set()
    for field in fields:
        key = field.key.text
        if counts[key] < 2:
            continue
        if key in seen:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code=code,
                    message=f"duplicate {label} {key!r}",
                    source=source_span(field.source),
                )
            )
        seen.add(key)


def invalid_enum(
    diagnostics: list[Diagnostic],
    source: ParsedTslField | ParsedTslAttribute | None,
    value_label: str,
    allowed: Sequence[str],
) -> None:
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-INVALID-ENUM",
            message=f"invalid {value_label}; expected one of: {', '.join(allowed)}",
            source=(source_span(source.source) if source is not None else None),
        )
    )


def is_non_empty_scalar_list(field: ParsedTslField) -> bool:
    value = field.value
    return isinstance(value, ParsedTslListValue) and any(
        isinstance(item, ParsedTslScalarValue) for item in value.items
    )


def is_scalar_list(field: ParsedTslField) -> bool:
    value = field.value
    return isinstance(value, ParsedTslListValue) and all(
        isinstance(item, ParsedTslScalarValue) for item in value.items
    )


def unquote_key(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text
