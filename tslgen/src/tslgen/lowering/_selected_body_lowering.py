from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
import tslgen.lowering._exact_shapes as _exact_shapes
from tslgen.lowering._generation_models import GenerationSizeByteBranchChainPruning
from tslgen.lowering._generation_models import PrunedGenerationBranch
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
from tslgen.lowering._stage_contracts import (
    GenerationLoweringStage,
    GenerationLoweringStageOutput,
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


def _stage_output_location(
    output: GenerationLoweringStageOutput,
) -> SourceLocation | None:
    if isinstance(
        output,
        (GenerationSizeByteBranchChainPruning, PrunedGenerationBranch),
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
