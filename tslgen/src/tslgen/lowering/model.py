"""Backend-neutral lowered function values for the tiny clean slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor


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


LoweredExpression = LoweredBinaryOperationExpression | LoweredUnaryOperationExpression


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


@dataclass(frozen=True, slots=True)
class LoweredFunction:
    signature: LoweredFunctionSignature
    body: LoweredFunctionBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredFunctionSet:
    functions: tuple[LoweredFunction, ...]
