"""Backend-neutral lowered function and type values for the clean slice."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from tslgen.analysis.selection import (
    SelectedImplementation,
    Target,
    TargetSpecializationBinding,
)
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
    "generic.length",
    "generic.runtime_length",
    "generation.integer_comparison",
    "generation.boolean_condition",
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
BackendControlDirectiveName = Literal["if", "else", "switch"]
BackendControlDirectiveSelector = Literal["compile"]
BackendIntrinsicKind = Literal["intrin", "intrin_compose"]
BackendIntrinsicModifierName = Literal[
    "suffix",
    "prefix",
    "post",
    "infix",
    "infix_sep",
    "immediate",
]
SourceOperationKind = Literal["cast", "mem", "io"]
MaskLaneConstantPolarity = Literal["all_true", "all_false"]
BackendValueUninitKind = Literal["array", "scalar"]
BackendValueConstantName = Literal["x86::mm_fround_to_zero"]

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
    selected_specialization_bindings: tuple[TargetSpecializationBinding, ...] = ()
    current_vector_keyword: str = CURRENT_VECTOR_KEYWORD
    current_scalar_keyword: str = CURRENT_SCALAR_KEYWORD


class CastSourceOperationSelector(Enum):
    STATIC = "static"
    REINTERPRET = "reinterpret"
    BITCAST = "bitcast"
    SATURATING = "saturating"


class MemorySourceOperationSelector(Enum):
    COPY = "copy"
    ALLOC = "alloc"
    ALLOC_ALIGNED = "alloc_aligned"
    FREE = "free"


class IoSourceOperationSelector(Enum):
    WRITE = "write"
    WRITE_BASE = "write_base"
    WRITE_BIN = "write_bin"
    ENDL = "endl"


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
    selected_return_binding_names: tuple[str | None, ...] = ()


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
class BackendTypeQueryRequestIsland:
    payload_text: str
    payload_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeQueryOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeQueryOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeQueryRequestIslandSegment:
    request: BackendTypeQueryRequestIsland
    source: SourceLocation


BackendTypeQueryDiscoverySegment = (
    BackendTypeQueryOpaqueTextSegment
    | BackendTypeQueryOpaqueTokenSegment
    | BackendTypeQueryRequestIslandSegment
)


@dataclass(frozen=True, slots=True)
class BackendTypeQueryDiscovery:
    segments: tuple[BackendTypeQueryDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeQueryDiscoveryLoweringResult:
    discovery: BackendTypeQueryDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendTypeQueryHandoffRequestSegment:
    request: BackendTypeSpellingRequest
    island: BackendTypeQueryRequestIsland
    source: SourceLocation


BackendTypeQueryHandoffSegment = (
    BackendTypeQueryOpaqueTextSegment
    | BackendTypeQueryOpaqueTokenSegment
    | BackendTypeQueryHandoffRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendTypeQueryHandoff:
    segments: tuple[BackendTypeQueryHandoffSegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendTypeQueryHandoffLoweringResult:
    handoff: BackendTypeQueryHandoff | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendValueQueryRequest:
    query_text: str
    query_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueQueryOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueQueryOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueQueryRequestSegment:
    request: BackendValueQueryRequest
    source: SourceLocation


BackendValueQueryDiscoverySegment = (
    BackendValueQueryOpaqueTextSegment
    | BackendValueQueryOpaqueTokenSegment
    | BackendValueQueryRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendValueQueryDiscovery:
    segments: tuple[BackendValueQueryDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueQueryDiscoveryLoweringResult:
    discovery: BackendValueQueryDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendValueTypeOperand:
    value: LoweredTypeValue
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueStringLiteralOperand:
    value: str
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueSymbolOperand:
    text: str
    source: SourceLocation


BackendValueSuffixOperand = (
    BackendValueTypeOperand
    | BackendValueStringLiteralOperand
    | BackendValueSymbolOperand
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicSuffixValueRequest:
    backend: str
    argument: BackendValueSuffixOperand | None
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicPrefixValueRequest:
    backend: str
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendUninitValueRequest:
    backend: str
    kind: BackendValueUninitKind
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendConstantValueRequest:
    backend: str
    name: BackendValueConstantName
    source_text: str
    source: SourceLocation


BackendValueRequest = (
    BackendIntrinsicSuffixValueRequest
    | BackendIntrinsicPrefixValueRequest
    | BackendUninitValueRequest
    | BackendConstantValueRequest
)


@dataclass(frozen=True, slots=True)
class BackendValueQueryHandoffRequestSegment:
    request: BackendValueRequest
    island: BackendValueQueryRequest
    source: SourceLocation


BackendValueQueryHandoffSegment = (
    BackendValueQueryOpaqueTextSegment
    | BackendValueQueryOpaqueTokenSegment
    | BackendValueQueryHandoffRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendValueQueryHandoff:
    segments: tuple[BackendValueQueryHandoffSegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendValueQueryHandoffLoweringResult:
    handoff: BackendValueQueryHandoff | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class MaskLaneConstantRequest:
    polarity: MaskLaneConstantPolarity
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskLaneConstantOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskLaneConstantOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskLaneConstantRequestSegment:
    request: MaskLaneConstantRequest
    source: SourceLocation


MaskLaneConstantDiscoverySegment = (
    MaskLaneConstantOpaqueTextSegment
    | MaskLaneConstantOpaqueTokenSegment
    | MaskLaneConstantRequestSegment
)


@dataclass(frozen=True, slots=True)
class MaskLaneConstantDiscovery:
    segments: tuple[MaskLaneConstantDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskLaneConstantDiscoveryLoweringResult:
    discovery: MaskLaneConstantDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendControlDirectiveRequest:
    directive_name: BackendControlDirectiveName
    selector: BackendControlDirectiveSelector
    selector_source: SourceLocation
    source_text: str
    source: SourceLocation
    payload_text: str | None = None
    payload_source: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class BackendControlDirectiveOpaqueSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendControlDirectiveRequestSegment:
    request: BackendControlDirectiveRequest
    source: SourceLocation


BackendControlDirectiveDiscoverySegment = (
    BackendControlDirectiveOpaqueSegment | BackendControlDirectiveRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendControlDirectiveDiscovery:
    segments: tuple[BackendControlDirectiveDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendControlDirectiveDiscoveryLoweringResult:
    discovery: BackendControlDirectiveDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendIntrinsicRequest:
    intrinsic_kind: BackendIntrinsicKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicRequestSegment:
    request: BackendIntrinsicRequest
    source: SourceLocation


BackendIntrinsicDiscoverySegment = (
    BackendIntrinsicOpaqueTextSegment
    | BackendIntrinsicOpaqueTokenSegment
    | BackendIntrinsicRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicDiscovery:
    segments: tuple[BackendIntrinsicDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicDiscoveryLoweringResult:
    discovery: BackendIntrinsicDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierBackendValueOperand:
    request: BackendValueRequest
    island: BackendValueQueryRequest
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierSymbolOperand:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierIntegerOperand:
    value: int
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierStringOperand:
    value: str
    source_text: str
    source: SourceLocation


BackendIntrinsicModifierOperand = (
    BackendIntrinsicModifierBackendValueOperand
    | BackendIntrinsicModifierIntegerOperand
    | BackendIntrinsicModifierStringOperand
    | BackendIntrinsicModifierSymbolOperand
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierField:
    name: BackendIntrinsicModifierName
    key_text: str
    value: BackendIntrinsicModifierOperand
    source_text: str
    source: SourceLocation
    key_source: SourceLocation
    value_source: SourceLocation
    immediate_index: int | None = None
    immediate_index_text: str | None = None


@dataclass(frozen=True, slots=True)
class BackendDirectIntrinsicHandoffRequest:
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicComposeHandoffRequest:
    base_text: str
    base_source: SourceLocation
    modifiers: tuple[BackendIntrinsicModifierField, ...]
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation


BackendIntrinsicHandoffRequest = (
    BackendDirectIntrinsicHandoffRequest | BackendIntrinsicComposeHandoffRequest
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicHandoffRequestSegment:
    request: BackendIntrinsicHandoffRequest
    island: BackendIntrinsicRequest
    source: SourceLocation


BackendIntrinsicHandoffSegment = (
    BackendIntrinsicOpaqueTextSegment
    | BackendIntrinsicOpaqueTokenSegment
    | BackendIntrinsicHandoffRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicHandoff:
    segments: tuple[BackendIntrinsicHandoffSegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicHandoffLoweringResult:
    handoff: BackendIntrinsicHandoff | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class SourceOperationRequest:
    operation_kind: SourceOperationKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceOperationOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceOperationOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceOperationRequestSegment:
    request: SourceOperationRequest
    source: SourceLocation


SourceOperationDiscoverySegment = (
    SourceOperationOpaqueTextSegment
    | SourceOperationOpaqueTokenSegment
    | SourceOperationRequestSegment
)


@dataclass(frozen=True, slots=True)
class SourceOperationDiscovery:
    segments: tuple[SourceOperationDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceOperationDiscoveryLoweringResult:
    discovery: SourceOperationDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class CastSourceOperationHandoffRequest:
    selector: CastSourceOperationSelector
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MemorySourceOperationHandoffRequest:
    selector: MemorySourceOperationSelector
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class IoSourceOperationHandoffRequest:
    selector: IoSourceOperationSelector
    source: SourceLocation


SourceOperationHandoffRequest = (
    CastSourceOperationHandoffRequest
    | MemorySourceOperationHandoffRequest
    | IoSourceOperationHandoffRequest
)


@dataclass(frozen=True, slots=True)
class SourceOperationHandoffRequestSegment:
    request: SourceOperationHandoffRequest
    island: SourceOperationRequest
    source: SourceLocation


SourceOperationHandoffSegment = (
    SourceOperationOpaqueTextSegment
    | SourceOperationOpaqueTokenSegment
    | SourceOperationHandoffRequestSegment
)


@dataclass(frozen=True, slots=True)
class SourceOperationHandoff:
    segments: tuple[SourceOperationHandoffSegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceOperationHandoffLoweringResult:
    handoff: SourceOperationHandoff | None
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
        selected_specialization_bindings=selected.target.specialization_bindings,
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
