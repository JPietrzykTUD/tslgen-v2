"""Shared helpers for parsed-source schema validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from difflib import get_close_matches

from tslc.syntax.access import source_span
from tslc.diagnostics import Diagnostic, RelatedLocation, diagnostic_at
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
            suggestion = _nearest(field.key.text, allowed)
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-FIELD",
                    message=f"unknown field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                    help=(f"did you mean {suggestion!r}?" if suggestion else None),
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
            suggestion = _nearest(field.key.text, backend_ids)
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-BACKEND",
                    message=f"unknown backend field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                    help=(f"did you mean {suggestion!r}?" if suggestion else None),
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
    first_by_key: dict[str, ParsedTslField] = {}
    seen: set[str] = set()
    for field in fields:
        key = field.key.text
        if counts[key] < 2:
            continue
        if key in seen:
            first = first_by_key[key]
            first_span = source_span(first.source)
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code=code,
                    message=f"duplicate {label} {key!r}",
                    source=source_span(field.source),
                    related=(
                        ()
                        if first_span is None
                        else (
                            RelatedLocation(
                                message=f"first {label} {key!r} is here",
                                span=first_span,
                            ),
                        )
                    ),
                )
            )
        else:
            first_by_key[key] = field
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
            help=f"allowed values: {', '.join(allowed)}",
        )
    )


def _nearest(value: str, choices: Collection[str]) -> str | None:
    matches = get_close_matches(value, sorted(choices), n=1, cutoff=0.6)
    return matches[0] if matches else None


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
