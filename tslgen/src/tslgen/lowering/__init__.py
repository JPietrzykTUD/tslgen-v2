"""Tiny lowering boundary for the clean restart generator."""

from tslgen.lowering.lowerer import Lowerer, LoweringResult
from tslgen.lowering.model import (
    LoweredBinaryOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
)
from tslgen.lowering.binary_operations import (
    SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
    BinaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    supported_binary_operation_ids,
)
from tslgen.lowering.scalar_types import (
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)

__all__ = [
    "LoweredBinaryOperationExpression",
    "LoweredFunction",
    "LoweredFunctionBody",
    "LoweredParameter",
    "LoweredParameterRef",
    "LoweredReturnStatement",
    "Lowerer",
    "LoweringResult",
    "SUPPORTED_BINARY_OPERATION_DESCRIPTORS",
    "BinaryOperationDescriptor",
    "lookup_binary_operation_descriptor",
    "supported_binary_operation_ids",
    "SUPPORTED_SCALAR_TYPE_DESCRIPTORS",
    "ScalarTypeDescriptor",
    "lookup_scalar_type_descriptor",
    "supported_scalar_type_tags",
]
