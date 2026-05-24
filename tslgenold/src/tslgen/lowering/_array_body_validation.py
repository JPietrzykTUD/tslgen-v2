from __future__ import annotations

import re
from typing import Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
import tslgen.lowering._array_body_diagnostics as _array_body_diagnostics
import tslgen.lowering._array_body_models as _array_body_models
import tslgen.lowering._selected_body_models as _selected_body_models
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeOpaqueSlot,
    ExactArrayBodyEnvelopeSelectedSlot,
    ExactArrayBodyEnvelopeSlot,
    ExactArrayBodyStructuralRoleLabel,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationUnresolvedLeaf,
    ExactArrayInitializationVectorAlignmentMetadata,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorAlignmentValue,
    ExactArrayInitializationVectorLengthMetadata,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactArrayInitializationVectorLengthValue,
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS,
    _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS,
    _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS,
    _ExactArrayBodyStructuralRole,
)
import tslgen.lowering._array_body_shapes as _array_body_shapes
import tslgen.lowering._exact_shapes as _exact_shapes


class _ArrayInitializationVectorLengthMetadataContext(Protocol):
    @property
    def array_initialization_vector_length_metadata(
        self,
    ) -> tuple[ExactArrayInitializationVectorLengthMetadata, ...]: ...


class _ArrayInitializationVectorAlignmentMetadataContext(Protocol):
    @property
    def array_initialization_vector_alignment_metadata(
        self,
    ) -> tuple[ExactArrayInitializationVectorAlignmentMetadata, ...]: ...


def _validate_array_initialization_slot_position(
    envelope: ExactArrayBodyEnvelopeIr,
    slot: ExactArrayBodyEnvelopeOpaqueSlot,
) -> Diagnostic | None:
    if (
        slot.candidate_id != envelope.candidate_id
        or slot.selected_type_tag != envelope.selected_type_tag
        or slot.originating_branch_chain_id != envelope.originating_branch_chain_id
    ):
        return _array_body_diagnostics._array_initialization_slot_provenance_mismatch_diagnostic(
            "array-initialization slot provenance must match the M65 "
            "array-body envelope candidate id, selected type tag, and "
            "branch-chain identity",
            slot.source_location,
        )
    if (
        slot.label != "opaque_pre_branch_array_initialization"
        or slot.ordinal != 0
    ):
        return _array_body_diagnostics._array_initialization_slot_wrong_position_diagnostic(
            "array-initialization slot form lowering refines only the "
            "opaque_pre_branch_array_initialization slot at ordinal 0; got "
            f"label {slot.label!r} and ordinal {slot.ordinal!r}",
            slot.source_location,
        )
    return None


def _validate_array_initialization_helper_form_provenance(
    form: ExactArrayInitializationSlotFormIr,
) -> Diagnostic | None:
    if not isinstance(form.source_envelope, ExactArrayBodyEnvelopeIr):
        return _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "slot form to reference an M65 array-body envelope",
            form.source_location,
        )
    if (
        form.candidate_id != form.source_envelope.candidate_id
        or form.selected_type_tag != form.source_envelope.selected_type_tag
        or form.originating_branch_chain_id
        != form.source_envelope.originating_branch_chain_id
    ):
        return _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires M66 form "
            "provenance (candidate id, selected type tag, and branch-chain "
            "identity) to match its M65 envelope",
            form.source_location,
        )
    if form.slot_label != "opaque_pre_branch_array_initialization":
        return _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "opaque_pre_branch_array_initialization slot form",
            form.source_location,
        )
    if form.slot_ordinal != 0:
        return _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "slot form at ordinal 0",
            form.source_location,
        )
    if form.variable_token != "tmp":
        return _array_body_diagnostics._array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "variable token tmp",
            form.variable_token_location or form.source_location,
        )
    return None


