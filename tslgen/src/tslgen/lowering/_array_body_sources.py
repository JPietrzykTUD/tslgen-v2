from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from tslgen.core.diagnostics import Diagnostic, SourceLocation, sort_diagnostics
from tslgen.core.result import Result
from tslgen.domain.generation_rules import (
    ConcreteIntegerGenerationRuleSet,
    ScalarSizeBytesGenerationRuleSet,
    default_concrete_integer_generation_rule_set,
    default_scalar_size_bytes_generation_rule_set,
)
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._generation_queries as _generation_queries
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSkeletonRequirement,
    ExactArrayBodyEnvelopeSlot,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationVectorAlignmentMetadata,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorLengthMetadata,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactArrayBodyStructuralSequenceIr,
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
)
from tslgen.lowering._generation_models import (
    GenerationSizeByteBranchChainPruning,
    PrunedGenerationBranch,
)
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    NoSelectedAssignmentDirectIntrinsicBodyIr,
    NoSelectedBodyEnvelopeIr,
    NoSelectedBranchBodyAssignmentFormRecognition,
    NoSelectedBranchBodyHandoff,
    OpaqueSelectedBranchBodyHandoff,
    SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeIr,
    SelectedBranchBodyAssignmentFormRecognition,
)
from tslgen.lowering._stage_contracts import (
    GenerationLoweringStage,
    GenerationLoweringStageOutput,
)


class ExactArrayBodyGenerationContext(_generation_queries.GenerationQueryContext, Protocol):
    @property
    def selected_candidate_id(self) -> str | None: ...

    @property
    def use_candidate_type_tag(self) -> bool: ...

    @property
    def array_initialization_vector_length_metadata(
        self,
    ) -> tuple[ExactArrayInitializationVectorLengthMetadata, ...]: ...

    @property
    def array_initialization_vector_alignment_metadata(
        self,
    ) -> tuple[ExactArrayInitializationVectorAlignmentMetadata, ...]: ...


@dataclass(frozen=True, slots=True)
class _DefaultExactArrayBodyGenerationContext:
    type_tag_override: str | None = None
    selected_type_tag: str | None = None
    selected_candidate_id: str | None = None
    use_candidate_type_tag: bool = True
    concrete_integer_generation_rules: ConcreteIntegerGenerationRuleSet = field(
        default_factory=default_concrete_integer_generation_rule_set,
    )
    scalar_size_bytes_generation_rules: ScalarSizeBytesGenerationRuleSet = field(
        default_factory=default_scalar_size_bytes_generation_rule_set,
    )
    array_initialization_vector_length_metadata: tuple[
        ExactArrayInitializationVectorLengthMetadata, ...
    ] = ()
    array_initialization_vector_alignment_metadata: tuple[
        ExactArrayInitializationVectorAlignmentMetadata, ...
    ] = ()


def _generation_context_or_default(
    context: ExactArrayBodyGenerationContext | None,
) -> ExactArrayBodyGenerationContext:
    if context is None:
        return _DefaultExactArrayBodyGenerationContext()
    return context


class ExactArrayBodyPipelineCandidate(Protocol):
    @property
    def type_tag(self) -> str: ...

    @property
    def target_extension(self) -> str: ...

    @property
    def source_extension(self) -> str: ...


class ExactArrayBodyPipelineInput(Protocol):
    @property
    def candidate_id(self) -> str: ...

    @property
    def candidate(self) -> ExactArrayBodyPipelineCandidate: ...


class ExactArrayBodyPipelineRequest(Protocol):
    @property
    def generation_context(self) -> ExactArrayBodyGenerationContext: ...

    @property
    def array_body_envelope_skeletons(
        self,
    ) -> tuple[ExactArrayBodyEnvelopeSkeleton, ...]: ...

    @property
    def required_array_body_envelope_skeletons(
        self,
    ) -> tuple[ExactArrayBodyEnvelopeSkeletonRequirement, ...]: ...


@runtime_checkable
class ExactArrayBodyLoweredImplementationSource(Protocol):
    @property
    def selected_body_envelopes(
        self,
    ) -> tuple[GenerationSelectedBodyEnvelopeIr, ...]: ...

    @property
    def array_body_envelopes(self) -> tuple[ExactArrayBodyEnvelopeIr, ...]: ...

    @property
    def array_initialization_slot_forms(
        self,
    ) -> tuple[ExactArrayInitializationSlotFormIr, ...]: ...

    @property
    def array_initialization_helper_requests(
        self,
    ) -> tuple[ExactArrayInitializationHelperRequestIr, ...]: ...

    @property
    def array_initialization_base_type_resolutions(
        self,
    ) -> tuple[ExactArrayInitializationBaseTypeResolutionIr, ...]: ...

    @property
    def array_initialization_vector_length_resolutions(
        self,
    ) -> tuple[ExactArrayInitializationVectorLengthResolutionIr, ...]: ...

    @property
    def array_initialization_vector_alignment_resolutions(
        self,
    ) -> tuple[ExactArrayInitializationVectorAlignmentResolutionIr, ...]: ...

    @property
    def array_initialization_helper_set_completions(
        self,
    ) -> tuple[ExactArrayInitializationHelperSetCompletionIr, ...]: ...

    @property
    def array_initialization_declaration_shells(
        self,
    ) -> tuple[ExactArrayInitializationDeclarationShellIr, ...]: ...

    @property
    def array_body_structural_sequences(
        self,
    ) -> tuple[ExactArrayBodyStructuralSequenceIr, ...]: ...

    @property
    def predicate_path_structural_requests(
        self,
    ) -> tuple[ExactPredicatePathStructuralRequestIr, ...]: ...

    @property
    def post_branch_intrinsic_call_site_structural_requests(
        self,
    ) -> tuple[ExactPostBranchIntrinsicCallSiteStructuralRequestIr, ...]: ...

    @property
    def generation_stages(self) -> tuple[GenerationLoweringStage, ...]: ...



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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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

    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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

    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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

    if isinstance(source, ExactArrayBodyLoweredImplementationSource):
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
    implementation: ExactArrayBodyLoweredImplementationSource,
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
