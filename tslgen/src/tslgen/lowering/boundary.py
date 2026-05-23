from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.generation_rules import (
    ConcreteIntegerGenerationRuleSet,
    ScalarSizeBytesGenerationRuleSet,
    build_concrete_integer_generation_rule_set_from_catalog,
    build_scalar_size_bytes_generation_rule_set_from_catalog,
    default_concrete_integer_generation_rule_set,
    default_scalar_size_bytes_generation_rule_set,
)
from tslgen.domain.values import CatalogValue
import tslgen.lowering._generation_control_flow as _generation_control_flow
import tslgen.lowering._generation_diagnostics as _generation_diagnostics
import tslgen.lowering._generation_queries as _generation_queries
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics  # noqa: F401
import tslgen.lowering._array_body_lowering as _array_body_lowering
import tslgen.lowering._array_body_models as _array_body_models  # noqa: F401
import tslgen.lowering._array_body_package as _array_body_package
import tslgen.lowering._array_body_backend_deferred_requests as _array_body_backend_deferred_requests
import tslgen.lowering._array_body_completion_package as _array_body_completion_package
import tslgen.lowering._array_body_backend_handoff as _array_body_backend_handoff
import tslgen.lowering._array_body_pipeline as _array_body_pipeline
import tslgen.lowering._array_body_shapes as _array_body_shapes  # noqa: F401
import tslgen.lowering._array_body_sources as _array_body_sources
import tslgen.lowering._array_body_validation as _array_body_validation  # noqa: F401
import tslgen.lowering._lowering_inputs as _lowering_inputs
import tslgen.lowering._lowering_completion_manifest as _lowering_completion_manifest
import tslgen.lowering._lowering_completion_gap_inventory as _lowering_completion_gap_inventory
import tslgen.lowering._lowering_backend_translation_request_inventory as _lowering_backend_translation_request_inventory
import tslgen.lowering._lowering_backend_translation_result as _lowering_backend_translation_result
import tslgen.lowering._lowering_stage_assembly as _stage_assembly
import tslgen.lowering._mini_tsil_lowering as _mini_tsil_lowering
import tslgen.lowering._operation_package as _operation_package
import tslgen.lowering._return_emission as _return_emission
import tslgen.lowering._selected_body_lowering as _selected_body_lowering
import tslgen.lowering._stage_contracts as _stage_contracts  # noqa: F401
from tslgen.lowering._lowering_inputs import (
    ClassifiedPayload as ClassifiedPayload,
    LoweringInput as LoweringInput,
    LoweringStrategy as LoweringStrategy,
    PayloadClassification as PayloadClassification,
)
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    GenerationSelectedBranchBodyAssignmentRecognition,
    GenerationSelectedBranchBodyHandoff,
    GenerationSelectedBranchBodyIr,
    NoSelectedAssignmentDirectIntrinsicBodyIr as NoSelectedAssignmentDirectIntrinsicBodyIr,
    NoSelectedBodyEnvelopeIr as NoSelectedBodyEnvelopeIr,
    NoSelectedBranchBodyAssignmentFormRecognition as NoSelectedBranchBodyAssignmentFormRecognition,
    NoSelectedBranchBodyHandoff as NoSelectedBranchBodyHandoff,
    OpaqueSelectedBranchBodyHandoff as OpaqueSelectedBranchBodyHandoff,
    SelectedAssignmentDirectIntrinsicBodyIr as SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeEntry as SelectedBodyEnvelopeEntry,
    SelectedBodyEnvelopeIr as SelectedBodyEnvelopeIr,
    SelectedBranchBodyAssignmentFormRecognition as SelectedBranchBodyAssignmentFormRecognition,
)
from tslgen.lowering._generation_models import (
    GenerationExpressionRecognition as GenerationExpressionRecognition,  # noqa: F401
    GenerationPredicate,
    GenerationSizeByteBranchChainArm as GenerationSizeByteBranchChainArm,
    GenerationSizeByteBranchChainPruning,
    GenerationTypeRef,
    GenerationTypeRefKind as GenerationTypeRefKind,
    GenerationValue,
    PrunedGenerationBranch,
    TsilPrimitiveAttributeCondition as TsilPrimitiveAttributeCondition,
    TsilTypeSignednessCondition as TsilTypeSignednessCondition,
    _GENERATION_CONDITION_MARKER,
    _GENERATION_TYPE_MARKER,
    _GENERATION_VALUE_MARKER,
    _has_generation_helper,
)
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeOpaqueSlot as ExactArrayBodyEnvelopeOpaqueSlot,
    ExactArrayBodyEnvelopeSelectedSlot as ExactArrayBodyEnvelopeSelectedSlot,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSkeletonKey as ExactArrayBodyEnvelopeSkeletonKey,
    ExactArrayBodyEnvelopeSkeletonRequirement,
    ExactArrayBodyEnvelopeSkeletonSlot,  # noqa: F401
    ExactArrayBodyEnvelopeSlot as ExactArrayBodyEnvelopeSlot,
    ExactArrayBodyEnvelopeSlotLabel as ExactArrayBodyEnvelopeSlotLabel,
    ExactArrayBodyStructuralRoleLabel,  # noqa: F401
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationDeferredBackendUninitValue as ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperLeafFieldName,  # noqa: F401
    ExactArrayInitializationHelperLeafKind as ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperRequestKind,  # noqa: F401
    ExactArrayInitializationHelperRequestRecord as ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationUnresolvedLeaf as ExactArrayInitializationUnresolvedLeaf,
    ExactArrayInitializationVectorAlignmentKind,  # noqa: F401
    ExactArrayInitializationVectorAlignmentMetadata,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorAlignmentValue,  # noqa: F401
    ExactArrayInitializationVectorLengthKind,  # noqa: F401
    ExactArrayInitializationVectorLengthMetadata,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactArrayInitializationVectorLengthValue,  # noqa: F401
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactPredicatePathSelectedUpdateState as ExactPredicatePathSelectedUpdateState,
    ExactPredicatePathStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
)
from tslgen.lowering._array_body_package import (
    ExactArrayBodyStructuralPackageIr,
)
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr as ExactArrayBackendDeferredRequestInventoryIr,
    ExactArrayBackendDeferredRequestInventoryMemberIr as ExactArrayBackendDeferredRequestInventoryMemberIr,
)
from tslgen.lowering._array_body_completion_package import (
    ExactArrayLoweringCompletionPackageIr as ExactArrayLoweringCompletionPackageIr,
    ExactArrayLoweringUnresolvedDependencyIr as ExactArrayLoweringUnresolvedDependencyIr,
)
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffRequestIr as ExactArrayBackendHandoffRequestIr,
    ExactArrayBackendHandoffUnresolvedDependencyRequestIr as ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
)
from tslgen.lowering._operation_package import (
    ExactArrayBackendHandoffOperationPackageEntryIr as ExactArrayBackendHandoffOperationPackageEntryIr,
    LoweringOperationPackageIr as LoweringOperationPackageIr,
    LoweringOperationPackageSourceFamily as LoweringOperationPackageSourceFamily,
    MiniTsilLeafReturnOperationPackageEntryIr as MiniTsilLeafReturnOperationPackageEntryIr,
    SelectedBodyDirectIntrinsicOperationPackageEntryIr as SelectedBodyDirectIntrinsicOperationPackageEntryIr,
)
from tslgen.lowering._stage_contracts import (
    GenerationLoweringStage,
    GenerationLoweringStageName,  # noqa: F401
    GenerationLoweringStageOutput,  # noqa: F401
    TsilBinaryExpression,  # noqa: F401
    TsilIntrinsicComposeExpression,  # noqa: F401
    TsilParameterReference,  # noqa: F401
    TsilReturnStatement,  # noqa: F401
    TsilStatement,
)


