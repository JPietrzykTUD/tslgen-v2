"""Validation for implementation ``requires`` shapes."""

from __future__ import annotations

from tslc.catalog.validation.source_spans import children, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedRequiresValue,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
)


def validate_requires(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    def walk(entry: ParsedImplementationSelectorEntry) -> None:
        for value in entry.requires:
            _validate_requires_value(value, diagnostics)
        for child in entry.children:
            walk(child)

    for entry in declaration.impl_entries:
        walk(entry)


def _validate_requires_value(
    value: ParsedRequiresValue,
    diagnostics: list[Diagnostic],
) -> None:
    field = value.field
    if isinstance(field.value, ParsedTslListValue):
        _validate_flag_list(field.value, diagnostics)
        return
    field_children = children(field)
    if not field_children:
        _malformed_requires(diagnostics, field, "requires must be a flag list or scoped map")
        return
    for child in field_children:
        if isinstance(child.value, ParsedTslListValue):
            _validate_flag_list(child.value, diagnostics)
            continue
        nested = children(child)
        if not nested:
            _malformed_requires(
                diagnostics,
                child,
                f"requires entry {child.key.text!r} must contain a flag list or extension-scoped type-group lists",
            )
            continue
        for grandchild in nested:
            if not isinstance(grandchild.value, ParsedTslListValue):
                _malformed_requires(
                    diagnostics,
                    grandchild,
                    f"requires entry {grandchild.key.text!r} must contain a flag list",
                )
                continue
            _validate_flag_list(grandchild.value, diagnostics)


def _validate_flag_list(
    value: ParsedTslListValue,
    diagnostics: list[Diagnostic],
) -> None:
    for item in value.items:
        if not isinstance(item, ParsedTslScalarValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-REQUIRES",
                    message="requires flags must be scalar feature names",
                    source=source_span(item.source),
                )
            )


def _malformed_requires(
    diagnostics: list[Diagnostic],
    field: ParsedTslField,
    message: str,
) -> None:
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-MALFORMED-REQUIRES",
            message=message,
            source=source_span(field.source),
        )
    )
