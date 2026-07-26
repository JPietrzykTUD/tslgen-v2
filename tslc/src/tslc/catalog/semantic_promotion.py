"""Validation and promotion for primitive operation and operand-role facts."""

from __future__ import annotations

from tslc.catalog._semantic_promotion_common import (
    duplicate_members as _duplicate_members,
    invalid_enum as _invalid_enum,
    joined as _joined,
    member_value_source as _member_value_source,
    scalar_source as _scalar_source,
)
from tslc.catalog.semantics import (
    OperandBinding,
    OperandRole,
    PrimitiveOperation,
    PrimitiveSemanticContract,
    operand_role_values,
    primitive_operation_values,
)
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.access import children, field_text, source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslScalarValue,
)

_VECTOR_VALUES = frozenset({"v", "m", "im"})
_ROLE_KINDS: dict[OperandRole, frozenset[str]] = {
    OperandRole.CONTROL_MASK: frozenset({"m"}),
    OperandRole.COUNT: frozenset({"s", "sImm", "usize", "v"}),
    OperandRole.INDEX: frozenset({"usize"}),
    OperandRole.MEMORY_DESTINATION: frozenset({"ptr", "ptr+"}),
    OperandRole.MEMORY_SOURCE: frozenset({"cptr", "cptr+"}),
    OperandRole.PASS_THROUGH: frozenset({"v"}),
    OperandRole.PRIMARY: _VECTOR_VALUES,
    OperandRole.SECONDARY: _VECTOR_VALUES,
    OperandRole.VALUE: frozenset({"s", "s[]", "v", "im"}),
}

