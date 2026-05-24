from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic
from tslgen.lowering._lowering_backend_boundary_worklist_diagnostics import (
    _worklist_conflicting_entry_diagnostic,
    _worklist_duplicate_value_diagnostic,
    _worklist_malformed_diagnostic,
    _worklist_provenance_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    Stage8BackendBoundaryWorklistEntryIr,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_result import (
    ExactArrayBackendUninitTranslationResultIr,
)
from tslgen.lowering._lowering_ir_contracts import lowering_ir_key
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_object,
)


def validate_stage8_backend_boundary_worklist_entry(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    entry: object,
) -> tuple[Diagnostic, ...]:
    if not isinstance(entry, Stage8BackendBoundaryWorklistEntryIr):
        return (
            _worklist_malformed_diagnostic(
                "Stage 8 backend-boundary worklist entries must be accepted "
                "Stage8BackendBoundaryWorklistEntryIr values",
                source_location_from_object(entry),
            ),
        )
    if entry.source_request_inventory is not inventory:
        return (_worklist_provenance_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist entries must preserve M99 "
            "request inventory object identity",
            entry.source_location,
        ),)
    if lowering_ir_key(entry) is None:
        return (_worklist_malformed_diagnostic(
            "Stage 8 backend-boundary worklist entries must expose a "
            "non-empty tuple key",
            entry.source_location,
        ),)
    if entry.source_request_record is not None and entry.source_no_request_record is not None:
        return (_worklist_conflicting_entry_diagnostic(
            "Stage 8 backend-boundary worklist entries must reference either "
            "a request record or a no-request record, not both",
            entry.source_location,
        ),)
    if entry.classification == "exact_array_backend_uninit_translated":
        return _validate_translated_entry(inventory, entry)
    if entry.classification == "exact_array_backend_uninit_unresolved":
        return _validate_unresolved_exact_entry(inventory, entry)
    if entry.classification == "selected_body_direct_intrinsic_deferred":
        return _validate_deferred_selected_entry(inventory, entry)
    if entry.classification == "no_accepted_backend_boundary_fact":
        return _validate_no_request_entry(inventory, entry)
    return (_worklist_malformed_diagnostic(
        "Stage 8 backend-boundary worklist entries support only accepted "
        "M103 classifications",
        entry.source_location,
    ),)


def _worklist_entries(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    result: ExactArrayBackendUninitTranslationResultIr | None,
) -> tuple[Stage8BackendBoundaryWorklistEntryIr, ...]:
    result_by_request = {
        id(record.source_request_record): record
        for record in (result.result_records if result else ())
    }
    deferred_by_request = {
        id(record): record
        for record in (result.deferred_request_records if result else ())
    }
    entries: list[Stage8BackendBoundaryWorklistEntryIr] = []
    for request in inventory.request_records:
        if request.kind == "exact_array_backend_value_uninit_array":
            result_record = result_by_request.get(id(request))
            entries.append(Stage8BackendBoundaryWorklistEntryIr(
                source_request_inventory=inventory,
                classification="exact_array_backend_uninit_translated"
                if result_record is not None
                else "exact_array_backend_uninit_unresolved",
                source_request_record=request,
                source_exact_array_backend_uninit_translation_result=result
                if result_record is not None
                else None,
                source_exact_array_backend_uninit_translation_record=result_record,
            ))
        elif request.kind == "selected_body_direct_intrinsic_handoff":
            entries.append(Stage8BackendBoundaryWorklistEntryIr(
                source_request_inventory=inventory,
                classification="selected_body_direct_intrinsic_deferred",
                source_request_record=request,
                source_exact_array_backend_uninit_translation_result=result
                if id(request) in deferred_by_request
                else None,
                source_deferred_request_record=deferred_by_request.get(id(request)),
            ))
        else:
            raise ValueError("worklist supports only accepted M99 request kinds")
    entries.extend(
        Stage8BackendBoundaryWorklistEntryIr(
            source_request_inventory=inventory,
            classification="no_accepted_backend_boundary_fact",
            source_no_request_record=record,
        )
        for record in inventory.no_request_records
    )
    return tuple(entries)


