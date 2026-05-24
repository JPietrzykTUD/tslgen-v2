"""Lowering-owned comparison operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

ComparisonOperationCategory = Literal["comparison"]


@dataclass(frozen=True, slots=True)
class ComparisonOperationDescriptor:
    operation_id: str
    arity: int
    category: ComparisonOperationCategory
    source_body_operation: str
    semantic_name: str


SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS: tuple[
    ComparisonOperationDescriptor, ...
] = (
    ComparisonOperationDescriptor(
        operation_id="equal",
        arity=2,
        category="comparison",
        source_body_operation="equal",
        semantic_name="comparison.equal",
    ),
)


def lookup_comparison_operation_descriptor(
    operation_id: str,
) -> ComparisonOperationDescriptor | None:
    for descriptor in SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS:
        if descriptor.operation_id == operation_id:
            return descriptor
    return None


def supported_comparison_operation_ids() -> tuple[str, ...]:
    return tuple(
        descriptor.operation_id
        for descriptor in SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS
    )
