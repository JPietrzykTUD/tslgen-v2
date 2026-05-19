from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
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
import tslgen.lowering._exact_shapes as _exact_shapes
import tslgen.lowering._generation_control_flow as _generation_control_flow
import tslgen.lowering._generation_diagnostics as _generation_diagnostics
import tslgen.lowering._generation_queries as _generation_queries
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._array_body_validation as _array_body_validation
import tslgen.lowering._array_body_models as _array_body_models
import tslgen.lowering._stage_contracts as _stage_contracts
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    GenerationSelectedBranchBodyAssignmentRecognition,
    GenerationSelectedBranchBodyHandoff,
    GenerationSelectedBranchBodyIr,
    NoSelectedAssignmentDirectIntrinsicBodyIr,
    NoSelectedBodyEnvelopeIr,
    NoSelectedBranchBodyAssignmentFormRecognition,
    NoSelectedBranchBodyHandoff,
    OpaqueSelectedBranchBodyHandoff,
    SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeEntry,
    SelectedBodyEnvelopeIr,
    SelectedBranchBodyAssignmentFormRecognition,
)
from tslgen.lowering._generation_models import (
    GenerationExpressionRecognition,
    GenerationPredicate,
    GenerationRecognitionKind,
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
    ExactArrayBodyEnvelopeOpaqueSlot,
    ExactArrayBodyEnvelopeSelectedSlot,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSkeletonKey,
    ExactArrayBodyEnvelopeSkeletonRequirement,
    ExactArrayBodyEnvelopeSkeletonSlot,
    ExactArrayBodyEnvelopeSlot,
    ExactArrayBodyEnvelopeSlotLabel,
    ExactArrayBodyStructuralRoleLabel,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperLeafFieldName,
    ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperRequestKind,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationUnresolvedLeaf,
    ExactArrayInitializationVectorAlignmentKind,
    ExactArrayInitializationVectorAlignmentMetadata,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorAlignmentValue,
    ExactArrayInitializationVectorLengthKind,
    ExactArrayInitializationVectorLengthMetadata,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactArrayInitializationVectorLengthValue,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactPredicatePathSelectedUpdateState,
    ExactPredicatePathStructuralRequestIr,
    _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS,
    _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS,
    _ExactArrayBodyStructuralRole,
)
from tslgen.lowering._stage_contracts import (
    GenerationLoweringStage,
    GenerationLoweringStageName,
    GenerationLoweringStageOutput,
    TsilBinaryExpression,
    TsilBinaryOperator,
    TsilExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilReturnStatement,
    TsilStatement,
)
import tslgen.lowering._array_body_shapes as _array_body_shapes
import tslgen.lowering._pipeline as _lowering_pipeline


_ARRAY_BODY_MODEL_FACADE_EXPORTS = (
    _array_body_models,
    ExactArrayBodyEnvelopeSkeletonSlot,
    ExactArrayBodyStructuralRoleLabel,
    ExactArrayInitializationHelperLeafFieldName,
    ExactArrayInitializationHelperRequestKind,
    ExactArrayInitializationVectorAlignmentValue,
    ExactArrayInitializationVectorAlignmentKind,
    ExactArrayInitializationVectorLengthValue,
    ExactArrayInitializationVectorLengthKind,
)
_STAGE_CONTRACT_FACADE_EXPORTS = (
    _stage_contracts,
    GenerationLoweringStage,
    GenerationLoweringStageName,
    GenerationLoweringStageOutput,
    TsilBinaryExpression,
    TsilBinaryOperator,
    TsilExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilReturnStatement,
    TsilStatement,
)


type LoweringStrategy = Literal["mini_tsil", "typed_opaque"]
type PayloadClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]
type LoweringStatus = Literal["lowered", "unsupported"]

_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_TSIL_IDENTIFIER_RE = re.compile(rf"\A{_TSIL_IDENTIFIER}\Z")
_DIRECT_PARAMETER_ADD_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*({_TSIL_IDENTIFIER})\s*\+\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*intrin_compose\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*"
    r"\(([^()]*)\)\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_MARKER_RE = re.compile(r"\bintrin_compose\s*<")
_EMIT_RETURN_HEAD_RE = re.compile(r"\A\s*emit_return\s*\(")


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


@dataclass(frozen=True, slots=True)
class ClassifiedPayload:
    body_kind: str
    classification: PayloadClassification
    raw_payload: CatalogValue
    text: str | None = None
    has_generation_condition: bool = False

    def __post_init__(self) -> None:
        if not self.body_kind:
            raise ValueError("classified payload body kind must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.classification,
            self.body_kind,
            self.text or "",
            self.has_generation_condition,
        )


@dataclass(frozen=True, slots=True)
class LoweringInput:
    candidate: ImplementationCandidate
    payload: ClassifiedPayload

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.candidate.variant.source.declaration.source_span.location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate.candidate_id,
            self.payload.key,
        )


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


@dataclass(frozen=True, slots=True)
class _ArrayBodyEnvelopeSkeletonLookup:
    skeletons: tuple[
        tuple[ExactArrayBodyEnvelopeSkeletonKey, ExactArrayBodyEnvelopeSkeleton],
        ...
    ]
    requirements: tuple[
        tuple[
            ExactArrayBodyEnvelopeSkeletonKey,
            ExactArrayBodyEnvelopeSkeletonRequirement,
        ],
        ...
    ]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "skeletons",
            tuple(sorted(self.skeletons, key=lambda item: item[0].key)),
        )
        object.__setattr__(
            self,
            "requirements",
            tuple(sorted(self.requirements, key=lambda item: item[0].key)),
        )

    @property
    def skeleton_keys(self) -> tuple[ExactArrayBodyEnvelopeSkeletonKey, ...]:
        return tuple(key for key, _skeleton in self.skeletons)

    def skeleton_for(
        self,
        lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    ) -> ExactArrayBodyEnvelopeSkeleton | None:
        for key, skeleton in self.skeletons:
            if key == lookup_key:
                return skeleton
        return None

    def requirement_for(
        self,
        lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    ) -> ExactArrayBodyEnvelopeSkeletonRequirement | None:
        for key, requirement in self.requirements:
            if key == lookup_key:
                return requirement
        return None


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


def handoff_opaque_selected_branch_body(
    candidate_id: str,
    stage: GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyHandoff]:
    if not candidate_id:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-CANDIDATE-MISSING",
                    "opaque selected-body handoff requires a candidate id",
                ),
            )
        )
    if (
        stage.stage != "generation_control_flow_pruning"
        or not isinstance(stage.output, GenerationSizeByteBranchChainPruning)
    ):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-SOURCE-UNSUPPORTED",
                    "opaque selected-body handoff consumes only typed "
                    "GenerationSizeByteBranchChainPruning output from the "
                    "generation_control_flow_pruning stage",
                    location=_stage_output_location(stage.output),
                ),
            )
        )

    pruning = stage.output
    if pruning.condition_location is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-PROVENANCE-MISSING",
                    "opaque selected-body handoff requires branch-chain "
                    "source provenance",
                ),
            )
        )

    originating_branch_chain_id = _originating_branch_chain_id(
        candidate_id,
        pruning,
    )
    if pruning.selected_literal is None:
        return Result.ok(
            NoSelectedBranchBodyHandoff(
                candidate_id=candidate_id,
                selected_type_tag=pruning.type_tag,
                source_location=pruning.condition_location,
                originating_branch_chain_id=originating_branch_chain_id,
                attempted_literals=tuple(arm.literal for arm in pruning.arms),
            )
        )

    if not (pruning.selected_statement_text or "").strip():
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-BODY-MISSING",
                    "opaque selected-body handoff requires selected branch "
                    "body text for matched branch-chain pruning",
                    location=pruning.condition_location,
                ),
            )
        )

    selected_literal = pruning.selected_literal
    body_text = pruning.selected_statement_text
    if selected_literal is None or body_text is None:
        raise AssertionError("selected branch handoff state was checked above")
    return Result.ok(
        OpaqueSelectedBranchBodyHandoff(
            candidate_id=candidate_id,
            selected_type_tag=pruning.type_tag,
            selected_literal=selected_literal,
            opaque_body_text=body_text,
            source_location=pruning.condition_location,
            originating_branch_chain_id=originating_branch_chain_id,
        )
    )


def recognize_selected_branch_body_assignment_form(
    source: GenerationSelectedBranchBodyHandoff | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyAssignmentRecognition]:
    handoff = _selected_body_assignment_handoff_source(source)
    if not handoff.is_ok:
        return Result.failure(handoff.diagnostics)

    selected_body_handoff = handoff.unwrap()
    if isinstance(selected_body_handoff, NoSelectedBranchBodyHandoff):
        return Result.ok(
            NoSelectedBranchBodyAssignmentFormRecognition(
                candidate_id=selected_body_handoff.candidate_id,
                selected_type_tag=selected_body_handoff.selected_type_tag,
                source_location=selected_body_handoff.source_location,
                originating_branch_chain_id=(
                    selected_body_handoff.originating_branch_chain_id
                ),
                attempted_literals=selected_body_handoff.attempted_literals,
            )
        )

    recognized = _recognize_opaque_selected_branch_body_assignment_form(
        selected_body_handoff,
    )
    if not recognized.is_ok:
        return Result.failure(recognized.diagnostics)
    return Result.ok(recognized.unwrap())


def lower_selected_branch_body_ir(
    source: GenerationSelectedBranchBodyAssignmentRecognition | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyIr]:
    recognition = _selected_body_ir_recognition_source(source)
    if not recognition.is_ok:
        return Result.failure(recognition.diagnostics)

    form = recognition.unwrap()
    if isinstance(form, NoSelectedBranchBodyAssignmentFormRecognition):
        return Result.ok(
            NoSelectedAssignmentDirectIntrinsicBodyIr(
                candidate_id=form.candidate_id,
                selected_type_tag=form.selected_type_tag,
                source_location=form.source_location,
                originating_branch_chain_id=form.originating_branch_chain_id,
                attempted_literals=form.attempted_literals,
            )
        )

    return Result.ok(
        SelectedAssignmentDirectIntrinsicBodyIr(
            candidate_id=form.candidate_id,
            selected_type_tag=form.selected_type_tag,
            selected_literal=form.selected_literal,
            originating_branch_chain_id=form.originating_branch_chain_id,
            original_opaque_body_text=form.original_opaque_body_text,
            source_location=form.selected_statement_location,
            assignment_target_text=form.assignment_target_text,
            opaque_rhs_text=form.opaque_rhs_text,
            direct_intrinsic_token_text=form.direct_intrinsic_token_text,
            direct_intrinsic_argument_texts=(),
        )
    )


def lower_selected_body_envelope(
    source: GenerationSelectedBranchBodyIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBodyEnvelopeIr]:
    body_ir_result = _selected_body_envelope_source(source)
    if not body_ir_result.is_ok:
        return Result.failure(body_ir_result.diagnostics)

    body_ir = body_ir_result.unwrap()
    if isinstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr):
        diagnostic = _validate_no_selected_body_envelope_source(body_ir)
        if diagnostic is not None:
            return Result.failure((diagnostic,))
        try:
            return Result.ok(
                NoSelectedBodyEnvelopeIr(
                    source_body_ir=body_ir,
                    candidate_id=body_ir.candidate_id,
                    selected_type_tag=body_ir.selected_type_tag,
                    source_location=body_ir.source_location,
                    originating_branch_chain_id=body_ir.originating_branch_chain_id,
                    attempted_literals=body_ir.attempted_literals,
                    entries=(),
                )
            )
        except (TypeError, ValueError) as exc:
            return Result.failure(
                (
                    _inconsistent_selected_body_envelope_diagnostic(
                        str(exc),
                        body_ir.source_location,
                    ),
                )
            )

    diagnostic = _validate_selected_body_envelope_source(body_ir)
    if diagnostic is not None:
        return Result.failure((diagnostic,))
    try:
        entry = SelectedBodyEnvelopeEntry(
            source_body_ir=body_ir,
            candidate_id=body_ir.candidate_id,
            selected_type_tag=body_ir.selected_type_tag,
            selected_literal=body_ir.selected_literal,
            originating_branch_chain_id=body_ir.originating_branch_chain_id,
            original_opaque_body_text=body_ir.original_opaque_body_text,
            source_location=body_ir.source_location,
            assignment_target_text=body_ir.assignment_target_text,
            opaque_rhs_text=body_ir.opaque_rhs_text,
            direct_intrinsic_token_text=body_ir.direct_intrinsic_token_text,
            direct_intrinsic_argument_texts=body_ir.direct_intrinsic_argument_texts,
        )
        return Result.ok(
            SelectedBodyEnvelopeIr(
                candidate_id=body_ir.candidate_id,
                selected_type_tag=body_ir.selected_type_tag,
                source_location=body_ir.source_location,
                originating_branch_chain_id=body_ir.originating_branch_chain_id,
                entries=(entry,),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _inconsistent_selected_body_envelope_diagnostic(
                    str(exc),
                    body_ir.source_location,
                ),
            )
        )