def _validate_translated_entry(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> tuple[Diagnostic, ...]:
    request = entry.source_request_record
    result = entry.source_exact_array_backend_uninit_translation_result
    record = entry.source_exact_array_backend_uninit_translation_record
    if request is None or request.kind != "exact_array_backend_value_uninit_array":
        return (_worklist_malformed_diagnostic(
            "translated exact-array worklist entries require an accepted M99 "
            "exact-array request record",
            entry.source_location,
        ),)
    if result is None or record is None or result.source_request_inventory is not inventory:
        return (_worklist_provenance_mismatch_diagnostic(
            "translated exact-array worklist entries must preserve M100 result "
            "to M99 inventory object identity",
            entry.source_location,
        ),)
    if record.source_request_record is not request or not any(
        record is accepted for accepted in result.result_records
    ):
        return (_worklist_provenance_mismatch_diagnostic(
            "translated exact-array worklist entries must preserve M100 result "
            "record to M99 request record object identity",
            entry.source_location,
        ),)
    if entry.source_deferred_request_record is not None or entry.source_no_request_record is not None:
        return (_worklist_malformed_diagnostic(
            "translated exact-array worklist entries must not carry deferred "
            "or no-request provenance",
            entry.source_location,
        ),)
    return ()


def _validate_unresolved_exact_entry(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> tuple[Diagnostic, ...]:
    request = entry.source_request_record
    if (
        request is None
        or request.kind != "exact_array_backend_value_uninit_array"
        or not any(request is accepted for accepted in inventory.request_records)
    ):
        return (_worklist_malformed_diagnostic(
            "unresolved exact-array worklist entries require an accepted M99 "
            "exact-array request record",
            entry.source_location,
        ),)
    if (
        entry.source_exact_array_backend_uninit_translation_result is not None
        or entry.source_exact_array_backend_uninit_translation_record is not None
        or entry.source_deferred_request_record is not None
        or entry.source_no_request_record is not None
    ):
        return (_worklist_malformed_diagnostic(
            "unresolved exact-array worklist entries must not carry M100 "
            "result, deferred, or no-request provenance",
            entry.source_location,
        ),)
    return ()


def _validate_deferred_selected_entry(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> tuple[Diagnostic, ...]:
    request = entry.source_request_record
    if (
        request is None
        or request.kind != "selected_body_direct_intrinsic_handoff"
        or not any(request is accepted for accepted in inventory.request_records)
    ):
        return (_worklist_malformed_diagnostic(
            "selected-body deferred worklist entries require an accepted M99 "
            "selected-body request record",
            entry.source_location,
        ),)
    if entry.source_deferred_request_record is not None:
        result = entry.source_exact_array_backend_uninit_translation_result
        if result is None or entry.source_deferred_request_record is not request:
            return (_worklist_provenance_mismatch_diagnostic(
                "selected-body deferred worklist entries must preserve M100 "
                "deferred request record object identity",
                entry.source_location,
            ),)
        if not any(
            entry.source_deferred_request_record is accepted
            for accepted in result.deferred_request_records
        ):
            return (_worklist_provenance_mismatch_diagnostic(
                "selected-body deferred worklist entries must preserve "
                "accepted M100 deferred record object identity",
                entry.source_location,
            ),)
    if entry.source_exact_array_backend_uninit_translation_record is not None or entry.source_no_request_record is not None:
        return (_worklist_malformed_diagnostic(
            "selected-body deferred worklist entries must not carry exact-array "
            "result-record or no-request provenance",
            entry.source_location,
        ),)
    return ()


def _validate_no_request_entry(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> tuple[Diagnostic, ...]:
    no_request = entry.source_no_request_record
    if no_request is None or not any(
        no_request is accepted for accepted in inventory.no_request_records
    ):
        return (_worklist_malformed_diagnostic(
            "no-request worklist entries require an accepted M99 no-request record",
            entry.source_location,
        ),)
    if (
        entry.source_request_record is not None
        or entry.source_exact_array_backend_uninit_translation_result is not None
        or entry.source_exact_array_backend_uninit_translation_record is not None
        or entry.source_deferred_request_record is not None
    ):
        return (_worklist_malformed_diagnostic(
            "no-request worklist entries must not carry request or M100 result "
            "provenance",
            entry.source_location,
        ),)
    return ()


def _validate_entry_against_expected(
    actual: Stage8BackendBoundaryWorklistEntryIr,
    expected: Stage8BackendBoundaryWorklistEntryIr,
) -> tuple[Diagnostic, ...]:
    if actual.classification != expected.classification:
        return (_worklist_conflicting_entry_diagnostic(
            "Stage 8 backend-boundary worklist entry classification must "
            "match accepted M99/M100 facts",
            actual.source_location,
        ),)
    identities = (
        (actual.source_request_inventory, expected.source_request_inventory, "M99 inventory"),
        (actual.source_request_record, expected.source_request_record, "M99 request record"),
        (actual.source_no_request_record, expected.source_no_request_record, "M99 no-request record"),
        (
            actual.source_exact_array_backend_uninit_translation_result,
            expected.source_exact_array_backend_uninit_translation_result,
            "M100 result",
        ),
        (
            actual.source_exact_array_backend_uninit_translation_record,
            expected.source_exact_array_backend_uninit_translation_record,
            "M100 result record",
        ),
        (
            actual.source_deferred_request_record,
            expected.source_deferred_request_record,
            "M100 deferred request record",
        ),
    )
    for actual_value, expected_value, label in identities:
        if actual_value is not expected_value:
            return (_worklist_provenance_mismatch_diagnostic(
                "Stage 8 backend-boundary worklist entries must preserve "
                f"{label} object identity",
                actual.source_location,
            ),)
    return ()


def _first_duplicate_key(
    entries: tuple[Stage8BackendBoundaryWorklistEntryIr, ...],
) -> tuple[object, ...] | None:
    seen: set[tuple[object, ...]] = set()
    for entry in entries:
        key = lowering_ir_key(entry)
        if key is None:
            return ()
        if key in seen:
            return key
        seen.add(key)
    return None


def _first_source_conflict(
    entries: tuple[Stage8BackendBoundaryWorklistEntryIr, ...],
) -> str | None:
    seen: set[tuple[str, int]] = set()
    for entry in entries:
        source: tuple[str, int] | None = None
        if entry.source_request_record is not None:
            source = ("request record", id(entry.source_request_record))
        if entry.source_no_request_record is not None:
            no_request_source = ("no-request record", id(entry.source_no_request_record))
            if source is not None:
                return "mixed request/no-request source"
            source = no_request_source
        if source is None:
            return "missing source record"
        if source in seen:
            return source[0]
        seen.add(source)
    return None
