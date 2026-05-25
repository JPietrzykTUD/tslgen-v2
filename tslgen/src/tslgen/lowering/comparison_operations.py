"""Lowering-owned comparison operation descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

from tslgen.lowering.semantic_origin import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    LoweringSemanticOrigin,
)

ComparisonOperationCategory = Literal["comparison"]


@dataclass(frozen=True, slots=True)
class ComparisonOperationDescriptor:
    operation_id: str
    arity: int
    category: ComparisonOperationCategory
    source_body_operation: str
    semantic_name: str
    semantic_origin: LoweringSemanticOrigin = (
        BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN
    )


SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS: tuple[
    ComparisonOperationDescriptor, ...
] = (
    ComparisonOperationDescriptor(
        operation_id="equal",
        arity=2,
        category="comparison",
        source_body_operation="equal",
        semantic_name="comparison.equal",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    ComparisonOperationDescriptor(
        operation_id="nequal",
        arity=2,
        category="comparison",
        source_body_operation="nequal",
        semantic_name="comparison.nequal",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    ComparisonOperationDescriptor(
        operation_id="less_than",
        arity=2,
        category="comparison",
        source_body_operation="less_than",
        semantic_name="comparison.less_than",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    ComparisonOperationDescriptor(
        operation_id="greater_than",
        arity=2,
        category="comparison",
        source_body_operation="greater_than",
        semantic_name="comparison.greater_than",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    ComparisonOperationDescriptor(
        operation_id="less_than_or_equal",
        arity=2,
        category="comparison",
        source_body_operation="less_than_or_equal",
        semantic_name="comparison.less_than_or_equal",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    ),
    ComparisonOperationDescriptor(
        operation_id="greater_than_or_equal",
        arity=2,
        category="comparison",
        source_body_operation="greater_than_or_equal",
        semantic_name="comparison.greater_than_or_equal",
        semantic_origin=BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
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
