"""Schema validation for primitive implementation body and safety metadata."""

from __future__ import annotations

from tslc.catalog.validation._schema_common import (
    KNOWN_BOOLEAN_VALUES,
    diagnose_duplicate_fields,
    invalid_enum,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import child, children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
)

_KNOWN_SAFETY_FIELDS = frozenset({"internal_unsafe", "caller_unsafe", "reasons"})


def validate_implementation_safety(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    def walk(entry: ParsedImplementationSelectorEntry) -> None:
        diagnose_duplicate_fields(
            tuple(field for field in entry.fields if field.key.text == "safety"),
            diagnostics,
            label="implementation safety block",
        )
        for field in entry.fields:
            if field.key.text == "safety":
                _validate_safety_field(field, diagnostics)
            elif field.key.text == "implementation":
                _validate_implementation_body_field(field, diagnostics)
        for child_entry in entry.children:
            walk(child_entry)

    for entry in declaration.impl_entries:
        walk(entry)


def _validate_implementation_body_field(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    body_children = children(field)
    validate_known_fields(
        body_children,
        frozenset({"tsil", "tsl"}),
        diagnostics,
        owner="implementation body",
    )
    for body in body_children:
        if body.key.text not in {"tsil", "tsl"}:
            continue
        if (
            not isinstance(body.value, ParsedTslScalarValue)
            or body.value.quote_form not in {"inline", "multiline"}
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-IMPLEMENTATION",
                    message="implementation body must be a quoted tsil/tsl field",
                    source=source_span(body.source),
                )
            )


def _validate_safety_field(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    field_children = children(field)
    if not field_children:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-SAFETY",
                message="implementation safety must contain safety fields",
                source=source_span(field.source),
            )
        )
        return
    validate_known_fields(
        field_children,
        _KNOWN_SAFETY_FIELDS,
        diagnostics,
        owner="implementation safety",
    )
    diagnose_duplicate_fields(
        field_children, diagnostics, label="implementation safety field"
    )
    for name in ("internal_unsafe", "caller_unsafe"):
        bool_field = child(field, name)
        value = field_text(bool_field)
        if bool_field is not None and value not in KNOWN_BOOLEAN_VALUES:
            invalid_enum(
                diagnostics,
                bool_field,
                f"implementation safety {name} value {value!r}",
                sorted(KNOWN_BOOLEAN_VALUES),
            )
    reasons = child(field, "reasons")
    if reasons is None:
        return
    if not isinstance(reasons.value, ParsedTslListValue):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-SAFETY",
                message="implementation safety reasons must be a scalar list",
                source=source_span(reasons.source),
            )
        )
        return
    for item in reasons.value.items:
        if not isinstance(item, ParsedTslScalarValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-SAFETY",
                    message="implementation safety reasons must be scalar labels",
                    source=source_span(item.source),
                )
            )
