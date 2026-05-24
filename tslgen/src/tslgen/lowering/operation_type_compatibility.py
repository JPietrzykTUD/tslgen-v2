"""Lowering-owned operation/type compatibility rules for the tiny clean slice."""

from dataclasses import dataclass

from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import (
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    ScalarTypeFamily,
)
from tslgen.lowering.unary_operations import UnaryOperationDescriptor


@dataclass(frozen=True, slots=True)
class BinaryOperationScalarTypeCompatibilityRule:
    operation_id: str
    accepted_scalar_families: tuple[ScalarTypeFamily, ...]


@dataclass(frozen=True, slots=True)
class UnaryOperationScalarTypeCompatibilityRule:
    operation_id: str
    accepted_scalar_families: tuple[ScalarTypeFamily, ...]


_BINARY_OPERATION_SCALAR_TYPE_RULES: tuple[
    BinaryOperationScalarTypeCompatibilityRule, ...
] = (
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="mod",
        accepted_scalar_families=("integer",),
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_and",
        accepted_scalar_families=("integer",),
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_or",
        accepted_scalar_families=("integer",),
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_xor",
        accepted_scalar_families=("integer",),
    ),
)

_UNARY_OPERATION_SCALAR_TYPE_RULES: tuple[
    UnaryOperationScalarTypeCompatibilityRule, ...
] = (
    UnaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_not",
        accepted_scalar_families=("integer",),
    ),
)


def binary_operation_supports_scalar_type(
    operation: BinaryOperationDescriptor,
    scalar_type: ScalarTypeDescriptor,
) -> bool:
    rule = _rule_for_operation(operation)
    if rule is None:
        return True
    return scalar_type.family in rule.accepted_scalar_families


def supported_scalar_type_tags_for_binary_operation(
    operation: BinaryOperationDescriptor,
) -> tuple[str, ...]:
    rule = _rule_for_operation(operation)
    if rule is None:
        return tuple(descriptor.tag for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS)
    return tuple(
        descriptor.tag
        for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS
        if descriptor.family in rule.accepted_scalar_families
    )


def unary_operation_supports_scalar_type(
    operation: UnaryOperationDescriptor,
    scalar_type: ScalarTypeDescriptor,
) -> bool:
    rule = _rule_for_unary_operation(operation)
    if rule is None:
        return True
    return scalar_type.family in rule.accepted_scalar_families


def supported_scalar_type_tags_for_unary_operation(
    operation: UnaryOperationDescriptor,
) -> tuple[str, ...]:
    rule = _rule_for_unary_operation(operation)
    if rule is None:
        return tuple(descriptor.tag for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS)
    return tuple(
        descriptor.tag
        for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS
        if descriptor.family in rule.accepted_scalar_families
    )


def _rule_for_operation(
    operation: BinaryOperationDescriptor,
) -> BinaryOperationScalarTypeCompatibilityRule | None:
    for rule in _BINARY_OPERATION_SCALAR_TYPE_RULES:
        if rule.operation_id == operation.operation_id:
            return rule
    return None


def _rule_for_unary_operation(
    operation: UnaryOperationDescriptor,
) -> UnaryOperationScalarTypeCompatibilityRule | None:
    for rule in _UNARY_OPERATION_SCALAR_TYPE_RULES:
        if rule.operation_id == operation.operation_id:
            return rule
    return None
