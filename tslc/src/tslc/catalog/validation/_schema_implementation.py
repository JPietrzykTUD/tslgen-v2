"""Schema validation for primitive implementation body and safety metadata."""

from __future__ import annotations

import re

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
_KNOWN_VARIANT_SAFETY_FIELDS = frozenset({"internal_unsafe", "reasons"})
_KNOWN_VARIANT_FIELDS = frozenset({"safety", "tsil", "tsl"})
_VARIANT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KNOWN_SELECTOR_METADATA_FIELDS = frozenset(
    {"implementation", "requires", "safety", "unroll_variants", "variants"}
)
_KNOWN_TARGET_CONSTRAINT_FIELDS = frozenset(
    {"family", "width", "safety", "implementation", "variants"}
)


def known_implementation_selector_fields() -> frozenset[str]:
    """Return the metadata keys accepted beneath an implementation selector."""

    return _KNOWN_SELECTOR_METADATA_FIELDS


def validate_implementation_safety(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    def walk(entry: ParsedImplementationSelectorEntry) -> None:
        if entry.selector.text == "where":
            _validate_target_constraint(entry, diagnostics)
        else:
            _validate_selector_metadata(entry, diagnostics)
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
            elif field.key.text == "variants":
                if not entry.body_envelopes:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-MALFORMED-VARIANT",
                            message=(
                                "implementation variants must be declared on the "
                                "same selector entry as an implementation body"
                            ),
                            source=source_span(field.source),
                        )
                    )
                _validate_variants_field(field, diagnostics)
        for child_entry in entry.children:
            walk(child_entry)

    for entry in declaration.impl_entries:
        walk(entry)


def _validate_selector_metadata(
    entry: ParsedImplementationSelectorEntry, diagnostics: list[Diagnostic]
) -> None:
    """Reject scalar metadata that cannot be a nested selector block."""

    scalar_unknown_fields = tuple(
        field
        for field in entry.fields
        if field.key.text not in _KNOWN_SELECTOR_METADATA_FIELDS and not children(field)
    )
    validate_known_fields(
        scalar_unknown_fields,
        _KNOWN_SELECTOR_METADATA_FIELDS,
        diagnostics,
        owner=f"implementation selector {entry.selector.text!r}",
    )


def _validate_target_constraint(
    entry: ParsedImplementationSelectorEntry, diagnostics: list[Diagnostic]
) -> None:
    validate_known_fields(
        entry.fields,
        _KNOWN_TARGET_CONSTRAINT_FIELDS,
        diagnostics,
        owner="target constraint",
    )
    for name, allowed in (
        ("family", frozenset({"same_as"})),
        ("width", frozenset({"smaller_than", "larger_than"})),
    ):
        matches = tuple(field for field in entry.fields if field.key.text == name)
        diagnose_duplicate_fields(matches, diagnostics, label=f"target constraint {name}")
        if not matches:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-TARGET-CONSTRAINT",
                    message=f"target constraint requires a {name!r} relation",
                    source=source_span(entry.source),
                )
            )
            continue
        value = field_text(matches[0])
        if value not in allowed:
            invalid_enum(
                diagnostics,
                matches[0],
                f"target constraint {name} value {value!r}",
                sorted(allowed),
            )


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
    *,
    owner: str = "implementation safety",
    allowed_fields: frozenset[str] = _KNOWN_SAFETY_FIELDS,
) -> None:
    field_children = children(field)
    if not field_children:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-SAFETY",
                message=f"{owner} must contain safety fields",
                source=source_span(field.source),
            )
        )
        return
    validate_known_fields(
        field_children,
        allowed_fields,
        diagnostics,
        owner=owner,
    )
    diagnose_duplicate_fields(
        field_children, diagnostics, label=f"{owner} field"
    )
    for name in ("internal_unsafe", "caller_unsafe"):
        if name not in allowed_fields:
            continue
        bool_field = child(field, name)
        value = field_text(bool_field)
        if bool_field is not None and value not in KNOWN_BOOLEAN_VALUES:
            invalid_enum(
                diagnostics,
                bool_field,
                f"{owner} {name} value {value!r}",
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
                message=f"{owner} reasons must be a scalar list",
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
                    message=f"{owner} reasons must be scalar labels",
                    source=source_span(item.source),
                )
            )


def _validate_variants_field(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    variant_fields = children(field)
    diagnose_duplicate_fields(
        variant_fields, diagnostics, label="implementation variant"
    )
    for variant in variant_fields:
        if _VARIANT_NAME_RE.fullmatch(variant.key.text) is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-VARIANT",
                    message=(
                        f"implementation variant name {variant.key.text!r} must be "
                        "an identifier"
                    ),
                    source=source_span(variant.key.source),
                )
            )
        variant_children = children(variant)
        validate_known_fields(
            variant_children,
            _KNOWN_VARIANT_FIELDS,
            diagnostics,
            owner=f"implementation variant {variant.key.text!r}",
        )
        diagnose_duplicate_fields(
            tuple(child for child in variant_children if child.key.text == "safety"),
            diagnostics,
            label="implementation variant safety block",
        )
        bodies = tuple(
            child for child in variant_children if child.key.text in {"tsil", "tsl"}
        )
        if len(bodies) != 1:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-VARIANT",
                    message=(
                        f"implementation variant {variant.key.text!r} must contain "
                        "exactly one quoted tsil/tsl body"
                    ),
                    source=source_span(variant.source),
                )
            )
        for safety in (child for child in variant_children if child.key.text == "safety"):
            _validate_safety_field(
                safety,
                diagnostics,
                owner=f"implementation variant {variant.key.text!r} safety",
                allowed_fields=_KNOWN_VARIANT_SAFETY_FIELDS,
            )
        for body in bodies:
            _validate_variant_body_field(variant, body, diagnostics)


def _validate_variant_body_field(
    variant: ParsedTslField,
    body: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    if (
        not isinstance(body.value, ParsedTslScalarValue)
        or body.value.quote_form not in {"inline", "multiline"}
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-VARIANT",
                message=(
                    f"implementation variant {variant.key.text!r} body must be a "
                    "quoted tsil/tsl field"
                ),
                source=source_span(body.source),
            )
        )
