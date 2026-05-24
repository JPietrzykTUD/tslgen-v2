from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic
from tslgen.core.result import Result
from tslgen.core.diagnostics import sort_diagnostics
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._array_body_shapes as _array_body_shapes
import tslgen.lowering._array_body_validation as _array_body_validation
import tslgen.lowering._exact_shapes as _exact_shapes
import tslgen.lowering._generation_queries as _generation_queries
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeOpaqueSlot,
    ExactArrayBodyEnvelopeSelectedSlot,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSlot,
    ExactArrayBodyEnvelopeSlotLabel,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationUnresolvedLeaf,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactPredicatePathSelectedUpdateState,
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS,
    _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS,
    _ExactArrayBodyStructuralRole,
)
from tslgen.lowering._array_body_sources import (
    ExactArrayBodyGenerationContext,
    _array_body_envelope_m63_source,
    _array_body_structural_sequence_source,
    _array_initialization_base_type_resolution_source,
    _array_initialization_declaration_shell_source,
    _array_initialization_envelope_slot,
    _array_initialization_helper_request_source,
    _array_initialization_helper_set_completion_source,
    _array_initialization_slot_form_source,
    _array_initialization_vector_alignment_resolution_source,
    _array_initialization_vector_length_resolution_source,
    _generation_context_or_default,
    _post_branch_intrinsic_call_site_source,
    _predicate_path_structural_request_source,
)
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    NoSelectedBodyEnvelopeIr,
    SelectedBodyEnvelopeIr,
)
from tslgen.lowering._stage_contracts import GenerationLoweringStage


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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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


def lower_exact_predicate_path_structural_request(
    source: object,
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
    context: ExactArrayBodyGenerationContext | None = None,
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

    generation_context = _generation_context_or_default(context)
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
