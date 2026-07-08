"""Schema validation for primitive declarations."""

from __future__ import annotations

import re

from tslc.catalog.validation._schema_common import (
    KNOWN_BOOLEAN_VALUES,
    diagnose_duplicate_fields,
    invalid_enum,
    is_non_empty_scalar_list,
    unquote_key,
    validate_known_fields,
)
from tslc.catalog.validation._schema_implementation import (
    validate_implementation_safety,
)
from tslc.catalog.validation._schema_tests import validate_tests
from tslc.catalog.validation.requires_validation import validate_requires
from tslc.catalog.validation.source_spans import (
    attribute_scalar_text,
    child,
    children,
    field_text,
    source_span,
)
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
)

_KNOWN_GENERIC_PARAM_KINDS = frozenset({"bool", "int", "simd_type"})
_KNOWN_IMMEDIATE_DISPATCH = frozenset({"literal_match"})
_KNOWN_PRIMITIVE_FIELDS = frozenset(
    {
        "brief_description",
        "cross_lane",
        "detailed_description",
        "generic_params",
        "impls",
        "operation",
        "param_types",
        "params",
        "return_type",
        "semantics",
        "sImm_type",
        "tests",
    }
)
_KNOWN_PRIMITIVE_ATTRIBUTES = {
    "aligned": frozenset({"true", "false", "*"}),
    "arg_count": frozenset({"return_vector_length"}),
    "cast": frozenset({"reinterpret", "convert"}),
    "direction": frozenset({"up", "down"}),
    "mask": frozenset({"zero", "pass_through"}),
    "op": frozenset({"pack", "expand", "keep"}),
    "packed": frozenset({"true", "false", "*"}),
    "value": frozenset({"zero", "undef", "all"}),
}
_PARAM_TYPE_CONDITION_RE = re.compile(r"^if\s+([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_]+)$")


def validate_primitive(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    fields = tuple(field.field for field in declaration.fields)
    validate_known_fields(
        fields,
        _KNOWN_PRIMITIVE_FIELDS,
        diagnostics,
        owner=f"primitive {declaration.name!r}",
    )
    diagnose_duplicate_fields(fields, diagnostics, label="primitive field")
    for cross_lane_field in declaration.fields_by_name("cross_lane"):
        value = field_text(cross_lane_field.field)
        if value not in KNOWN_BOOLEAN_VALUES:
            invalid_enum(
                diagnostics,
                cross_lane_field.field,
                f"primitive {declaration.name!r} cross_lane value {value!r}",
                sorted(KNOWN_BOOLEAN_VALUES),
            )
    _validate_attributes(declaration.attributes, diagnostics)
    _validate_generic_params(declaration, diagnostics)
    _validate_immediate_params(declaration, diagnostics)
    _validate_param_types(declaration, diagnostics)
    validate_implementation_safety(declaration, diagnostics)
    _validate_return_type(declaration, diagnostics)
    validate_tests(declaration, diagnostics)
    validate_requires(declaration, diagnostics)


def _validate_attributes(
    attributes: tuple[ParsedTslAttribute, ...],
    diagnostics: list[Diagnostic],
) -> None:
    seen: set[tuple[str, str | None]] = set()
    for attribute in attributes:
        key = attribute.key.text
        key_arg = attribute.key_argument.text if attribute.key_argument is not None else None
        identity = (key, key_arg)
        if identity in seen:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-DUPLICATE-ATTRIBUTE",
                    message=f"duplicate primitive attribute {key!r}",
                    source=source_span(attribute.source),
                )
            )
        seen.add(identity)
        allowed = _KNOWN_PRIMITIVE_ATTRIBUTES.get(key)
        if allowed is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-ATTRIBUTE",
                    message=f"unknown primitive attribute {key!r}",
                    source=source_span(attribute.source),
                )
            )
            continue
        value = attribute_scalar_text(attribute)
        if value is not None and value not in allowed:
            invalid_enum(
                diagnostics,
                attribute,
                f"primitive attribute {key!r} value {value!r}",
                sorted(allowed),
            )


def _validate_generic_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("generic_params"):
        diagnose_duplicate_fields(children(field.field), diagnostics, label="generic parameter")
        for entry in children(field.field):
            validate_known_fields(
                children(entry),
                frozenset({"kind", "default", "base_types", "specialize_base"}),
                diagnostics,
                owner=f"generic parameter {entry.key.text!r}",
            )
            kind_field = child(entry, "kind")
            kind = field_text(kind_field)
            if kind is not None and kind not in _KNOWN_GENERIC_PARAM_KINDS:
                invalid_enum(
                    diagnostics,
                    kind_field,
                    f"generic parameter kind {kind!r}",
                    sorted(_KNOWN_GENERIC_PARAM_KINDS),
                )
            specialize_base = child(entry, "specialize_base")
            if specialize_base is not None:
                specialize_value = field_text(specialize_base)
                if specialize_value not in KNOWN_BOOLEAN_VALUES:
                    invalid_enum(
                        diagnostics,
                        specialize_base,
                        f"generic parameter {entry.key.text!r} specialize_base value "
                        f"{specialize_value!r}",
                        sorted(KNOWN_BOOLEAN_VALUES),
                    )
                if kind != "simd_type":
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                            message=(
                                f"generic parameter {entry.key.text!r} uses specialize_base, "
                                "but specialize_base is allowed only for kind 'simd_type'"
                            ),
                            source=source_span(specialize_base.source),
                        )
                    )
            base_types = child(entry, "base_types")
            if (
                specialize_base is not None
                and field_text(specialize_base) == "true"
                and base_types is None
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {entry.key.text!r} uses specialize_base, "
                            "but specialized simd_type parameters must declare base_types"
                        ),
                        source=source_span(specialize_base.source),
                    )
                )
            if base_types is None:
                continue
            if kind != "simd_type":
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {entry.key.text!r} uses base_types, "
                            "but base_types is allowed only for kind 'simd_type'"
                        ),
                        source=source_span(base_types.source),
                    )
                )
            if not is_non_empty_scalar_list(base_types):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {entry.key.text!r} base_types must be "
                            "a non-empty list of scalar type tags or type groups"
                        ),
                        source=source_span(base_types.source),
                    )
                )


