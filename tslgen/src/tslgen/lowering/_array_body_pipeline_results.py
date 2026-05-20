from __future__ import annotations

from dataclasses import dataclass, field

import tslgen.lowering._pipeline as _lowering_pipeline
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
)
from tslgen.lowering._array_body_completion_package import (
    ExactArrayLoweringCompletionPackageIr,
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
from tslgen.lowering._stage_contracts import GenerationLoweringStage


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
    array_body_structural_packages: tuple[
        ExactArrayBodyStructuralPackageIr, ...
    ] = ()
    array_backend_deferred_request_inventories: tuple[
        ExactArrayBackendDeferredRequestInventoryIr, ...
    ] = ()
    array_lowering_completion_packages: tuple[
        ExactArrayLoweringCompletionPackageIr, ...
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
                request.key
                for request in self.return_emission_structural_requests
            ),
            tuple(
                package.key for package in self.array_body_structural_packages
            ),
            tuple(
                inventory.key
                for inventory in self.array_backend_deferred_request_inventories
            ),
            tuple(
                package.key
                for package in self.array_lowering_completion_packages
            ),
            self.pipeline_snapshot.key,
            tuple(stage.key for stage in self.stages),
        )