_ArrayBodyEnvelopeSkeletonLookup = _array_body_pipeline._ArrayBodyEnvelopeSkeletonLookup
_ExactArrayInitializationStagePipelineResult = _array_body_pipeline._ExactArrayInitializationStagePipelineResult
_array_body_envelope_skeleton_lookup_key = _array_body_pipeline._array_body_envelope_skeleton_lookup_key
_array_body_envelope_m63_lookup_key = _array_body_pipeline._array_body_envelope_m63_lookup_key
_build_array_body_envelope_skeleton_lookup = _array_body_pipeline._build_array_body_envelope_skeleton_lookup
_lower_exact_array_initialization_stage_pipeline = _array_body_pipeline._lower_exact_array_initialization_stage_pipeline
_unused_array_body_envelope_skeleton_diagnostics = _array_body_pipeline._unused_array_body_envelope_skeleton_diagnostics
_stage_output_location = _array_body_sources._stage_output_location

handoff_opaque_selected_branch_body = _selected_body_lowering.handoff_opaque_selected_branch_body
recognize_selected_branch_body_assignment_form = _selected_body_lowering.recognize_selected_branch_body_assignment_form
lower_selected_branch_body_ir = _selected_body_lowering.lower_selected_branch_body_ir
lower_selected_body_envelope = _selected_body_lowering.lower_selected_body_envelope

assemble_exact_array_body_envelope = _array_body_lowering.assemble_exact_array_body_envelope
lower_exact_array_initialization_slot_form = _array_body_lowering.lower_exact_array_initialization_slot_form
lower_exact_array_initialization_helper_requests = _array_body_lowering.lower_exact_array_initialization_helper_requests
lower_exact_array_initialization_base_type_request = _array_body_lowering.lower_exact_array_initialization_base_type_request
lower_exact_array_initialization_vector_length_request = _array_body_lowering.lower_exact_array_initialization_vector_length_request
lower_exact_array_initialization_vector_alignment_request = _array_body_lowering.lower_exact_array_initialization_vector_alignment_request
lower_exact_array_initialization_helper_set_completion = _array_body_lowering.lower_exact_array_initialization_helper_set_completion
lower_exact_array_initialization_declaration_shell = _array_body_lowering.lower_exact_array_initialization_declaration_shell
lower_exact_array_body_structural_sequence = _array_body_lowering.lower_exact_array_body_structural_sequence
lower_exact_predicate_path_structural_request = _array_body_lowering.lower_exact_predicate_path_structural_request
lower_exact_post_branch_intrinsic_call_site_structural_request = _array_body_lowering.lower_exact_post_branch_intrinsic_call_site_structural_request
lower_exact_return_emission_structural_request = _return_emission.lower_exact_return_emission_structural_request
lower_exact_array_body_structural_package = _array_body_package.lower_exact_array_body_structural_package
lower_exact_array_backend_deferred_request_inventory = _array_body_backend_deferred_requests.lower_exact_array_backend_deferred_request_inventory
lower_exact_array_lowering_completion_package = _array_body_completion_package.lower_exact_array_lowering_completion_package
lower_exact_array_backend_handoff_request = _array_body_backend_handoff.lower_exact_array_backend_handoff_request
lower_lowering_operation_package = _operation_package.lower_lowering_operation_package
lower_exact_array_backend_uninit_translation_result = _lowering_backend_translation_result.lower_exact_array_backend_uninit_translation_result
_classify_payload = _lowering_inputs._classify_payload
_unsupported_payload_diagnostic = _lowering_inputs._unsupported_payload_diagnostic
_mini_return_statement = _mini_tsil_lowering._mini_return_statement