def _validate_array_initialization_base_type_request_ir_provenance(
    request_ir: ExactArrayInitializationHelperRequestIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if request_ir.source_envelope != request_ir.source_form.source_envelope:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR envelope must match its M66 slot form "
                "envelope",
                request_ir.source_location,
            )
        )
    if request_ir.source_location != request_ir.source_form.source_location:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR source location must match its M66 slot "
                "form source location",
                request_ir.source_location,
            )
        )
    if (
        request_ir.candidate_id != request_ir.source_form.candidate_id
        or request_ir.selected_type_tag != request_ir.source_form.selected_type_tag
        or request_ir.originating_branch_chain_id
        != request_ir.source_form.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR provenance must match its M66 slot form",
                request_ir.source_location,
            )
        )
    if (
        request_ir.slot_label != request_ir.source_form.slot_label
        or request_ir.slot_ordinal != request_ir.source_form.slot_ordinal
        or request_ir.variable_token != request_ir.source_form.variable_token
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR slot provenance must match its M66 "
                "slot form",
                request_ir.source_location,
            )
        )
    for request in request_ir.requests:
        if request.source_form != request_ir.source_form:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record source form must match the "
                    "source helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != request_ir.source_envelope:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record envelope must match the source "
                    "helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != request_ir.candidate_id
            or request.selected_type_tag != request_ir.selected_type_tag
            or request.originating_branch_chain_id
            != request_ir.originating_branch_chain_id
            or request.slot_label != request_ir.slot_label
            or request.slot_ordinal != request_ir.slot_ordinal
            or request.variable_token != request_ir.variable_token
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record provenance must match the "
                    "source helper-request IR",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_base_type_request_record(
    request_ir: ExactArrayInitializationHelperRequestIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE
    base_records = tuple(
        request
        for request in request_ir.requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not base_records:
        ordinal_or_kind_records = tuple(
            request
            for request in request_ir.requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_body_diagnostics._array_initialization_base_type_resolution_mismatch_diagnostic(
                        "array-initialization base-type request resolution "
                        "expected the M67 base request to carry ordinal "
                        f"{rule.request_ordinal}, kind {rule.request_kind!r}, "
                        f"and leaf kind {rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_missing_request_diagnostic(
                "array-initialization base-type request resolution requires "
                "one M67 base-type request record",
                request_ir.source_location,
            )
        )
        return None
    if len(base_records) > 1:
        for request in base_records:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_base_type_resolution_duplicate_request_diagnostic(
                    "array-initialization base-type request resolution requires "
                    "exactly one M67 base-type request record; duplicate "
                    f"record appeared at ordinal {request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    base_request = base_records[0]
    if (
        base_request.request_ordinal != rule.request_ordinal
        or base_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_mismatch_diagnostic(
                "array-initialization base-type request resolution expected "
                f"ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{base_request.request_ordinal} and kind "
                f"{base_request.request_kind!r}",
                base_request.leaf_source_location,
            )
        )
    if base_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_base_type_resolution_unsupported_request_diagnostic(
                "array-initialization base-type request resolution preserves "
                "the M67 leaf source text only as provenance and accepts only "
                "the exact M67 base-type leaf text for that typed request; got "
                f"{base_request.leaf_source_text!r}",
                base_request.leaf_source_location,
            )
        )
    return base_request


def _validate_array_initialization_vector_length_resolution_provenance(
    base_resolution: ExactArrayInitializationBaseTypeResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    request_ir = base_resolution.source_request_ir
    if base_resolution.source_base_type_request not in request_ir.requests:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution source request must come from its "
                "M67 helper-request IR",
                base_resolution.source_location,
            )
        )
    if base_resolution.source_location != request_ir.source_location:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution source location must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    if (
        base_resolution.candidate_id != request_ir.candidate_id
        or base_resolution.selected_type_tag != request_ir.selected_type_tag
        or base_resolution.originating_branch_chain_id
        != request_ir.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution provenance must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    if (
        base_resolution.slot_label != request_ir.slot_label
        or base_resolution.slot_ordinal != request_ir.slot_ordinal
        or base_resolution.variable_token != request_ir.variable_token
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution slot provenance must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    for request in base_resolution.unresolved_requests:
        if request.source_form != request_ir.source_form:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != request_ir.source_envelope:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != base_resolution.candidate_id
            or request.selected_type_tag != base_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != base_resolution.originating_branch_chain_id
            or request.slot_label != base_resolution.slot_label
            or request.slot_ordinal != base_resolution.slot_ordinal
            or request.variable_token != base_resolution.variable_token
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record provenance must match the "
                    "source base-type resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_vector_length_request_record(
    base_resolution: ExactArrayInitializationBaseTypeResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_VECTOR_LENGTH_REQUEST_RULE
    vector_length_records = tuple(
        request
        for request in base_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not vector_length_records:
        ordinal_or_kind_records = tuple(
            request
            for request in base_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_body_diagnostics._array_initialization_vector_length_mismatch_diagnostic(
                        "array-initialization vector-length request resolution "
                        "expected the M67 vector-length request to carry "
                        f"ordinal {rule.request_ordinal}, kind "
                        f"{rule.request_kind!r}, and leaf kind "
                        f"{rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_missing_request_diagnostic(
                "array-initialization vector-length request resolution "
                "requires one M67 vector-length request record preserved by "
                "M68",
                base_resolution.source_location,
            )
        )
        return None
    if len(vector_length_records) > 1:
        for request in vector_length_records:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_length_duplicate_request_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires exactly one M67 vector-length request record; "
                    f"duplicate record appeared at ordinal "
                    f"{request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    vector_length_request = vector_length_records[0]
    if (
        vector_length_request.request_ordinal != rule.request_ordinal
        or vector_length_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_mismatch_diagnostic(
                "array-initialization vector-length request resolution "
                f"expected ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{vector_length_request.request_ordinal} and kind "
                f"{vector_length_request.request_kind!r}",
                vector_length_request.leaf_source_location,
            )
        )
    if vector_length_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_length_unsupported_request_diagnostic(
                "array-initialization vector-length request resolution "
                "preserves the M67 leaf source text only as provenance and "
                "accepts only the exact M67 vector-length leaf text for that "
                f"typed request; got {vector_length_request.leaf_source_text!r}",
                vector_length_request.leaf_source_location,
            )
        )
    return vector_length_request


def _array_initialization_vector_length_metadata_for_context(
    context: _ArrayInitializationVectorLengthMetadataContext,
    *,
    candidate_id: str,
    target_extension: str,
    source_extension: str,
    selected_type_tag: str,
    location: SourceLocation | None,
) -> Result[ExactArrayInitializationVectorLengthMetadata]:
    lookup_key = (
        candidate_id,
        target_extension,
        source_extension,
        selected_type_tag,
    )
    matches = tuple(
        metadata
        for metadata in context.array_initialization_vector_length_metadata
        if metadata.lookup_key == lookup_key
    )
    if not matches:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_length_metadata_missing_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires explicit typed vector-length metadata for "
                    f"candidate {candidate_id!r}, target extension "
                    f"{target_extension!r}, source extension "
                    f"{source_extension!r}, and selected type tag "
                    f"{selected_type_tag!r}",
                    location,
                ),
            )
        )
    if len(matches) > 1:
        values = tuple(metadata.vector_length for metadata in matches)
        code_detail = "conflicting" if len(set(values)) > 1 else "duplicate"
        diagnostic = (
            _array_body_diagnostics._array_initialization_vector_length_metadata_conflict_diagnostic
            if code_detail == "conflicting"
            else _array_body_diagnostics._array_initialization_vector_length_metadata_duplicate_diagnostic
        )
        return Result.failure(
            (
                diagnostic(
                    "array-initialization vector-length metadata requires "
                    f"exactly one entry for {lookup_key!r}; found "
                    f"{code_detail} entries",
                    matches[0].source_location or location,
                ),
            )
        )
    return Result.ok(matches[0])


