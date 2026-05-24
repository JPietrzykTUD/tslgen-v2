"""Lowering-owned binary operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

BinaryOperationCategory = Literal["binary"]


@dataclass(frozen=True, slots=True)
class BinaryOperationDescriptor:
    operation_id: str
    arity: int
    category: BinaryOperationCategory
    source_body_operation: str
    semantic_name: str


SUPPORTED_BINARY_OPERATION_DESCRIPTORS: tuple[BinaryOperationDescriptor, ...] = (
    BinaryOperationDescriptor(
        operation_id="add",
        arity=2,
        category="binary",
        source_body_operation="add",
        semantic_name="binary.add",
    ),
    BinaryOperationDescriptor(
        operation_id="sub",
        arity=2,
        category="binary",
        source_body_operation="sub",
        semantic_name="binary.sub",
    ),
    BinaryOperationDescriptor(
        operation_id="mul",
        arity=2,
        category="binary",
        source_body_operation="mul",
        semantic_name="binary.mul",
    ),
    BinaryOperationDescriptor(
        operation_id="div",
        arity=2,
        category="binary",
        source_body_operation="div",
        semantic_name="binary.div",
    ),
    BinaryOperationDescriptor(
        operation_id="mod",
        arity=2,
        category="binary",
        source_body_operation="mod",
        semantic_name="binary.mod",
    ),
    BinaryOperationDescriptor(
        operation_id="bit_and",
        arity=2,
        category="binary",
        source_body_operation="bit_and",
        semantic_name="binary.bit_and",
    ),
    BinaryOperationDescriptor(
        operation_id="bit_or",
        arity=2,
        category="binary",
        source_body_operation="bit_or",
        semantic_name="binary.bit_or",
    ),
    BinaryOperationDescriptor(
        operation_id="bit_xor",
        arity=2,
        category="binary",
        source_body_operation="bit_xor",
        semantic_name="binary.bit_xor",
    ),
    BinaryOperationDescriptor(
        operation_id="shift_left",
        arity=2,
        category="binary",
        source_body_operation="shift_left",
        semantic_name="binary.shift_left",
    ),
    BinaryOperationDescriptor(
        operation_id="shift_right",
        arity=2,
        category="binary",
        source_body_operation="shift_right",
        semantic_name="binary.shift_right",
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