ExactArrayBackendUninitTranslationRule = _lowering_backend_translation_result.ExactArrayBackendUninitTranslationRule
ExactArrayBackendUninitTranslationRecordIr = _lowering_backend_translation_result.ExactArrayBackendUninitTranslationRecordIr
ExactArrayBackendUninitTranslationResultIr = _lowering_backend_translation_result.ExactArrayBackendUninitTranslationResultIr

type LoweringStatus = Literal["lowered", "unsupported"]


@dataclass(frozen=True, slots=True)
class GenerationContext:
    values: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    primitive_attributes: FrozenMap[str, CatalogValue] | None = None
    use_candidate_attributes: bool = True
    selected_primitive_name: str | None = None
    emitted_primitive_name: str | None = None
    selected_candidate_id: str | None = None
    normalized_signature: str | None = None
    parameters: tuple[str, ...] = ()
    selected_type_tag: str | None = None
    type_tag_override: str | None = None
    use_candidate_type_tag: bool = True
    concrete_integer_generation_rules: ConcreteIntegerGenerationRuleSet = field(
        default_factory=default_concrete_integer_generation_rule_set
    )
    scalar_size_bytes_generation_rules: ScalarSizeBytesGenerationRuleSet = field(
        default_factory=default_scalar_size_bytes_generation_rule_set
    )
    array_initialization_vector_length_metadata: tuple[
        ExactArrayInitializationVectorLengthMetadata, ...
    ] = ()
    array_initialization_vector_alignment_metadata: tuple[
        ExactArrayInitializationVectorAlignmentMetadata, ...
    ] = ()
    implementation_source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", FrozenMap(self.values.items()))
        if self.primitive_attributes is not None:
            object.__setattr__(
                self,
                "primitive_attributes",
                FrozenMap(self.primitive_attributes.items()),
            )
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(
            self,
            "array_initialization_vector_length_metadata",
            tuple(
                sorted(
                    self.array_initialization_vector_length_metadata,
                    key=lambda metadata: metadata.key,
                )
            ),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_alignment_metadata",
            tuple(
                sorted(
                    self.array_initialization_vector_alignment_metadata,
                    key=lambda metadata: metadata.key,
                )
            ),
        )
        for field_name in (
            "selected_primitive_name",
            "emitted_primitive_name",
            "selected_candidate_id",
            "normalized_signature",
            "selected_type_tag",
            "type_tag_override",
        ):
            value = getattr(self, field_name)
            if value == "":
                raise ValueError(f"generation context {field_name} must be non-empty")
        for parameter in self.parameters:
            if not parameter:
                raise ValueError("generation context parameters must be non-empty")


