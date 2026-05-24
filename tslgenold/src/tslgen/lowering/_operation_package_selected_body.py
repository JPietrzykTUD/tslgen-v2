from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._operation_package_diagnostics import (
    operation_package_context_mismatch_diagnostic,
    operation_package_malformed_diagnostic,
    operation_package_provenance_mismatch_diagnostic,
    operation_package_source_location_mismatch_diagnostic,
)
from tslgen.lowering._selected_body_models import (
    NoSelectedBodyEnvelopeIr,
    SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeEntry,
    SelectedBodyEnvelopeIr,
)


@dataclass(frozen=True, slots=True)
class SelectedBodyDirectIntrinsicOperationPackageEntryIr:
    source_envelope: SelectedBodyEnvelopeIr

    def __post_init__(self) -> None:
        if not isinstance(self.source_envelope, SelectedBodyEnvelopeIr):
            raise TypeError(
                "selected-body direct-intrinsic operation package requires an "
                "accepted M63 SelectedBodyEnvelopeIr"
            )
        diagnostics = validate_selected_body_direct_intrinsic_envelope(
            self.source_envelope,
        )
        if diagnostics:
            raise ValueError(
                "selected-body direct-intrinsic operation package requires "
                "accepted M62/M63 selected-body provenance"
            )

    @property
    def candidate_id(self) -> str:
        return self.source_envelope.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.source_envelope.source_location

    @property
    def source_body_ir(self) -> SelectedAssignmentDirectIntrinsicBodyIr:
        return self.source_envelope.entries[0].source_body_ir

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "selected_body_direct_intrinsic_operation",
            self.source_envelope.key,
        )


def is_generation_selected_body_envelope(value: object) -> bool:
    return isinstance(value, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr))


def validate_selected_body_direct_intrinsic_envelope(
    envelope: SelectedBodyEnvelopeIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(envelope, SelectedBodyEnvelopeIr):
        return (
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package requires an "
                "accepted M63 SelectedBodyEnvelopeIr",
                None,
            ),
        )

    entries = envelope.entries
    if not isinstance(entries, tuple):
        return (
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "envelope entries to be a tuple",
                envelope.source_location,
            ),
        )
    if len(entries) != 1:
        return (
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                f"exactly one M63 envelope entry; got {len(entries)}",
                envelope.source_location,
            ),
        )

    entry = entries[0]
    if not isinstance(entry, SelectedBodyEnvelopeEntry):
        return (
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "a typed M63 SelectedBodyEnvelopeEntry",
                envelope.source_location,
            ),
        )
    body_ir = entry.source_body_ir
    if not isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr):
        return (
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "the entry to preserve an accepted M62 "
                "SelectedAssignmentDirectIntrinsicBodyIr",
                envelope.source_location,
            ),
        )

    envelope_context = (
        envelope.candidate_id,
        envelope.selected_type_tag,
        envelope.originating_branch_chain_id,
    )
    entry_context = (
        entry.candidate_id,
        entry.selected_type_tag,
        entry.originating_branch_chain_id,
    )
    body_context = (
        body_ir.candidate_id,
        body_ir.selected_type_tag,
        body_ir.originating_branch_chain_id,
    )
    if entry_context != envelope_context or body_context != envelope_context:
        diagnostics.append(
            operation_package_context_mismatch_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "M63 envelope, M63 entry, and M62 body IR context to match",
                envelope.source_location,
            )
        )
    if entry.selected_literal != body_ir.selected_literal:
        diagnostics.append(
            operation_package_context_mismatch_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "the M63 entry selected literal to match the M62 body IR",
                envelope.source_location,
            )
        )
    if envelope.source_location != entry.source_location:
        diagnostics.append(
            operation_package_source_location_mismatch_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "the M63 entry source location to match its envelope",
                envelope.source_location,
            )
        )
    if entry.source_location != body_ir.source_location:
        diagnostics.append(
            operation_package_source_location_mismatch_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "the M63 entry source location to match the M62 body IR",
                entry.source_location,
            )
        )

    provenance_fields = (
        entry.original_opaque_body_text == body_ir.original_opaque_body_text,
        entry.assignment_target_text == body_ir.assignment_target_text,
        entry.opaque_rhs_text == body_ir.opaque_rhs_text,
        entry.direct_intrinsic_token_text == body_ir.direct_intrinsic_token_text,
        entry.direct_intrinsic_argument_texts
        == body_ir.direct_intrinsic_argument_texts,
    )
    if not all(provenance_fields):
        diagnostics.append(
            operation_package_provenance_mismatch_diagnostic(
                "selected-body direct-intrinsic operation package requires "
                "M63 entry provenance fields to match the M62 body IR",
                envelope.source_location,
            )
        )
    if body_ir.direct_intrinsic_argument_texts:
        diagnostics.append(
            operation_package_malformed_diagnostic(
                "selected-body direct-intrinsic operation package supports "
                "only the accepted M62 empty argument list",
                body_ir.source_location,
            )
        )
    return tuple(diagnostics)
