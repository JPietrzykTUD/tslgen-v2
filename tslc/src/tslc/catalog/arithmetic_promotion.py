"""Validation and promotion for primitive ``arithmetic`` blocks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from difflib import get_close_matches

from tslc.catalog.arithmetic import (
    ARITHMETIC_GUARANTEE_SPECS,
    ARITHMETIC_OPERAND_ROLE_KINDS,
    ArithmeticConflictGroup,
    ArithmeticContract,
    ArithmeticGuarantee,
    ArithmeticMaskRequirement,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
    ArithmeticOperation,
    arithmetic_guarantee_values,
    arithmetic_operand_role_values,
    arithmetic_operation_values,
)
from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at
from tslc.syntax.access import children, source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
)


KNOWN_ARITHMETIC_FIELDS = frozenset(
    {"operations", "operand_roles", "guarantees"}
)


def build_arithmetic_contract(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> ArithmeticContract | None:
    """Validate and resolve one source contract, or return ``None`` on any error."""

    parsed_fields = declaration.fields_by_name("arithmetic")
    if not parsed_fields:
        return None
    # Primitive-level duplicate-field validation owns this diagnostic. Avoid
    # promoting an arbitrary member and causing misleading family diagnostics.
    if len(parsed_fields) != 1:
        return None

    start_diagnostics = len(diagnostics)
    arithmetic_field = parsed_fields[0].field
    fields = children(arithmetic_field)
    _validate_known_fields(
        fields,
        KNOWN_ARITHMETIC_FIELDS,
        diagnostics,
        owner=f"primitive {declaration.name!r} arithmetic contract",
    )
    _diagnose_duplicate_fields(
        fields,
        diagnostics,
        label=f"primitive {declaration.name!r} arithmetic field",
    )
    by_name = {field.key.text: field for field in fields}
    for required in sorted(KNOWN_ARITHMETIC_FIELDS):
        if required not in by_name:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-MISSING-FIELD",
                    message=(
                        f"primitive {declaration.name!r} arithmetic contract must "
                        f"declare {required!r}"
                    ),
                    source=source_span(arithmetic_field.source),
                )
            )

    operation_items = _scalar_list(
        declaration,
        by_name.get("operations"),
        "operations",
        diagnostics,
        nonempty=True,
    )
    guarantee_items = _scalar_list(
        declaration,
        by_name.get("guarantees"),
        "guarantees",
        diagnostics,
        nonempty=False,
    )
    _diagnose_duplicate_items(
        declaration,
        operation_items,
        "operation",
        "TSL-CATALOG-ARITHMETIC-DUPLICATE-OPERATION",
        diagnostics,
    )
    _diagnose_duplicate_items(
        declaration,
        guarantee_items,
        "guarantee",
        "TSL-CATALOG-ARITHMETIC-DUPLICATE-GUARANTEE",
        diagnostics,
    )

    operations: set[ArithmeticOperation] = set()
    for item in operation_items:
        try:
            operations.add(ArithmeticOperation(item.text))
        except ValueError:
            diagnostics.append(
                _invalid_value(
                    declaration,
                    item,
                    "operation",
                    arithmetic_operation_values(),
                    "TSL-CATALOG-ARITHMETIC-UNKNOWN-OPERATION",
                )
            )

    guarantees: set[ArithmeticGuarantee] = set()
    for item in guarantee_items:
        try:
            guarantees.add(ArithmeticGuarantee(item.text))
        except ValueError:
            diagnostics.append(
                _invalid_value(
                    declaration,
                    item,
                    "guarantee",
                    arithmetic_guarantee_values(),
                    "TSL-CATALOG-ARITHMETIC-UNKNOWN-GUARANTEE",
                )
            )

    bindings = _operand_bindings(
        declaration,
        by_name.get("operand_roles"),
        diagnostics,
    )
    roles = frozenset(binding.role for binding in bindings)
    required_roles: set[ArithmeticOperandRole] = set()
    for operation in operations:
        if operation in {
            ArithmeticOperation.ADDITION,
            ArithmeticOperation.MULTIPLICATION,
            ArithmeticOperation.SUBTRACTION,
        }:
            required_roles.update(
                {ArithmeticOperandRole.PRIMARY, ArithmeticOperandRole.SECONDARY}
            )
        elif operation in {
            ArithmeticOperation.DIVISION,
            ArithmeticOperation.REMAINDER,
        }:
            required_roles.update(
                {ArithmeticOperandRole.PRIMARY, ArithmeticOperandRole.DIVISOR}
            )
    missing_operation_roles = required_roles - roles
    if missing_operation_roles:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-ARITHMETIC-MISSING-ROLE",
                message=(
                    f"primitive {declaration.name!r} arithmetic operand_roles must "
                    f"bind {_joined(role.value for role in missing_operation_roles)}"
                ),
                source=(
                    source_span(by_name["operand_roles"].source)
                    if "operand_roles" in by_name
                    else source_span(arithmetic_field.source)
                ),
            )
        )
    # Applicability checks assume a structurally valid closed contract. Returning
    # here prevents one typo from cascading into several prerequisite errors.
    if len(diagnostics) != start_diagnostics:
        return None

    masked = any(attribute.key.text == "mask" for attribute in declaration.attributes)
    conflict_groups: dict[ArithmeticConflictGroup, ArithmeticGuarantee] = {}
    for guarantee in sorted(guarantees, key=lambda item: item.value):
        spec = ARITHMETIC_GUARANTEE_SPECS[guarantee]
        guarantee_item = next(
            (candidate for candidate in guarantee_items if candidate.text == guarantee.value),
            None,
        )
        guarantee_source = (
            _scalar_source(guarantee_item) if guarantee_item is not None else None
        )
        if not spec.required_all_operations.issubset(operations):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-GUARANTEE-OPERATION",
                    message=(
                        f"arithmetic guarantee {guarantee.value!r} on primitive "
                        f"{declaration.name!r} requires operations "
                        f"{_joined(item.value for item in spec.required_all_operations)}"
                    ),
                    source=guarantee_source,
                )
            )
        if (
            spec.required_any_operations
            and not spec.required_any_operations.intersection(operations)
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-GUARANTEE-OPERATION",
                    message=(
                        f"arithmetic guarantee {guarantee.value!r} on primitive "
                        f"{declaration.name!r} requires at least one of operations "
                        f"{_joined(item.value for item in spec.required_any_operations)}"
                    ),
                    source=guarantee_source,
                )
            )
        missing_roles = spec.prerequisite_roles - roles
        if missing_roles:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-GUARANTEE-ROLE",
                    message=(
                        f"arithmetic guarantee {guarantee.value!r} on primitive "
                        f"{declaration.name!r} requires operand roles "
                        f"{_joined(role.value for role in missing_roles)}"
                    ),
                    source=guarantee_source,
                )
            )
        if (
            spec.mask_requirement is ArithmeticMaskRequirement.MASKED
            and not masked
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-GUARANTEE-MASK",
                    message=(
                        f"arithmetic guarantee {guarantee.value!r} on primitive "
                        f"{declaration.name!r} requires a masked declaration"
                    ),
                    source=guarantee_source,
                )
            )
        group = spec.conflict_group
        if group is None:
            continue
        first = conflict_groups.get(group)
        if first is None:
            conflict_groups[group] = guarantee
            continue
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-ARITHMETIC-CONFLICTING-GUARANTEES",
                message=(
                    f"arithmetic guarantees {first.value!r} and {guarantee.value!r} "
                    f"on primitive {declaration.name!r} conflict"
                ),
                source=guarantee_source,
            )
        )

    if len(diagnostics) != start_diagnostics:
        return None
    operations_field = by_name["operations"]
    guarantees_field = by_name["guarantees"]
    return ArithmeticContract(
        operations=frozenset(operations),
        operand_bindings=tuple(sorted(bindings, key=lambda item: item.role.value)),
        guarantees=frozenset(guarantees),
        source=source_span(arithmetic_field.source),
        operations_source=source_span(operations_field.source),
        guarantees_source=source_span(guarantees_field.source),
    )


def _operand_bindings(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField | None,
    diagnostics: list[Diagnostic],
) -> tuple[ArithmeticOperandBinding, ...]:
    if field is None:
        return ()
    role_fields = children(field)
    _diagnose_duplicate_fields(
        role_fields,
        diagnostics,
        label=f"primitive {declaration.name!r} arithmetic operand role",
        code="TSL-CATALOG-ARITHMETIC-DUPLICATE-ROLE",
    )
    known_roles = frozenset(arithmetic_operand_role_values())
    _validate_known_fields(
        role_fields,
        known_roles,
        diagnostics,
        owner=f"primitive {declaration.name!r} arithmetic operand_roles",
    )
    shape = parse_signature(declaration.signature)
    if shape is None or len(shape.param_kinds) != len(declaration.parameters):
        return ()
    bindings: list[ArithmeticOperandBinding] = []
    for role_field in role_fields:
        try:
            role = ArithmeticOperandRole(role_field.key.text)
        except ValueError:
            continue
        value = role_field.value
        if not isinstance(value, ParsedTslScalarValue) or not value.text:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-MALFORMED-ROLE-BINDING",
                    message=(
                        f"arithmetic operand role {role.value!r} on primitive "
                        f"{declaration.name!r} must reference one parameter by name"
                    ),
                    source=source_span(role_field.source),
                )
            )
            continue
        matches = tuple(
            index
            for index, parameter in enumerate(declaration.parameters)
            if parameter == value.text
        )
        if len(matches) != 1:
            reason = "is ambiguous" if matches else "does not exist"
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-INVALID-PARAMETER",
                    message=(
                        f"arithmetic operand role {role.value!r} on primitive "
                        f"{declaration.name!r} references parameter {value.text!r}, "
                        f"which {reason}"
                    ),
                    source=_scalar_source(value),
                    help=(
                        "declared parameters: " + ", ".join(declaration.parameters)
                        if declaration.parameters
                        else "this primitive declares no parameters"
                    ),
                )
            )
            continue
        index = matches[0]
        kind = shape.param_kinds[index]
        compatible_kinds = ARITHMETIC_OPERAND_ROLE_KINDS[role]
        if kind not in compatible_kinds:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-ARITHMETIC-INCOMPATIBLE-PARAMETER",
                    message=(
                        f"arithmetic {role.value} role on primitive {declaration.name!r} "
                        f"cannot bind parameter {value.text!r} of signature kind {kind!r}"
                    ),
                    source=_scalar_source(value),
                    help=(
                        "compatible kinds: " + ", ".join(sorted(compatible_kinds))
                    ),
                )
            )
            continue
        non_mask_ordinal = sum(
            not DEFAULT_SIGNATURE_KINDS.is_test_mask_argument(previous)
            for previous in shape.param_kinds[:index]
        )
        bindings.append(
            ArithmeticOperandBinding(
                role=role,
                parameter_name=value.text,
                parameter_index=index,
                non_mask_ordinal=non_mask_ordinal,
                parameter_kind=kind,
                source=source_span(role_field.source),
                parameter_source=_scalar_source(value),
            )
        )
    return tuple(bindings)


def _scalar_list(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField | None,
    name: str,
    diagnostics: list[Diagnostic],
    *,
    nonempty: bool,
) -> tuple[ParsedTslScalarValue, ...]:
    if field is None:
        return ()
    value = field.value
    if not isinstance(value, ParsedTslListValue) or any(
        not isinstance(item, ParsedTslScalarValue) for item in value.items
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-ARITHMETIC-MALFORMED-LIST",
                message=(
                    f"primitive {declaration.name!r} arithmetic {name!r} must be "
                    "a scalar list"
                ),
                source=source_span(field.source),
            )
        )
        return ()
    items = tuple(item for item in value.items if isinstance(item, ParsedTslScalarValue))
    if nonempty and not items:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-ARITHMETIC-EMPTY-OPERATIONS",
                message=(
                    f"primitive {declaration.name!r} arithmetic operations must "
                    "contain at least one operation"
                ),
                source=source_span(field.source),
            )
        )
    return items


def _diagnose_duplicate_items(
    declaration: ParsedPrimitiveDeclaration,
    items: tuple[ParsedTslScalarValue, ...],
    label: str,
    code: str,
    diagnostics: list[Diagnostic],
) -> None:
    counts = Counter(item.text for item in items)
    first_by_value: dict[str, ParsedTslScalarValue] = {}
    for item in items:
        if counts[item.text] < 2:
            continue
        first = first_by_value.get(item.text)
        if first is None:
            first_by_value[item.text] = item
            continue
        first_span = _scalar_source(first)
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code=code,
                message=(
                    f"duplicate arithmetic {label} {item.text!r} on primitive "
                    f"{declaration.name!r}"
                ),
                source=_scalar_source(item),
                related=(
                    ()
                    if first_span is None
                    else (
                        RelatedLocation(
                            message=f"first arithmetic {label} is here",
                            span=first_span,
                        ),
                    )
                ),
            )
        )


def _invalid_value(
    declaration: ParsedPrimitiveDeclaration,
    item: ParsedTslScalarValue,
    label: str,
    allowed: tuple[str, ...],
    code: str,
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code=code,
        message=(
            f"unknown arithmetic {label} {item.text!r} on primitive "
            f"{declaration.name!r}"
        ),
        source=_scalar_source(item),
        help="allowed values: " + ", ".join(allowed),
    )


def _scalar_source(value: ParsedTslScalarValue) -> SourceSpan | None:
    return source_span(value.payload_source or value.source)


def _joined(values: Iterable[str]) -> str:
    return ", ".join(sorted(str(value) for value in values))


def _validate_known_fields(
    fields: tuple[ParsedTslField, ...],
    allowed: frozenset[str],
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for field in fields:
        if field.key.text in allowed:
            continue
        matches = get_close_matches(field.key.text, sorted(allowed), n=1, cutoff=0.6)
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-UNKNOWN-FIELD",
                message=f"unknown field {field.key.text!r} in {owner}",
                source=source_span(field.source),
                help=f"did you mean {matches[0]!r}?" if matches else None,
            )
        )


def _diagnose_duplicate_fields(
    fields: tuple[ParsedTslField, ...],
    diagnostics: list[Diagnostic],
    *,
    label: str,
    code: str = "TSL-CATALOG-DUPLICATE-FIELD",
) -> None:
    counts = Counter(field.key.text for field in fields)
    first_by_key: dict[str, ParsedTslField] = {}
    for field in fields:
        key = field.key.text
        if counts[key] < 2:
            continue
        first = first_by_key.get(key)
        if first is None:
            first_by_key[key] = field
            continue
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


__all__ = ("KNOWN_ARITHMETIC_FIELDS", "build_arithmetic_contract")
