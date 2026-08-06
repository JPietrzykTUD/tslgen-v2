"""Validation for implementation ``requires`` shapes."""

from __future__ import annotations

from collections.abc import Collection, Mapping

from tslc.syntax.access import children, source_span
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
    known_target_features: Collection[str] = (),
    known_compiler_capabilities: Mapping[str, Collection[str]] | None = None,
) -> None:
    def walk(entry: ParsedImplementationSelectorEntry) -> None:
        for value in entry.requires:
            _validate_requires_value(
                value,
                diagnostics,
                known_target_features,
                known_compiler_capabilities or {},
            )
        for child in entry.children:
            walk(child)

    for entry in declaration.impl_entries:
        walk(entry)


def _validate_requires_value(
    value: ParsedRequiresValue,
    diagnostics: list[Diagnostic],
    known_target_features: Collection[str],
    known_compiler_capabilities: Mapping[str, Collection[str]],
) -> None:
    field = value.field
    if isinstance(field.value, ParsedTslListValue):
        _validate_flag_list(field.value, diagnostics, known_target_features)
        return
    field_children = children(field)
    if not field_children:
        _malformed_requires(diagnostics, field, "requires must be a flag list or scoped map")
        return
    for child in field_children:
        if child.key.text == "target_features":
            if not isinstance(child.value, ParsedTslListValue):
                _malformed_requires(
                    diagnostics,
                    child,
                    "requires target_features must be a feature list",
                )
            else:
                _validate_flag_list(child.value, diagnostics, known_target_features)
            continue
        if child.key.text == "compiler":
            _validate_compiler_requirements(
                child,
                diagnostics,
                known_compiler_capabilities,
            )
            continue
        if isinstance(child.value, ParsedTslListValue):
            _validate_flag_list(child.value, diagnostics, known_target_features)
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
            _validate_flag_list(grandchild.value, diagnostics, known_target_features)


def _validate_compiler_requirements(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
    known_compiler_capabilities: Mapping[str, Collection[str]],
) -> None:
    backends = children(field)
    if not backends:
        _malformed_requires(
            diagnostics,
            field,
            "requires compiler must map a backend to capabilities",
        )
        return
    for backend in backends:
        known = known_compiler_capabilities.get(backend.key.text)
        if known_compiler_capabilities and known is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-COMPILER-BACKEND",
                    message=(
                        f"requires compiler uses unknown backend {backend.key.text!r}; "
                        f"expected one of: {', '.join(sorted(known_compiler_capabilities))}"
                    ),
                    source=source_span(backend.source),
                )
            )
        backend_fields = children(backend)
        if not backend_fields:
            _malformed_requires(
                diagnostics,
                backend,
                f"requires compiler backend {backend.key.text!r} must contain capabilities",
            )
            continue
        for capability_field in backend_fields:
            if (
                capability_field.key.text != "capabilities"
                or not isinstance(capability_field.value, ParsedTslListValue)
            ):
                _malformed_requires(
                    diagnostics,
                    capability_field,
                    f"requires compiler backend {backend.key.text!r} accepts only a capabilities list",
                )
                continue
            _validate_capability_list(
                capability_field.value,
                backend.key.text,
                diagnostics,
                known,
            )


def _validate_capability_list(
    value: ParsedTslListValue,
    backend_id: str,
    diagnostics: list[Diagnostic],
    known_capabilities: Collection[str] | None,
) -> None:
    for item in value.items:
        if not isinstance(item, ParsedTslScalarValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-REQUIRES",
                    message="compiler capabilities must be scalar capability names",
                    source=source_span(item.source),
                )
            )
        elif known_capabilities is not None and item.text not in known_capabilities:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-COMPILER-CAPABILITY",
                    message=(
                        f"requires compiler backend {backend_id!r} uses unknown capability "
                        f"{item.text!r}; expected one of: "
                        f"{', '.join(sorted(known_capabilities)) or '(none)'}"
                    ),
                    source=source_span(item.source),
                )
            )


def _validate_flag_list(
    value: ParsedTslListValue,
    diagnostics: list[Diagnostic],
    known_target_features: Collection[str],
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
        elif known_target_features and item.text not in known_target_features:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-TARGET-FEATURE",
                    message=(
                        f"requires uses unknown target feature {item.text!r}; "
                        f"expected one of: {', '.join(sorted(known_target_features))}"
                    ),
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
