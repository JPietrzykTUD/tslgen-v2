"""Lowering-owned unary operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

UnaryOperationCategory = Literal["unary"]


@dataclass(frozen=True, slots=True)
class UnaryOperationDescriptor:
    operation_id: str
    arity: int
    category: UnaryOperationCategory
    source_body_operation: str
    semantic_name: str


SUPPORTED_UNARY_OPERATION_DESCRIPTORS: tuple[UnaryOperationDescriptor, ...] = (
    UnaryOperationDescriptor(
        operation_id="bit_not",
        arity=1,
        category="unary",
        source_body_operation="bit_not",
        semantic_name="unary.bit_not",
    ),
    UnaryOperationDescriptor(
        operation_id="neg",
        arity=1,
        category="unary",
        source_body_operation="neg",
        semantic_name="unary.neg",
    ),
)


def lookup_unary_operation_descriptor(
    operation_id: str,
) -> UnaryOperationDescriptor | None:
    for descriptor in SUPPORTED_UNARY_OPERATION_DESCRIPTORS:
        if descriptor.operation_id == operation_id:
            return descriptor
    return None


def supported_unary_operation_ids() -> tuple[str, ...]:
    return tuple(
        descriptor.operation_id
        for descriptor in SUPPORTED_UNARY_OPERATION_DESCRIPTORS
    )
