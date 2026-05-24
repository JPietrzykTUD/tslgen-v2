from __future__ import annotations

import tslgen.lowering._pipeline as _lowering_pipeline
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
)
from tslgen.lowering._array_body_completion_package import (
    ExactArrayLoweringCompletionPackageIr,
)
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffRequestIr,
)
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
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
)
from tslgen.lowering._array_body_package import (
    ExactArrayBodyStructuralPackageIr,
)
from tslgen.lowering._array_body_pipeline_results import (
    _ExactArrayInitializationStagePipelineResult,
)
from tslgen.lowering._operation_package import LoweringOperationPackageIr
from tslgen.lowering._stage_contracts import GenerationLoweringStage


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


def _array_body_structural_package_stage(
    output: ExactArrayBodyStructuralPackageIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_body_structural_package_assembly",
        output=output,
    )


def _array_backend_deferred_request_inventory_stage(
    output: ExactArrayBackendDeferredRequestInventoryIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_backend_deferred_request_inventory",
        output=output,
    )


def _array_lowering_completion_package_stage(
    output: ExactArrayLoweringCompletionPackageIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_lowering_completion_package",
        output=output,
    )


def _array_backend_handoff_request_stage(
    output: ExactArrayBackendHandoffRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_backend_handoff_request",
        output=output,
    )


def _lowering_operation_package_stage(
    output: LoweringOperationPackageIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="lowering_operation_package",
        output=output,
    )


def _assemble_exact_array_initialization_stage_pipeline_result(
    *,
    array_body_stage: GenerationLoweringStage,
    array_envelope: ExactArrayBodyEnvelopeIr,
    array_initialization_slot_form_stage: GenerationLoweringStage,
    array_initialization_slot_form: ExactArrayInitializationSlotFormIr,
    array_initialization_helper_request_stage: GenerationLoweringStage,
    array_initialization_helper_request: ExactArrayInitializationHelperRequestIr,
    base_type_resolution_stage: GenerationLoweringStage,
    base_type_resolution: ExactArrayInitializationBaseTypeResolutionIr,
    vector_length_resolution_stage: GenerationLoweringStage,
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
    vector_alignment_resolution_stage: GenerationLoweringStage,
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
    helper_set_completion_stage: GenerationLoweringStage,
    helper_set_completion: ExactArrayInitializationHelperSetCompletionIr,
    declaration_shell_stage: GenerationLoweringStage,
    declaration_shell: ExactArrayInitializationDeclarationShellIr,
    structural_sequence_stage: GenerationLoweringStage,
    structural_sequence: ExactArrayBodyStructuralSequenceIr,
    predicate_path_stage: GenerationLoweringStage,
    predicate_path: ExactPredicatePathStructuralRequestIr,
    post_branch_call_site_stage: GenerationLoweringStage,
    post_branch_call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    return_emission_stage: GenerationLoweringStage,
    return_emission: ExactReturnEmissionStructuralRequestIr,
    structural_package_stage: GenerationLoweringStage,
    structural_package: ExactArrayBodyStructuralPackageIr,
    backend_deferred_inventory_stage: GenerationLoweringStage,
    backend_deferred_inventory: ExactArrayBackendDeferredRequestInventoryIr,
    completion_package_stage: GenerationLoweringStage,
    completion_package: ExactArrayLoweringCompletionPackageIr,
    backend_handoff_request_stage: GenerationLoweringStage,
    backend_handoff_request: ExactArrayBackendHandoffRequestIr,
    operation_package_stage: GenerationLoweringStage,
    operation_package: LoweringOperationPackageIr,
) -> _ExactArrayInitializationStagePipelineResult:
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
        structural_package_stage,
        backend_deferred_inventory_stage,
        completion_package_stage,
        backend_handoff_request_stage,
        operation_package_stage,
    )
    pipeline_snapshot = _assemble_exact_array_body_pipeline_snapshot(
        array_body_stage=array_body_stage,
        array_envelope=array_envelope,
        array_initialization_slot_form_stage=array_initialization_slot_form_stage,
        array_initialization_slot_form=array_initialization_slot_form,
        array_initialization_helper_request_stage=(
            array_initialization_helper_request_stage
        ),
        array_initialization_helper_request=array_initialization_helper_request,
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
        operation_package_stage=operation_package_stage,
        operation_package=operation_package,
    )

    return _ExactArrayInitializationStagePipelineResult(
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
        array_body_structural_packages=(structural_package,),
        array_backend_deferred_request_inventories=(
            backend_deferred_inventory,
        ),
        array_lowering_completion_packages=(completion_package,),
        array_backend_handoff_requests=(backend_handoff_request,),
        operation_packages=(operation_package,),
        pipeline_snapshot=pipeline_snapshot,
        stages=pipeline_stages,
    )


