"""Schema validation for ``overload_axes:`` declarations."""

from __future__ import annotations

from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    is_non_empty_scalar_list,
    is_scalar_list,
    validate_known_fields,
)
from tslc.diagnostics import Diagnostic, RelatedLocation, diagnostic_at
from tslc.syntax.access import child, children, source_span
from tslc.syntax.ast import ParsedTslField, ParsedTslListValue, ParsedTslScalarValue


KNOWN_OVERLOAD_AXIS_FIELDS = frozenset({"values"})
KNOWN_OVERLOAD_VALUE_FIELDS = frozenset({"operand_kinds"})


def validate_overload_axes(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    axes = children(field)
    diagnose_duplicate_fields(
        axes,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-OVERLOAD-AXIS",
        label="overload axis",
    )
    for axis in axes:
        _validate_non_empty_name(axis, "overload axis", diagnostics)
        axis_fields = children(axis)
        validate_known_fields(
            axis_fields,
            KNOWN_OVERLOAD_AXIS_FIELDS,
            diagnostics,
            owner=f"overload axis {axis.key.text!r}",
        )
        diagnose_duplicate_fields(
            axis_fields,
            diagnostics,
            label=f"overload axis {axis.key.text!r} field",
        )
        values_field = child(axis, "values")
        values = children(values_field)
        if values_field is None or not values:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OVERLOAD-MISSING-VALUES",
                    message=(
                        f"overload axis {axis.key.text!r} must declare a non-empty "
                        "values map"
                    ),
                    source=source_span((values_field or axis).source),
                )
            )
            continue
        diagnose_duplicate_fields(
            values,
            diagnostics,
            code="TSL-CATALOG-DUPLICATE-OVERLOAD-VALUE",
            label=f"overload value in axis {axis.key.text!r}",
        )
        for value in values:
            _validate_value(axis.key.text, value, diagnostics)


def _validate_value(
    axis: str,
    value: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    _validate_non_empty_name(value, f"overload value in axis {axis!r}", diagnostics)
    value_fields = children(value)
    validate_known_fields(
        value_fields,
        KNOWN_OVERLOAD_VALUE_FIELDS,
        diagnostics,
        owner=f"overload value {axis}={value.key.text}",
    )
    diagnose_duplicate_fields(
        value_fields,
        diagnostics,
        label=f"overload value {axis}={value.key.text} field",
    )
    kinds_field = child(value, "operand_kinds")
    if (
        kinds_field is None
        or not is_non_empty_scalar_list(kinds_field)
        or not is_scalar_list(kinds_field)
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-MALFORMED-OPERAND-KINDS",
                message=(
                    f"overload value {axis}={value.key.text} must declare a non-empty "
                    "scalar operand_kinds list"
                ),
                source=source_span((kinds_field or value).source),
            )
        )
        return
    assert isinstance(kinds_field.value, ParsedTslListValue)
    seen: dict[str, ParsedTslScalarValue] = {}
    for item in kinds_field.value.items:
        if not isinstance(item, ParsedTslScalarValue):
            continue
        first = seen.get(item.text)
        if first is not None:
            first_span = source_span(first.source)
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OVERLOAD-DUPLICATE-OPERAND-KIND",
                    message=(
                        f"duplicate operand kind {item.text!r} for overload value "
                        f"{axis}={value.key.text}"
                    ),
                    source=source_span(item.source),
                    related=(
                        ()
                        if first_span is None
                        else (
                            RelatedLocation(
                                message="first operand kind is here",
                                span=first_span,
                            ),
                        )
                    ),
                )
            )
        else:
            seen[item.text] = item
        if not DEFAULT_SIGNATURE_KINDS.supports(item.text):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OVERLOAD-UNKNOWN-OPERAND-KIND",
                    message=(
                        f"unknown signature kind {item.text!r} for overload value "
                        f"{axis}={value.key.text}"
                    ),
                    source=source_span(item.source),
                    help=(
                        "known signature kinds: "
                        + ", ".join(sorted(DEFAULT_SIGNATURE_KINDS.supported_kinds))
                    ),
                )
            )


def _validate_non_empty_name(
    field: ParsedTslField,
    label: str,
    diagnostics: list[Diagnostic],
) -> None:
    if field.key.text.strip():
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-OVERLOAD-EMPTY-NAME",
            message=f"{label} must have a non-empty name",
            source=source_span(field.source),
        )
    )


__all__ = (
    "KNOWN_OVERLOAD_AXIS_FIELDS",
    "KNOWN_OVERLOAD_VALUE_FIELDS",
    "validate_overload_axes",
)
