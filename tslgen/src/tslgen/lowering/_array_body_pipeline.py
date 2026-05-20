from __future__ import annotations

from dataclasses import dataclass, field

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._pipeline as _lowering_pipeline
from tslgen.lowering._array_body_lowering import (
    assemble_exact_array_body_envelope,
    lower_exact_array_body_structural_sequence,
    lower_exact_array_initialization_base_type_request,
    lower_exact_array_initialization_declaration_shell,
    lower_exact_array_initialization_helper_requests,
    lower_exact_array_initialization_helper_set_completion,
    lower_exact_array_initialization_slot_form,
    lower_exact_array_initialization_vector_alignment_request,
    lower_exact_array_initialization_vector_length_request,
    lower_exact_post_branch_intrinsic_call_site_structural_request,
    lower_exact_predicate_path_structural_request,
)
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSkeletonKey,
    ExactArrayBodyEnvelopeSkeletonRequirement,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
)
from tslgen.lowering._array_body_sources import (
    ExactArrayBodyLoweredImplementationSource,
    ExactArrayBodyPipelineInput,
    ExactArrayBodyPipelineRequest,
)
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    NoSelectedBodyEnvelopeIr,
    SelectedBodyEnvelopeIr,
)
from tslgen.lowering._stage_contracts import GenerationLoweringStage
from tslgen.lowering._return_emission import (
    lower_exact_return_emission_structural_request,
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
    return_emission_structural_requests: tuple[
        ExactReturnEmissionStructuralRequestIr, ...
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
        object.__setattr__(
            self,
            "return_emission_structural_requests",
            tuple(self.return_emission_structural_requests),
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
            tuple(
                request.key for request in self.return_emission_structural_requests
            ),
            self.pipeline_snapshot.key,
            tuple(stage.key for stage in self.stages),
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


def _return_emission_structural_request_stage(
    output: ExactReturnEmissionStructuralRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="return_emission_structural_request_lowering",
        output=output,
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
    request: ExactArrayBodyPipelineRequest,
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
    item: ExactArrayBodyPipelineInput,
    request: ExactArrayBodyPipelineRequest,
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
        request.generation_context,
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
            request.generation_context,
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
            request.generation_context,
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
        request.generation_context,
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
        request.generation_context,
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
        request.generation_context,
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
        request.generation_context,
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
            request.generation_context,
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
    return_emission_result = lower_exact_return_emission_structural_request(
        post_branch_call_site_stage,
        request.generation_context,
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not return_emission_result.is_ok:
        return Result.failure(return_emission_result.diagnostics)
    return_emission = return_emission_result.unwrap()
    return_emission_stage = _return_emission_structural_request_stage(
        return_emission,
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
        return_emission_stage,
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
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="return_emission_structural_request_lowering",
                stage=return_emission_stage,
                artifact_kind="return_emission_structural_request",
                artifact_key=return_emission.key,
                artifact_value=return_emission,
                depends_on=(
                    "array_body_structural_sequence",
                    "post_branch_intrinsic_call_site_structural_request",
                ),
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
            return_emission_structural_requests=(return_emission,),
            pipeline_snapshot=pipeline_snapshot,
            stages=pipeline_stages,
        )
    )


def _unused_array_body_envelope_skeleton_diagnostics(
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
    implementations: tuple[ExactArrayBodyLoweredImplementationSource, ...],
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