def _validate_array_initialization_vector_alignment_resolution_provenance(
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    base_resolution = vector_length_resolution.source_base_type_resolution
    if vector_length_resolution.source_vector_length_request not in (
        base_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution source request must come from its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if vector_length_resolution.source_location != base_resolution.source_location:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution source location must match its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if (
        vector_length_resolution.candidate_id != base_resolution.candidate_id
        or vector_length_resolution.selected_type_tag
        != base_resolution.selected_type_tag
        or vector_length_resolution.originating_branch_chain_id
        != base_resolution.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution provenance must match its M68 "
                "base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if (
        vector_length_resolution.slot_label != base_resolution.slot_label
        or vector_length_resolution.slot_ordinal != base_resolution.slot_ordinal
        or vector_length_resolution.variable_token != base_resolution.variable_token
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution slot provenance must match its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    for request in vector_length_resolution.unresolved_requests:
        if request.source_form != base_resolution.source_request_ir.source_form:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != base_resolution.source_request_ir.source_envelope:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != vector_length_resolution.candidate_id
            or request.selected_type_tag
            != vector_length_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != vector_length_resolution.originating_branch_chain_id
            or request.slot_label != vector_length_resolution.slot_label
            or request.slot_ordinal != vector_length_resolution.slot_ordinal
            or request.variable_token != vector_length_resolution.variable_token
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record provenance must match the "
                    "source vector-length resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_vector_alignment_request_record(
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_VECTOR_ALIGNMENT_REQUEST_RULE
    vector_alignment_records = tuple(
        request
        for request in vector_length_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not vector_alignment_records:
        ordinal_or_kind_records = tuple(
            request
            for request in vector_length_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_body_diagnostics._array_initialization_vector_alignment_mismatch_diagnostic(
                        "array-initialization vector-alignment request "
                        "resolution expected the M67 vector-alignment request "
                        f"to carry ordinal {rule.request_ordinal}, kind "
                        f"{rule.request_kind!r}, and leaf kind "
                        f"{rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_missing_request_diagnostic(
                "array-initialization vector-alignment request resolution "
                "requires one M67 vector-alignment request record preserved by "
                "M70",
                vector_length_resolution.source_location,
            )
        )
        return None
    if len(vector_alignment_records) > 1:
        for request in vector_alignment_records:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_vector_alignment_duplicate_request_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires exactly one M67 vector-alignment request record; "
                    f"duplicate record appeared at ordinal "
                    f"{request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    vector_alignment_request = vector_alignment_records[0]
    if (
        vector_alignment_request.request_ordinal != rule.request_ordinal
        or vector_alignment_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_mismatch_diagnostic(
                "array-initialization vector-alignment request resolution "
                f"expected ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{vector_alignment_request.request_ordinal} and kind "
                f"{vector_alignment_request.request_kind!r}",
                vector_alignment_request.leaf_source_location,
            )
        )
    if vector_alignment_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_vector_alignment_unsupported_request_diagnostic(
                "array-initialization vector-alignment request resolution "
                "preserves the M67 leaf source text only as provenance and "
                "accepts only the exact M67 vector-alignment leaf text for "
                f"that typed request; got "
                f"{vector_alignment_request.leaf_source_text!r}",
                vector_alignment_request.leaf_source_location,
            )
        )
    return vector_alignment_request


def _array_initialization_vector_alignment_metadata_for_context(
    context: _ArrayInitializationVectorAlignmentMetadataContext,
    *,
    candidate_id: str,
    target_extension: str,
    source_extension: str,
    selected_type_tag: str,
    location: SourceLocation | None,
) -> Result[ExactArrayInitializationVectorAlignmentMetadata]:
    lookup_key = (
        candidate_id,
        target_extension,
        source_extension,
        selected_type_tag,
    )
    matches = tuple(
        metadata
        for metadata in context.array_initialization_vector_alignment_metadata
        if metadata.lookup_key == lookup_key
    )
    if not matches:
        return Result.failure(
            (
                _array_body_diagnostics._array_initialization_vector_alignment_metadata_missing_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires explicit typed vector-alignment metadata for "
                    f"candidate {candidate_id!r}, target extension "
                    f"{target_extension!r}, source extension "
                    f"{source_extension!r}, and selected type tag "
                    f"{selected_type_tag!r}",
                    location,
                ),
            )
        )
    if len(matches) > 1:
        values = tuple(metadata.vector_alignment for metadata in matches)
        code_detail = "conflicting" if len(set(values)) > 1 else "duplicate"
        diagnostic = (
            _array_body_diagnostics._array_initialization_vector_alignment_metadata_conflict_diagnostic
            if code_detail == "conflicting"
            else _array_body_diagnostics._array_initialization_vector_alignment_metadata_duplicate_diagnostic
        )
        return Result.failure(
            (
                diagnostic(
                    "array-initialization vector-alignment metadata requires "
                    f"exactly one entry for {lookup_key!r}; found "
                    f"{code_detail} entries",
                    matches[0].source_location or location,
                ),
            )
        )
    return Result.ok(matches[0])


def _validate_array_initialization_helper_set_completion_provenance(
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    vector_length_resolution = (
        vector_alignment_resolution.source_vector_length_resolution
    )
    if vector_alignment_resolution.source_vector_alignment_request not in (
        vector_length_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution source request must come "
                "from its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if vector_alignment_resolution.source_location != (
        vector_length_resolution.source_location
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution source location must match "
                "its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if (
        vector_alignment_resolution.candidate_id
        != vector_length_resolution.candidate_id
        or vector_alignment_resolution.target_extension
        != vector_length_resolution.target_extension
        or vector_alignment_resolution.source_extension
        != vector_length_resolution.source_extension
        or vector_alignment_resolution.selected_type_tag
        != vector_length_resolution.selected_type_tag
        or vector_alignment_resolution.originating_branch_chain_id
        != vector_length_resolution.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution provenance must match its "
                "M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if (
        vector_alignment_resolution.slot_label
        != vector_length_resolution.slot_label
        or vector_alignment_resolution.slot_ordinal
        != vector_length_resolution.slot_ordinal
        or vector_alignment_resolution.variable_token
        != vector_length_resolution.variable_token
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution slot provenance must match "
                "its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    for request in vector_alignment_resolution.unresolved_requests:
        if request.source_form != (
            vector_length_resolution.source_base_type_resolution
            .source_request_ir.source_form
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != (
            vector_length_resolution.source_base_type_resolution
            .source_request_ir.source_envelope
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != vector_alignment_resolution.candidate_id
            or request.selected_type_tag
            != vector_alignment_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != vector_alignment_resolution.originating_branch_chain_id
            or request.slot_label != vector_alignment_resolution.slot_label
            or request.slot_ordinal != vector_alignment_resolution.slot_ordinal
            or request.variable_token != vector_alignment_resolution.variable_token
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record provenance must match the "
                    "source vector-alignment resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_backend_uninit_request_record(
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _array_body_shapes._EXACT_ARRAY_INITIALIZATION_BACKEND_UNINIT_REQUEST_RULE
    backend_uninit_records = tuple(
        request
        for request in vector_alignment_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not backend_uninit_records:
        ordinal_or_kind_records = tuple(
            request
            for request in vector_alignment_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_body_diagnostics._array_initialization_helper_set_mismatch_diagnostic(
                        "array-initialization helper-set completion expected "
                        "the M67 backend-uninit request to carry ordinal "
                        f"{rule.request_ordinal}, kind {rule.request_kind!r}, "
                        f"and leaf kind {rule.helper_leaf_kind!r}; got "
                        f"ordinal {request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_missing_request_diagnostic(
                "array-initialization helper-set completion requires one M67 "
                "backend-uninit request record preserved by M71",
                vector_alignment_resolution.source_location,
            )
        )
        return None
    if len(backend_uninit_records) > 1:
        for request in backend_uninit_records:
            diagnostics.append(
                _array_body_diagnostics._array_initialization_helper_set_duplicate_request_diagnostic(
                    "array-initialization helper-set completion requires "
                    "exactly one M67 backend-uninit request record; duplicate "
                    f"record appeared at ordinal {request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    backend_uninit_request = backend_uninit_records[0]
    if (
        backend_uninit_request.request_ordinal != rule.request_ordinal
        or backend_uninit_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_mismatch_diagnostic(
                "array-initialization helper-set completion expected ordinal "
                f"{rule.request_ordinal} and kind {rule.request_kind!r}; got "
                f"ordinal {backend_uninit_request.request_ordinal} and kind "
                f"{backend_uninit_request.request_kind!r}",
                backend_uninit_request.leaf_source_location,
            )
        )
    if backend_uninit_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_helper_set_unsupported_request_diagnostic(
                "array-initialization helper-set completion preserves the M67 "
                "backend-uninit leaf source text only as provenance and "
                "accepts only the exact M67 backend-uninit leaf text for that "
                f"typed request; got {backend_uninit_request.leaf_source_text!r}",
                backend_uninit_request.leaf_source_location,
            )
        )
    return backend_uninit_request


def _validate_array_initialization_declaration_shell(
    completion: ExactArrayInitializationHelperSetCompletionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    vector_alignment_resolution = completion.source_vector_alignment_resolution
    vector_length_resolution = completion.source_vector_length_resolution
    base_type_resolution = completion.source_base_type_resolution
    helper_request_ir = base_type_resolution.source_request_ir
    source_form = helper_request_ir.source_form
    source_envelope = helper_request_ir.source_envelope
    backend_uninit = completion.unresolved_backend_uninit

    if vector_length_resolution is not (
        vector_alignment_resolution.source_vector_length_resolution
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion must carry the M70 vector-length "
                "resolution accepted by its M71 vector-alignment resolution",
                completion.source_location,
            )
        )
    if base_type_resolution is not vector_length_resolution.source_base_type_resolution:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion must carry the M68 base-type "
                "resolution accepted by its M70 vector-length resolution",
                completion.source_location,
            )
        )
    if (
        completion.source_backend_uninit_request
        not in vector_alignment_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion backend-uninit request must come "
                "from the M71 unresolved request records",
                completion.source_location,
            )
        )
    if (
        backend_uninit.source_backend_uninit_request
        is not completion.source_backend_uninit_request
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 deferred backend-uninit boundary must reference the "
                "selected M67 backend-uninit request",
                completion.source_location,
            )
        )
    if backend_uninit.policy != "deferred_backend_value":
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_backend_policy_mismatch_diagnostic(
                "array-initialization declaration-shell lowering preserves "
                "only the M72 deferred_backend_value backend-uninit policy; "
                f"got {backend_uninit.policy!r}",
                backend_uninit.source_location,
            )
        )

    if source_form.source_envelope is not source_envelope:
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M67 helper-request IR source envelope must be the M65 "
                "envelope carried by its M66 slot form",
                source_form.source_location,
            )
        )
    if (
        source_envelope.candidate_id != completion.candidate_id
        or source_envelope.selected_type_tag != completion.selected_type_tag
        or source_envelope.originating_branch_chain_id
        != completion.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M65 envelope provenance must match the M72 helper-set "
                "completion candidate id, selected type tag, and branch-chain "
                "identity",
                source_envelope.source_location,
            )
        )
    for stage_name, source in (
        ("M66 slot form", source_form),
        ("M68 base-type resolution", base_type_resolution),
        ("M70 vector-length resolution", vector_length_resolution),
        ("M71 vector-alignment resolution", vector_alignment_resolution),
        ("M72 backend-uninit boundary", backend_uninit),
    ):
        if (
            source.candidate_id != completion.candidate_id
            or source.selected_type_tag != completion.selected_type_tag
            or source.originating_branch_chain_id
            != completion.originating_branch_chain_id
            or source.slot_label != completion.slot_label
            or source.slot_ordinal != completion.slot_ordinal
            or source.variable_token != completion.variable_token
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    f"{stage_name} provenance must match the M72 helper-set "
                    "completion",
                    source.source_location,
                )
            )
    for stage_name, source in (
        ("M70 vector-length resolution", vector_length_resolution),
        ("M71 vector-alignment resolution", vector_alignment_resolution),
        ("M72 backend-uninit boundary", backend_uninit),
    ):
        if (
            source.target_extension != completion.target_extension
            or source.source_extension != completion.source_extension
        ):
            diagnostics.append(
                _array_body_diagnostics._array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    f"{stage_name} target/source extension provenance must "
                    "match the M72 helper-set completion",
                    source.source_location,
                )
            )

    if (
        completion.slot_label != "opaque_pre_branch_array_initialization"
        or completion.slot_ordinal != 0
        or completion.variable_token != "tmp"
        or source_form.slot_label != "opaque_pre_branch_array_initialization"
        or source_form.slot_ordinal != 0
        or source_form.variable_token != "tmp"
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering supports "
                "only the exact first-slot "
                "opaque_pre_branch_array_initialization var<typed>(..., tmp, "
                "...) shell",
                source_form.variable_token_location or source_form.source_location,
            )
        )
    expected_leaf_kinds = (
        source_form.base_type_leaf.kind,
        source_form.vector_length_leaf.kind,
        source_form.vector_alignment_leaf.kind,
        source_form.backend_uninit_leaf.kind,
    )
    if expected_leaf_kinds != (
        "type_generation_base_in",
        "value_generation_vector_length",
        "value_generation_vector_alignment",
        "value_backend_uninit_array",
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "exact M66 helper-leaf shape for base type, vector length, "
                "vector alignment, and deferred backend uninit",
                source_form.source_location,
            )
        )
    if (
        base_type_resolution.resolved_type_ref.kind != "base.in"
        or base_type_resolution.resolved_type_ref.type_tag
        != completion.selected_type_tag
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted M68 base.in type fact for the selected type tag",
                base_type_resolution.source_location,
            )
        )
    if not isinstance(
        vector_length_resolution.resolved_vector_length,
        ExactArrayInitializationVectorLengthValue,
    ):
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted typed M70 vector-length fact",
                vector_length_resolution.source_location,
            )
        )
    if not isinstance(
        vector_alignment_resolution.resolved_vector_alignment,
        ExactArrayInitializationVectorAlignmentValue,
    ) or vector_alignment_resolution.resolved_vector_alignment.kind == "unsupported":
        diagnostics.append(
            _array_body_diagnostics._array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted typed M71 vector-alignment fact",
                vector_alignment_resolution.source_location,
            )
        )
    return diagnostics