def assemble_exact_array_body_envelope(
    source: GenerationSelectedBodyEnvelopeIr | GenerationLoweringStage,
    skeleton: ExactArrayBodyEnvelopeSkeleton,
) -> Result[ExactArrayBodyEnvelopeIr]:
    envelope_result = _array_body_envelope_m63_source(source)
    if not envelope_result.is_ok:
        return Result.failure(envelope_result.diagnostics)

    envelope = envelope_result.unwrap()
    skeleton_diagnostic = _validate_exact_array_body_envelope_skeleton(
        skeleton,
        envelope,
    )
    if skeleton_diagnostic is not None:
        return Result.failure((skeleton_diagnostic,))

    slots: list[ExactArrayBodyEnvelopeSlot] = []
    for skeleton_slot in skeleton.slots:
        if skeleton_slot.label == "selected_body_envelope":
            slots.append(
                ExactArrayBodyEnvelopeSelectedSlot(
                    label="selected_body_envelope",
                    ordinal=skeleton_slot.ordinal,
                    selected_body_envelope=envelope,
                    source_location=skeleton_slot.source_location,
                    candidate_id=skeleton_slot.candidate_id,
                    selected_type_tag=skeleton_slot.selected_type_tag,
                    originating_branch_chain_id=(
                        skeleton_slot.originating_branch_chain_id
                    ),
                )
            )
            continue

        opaque_source_text = skeleton_slot.opaque_source_text
        if opaque_source_text is None:
            raise AssertionError("M64 opaque slot text was validated above")
        slots.append(
            ExactArrayBodyEnvelopeOpaqueSlot(
                label=skeleton_slot.label,
                ordinal=skeleton_slot.ordinal,
                opaque_source_text=opaque_source_text,
                source_location=skeleton_slot.source_location,
                candidate_id=skeleton_slot.candidate_id,
                selected_type_tag=skeleton_slot.selected_type_tag,
                originating_branch_chain_id=(
                    skeleton_slot.originating_branch_chain_id
                ),
            )
        )

    try:
        return Result.ok(
            ExactArrayBodyEnvelopeIr(
                candidate_id=skeleton.candidate_id,
                selected_type_tag=skeleton.selected_type_tag,
                source_location=skeleton.source_location,
                originating_branch_chain_id=skeleton.originating_branch_chain_id,
                slots=tuple(slots),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
                    str(exc),
                    skeleton.source_location,
                ),
            )
        )


def lower_exact_array_initialization_slot_form(
    source: object,
) -> Result[ExactArrayInitializationSlotFormIr]:
    envelope_result = _array_initialization_slot_form_source(source)
    if not envelope_result.is_ok:
        return Result.failure(envelope_result.diagnostics)

    envelope = envelope_result.unwrap()
    selected_slot = _array_initialization_envelope_slot(envelope)
    if selected_slot is None:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_missing_diagnostic(
                    "array-initialization slot form lowering requires the M65 "
                    "opaque_pre_branch_array_initialization slot at ordinal 0",
                    envelope.source_location,
                ),
            )
        )
    if not isinstance(selected_slot, ExactArrayBodyEnvelopeOpaqueSlot):
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_wrong_position_diagnostic(
                    "array-initialization slot form lowering requires an opaque "
                    "M65 slot, but the selected slot is not opaque",
                    selected_slot.source_location,
                ),
            )
        )

    slot_diagnostic = _array_body_validation._validate_array_initialization_slot_position(
        envelope,
        selected_slot,
    )
    if slot_diagnostic is not None:
        return Result.failure((slot_diagnostic,))

    exact_match = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_SLOT_RE.match(
        selected_slot.opaque_source_text,
    )
    if exact_match is None:
        shape_match = _array_body_shapes._ARRAY_INITIALIZATION_SLOT_HELPER_SHAPE_RE.match(
            selected_slot.opaque_source_text,
        )
        if shape_match is not None:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_slot_helper_unsupported_diagnostic(
                        selected_slot,
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_malformed_diagnostic(
                    "array-initialization slot form lowering recognizes only "
                    "the exact array.tsl:105 var<typed>(array_type<...>, tmp, "
                    "value<backend>(uninit::array)) form",
                    selected_slot.source_location,
                ),
            )
        )

    try:
        return Result.ok(
            ExactArrayInitializationSlotFormIr(
                source_envelope=envelope,
                slot_label="opaque_pre_branch_array_initialization",
                slot_ordinal=selected_slot.ordinal,
                source_location=selected_slot.source_location,
                candidate_id=selected_slot.candidate_id,
                selected_type_tag=selected_slot.selected_type_tag,
                originating_branch_chain_id=(
                    selected_slot.originating_branch_chain_id
                ),
                original_slot_text=selected_slot.opaque_source_text,
                variable_token=exact_match.group("variable"),
                variable_token_location=_array_body_validation._source_span_for_match_group(
                    selected_slot.source_location,
                    exact_match,
                    "variable",
                ),
                base_type_leaf=_array_body_validation._array_initialization_leaf(
                    "type_generation_base_in",
                    selected_slot.source_location,
                    exact_match,
                    "base_type",
                ),
                vector_length_leaf=_array_body_validation._array_initialization_leaf(
                    "value_generation_vector_length",
                    selected_slot.source_location,
                    exact_match,
                    "vector_length",
                ),
                vector_alignment_leaf=_array_body_validation._array_initialization_leaf(
                    "value_generation_vector_alignment",
                    selected_slot.source_location,
                    exact_match,
                    "vector_alignment",
                ),
                backend_uninit_leaf=_array_body_validation._array_initialization_leaf(
                    "value_backend_uninit_array",
                    selected_slot.source_location,
                    exact_match,
                    "backend_uninit",
                ),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_provenance_mismatch_diagnostic(
                    str(exc),
                    selected_slot.source_location,
                ),
            )
        )


def lower_exact_array_initialization_helper_requests(
    source: object,
) -> Result[ExactArrayInitializationHelperRequestIr]:
    form_result = _array_initialization_helper_request_source(source)
    if not form_result.is_ok:
        return Result.failure(form_result.diagnostics)

    form = form_result.unwrap()
    provenance_diagnostic = _array_body_validation._validate_array_initialization_helper_form_provenance(
        form,
    )
    if provenance_diagnostic is not None:
        return Result.failure((provenance_diagnostic,))

    diagnostics: list[Diagnostic] = []
    requests: list[ExactArrayInitializationHelperRequestRecord] = []
    seen_leaf_kinds: set[ExactArrayInitializationHelperLeafKind] = set()
    for spec in _array_body_shapes._EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS:
        leaf = getattr(form, spec.field_name, None)
        if not isinstance(leaf, ExactArrayInitializationUnresolvedLeaf):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_missing_leaf_diagnostic(
                    spec,
                    form,
                )
            )
            continue
        if leaf.kind in seen_leaf_kinds:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_duplicate_leaf_diagnostic(
                    leaf,
                    form,
                )
            )
            continue
        seen_leaf_kinds.add(leaf.kind)
        if leaf.kind != spec.expected_leaf_kind:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_mismatched_leaf_diagnostic(
                    spec,
                    leaf,
                )
            )
            continue
        expected_text = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND.get(leaf.kind)
        if expected_text is None or leaf.source_text != expected_text:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_unsupported_leaf_diagnostic(
                    spec,
                    leaf,
                )
            )
            continue
        if leaf.source_location is None:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_missing_leaf_diagnostic(
                    spec,
                    form,
                )
            )
            continue
        try:
            requests.append(
                ExactArrayInitializationHelperRequestRecord(
                    source_form=form,
                    source_envelope=form.source_envelope,
                    request_ordinal=spec.request_ordinal,
                    request_kind=spec.request_kind,
                    helper_leaf_kind=leaf.kind,
                    leaf_source_text=leaf.source_text,
                    leaf_source_location=leaf.source_location,
                    candidate_id=form.candidate_id,
                    selected_type_tag=form.selected_type_tag,
                    originating_branch_chain_id=form.originating_branch_chain_id,
                    slot_label=form.slot_label,
                    slot_ordinal=form.slot_ordinal,
                    variable_token=form.variable_token,
                )
            )
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
                    str(exc),
                    leaf.source_location,
                )
            )

    if diagnostics:
        ordered = sort_diagnostics(tuple(diagnostics))
        return Result.failure(ordered)

    try:
        return Result.ok(
            ExactArrayInitializationHelperRequestIr(
                source_form=form,
                source_envelope=form.source_envelope,
                source_location=form.source_location,
                candidate_id=form.candidate_id,
                selected_type_tag=form.selected_type_tag,
                originating_branch_chain_id=form.originating_branch_chain_id,
                slot_label=form.slot_label,
                slot_ordinal=form.slot_ordinal,
                variable_token=form.variable_token,
                requests=tuple(requests),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
                    str(exc),
                    form.source_location,
                ),
            )
        )


def lower_exact_array_initialization_base_type_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
) -> Result[ExactArrayInitializationBaseTypeResolutionIr]:
    request_ir_result = _array_initialization_base_type_resolution_source(source)
    if not request_ir_result.is_ok:
        return Result.failure(request_ir_result.diagnostics)

    request_ir = request_ir_result.unwrap()
    diagnostics = _array_body_validation._validate_array_initialization_base_type_request_ir_provenance(
        request_ir,
    )
    base_request = _array_body_validation._array_initialization_base_type_request_record(
        request_ir,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if base_request is None:
        raise AssertionError("base request diagnostics must be present when missing")

    generation_context = context or GenerationContext()
    candidate_type_tag = selected_candidate_type_tag
    if candidate_type_tag is None and generation_context.use_candidate_type_tag:
        candidate_type_tag = request_ir.selected_type_tag
    semantic_label = "array-initialization base-type request"
    effective_type_tag = _generation_queries._effective_generation_type_tag(
        generation_context,
        selected_candidate_type_tag=candidate_type_tag,
        query_text=semantic_label,
        location=base_request.leaf_source_location,
    )
    if not effective_type_tag.is_ok:
        return Result.failure(effective_type_tag.diagnostics)

    resolved_type_ref = _generation_queries._base_in_type_ref(
        effective_type_tag.unwrap(),
        generation_context.concrete_integer_generation_rules,
        semantic_label,
        base_request.leaf_source_location,
    )
    if not resolved_type_ref.is_ok:
        return Result.failure(resolved_type_ref.diagnostics)
    type_ref = resolved_type_ref.unwrap()
    if type_ref.type_tag != request_ir.selected_type_tag:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "array-initialization base-type request resolved selected "
                    f"type tag {type_ref.type_tag!r}, but the M67 "
                    "helper-request IR records selected type tag "
                    f"{request_ir.selected_type_tag!r}",
                    base_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in request_ir.requests
        if request is not base_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationBaseTypeResolutionIr(
                source_request_ir=request_ir,
                source_base_type_request=base_request,
                resolved_type_ref=type_ref,
                unresolved_requests=unresolved_requests,
                source_location=request_ir.source_location,
                candidate_id=request_ir.candidate_id,
                selected_type_tag=request_ir.selected_type_tag,
                originating_branch_chain_id=request_ir.originating_branch_chain_id,
                slot_label=request_ir.slot_label,
                slot_ordinal=request_ir.slot_ordinal,
                variable_token=request_ir.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    str(exc),
                    request_ir.source_location,
                ),
            )
        )


