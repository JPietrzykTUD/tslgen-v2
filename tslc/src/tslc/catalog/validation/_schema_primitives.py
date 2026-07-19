"""Schema validation for primitive declarations."""

from __future__ import annotations

from collections.abc import Collection
from typing import get_args

from tslc.catalog.model import GenericParamKind
from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.signatures import parse_signature
from tslc.catalog.param_types import (
    BASE_WIDTH_RELATIONS,
    base_width_relation_text,
    parse_base_width_constraint,
    parse_param_type_condition,
    unquote_key,
)
from tslc.catalog.validation._schema_common import (
    KNOWN_BOOLEAN_VALUES,
    diagnose_duplicate_fields,
    invalid_enum,
    is_non_empty_scalar_list,
    validate_known_fields,
)
from tslc.catalog.validation._schema_implementation import (
    validate_implementation_safety,
)
from tslc.catalog.validation._schema_benchmarks import validate_benchmarks
from tslc.catalog.validation._schema_tests import validate_tests
from tslc.catalog.validation.requires_validation import validate_requires
from tslc.syntax.access import (
    attribute_scalar_text,
    child,
    children,
    field_text,
    source_span,
)
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
    ParsedTslField,
)

# Derived from the typed catalog kind so the validator cannot drift from the model.
KNOWN_GENERIC_PARAM_KINDS: frozenset[str] = frozenset(get_args(GenericParamKind))
KNOWN_IMMEDIATE_DISPATCH = frozenset({"literal_match"})
KNOWN_GENERIC_PARAM_FIELDS = frozenset(
    {"kind", "default", "base_types", "specialize_base", "constraints"}
)
KNOWN_IMMEDIATE_PARAM_FIELDS = frozenset({"type", "value_range", "dispatch"})
KNOWN_RETURN_TYPE_FIELDS = frozenset({"base", "extension"})
KNOWN_PRIMITIVE_FIELDS = frozenset(
    {
        "benchmarks",
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
KNOWN_PRIMITIVE_ATTRIBUTES = {
    "aligned": frozenset({"true", "false", "*"}),
    "arg_count": frozenset({"return_vector_length"}),
    "cast": frozenset({"reinterpret", "convert"}),
    "direction": frozenset({"up", "down"}),
    "mask": frozenset({"zero", "pass_through"}),
    "op": frozenset({"pack", "expand", "keep"}),
    "packed": frozenset({"true", "false", "*"}),
    "value": frozenset({"zero", "undef", "all"}),
}


def validate_primitive(
    declaration: ParsedPrimitiveDeclaration,
    backend_ids: Collection[str],
    diagnostics: list[Diagnostic],
    known_target_features: Collection[str] = (),
) -> None:
    fields = tuple(field.field for field in declaration.fields)
    validate_known_fields(
        fields,
        KNOWN_PRIMITIVE_FIELDS,
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
    _validate_immediate_params(declaration, backend_ids, diagnostics)
    _validate_param_types(declaration, diagnostics)
    validate_implementation_safety(declaration, diagnostics)
    _validate_return_type(declaration, diagnostics)
    validate_benchmarks(declaration, diagnostics)
    validate_tests(declaration, diagnostics)
    validate_requires(declaration, diagnostics, known_target_features)


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
        allowed = KNOWN_PRIMITIVE_ATTRIBUTES.get(key)
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
                KNOWN_GENERIC_PARAM_FIELDS,
                diagnostics,
                owner=f"generic parameter {entry.key.text!r}",
            )
            kind_field = child(entry, "kind")
            kind = field_text(kind_field)
            if kind is not None and kind not in KNOWN_GENERIC_PARAM_KINDS:
                invalid_enum(
                    diagnostics,
                    kind_field,
                    f"generic parameter kind {kind!r}",
                    sorted(KNOWN_GENERIC_PARAM_KINDS),
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
            constraints = child(entry, "constraints")
            if constraints is not None:
                _validate_generic_param_constraints(
                    entry.key.text,
                    constraints,
                    kind,
                    field_text(specialize_base) == "true",
                    diagnostics,
                )
            direct_base_types = child(entry, "base_types")
            nested_base_types = child(constraints, "base_types")
            if direct_base_types is not None and nested_base_types is not None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {entry.key.text!r} declares base_types "
                            "both directly and inside constraints"
                        ),
                        source=source_span(nested_base_types.source),
                    )
                )
            base_types = nested_base_types or direct_base_types
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