def _validate_array_body_structural_sequence_inputs(
    envelope: ExactArrayBodyEnvelopeIr,
    shell: ExactArrayInitializationDeclarationShellIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    if not isinstance(envelope, ExactArrayBodyEnvelopeIr):
        diagnostics.append(
            _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M65 ExactArrayBodyEnvelopeIr source",
                None,
            )
        )
        return diagnostics
    if not isinstance(shell, ExactArrayInitializationDeclarationShellIr):
        diagnostics.append(
            _array_body_diagnostics._array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M73 ExactArrayInitializationDeclarationShellIr source",
                None,
            )
        )
        return diagnostics

    if not _exact_array_body_envelope_shape_is_supported(envelope):
        labels = tuple(slot.label for slot in envelope.slots)
        ordinals = tuple(slot.ordinal for slot in envelope.slots)
        if len(envelope.slots) == len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_role_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the accepted M65 five-slot source order "
                    f"{_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got labels "
                    f"{labels!r} and ordinals {ordinals!r}",
                    envelope.source_location,
                )
            )
        else:
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_malformed_diagnostic(
                    "array-body structural sequence classification requires "
                    f"exactly five accepted M65 slots; got {len(envelope.slots)}",
                    envelope.source_location,
                )
            )

    if (
        envelope.candidate_id != shell.candidate_id
        or envelope.selected_type_tag != shell.selected_type_tag
        or envelope.originating_branch_chain_id != shell.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._array_body_structural_sequence_context_mismatch_diagnostic(
                "array-body structural sequence classification requires M65 "
                "envelope and M73 declaration shell candidate id, selected "
                "type tag, and branch-chain identity to match",
                shell.source_location,
            )
        )

    if shell.source_envelope is not envelope:
        diagnostics.append(
            _array_body_diagnostics._array_body_structural_sequence_provenance_mismatch_diagnostic(
                "M73 declaration shell must reference the same accepted M65 "
                "array-body envelope supplied to structural sequence "
                "classification",
                shell.source_location,
            )
        )
    if (
        shell.slot_label != "opaque_pre_branch_array_initialization"
        or shell.slot_ordinal != 0
    ):
        diagnostics.append(
            _array_body_diagnostics._array_body_structural_sequence_malformed_diagnostic(
                "array-body structural sequence classification attaches the "
                "M73 declaration shell only to the first M65 slot at ordinal 0",
                shell.source_location,
            )
        )
    if len(envelope.slots) >= 3:
        selected_slot = envelope.slots[2]
        if not isinstance(selected_slot, ExactArrayBodyEnvelopeSelectedSlot):
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_role_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the selected-body envelope role at slot ordinal 2",
                    getattr(selected_slot, "source_location", envelope.source_location),
                )
            )
        elif (
            selected_slot.selected_body_envelope.candidate_id != envelope.candidate_id
            or selected_slot.selected_body_envelope.selected_type_tag
            != envelope.selected_type_tag
            or selected_slot.selected_body_envelope.originating_branch_chain_id
            != envelope.originating_branch_chain_id
        ):
            diagnostics.append(
                _array_body_diagnostics._array_body_structural_sequence_provenance_mismatch_diagnostic(
                    "M65 selected-body slot must preserve the accepted M63 "
                    "selected/no-body envelope provenance",
                    selected_slot.source_location,
                )
            )
    return diagnostics