def lower_exact_array_initialization_vector_length_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
    require_fixed_lanes: bool = False,
) -> Result[ExactArrayInitializationVectorLengthResolutionIr]:
    base_resolution_result = _array_initialization_vector_length_resolution_source(
        source,
    )
    if not base_resolution_result.is_ok:
        return Result.failure(base_resolution_result.diagnostics)

    base_resolution = base_resolution_result.unwrap()
    diagnostics = _array_body_validation._validate_array_initialization_vector_length_resolution_provenance(
        base_resolution,
    )
    vector_length_request = _array_body_validation._array_initialization_vector_length_request_record(
        base_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if vector_length_request is None:
        raise AssertionError(
            "vector-length request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or base_resolution.candidate_id
    )
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or base_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != base_resolution.candidate_id
        or effective_type_tag != base_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_context_mismatch_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires the typed selected candidate context to match "
                    "the M68 base-type resolution candidate id and selected "
                    "type tag",
                    vector_length_request.leaf_source_location,
                ),
            )
        )
    if target_extension is None or source_extension is None:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_metadata_missing_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires typed target/source extension context before "
                    "lowering evaluation",
                    vector_length_request.leaf_source_location,
                ),
            )
        )

    metadata_result = _array_body_validation._array_initialization_vector_length_metadata_for_context(
        generation_context,
        candidate_id=base_resolution.candidate_id,
        target_extension=target_extension,
        source_extension=source_extension,
        selected_type_tag=base_resolution.selected_type_tag,
        location=vector_length_request.leaf_source_location,
    )
    if not metadata_result.is_ok:
        return Result.failure(metadata_result.diagnostics)
    metadata = metadata_result.unwrap()
    if require_fixed_lanes and metadata.vector_length.kind != "fixed_lanes":
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_metadata_unsupported_diagnostic(
                    "array-initialization vector-length request resolution was "
                    "asked for fixed numeric lanes, but the supplied typed "
                    f"metadata is {metadata.vector_length.kind!r}",
                    metadata.source_location or vector_length_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in base_resolution.unresolved_requests
        if request is not vector_length_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationVectorLengthResolutionIr(
                source_base_type_resolution=base_resolution,
                source_vector_length_request=vector_length_request,
                resolved_vector_length=metadata.vector_length,
                unresolved_requests=unresolved_requests,
                source_location=base_resolution.source_location,
                candidate_id=base_resolution.candidate_id,
                target_extension=metadata.target_extension,
                source_extension=metadata.source_extension,
                selected_type_tag=base_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    base_resolution.originating_branch_chain_id
                ),
                slot_label=base_resolution.slot_label,
                slot_ordinal=base_resolution.slot_ordinal,
                variable_token=base_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                    str(exc),
                    base_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_vector_alignment_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationVectorAlignmentResolutionIr]:
    vector_length_result = _array_initialization_vector_alignment_resolution_source(
        source,
    )
    if not vector_length_result.is_ok:
        return Result.failure(vector_length_result.diagnostics)

    vector_length_resolution = vector_length_result.unwrap()
    diagnostics = _array_body_validation._validate_array_initialization_vector_alignment_resolution_provenance(
        vector_length_resolution,
    )
    vector_alignment_request = _array_body_validation._array_initialization_vector_alignment_request_record(
        vector_length_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if vector_alignment_request is None:
        raise AssertionError(
            "vector-alignment request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or vector_length_resolution.candidate_id
    )
    effective_target_extension = target_extension or vector_length_resolution.target_extension
    effective_source_extension = source_extension or vector_length_resolution.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or vector_length_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != vector_length_resolution.candidate_id
        or effective_target_extension != vector_length_resolution.target_extension
        or effective_source_extension != vector_length_resolution.source_extension
        or effective_type_tag != vector_length_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_context_mismatch_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires the typed selected candidate context to match "
                    "the M70 vector-length resolution candidate id, target "
                    "extension, source extension, and selected type tag",
                    vector_alignment_request.leaf_source_location,
                ),
            )
        )

    metadata_result = _array_body_validation._array_initialization_vector_alignment_metadata_for_context(
        generation_context,
        candidate_id=vector_length_resolution.candidate_id,
        target_extension=vector_length_resolution.target_extension,
        source_extension=vector_length_resolution.source_extension,
        selected_type_tag=vector_length_resolution.selected_type_tag,
        location=vector_alignment_request.leaf_source_location,
    )
    if not metadata_result.is_ok:
        return Result.failure(metadata_result.diagnostics)
    metadata = metadata_result.unwrap()
    if metadata.vector_alignment.kind == "unsupported":
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_metadata_unsupported_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "received explicit unsupported vector-alignment metadata "
                    f"policy {metadata.vector_alignment.unsupported_policy!r}",
                    metadata.source_location
                    or vector_alignment_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in vector_length_resolution.unresolved_requests
        if request is not vector_alignment_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationVectorAlignmentResolutionIr(
                source_vector_length_resolution=vector_length_resolution,
                source_vector_alignment_request=vector_alignment_request,
                resolved_vector_alignment=metadata.vector_alignment,
                unresolved_requests=unresolved_requests,
                source_location=vector_length_resolution.source_location,
                candidate_id=vector_length_resolution.candidate_id,
                target_extension=vector_length_resolution.target_extension,
                source_extension=vector_length_resolution.source_extension,
                selected_type_tag=vector_length_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    vector_length_resolution.originating_branch_chain_id
                ),
                slot_label=vector_length_resolution.slot_label,
                slot_ordinal=vector_length_resolution.slot_ordinal,
                variable_token=vector_length_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    str(exc),
                    vector_length_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_helper_set_completion(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationHelperSetCompletionIr]:
    vector_alignment_result = _array_initialization_helper_set_completion_source(
        source,
    )
    if not vector_alignment_result.is_ok:
        return Result.failure(vector_alignment_result.diagnostics)

    vector_alignment_resolution = vector_alignment_result.unwrap()
    diagnostics = _array_body_validation._validate_array_initialization_helper_set_completion_provenance(
        vector_alignment_resolution,
    )
    backend_uninit_request = _array_body_validation._array_initialization_backend_uninit_request_record(
        vector_alignment_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if backend_uninit_request is None:
        raise AssertionError(
            "backend-uninit request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or vector_alignment_resolution.candidate_id
    )
    effective_target_extension = (
        target_extension or vector_alignment_resolution.target_extension
    )
    effective_source_extension = (
        source_extension or vector_alignment_resolution.source_extension
    )
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or vector_alignment_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != vector_alignment_resolution.candidate_id
        or effective_target_extension != vector_alignment_resolution.target_extension
        or effective_source_extension != vector_alignment_resolution.source_extension
        or effective_type_tag != vector_alignment_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_set_context_mismatch_diagnostic(
                    "array-initialization helper-set completion requires the "
                    "typed selected candidate context to match the M71 "
                    "vector-alignment resolution candidate id, target "
                    "extension, source extension, and selected type tag",
                    backend_uninit_request.leaf_source_location,
                ),
            )
        )

    try:
        deferred_backend_uninit = ExactArrayInitializationDeferredBackendUninitValue(
            source_backend_uninit_request=backend_uninit_request,
            policy="deferred_backend_value",
            source_location=backend_uninit_request.leaf_source_location,
            candidate_id=vector_alignment_resolution.candidate_id,
            target_extension=vector_alignment_resolution.target_extension,
            source_extension=vector_alignment_resolution.source_extension,
            selected_type_tag=vector_alignment_resolution.selected_type_tag,
            originating_branch_chain_id=(
                vector_alignment_resolution.originating_branch_chain_id
            ),
            slot_label=vector_alignment_resolution.slot_label,
            slot_ordinal=vector_alignment_resolution.slot_ordinal,
            variable_token=vector_alignment_resolution.variable_token,
        )
        return Result.ok(
            ExactArrayInitializationHelperSetCompletionIr(
                source_vector_alignment_resolution=vector_alignment_resolution,
                source_vector_length_resolution=(
                    vector_alignment_resolution.source_vector_length_resolution
                ),
                source_base_type_resolution=(
                    vector_alignment_resolution.source_vector_length_resolution
                    .source_base_type_resolution
                ),
                source_backend_uninit_request=backend_uninit_request,
                unresolved_backend_uninit=deferred_backend_uninit,
                source_location=vector_alignment_resolution.source_location,
                candidate_id=vector_alignment_resolution.candidate_id,
                target_extension=vector_alignment_resolution.target_extension,
                source_extension=vector_alignment_resolution.source_extension,
                selected_type_tag=vector_alignment_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    vector_alignment_resolution.originating_branch_chain_id
                ),
                slot_label=vector_alignment_resolution.slot_label,
                slot_ordinal=vector_alignment_resolution.slot_ordinal,
                variable_token=vector_alignment_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                    str(exc),
                    vector_alignment_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_declaration_shell(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationDeclarationShellIr]:
    completion_result = _array_initialization_declaration_shell_source(source)
    if not completion_result.is_ok:
        return Result.failure(completion_result.diagnostics)

    completion = completion_result.unwrap()
    diagnostics = _array_body_validation._validate_array_initialization_declaration_shell(completion)
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or completion.candidate_id
    )
    effective_target_extension = target_extension or completion.target_extension
    effective_source_extension = source_extension or completion.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or completion.selected_type_tag
    )
    if (
        effective_candidate_id != completion.candidate_id
        or effective_target_extension != completion.target_extension
        or effective_source_extension != completion.source_extension
        or effective_type_tag != completion.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_declaration_shell_context_mismatch_diagnostic(
                    "array-initialization declaration-shell lowering requires "
                    "the typed selected candidate context to match the M72 "
                    "helper-set completion candidate id, target extension, "
                    "source extension, and selected type tag",
                    completion.source_location,
                ),
            )
        )

    source_slot_form = completion.source_base_type_resolution.source_request_ir.source_form
    source_envelope = source_slot_form.source_envelope
    try:
        return Result.ok(
            ExactArrayInitializationDeclarationShellIr(
                source_helper_set_completion=completion,
                source_slot_form=source_slot_form,
                source_envelope=source_envelope,
                declaration_kind="var<typed>",
                array_type_kind="array_type",
                base_type_ref=completion.source_base_type_resolution.resolved_type_ref,
                vector_length=(
                    completion.source_vector_length_resolution.resolved_vector_length
                ),
                vector_alignment=(
                    completion.source_vector_alignment_resolution
                    .resolved_vector_alignment
                ),
                unresolved_backend_uninit=completion.unresolved_backend_uninit,
                source_location=completion.source_location,
                candidate_id=completion.candidate_id,
                target_extension=completion.target_extension,
                source_extension=completion.source_extension,
                selected_type_tag=completion.selected_type_tag,
                originating_branch_chain_id=completion.originating_branch_chain_id,
                slot_label=completion.slot_label,
                slot_ordinal=completion.slot_ordinal,
                variable_token=completion.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    str(exc),
                    completion.source_location,
                ),
            )
        )


def lower_exact_array_body_structural_sequence(
    source: object,
    declaration_shell: object | None = None,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayBodyStructuralSequenceIr]:
    source_result = _array_body_structural_sequence_source(source, declaration_shell)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    envelope, shell = source_result.unwrap()

    diagnostics = _array_body_validation._validate_array_body_structural_sequence_inputs(envelope, shell)
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or shell.candidate_id
    )
    effective_target_extension = target_extension or shell.target_extension
    effective_source_extension = source_extension or shell.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or shell.selected_type_tag
    )
    if (
        effective_candidate_id != shell.candidate_id
        or effective_target_extension != shell.target_extension
        or effective_source_extension != shell.source_extension
        or effective_type_tag != shell.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._array_body_structural_sequence_context_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the typed selected candidate context to match the M73 "
                    "declaration shell candidate id, target extension, source "
                    "extension, and selected type tag",
                    shell.source_location,
                ),
            )
        )

    roles: list[_ExactArrayBodyStructuralRole] = []
    for role_label, slot in zip(
        _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS,
        envelope.slots,
        strict=True,
    ):
        try:
            roles.append(
                _array_body_validation._structural_role_from_slot(
                    role_label,
                    slot,
                    shell,
                    target_extension=shell.target_extension,
                    source_extension=shell.source_extension,
                )
            )
        except (TypeError, ValueError) as exc:
            return Result.failure(
                (
                    _array_body_diagnostics._array_body_structural_sequence_malformed_diagnostic(
                        str(exc),
                        slot.source_location,
                    ),
                )
            )

    try:
        return Result.ok(
            ExactArrayBodyStructuralSequenceIr(
                source_envelope=envelope,
                declaration_shell=shell,
                roles=tuple(roles),
                source_location=envelope.source_location,
                candidate_id=envelope.candidate_id,
                target_extension=shell.target_extension,
                source_extension=shell.source_extension,
                selected_type_tag=envelope.selected_type_tag,
                originating_branch_chain_id=envelope.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._array_body_structural_sequence_malformed_diagnostic(
                    str(exc),
                    envelope.source_location,
                ),
            )
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


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationStagePipelineResult:
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
    pipeline_snapshot: _lowering_pipeline.ExactArrayBodyPipelineSnapshot = field(
        default_factory=_lowering_pipeline.ExactArrayBodyPipelineSnapshot.empty,
    )
    stages: tuple[GenerationLoweringStage, ...] = ()

    def __post_init__(self) -> None:
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
        object.__setattr__(self, "pipeline_snapshot", self.pipeline_snapshot)
        object.__setattr__(self, "stages", tuple(self.stages))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            tuple(envelope.key for envelope in self.array_body_envelopes),
            tuple(form.key for form in self.array_initialization_slot_forms),
            tuple(
                request.key
                for request in self.array_initialization_helper_requests
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
            self.pipeline_snapshot.key,
            tuple(stage.key for stage in self.stages),
        )


def _recognition_stage(
    kind: GenerationRecognitionKind,
    source_text: str,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="helper_expression_recognition",
        output=GenerationExpressionRecognition(
            kind=kind,
            source_text=source_text.strip(),
        ),
    )


def _generation_value_stage(value: GenerationValue) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="typed_generation_value", output=value)


