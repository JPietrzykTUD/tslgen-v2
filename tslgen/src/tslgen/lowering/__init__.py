"""Tiny lowering boundary for the clean restart generator."""

from tslgen.lowering.lowerer import Lowerer, LoweringResult, LoweringStageResult
from tslgen.lowering.model import (
    INPUT_SCALAR_RESULT_TYPE,
    SCALAR_COMPARISON_RESULT_TYPE,
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredResultType,
    LoweredUnaryOperationExpression,
    SelectedImplementationLoweringContext,
    build_selected_implementation_lowering_context,
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
from tslgen.lowering.comparison_operations import (
    SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS,
    ComparisonOperationDescriptor,
    lookup_comparison_operation_descriptor,
    supported_comparison_operation_ids,
)
from tslgen.lowering.scalar_types import (
    SUPPORTED_SCALAR_TYPE_DESCRIPTORS,
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)
from tslgen.lowering.semantic_origin import (
    BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN,
    LoweringSemanticOrigin,
)

__all__ = [
    "BOOTSTRAP_CORE_OPERATION_SEMANTIC_ORIGIN",
    "INPUT_SCALAR_RESULT_TYPE",
    "LoweringSemanticOrigin",
    "LoweredBinaryOperationExpression",
    "LoweredComparisonOperationExpression",
    "LoweredExpression",
    "LoweredFunction",
    "LoweredFunctionBody",
    "LoweredFunctionSet",
    "LoweredFunctionSignature",
    "LoweredParameter",
    "LoweredParameterRef",
    "LoweredReturnStatement",
    "LoweredResultType",
    "LoweredUnaryOperationExpression",
    "SelectedImplementationLoweringContext",
    "Lowerer",
    "LoweringResult",
    "LoweringStageResult",
    "SCALAR_COMPARISON_RESULT_TYPE",
    "build_selected_implementation_lowering_context",
    "SUPPORTED_BINARY_OPERATION_DESCRIPTORS",
    "BinaryOperationDescriptor",
    "lookup_binary_operation_descriptor",
    "supported_binary_operation_ids",
    "SUPPORTED_UNARY_OPERATION_DESCRIPTORS",
    "UnaryOperationDescriptor",
    "lookup_unary_operation_descriptor",
    "supported_unary_operation_ids",
    "SUPPORTED_COMPARISON_OPERATION_DESCRIPTORS",
    "ComparisonOperationDescriptor",
    "lookup_comparison_operation_descriptor",
    "supported_comparison_operation_ids",
    "SUPPORTED_SCALAR_TYPE_DESCRIPTORS",
    "ScalarTypeDescriptor",
    "lookup_scalar_type_descriptor",
    "supported_scalar_type_tags",
]
