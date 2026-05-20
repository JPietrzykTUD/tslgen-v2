from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactPredicatePathStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
)
from tslgen.lowering._array_body_package import (
    ExactArrayBodyStructuralPackageIr,
)
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
)
from tslgen.lowering._generation_models import (
    GenerationExpressionRecognition,
    GenerationPredicate,
    GenerationSizeByteBranchChainPruning,
    GenerationValue,
    PrunedGenerationBranch,
)
from tslgen.lowering._selected_body_models import (
    NoSelectedAssignmentDirectIntrinsicBodyIr,
    NoSelectedBodyEnvelopeIr,
    NoSelectedBranchBodyAssignmentFormRecognition,
    NoSelectedBranchBodyHandoff,
    OpaqueSelectedBranchBodyHandoff,
    SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeIr,
    SelectedBranchBodyAssignmentFormRecognition,
)


type GenerationLoweringStageName = Literal[
    "helper_expression_recognition",
    "typed_generation_value",
    "typed_generation_predicate",
    "generation_control_flow_pruning",
    "selected_body_lowering",
    "selected_body_form_recognition",
    "selected_body_ir_lowering",
    "selected_body_envelope_lowering",
    "array_body_envelope_slot_assembly",
    "array_initialization_slot_form_lowering",
    "array_initialization_helper_request_lowering",
    "array_initialization_base_type_request_resolution",
    "array_initialization_vector_length_request_resolution",
    "array_initialization_vector_alignment_request_resolution",
    "array_initialization_helper_set_completion",
    "array_initialization_declaration_shell_lowering",
    "array_body_structural_sequence_classification",
    "predicate_path_structural_request_lowering",
    "post_branch_intrinsic_call_site_structural_request_lowering",
    "return_emission_structural_request_lowering",
    "array_body_structural_package_assembly",
    "array_backend_deferred_request_inventory",
]
type TsilBinaryOperator = Literal["+"]


@dataclass(frozen=True, slots=True)
class TsilParameterReference:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TSIL parameter reference name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("parameter", self.name)


@dataclass(frozen=True, slots=True)
class TsilBinaryExpression:
    operator: TsilBinaryOperator
    left: TsilParameterReference
    right: TsilParameterReference

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "binary",
            self.operator,
            self.left.key,
            self.right.key,
        )