def _generation_predicate_stage(
    predicate: GenerationPredicate,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="typed_generation_predicate",
        output=predicate,
    )


def _generation_control_flow_stage(
    branch: PrunedGenerationBranch | GenerationSizeByteBranchChainPruning,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="generation_control_flow_pruning",
        output=branch,
    )


def _selected_body_stage(
    output: TsilStatement | GenerationSelectedBranchBodyHandoff,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="selected_body_lowering", output=output)


def _selected_body_form_recognition_stage(
    output: GenerationSelectedBranchBodyAssignmentRecognition,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_form_recognition",
        output=output,
    )


def _selected_body_ir_stage(
    output: GenerationSelectedBranchBodyIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_ir_lowering",
        output=output,
    )


def _selected_body_envelope_stage(
    output: GenerationSelectedBodyEnvelopeIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_envelope_lowering",
        output=output,
    )


def _array_body_envelope_slot_assembly_stage(
    output: ExactArrayBodyEnvelopeIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_body_envelope_slot_assembly",
        output=output,
    )


def _array_initialization_slot_form_stage(
    output: ExactArrayInitializationSlotFormIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_slot_form_lowering",
        output=output,
    )


def _array_initialization_helper_request_stage(
    output: ExactArrayInitializationHelperRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_helper_request_lowering",
        output=output,
    )


def _array_initialization_base_type_resolution_stage(
    output: ExactArrayInitializationBaseTypeResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_base_type_request_resolution",
        output=output,
    )


def _array_initialization_vector_length_resolution_stage(
    output: ExactArrayInitializationVectorLengthResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_vector_length_request_resolution",
        output=output,
    )


def _array_initialization_vector_alignment_resolution_stage(
    output: ExactArrayInitializationVectorAlignmentResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_vector_alignment_request_resolution",
        output=output,
    )


def _array_initialization_helper_set_completion_stage(
    output: ExactArrayInitializationHelperSetCompletionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_helper_set_completion",
        output=output,
    )


def _array_initialization_declaration_shell_stage(
    output: ExactArrayInitializationDeclarationShellIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_declaration_shell_lowering",
        output=output,
    )


def _array_body_structural_sequence_stage(
    output: ExactArrayBodyStructuralSequenceIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_body_structural_sequence_classification",
        output=output,
    )


def _predicate_path_structural_request_stage(
    output: ExactPredicatePathStructuralRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="predicate_path_structural_request_lowering",
        output=output,
    )


def _post_branch_intrinsic_call_site_structural_request_stage(
    output: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="post_branch_intrinsic_call_site_structural_request_lowering",
        output=output,
    )


def _stage_output_location(
    output: GenerationLoweringStageOutput,
) -> SourceLocation | None:
    if isinstance(
        output,
        (
            PrunedGenerationBranch,
            GenerationSizeByteBranchChainPruning,
        ),
    ):
        return output.condition_location
    if isinstance(output, SelectedBranchBodyAssignmentFormRecognition):
        return output.selected_statement_location
    if isinstance(
        output,
        (
            OpaqueSelectedBranchBodyHandoff,
            NoSelectedBranchBodyHandoff,
            NoSelectedBranchBodyAssignmentFormRecognition,
            SelectedAssignmentDirectIntrinsicBodyIr,
            NoSelectedAssignmentDirectIntrinsicBodyIr,
            SelectedBodyEnvelopeIr,
            NoSelectedBodyEnvelopeIr,
            ExactArrayBodyEnvelopeIr,
            ExactArrayInitializationSlotFormIr,
            ExactArrayInitializationHelperRequestIr,
            ExactArrayInitializationBaseTypeResolutionIr,
            ExactArrayInitializationVectorLengthResolutionIr,
            ExactArrayInitializationVectorAlignmentResolutionIr,
            ExactArrayInitializationHelperSetCompletionIr,
            ExactArrayInitializationDeclarationShellIr,
            ExactArrayBodyStructuralSequenceIr,
            ExactPredicatePathStructuralRequestIr,
            ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
        ),
    ):
        return output.source_location
    return None


def _originating_branch_chain_id(
    candidate_id: str,
    pruning: GenerationSizeByteBranchChainPruning,
) -> str:
    location_key = (
        pruning.condition_location.sort_key()
        if pruning.condition_location is not None
        else ("", 0, 0, 0, 0)
    )
    literal_key = ",".join(str(arm.literal) for arm in pruning.arms)
    return (
        f"{candidate_id}:generation-size-byte-branch-chain:"
        f"{pruning.type_tag}:{literal_key}:{location_key}"
    )


def _array_body_envelope_skeleton_lookup_key(
    skeleton: ExactArrayBodyEnvelopeSkeleton,
) -> ExactArrayBodyEnvelopeSkeletonKey:
    return ExactArrayBodyEnvelopeSkeletonKey(
        candidate_id=skeleton.candidate_id,
        selected_type_tag=skeleton.selected_type_tag,
        originating_branch_chain_id=skeleton.originating_branch_chain_id,
    )


def _array_body_envelope_m63_lookup_key(
    envelope: GenerationSelectedBodyEnvelopeIr,
) -> ExactArrayBodyEnvelopeSkeletonKey:
    return ExactArrayBodyEnvelopeSkeletonKey(
        candidate_id=envelope.candidate_id,
        selected_type_tag=envelope.selected_type_tag,
        originating_branch_chain_id=envelope.originating_branch_chain_id,
    )


def _build_array_body_envelope_skeleton_lookup(
    request: LoweringRequest,
) -> Result[_ArrayBodyEnvelopeSkeletonLookup]:
    diagnostics: list[Diagnostic] = []
    skeletons_by_key: dict[
        ExactArrayBodyEnvelopeSkeletonKey,
        ExactArrayBodyEnvelopeSkeleton,
    ] = {}
    for skeleton in request.array_body_envelope_skeletons:
        lookup_key = _array_body_envelope_skeleton_lookup_key(skeleton)
        existing = skeletons_by_key.get(lookup_key)
        if existing is None:
            skeletons_by_key[lookup_key] = skeleton
            continue
        diagnostics.append(
            _array_body_diagnostics._duplicate_array_body_envelope_skeleton_diagnostic(
                lookup_key,
                skeleton,
                conflicting=existing != skeleton,
            )
        )

    requirements_by_key: dict[
        ExactArrayBodyEnvelopeSkeletonKey,
        ExactArrayBodyEnvelopeSkeletonRequirement,
    ] = {}
    for requirement in request.required_array_body_envelope_skeletons:
        requirements_by_key.setdefault(requirement.lookup_key, requirement)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        _ArrayBodyEnvelopeSkeletonLookup(
            skeletons=tuple(
                sorted(
                    skeletons_by_key.items(),
                    key=lambda item: item[0].key,
                )
            ),
            requirements=tuple(
                sorted(
                    requirements_by_key.items(),
                    key=lambda item: item[0].key,
                )
            ),
        ),
        diagnostics=ordered,
    )


