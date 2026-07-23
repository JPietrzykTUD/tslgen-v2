"""Shared closed-contract validation helpers for primitive semantic facts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable
from enum import StrEnum
from typing import TypeVar

from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at
from tslc.syntax.access import children, field_text, source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslScalarValue,
)


EnumValue = TypeVar("EnumValue", bound=StrEnum)


def closed_members(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField,
    known: Collection[str],
    label: str,
    diagnostics: list[Diagnostic],
) -> dict[str, ParsedTslField]:
    members = children(field)
    duplicate_members(
        declaration,
        members,
        f"{label} field",
        f"TSL-CATALOG-DUPLICATE-{label.upper()}-FIELD",
        diagnostics,
    )
    for member in members:
        if member.key.text not in known:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code=f"TSL-CATALOG-UNKNOWN-{label.upper()}-FIELD",
                    message=(
                        f"unknown {label} field {member.key.text!r} on primitive "
                        f"{declaration.name!r}; expected {joined(known)}"
                    ),
                    source=source_span(member.key.source),
                )
            )
    by_name = {member.key.text: member for member in members}
    for required in sorted(known):
        if required not in by_name:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code=f"TSL-CATALOG-MISSING-{label.upper()}-FIELD",
                    message=(
                        f"primitive {declaration.name!r} {label} contract must "
                        f"declare {required!r}"
                    ),
                    source=source_span(field.source),
                )
            )
    return by_name


def enum_member(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField | None,
    enum_type: type[EnumValue],
    values: tuple[str, ...],
    label: str,
    code: str,
    diagnostics: list[Diagnostic],
) -> EnumValue | None:
    if field is None:
        return None
    text = field_text(field)
    try:
        return enum_type(text or "")
    except ValueError:
        diagnostics.append(
            invalid_enum(declaration, field, label, text, values, code)
        )
        return None


def duplicate_members(
    declaration: ParsedPrimitiveDeclaration,
    members: tuple[ParsedTslField, ...],
    label: str,
    code: str,
    diagnostics: list[Diagnostic],
) -> None:
    counts = Counter(member.key.text for member in members)
    first: dict[str, ParsedTslField] = {}
    for member in members:
        if counts[member.key.text] < 2:
            continue
        previous = first.get(member.key.text)
        if previous is None:
            first[member.key.text] = member
            continue
        previous_span = source_span(previous.key.source)
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code=code,
                message=(
                    f"duplicate {label} {member.key.text!r} on primitive "
                    f"{declaration.name!r}"
                ),
                source=source_span(member.key.source),
                related=(
                    ()
                    if previous_span is None
                    else (
                        RelatedLocation(
                            message=f"first {label} is here",
                            span=previous_span,
                        ),
                    )
                ),
            )
        )


def invalid_enum(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField,
    label: str,
    value: str | None,
    values: Collection[str],
    code: str,
    *,
    source: SourceSpan | None = None,
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code=code,
        message=(
            f"unknown {label} {value!r} on primitive {declaration.name!r}; "
            f"expected {joined(values)}"
        ),
        source=source or member_value_source(field) or source_span(field.source),
    )


def member_value_source(field: ParsedTslField | None) -> SourceSpan | None:
    if field is None or not isinstance(field.value, ParsedTslScalarValue):
        return None
    return scalar_source(field.value)


def scalar_source(value: ParsedTslScalarValue) -> SourceSpan | None:
    return source_span(value.payload_source or value.source)


def joined(values: Iterable[object]) -> str:
    return ", ".join(repr(str(value)) for value in sorted(values, key=str))


__all__ = (
    "closed_members",
    "duplicate_members",
    "enum_member",
    "invalid_enum",
    "joined",
    "member_value_source",
    "scalar_source",
)