@dataclass(frozen=True, slots=True)
class TsilIntrinsicComposeExpression:
    intrinsic: str
    arguments: tuple[TsilParameterReference, ...]

    def __post_init__(self) -> None:
        if not self.intrinsic:
            raise ValueError("TSIL intrinsic-compose intrinsic must be non-empty")
        object.__setattr__(self, "arguments", tuple(self.arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "intrin_compose",
            self.intrinsic,
            tuple(argument.key for argument in self.arguments),
        )


type TsilExpression = (
    TsilParameterReference | TsilBinaryExpression | TsilIntrinsicComposeExpression
)


@dataclass(frozen=True, slots=True)
class TsilReturnStatement:
    expression: TsilExpression

    @property
    def key(self) -> tuple[object, ...]:
        return ("return", self.expression.key)


type TsilStatement = TsilReturnStatement
type GenerationLoweringStageOutput = (
    GenerationExpressionRecognition
    | GenerationValue
    | GenerationPredicate
    | PrunedGenerationBranch
    | GenerationSizeByteBranchChainPruning
    | OpaqueSelectedBranchBodyHandoff
    | NoSelectedBranchBodyHandoff
    | SelectedBranchBodyAssignmentFormRecognition
    | NoSelectedBranchBodyAssignmentFormRecognition
    | SelectedAssignmentDirectIntrinsicBodyIr
    | NoSelectedAssignmentDirectIntrinsicBodyIr
    | SelectedBodyEnvelopeIr
    | NoSelectedBodyEnvelopeIr
    | ExactArrayBodyEnvelopeIr
    | ExactArrayInitializationSlotFormIr
    | ExactArrayInitializationHelperRequestIr
    | ExactArrayInitializationBaseTypeResolutionIr
    | ExactArrayInitializationVectorLengthResolutionIr
    | ExactArrayInitializationVectorAlignmentResolutionIr
    | ExactArrayInitializationHelperSetCompletionIr
    | ExactArrayInitializationDeclarationShellIr
    | ExactArrayBodyStructuralSequenceIr
    | ExactPredicatePathStructuralRequestIr
    | ExactPostBranchIntrinsicCallSiteStructuralRequestIr
    | ExactReturnEmissionStructuralRequestIr
    | ExactArrayBodyStructuralPackageIr
    | ExactArrayBackendDeferredRequestInventoryIr
    | TsilStatement
)


@dataclass(frozen=True, slots=True)
class GenerationLoweringStageOutputContract:
    stage: GenerationLoweringStageName
    output_types: tuple[type[object], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_types", tuple(self.output_types))
        if not self.output_types:
            raise ValueError("generation lowering stage contract must have outputs")

    @property
    def expected_type_names(self) -> str:
        return ", ".join(item.__name__ for item in self.output_types)


_GENERATION_LOWERING_STAGE_OUTPUT_CONTRACTS: tuple[
    GenerationLoweringStageOutputContract,
    ...,
] = (
    GenerationLoweringStageOutputContract(
        "helper_expression_recognition",
        (GenerationExpressionRecognition,),
    ),
    GenerationLoweringStageOutputContract(
        "typed_generation_value",
        (GenerationValue,),
    ),
    GenerationLoweringStageOutputContract(
        "typed_generation_predicate",
        (GenerationPredicate,),
    ),
    GenerationLoweringStageOutputContract(
        "generation_control_flow_pruning",
        (PrunedGenerationBranch, GenerationSizeByteBranchChainPruning),
    ),
    GenerationLoweringStageOutputContract(
        "selected_body_lowering",
        (
            TsilReturnStatement,
            OpaqueSelectedBranchBodyHandoff,
            NoSelectedBranchBodyHandoff,
        ),
    ),
    GenerationLoweringStageOutputContract(
        "selected_body_form_recognition",
        (
            SelectedBranchBodyAssignmentFormRecognition,
            NoSelectedBranchBodyAssignmentFormRecognition,
        ),
    ),
    GenerationLoweringStageOutputContract(
        "selected_body_ir_lowering",
        (
            SelectedAssignmentDirectIntrinsicBodyIr,
            NoSelectedAssignmentDirectIntrinsicBodyIr,
        ),
    ),
    GenerationLoweringStageOutputContract(
        "selected_body_envelope_lowering",
        (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
    ),
    GenerationLoweringStageOutputContract(
        "array_body_envelope_slot_assembly",
        (ExactArrayBodyEnvelopeIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_slot_form_lowering",
        (ExactArrayInitializationSlotFormIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_helper_request_lowering",
        (ExactArrayInitializationHelperRequestIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_base_type_request_resolution",
        (ExactArrayInitializationBaseTypeResolutionIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_vector_length_request_resolution",
        (ExactArrayInitializationVectorLengthResolutionIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_vector_alignment_request_resolution",
        (ExactArrayInitializationVectorAlignmentResolutionIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_helper_set_completion",
        (ExactArrayInitializationHelperSetCompletionIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_initialization_declaration_shell_lowering",
        (ExactArrayInitializationDeclarationShellIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_body_structural_sequence_classification",
        (ExactArrayBodyStructuralSequenceIr,),
    ),
    GenerationLoweringStageOutputContract(
        "predicate_path_structural_request_lowering",
        (ExactPredicatePathStructuralRequestIr,),
    ),
    GenerationLoweringStageOutputContract(
        "post_branch_intrinsic_call_site_structural_request_lowering",
        (ExactPostBranchIntrinsicCallSiteStructuralRequestIr,),
    ),
    GenerationLoweringStageOutputContract(
        "return_emission_structural_request_lowering",
        (ExactReturnEmissionStructuralRequestIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_body_structural_package_assembly",
        (ExactArrayBodyStructuralPackageIr,),
    ),
    GenerationLoweringStageOutputContract(
        "array_backend_deferred_request_inventory",
        (ExactArrayBackendDeferredRequestInventoryIr,),
    ),
)
_GENERATION_LOWERING_STAGE_OUTPUT_CONTRACT_BY_STAGE: dict[
    str,
    GenerationLoweringStageOutputContract,
] = {
    contract.stage: contract
    for contract in _GENERATION_LOWERING_STAGE_OUTPUT_CONTRACTS
}


def _stage_output_contract(stage: str) -> GenerationLoweringStageOutputContract:
    contract = _GENERATION_LOWERING_STAGE_OUTPUT_CONTRACT_BY_STAGE.get(stage)
    if contract is None:
        raise ValueError(f"unknown generation lowering stage: {stage!r}")
    return contract


def validate_generation_lowering_stage_output(
    stage: str,
    output: object,
) -> None:
    contract = _stage_output_contract(stage)
    if not isinstance(output, contract.output_types):
        raise TypeError(
            f"{stage} stage requires output type {contract.expected_type_names}"
        )


@dataclass(frozen=True, slots=True)
class GenerationLoweringStage:
    stage: GenerationLoweringStageName
    output: GenerationLoweringStageOutput

    def __post_init__(self) -> None:
        validate_generation_lowering_stage_output(self.stage, self.output)

    @property
    def key(self) -> tuple[object, ...]:
        return (self.stage, self.output.key)