def _assemble_matching_array_body_envelope(
    envelope_stage: GenerationLoweringStage,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[ExactArrayBodyEnvelopeIr | None]:
    if not isinstance(
        envelope_stage.output,
        (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
    ):
        raise TypeError("array-body envelope integration requires an M63 stage")

    lookup_key = _array_body_envelope_m63_lookup_key(envelope_stage.output)
    skeleton = skeleton_lookup.skeleton_for(lookup_key)
    if skeleton is None:
        requirement = skeleton_lookup.requirement_for(lookup_key)
        if requirement is None:
            return Result.ok(None)
        return Result.failure(
            (
                _array_body_diagnostics._missing_array_body_envelope_skeleton_diagnostic(
                    requirement,
                    envelope_stage.output,
                ),
            )
        )

    assembled = assemble_exact_array_body_envelope(envelope_stage, skeleton)
    if not assembled.is_ok:
        return Result.failure(assembled.diagnostics)
    return Result.ok(assembled.unwrap())


def _lower_exact_array_initialization_stage_pipeline(
    item: LoweringInput,
    request: LoweringRequest,
    envelope_stage: GenerationLoweringStage,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[_ExactArrayInitializationStagePipelineResult]:
    array_envelope_result = _assemble_matching_array_body_envelope(
        envelope_stage,
        skeleton_lookup,
    )
    if not array_envelope_result.is_ok:
        return Result.failure(array_envelope_result.diagnostics)
    array_envelope = array_envelope_result.unwrap()
    if array_envelope is None:
        return Result.ok(_ExactArrayInitializationStagePipelineResult())

    array_body_stage = _array_body_envelope_slot_assembly_stage(array_envelope)
    array_initialization_slot_form_result = (
        lower_exact_array_initialization_slot_form(array_envelope)
    )
    if not array_initialization_slot_form_result.is_ok:
        return Result.failure(array_initialization_slot_form_result.diagnostics)
    array_initialization_slot_form = array_initialization_slot_form_result.unwrap()
    array_initialization_slot_form_stage = _array_initialization_slot_form_stage(
        array_initialization_slot_form,
    )

    array_initialization_helper_request_result = (
        lower_exact_array_initialization_helper_requests(
            array_initialization_slot_form,
        )
    )
    if not array_initialization_helper_request_result.is_ok:
        return Result.failure(array_initialization_helper_request_result.diagnostics)
    array_initialization_helper_request = (
        array_initialization_helper_request_result.unwrap()
    )
    array_initialization_helper_request_stage = (
        _array_initialization_helper_request_stage(
            array_initialization_helper_request,
        )
    )

    base_type_resolution_result = lower_exact_array_initialization_base_type_request(
        array_initialization_helper_request,
        _context_for_candidate(item, request),
        selected_candidate_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not base_type_resolution_result.is_ok:
        return Result.failure(base_type_resolution_result.diagnostics)
    base_type_resolution = base_type_resolution_result.unwrap()
    base_type_resolution_stage = _array_initialization_base_type_resolution_stage(
        base_type_resolution,
    )
    vector_length_resolution_result = (
        lower_exact_array_initialization_vector_length_request(
            base_type_resolution,
            _context_for_candidate(item, request),
            selected_candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=(
                item.candidate.type_tag
                if request.generation_context.use_candidate_type_tag
                else None
            ),
        )
    )
    if not vector_length_resolution_result.is_ok:
        return Result.failure(vector_length_resolution_result.diagnostics)
    vector_length_resolution = vector_length_resolution_result.unwrap()
    vector_length_resolution_stage = (
        _array_initialization_vector_length_resolution_stage(
            vector_length_resolution,
        )
    )
    vector_alignment_resolution_result = (
        lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            _context_for_candidate(item, request),
            selected_candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=(
                item.candidate.type_tag
                if request.generation_context.use_candidate_type_tag
                else None
            ),
        )
    )
    if not vector_alignment_resolution_result.is_ok:
        return Result.failure(vector_alignment_resolution_result.diagnostics)
    vector_alignment_resolution = vector_alignment_resolution_result.unwrap()
    vector_alignment_resolution_stage = (
        _array_initialization_vector_alignment_resolution_stage(
            vector_alignment_resolution,
        )
    )
    helper_set_completion_result = lower_exact_array_initialization_helper_set_completion(
        vector_alignment_resolution,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not helper_set_completion_result.is_ok:
        return Result.failure(helper_set_completion_result.diagnostics)
    helper_set_completion = helper_set_completion_result.unwrap()
    helper_set_completion_stage = _array_initialization_helper_set_completion_stage(
        helper_set_completion,
    )
    declaration_shell_result = lower_exact_array_initialization_declaration_shell(
        helper_set_completion,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not declaration_shell_result.is_ok:
        return Result.failure(declaration_shell_result.diagnostics)
    declaration_shell = declaration_shell_result.unwrap()
    declaration_shell_stage = _array_initialization_declaration_shell_stage(
        declaration_shell,
    )
    structural_sequence_result = lower_exact_array_body_structural_sequence(
        array_envelope,
        declaration_shell,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not structural_sequence_result.is_ok:
        return Result.failure(structural_sequence_result.diagnostics)
    structural_sequence = structural_sequence_result.unwrap()
    structural_sequence_stage = _array_body_structural_sequence_stage(
        structural_sequence,
    )
    predicate_path_result = lower_exact_predicate_path_structural_request(
        structural_sequence_stage,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not predicate_path_result.is_ok:
        return Result.failure(predicate_path_result.diagnostics)
    predicate_path = predicate_path_result.unwrap()
    predicate_path_stage = _predicate_path_structural_request_stage(predicate_path)
    post_branch_call_site_result = (
        lower_exact_post_branch_intrinsic_call_site_structural_request(
            predicate_path_stage,
            _context_for_candidate(item, request),
            selected_candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=(
                item.candidate.type_tag
                if request.generation_context.use_candidate_type_tag
                else None
            ),
        )
    )
    if not post_branch_call_site_result.is_ok:
        return Result.failure(post_branch_call_site_result.diagnostics)
    post_branch_call_site = post_branch_call_site_result.unwrap()
    post_branch_call_site_stage = (
        _post_branch_intrinsic_call_site_structural_request_stage(
            post_branch_call_site,
        )
    )
    pipeline_stages = (
        array_body_stage,
        array_initialization_slot_form_stage,
        array_initialization_helper_request_stage,
        base_type_resolution_stage,
        vector_length_resolution_stage,
        vector_alignment_resolution_stage,
        helper_set_completion_stage,
        declaration_shell_stage,
        structural_sequence_stage,
        predicate_path_stage,
        post_branch_call_site_stage,
    )
    pipeline_snapshot = _lowering_pipeline.ExactArrayBodyPipelineSnapshot(
        steps=(
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_body_envelope_slot_assembly",
                stage=array_body_stage,
                artifact_kind="array_body_envelope",
                artifact_key=array_envelope.key,
                artifact_value=array_envelope,
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_slot_form_lowering",
                stage=array_initialization_slot_form_stage,
                artifact_kind="array_initialization_slot_form",
                artifact_key=array_initialization_slot_form.key,
                artifact_value=array_initialization_slot_form,
                depends_on=("array_body_envelope",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_helper_request_lowering",
                stage=array_initialization_helper_request_stage,
                artifact_kind="array_initialization_helper_request",
                artifact_key=array_initialization_helper_request.key,
                artifact_value=array_initialization_helper_request,
                depends_on=("array_initialization_slot_form",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_base_type_request_resolution",
                stage=base_type_resolution_stage,
                artifact_kind="array_initialization_base_type_resolution",
                artifact_key=base_type_resolution.key,
                artifact_value=base_type_resolution,
                depends_on=("array_initialization_helper_request",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_vector_length_request_resolution",
                stage=vector_length_resolution_stage,
                artifact_kind="array_initialization_vector_length_resolution",
                artifact_key=vector_length_resolution.key,
                artifact_value=vector_length_resolution,
                depends_on=("array_initialization_base_type_resolution",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_vector_alignment_request_resolution",
                stage=vector_alignment_resolution_stage,
                artifact_kind="array_initialization_vector_alignment_resolution",
                artifact_key=vector_alignment_resolution.key,
                artifact_value=vector_alignment_resolution,
                depends_on=("array_initialization_vector_length_resolution",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_helper_set_completion",
                stage=helper_set_completion_stage,
                artifact_kind="array_initialization_helper_set_completion",
                artifact_key=helper_set_completion.key,
                artifact_value=helper_set_completion,
                depends_on=("array_initialization_vector_alignment_resolution",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_initialization_declaration_shell_lowering",
                stage=declaration_shell_stage,
                artifact_kind="array_initialization_declaration_shell",
                artifact_key=declaration_shell.key,
                artifact_value=declaration_shell,
                depends_on=("array_initialization_helper_set_completion",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_body_structural_sequence_classification",
                stage=structural_sequence_stage,
                artifact_kind="array_body_structural_sequence",
                artifact_key=structural_sequence.key,
                artifact_value=structural_sequence,
                depends_on=(
                    "array_body_envelope",
                    "array_initialization_declaration_shell",
                ),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="predicate_path_structural_request_lowering",
                stage=predicate_path_stage,
                artifact_kind="predicate_path_structural_request",
                artifact_key=predicate_path.key,
                artifact_value=predicate_path,
                depends_on=("array_body_structural_sequence",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name=(
                    "post_branch_intrinsic_call_site_structural_request_lowering"
                ),
                stage=post_branch_call_site_stage,
                artifact_kind=(
                    "post_branch_intrinsic_call_site_structural_request"
                ),
                artifact_key=post_branch_call_site.key,
                artifact_value=post_branch_call_site,
                depends_on=("predicate_path_structural_request",),
            ),
        ),
    )

    return Result.ok(
        _ExactArrayInitializationStagePipelineResult(
            array_body_envelopes=(array_envelope,),
            array_initialization_slot_forms=(array_initialization_slot_form,),
            array_initialization_helper_requests=(
                array_initialization_helper_request,
            ),
            array_initialization_base_type_resolutions=(base_type_resolution,),
            array_initialization_vector_length_resolutions=(
                vector_length_resolution,
            ),
            array_initialization_vector_alignment_resolutions=(
                vector_alignment_resolution,
            ),
            array_initialization_helper_set_completions=(
                helper_set_completion,
            ),
            array_initialization_declaration_shells=(
                declaration_shell,
            ),
            array_body_structural_sequences=(
                structural_sequence,
            ),
            predicate_path_structural_requests=(
                predicate_path,
            ),
            post_branch_intrinsic_call_site_structural_requests=(
                post_branch_call_site,
            ),
            pipeline_snapshot=pipeline_snapshot,
            stages=pipeline_stages,
        )
    )


def _unused_array_body_envelope_skeleton_diagnostics(
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
    implementations: tuple[LoweredImplementation, ...],
) -> tuple[Diagnostic, ...]:
    if not skeleton_lookup.skeleton_keys:
        return ()

    envelope_keys = tuple(
        _array_body_envelope_m63_lookup_key(envelope)
        for implementation in implementations
        for envelope in implementation.selected_body_envelopes
    )
    used_keys = {
        ExactArrayBodyEnvelopeSkeletonKey(
            candidate_id=envelope.candidate_id,
            selected_type_tag=envelope.selected_type_tag,
            originating_branch_chain_id=envelope.originating_branch_chain_id,
        )
        for implementation in implementations
        for envelope in implementation.array_body_envelopes
    }
    diagnostics: list[Diagnostic] = []
    for skeleton_key in skeleton_lookup.skeleton_keys:
        if skeleton_key in used_keys:
            continue
        skeleton = skeleton_lookup.skeleton_for(skeleton_key)
        if skeleton is None:
            raise AssertionError("array-body skeleton lookup key disappeared")
        if any(
            envelope_key.candidate_id == skeleton_key.candidate_id
            for envelope_key in envelope_keys
        ):
            diagnostics.append(
                _array_body_diagnostics._mismatched_array_body_envelope_skeleton_diagnostic(
                    skeleton_key,
                    skeleton,
                    envelope_keys,
                )
            )
            continue
        diagnostics.append(
            _array_body_diagnostics._orphan_array_body_envelope_skeleton_diagnostic(skeleton_key, skeleton)
        )
    return tuple(diagnostics)


def _selected_body_assignment_handoff_source(
    source: GenerationSelectedBranchBodyHandoff | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyHandoff]:
    if isinstance(source, (OpaqueSelectedBranchBodyHandoff, NoSelectedBranchBodyHandoff)):
        return Result.ok(source)
    if (
        source.stage == "selected_body_lowering"
        and isinstance(
            source.output,
            (OpaqueSelectedBranchBodyHandoff, NoSelectedBranchBodyHandoff),
        )
    ):
        return Result.ok(source.output)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-FORM-SOURCE-UNSUPPORTED",
                "selected-body assignment-form recognition consumes only typed "
                "OpaqueSelectedBranchBodyHandoff or NoSelectedBranchBodyHandoff "
                "values, or the selected_body_lowering stage output containing "
                "one of those values",
                location=_stage_output_location(source.output),
            ),
        )
    )


def _selected_body_ir_recognition_source(
    source: GenerationSelectedBranchBodyAssignmentRecognition | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyAssignmentRecognition]:
    if isinstance(
        source,
        (
            SelectedBranchBodyAssignmentFormRecognition,
            NoSelectedBranchBodyAssignmentFormRecognition,
        ),
    ):
        return Result.ok(source)
    if (
        source.stage == "selected_body_form_recognition"
        and isinstance(
            source.output,
            (
                SelectedBranchBodyAssignmentFormRecognition,
                NoSelectedBranchBodyAssignmentFormRecognition,
            ),
        )
    ):
        return Result.ok(source.output)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-IR-SOURCE-UNSUPPORTED",
                "selected-body IR lowering consumes only typed "
                "SelectedBranchBodyAssignmentFormRecognition or "
                "NoSelectedBranchBodyAssignmentFormRecognition values, or the "
                "selected_body_form_recognition stage output containing one "
                "of those values",
                location=_stage_output_location(source.output),
            ),
        )
    )


def _selected_body_envelope_source(
    source: GenerationSelectedBranchBodyIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyIr]:
    if isinstance(
        source,
        (
            SelectedAssignmentDirectIntrinsicBodyIr,
            NoSelectedAssignmentDirectIntrinsicBodyIr,
        ),
    ):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "selected_body_ir_lowering"
            and isinstance(
                source.output,
                (
                    SelectedAssignmentDirectIntrinsicBodyIr,
                    NoSelectedAssignmentDirectIntrinsicBodyIr,
                ),
            )
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
    else:
        location = None
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
                "selected-body envelope lowering consumes only typed "
                "SelectedAssignmentDirectIntrinsicBodyIr or "
                "NoSelectedAssignmentDirectIntrinsicBodyIr values, or the "
                "selected_body_ir_lowering stage output containing one of "
                "those M62 values",
                location=location,
            ),
        )
    )


def _array_body_envelope_m63_source(
    source: GenerationSelectedBodyEnvelopeIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBodyEnvelopeIr]:
    if isinstance(source, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr)):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "selected_body_envelope_lowering"
            and isinstance(source.output, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr))
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
    else:
        location = None
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
                "array-body envelope slot assembly consumes only typed M63 "
                "SelectedBodyEnvelopeIr or NoSelectedBodyEnvelopeIr values, "
                "or the selected_body_envelope_lowering stage output "
                "containing one of those M63 values",
                location=location,
            ),
        )
    )


def _array_initialization_slot_form_source(
    source: object,
) -> Result[ExactArrayBodyEnvelopeIr]:
    if isinstance(source, ExactArrayBodyEnvelopeIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_body_envelope_slot_assembly"
            and isinstance(source.output, ExactArrayBodyEnvelopeIr)
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_source_unsupported_diagnostic(
                    "array-initialization slot form lowering consumes only "
                    "typed M65 ExactArrayBodyEnvelopeIr values, the "
                    "array_body_envelope_slot_assembly stage output, or a "
                    "LoweredImplementation with a matching M65 envelope",
                    location,
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_body_envelopes) == 1:
            return Result.ok(source.array_body_envelopes[0])
        if len(source.array_body_envelopes) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_slot_missing_diagnostic(
                        "array-initialization slot form lowering requires a "
                        "LoweredImplementation carrying an accepted M65 "
                        "array_body_envelopes entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_slot_source_unsupported_diagnostic(
                    "array-initialization slot form lowering consumes exactly "
                    "one M65 array-body envelope at this boundary",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_slot_source_unsupported_diagnostic(
                "array-initialization slot form lowering consumes only typed "
                "M65 ExactArrayBodyEnvelopeIr values or "
                "array_body_envelope_slot_assembly stage output",
                None,
            ),
        )
    )