_BINARY_VALUE_ROLES = frozenset({OperandRole.PRIMARY, OperandRole.SECONDARY})
_OPTIONAL_MASK_ROLES = frozenset(
    {OperandRole.CONTROL_MASK, OperandRole.PASS_THROUGH}
)
_OPERATION_ROLES: dict[
    PrimitiveOperation, tuple[frozenset[OperandRole], frozenset[OperandRole]]
] = {
    PrimitiveOperation.BIT_AND: (_BINARY_VALUE_ROLES, _OPTIONAL_MASK_ROLES),
    PrimitiveOperation.BIT_AND_NOT: (_BINARY_VALUE_ROLES, _OPTIONAL_MASK_ROLES),
    PrimitiveOperation.BIT_NOT: (
        frozenset({OperandRole.PRIMARY}),
        _OPTIONAL_MASK_ROLES,
    ),
    PrimitiveOperation.BIT_OR: (_BINARY_VALUE_ROLES, _OPTIONAL_MASK_ROLES),
    PrimitiveOperation.BIT_XOR: (_BINARY_VALUE_ROLES, _OPTIONAL_MASK_ROLES),
    PrimitiveOperation.COMPARE_EQUAL: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.COMPARE_GREATER: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.COMPARE_GREATER_EQUAL: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.COMPARE_LESS: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.COMPARE_LESS_EQUAL: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.COMPARE_NOT_EQUAL: (
        _BINARY_VALUE_ROLES,
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.CONVERT: (frozenset({OperandRole.PRIMARY}), frozenset()),
    PrimitiveOperation.EXTRACT_LANE: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.INDEX}),
    ),
    PrimitiveOperation.HORIZONTAL_ADD: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.HORIZONTAL_BIT_AND: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.HORIZONTAL_BIT_OR: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.HORIZONTAL_MAX: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.HORIZONTAL_MIN: (
        frozenset({OperandRole.PRIMARY}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.INTEGRAL_MASK_TEST: (
        frozenset({OperandRole.PRIMARY, OperandRole.INDEX}),
        frozenset(),
    ),
    PrimitiveOperation.INSERT_LANE: (
        frozenset({OperandRole.PRIMARY, OperandRole.VALUE}),
        frozenset({OperandRole.INDEX}),
    ),
    PrimitiveOperation.LOAD: (
        frozenset({OperandRole.MEMORY_SOURCE}),
        frozenset({OperandRole.CONTROL_MASK, OperandRole.PASS_THROUGH}),
    ),
    PrimitiveOperation.MASK_ALL_FALSE: (frozenset(), frozenset()),
    PrimitiveOperation.MASK_ALL_TRUE: (frozenset(), frozenset()),
    PrimitiveOperation.MASK_AND: (_BINARY_VALUE_ROLES, frozenset()),
    PrimitiveOperation.MASK_FROM_INTEGRAL: (
        frozenset({OperandRole.VALUE}),
        frozenset(),
    ),
    PrimitiveOperation.MASK_NOT: (frozenset({OperandRole.PRIMARY}), frozenset()),
    PrimitiveOperation.MASK_OR: (_BINARY_VALUE_ROLES, frozenset()),
    PrimitiveOperation.MASK_POPULATION_COUNT: (
        frozenset({OperandRole.PRIMARY}),
        frozenset(),
    ),
    PrimitiveOperation.MASK_SET_LANE: (
        frozenset({OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE}),
        frozenset(),
    ),
    PrimitiveOperation.MASK_TO_INTEGRAL: (
        frozenset({OperandRole.PRIMARY}),
        frozenset(),
    ),
    PrimitiveOperation.MASK_XOR: (_BINARY_VALUE_ROLES, frozenset()),
    PrimitiveOperation.REINTERPRET: (
        frozenset({OperandRole.PRIMARY}),
        frozenset(),
    ),
    PrimitiveOperation.SELECT: (
        frozenset(
            {
                OperandRole.CONTROL_MASK,
                OperandRole.PASS_THROUGH,
                OperandRole.PRIMARY,
            }
        ),
        frozenset(),
    ),
    PrimitiveOperation.SHIFT_LEFT: (
        frozenset({OperandRole.PRIMARY, OperandRole.COUNT}),
        _OPTIONAL_MASK_ROLES,
    ),
    PrimitiveOperation.SHIFT_LEFT_WRAPPING: (
        frozenset({OperandRole.PRIMARY, OperandRole.COUNT}),
        frozenset(),
    ),
    PrimitiveOperation.SHIFT_RIGHT: (
        frozenset({OperandRole.PRIMARY, OperandRole.COUNT}),
        _OPTIONAL_MASK_ROLES,
    ),
    PrimitiveOperation.SHIFT_RIGHT_WRAPPING: (
        frozenset({OperandRole.PRIMARY, OperandRole.COUNT}),
        frozenset(),
    ),
    PrimitiveOperation.STORE: (
        frozenset({OperandRole.MEMORY_DESTINATION, OperandRole.VALUE}),
        frozenset({OperandRole.CONTROL_MASK}),
    ),
    PrimitiveOperation.VECTOR_FROM_ARRAY: (
        frozenset({OperandRole.VALUE}),
        frozenset(),
    ),
    PrimitiveOperation.VECTOR_SPLAT: (
        frozenset({OperandRole.VALUE}),
        frozenset(),
    ),
    PrimitiveOperation.VECTOR_TO_ARRAY: (
        frozenset({OperandRole.PRIMARY}),
        frozenset(),
    ),
    PrimitiveOperation.VECTOR_ZERO: (frozenset(), frozenset()),
}

_OPERATION_RESULT_KINDS: dict[PrimitiveOperation, frozenset[str]] = {
    PrimitiveOperation.BIT_AND: frozenset({"v"}),
    PrimitiveOperation.BIT_AND_NOT: frozenset({"v"}),
    PrimitiveOperation.BIT_NOT: frozenset({"v"}),
    PrimitiveOperation.BIT_OR: frozenset({"v"}),
    PrimitiveOperation.BIT_XOR: frozenset({"v"}),
    PrimitiveOperation.COMPARE_EQUAL: frozenset({"m"}),
    PrimitiveOperation.COMPARE_GREATER: frozenset({"m"}),
    PrimitiveOperation.COMPARE_GREATER_EQUAL: frozenset({"m"}),
    PrimitiveOperation.COMPARE_LESS: frozenset({"m"}),
    PrimitiveOperation.COMPARE_LESS_EQUAL: frozenset({"m"}),
    PrimitiveOperation.COMPARE_NOT_EQUAL: frozenset({"m"}),
    PrimitiveOperation.CONVERT: frozenset({"v"}),
    PrimitiveOperation.EXTRACT_LANE: frozenset({"s"}),
    PrimitiveOperation.HORIZONTAL_ADD: frozenset({"s"}),
    PrimitiveOperation.HORIZONTAL_BIT_AND: frozenset({"s"}),
    PrimitiveOperation.HORIZONTAL_BIT_OR: frozenset({"s"}),
    PrimitiveOperation.HORIZONTAL_MAX: frozenset({"s"}),
    PrimitiveOperation.HORIZONTAL_MIN: frozenset({"s"}),
    PrimitiveOperation.INTEGRAL_MASK_TEST: frozenset({"im"}),
    PrimitiveOperation.INSERT_LANE: frozenset({"v"}),
    PrimitiveOperation.LOAD: frozenset({"v"}),
    PrimitiveOperation.MASK_ALL_FALSE: frozenset({"m"}),
    PrimitiveOperation.MASK_ALL_TRUE: frozenset({"m"}),
    PrimitiveOperation.MASK_AND: frozenset({"m"}),
    PrimitiveOperation.MASK_FROM_INTEGRAL: frozenset({"m"}),
    PrimitiveOperation.MASK_NOT: frozenset({"m"}),
    PrimitiveOperation.MASK_OR: frozenset({"m"}),
    PrimitiveOperation.MASK_POPULATION_COUNT: frozenset({"usize"}),
    PrimitiveOperation.MASK_SET_LANE: frozenset({"m"}),
    PrimitiveOperation.MASK_TO_INTEGRAL: frozenset({"im"}),
    PrimitiveOperation.MASK_XOR: frozenset({"m"}),
    PrimitiveOperation.REINTERPRET: frozenset({"v"}),
    PrimitiveOperation.SELECT: frozenset({"v"}),
    PrimitiveOperation.SHIFT_LEFT: frozenset({"v"}),
    PrimitiveOperation.SHIFT_LEFT_WRAPPING: frozenset({"v"}),
    PrimitiveOperation.SHIFT_RIGHT: frozenset({"v"}),
    PrimitiveOperation.SHIFT_RIGHT_WRAPPING: frozenset({"v"}),
    PrimitiveOperation.STORE: frozenset({"void"}),
    PrimitiveOperation.VECTOR_FROM_ARRAY: frozenset({"v"}),
    PrimitiveOperation.VECTOR_SPLAT: frozenset({"v"}),
    PrimitiveOperation.VECTOR_TO_ARRAY: frozenset({"s[]"}),
    PrimitiveOperation.VECTOR_ZERO: frozenset({"v"}),
}

_OPERATION_ROLE_KINDS: dict[
    PrimitiveOperation, dict[OperandRole, frozenset[str]]
] = {
    operation: {
        OperandRole.PRIMARY: frozenset({"v"}),
        OperandRole.SECONDARY: frozenset({"v"}),
    }
    for operation in {
        PrimitiveOperation.BIT_AND,
        PrimitiveOperation.BIT_AND_NOT,
        PrimitiveOperation.BIT_OR,
        PrimitiveOperation.BIT_XOR,
        PrimitiveOperation.COMPARE_EQUAL,
        PrimitiveOperation.COMPARE_GREATER,
        PrimitiveOperation.COMPARE_GREATER_EQUAL,
        PrimitiveOperation.COMPARE_LESS,
        PrimitiveOperation.COMPARE_LESS_EQUAL,
        PrimitiveOperation.COMPARE_NOT_EQUAL,
    }
}
_OPERATION_ROLE_KINDS.update(
    {
        PrimitiveOperation.BIT_NOT: {OperandRole.PRIMARY: frozenset({"v"})},
        PrimitiveOperation.CONVERT: {OperandRole.PRIMARY: frozenset({"v"})},
        PrimitiveOperation.EXTRACT_LANE: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.INDEX: frozenset({"usize"}),
        },
        PrimitiveOperation.HORIZONTAL_ADD: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.CONTROL_MASK: frozenset({"m"}),
        },
        PrimitiveOperation.HORIZONTAL_BIT_AND: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.CONTROL_MASK: frozenset({"m"}),
        },
        PrimitiveOperation.HORIZONTAL_BIT_OR: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.CONTROL_MASK: frozenset({"m"}),
        },
        PrimitiveOperation.HORIZONTAL_MAX: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.CONTROL_MASK: frozenset({"m"}),
        },
        PrimitiveOperation.HORIZONTAL_MIN: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.CONTROL_MASK: frozenset({"m"}),
        },
        PrimitiveOperation.INTEGRAL_MASK_TEST: {
            OperandRole.PRIMARY: frozenset({"im"}),
            OperandRole.INDEX: frozenset({"usize"}),
        },
        PrimitiveOperation.INSERT_LANE: {
            OperandRole.PRIMARY: frozenset({"v"}),
            OperandRole.INDEX: frozenset({"usize"}),
            OperandRole.VALUE: frozenset({"s"}),
        },
        PrimitiveOperation.MASK_AND: {
            OperandRole.PRIMARY: frozenset({"m"}),
            OperandRole.SECONDARY: frozenset({"m"}),
        },
        PrimitiveOperation.MASK_FROM_INTEGRAL: {
            OperandRole.VALUE: frozenset({"im"})
        },
        PrimitiveOperation.MASK_NOT: {OperandRole.PRIMARY: frozenset({"m"})},
        PrimitiveOperation.MASK_OR: {
            OperandRole.PRIMARY: frozenset({"m"}),
            OperandRole.SECONDARY: frozenset({"m"}),
        },
        PrimitiveOperation.MASK_POPULATION_COUNT: {
            OperandRole.PRIMARY: frozenset({"m"})
        },
        PrimitiveOperation.MASK_SET_LANE: {
            OperandRole.PRIMARY: frozenset({"m"}),
            OperandRole.INDEX: frozenset({"usize"}),
            OperandRole.VALUE: frozenset({"im"}),
        },
        PrimitiveOperation.MASK_TO_INTEGRAL: {
            OperandRole.PRIMARY: frozenset({"m"})
        },
        PrimitiveOperation.MASK_XOR: {
            OperandRole.PRIMARY: frozenset({"m"}),
            OperandRole.SECONDARY: frozenset({"m"}),
        },
        PrimitiveOperation.REINTERPRET: {OperandRole.PRIMARY: frozenset({"v"})},
        PrimitiveOperation.SELECT: {
            OperandRole.PASS_THROUGH: frozenset({"v"}),
            OperandRole.PRIMARY: frozenset({"v"}),
        },
        PrimitiveOperation.SHIFT_LEFT: {OperandRole.PRIMARY: frozenset({"v"})},
        PrimitiveOperation.SHIFT_LEFT_WRAPPING: {
            OperandRole.PRIMARY: frozenset({"v"})
        },
        PrimitiveOperation.SHIFT_RIGHT: {OperandRole.PRIMARY: frozenset({"v"})},
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING: {
            OperandRole.PRIMARY: frozenset({"v"})
        },
        PrimitiveOperation.STORE: {OperandRole.VALUE: frozenset({"s", "v"})},
        PrimitiveOperation.VECTOR_FROM_ARRAY: {
            OperandRole.VALUE: frozenset({"s[]"})
        },
        PrimitiveOperation.VECTOR_SPLAT: {
            OperandRole.VALUE: frozenset({"s"})
        },
        PrimitiveOperation.VECTOR_TO_ARRAY: {
            OperandRole.PRIMARY: frozenset({"v"})
        },
    }
)


