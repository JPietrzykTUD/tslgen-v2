from __future__ import annotations

from tslgen.core.result import Result
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._array_body_validation as _array_body_validation
import tslgen.lowering._exact_shapes as _exact_shapes
from tslgen.lowering._array_body_models import (
    ExactReturnEmissionStructuralRequestIr,
)
from tslgen.lowering._array_body_sources import (
    ExactArrayBodyGenerationContext,
    _generation_context_or_default,
    _return_emission_structural_request_source,
)


def lower_exact_return_emission_structural_request(
    source: object,
    context: ExactArrayBodyGenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactReturnEmissionStructuralRequestIr]:
    source_result = _return_emission_structural_request_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    post_branch_call_site = source_result.unwrap()

    generation_context = _generation_context_or_default(context)
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or post_branch_call_site.candidate_id
    )
    effective_target_extension = target_extension or post_branch_call_site.target_extension
    effective_source_extension = (
        source_extension or post_branch_call_site.source_extension
    )
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or post_branch_call_site.selected_type_tag
    )
    if (
        effective_candidate_id != post_branch_call_site.candidate_id
        or effective_target_extension != post_branch_call_site.target_extension
        or effective_source_extension != post_branch_call_site.source_extension
        or effective_type_tag != post_branch_call_site.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_diagnostics._return_emission_context_mismatch_diagnostic(
                    "return-emission structural request lowering requires the "
                    "typed selected candidate context to match the M76 "
                    "post-branch call-site request candidate id, target "
                    "extension, source extension, and selected type tag",
                    post_branch_call_site.source_location,
                ),
            )
        )

    validation_diagnostics = (
        _array_body_validation._validate_return_emission_structural_request_input(
            post_branch_call_site,
        )
    )
    if validation_diagnostics:
        return Result.failure(validation_diagnostics)

    sequence = post_branch_call_site.source_sequence
    return_role = sequence.roles[4]
    source_text = return_role.opaque_source_text
    if source_text is None:
        raise AssertionError("M87 validation did not enforce source text")
    match = _exact_shapes.EXACT_RETURN_EMISSION_SLOT_RE.match(source_text)
    if match is None:
        raise AssertionError("M87 validation did not enforce return-emission shape")

    try:
        return Result.ok(
            ExactReturnEmissionStructuralRequestIr(
                source_post_branch_call_site=post_branch_call_site,
                source_sequence=sequence,
                return_role_label="opaque_return_emission_shaped_slot",
                return_slot_ordinal=4,
                return_source_location=return_role.source_location,
                original_return_source_text=source_text,
                emit_return_token_text=match.group("emit_return_token"),
                returned_token_text=match.group("returned_token"),
                declaration_variable_token_text=(
                    sequence.declaration_shell.variable_token
                ),
                candidate_id=post_branch_call_site.candidate_id,
                target_extension=post_branch_call_site.target_extension,
                source_extension=post_branch_call_site.source_extension,
                selected_type_tag=post_branch_call_site.selected_type_tag,
                originating_branch_chain_id=(
                    post_branch_call_site.originating_branch_chain_id
                ),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_diagnostics._return_emission_provenance_mismatch_diagnostic(
                    str(exc),
                    post_branch_call_site.source_location,
                ),
            )
        )
