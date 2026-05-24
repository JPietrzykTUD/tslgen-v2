"""Tiny lowering boundary for the clean restart generator."""

from tslgen.lowering.lowerer import Lowerer, LoweringResult, LoweringStageResult
from tslgen.lowering.model import (
    LoweredBinaryOperationExpression,
    LoweredExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredUnaryOperationExpression,
)
from tslgen.lowering.binary_operations import (
    SUPPORTED_BINARY_OPERATION_DESCRIPTORS,
    BinaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    supported_binary_operation_ids,
)
from tslgen.lowering.unary_operations import (
    SUPPORTED_UNARY_OPERATION_DESCRIPTORS,
    UnaryOperationDescriptor,
    lookup_unary_operation_descriptor,
    supported_unary_operation_ids,
)
from tslgen.lowering.scalar_types import (
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)

__all__ = [
    "LoweredBinaryOperationExpression",
    "LoweredExpression",
    "LoweredFunction",
    "LoweredFunctionBody",
    "LoweredFunctionSet",
    "LoweredFunctionSignature",
    "LoweredParameter",
    "LoweredParameterRef",
    "LoweredReturnStatement",
    "LoweredUnaryOperationExpression",
    "Lowerer",
    "LoweringResult",
    "LoweringStageResult",
    "SUPPORTED_BINARY_OPERATION_DESCRIPTORS",
    "BinaryOperationDescriptor",
    "lookup_binary_operation_descriptor",
    "supported_binary_operation_ids",
    "SUPPORTED_UNARY_OPERATION_DESCRIPTORS",
    "UnaryOperationDescriptor",
    "lookup_unary_operation_descriptor",
    "supported_unary_operation_ids",
    "SUPPORTED_SCALAR_TYPE_DESCRIPTORS",
    "ScalarTypeDescriptor",
    "lookup_scalar_type_descriptor",
    "supported_scalar_type_tags",
]