def _assemble_exact_array_body_pipeline_snapshot(
    *,
    array_body_stage: GenerationLoweringStage,
    array_envelope: ExactArrayBodyEnvelopeIr,
    array_initialization_slot_form_stage: GenerationLoweringStage,
    array_initialization_slot_form: ExactArrayInitializationSlotFormIr,
    array_initialization_helper_request_stage: GenerationLoweringStage,
    array_initialization_helper_request: ExactArrayInitializationHelperRequestIr,
    base_type_resolution_stage: GenerationLoweringStage,
    base_type_resolution: ExactArrayInitializationBaseTypeResolutionIr,
    vector_length_resolution_stage: GenerationLoweringStage,
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
    vector_alignment_resolution_stage: GenerationLoweringStage,
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
    helper_set_completion_stage: GenerationLoweringStage,
    helper_set_completion: ExactArrayInitializationHelperSetCompletionIr,
    declaration_shell_stage: GenerationLoweringStage,
    declaration_shell: ExactArrayInitializationDeclarationShellIr,
    structural_sequence_stage: GenerationLoweringStage,
    structural_sequence: ExactArrayBodyStructuralSequenceIr,
    predicate_path_stage: GenerationLoweringStage,
    predicate_path: ExactPredicatePathStructuralRequestIr,
    post_branch_call_site_stage: GenerationLoweringStage,
    post_branch_call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    return_emission_stage: GenerationLoweringStage,
    return_emission: ExactReturnEmissionStructuralRequestIr,
    structural_package_stage: GenerationLoweringStage,
    structural_package: ExactArrayBodyStructuralPackageIr,
    backend_deferred_inventory_stage: GenerationLoweringStage,
    backend_deferred_inventory: ExactArrayBackendDeferredRequestInventoryIr,
    completion_package_stage: GenerationLoweringStage,
    completion_package: ExactArrayLoweringCompletionPackageIr,
    backend_handoff_request_stage: GenerationLoweringStage,
    backend_handoff_request: ExactArrayBackendHandoffRequestIr,
    operation_package_stage: GenerationLoweringStage,
    operation_package: LoweringOperationPackageIr,
) -> _lowering_pipeline.ExactArrayBodyPipelineSnapshot:
    return _lowering_pipeline.ExactArrayBodyPipelineSnapshot(
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
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_body_structural_package_assembly",
                stage=structural_package_stage,
                artifact_kind="array_body_structural_package",
                artifact_key=structural_package.key,
                artifact_value=structural_package,
                depends_on=(
                    "array_body_envelope",
                    "array_initialization_helper_set_completion",
                    "array_initialization_declaration_shell",
                    "array_body_structural_sequence",
                    "predicate_path_structural_request",
                    "post_branch_intrinsic_call_site_structural_request",
                    "return_emission_structural_request",
                ),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_backend_deferred_request_inventory",
                stage=backend_deferred_inventory_stage,
                artifact_kind="array_backend_deferred_request_inventory",
                artifact_key=backend_deferred_inventory.key,
                artifact_value=backend_deferred_inventory,
                depends_on=("array_body_structural_package",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_lowering_completion_package",
                stage=completion_package_stage,
                artifact_kind="array_lowering_completion_package",
                artifact_key=completion_package.key,
                artifact_value=completion_package,
                depends_on=("array_backend_deferred_request_inventory",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="array_backend_handoff_request",
                stage=backend_handoff_request_stage,
                artifact_kind="array_backend_handoff_request",
                artifact_key=backend_handoff_request.key,
                artifact_value=backend_handoff_request,
                depends_on=("array_lowering_completion_package",),
            ),
            _lowering_pipeline.exact_array_body_pipeline_step(
                stage_name="lowering_operation_package",
                stage=operation_package_stage,
                artifact_kind="lowering_operation_package",
                artifact_key=operation_package.key,
                artifact_value=operation_package,
                depends_on=("array_backend_handoff_request",),
            ),
        ),
    )
