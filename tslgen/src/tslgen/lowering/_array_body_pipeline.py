from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._array_body_stage_assembly as _array_body_stage_assembly
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
)
from tslgen.lowering._array_body_package import (
    lower_exact_array_body_structural_package,
)
from tslgen.lowering._array_body_backend_deferred_requests import (
    lower_exact_array_backend_deferred_request_inventory,
)
from tslgen.lowering._array_body_completion_package import (
    lower_exact_array_lowering_completion_package,
)
from tslgen.lowering._array_body_backend_handoff import (
    lower_exact_array_backend_handoff_request,
)
from tslgen.lowering._array_body_pipeline_results import (
    _ExactArrayInitializationStagePipelineResult,
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

    array_body_stage = (
        _array_body_stage_assembly._array_body_envelope_slot_assembly_stage(
            array_envelope,
        )
    )
    array_initialization_slot_form_result = (
        lower_exact_array_initialization_slot_form(array_envelope)
    )
    if not array_initialization_slot_form_result.is_ok:
        return Result.failure(array_initialization_slot_form_result.diagnostics)
    array_initialization_slot_form = array_initialization_slot_form_result.unwrap()
    array_initialization_slot_form_stage = (
        _array_body_stage_assembly._array_initialization_slot_form_stage(
            array_initialization_slot_form,
        )
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
        _array_body_stage_assembly._array_initialization_helper_request_stage(
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
    base_type_resolution_stage = (
        _array_body_stage_assembly._array_initialization_base_type_resolution_stage(
            base_type_resolution,
        )
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
        _array_body_stage_assembly._array_initialization_vector_length_resolution_stage(
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
        _array_body_stage_assembly._array_initialization_vector_alignment_resolution_stage(
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
    helper_set_completion_stage = (
        _array_body_stage_assembly._array_initialization_helper_set_completion_stage(
            helper_set_completion,
        )
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
    declaration_shell_stage = (
        _array_body_stage_assembly._array_initialization_declaration_shell_stage(
            declaration_shell,
        )
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
    structural_sequence_stage = (
        _array_body_stage_assembly._array_body_structural_sequence_stage(
            structural_sequence,
        )
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
    predicate_path_stage = (
        _array_body_stage_assembly._predicate_path_structural_request_stage(
            predicate_path,
        )
    )
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
        _array_body_stage_assembly._post_branch_intrinsic_call_site_structural_request_stage(
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
    return_emission_stage = (
        _array_body_stage_assembly._return_emission_structural_request_stage(
            return_emission,
        )
    )
    structural_package_result = lower_exact_array_body_structural_package(
        return_emission_stage,
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
    if not structural_package_result.is_ok:
        return Result.failure(structural_package_result.diagnostics)
    structural_package = structural_package_result.unwrap()
    structural_package_stage = (
        _array_body_stage_assembly._array_body_structural_package_stage(
            structural_package,
        )
    )
    backend_deferred_inventory_result = (
        lower_exact_array_backend_deferred_request_inventory(
            structural_package_stage,
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
    if not backend_deferred_inventory_result.is_ok:
        return Result.failure(backend_deferred_inventory_result.diagnostics)
    backend_deferred_inventory = backend_deferred_inventory_result.unwrap()
    backend_deferred_inventory_stage = (
        _array_body_stage_assembly._array_backend_deferred_request_inventory_stage(
            backend_deferred_inventory,
        )
    )
    completion_package_result = lower_exact_array_lowering_completion_package(
        backend_deferred_inventory_stage,
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
    if not completion_package_result.is_ok:
        return Result.failure(completion_package_result.diagnostics)
    completion_package = completion_package_result.unwrap()
    completion_package_stage = (
        _array_body_stage_assembly._array_lowering_completion_package_stage(
            completion_package,
        )
    )
    backend_handoff_request_result = lower_exact_array_backend_handoff_request(
        completion_package_stage,
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
    if not backend_handoff_request_result.is_ok:
        return Result.failure(backend_handoff_request_result.diagnostics)
    backend_handoff_request = backend_handoff_request_result.unwrap()
    backend_handoff_request_stage = (
        _array_body_stage_assembly._array_backend_handoff_request_stage(
            backend_handoff_request,
        )
    )

    return Result.ok(
        _array_body_stage_assembly._assemble_exact_array_initialization_stage_pipeline_result(
            array_body_stage=array_body_stage,
            array_envelope=array_envelope,
            array_initialization_slot_form_stage=(
                array_initialization_slot_form_stage
            ),
            array_initialization_slot_form=array_initialization_slot_form,
            array_initialization_helper_request_stage=(
                array_initialization_helper_request_stage
            ),
            array_initialization_helper_request=(
                array_initialization_helper_request
            ),
            base_type_resolution_stage=base_type_resolution_stage,
            base_type_resolution=base_type_resolution,
            vector_length_resolution_stage=vector_length_resolution_stage,
            vector_length_resolution=vector_length_resolution,
            vector_alignment_resolution_stage=vector_alignment_resolution_stage,
            vector_alignment_resolution=vector_alignment_resolution,
            helper_set_completion_stage=helper_set_completion_stage,
            helper_set_completion=helper_set_completion,
            declaration_shell_stage=declaration_shell_stage,
            declaration_shell=declaration_shell,
            structural_sequence_stage=structural_sequence_stage,
            structural_sequence=structural_sequence,
            predicate_path_stage=predicate_path_stage,
            predicate_path=predicate_path,
            post_branch_call_site_stage=post_branch_call_site_stage,
            post_branch_call_site=post_branch_call_site,
            return_emission_stage=return_emission_stage,
            return_emission=return_emission,
            structural_package_stage=structural_package_stage,
            structural_package=structural_package,
            backend_deferred_inventory_stage=backend_deferred_inventory_stage,
            backend_deferred_inventory=backend_deferred_inventory,
            completion_package_stage=completion_package_stage,
            completion_package=completion_package,
            backend_handoff_request_stage=backend_handoff_request_stage,
            backend_handoff_request=backend_handoff_request,
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
            _array_body_diagnostics._orphan_array_body_envelope_skeleton_diagnostic(
                skeleton_key,
                skeleton,
            )
        )
    return tuple(diagnostics)