def _validate_predicate_path_structural_request_input(
    sequence: ExactArrayBodyStructuralSequenceIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(sequence, ExactArrayBodyStructuralSequenceIr):
        return [
            _array_body_diagnostics._predicate_path_source_unsupported_diagnostic(
                "predicate-path structural request lowering requires an "
                "accepted M74 ExactArrayBodyStructuralSequenceIr source",
                None,
            )
        ]
    if tuple(role.role_label for role in sequence.roles) != (
        _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS
    ) or tuple(role.role_ordinal for role in sequence.roles) != (
        _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS
    ):
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request lowering requires the "
                "accepted M74 five-role source order",
                sequence.source_location,
            )
        )
        return diagnostics

    envelope = sequence.source_envelope
    if tuple(role.envelope_slot for role in sequence.roles) != envelope.slots:
        diagnostics.append(
            _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                "M75 predicate-path roles must preserve the M74 source slot "
                "identity and order",
                sequence.source_location,
            )
        )
    for role in sequence.roles:
        if (
            role.candidate_id != sequence.candidate_id
            or role.selected_type_tag != sequence.selected_type_tag
            or role.originating_branch_chain_id
            != sequence.originating_branch_chain_id
            or role.target_extension != sequence.target_extension
            or role.source_extension != sequence.source_extension
        ):
            diagnostics.append(
                _array_body_diagnostics._predicate_path_context_mismatch_diagnostic(
                    "predicate-path structural request roles must match the "
                    "M74 sequence candidate, extension, selected type, and "
                    "branch-chain context",
                    role.source_location,
                )
            )

    init_role = sequence.roles[1]
    selected_role = sequence.roles[2]
    store_role = sequence.roles[3]
    if (
        init_role.role_label != "opaque_predicate_init_shaped_slot"
        or init_role.role_ordinal != 1
        or not isinstance(init_role.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        or init_role.opaque_source_text != init_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "1 to be the opaque predicate-init-shaped slot",
                init_role.source_location,
            )
        )
    if (
        selected_role.role_label != "selected_body_envelope_slot"
        or selected_role.role_ordinal != 2
        or not (
            _selected_body_models.is_selected_body_envelope_ir(
                selected_role.selected_body_envelope,
            )
            or _selected_body_models.is_no_selected_body_envelope_ir(
                selected_role.selected_body_envelope,
            )
        )
        or selected_role.selected_body_envelope
        is not envelope.selected_body_slot.selected_body_envelope
    ):
        diagnostics.append(
            _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "2 to preserve the accepted M63 selected/no-body envelope",
                selected_role.source_location,
            )
        )
    if (
        store_role.role_label != "opaque_post_branch_store_call_shaped_slot"
        or store_role.role_ordinal != 3
        or not isinstance(store_role.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        or store_role.opaque_source_text != store_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "3 to be the opaque post-branch store-call-shaped slot",
                store_role.source_location,
            )
        )

    if diagnostics:
        return diagnostics

    assert init_role.opaque_source_text is not None
    assert store_role.opaque_source_text is not None
    init_match = _exact_shapes.EXACT_PREDICATE_INIT_SLOT_RE.match(init_role.opaque_source_text)
    if init_match is None:
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request requires exact predicate-init "
                "shape 'svbool_t pg = intrin<svptrue_b8>();'",
                init_role.source_location,
            )
        )
    store_match = _exact_shapes.EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE.match(
        store_role.opaque_source_text,
    )
    if store_match is None:
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request requires exact post-branch "
                "store-call predicate-token shape",
                store_role.source_location,
            )
        )

    if init_match is None or store_match is None:
        return diagnostics

    predicate_type = init_match.group("predicate_type")
    predicate_token = init_match.group("predicate_token")
    init_direct_token = init_match.group("direct_intrinsic_token")
    store_call_token = store_match.group("call_token")
    store_predicate_token = store_match.group("predicate_token")
    if (
        predicate_type != _exact_shapes.EXACT_PREDICATE_INIT_TYPE_TOKEN
        or predicate_token != _exact_shapes.EXACT_PREDICATE_TOKEN
        or init_direct_token
        != _exact_shapes.EXACT_PREDICATE_INIT_DIRECT_INTRINSIC_TOKEN
        or store_call_token != _exact_shapes.EXACT_POST_BRANCH_INTRINSIC_TOKEN
    ):
        diagnostics.append(
            _array_body_diagnostics._predicate_path_malformed_diagnostic(
                "predicate-path structural request requires the exact M75 "
                "predicate-init and store-call structural tokens",
                init_role.source_location,
            )
        )
    if store_predicate_token != predicate_token:
        diagnostics.append(
            _array_body_diagnostics._predicate_path_token_mismatch_diagnostic(
                "predicate-path structural request requires the slot-3 predicate "
                "argument token to match the slot-1 predicate token",
                store_role.source_location,
            )
        )

    selected_body_envelope = selected_role.selected_body_envelope
    if isinstance(
        selected_body_envelope,
        _selected_body_models.SelectedBodyEnvelopeIr,
    ):
        selected_envelope = selected_body_envelope
        if len(selected_envelope.entries) != 1:
            diagnostics.append(
                _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires the accepted "
                    "M63 selected-body envelope to carry exactly one M62 entry",
                    selected_envelope.source_location,
                )
            )
            return diagnostics
        entry = selected_envelope.entries[0]
        if (
            entry.candidate_id != selected_envelope.candidate_id
            or entry.selected_type_tag != selected_envelope.selected_type_tag
            or entry.originating_branch_chain_id
            != selected_envelope.originating_branch_chain_id
            or entry.source_location != selected_envelope.source_location
            or entry.source_body_ir.candidate_id != entry.candidate_id
            or entry.source_body_ir.selected_type_tag != entry.selected_type_tag
            or entry.source_body_ir.originating_branch_chain_id
            != entry.originating_branch_chain_id
            or entry.source_body_ir.source_location != entry.source_location
            or entry.source_body_ir.direct_intrinsic_token_text
            != entry.direct_intrinsic_token_text
        ):
            diagnostics.append(
                _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires M63 selected-body "
                    "envelope and M62 direct-intrinsic body IR provenance to match",
                    entry.source_location,
                )
            )
        if entry.assignment_target_text != predicate_token:
            diagnostics.append(
                _array_body_diagnostics._predicate_path_token_mismatch_diagnostic(
                    "predicate-path structural request requires the selected-body "
                    "assignment target token to match the slot-1 predicate token",
                    entry.source_location,
                )
            )
    elif isinstance(
        selected_body_envelope,
        _selected_body_models.NoSelectedBodyEnvelopeIr,
    ):
        no_selected_envelope = selected_body_envelope
        if (
            no_selected_envelope.entries
            or no_selected_envelope.source_body_ir.candidate_id
            != no_selected_envelope.candidate_id
            or no_selected_envelope.source_body_ir.selected_type_tag
            != no_selected_envelope.selected_type_tag
            or no_selected_envelope.source_body_ir.originating_branch_chain_id
            != no_selected_envelope.originating_branch_chain_id
            or no_selected_envelope.source_body_ir.source_location
            != no_selected_envelope.source_location
        ):
            diagnostics.append(
                _array_body_diagnostics._predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires accepted "
                    "no-selected-body envelope provenance to match its M62 "
                    "no-body IR",
                    no_selected_envelope.source_location,
                )
            )

    return diagnostics


