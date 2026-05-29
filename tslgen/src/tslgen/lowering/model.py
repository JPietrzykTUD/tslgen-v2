"""Backend-neutral lowered function and type values for the clean slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Implementation,
    Primitive,
    PrimitiveAttribute,
    PrimitiveCall,
    PrimitiveCallArgument,
    PrimitiveCallTarget,
)
from tslgen.domain.catalog import ExtensionName, TypeTag
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.comparison_operations import ComparisonOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor

LoweredResultTypeKind = Literal["input_scalar", "scalar_comparison"]
LoweredVectorMemberKind = Literal[
    "register",
    "mask",
    "imask",
    "mask_underlying",
    "offset_base",
]
LoweredBaseTransformKind = Literal["signed_of", "unsigned_of", "generic", "id"]
LoweredVectorTransformKind = Literal["transform", "transform_extension"]
LoweredGenerationValueKind = Literal[
    "generation.integer_literal",
    "vector.length",
    "vector.alignment",
    "type.size_bytes",
    "type.is_signed",
    "type.is_same",
    "primitive.attribute",
    "generation.integer_comparison",
    "generation.arithmetic.add",
    "generation.arithmetic.sub",
    "generation.arithmetic.mul",
    "generation.arithmetic.div",
    "generation.arithmetic.rem",
]
LoweredGenerationValuePayload = int | bool
GenerationVariableDeclarationSelector = Literal[
    "init_register",
    "infer",
    "const_infer",
    "typed",
]

CURRENT_VECTOR_KEYWORD = "Vec"
CURRENT_SCALAR_KEYWORD = "scalar"


@dataclass(frozen=True, slots=True)
class SelectedImplementationLoweringContext:
    target: Target
    primitive: Primitive
    implementation: Implementation
    primitive_name: str
    primitive_attributes: tuple[PrimitiveAttribute, ...]
    backend: str
    extension: ExtensionName
    type_tag: TypeTag
    signature: str
    template: str
    parameter_names: tuple[str, ...]
    primitive_source: SourceLocation
    implementation_source: SourceLocation
    current_vector_keyword: str = CURRENT_VECTOR_KEYWORD
    current_scalar_keyword: str = CURRENT_SCALAR_KEYWORD


@dataclass(frozen=True, slots=True)
class CurrentVector:
    extension: ExtensionName
    type_tag: TypeTag


@dataclass(frozen=True, slots=True)
class LoweredCurrentScalarType:
    type_tag: TypeTag


@dataclass(frozen=True, slots=True)
class LoweredScalarTypeIdentity:
    type_tag: TypeTag


@dataclass(frozen=True, slots=True)
class LoweredSizeType:
    pass


@dataclass(frozen=True, slots=True)
class LoweredIntrinsicVectorImaskType:
    pass


@dataclass(frozen=True, slots=True)
class LoweredSpecializationTypeSymbol:
    name: str


@dataclass(frozen=True, slots=True)
class LoweredVectorMemberType:
    member: LoweredVectorMemberKind
    extension: ExtensionName
    type_tag: TypeTag


@dataclass(frozen=True, slots=True)
class LoweredBaseTransformType:
    transform: LoweredBaseTransformKind
    value: LoweredTypeValue


@dataclass(frozen=True, slots=True)
class LoweredGenericRegisterType:
    vector_type: LoweredTypeValue


@dataclass(frozen=True, slots=True)
class LoweredVectorTransformType:
    transform: LoweredVectorTransformKind
    base_type: LoweredTypeValue
    extension: ExtensionName


@dataclass(frozen=True, slots=True)
class LoweredVectorAsExtensionType:
    base_type: LoweredTypeValue
    extension: ExtensionName


@dataclass(frozen=True, slots=True)
class LoweredTypeIsSamePredicate:
    left: LoweredTypeValue
    right: LoweredTypeValue


LoweredTypePredicate = LoweredTypeIsSamePredicate


@dataclass(frozen=True, slots=True)
class LoweredTypeSelectType:
    condition: LoweredTypePredicate
    then_type: LoweredTypeValue
    else_type: LoweredTypeValue


@dataclass(frozen=True, slots=True)
class BackendTypeSpellingRequest:
    backend: str
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredBackendTypeReference:
    request: BackendTypeSpellingRequest


LoweredTypeValue = (
    LoweredBackendTypeReference
    | LoweredBaseTransformType
    | LoweredCurrentScalarType
    | CurrentVector
    | LoweredGenericRegisterType
    | LoweredIntrinsicVectorImaskType
    | LoweredScalarTypeIdentity
    | LoweredSizeType
    | LoweredSpecializationTypeSymbol
    | LoweredTypeSelectType
    | LoweredVectorAsExtensionType
    | LoweredVectorMemberType
    | LoweredVectorTransformType
)


@dataclass(frozen=True, slots=True)
class LoweredTypeAliasBinding:
    alias_name: str
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelectedTypeEnvironment:
    context: SelectedImplementationLoweringContext
    context_symbols: tuple[str, ...]
    alias_bindings: tuple[LoweredTypeAliasBinding, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class ExtensionOperand:
    name: ExtensionName
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelectorSymbol:
    name: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelectorLiteral:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelectorAttribute:
    key: str
    value: str
    source: SourceLocation
    key_argument: str | None = None


SelectorSpecializationValue = (
    LoweredTypeValue | ExtensionOperand | SelectorLiteral | SelectorSymbol
)


@dataclass(frozen=True, slots=True)
class PrimitiveCallSelectorPayload:
    target: PrimitiveCallTarget
    specializations: tuple[SelectorSpecializationValue, ...]
    attributes: tuple[SelectorAttribute, ...]
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCallSelectorPayloadLoweringResult:
    payload: PrimitiveCallSelectorPayload | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveCallTargetMatch:
    selected: SelectedImplementation
    selector_payload: PrimitiveCallSelectorPayload
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCallTargetMatchingResult:
    match: PrimitiveCallTargetMatch | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveCallArgumentBinding:
    parameter_name: str
    argument: PrimitiveCallArgument


@dataclass(frozen=True, slots=True)
class PrimitiveCallReference:
    primitive_call: PrimitiveCall
    target_match: PrimitiveCallTargetMatch
    bindings: tuple[PrimitiveCallArgumentBinding, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCallArgumentBindingResult:
    reference: PrimitiveCallReference | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweredPrimitiveCallExpression:
    reference: PrimitiveCallReference


@dataclass(frozen=True, slots=True)
class PrimitiveCallExpressionLoweringResult:
    expression: LoweredPrimitiveCallExpression | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveCallReferenceInventory:
    references: tuple[PrimitiveCallReference, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveCallDependencyClosure:
    selected: tuple[SelectedImplementation, ...]
    references: tuple[PrimitiveCallReference, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class TypeExpressionLoweringResult:
    value: LoweredTypeValue | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendTypeQueryLoweringResult:
    request: BackendTypeSpellingRequest | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweredGenerationValue:
    kind: LoweredGenerationValueKind
    value: LoweredGenerationValuePayload
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationValueQueryLoweringResult:
    value: LoweredGenerationValue | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweredGenerationControlBranch:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredGenerationControlRegion:
    condition: LoweredGenerationValue
    selected_branch: LoweredGenerationControlBranch
    unselected_branch: LoweredGenerationControlBranch
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationControlRegionLoweringResult:
    region: LoweredGenerationControlRegion | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopBody:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopRegion:
    index_name: str
    start: LoweredGenerationValue
    end: LoweredGenerationValue
    step: LoweredGenerationValue
    body: LoweredGenerationLoopBody
    source: SourceLocation
    unroll_count: LoweredGenerationValue | None = None


@dataclass(frozen=True, slots=True)
class GenerationLoopRegionLoweringResult:
    region: LoweredGenerationLoopRegion | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopRegionSegment:
    region: LoweredGenerationLoopRegion
    source: SourceLocation


LoweredGenerationLoopDiscoverySegment = (
    LoweredGenerationLoopOpaqueSegment | LoweredGenerationLoopRegionSegment
)


@dataclass(frozen=True, slots=True)
class LoweredGenerationLoopDiscovery:
    segments: tuple[LoweredGenerationLoopDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationLoopDiscoveryLoweringResult:
    discovery: LoweredGenerationLoopDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationText:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationRequest:
    selector: GenerationVariableDeclarationSelector
    name: str
    name_source: SourceLocation
    payload_text: str
    source: SourceLocation
    explicit_type: GenerationVariableDeclarationText | None = None
    initializer: GenerationVariableDeclarationText | None = None


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationRequestSegment:
    declaration: GenerationVariableDeclarationRequest
    source: SourceLocation


GenerationVariableDeclarationDiscoverySegment = (
    GenerationVariableDeclarationOpaqueSegment
    | GenerationVariableDeclarationRequestSegment
)


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationDiscovery:
    segments: tuple[GenerationVariableDeclarationDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class GenerationVariableDeclarationDiscoveryLoweringResult:
    discovery: GenerationVariableDeclarationDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


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
        extension=ExtensionName(selected.implementation.extension),
        type_tag=TypeTag(selected.implementation.type_tag),
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
    | LoweredPrimitiveCallExpression
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


@dataclass(frozen=True, slots=True)
class PrimitiveCallClosureLoweringPackage:
    closure: PrimitiveCallDependencyClosure
    lowered_functions: LoweredFunctionSet
    diagnostics: tuple[Diagnostic, ...]