def _validate_generic_param_constraints(
    name: str,
    constraints: ParsedTslField,
    kind: str | None,
    specialize_base: bool,
    diagnostics: list[Diagnostic],
) -> None:
    constraint_fields = children(constraints)
    diagnose_duplicate_fields(
        constraint_fields,
        diagnostics,
        label=f"generic parameter {name!r} constraint",
    )
    width_constraint_count = 0
    for field in constraint_fields:
        key = field.key.text
        if key == "base_types":
            continue
        relation_text = base_width_relation_text(key)
        if relation_text is not None and parse_base_width_constraint(key) is None:
            # The key is base-width shaped but its relation is mistyped (`<`, `=>`).
            # Diagnose the relation itself so the author fixes the operator, not the key.
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-BASE-WIDTH-RELATION",
                    message=(
                        f"generic parameter {name!r} base-width constraint uses "
                        f"unknown relation {relation_text!r}; expected one of: "
                        f"{', '.join(BASE_WIDTH_RELATIONS)}"
                    ),
                    source=source_span(field.source),
                )
            )
            continue
        if parse_base_width_constraint(key) is not None:
            width_constraint_count += 1
            if kind != "simd_type":
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {name!r} uses a base-width constraint, "
                            "but base-width constraints are allowed only for kind 'simd_type'"
                        ),
                        source=source_span(field.source),
                    )
                )
            if not specialize_base:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                        message=(
                            f"generic parameter {name!r} uses a base-width constraint, "
                            "but base-width constraints require specialize_base true"
                        ),
                        source=source_span(field.source),
                    )
                )
            continue
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-UNKNOWN-FIELD",
                message=f"unknown field {key!r} in generic parameter {name!r} constraints",
                source=source_span(field.source),
            )
        )
    if width_constraint_count > 1:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                message=(
                    f"generic parameter {name!r} constraints may contain at most one "
                    "base-width constraint"
                ),
                source=source_span(constraints.source),
            )
        )


def _validate_immediate_params(
    declaration: ParsedPrimitiveDeclaration,
    backend_ids: Collection[str],
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("params"):
        for entry in children(field.field):
            validate_known_fields(
                children(entry),
                KNOWN_IMMEDIATE_PARAM_FIELDS,
                diagnostics,
                owner=f"params entry {entry.key.text!r}",
            )
            dispatch = child(entry, "dispatch")
            for child_field in children(dispatch):
                if child_field.key.text not in backend_ids:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-UNKNOWN-BACKEND",
                            message=f"dispatch backend {child_field.key.text!r} is not supported",
                            source=source_span(child_field.source),
                        )
                    )
                strategy = field_text(child_field)
                if strategy is not None and strategy not in KNOWN_IMMEDIATE_DISPATCH:
                    invalid_enum(
                        diagnostics,
                        child_field,
                        f"immediate dispatch strategy {strategy!r}",
                        sorted(KNOWN_IMMEDIATE_DISPATCH),
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
                parsed = parse_param_type_condition(entry.key.text)
                if parsed is None:
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
                assert attribute_value is not None
                allowed = KNOWN_PRIMITIVE_ATTRIBUTES.get(attribute_name, frozenset())
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


def _validate_return_type(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    target_fields: list[ParsedTslField] = []
    for field in declaration.fields_by_name("return_type"):
        target_fields.extend(
            child_field
            for child_field in children(field.field)
            if child_field.key.text in KNOWN_RETURN_TYPE_FIELDS
        )
        validate_known_fields(
            children(field.field),
            KNOWN_RETURN_TYPE_FIELDS,
            diagnostics,
            owner="return_type",
        )
    shape = parse_signature(declaration.signature)
    if shape is None:
        return
    target_param_kinds = tuple(
        kind
        for kind in shape.param_kinds
        if DEFAULT_SIGNATURE_KINDS.is_target_vector_parameter(kind)
    )
    if DEFAULT_SIGNATURE_KINDS.is_target_vector_parameter(shape.result_kind):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TARGET-KIND-RESULT",
                message=(
                    f"target-vector signature kind {shape.result_kind!r} is valid only "
                    "for parameters"
                ),
                source=source_span(declaration.signature_source),
            )
        )
    if target_param_kinds and len(target_fields) != 1:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TARGET-PARAM-RETURN-TYPE",
                message=(
                    f"primitive {declaration.name!r} uses target-vector parameter kind(s) "
                    f"{', '.join(repr(kind) for kind in target_param_kinds)} and must "
                    "declare exactly one return_type base or extension target"
                ),
                source=source_span(declaration.signature_source),
            )
        )