def _array_initialization_helper_request_source(
    source: object,
) -> Result[ExactArrayInitializationSlotFormIr]:
    if isinstance(source, ExactArrayInitializationSlotFormIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_slot_form_lowering"
            and isinstance(source.output, ExactArrayInitializationSlotFormIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_request_source_unsupported_diagnostic(
                    "array-initialization helper request lowering consumes only "
                    "typed M66 ExactArrayInitializationSlotFormIr values, the "
                    "array_initialization_slot_form_lowering stage output, or "
                    "a LoweredImplementation with a matching M66 form",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_slot_forms) == 1:
            return Result.ok(source.array_initialization_slot_forms[0])
        if len(source.array_initialization_slot_forms) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_helper_request_missing_form_diagnostic(
                        "array-initialization helper request lowering requires "
                        "a LoweredImplementation carrying an accepted M66 "
                        "array_initialization_slot_forms entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_request_source_unsupported_diagnostic(
                    "array-initialization helper request lowering consumes "
                    "exactly one M66 array-initialization slot form at this "
                    "boundary",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_helper_request_source_unsupported_diagnostic(
                "array-initialization helper request lowering consumes only "
                "typed M66 ExactArrayInitializationSlotFormIr values or "
                "array_initialization_slot_form_lowering stage output",
                None,
            ),
        )
    )


def _array_initialization_base_type_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationHelperRequestIr]:
    if isinstance(source, ExactArrayInitializationHelperRequestIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_helper_request_lowering"
            and isinstance(source.output, ExactArrayInitializationHelperRequestIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_base_type_resolution_source_unsupported_diagnostic(
                    "array-initialization base-type request resolution consumes "
                    "typed M67 ExactArrayInitializationHelperRequestIr values, "
                    "the array_initialization_helper_request_lowering stage "
                    "output, or a LoweredImplementation with a matching M67 "
                    "helper-request IR",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_helper_requests) == 1:
            return Result.ok(source.array_initialization_helper_requests[0])
        if len(source.array_initialization_helper_requests) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_base_type_resolution_missing_ir_diagnostic(
                        "array-initialization base-type request resolution "
                        "requires a LoweredImplementation carrying an accepted "
                        "M67 array_initialization_helper_requests entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_base_type_resolution_multiple_ir_diagnostic(
                    "array-initialization base-type request resolution requires "
                    "exactly one M67 array_initialization_helper_requests "
                    f"entry; got {len(source.array_initialization_helper_requests)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_base_type_resolution_source_unsupported_diagnostic(
                "array-initialization base-type request resolution consumes "
                "typed M67 ExactArrayInitializationHelperRequestIr values or "
                "array_initialization_helper_request_lowering stage output",
                None,
            ),
        )
    )


def _array_initialization_vector_length_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationBaseTypeResolutionIr]:
    if isinstance(source, ExactArrayInitializationBaseTypeResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_base_type_request_resolution"
            and isinstance(source.output, ExactArrayInitializationBaseTypeResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_source_unsupported_diagnostic(
                    "array-initialization vector-length request resolution "
                    "consumes typed M68 "
                    "ExactArrayInitializationBaseTypeResolutionIr values, the "
                    "array_initialization_base_type_request_resolution stage "
                    "output, or a LoweredImplementation with a matching M68 "
                    "base-type resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_base_type_resolutions) == 1:
            return Result.ok(source.array_initialization_base_type_resolutions[0])
        if len(source.array_initialization_base_type_resolutions) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_vector_length_missing_ir_diagnostic(
                        "array-initialization vector-length request resolution "
                        "requires a LoweredImplementation carrying an accepted "
                        "M68 array_initialization_base_type_resolutions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_multiple_ir_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires exactly one M68 "
                    "array_initialization_base_type_resolutions entry; got "
                    f"{len(source.array_initialization_base_type_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_vector_length_source_unsupported_diagnostic(
                "array-initialization vector-length request resolution "
                "consumes only typed M68 "
                "ExactArrayInitializationBaseTypeResolutionIr values or "
                "array_initialization_base_type_request_resolution stage output",
                None,
            ),
        )
    )


def _array_initialization_vector_alignment_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationVectorLengthResolutionIr]:
    if isinstance(source, ExactArrayInitializationVectorLengthResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_vector_length_request_resolution"
            and isinstance(source.output, ExactArrayInitializationVectorLengthResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_source_unsupported_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "consumes typed M70 "
                    "ExactArrayInitializationVectorLengthResolutionIr values, "
                    "the array_initialization_vector_length_request_resolution "
                    "stage output, or a LoweredImplementation with a matching "
                    "M70 vector-length resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_vector_length_resolutions) == 1:
            return Result.ok(source.array_initialization_vector_length_resolutions[0])
        if len(source.array_initialization_vector_length_resolutions) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_vector_alignment_missing_ir_diagnostic(
                        "array-initialization vector-alignment request "
                        "resolution requires a LoweredImplementation carrying "
                        "an accepted M70 "
                        "array_initialization_vector_length_resolutions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_multiple_ir_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires exactly one M70 "
                    "array_initialization_vector_length_resolutions entry; "
                    f"got {len(source.array_initialization_vector_length_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_vector_alignment_source_unsupported_diagnostic(
                "array-initialization vector-alignment request resolution "
                "consumes only typed M70 "
                "ExactArrayInitializationVectorLengthResolutionIr values or "
                "array_initialization_vector_length_request_resolution stage "
                "output",
                None,
            ),
        )
    )


def _array_initialization_helper_set_completion_source(
    source: object,
) -> Result[ExactArrayInitializationVectorAlignmentResolutionIr]:
    if isinstance(source, ExactArrayInitializationVectorAlignmentResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_vector_alignment_request_resolution"
            and isinstance(source.output, ExactArrayInitializationVectorAlignmentResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_set_source_unsupported_diagnostic(
                    "array-initialization helper-set completion consumes typed "
                    "M71 ExactArrayInitializationVectorAlignmentResolutionIr "
                    "values, the "
                    "array_initialization_vector_alignment_request_resolution "
                    "stage output, or a LoweredImplementation with a matching "
                    "M71 vector-alignment resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_vector_alignment_resolutions) == 1:
            return Result.ok(
                source.array_initialization_vector_alignment_resolutions[0]
            )
        if len(source.array_initialization_vector_alignment_resolutions) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_helper_set_missing_ir_diagnostic(
                        "array-initialization helper-set completion requires "
                        "a LoweredImplementation carrying an accepted M71 "
                        "array_initialization_vector_alignment_resolutions "
                        "entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_helper_set_multiple_ir_diagnostic(
                    "array-initialization helper-set completion requires "
                    "exactly one M71 "
                    "array_initialization_vector_alignment_resolutions entry; "
                    f"got {len(source.array_initialization_vector_alignment_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_helper_set_source_unsupported_diagnostic(
                "array-initialization helper-set completion consumes only "
                "typed M71 ExactArrayInitializationVectorAlignmentResolutionIr "
                "values or "
                "array_initialization_vector_alignment_request_resolution "
                "stage output",
                None,
            ),
        )
    )


def _array_initialization_declaration_shell_source(
    source: object,
) -> Result[ExactArrayInitializationHelperSetCompletionIr]:
    if isinstance(source, ExactArrayInitializationHelperSetCompletionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_helper_set_completion"
            and isinstance(source.output, ExactArrayInitializationHelperSetCompletionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_declaration_shell_source_unsupported_diagnostic(
                    "array-initialization declaration-shell lowering consumes "
                    "typed M72 ExactArrayInitializationHelperSetCompletionIr "
                    "values, the array_initialization_helper_set_completion "
                    "stage output, or a LoweredImplementation with a matching "
                    "M72 helper-set completion",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_helper_set_completions) == 1:
            return Result.ok(source.array_initialization_helper_set_completions[0])
        if len(source.array_initialization_helper_set_completions) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._array_initialization_declaration_shell_missing_ir_diagnostic(
                        "array-initialization declaration-shell lowering "
                        "requires a LoweredImplementation carrying an accepted "
                        "M72 array_initialization_helper_set_completions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_declaration_shell_multiple_ir_diagnostic(
                    "array-initialization declaration-shell lowering requires "
                    "exactly one M72 "
                    "array_initialization_helper_set_completions entry; got "
                    f"{len(source.array_initialization_helper_set_completions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_initialization_declaration_shell_source_unsupported_diagnostic(
                "array-initialization declaration-shell lowering consumes "
                "only typed M72 "
                "ExactArrayInitializationHelperSetCompletionIr values or "
                "array_initialization_helper_set_completion stage output",
                None,
            ),
        )
        )


def lower_exact_predicate_path_structural_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactPredicatePathStructuralRequestIr]:
    source_result = _predicate_path_structural_request_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    sequence = source_result.unwrap()

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or sequence.candidate_id
    )
    effective_target_extension = target_extension or sequence.target_extension
    effective_source_extension = source_extension or sequence.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or sequence.selected_type_tag
    )
    if (
        effective_candidate_id != sequence.candidate_id
        or effective_target_extension != sequence.target_extension
        or effective_source_extension != sequence.source_extension
        or effective_type_tag != sequence.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._predicate_path_context_mismatch_diagnostic(
                    "predicate-path structural request lowering requires the "
                    "typed selected candidate context to match the M74 sequence "
                    "candidate id, target extension, source extension, and "
                    "selected type tag",
                    sequence.source_location,
                ),
            )
        )

    validation_diagnostics = _array_body_validation._validate_predicate_path_structural_request_input(
        sequence,
    )
    if validation_diagnostics:
        return Result.failure(sort_diagnostics(tuple(validation_diagnostics)))

    init_role = sequence.roles[1]
    selected_role = sequence.roles[2]
    store_role = sequence.roles[3]
    assert init_role.opaque_source_text is not None
    assert store_role.opaque_source_text is not None
    init_match = _exact_shapes.EXACT_PREDICATE_INIT_SLOT_RE.match(init_role.opaque_source_text)
    store_match = _exact_shapes.EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE.match(
        store_role.opaque_source_text,
    )
    if init_match is None or store_match is None:
        raise AssertionError("predicate-path validation did not enforce exact shapes")
    selected_body_envelope = selected_role.selected_body_envelope
    assert isinstance(
        selected_body_envelope,
        (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
    )
    if isinstance(selected_body_envelope, SelectedBodyEnvelopeIr):
        entry = selected_body_envelope.entries[0]
        selected_update_state: ExactPredicatePathSelectedUpdateState = (
            "accepted_selected_update"
        )
        selected_update_assignment_target_text = entry.assignment_target_text
        selected_update_direct_intrinsic_token_text = entry.direct_intrinsic_token_text
        selected_update_source_location = entry.source_location
    else:
        selected_update_state = "accepted_no_update"
        selected_update_assignment_target_text = None
        selected_update_direct_intrinsic_token_text = None
        selected_update_source_location = selected_body_envelope.source_location

    try:
        return Result.ok(
            ExactPredicatePathStructuralRequestIr(
                source_sequence=sequence,
                predicate_init_role_label="opaque_predicate_init_shaped_slot",
                predicate_init_slot_ordinal=1,
                predicate_init_source_location=init_role.source_location,
                predicate_type_token_text=init_match.group("predicate_type"),
                predicate_token_text=init_match.group("predicate_token"),
                predicate_init_direct_intrinsic_token_text=init_match.group(
                    "direct_intrinsic_token",
                ),
                selected_update_state=selected_update_state,
                selected_body_envelope=selected_body_envelope,
                selected_update_slot_ordinal=2,
                selected_update_source_location=selected_update_source_location,
                selected_update_assignment_target_text=(
                    selected_update_assignment_target_text
                ),
                selected_update_direct_intrinsic_token_text=(
                    selected_update_direct_intrinsic_token_text
                ),
                store_call_role_label="opaque_post_branch_store_call_shaped_slot",
                store_call_slot_ordinal=3,
                store_call_source_location=store_role.source_location,
                store_call_predicate_argument_text=store_match.group(
                    "predicate_token",
                ),
                candidate_id=sequence.candidate_id,
                target_extension=sequence.target_extension,
                source_extension=sequence.source_extension,
                selected_type_tag=sequence.selected_type_tag,
                originating_branch_chain_id=sequence.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                    str(exc),
                    sequence.source_location,
                ),
            )
        )


