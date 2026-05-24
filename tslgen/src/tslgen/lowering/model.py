"""Backend-neutral lowered function values for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.comparison_operations import ComparisonOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor

LoweredResultTypeKind = Literal["input_scalar", "scalar_comparison"]


@dataclass(frozen=True, slots=True)
class LoweredResultType:
    result_id: str
    kind: LoweredResultTypeKind


INPUT_SCALAR_RESULT_TYPE = LoweredResultType(
    result_id="input_scalar",
    kind="input_scalar",
)
SCALAR_COMPARISON_RESULT_TYPE = LoweredResultType(
    result_id="scalar_comparison",
    kind="scalar_comparison",
)


@dataclass(frozen=True, slots=True)
class LoweredParameter:
    name: str


@dataclass(frozen=True, slots=True)
class LoweredParameterRef:
    parameter_name: str


@dataclass(frozen=True, slots=True)
class LoweredBinaryOperationExpression:
    operation: BinaryOperationDescriptor
    left: LoweredParameterRef
    right: LoweredParameterRef


@dataclass(frozen=True, slots=True)
class LoweredUnaryOperationExpression:
    operation: UnaryOperationDescriptor
    value: LoweredParameterRef


@dataclass(frozen=True, slots=True)
class LoweredComparisonOperationExpression:
    operation: ComparisonOperationDescriptor
    left: LoweredParameterRef
    right: LoweredParameterRef


LoweredExpression = (
    LoweredBinaryOperationExpression
    | LoweredUnaryOperationExpression
    | LoweredComparisonOperationExpression
)


@dataclass(frozen=True, slots=True)
class LoweredReturnStatement:
    expression: LoweredExpression
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredFunctionBody:
    return_statement: LoweredReturnStatement


@dataclass(frozen=True, slots=True)
class LoweredFunctionSignature:
    name: str
    primitive_name: str
    parameters: tuple[LoweredParameter, ...]
    scalar_type: ScalarTypeDescriptor
    result_type: LoweredResultType = INPUT_SCALAR_RESULT_TYPE


@dataclass(frozen=True, slots=True)
class LoweredFunction:
    signature: LoweredFunctionSignature
    body: LoweredFunctionBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredFunctionSet:
    functions: tuple[LoweredFunction, ...]