def _validate_immediate_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("params"):
        for entry in children(field.field):
            validate_known_fields(
                children(entry),
                frozenset({"type", "value_range", "dispatch"}),
                diagnostics,
                owner=f"params entry {entry.key.text!r}",
            )
            dispatch = child(entry, "dispatch")
            for child_field in children(dispatch):
                if not DEFAULT_SUPPORT_POLICY.supports_backend(child_field.key.text):
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-UNKNOWN-BACKEND",
                            message=f"dispatch backend {child_field.key.text!r} is not supported",
                            source=source_span(child_field.source),
                        )
                    )
                strategy = field_text(child_field)
                if strategy is not None and strategy not in _KNOWN_IMMEDIATE_DISPATCH:
                    invalid_enum(
                        diagnostics,
                        child_field,
                        f"immediate dispatch strategy {strategy!r}",
                        sorted(_KNOWN_IMMEDIATE_DISPATCH),
                    )


def _validate_param_types(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    attributes = {attribute.key.text: attribute for attribute in declaration.attributes}
    seen: set[tuple[str, str, str]] = set()
    for field in declaration.fields_by_name("param_types"):
        diagnose_duplicate_fields(
            children(field.field), diagnostics, label="param_types parameter"
        )
        for parameter in children(field.field):
            parameter_name = parameter.key.text
            if parameter_name not in declaration.parameters:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-PARAM-TYPES-UNKNOWN-PARAM",
                        message=(
                            f"primitive {declaration.name!r} param_types references "
                            f"unknown parameter {parameter_name!r}"
                        ),
                        source=source_span(parameter.source),
                    )
                )
            for entry in children(parameter):
                parsed = _parse_param_type_condition(entry.key.text)
                if parsed is _INVALID_PARAM_TYPE_CONDITION:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-BAD-CONDITION",
                            message=(
                                f"primitive {declaration.name!r} param_types rule "
                                f"{unquote_key(entry.key.text)!r} must be shaped "
                                "as 'default' or 'if attribute=value'"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                    continue
                attribute_name, attribute_value = parsed
                if attribute_name is None:
                    identity = (parameter_name, "", "")
                    if identity in seen:
                        diagnostics.append(
                            diagnostic_at(
                                severity="error",
                                code="TSL-CATALOG-PARAM-TYPES-DUPLICATE-RULE",
                                message=(
                                    "duplicate default param_types rule for parameter "
                                    f"{parameter_name!r}"
                                ),
                                source=source_span(entry.source),
                            )
                        )
                    seen.add(identity)
                    if not field_text(entry):
                        diagnostics.append(
                            diagnostic_at(
                                severity="error",
                                code="TSL-CATALOG-PARAM-TYPES-MISSING-TYPE",
                                message=(
                                    f"primitive {declaration.name!r} param_types rule for "
                                    f"parameter {parameter_name!r} has no type expression"
                                ),
                                source=source_span(entry.source),
                            )
                        )
                    continue
                attribute = attributes.get(attribute_name)
                if attribute is None:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-UNKNOWN-ATTRIBUTE",
                            message=(
                                f"primitive {declaration.name!r} param_types rule references "
                                f"unknown attribute {attribute_name!r}"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                    continue
                allowed = _KNOWN_PRIMITIVE_ATTRIBUTES.get(attribute_name, frozenset())
                if attribute_value not in allowed or attribute_value == "*":
                    invalid_enum(
                        diagnostics,
                        entry,
                        (
                            f"param_types condition value {attribute_value!r} for "
                            f"attribute {attribute_name!r}"
                        ),
                        sorted(value for value in allowed if value != "*"),
                    )
                identity = (parameter_name, attribute_name, attribute_value)
                if identity in seen:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-DUPLICATE-RULE",
                            message=(
                                f"duplicate param_types rule for parameter {parameter_name!r} "
                                f"when {attribute_name}={attribute_value}"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                seen.add(identity)
                if not field_text(entry):
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-MISSING-TYPE",
                            message=(
                                f"primitive {declaration.name!r} param_types rule for "
                                f"parameter {parameter_name!r} has no type expression"
                            ),
                            source=source_span(entry.source),
                        )
                    )


_INVALID_PARAM_TYPE_CONDITION = object()


def _parse_param_type_condition(text: str) -> tuple[str | None, str | None] | object:
    condition = unquote_key(text)
    if condition == "default":
        return (None, None)
    match = _PARAM_TYPE_CONDITION_RE.fullmatch(condition)
    if match is None:
        return _INVALID_PARAM_TYPE_CONDITION
    return match.group(1), match.group(2)


def _validate_return_type(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("return_type"):
        validate_known_fields(
            children(field.field),
            frozenset({"base", "extension"}),
            diagnostics,
            owner="return_type",
        )