def lower_exact_post_branch_intrinsic_call_site_structural_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactPostBranchIntrinsicCallSiteStructuralRequestIr]:
    source_result = _post_branch_intrinsic_call_site_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    predicate_path = source_result.unwrap()

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or predicate_path.candidate_id
    )
    effective_target_extension = target_extension or predicate_path.target_extension
    effective_source_extension = source_extension or predicate_path.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or predicate_path.selected_type_tag
    )
    if (
        effective_candidate_id != predicate_path.candidate_id
        or effective_target_extension != predicate_path.target_extension
        or effective_source_extension != predicate_path.source_extension
        or effective_type_tag != predicate_path.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._post_branch_call_site_context_mismatch_diagnostic(
                    "post-branch intrinsic call-site structural request lowering "
                    "requires the typed selected candidate context to match the "
                    "M75 predicate-path request candidate id, target extension, "
                    "source extension, and selected type tag",
                    predicate_path.source_location,
                ),
            )
        )

    validation_diagnostics = _array_body_validation._validate_post_branch_intrinsic_call_site_input(
        predicate_path,
    )
    if validation_diagnostics:
        return Result.failure(sort_diagnostics(tuple(validation_diagnostics)))

    sequence = predicate_path.source_sequence
    post_branch_role = sequence.roles[3]
    source_text = post_branch_role.opaque_source_text
    if source_text is None:
        raise AssertionError("M76 validation did not enforce source text")
    match = _exact_shapes.POST_BRANCH_INTRINSIC_CALL_SITE_CONTAINER_RE.match(
        source_text,
    )
    if match is None:
        raise AssertionError("M76 validation did not enforce call-site shape")
    arguments = tuple(part.strip() for part in match.group("arguments").split(","))
    if len(arguments) != 3:
        raise AssertionError("M76 validation did not enforce argument count")
    member_match = _exact_shapes.POST_BRANCH_MEMBER_ACCESS_ARGUMENT_RE.match(
        arguments[1],
    )
    if member_match is None:
        raise AssertionError("M76 validation did not enforce tmp.data() shape")
    try:
        return Result.ok(
            ExactPostBranchIntrinsicCallSiteStructuralRequestIr(
                source_predicate_path=predicate_path,
                source_sequence=sequence,
                post_branch_role_label="opaque_post_branch_store_call_shaped_slot",
                post_branch_slot_ordinal=3,
                post_branch_source_location=post_branch_role.source_location,
                original_call_source_text=source_text,
                call_head_token_text=match.group("call_head"),
                unresolved_intrinsic_token_text=match.group("intrinsic_token"),
                predicate_argument_ordinal=0,
                predicate_argument_token_text=arguments[0],
                predicate_argument_source_slot_ordinal=(
                    predicate_path.store_call_slot_ordinal
                ),
                predicate_argument_source_token_text=(
                    predicate_path.store_call_predicate_argument_text
                ),
                member_access_argument_ordinal=1,
                member_access_argument_text=arguments[1],
                member_access_base_token_text=member_match.group("base_token"),
                member_access_member_token_text=member_match.group("member_token"),
                member_access_source_variable_token_text=(
                    sequence.declaration_shell.variable_token
                ),
                source_operand_argument_ordinal=2,
                source_operand_argument_token_text=arguments[2],
                candidate_id=predicate_path.candidate_id,
                target_extension=predicate_path.target_extension,
                source_extension=predicate_path.source_extension,
                selected_type_tag=predicate_path.selected_type_tag,
                originating_branch_chain_id=(
                    predicate_path.originating_branch_chain_id
                ),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._post_branch_call_site_provenance_mismatch_diagnostic(
                    str(exc),
                    predicate_path.source_location,
                ),
            )
        )


def _post_branch_intrinsic_call_site_source(
    source: object,
) -> Result[ExactPredicatePathStructuralRequestIr]:
    if isinstance(source, ExactPredicatePathStructuralRequestIr):
        return Result.ok(source)

    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "predicate_path_structural_request_lowering"
            and isinstance(source.output, ExactPredicatePathStructuralRequestIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._post_branch_call_site_source_unsupported_diagnostic(
                    "post-branch intrinsic call-site structural request lowering "
                    "consumes accepted M75 ExactPredicatePathStructuralRequestIr "
                    "values, the predicate_path_structural_request_lowering stage "
                    "output, or a LoweredImplementation carrying exactly one "
                    "M75 value",
                    _stage_output_location(source.output),
                ),
            )
        )

    if isinstance(source, LoweredImplementation):
        if len(source.predicate_path_structural_requests) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._post_branch_call_site_missing_ir_diagnostic(
                        "post-branch intrinsic call-site structural request "
                        "lowering requires a LoweredImplementation carrying "
                        "one accepted M75 predicate_path_structural_requests entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        if len(source.predicate_path_structural_requests) > 1:
            return Result.failure(
                (
                    _array_body_diagnostics._post_branch_call_site_multiple_ir_diagnostic(
                        "post-branch intrinsic call-site structural request "
                        "lowering requires exactly one M75 "
                        "predicate_path_structural_requests entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.ok(source.predicate_path_structural_requests[0])

    return Result.failure(
        (
            _array_body_diagnostics._post_branch_call_site_source_unsupported_diagnostic(
                "post-branch intrinsic call-site structural request lowering "
                "consumes only accepted M75 predicate-path typed sources",
                None,
            ),
        )
    )


def _array_body_structural_sequence_source(
    source: object,
    declaration_shell: object | None,
) -> Result[tuple[ExactArrayBodyEnvelopeIr, ExactArrayInitializationDeclarationShellIr]]:
    if isinstance(source, ExactArrayInitializationDeclarationShellIr):
        if declaration_shell is not None:
            return Result.failure(
                (
                    _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                        "array-body structural sequence classification accepts "
                        "a separate declaration-shell argument only when the "
                        "primary source is an M65 envelope source",
                        source.source_location,
                    ),
                )
            )
        return Result.ok((source.source_envelope, source))

    if isinstance(source, ExactArrayBodyEnvelopeIr):
        shell_result = _array_body_structural_sequence_shell_source(
            declaration_shell,
        )
        if not shell_result.is_ok:
            return Result.failure(shell_result.diagnostics)
        return Result.ok((source, shell_result.unwrap()))

    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_declaration_shell_lowering"
            and isinstance(source.output, ExactArrayInitializationDeclarationShellIr)
        ):
            if declaration_shell is not None:
                return Result.failure(
                    (
                        _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                            "array-body structural sequence classification "
                            "accepts a separate declaration-shell argument only "
                            "when the primary source is an M65 envelope source",
                            source.output.source_location,
                        ),
                    )
                )
            return Result.ok((source.output.source_envelope, source.output))
        if (
            source.stage == "array_body_envelope_slot_assembly"
            and isinstance(source.output, ExactArrayBodyEnvelopeIr)
        ):
            shell_result = _array_body_structural_sequence_shell_source(
                declaration_shell,
            )
            if not shell_result.is_ok:
                return Result.failure(shell_result.diagnostics)
            return Result.ok((source.output, shell_result.unwrap()))
        return Result.failure(
            (
                _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                    "array-body structural sequence classification consumes "
                    "accepted M65 ExactArrayBodyEnvelopeIr values with an M73 "
                    "declaration shell, accepted M73 declaration-shell values "
                    "or stage output, or a LoweredImplementation carrying "
                    "exactly one matching M65 envelope and M73 shell",
                    _stage_output_location(source.output),
                ),
            )
        )

    if isinstance(source, LoweredImplementation):
        if declaration_shell is not None:
            return Result.failure(
                (
                    _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                        "array-body structural sequence classification does "
                        "not accept a separate declaration-shell argument when "
                        "the primary source is a LoweredImplementation",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        diagnostics: list[Diagnostic] = []
        if len(source.array_body_envelopes) == 0:
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "a LoweredImplementation carrying one accepted M65 "
                    "array_body_envelopes entry",
                    _lowered_implementation_location(source),
                )
            )
        elif len(source.array_body_envelopes) > 1:
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_multiple_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "exactly one M65 array_body_envelopes entry",
                    _lowered_implementation_location(source),
                )
            )
        if len(source.array_initialization_declaration_shells) == 0:
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "a LoweredImplementation carrying one accepted M73 "
                    "array_initialization_declaration_shells entry",
                    _lowered_implementation_location(source),
                )
            )
        elif len(source.array_initialization_declaration_shells) > 1:
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_multiple_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "exactly one M73 array_initialization_declaration_shells "
                    "entry",
                    _lowered_implementation_location(source),
                )
            )
        if diagnostics:
            return Result.failure(sort_diagnostics(tuple(diagnostics)))
        return Result.ok(
            (
                source.array_body_envelopes[0],
                source.array_initialization_declaration_shells[0],
            )
        )

    return Result.failure(
        (
            _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification consumes only "
                "accepted M65 envelope/M73 declaration-shell typed sources or "
                "a matching LoweredImplementation",
                None,
            ),
        )
    )


def _array_body_structural_sequence_shell_source(
    source: object | None,
) -> Result[ExactArrayInitializationDeclarationShellIr]:
    if isinstance(source, ExactArrayInitializationDeclarationShellIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_declaration_shell_lowering"
            and isinstance(source.output, ExactArrayInitializationDeclarationShellIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                    "array-body structural sequence classification requires "
                    "the separate source to be an accepted M73 declaration "
                    "shell or array_initialization_declaration_shell_lowering "
                    "stage output",
                    _stage_output_location(source.output),
                ),
            )
        )
    if source is None:
        return Result.failure(
            (
                _array_body_diagnostics._array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "an accepted M73 declaration-shell value when the primary "
                    "source is an M65 envelope",
                    None,
                ),
            )
        )
    return Result.failure(
        (
            _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M73 declaration-shell value",
                None,
            ),
        )
    )


def _predicate_path_structural_request_source(
    source: object,
) -> Result[ExactArrayBodyStructuralSequenceIr]:
    if isinstance(source, ExactArrayBodyStructuralSequenceIr):
        return Result.ok(source)

    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_body_structural_sequence_classification"
            and isinstance(source.output, ExactArrayBodyStructuralSequenceIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_diagnostics._predicate_path_source_unsupported_diagnostic(
                    "predicate-path structural request lowering consumes "
                    "accepted M74 ExactArrayBodyStructuralSequenceIr values, "
                    "the array_body_structural_sequence_classification stage "
                    "output, or a LoweredImplementation carrying exactly one "
                    "M74 value",
                    _stage_output_location(source.output),
                ),
            )
        )

    if isinstance(source, LoweredImplementation):
        if len(source.array_body_structural_sequences) == 0:
            return Result.failure(
                (
                    _array_body_diagnostics._predicate_path_missing_ir_diagnostic(
                        "predicate-path structural request lowering requires "
                        "a LoweredImplementation carrying one accepted M74 "
                        "array_body_structural_sequences entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        if len(source.array_body_structural_sequences) > 1:
            return Result.failure(
                (
                    _array_body_diagnostics._predicate_path_multiple_ir_diagnostic(
                        "predicate-path structural request lowering requires "
                        "exactly one M74 array_body_structural_sequences entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.ok(source.array_body_structural_sequences[0])

    return Result.failure(
        (
            _array_body_diagnostics._predicate_path_source_unsupported_diagnostic(
                "predicate-path structural request lowering consumes only "
                "accepted M74 structural sequence typed sources",
                None,
            ),
        )
    )


def _array_initialization_envelope_slot(
    envelope: ExactArrayBodyEnvelopeIr,
) -> ExactArrayBodyEnvelopeSlot | None:
    if len(envelope.slots) <= 0:
        return None
    return envelope.slots[0]


def _lowered_implementation_location(
    implementation: LoweredImplementation,
) -> SourceLocation | None:
    for call_site in implementation.post_branch_intrinsic_call_site_structural_requests:
        return call_site.source_location
    for predicate_path in implementation.predicate_path_structural_requests:
        return predicate_path.source_location
    for array_envelope in implementation.array_body_envelopes:
        return array_envelope.source_location
    for declaration_shell in implementation.array_initialization_declaration_shells:
        return declaration_shell.source_location
    for selected_envelope in implementation.selected_body_envelopes:
        return selected_envelope.source_location
    for stage in implementation.generation_stages:
        location = _stage_output_location(stage.output)
        if location is not None:
            return location
    return None


def _validate_exact_array_body_envelope_skeleton(
    skeleton: ExactArrayBodyEnvelopeSkeleton,
    envelope: GenerationSelectedBodyEnvelopeIr,
) -> Diagnostic | None:
    if not skeleton.is_exact_array_body_shape:
        return _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly supports only the exact "
            "array.tsl:105-111 structural skeleton",
            skeleton.source_location,
        )

    slots = skeleton.slots
    if len(slots) != len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
        return _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly requires exactly five slots; "
            f"got {len(slots)}",
            skeleton.source_location,
        )

    labels = tuple(slot.label for slot in slots)
    if labels != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS:
        if _has_exact_array_body_labels_once(labels):
            return Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
                "array-body envelope slots must appear in the exact M64 "
                f"order {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got "
                f"{labels!r}",
                location=skeleton.source_location,
            )
        return _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly requires exactly one of each "
            f"M64 slot label {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got "
            f"{labels!r}",
            skeleton.source_location,
        )

    ordinals = tuple(slot.ordinal for slot in slots)
    if ordinals != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
            "array-body envelope slot ordinals must be deterministic and "
            f"ordered as {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS!r}; got "
            f"{ordinals!r}",
            location=skeleton.source_location,
        )

    for slot in slots:
        if (
            slot.candidate_id != skeleton.candidate_id
            or slot.selected_type_tag != skeleton.selected_type_tag
            or slot.originating_branch_chain_id
            != skeleton.originating_branch_chain_id
        ):
            return Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
                "array-body envelope skeleton slot provenance must match "
                "the skeleton candidate, selected type tag, and branch-chain "
                "identity",
                location=slot.source_location,
            )
        if (
            slot.label in _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS
            and not (slot.opaque_source_text or "").strip()
        ):
            return _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
                "array-body envelope opaque slots must preserve opaque source text",
                slot.source_location,
            )
        if slot.label == "selected_body_envelope" and slot.opaque_source_text is not None:
            return _array_body_diagnostics._array_body_envelope_shape_unsupported_diagnostic(
                "array-body envelope selected-body slot must reference the "
                "M63 envelope without carrying selected branch text",
                slot.source_location,
            )

    if (
        skeleton.candidate_id != envelope.candidate_id
        or skeleton.selected_type_tag != envelope.selected_type_tag
        or skeleton.originating_branch_chain_id
        != envelope.originating_branch_chain_id
    ):
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
            "array-body envelope skeleton provenance must match the nested "
            "M63 envelope candidate id, selected type tag, and branch-chain "
            "identity",
            location=skeleton.source_location,
        )

    selected_slot = slots[2]
    if (
        selected_slot.candidate_id != envelope.candidate_id
        or selected_slot.selected_type_tag != envelope.selected_type_tag
        or selected_slot.originating_branch_chain_id
        != envelope.originating_branch_chain_id
    ):
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
            "array-body envelope selected slot provenance must match the "
            "nested M63 envelope candidate id, selected type tag, and "
            "branch-chain identity",
            location=selected_slot.source_location,
        )

    return None


