"""Lowering-owned binary operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

from tslgen.lowering.semantic_origin import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    LoweringSemanticOrigin,
)

BinaryOperationCategory = Literal["binary"]


@dataclass(frozen=True, slots=True)
class BinaryOperationDescriptor:
    operation_id: str
    arity: int
    category: BinaryOperationCategory
    source_body_operation: str
    semantic_name: str
    semantic_origin: LoweringSemanticOrigin = (
        BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN
    )


SUPPORTED_BINARY_OPERATION_DESCRIPTORS: tuple[BinaryOperationDescriptor, ...] = (
    BinaryOperationDescriptor(
        operation_id="add",
        arity=2,
        category="binary",
        source_body_operation="add",
        semantic_name="binary.add",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="sub",
        arity=2,
        category="binary",
        source_body_operation="sub",
        semantic_name="binary.sub",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="mul",
        arity=2,
        category="binary",
        source_body_operation="mul",
        semantic_name="binary.mul",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="div",
        arity=2,
        category="binary",
        source_body_operation="div",
        semantic_name="binary.div",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="mod",
        arity=2,
        category="binary",
        source_body_operation="mod",
        semantic_name="binary.mod",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="bit_and",
        arity=2,
        category="binary",
        source_body_operation="bit_and",
        semantic_name="binary.bit_and",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="bit_or",
        arity=2,
        category="binary",
        source_body_operation="bit_or",
        semantic_name="binary.bit_or",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="bit_xor",
        arity=2,
        category="binary",
        source_body_operation="bit_xor",
        semantic_name="binary.bit_xor",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="shift_left",
        arity=2,
        category="binary",
        source_body_operation="shift_left",
        semantic_name="binary.shift_left",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    BinaryOperationDescriptor(
        operation_id="shift_right",
        arity=2,
        category="binary",
        source_body_operation="shift_right",
        semantic_name="binary.shift_right",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
)


def lookup_binary_operation_descriptor(
    operation_id: str,
) -> BinaryOperationDescriptor | None:
    for descriptor in SUPPORTED_BINARY_OPERATION_DESCRIPTORS:
        if descriptor.operation_id == operation_id:
            return descriptor
    return None


def supported_binary_operation_ids() -> tuple[str, ...]:
    return tuple(
        descriptor.operation_id
        for descriptor in SUPPORTED_BINARY_OPERATION_DESCRIPTORS
    )