def build_semantic_contract(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> PrimitiveSemanticContract | None:
    operation_fields = declaration.fields_by_name("operation")
    role_fields = declaration.fields_by_name("operand_roles")
    if not operation_fields and not role_fields:
        return None
    if not operation_fields:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OPERATION-MISSING-FIELD",
                message=(
                    f"primitive {declaration.name!r} operand roles require an "
                    "'operation' field"
                ),
                source=source_span(role_fields[0].field.source),
            )
        )
        return None
    if len(operation_fields) != 1 or len(role_fields) > 1:
        return None
    operation_field = operation_fields[0].field
    operation_text = field_text(operation_field)
    try:
        operation = PrimitiveOperation(operation_text or "")
    except ValueError:
        diagnostics.append(
            _invalid_enum(
                declaration,
                operation_field,
                "operation",
                operation_text,
                primitive_operation_values(),
                "TSL-CATALOG-UNKNOWN-OPERATION",
            )
        )
        return None

    required, optional = _OPERATION_ROLES[operation]
    if not role_fields and required:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OPERATION-MISSING-FIELD",
                message=(
                    f"primitive {declaration.name!r} operation requires an "
                    "'operand_roles' field"
                ),
                source=source_span(operation_field.source),
            )
        )
        return None

    start_diagnostics = len(diagnostics)
    bindings = (
        _operand_bindings(declaration, role_fields[0].field, diagnostics)
        if role_fields
        else ()
    )
    shape = parse_signature(declaration.signature)
    if shape is not None and shape.result_kind not in _OPERATION_RESULT_KINDS[operation]:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-INCOMPATIBLE-OPERATION-SIGNATURE",
                message=(
                    f"operation {operation.value!r} on primitive "
                    f"{declaration.name!r} cannot produce signature result kind "
                    f"{shape.result_kind!r}"
                ),
                source=source_span(declaration.signature_source),
                help=(
                    "compatible result kinds: "
                    + ", ".join(sorted(_OPERATION_RESULT_KINDS[operation]))
                ),
            )
        )
    role_kinds = _OPERATION_ROLE_KINDS.get(operation, {})
    for binding in bindings:
        compatible = role_kinds.get(binding.role)
        if compatible is None or binding.parameter_kind in compatible:
            continue
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-INCOMPATIBLE-OPERATION-SIGNATURE",
                message=(
                    f"operation {operation.value!r} on primitive "
                    f"{declaration.name!r} cannot bind role {binding.role.value!r} "
                    f"to signature kind {binding.parameter_kind!r}"
                ),
                source=binding.parameter_source or binding.source,
                help="compatible kinds: " + ", ".join(sorted(compatible)),
            )
        )
    roles = frozenset(binding.role for binding in bindings)
    missing = required - roles
    unexpected = roles - required - optional
    if missing:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OPERATION-MISSING-ROLE",
                message=(
                    f"operation {operation.value!r} on primitive "
                    f"{declaration.name!r} requires operand roles "
                    f"{_joined(role.value for role in missing)}"
                ),
                source=(
                    source_span(role_fields[0].field.source)
                    if role_fields
                    else source_span(operation_field.source)
                ),
            )
        )
    if unexpected:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OPERATION-UNEXPECTED-ROLE",
                message=(
                    f"operation {operation.value!r} on primitive "
                    f"{declaration.name!r} does not accept operand roles "
                    f"{_joined(role.value for role in unexpected)}"
                ),
                source=(
                    source_span(role_fields[0].field.source)
                    if role_fields
                    else source_span(operation_field.source)
                ),
            )
        )
    if len(diagnostics) != start_diagnostics:
        return None
    return PrimitiveSemanticContract(
        kind=operation,
        operand_bindings=tuple(sorted(bindings, key=lambda item: item.role.value)),
        source=source_span(operation_field.source),
        operation_source=_member_value_source(operation_field),
        operand_roles_source=(
            source_span(role_fields[0].field.source) if role_fields else None
        ),
    )


