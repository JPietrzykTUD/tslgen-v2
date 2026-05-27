"""Backend-neutral lowered function values for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Implementation, Primitive, PrimitiveAttribute
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.comparison_operations import ComparisonOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor

LoweredResultTypeKind = Literal["input_scalar", "scalar_comparison"]

CURRENT_VECTOR_KEYWORD = "Vec"
UNRESOLVED_IMPLEMENTATION_TYPE_ALIASES = ("MaskVec", "GenericVec")


@dataclass(frozen=True, slots=True)
class SelectedImplementationLoweringContext:
    target: Target
    primitive: Primitive
    implementation: Implementation
    primitive_name: str
    primitive_attributes: tuple[PrimitiveAttribute, ...]
    backend: str
    extension: str
    type_tag: str
    signature: str
    template: str
    parameter_names: tuple[str, ...]
    primitive_source: SourceLocation
    implementation_source: SourceLocation
    current_vector_keyword: str = CURRENT_VECTOR_KEYWORD
    unresolved_type_aliases: tuple[str, ...] = UNRESOLVED_IMPLEMENTATION_TYPE_ALIASES


def build_selected_implementation_lowering_context(
    selected: SelectedImplementation,
) -> SelectedImplementationLoweringContext:
    return SelectedImplementationLoweringContext(
        target=selected.target,
        primitive=selected.primitive,
        implementation=selected.implementation,
        primitive_name=selected.primitive.name,
        primitive_attributes=selected.primitive.attributes,
        backend=selected.target.backend,
        extension=selected.implementation.extension,
        type_tag=selected.implementation.type_tag,
        signature=selected.primitive.signature,
        template=selected.primitive.template,
        parameter_names=selected.primitive.parameters,
        primitive_source=selected.primitive.source,
        implementation_source=selected.implementation.source,
    )


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
