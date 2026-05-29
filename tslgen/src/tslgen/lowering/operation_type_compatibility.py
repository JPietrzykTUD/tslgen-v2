"""Lowering-owned operation/type compatibility rules for the tiny clean slice."""

from dataclasses import dataclass

from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import (
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    ScalarTypeFamily,
    ScalarSignedness,
)
from tslgen.lowering.semantic_origin import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    LoweringSemanticOrigin,
)
from tslgen.lowering.unary_operations import UnaryOperationDescriptor


@dataclass(frozen=True, slots=True)
class BinaryOperationScalarTypeCompatibilityRule:
    operation_id: str
    accepted_scalar_families: tuple[ScalarTypeFamily, ...]
    semantic_origin: LoweringSemanticOrigin = (
        BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN
    )


@dataclass(frozen=True, slots=True)
class UnaryOperationScalarTypeCompatibilityRule:
    operation_id: str
    accepted_scalar_families: tuple[ScalarTypeFamily, ...] = ()
    accepted_scalar_signedness: tuple[ScalarSignedness, ...] = ()
    semantic_origin: LoweringSemanticOrigin = (
        BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN
    )


_BINARY_OPERATION_SCALAR_TYPE_RULES: tuple[
    BinaryOperationScalarTypeCompatibilityRule, ...
] = (
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="mod",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_and",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_or",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_xor",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="shift_left",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationScalarTypeCompatibilityRule(
        operation_id="shift_right",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
)

_UNARY_OPERATION_SCALAR_TYPE_RULES: tuple[
    UnaryOperationScalarTypeCompatibilityRule, ...
] = (
    UnaryOperationScalarTypeCompatibilityRule(
        operation_id="bit_not",
        accepted_scalar_families=("integer",),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    UnaryOperationScalarTypeCompatibilityRule(
        operation_id="neg",
        accepted_scalar_families=("integer", "floating"),
        accepted_scalar_signedness=("signed", "not_applicable"),
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
)


def binary_operation_scalar_type_compatibility_rules() -> tuple[
    BinaryOperationScalarTypeCompatibilityRule, ...
]:
    return _BINARY_OPERATION_SCALAR_TYPE_RULES


def unary_operation_scalar_type_compatibility_rules() -> tuple[
    UnaryOperationScalarTypeCompatibilityRule, ...
]:
    return _UNARY_OPERATION_SCALAR_TYPE_RULES


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
    return _unary_rule_accepts_scalar_type(rule, scalar_type)


def supported_scalar_type_tags_for_unary_operation(
    operation: UnaryOperationDescriptor,
) -> tuple[str, ...]:
    rule = _rule_for_unary_operation(operation)
    if rule is None:
        return tuple(descriptor.tag for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS)
    return tuple(
        descriptor.tag
        for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS
        if _unary_rule_accepts_scalar_type(rule, descriptor)
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


def _unary_rule_accepts_scalar_type(
    rule: UnaryOperationScalarTypeCompatibilityRule,
    scalar_type: ScalarTypeDescriptor,
) -> bool:
    return (
        scalar_type.family in rule.accepted_scalar_families
        and (
            not rule.accepted_scalar_signedness
            or scalar_type.signedness in rule.accepted_scalar_signedness
        )
    )