def _validate_post_branch_intrinsic_call_site_input(
    predicate_path: ExactPredicatePathStructuralRequestIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(predicate_path, ExactPredicatePathStructuralRequestIr):
        return [
            _array_body_diagnostics._post_branch_call_site_source_unsupported_diagnostic(
                "post-branch intrinsic call-site structural request lowering "
                "requires an accepted M75 ExactPredicatePathStructuralRequestIr "
                "source",
                None,
            )
        ]

    sequence = predicate_path.source_sequence
    if not isinstance(sequence, ExactArrayBodyStructuralSequenceIr):
        return [
            _array_body_diagnostics._post_branch_call_site_sequence_missing_diagnostic(
                "post-branch intrinsic call-site structural request lowering "
                "requires M74 structural sequence provenance carried by M75",
                predicate_path.store_call_source_location,
            )
        ]
    if not isinstance(
        sequence.declaration_shell,
        ExactArrayInitializationDeclarationShellIr,
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_sequence_missing_diagnostic(
                "post-branch intrinsic call-site structural request lowering "
                "requires M73 declaration-shell provenance carried through M74/M75",
                sequence.source_location,
            )
        )
    if (
        predicate_path.candidate_id != sequence.candidate_id
        or predicate_path.target_extension != sequence.target_extension
        or predicate_path.source_extension != sequence.source_extension
        or predicate_path.selected_type_tag != sequence.selected_type_tag
        or predicate_path.originating_branch_chain_id
        != sequence.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_context_mismatch_diagnostic(
                "post-branch intrinsic call-site structural request requires M75 "
                "candidate, extension, selected type, and branch-chain context "
                "to match the carried M74 sequence",
                predicate_path.source_location,
            )
        )
    if len(sequence.roles) <= 3:
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_sequence_missing_diagnostic(
                "post-branch intrinsic call-site structural request requires "
                "M74 role ordinal 3 provenance",
                sequence.source_location,
            )
        )
        return diagnostics

    post_branch_role = sequence.roles[3]
    if (
        predicate_path.store_call_role_label
        != "opaque_post_branch_store_call_shaped_slot"
        or predicate_path.store_call_slot_ordinal != 3
        or predicate_path.store_call_source_location is None
        or not predicate_path.store_call_predicate_argument_text
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_provenance_mismatch_diagnostic(
                "post-branch intrinsic call-site request requires the accepted "
                "M75 slot-3 predicate-token use",
                predicate_path.source_location,
            )
        )
    if (
        post_branch_role.role_label != "opaque_post_branch_store_call_shaped_slot"
        or post_branch_role.role_ordinal != 3
        or not isinstance(
            post_branch_role.envelope_slot,
            ExactArrayBodyEnvelopeOpaqueSlot,
        )
        or post_branch_role.opaque_source_text
        != post_branch_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_provenance_mismatch_diagnostic(
                "post-branch intrinsic call-site request requires M74 role "
                "ordinal 3 to preserve the accepted opaque post-branch "
                "call-site slot",
                post_branch_role.source_location,
            )
        )
    if (
        post_branch_role.source_location
        != predicate_path.store_call_source_location
        or post_branch_role.role_ordinal != predicate_path.store_call_slot_ordinal
        or post_branch_role.role_label != predicate_path.store_call_role_label
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_provenance_mismatch_diagnostic(
                "post-branch intrinsic call-site slot identity must match the "
                "M75 store-call predicate-token use",
                post_branch_role.source_location,
            )
        )
    if diagnostics:
        return diagnostics

    source_text = post_branch_role.opaque_source_text
    if source_text is None:
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_malformed_diagnostic(
                "post-branch intrinsic call-site structural request requires "
                "the accepted M74 opaque source text",
                post_branch_role.source_location,
            )
        )
        return diagnostics

    match = _exact_shapes.POST_BRANCH_INTRINSIC_CALL_SITE_CONTAINER_RE.match(
        source_text,
    )
    if match is None:
        stripped = source_text.strip()
        if stripped and not stripped.startswith(
            _exact_shapes.EXACT_POST_BRANCH_CALL_HEAD_TOKEN,
        ):
            diagnostics.append(
                _array_body_diagnostics._post_branch_call_site_shape_unsupported_diagnostic(
                    "post-branch intrinsic call-site structural request supports "
                    "only the exact intrin<...>(...) call-site shape",
                    post_branch_role.source_location,
                )
            )
        else:
            diagnostics.append(
                _array_body_diagnostics._post_branch_call_site_malformed_diagnostic(
                    "post-branch intrinsic call-site structural request requires "
                    "an exact call-site shaped as "
                    "'intrin<svst1>(pg, tmp.data(), a);'",
                    post_branch_role.source_location,
                )
            )
        return diagnostics

    call_head_token = match.group("call_head")
    intrinsic_token = match.group("intrinsic_token")
    arguments = tuple(part.strip() for part in match.group("arguments").split(","))
    if call_head_token != _exact_shapes.EXACT_POST_BRANCH_CALL_HEAD_TOKEN:
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_call_head_mismatch_diagnostic(
                "post-branch intrinsic call-site structural request requires "
                "the exact structural call-head token intrin",
                post_branch_role.source_location,
            )
        )
    if intrinsic_token != _exact_shapes.EXACT_POST_BRANCH_INTRINSIC_TOKEN:
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_intrinsic_token_mismatch_diagnostic(
                "post-branch intrinsic call-site structural request records "
                "only the exact unresolved intrinsic token svst1",
                post_branch_role.source_location,
            )
        )
    if len(arguments) != 3:
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_argument_count_mismatch_diagnostic(
                "post-branch intrinsic call-site structural request requires "
                "exactly three structural arguments",
                post_branch_role.source_location,
            )
        )
        return diagnostics

    predicate_argument = arguments[0]
    if (
        predicate_argument
        != predicate_path.store_call_predicate_argument_text
        or predicate_argument
        != _exact_shapes.EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE.target_text
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_predicate_argument_mismatch_diagnostic(
                "post-branch intrinsic call-site predicate argument must link "
                "to the accepted M75 slot-3 predicate-token use",
                post_branch_role.source_location,
            )
        )

    member_access_argument = arguments[1]
    member_match = _exact_shapes.POST_BRANCH_MEMBER_ACCESS_ARGUMENT_RE.match(
        member_access_argument,
    )
    if (
        member_match is None
        or member_access_argument
        != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_TEXT
        or member_match.group("base_token")
        != sequence.declaration_shell.variable_token
        or member_match.group("base_token")
        != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_BASE_TOKEN
        or member_match.group("member_token")
        != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_MEMBER_TOKEN
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_member_access_unsupported_diagnostic(
                "post-branch intrinsic call-site structural request supports "
                "only the exact structural member-access-shaped token/path "
                "tmp.data() linked to M73/M74/M75 tmp provenance",
                post_branch_role.source_location,
            )
        )

    source_operand_argument = arguments[2]
    if (
        source_operand_argument
        != _exact_shapes.EXACT_POST_BRANCH_SOURCE_OPERAND_TOKEN
    ):
        diagnostics.append(
            _array_body_diagnostics._post_branch_call_site_source_operand_unsupported_diagnostic(
                "post-branch intrinsic call-site structural request records "
                "only the exact structural source operand token a",
                post_branch_role.source_location,
            )
        )

    return diagnostics