def _has_exact_array_body_labels_once(
    labels: tuple[ExactArrayBodyEnvelopeSlotLabel, ...],
) -> bool:
    if len(labels) != len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
        return False
    return all(
        labels.count(expected) == 1
        for expected in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS
    )




def _validate_selected_body_envelope_source(
    body_ir: SelectedAssignmentDirectIntrinsicBodyIr,
) -> Diagnostic | None:
    if not body_ir.candidate_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR candidate id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.selected_type_tag:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR type tag must be non-empty",
            body_ir.source_location,
        )
    if body_ir.selected_literal not in (2, 4, 8):
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR literal must be 2, 4, or 8",
            body_ir.source_location,
        )
    if not body_ir.originating_branch_chain_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR branch-chain id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.original_opaque_body_text.strip():
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR original body text must be non-empty",
            body_ir.source_location,
        )
    if body_ir.source_location is None:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR requires source location",
            None,
        )
    if not body_ir.assignment_target_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR assignment target text must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.opaque_rhs_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR RHS text must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.direct_intrinsic_token_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR direct intrinsic token text must be non-empty",
            body_ir.source_location,
        )
    if tuple(body_ir.direct_intrinsic_argument_texts) != ():
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR must carry an explicit empty argument list",
            body_ir.source_location,
        )
    return None


def _validate_no_selected_body_envelope_source(
    body_ir: NoSelectedAssignmentDirectIntrinsicBodyIr,
) -> Diagnostic | None:
    if not body_ir.candidate_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR candidate id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.selected_type_tag:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR type tag must be non-empty",
            body_ir.source_location,
        )
    if body_ir.source_location is None:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR requires source location",
            None,
        )
    if not body_ir.originating_branch_chain_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR branch-chain id must be non-empty",
            body_ir.source_location,
        )
    if tuple(body_ir.attempted_literals) != (2, 4, 8):
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR attempted literals must be 2, 4, 8",
            body_ir.source_location,
        )
    return None


def _recognize_opaque_selected_branch_body_assignment_form(
    handoff: OpaqueSelectedBranchBodyHandoff,
) -> Result[SelectedBranchBodyAssignmentFormRecognition]:
    parsed = _parse_selected_body_assignment_form(
        handoff.opaque_body_text,
        handoff.source_location,
    )
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    assignment_target_text, opaque_rhs_text, direct_intrinsic_token_text = (
        parsed.unwrap()
    )
    return Result.ok(
        SelectedBranchBodyAssignmentFormRecognition(
            candidate_id=handoff.candidate_id,
            selected_type_tag=handoff.selected_type_tag,
            selected_literal=handoff.selected_literal,
            originating_branch_chain_id=handoff.originating_branch_chain_id,
            original_opaque_body_text=handoff.opaque_body_text,
            selected_statement_location=handoff.source_location,
            assignment_target_text=assignment_target_text,
            opaque_rhs_text=opaque_rhs_text,
            direct_intrinsic_token_text=direct_intrinsic_token_text,
        )
    )


def _parse_selected_body_assignment_form(
    body_text: str,
    location: SourceLocation | None,
) -> Result[tuple[str, str, str]]:
    parsed = _exact_shapes.parse_exact_selected_body_assignment_form(
        body_text,
        location,
    )
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    shape = parsed.unwrap()
    return Result.ok(
        (
            shape.assignment_target_text,
            shape.opaque_rhs_text,
            shape.direct_intrinsic_token_text,
        )
    )


def _classify_payload(candidate: ImplementationCandidate) -> Result[ClassifiedPayload]:
    body = candidate.implementation.body
    text = body.text
    if body.kind == "tsil" and text is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-PAYLOAD-SHAPE",
                    f"candidate {candidate.candidate_id!r} has a TSIL payload "
                    "that is not text",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    return Result.ok(
        ClassifiedPayload(
            body_kind=body.kind,
            classification=body.classification,
            raw_payload=body.payload,
            text=text,
            has_generation_condition=(
                text is not None
                and _has_generation_helper(text)
            ),
        )
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
                    _recognition_stage("generation.predicate", text),
                    *(
                        _generation_value_stage(value)
                        for value in staged_predicate.generation_values
                    ),
                    _generation_predicate_stage(staged_predicate.predicate),
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
                    _recognition_stage("generation.value", text),
                    _generation_value_stage(value),
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
            control_flow_stage = _generation_control_flow_stage(staged_chain.pruning)
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
            envelope_stage = _selected_body_envelope_stage(envelope)
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
                    generation_stages=(
                        _recognition_stage(
                            "generation.control_flow",
                            item.payload.text or text,
                        ),
                        *(
                            _generation_value_stage(value)
                            for value in staged_chain.generation_values
                        ),
                        *(
                            _generation_predicate_stage(predicate)
                            for predicate in staged_chain.generation_predicates
                        ),
                        control_flow_stage,
                        _selected_body_stage(handoff),
                        _selected_body_form_recognition_stage(
                            recognized_assignment_form,
                        ),
                        _selected_body_ir_stage(body_ir),
                        envelope_stage,
                        *array_initialization_pipeline.stages,
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
            _recognition_stage("generation.control_flow", item.payload.text or text),
            _generation_control_flow_stage(branch),
        )
        if _has_generation_helper(text):
            return Result.failure((_generation_diagnostics._unresolved_selected_branch_diagnostic(item, text),))

    statement = _mini_return_statement(item, text)
    if not statement.is_ok:
        return Result.failure(statement.diagnostics)
    lowered_statement = statement.unwrap()

    return Result.ok(
        LoweredImplementation(
            candidate_id=item.candidate_id,
            status="lowered",
            statements=(lowered_statement,),
            generation_branches=generation_branches,
            generation_stages=(
                *generation_stages,
                _selected_body_stage(lowered_statement),
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


def _mini_return_statement(
    item: LoweringInput,
    text: str | None = None,
) -> Result[TsilReturnStatement]:
    text = item.payload.text or "" if text is None else text
    match = _DIRECT_PARAMETER_ADD_RETURN_RE.fullmatch(text)
    if match is not None:
        return _direct_parameter_add_return_statement(item, match)
    if _INTRIN_COMPOSE_MARKER_RE.search(text):
        return _intrinsic_compose_return_statement(item, text)
    if _EMIT_RETURN_HEAD_RE.match(text):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-RETURN-SHAPE",
                    "mini TSIL lowering supports only direct parameter addition "
                    "returns shaped as 'emit_return(<parameter> + <parameter>);' "
                    "or intrinsic-compose returns shaped as "
                    "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
                    location=item.source_location,
                ),
            )
        )
    return Result.failure((_unsupported_payload_diagnostic(item),))


def _direct_parameter_add_return_statement(
    item: LoweringInput,
    match: re.Match[str],
) -> Result[TsilReturnStatement]:
    left_name, right_name = match.groups()
    unknown = _unknown_parameter_names(item, (left_name, right_name))
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference(left_name),
                right=TsilParameterReference(right_name),
            )
        )
    )


def _intrinsic_compose_return_statement(
    item: LoweringInput,
    text: str,
) -> Result[TsilReturnStatement]:
    match = _INTRIN_COMPOSE_RETURN_RE.fullmatch(text)
    if match is None:
        return Result.failure((_malformed_intrinsic_compose_diagnostic(item),))

    intrinsic_name, arguments_text = match.groups()
    if intrinsic_name != "add":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-UNSUPPORTED",
                    "mini TSIL lowering supports only intrinsic-compose "
                    f"intrinsic 'add'; got {intrinsic_name!r}",
                    location=item.source_location,
                ),
            )
        )

    argument_names = _intrinsic_argument_names(arguments_text)
    invalid_arguments = tuple(
        argument
        for argument in argument_names
        if _TSIL_IDENTIFIER_RE.fullmatch(argument) is None
    )
    if invalid_arguments:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARGUMENT",
                    "mini TSIL lowering supports only primitive parameter "
                    "references as intrin_compose<add> arguments; invalid "
                    f"argument(s): "
                    f"{', '.join(repr(argument) for argument in invalid_arguments)}",
                    location=item.source_location,
                ),
            )
        )

    if len(argument_names) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARITY",
                    "mini TSIL lowering supports only "
                    "intrin_compose<add> with exactly two arguments; got "
                    f"{len(argument_names)}",
                    location=item.source_location,
                ),
            )
        )

    unknown = _unknown_parameter_names(item, argument_names)
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilIntrinsicComposeExpression(
                intrinsic=intrinsic_name,
                arguments=tuple(
                    TsilParameterReference(argument) for argument in argument_names
                ),
            )
        )
    )


def _intrinsic_argument_names(arguments_text: str) -> tuple[str, ...]:
    stripped = arguments_text.strip()
    if not stripped:
        return ()
    return tuple(argument.strip() for argument in arguments_text.split(","))


def _unknown_parameter_names(
    item: LoweringInput,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    parameter_names = tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    return tuple(name for name in names if name not in parameter_names)


def _unknown_parameter_diagnostic(
    item: LoweringInput,
    unknown_names: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
        "mini TSIL lowering can reference only declared primitive "
        f"parameters; unknown name(s): "
        f"{', '.join(repr(name) for name in unknown_names)}",
        location=item.source_location,
    )


def _malformed_intrinsic_compose_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-INTRIN-MALFORMED",
        "mini TSIL lowering supports only intrinsic-compose returns shaped as "
        "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
        location=item.source_location,
    )


def _inconsistent_selected_body_envelope_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT",
        "selected-body envelope lowering received inconsistent M62 body IR "
        f"boundary state: {detail}",
        location=location,
    )


def _unsupported_payload_diagnostic(
    item: LoweringInput,
    *,
    strategy: LoweringStrategy = "mini_tsil",
) -> Diagnostic:
    if item.payload.classification == "tsil":
        code = "TSL-LOWER-TSIL-UNSUPPORTED"
        if strategy == "typed_opaque":
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering is disabled by the typed-opaque strategy"
            )
        else:
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering supports only the mini direct parameter-add return "
                "and intrinsic-compose add return slices"
            )
        if item.payload.has_generation_condition:
            message += (
                " and contains generation-time helpers that must be evaluated "
                "by a future lowering slice"
            )
    else:
        code = "TSL-LOWER-PAYLOAD-UNSUPPORTED"
        message = (
            f"candidate {item.candidate_id!r} has unsupported implementation "
            f"payload kind {item.payload.body_kind!r}"
        )
    return Diagnostic.error(code, message, location=item.source_location)