@dataclass(frozen=True, slots=True)
class LoweringRequest:
    strategy: LoweringStrategy = "mini_tsil"
    backend_id: str | None = None
    generation_context: GenerationContext = field(default_factory=GenerationContext)
    array_body_envelope_skeletons: tuple[ExactArrayBodyEnvelopeSkeleton, ...] = ()
    required_array_body_envelope_skeletons: tuple[
        ExactArrayBodyEnvelopeSkeletonRequirement, ...
    ] = ()
    exact_array_backend_uninit_translation_rules: tuple[ExactArrayBackendUninitTranslationRule, ...] = ()

    def __post_init__(self) -> None:
        if self.strategy not in ("mini_tsil", "typed_opaque"):
            raise ValueError(f"unknown lowering strategy: {self.strategy!r}")
        if self.backend_id is not None and not self.backend_id:
            raise ValueError("lowering backend id must be non-empty when provided")
        object.__setattr__(
            self,
            "array_body_envelope_skeletons",
            tuple(
                sorted(
                    self.array_body_envelope_skeletons,
                    key=lambda skeleton: (
                        _array_body_envelope_skeleton_lookup_key(skeleton).key,
                        skeleton.key,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "required_array_body_envelope_skeletons",
            tuple(
                sorted(
                    self.required_array_body_envelope_skeletons,
                    key=lambda requirement: requirement.key,
                )
            ),
        )
        object.__setattr__(self, "exact_array_backend_uninit_translation_rules", tuple(sorted(self.exact_array_backend_uninit_translation_rules, key=lambda rule: rule.key)))


@dataclass(frozen=True, slots=True)
class LoweringInputSet:
    request: LoweringRequest
    inputs: tuple[LoweringInput, ...]
    inputs_by_candidate_id: FrozenMap[str, LoweringInput] = field(init=False)

    def __post_init__(self) -> None:
        inputs = tuple(sorted(self.inputs, key=lambda item: item.key))
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(
            self,
            "inputs_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in inputs),
        )


def build_catalog_lowering_request(
    catalog: Catalog,
    *,
    strategy: LoweringStrategy = "mini_tsil",
    backend_id: str | None = None,
    generation_context: GenerationContext | None = None,
) -> Result[LoweringRequest]:
    """Build a lowering request with generation rules derived before evaluation."""

    concrete_rules = build_concrete_integer_generation_rule_set_from_catalog(catalog)
    scalar_size_rules = build_scalar_size_bytes_generation_rule_set_from_catalog(catalog)
    diagnostics = (*concrete_rules.diagnostics, *scalar_size_rules.diagnostics)
    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    concrete_rule_set = concrete_rules.unwrap()
    scalar_size_rule_set = scalar_size_rules.unwrap()
    context = (
        GenerationContext(
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
        if generation_context is None
        else replace(
            generation_context,
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
    )
    return Result.ok(
        LoweringRequest(
            strategy=strategy,
            backend_id=backend_id,
            generation_context=context,
        )
    )


@dataclass(frozen=True, slots=True)
class LoweredImplementation:
    candidate_id: str
    status: LoweringStatus
    statements: tuple[TsilStatement, ...] = ()
    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    generation_type_refs: tuple[GenerationTypeRef, ...] = ()
    generation_values: tuple[GenerationValue, ...] = ()
    generation_predicates: tuple[GenerationPredicate, ...] = ()
    generation_branch_chains: tuple[GenerationSizeByteBranchChainPruning, ...] = ()
    selected_branch_body_handoffs: tuple[GenerationSelectedBranchBodyHandoff, ...] = ()
    selected_branch_body_assignment_forms: tuple[
        GenerationSelectedBranchBodyAssignmentRecognition, ...
    ] = ()
    selected_branch_body_irs: tuple[GenerationSelectedBranchBodyIr, ...] = ()
    selected_body_envelopes: tuple[GenerationSelectedBodyEnvelopeIr, ...] = ()
    array_body_envelopes: tuple[ExactArrayBodyEnvelopeIr, ...] = ()
    array_initialization_slot_forms: tuple[
        ExactArrayInitializationSlotFormIr, ...
    ] = ()
    array_initialization_helper_requests: tuple[
        ExactArrayInitializationHelperRequestIr, ...
    ] = ()
    array_initialization_base_type_resolutions: tuple[
        ExactArrayInitializationBaseTypeResolutionIr, ...
    ] = ()
    array_initialization_vector_length_resolutions: tuple[
        ExactArrayInitializationVectorLengthResolutionIr, ...
    ] = ()
    array_initialization_vector_alignment_resolutions: tuple[
        ExactArrayInitializationVectorAlignmentResolutionIr, ...
    ] = ()
    array_initialization_helper_set_completions: tuple[
        ExactArrayInitializationHelperSetCompletionIr, ...
    ] = ()
    array_initialization_declaration_shells: tuple[
        ExactArrayInitializationDeclarationShellIr, ...
    ] = ()
    array_body_structural_sequences: tuple[
        ExactArrayBodyStructuralSequenceIr, ...
    ] = ()
    predicate_path_structural_requests: tuple[
        ExactPredicatePathStructuralRequestIr, ...
    ] = ()
    post_branch_intrinsic_call_site_structural_requests: tuple[
        ExactPostBranchIntrinsicCallSiteStructuralRequestIr, ...
    ] = ()
    return_emission_structural_requests: tuple[
        ExactReturnEmissionStructuralRequestIr, ...
    ] = ()
    array_body_structural_packages: tuple[
        ExactArrayBodyStructuralPackageIr, ...
    ] = ()
    array_backend_deferred_request_inventories: tuple[
        ExactArrayBackendDeferredRequestInventoryIr, ...
    ] = ()
    array_lowering_completion_packages: tuple[
        ExactArrayLoweringCompletionPackageIr, ...
    ] = ()
    array_backend_handoff_requests: tuple[
        ExactArrayBackendHandoffRequestIr, ...
    ] = ()
    operation_packages: tuple[LoweringOperationPackageIr, ...] = ()
    lowering_completion_manifests: tuple[_lowering_completion_manifest.Stage8LoweringCompletionManifestIr, ...] = ()
    lowering_completion_gap_inventories: tuple[_lowering_completion_gap_inventory.Stage8LoweringCompletionGapInventoryIr, ...] = ()
    lowering_backend_translation_request_inventories: tuple[_lowering_backend_translation_request_inventory.Stage8BackendTranslationRequestInventoryIr, ...] = ()
    exact_array_backend_uninit_translation_results: tuple[ExactArrayBackendUninitTranslationResultIr, ...] = ()
    generation_stages: tuple[GenerationLoweringStage, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowered implementation candidate id must be non-empty")
        object.__setattr__(self, "statements", tuple(self.statements))
        object.__setattr__(
            self,
            "generation_branches",
            tuple(self.generation_branches),
        )
        object.__setattr__(
            self,
            "generation_type_refs",
            tuple(self.generation_type_refs),
        )
        object.__setattr__(
            self,
            "generation_values",
            tuple(self.generation_values),
        )
        object.__setattr__(
            self,
            "generation_predicates",
            tuple(self.generation_predicates),
        )
        object.__setattr__(
            self,
            "generation_branch_chains",
            tuple(self.generation_branch_chains),
        )
        object.__setattr__(
            self,
            "selected_branch_body_handoffs",
            tuple(self.selected_branch_body_handoffs),
        )
        object.__setattr__(
            self,
            "selected_branch_body_assignment_forms",
            tuple(self.selected_branch_body_assignment_forms),
        )
        object.__setattr__(
            self,
            "selected_branch_body_irs",
            tuple(self.selected_branch_body_irs),
        )
        object.__setattr__(
            self,
            "selected_body_envelopes",
            tuple(self.selected_body_envelopes),
        )
        object.__setattr__(
            self,
            "array_body_envelopes",
            tuple(self.array_body_envelopes),
        )
        object.__setattr__(
            self,
            "array_initialization_slot_forms",
            tuple(self.array_initialization_slot_forms),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_requests",
            tuple(self.array_initialization_helper_requests),
        )
        object.__setattr__(
            self,
            "array_initialization_base_type_resolutions",
            tuple(self.array_initialization_base_type_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_length_resolutions",
            tuple(self.array_initialization_vector_length_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_alignment_resolutions",
            tuple(self.array_initialization_vector_alignment_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_set_completions",
            tuple(self.array_initialization_helper_set_completions),
        )
        object.__setattr__(
            self,
            "array_initialization_declaration_shells",
            tuple(self.array_initialization_declaration_shells),
        )
        object.__setattr__(
            self,
            "array_body_structural_sequences",
            tuple(self.array_body_structural_sequences),
        )
        object.__setattr__(
            self,
            "predicate_path_structural_requests",
            tuple(self.predicate_path_structural_requests),
        )
        object.__setattr__(
            self,
            "post_branch_intrinsic_call_site_structural_requests",
            tuple(self.post_branch_intrinsic_call_site_structural_requests),
        )
        object.__setattr__(
            self,
            "return_emission_structural_requests",
            tuple(self.return_emission_structural_requests),
        )
        object.__setattr__(
            self,
            "array_body_structural_packages",
            tuple(self.array_body_structural_packages),
        )
        object.__setattr__(
            self,
            "array_backend_deferred_request_inventories",
            tuple(self.array_backend_deferred_request_inventories),
        )
        object.__setattr__(
            self,
            "array_lowering_completion_packages",
            tuple(self.array_lowering_completion_packages),
        )
        object.__setattr__(
            self,
            "array_backend_handoff_requests",
            tuple(self.array_backend_handoff_requests),
        )
        object.__setattr__(self, "operation_packages", tuple(self.operation_packages))
        object.__setattr__(self, "lowering_completion_manifests", tuple(self.lowering_completion_manifests))
        object.__setattr__(self, "lowering_completion_gap_inventories", tuple(self.lowering_completion_gap_inventories))
        object.__setattr__(self, "lowering_backend_translation_request_inventories", tuple(self.lowering_backend_translation_request_inventories))
        object.__setattr__(
            self,
            "exact_array_backend_uninit_translation_results",
            tuple(self.exact_array_backend_uninit_translation_results),
        )
        object.__setattr__(
            self,
            "generation_stages",
            tuple(self.generation_stages),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate_id,
            self.status,
            tuple(statement.key for statement in self.statements),
            tuple(branch.key for branch in self.generation_branches),
            tuple(type_ref.key for type_ref in self.generation_type_refs),
            tuple(value.key for value in self.generation_values),
            tuple(predicate.key for predicate in self.generation_predicates),
            tuple(chain.key for chain in self.generation_branch_chains),
            tuple(handoff.key for handoff in self.selected_branch_body_handoffs),
            tuple(
                form.key for form in self.selected_branch_body_assignment_forms
            ),
            tuple(body_ir.key for body_ir in self.selected_branch_body_irs),
            tuple(envelope.key for envelope in self.selected_body_envelopes),
            tuple(envelope.key for envelope in self.array_body_envelopes),
            tuple(form.key for form in self.array_initialization_slot_forms),
            tuple(
                helper_request.key
                for helper_request in self.array_initialization_helper_requests
            ),
            tuple(
                resolution.key
                for resolution in self.array_initialization_base_type_resolutions
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_length_resolutions
                )
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_alignment_resolutions
                )
            ),
            tuple(
                completion.key
                for completion in self.array_initialization_helper_set_completions
            ),
            tuple(
                shell.key
                for shell in self.array_initialization_declaration_shells
            ),
            tuple(
                sequence.key
                for sequence in self.array_body_structural_sequences
            ),
            tuple(
                request.key
                for request in self.predicate_path_structural_requests
            ),
            tuple(
                request.key
                for request in (
                    self.post_branch_intrinsic_call_site_structural_requests
                )
            ),
            tuple(
                request.key for request in self.return_emission_structural_requests
            ),
            tuple(
                package.key for package in self.array_body_structural_packages
            ),
            tuple(
                inventory.key
                for inventory in self.array_backend_deferred_request_inventories
            ),
            tuple(
                package.key for package in self.array_lowering_completion_packages
            ),
            tuple(request.key for request in self.array_backend_handoff_requests),
            tuple(package.key for package in self.operation_packages),
            tuple(manifest.key for manifest in self.lowering_completion_manifests),
            tuple(inventory.key for inventory in self.lowering_completion_gap_inventories),
            tuple(
                inventory.key
                for inventory in self.lowering_backend_translation_request_inventories
            ),
            tuple(
                result.key
                for result in self.exact_array_backend_uninit_translation_results
            ),
            tuple(stage.key for stage in self.generation_stages),
        )


@dataclass(frozen=True, slots=True)
class LoweringPlan:
    request: LoweringRequest
    input_set: LoweringInputSet
    implementations: tuple[LoweredImplementation, ...]
    implementations_by_candidate_id: FrozenMap[str, LoweredImplementation] = field(
        init=False
    )

    def __post_init__(self) -> None:
        implementations = tuple(sorted(self.implementations, key=lambda item: item.key))
        object.__setattr__(self, "implementations", implementations)
        object.__setattr__(
            self,
            "implementations_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in implementations),
        )


def prepare_lowering_inputs(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringInputSet]:
    lowering_request = request or LoweringRequest()
    diagnostics: list[Diagnostic] = []
    inputs: list[LoweringInput] = []
    for candidate in selection.candidates:
        classified = _classify_payload(candidate)
        diagnostics.extend(classified.diagnostics)
        if classified.is_ok:
            inputs.append(
                LoweringInput(
                    candidate=candidate,
                    payload=classified.unwrap(),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringInputSet(request=lowering_request, inputs=tuple(inputs)),
        diagnostics=ordered,
    )


def lower_candidates(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringPlan]:
    input_set = prepare_lowering_inputs(selection, request)
    if not input_set.is_ok:
        return Result.failure(input_set.diagnostics)

    lowering_inputs = input_set.unwrap()
    if lowering_inputs.request.strategy == "typed_opaque":
        unsupported_diagnostics = tuple(
            _unsupported_payload_diagnostic(item, strategy="typed_opaque")
            for item in lowering_inputs.inputs
        )
        ordered = sort_diagnostics(unsupported_diagnostics)
        if has_errors(ordered):
            return Result.failure(ordered)
        return Result.ok(
            LoweringPlan(
                request=lowering_inputs.request,
                input_set=lowering_inputs,
                implementations=(),
            ),
            diagnostics=ordered,
        )

    diagnostics: list[Diagnostic] = []
    skeleton_lookup_result = _build_array_body_envelope_skeleton_lookup(
        lowering_inputs.request,
    )
    diagnostics.extend(skeleton_lookup_result.diagnostics)
    if not skeleton_lookup_result.is_ok:
        ordered = sort_diagnostics(diagnostics)
        return Result.failure(ordered)
    skeleton_lookup = skeleton_lookup_result.unwrap()
    implementations: list[LoweredImplementation] = []
    for item in lowering_inputs.inputs:
        lowered = _lower_input(item, lowering_inputs.request, skeleton_lookup)
        diagnostics.extend(lowered.diagnostics)
        if lowered.is_ok:
            implementations.append(lowered.unwrap())

    if not has_errors(tuple(diagnostics)):
        diagnostics.extend(
            _unused_array_body_envelope_skeleton_diagnostics(
                skeleton_lookup,
                tuple(implementations),
            )
        )
    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringPlan(
            request=lowering_inputs.request,
            input_set=lowering_inputs,
            implementations=tuple(implementations),
        ),
        diagnostics=ordered,
    )


def resolve_generation_type_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationTypeRef]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    return _generation_queries.resolve_generation_type_query(
        query_text,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_value_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationValue]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    return _generation_queries.resolve_generation_value_query(
        query_text,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_predicate_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationPredicate]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    return _generation_queries.resolve_generation_predicate_query(
        query_text,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


_StagedGenerationPredicate = _generation_queries._StagedGenerationPredicate


def _context_for_candidate(
    item: LoweringInput,
    request: LoweringRequest,
) -> GenerationContext:
    context = request.generation_context
    parameters = context.parameters or tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    selected_type_tag = context.selected_type_tag
    if selected_type_tag is None and context.use_candidate_type_tag:
        selected_type_tag = item.candidate.type_tag
    return GenerationContext(
        values=context.values,
        primitive_attributes=context.primitive_attributes,
        use_candidate_attributes=context.use_candidate_attributes,
        selected_primitive_name=(
            context.selected_primitive_name or item.candidate.source_primitive_name
        ),
        emitted_primitive_name=(
            context.emitted_primitive_name or item.candidate.emitted_primitive_name
        ),
        selected_candidate_id=context.selected_candidate_id or item.candidate_id,
        normalized_signature=(
            context.normalized_signature
            or item.candidate.variant.source.signature.normalized
        ),
        parameters=parameters,
        selected_type_tag=selected_type_tag,
        type_tag_override=context.type_tag_override,
        use_candidate_type_tag=context.use_candidate_type_tag,
        concrete_integer_generation_rules=context.concrete_integer_generation_rules,
        scalar_size_bytes_generation_rules=(
            context.scalar_size_bytes_generation_rules
        ),
        array_initialization_vector_length_metadata=(
            context.array_initialization_vector_length_metadata
        ),
        array_initialization_vector_alignment_metadata=(
            context.array_initialization_vector_alignment_metadata
        ),
        implementation_source_location=(
            context.implementation_source_location or item.source_location
        ),
    )


def _lower_input(
    item: LoweringInput,
    request: LoweringRequest,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[LoweredImplementation]:
    if item.payload.classification != "tsil":
        return Result.failure((_unsupported_payload_diagnostic(item),))

    text = item.payload.text or ""
    type_ref = _lower_generation_type_query_payload(item, request, text)
    if type_ref is not None:
        if not type_ref.is_ok:
            return Result.failure(type_ref.diagnostics)
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_type_refs=(type_ref.unwrap(),),
            )
        )

    generation_predicate = _lower_generation_predicate_query_payload(
        item,
        request,
        text,
    )
    if generation_predicate is not None:
        if not generation_predicate.is_ok:
            return Result.failure(generation_predicate.diagnostics)
        staged_predicate = generation_predicate.unwrap()
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_predicates=(staged_predicate.predicate,),
                generation_stages=(
                    _stage_assembly._recognition_stage(
                        "generation.predicate",
                        text,
                    ),
                    *(
                        _stage_assembly._generation_value_stage(value)
                        for value in staged_predicate.generation_values
                    ),
                    _stage_assembly._generation_predicate_stage(
                        staged_predicate.predicate,
                    ),
                ),
            )
        )

    generation_value = _lower_generation_value_query_payload(item, request, text)
    if generation_value is not None:
        if not generation_value.is_ok:
            return Result.failure(generation_value.diagnostics)
        value = generation_value.unwrap()
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_values=(value,),
                generation_stages=(
                    _stage_assembly._recognition_stage(
                        "generation.value",
                        text,
                    ),
                    _stage_assembly._generation_value_stage(value),
                ),
            )
        )

    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    generation_stages: tuple[GenerationLoweringStage, ...] = ()
    if item.payload.has_generation_condition:
        if _GENERATION_CONDITION_MARKER not in text:
            return Result.failure((_generation_diagnostics._unresolved_selected_branch_diagnostic(item, text),))
        branch_chain = _generation_control_flow._prune_generation_size_byte_branch_chain(item, request, text)
        if branch_chain is not None:
            if not branch_chain.is_ok:
                return Result.failure(branch_chain.diagnostics)
            staged_chain = branch_chain.unwrap()
            control_flow_stage = _stage_assembly._generation_control_flow_stage(
                staged_chain.pruning,
            )
            selected_body_handoff = handoff_opaque_selected_branch_body(
                item.candidate_id,
                control_flow_stage,
            )
            if not selected_body_handoff.is_ok:
                return Result.failure(selected_body_handoff.diagnostics)
            handoff = selected_body_handoff.unwrap()
            assignment_form = recognize_selected_branch_body_assignment_form(handoff)
            if not assignment_form.is_ok:
                return Result.failure(assignment_form.diagnostics)
            recognized_assignment_form = assignment_form.unwrap()
            body_ir_result = lower_selected_branch_body_ir(
                recognized_assignment_form,
            )
            if not body_ir_result.is_ok:
                return Result.failure(body_ir_result.diagnostics)
            body_ir = body_ir_result.unwrap()
            envelope_result = lower_selected_body_envelope(body_ir)
            if not envelope_result.is_ok:
                return Result.failure(envelope_result.diagnostics)
            envelope = envelope_result.unwrap()
            envelope_stage = _stage_assembly._selected_body_envelope_stage(envelope)
            selected_body_operation_packages: tuple[
                LoweringOperationPackageIr,
                ...
            ] = ()
            selected_body_operation_package_stages: tuple[
                GenerationLoweringStage,
                ...
            ] = ()
            if isinstance(envelope, SelectedBodyEnvelopeIr):
                operation_package_result = lower_lowering_operation_package(
                    envelope_stage,
                )
                if not operation_package_result.is_ok:
                    return Result.failure(operation_package_result.diagnostics)
                operation_package = operation_package_result.unwrap()
                selected_body_operation_packages = (operation_package,)
                selected_body_operation_package_stages = (
                    _stage_assembly._lowering_operation_package_stage(
                        operation_package,
                    ),
                )
            array_initialization_pipeline_result = (
                _lower_exact_array_initialization_stage_pipeline(
                    item,
                    request,
                    envelope_stage,
                    skeleton_lookup,
                )
            )
            if not array_initialization_pipeline_result.is_ok:
                return Result.failure(
                    array_initialization_pipeline_result.diagnostics
                )
            array_initialization_pipeline = (
                array_initialization_pipeline_result.unwrap()
            )
            operation_packages = (
                *selected_body_operation_packages,
                *array_initialization_pipeline.operation_packages,
            )
            completion_tail = _stage_assembly._assemble_stage8_completion_tail(
                operation_packages,
                candidate_id=item.candidate_id,
                exact_array_backend_uninit_translation_rules=(
                    request.exact_array_backend_uninit_translation_rules
                ),
            )
            if not completion_tail.is_ok:
                return Result.failure(completion_tail.diagnostics)
            assembled_tail = completion_tail.unwrap()
            return Result.ok(
                LoweredImplementation(
                    candidate_id=item.candidate_id,
                    status="lowered",
                    generation_predicates=staged_chain.generation_predicates,
                    generation_branch_chains=(staged_chain.pruning,),
                    selected_branch_body_handoffs=(handoff,),
                    selected_branch_body_assignment_forms=(
                        recognized_assignment_form,
                    ),
                    selected_branch_body_irs=(body_ir,),
                    selected_body_envelopes=(envelope,),
                    array_body_envelopes=(
                        array_initialization_pipeline.array_body_envelopes
                    ),
                    array_initialization_slot_forms=(
                        array_initialization_pipeline.array_initialization_slot_forms
                    ),
                    array_initialization_helper_requests=(
                        array_initialization_pipeline.array_initialization_helper_requests
                    ),
                    array_initialization_base_type_resolutions=(
                        array_initialization_pipeline.array_initialization_base_type_resolutions
                    ),
                    array_initialization_vector_length_resolutions=(
                        array_initialization_pipeline.array_initialization_vector_length_resolutions
                    ),
                    array_initialization_vector_alignment_resolutions=(
                        array_initialization_pipeline.array_initialization_vector_alignment_resolutions
                    ),
                    array_initialization_helper_set_completions=(
                        array_initialization_pipeline.array_initialization_helper_set_completions
                    ),
                    array_initialization_declaration_shells=(
                        array_initialization_pipeline.array_initialization_declaration_shells
                    ),
                    array_body_structural_sequences=(
                        array_initialization_pipeline.array_body_structural_sequences
                    ),
                    predicate_path_structural_requests=(
                        array_initialization_pipeline.predicate_path_structural_requests
                    ),
                    post_branch_intrinsic_call_site_structural_requests=(
                        array_initialization_pipeline.post_branch_intrinsic_call_site_structural_requests
                    ),
                    return_emission_structural_requests=(
                        array_initialization_pipeline.return_emission_structural_requests
                    ),
                    array_body_structural_packages=(
                        array_initialization_pipeline.array_body_structural_packages
                    ),
                    array_backend_deferred_request_inventories=(
                        array_initialization_pipeline.array_backend_deferred_request_inventories
                    ),
                    array_lowering_completion_packages=(
                        array_initialization_pipeline.array_lowering_completion_packages
                    ),
                    array_backend_handoff_requests=(
                        array_initialization_pipeline.array_backend_handoff_requests
                    ),
                    operation_packages=operation_packages,
                    lowering_completion_manifests=(
                        assembled_tail.lowering_completion_manifests
                    ),
                    lowering_completion_gap_inventories=(
                        assembled_tail.lowering_completion_gap_inventories
                    ),
                    lowering_backend_translation_request_inventories=(
                        assembled_tail.lowering_backend_translation_request_inventories
                    ),
                    exact_array_backend_uninit_translation_results=(
                        assembled_tail.exact_array_backend_uninit_translation_results
                    ),
                    generation_stages=(
                        _stage_assembly._recognition_stage(
                            "generation.control_flow",
                            item.payload.text or text,
                        ),
                        *(
                            _stage_assembly._generation_value_stage(value)
                            for value in staged_chain.generation_values
                        ),
                        *(
                            _stage_assembly._generation_predicate_stage(predicate)
                            for predicate in staged_chain.generation_predicates
                        ),
                        control_flow_stage,
                        _stage_assembly._selected_body_stage(handoff),
                        _stage_assembly._selected_body_form_recognition_stage(
                            recognized_assignment_form,
                        ),
                        _stage_assembly._selected_body_ir_stage(body_ir),
                        envelope_stage,
                        *selected_body_operation_package_stages,
                        *array_initialization_pipeline.stages,
                        *assembled_tail.stages,
                    ),
                )
            )
        pruned = _generation_control_flow._prune_generation_branch(item, request, text)
        if not pruned.is_ok:
            return Result.failure(pruned.diagnostics)
        branch = pruned.unwrap()
        text = branch.statement_text
        generation_branches = (branch,)
        generation_stages = (
            _stage_assembly._recognition_stage(
                "generation.control_flow",
                item.payload.text or text,
            ),
            _stage_assembly._generation_control_flow_stage(branch),
        )
        if _has_generation_helper(text):
            return Result.failure((_generation_diagnostics._unresolved_selected_branch_diagnostic(item, text),))

    statement = _mini_return_statement(item, text)
    if not statement.is_ok:
        return Result.failure(statement.diagnostics)
    lowered_statement = statement.unwrap()
    operation_package_result = lower_lowering_operation_package(
        lowered_statement,
        candidate_id=item.candidate_id,
        source_location=item.source_location,
    )
    if not operation_package_result.is_ok:
        return Result.failure(operation_package_result.diagnostics)
    operation_package = operation_package_result.unwrap()
    completion_tail = _stage_assembly._assemble_stage8_completion_tail(
        (operation_package,),
        candidate_id=item.candidate_id,
        source_location=item.source_location,
        exact_array_backend_uninit_translation_rules=(
            request.exact_array_backend_uninit_translation_rules
        ),
    )
    if not completion_tail.is_ok:
        return Result.failure(completion_tail.diagnostics)
    assembled_tail = completion_tail.unwrap()

    return Result.ok(
        LoweredImplementation(
            candidate_id=item.candidate_id,
            status="lowered",
            statements=(lowered_statement,),
            generation_branches=generation_branches,
            operation_packages=(operation_package,),
            lowering_completion_manifests=(
                assembled_tail.lowering_completion_manifests
            ),
            lowering_completion_gap_inventories=(
                assembled_tail.lowering_completion_gap_inventories
            ),
            lowering_backend_translation_request_inventories=(
                assembled_tail.lowering_backend_translation_request_inventories
            ),
            exact_array_backend_uninit_translation_results=(
                assembled_tail.exact_array_backend_uninit_translation_results
            ),
            generation_stages=(
                *generation_stages,
                _stage_assembly._selected_body_stage(lowered_statement),
                _stage_assembly._lowering_operation_package_stage(
                    operation_package,
                ),
                *assembled_tail.stages,
            ),
        )
    )


def _lower_generation_type_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationTypeRef] | None:
    if _GENERATION_TYPE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_TYPE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_type_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_predicate_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[_StagedGenerationPredicate] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    if not _generation_queries._has_top_level_generation_comparison_operator(stripped):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return _generation_queries._resolve_generation_predicate_query_staged(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_value_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationValue] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_value_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )
