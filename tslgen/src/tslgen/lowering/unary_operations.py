"""Lowering-owned unary operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

from tslgen.lowering.semantic_origin import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    LoweringSemanticOrigin,
)

UnaryOperationCategory = Literal["unary"]


@dataclass(frozen=True, slots=True)
class UnaryOperationDescriptor:
    operation_id: str
    arity: int
    category: UnaryOperationCategory
    source_body_operation: str
    semantic_name: str
    semantic_origin: LoweringSemanticOrigin = (
        BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN
    )


SUPPORTED_UNARY_OPERATION_DESCRIPTORS: tuple[UnaryOperationDescriptor, ...] = (
    UnaryOperationDescriptor(
        operation_id="bit_not",
        arity=1,
        category="unary",
        source_body_operation="bit_not",
        semantic_name="unary.bit_not",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    UnaryOperationDescriptor(
        operation_id="neg",
        arity=1,
        category="unary",
        source_body_operation="neg",
        semantic_name="unary.neg",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
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
