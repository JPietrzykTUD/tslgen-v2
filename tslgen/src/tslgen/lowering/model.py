"""Backend-neutral lowered function values for the tiny M108 slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation


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
    scalar_type_tag: str
    expression: LoweredBinaryAddExpression
    source: SourceLocation