def _operand_bindings(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> tuple[OperandBinding, ...]:
    members = children(field)
    _duplicate_members(
        declaration,
        members,
        "operand role",
        "TSL-CATALOG-DUPLICATE-OPERAND-ROLE",
        diagnostics,
    )
    shape = parse_signature(declaration.signature)
    if shape is None or len(shape.param_kinds) != len(declaration.parameters):
        return ()
    bindings: list[OperandBinding] = []
    for member in members:
        try:
            role = OperandRole(member.key.text)
        except ValueError:
            diagnostics.append(
                _invalid_enum(
                    declaration,
                    member,
                    "operand role",
                    member.key.text,
                    operand_role_values(),
                    "TSL-CATALOG-UNKNOWN-OPERAND-ROLE",
                    source=source_span(member.key.source),
                )
            )
            continue
        value = member.value
        if not isinstance(value, ParsedTslScalarValue) or not value.text:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-OPERAND-ROLE",
                    message=(
                        f"operand role {role.value!r} on primitive "
                        f"{declaration.name!r} must reference one parameter by name"
                    ),
                    source=source_span(member.source),
                )
            )
            continue
        matches = tuple(
            index
            for index, parameter in enumerate(declaration.parameters)
            if parameter == value.text
        )
        if len(matches) != 1:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-INVALID-OPERAND-PARAMETER",
                    message=(
                        f"operand role {role.value!r} on primitive "
                        f"{declaration.name!r} references unknown or ambiguous "
                        f"parameter {value.text!r}"
                    ),
                    source=_scalar_source(value),
                    help="declared parameters: " + ", ".join(declaration.parameters),
                )
            )
            continue
        index = matches[0]
        kind = shape.param_kinds[index]
        if kind not in _ROLE_KINDS[role]:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-INCOMPATIBLE-OPERAND-ROLE",
                    message=(
                        f"operand role {role.value!r} on primitive "
                        f"{declaration.name!r} cannot bind parameter {value.text!r} "
                        f"of signature kind {kind!r}"
                    ),
                    source=_scalar_source(value),
                    help="compatible kinds: " + ", ".join(sorted(_ROLE_KINDS[role])),
                )
            )
            continue
        bindings.append(
            OperandBinding(
                role=role,
                parameter_name=value.text,
                parameter_index=index,
                parameter_kind=kind,
                source=source_span(member.source),
                parameter_source=_scalar_source(value),
            )
        )
    return tuple(bindings)


__all__ = ("build_semantic_contract",)
