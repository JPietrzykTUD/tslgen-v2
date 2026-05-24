"""Backend-neutral lowered function values for the tiny clean slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering.scalar_types import ScalarTypeDescriptor


@dataclass(frozen=True, slots=True)
class LoweredParameter:
    name: str


@dataclass(frozen=True, slots=True)
class LoweredParameterRef:
    parameter_name: str


@dataclass(frozen=True, slots=True)
class LoweredBinaryAddExpression:
    left: LoweredParameterRef
    right: LoweredParameterRef


@dataclass(frozen=True, slots=True)
class LoweredFunction:
    name: str
    primitive_name: str
    parameters: tuple[LoweredParameter, ...]
    scalar_type: ScalarTypeDescriptor
    expression: LoweredBinaryAddExpression
    source: SourceLocation