def _validate_return_emission_structural_request_input(
    post_branch_call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(
        post_branch_call_site,
        ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ):
        return (
            _array_body_diagnostics._return_emission_source_unsupported_diagnostic(
                "return-emission structural request lowering requires an "
                "accepted M76 "
                "ExactPostBranchIntrinsicCallSiteStructuralRequestIr source",
                None,
            ),
        )

    sequence = post_branch_call_site.source_sequence
    if not isinstance(sequence, ExactArrayBodyStructuralSequenceIr):
        return (
            _array_body_diagnostics._return_emission_slot_missing_diagnostic(
                "return-emission structural request lowering requires M74 "
                "structural sequence provenance carried by M76",
                post_branch_call_site.source_location,
            ),
        )
    if post_branch_call_site.source_sequence is not (
        post_branch_call_site.source_predicate_path.source_sequence
    ):
        diagnostics.append(
            _array_body_diagnostics._return_emission_provenance_mismatch_diagnostic(
                "return-emission structural request requires the M76 call-site "
                "request to preserve the M74 sequence carried by M75",
                post_branch_call_site.source_location,
            )
        )
    if (
        post_branch_call_site.candidate_id != sequence.candidate_id
        or post_branch_call_site.target_extension != sequence.target_extension
        or post_branch_call_site.source_extension != sequence.source_extension
        or post_branch_call_site.selected_type_tag != sequence.selected_type_tag
        or post_branch_call_site.originating_branch_chain_id
        != sequence.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_diagnostics._return_emission_context_mismatch_diagnostic(
                "return-emission structural request requires M76 candidate, "
                "extension, selected type, and branch-chain context to match "
                "the carried M74 sequence",
                post_branch_call_site.source_location,
            )
        )
    if len(sequence.roles) <= 4:
        diagnostics.append(
            _array_body_diagnostics._return_emission_slot_missing_diagnostic(
                "return-emission structural request requires the accepted M74 "
                "opaque_return_emission_shaped_slot at role ordinal 4",
                sequence.source_location,
            )
        )
        return tuple(diagnostics)

    return_role = sequence.roles[4]
    if (
        return_role.role_label != "opaque_return_emission_shaped_slot"
        or return_role.role_ordinal != 4
        or not isinstance(return_role.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        or return_role.opaque_source_text
        != return_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _array_body_diagnostics._return_emission_provenance_mismatch_diagnostic(
                "return-emission structural request requires M74 role ordinal "
                "4 to preserve the accepted opaque return-emission slot",
                return_role.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)

    source_text = return_role.opaque_source_text
    if source_text is None:
        return (
            _array_body_diagnostics._return_emission_malformed_diagnostic(
                "return-emission structural request requires the accepted M74 "
                "opaque source text",
                return_role.source_location,
            ),
        )

    match = _exact_shapes.EXACT_RETURN_EMISSION_SLOT_RE.match(source_text)
    if match is None:
        return (
            _array_body_diagnostics._return_emission_malformed_diagnostic(
                "return-emission structural request recognizes only the exact "
                "trailing shape 'emit_return(tmp);' with insignificant whitespace",
                return_role.source_location,
            ),
        )

    returned_token = match.group("returned_token")
    declaration_token = sequence.declaration_shell.variable_token
    if returned_token != declaration_token:
        return (
            _array_body_diagnostics._return_emission_returned_token_mismatch_diagnostic(
                "return-emission returned token must match the accepted M73 "
                "declaration-shell variable token",
                return_role.source_location,
            ),
        )
    return ()


def _exact_array_body_envelope_shape_is_supported(
    envelope: ExactArrayBodyEnvelopeIr,
) -> bool:
    return (
        tuple(slot.label for slot in envelope.slots)
        == _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS
        and tuple(slot.ordinal for slot in envelope.slots)
        == _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS
    )


def _structural_role_from_slot(
    role_label: ExactArrayBodyStructuralRoleLabel,
    slot: ExactArrayBodyEnvelopeSlot,
    shell: ExactArrayInitializationDeclarationShellIr,
    *,
    target_extension: str,
    source_extension: str,
) -> _ExactArrayBodyStructuralRole:
    declaration_shell: ExactArrayInitializationDeclarationShellIr | None = None
    selected_body_envelope: (
        _array_body_models.GenerationSelectedBodyEnvelopeIr | None
    ) = None
    opaque_source_text: str | None = None

    if role_label == "first_slot_declaration_shell":
        declaration_shell = shell
    elif role_label == "selected_body_envelope_slot":
        if not isinstance(slot, ExactArrayBodyEnvelopeSelectedSlot):
            raise ValueError(
                "selected-body role must be backed by the M65 selected-body slot"
            )
        selected_body_envelope = slot.selected_body_envelope
    else:
        if not isinstance(slot, ExactArrayBodyEnvelopeOpaqueSlot):
            raise ValueError("opaque structural role must be backed by an opaque slot")
        opaque_source_text = slot.opaque_source_text

    return _ExactArrayBodyStructuralRole(
        role_label=role_label,
        role_ordinal=slot.ordinal,
        envelope_slot=slot,
        source_location=slot.source_location,
        candidate_id=slot.candidate_id,
        target_extension=target_extension,
        source_extension=source_extension,
        selected_type_tag=slot.selected_type_tag,
        originating_branch_chain_id=slot.originating_branch_chain_id,
        declaration_shell=declaration_shell,
        selected_body_envelope=selected_body_envelope,
        opaque_source_text=opaque_source_text,
    )


def _array_initialization_leaf(
    kind: ExactArrayInitializationHelperLeafKind,
    slot_location: SourceLocation,
    match: re.Match[str],
    group_name: str,
) -> ExactArrayInitializationUnresolvedLeaf:
    return ExactArrayInitializationUnresolvedLeaf(
        kind=kind,
        source_text=match.group(group_name),
        source_location=_source_span_for_match_group(
            slot_location,
            match,
            group_name,
        ),
    )


def _source_span_for_match_group(
    source_location: SourceLocation,
    match: re.Match[str],
    group_name: str,
) -> SourceLocation:
    start = match.start(group_name)
    end = match.end(group_name)
    return SourceLocation(
        source_location.path,
        source_location.line,
        source_location.column + start,
        end_line=source_location.line,
        end_column=source_location.column + end,
    )
