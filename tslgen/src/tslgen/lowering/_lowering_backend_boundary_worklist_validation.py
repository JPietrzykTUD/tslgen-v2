from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._lowering_backend_boundary_worklist_diagnostics import (
    _worklist_conflicting_entry_diagnostic,
    _worklist_context_mismatch_diagnostic,
    _worklist_duplicate_value_diagnostic,
    _worklist_malformed_diagnostic,
    _worklist_missing_value_diagnostic,
    _worklist_provenance_mismatch_diagnostic,
    _worklist_source_location_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_boundary_worklist_entries import (
    _first_duplicate_key,
    _first_source_conflict,
    _validate_entry_against_expected,
    _worklist_entries,
    validate_stage8_backend_boundary_worklist_entry,
)
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestInventoryIr,
    validate_stage8_backend_translation_request_inventory,
)
from tslgen.lowering._lowering_backend_translation_result import (
    ExactArrayBackendUninitTranslationResultIr,
    validate_exact_array_backend_uninit_translation_result,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_object,
)


def validate_stage8_backend_boundary_worklist_inventory(
    inventory: object,
) -> tuple[Diagnostic, ...]:
    if not isinstance(inventory, Stage8BackendBoundaryWorklistInventoryIr):
        return (
            _worklist_malformed_diagnostic(
                "Stage 8 backend-boundary worklist validation requires an "
                "accepted Stage8BackendBoundaryWorklistInventoryIr",
                source_location_from_object(inventory),
            ),
        )
    source_inventory = inventory.source_request_inventory
    result = inventory.source_exact_array_backend_uninit_translation_result
    if not isinstance(source_inventory, Stage8BackendTranslationRequestInventoryIr):
        return (
            _worklist_malformed_diagnostic(
                "Stage 8 backend-boundary worklist inventory requires an "
                "accepted concrete M99 Stage8BackendTranslationRequestInventoryIr",
                source_location_from_object(source_inventory),
            ),
        )
    if result is not None and not isinstance(
        result,
        ExactArrayBackendUninitTranslationResultIr,
    ):
        return (
            _worklist_malformed_diagnostic(
                "Stage 8 backend-boundary worklist inventory requires optional "
                "M100 results to be accepted concrete "
                "ExactArrayBackendUninitTranslationResultIr values",
                source_location_from_object(result),
            ),
        )
    diagnostics = _validate_source_context(
        source_inventory,
        result,
        explicit_candidate_id=inventory.candidate_id,
        explicit_source_location=inventory.source_location,
    )
    if diagnostics:
        return diagnostics

    expected_entries = _worklist_entries(source_inventory, result)
    if len(inventory.entries) != len(expected_entries):
        return (
            _worklist_provenance_mismatch_diagnostic(
                "Stage 8 backend-boundary worklist inventory requires one "
                "entry for each accepted backend-boundary request, result, "
                "deferred request, or no-request fact",
                inventory.source_location,
            ),
        )
    for actual in inventory.entries:
        diagnostics = validate_stage8_backend_boundary_worklist_entry(
            source_inventory,
            actual,
        )
        if diagnostics:
            return diagnostics
    duplicate = _first_duplicate_key(inventory.entries)
    if duplicate is not None:
        return (
            _worklist_duplicate_value_diagnostic(
                "Stage 8 backend-boundary worklist entries must have unique "
                f"keys; duplicate key {duplicate!r}",
                inventory.source_location,
            ),
        )
    conflict = _first_source_conflict(inventory.entries)
    if conflict is not None:
        return (
            _worklist_conflicting_entry_diagnostic(
                "Stage 8 backend-boundary worklist entries must preserve "
                f"exactly one classification per {conflict}",
                inventory.source_location,
            ),
        )
    for actual, expected in zip(inventory.entries, expected_entries, strict=True):
        diagnostics = _validate_entry_against_expected(actual, expected)
        if diagnostics:
            return diagnostics
    return ()


def _validate_source_context(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    result: ExactArrayBackendUninitTranslationResultIr | None,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    inventory_diagnostics = validate_stage8_backend_translation_request_inventory(
        inventory,
    )
    if inventory_diagnostics:
        return (_remap_diagnostic(inventory_diagnostics[0], inventory.source_location),)
    if explicit_candidate_id is not None and explicit_candidate_id != inventory.candidate_id:
        return (_worklist_context_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist candidate context must match "
            "the accepted M99 request inventory",
            inventory.source_location,
        ),)
    if explicit_source_location is not None and explicit_source_location != inventory.source_location:
        return (_worklist_source_location_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist source location must match "
            "the accepted M99 request inventory",
            inventory.source_location,
        ),)
    if result is None:
        return ()
    result_diagnostics = validate_exact_array_backend_uninit_translation_result(result)
    if result_diagnostics:
        return (_remap_diagnostic(result_diagnostics[0], result.source_location),)
    if result.source_request_inventory is not inventory:
        return (_worklist_provenance_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist requires the M100 result to "
            "preserve M99 request inventory object identity",
            result.source_location,
        ),)
    if result.candidate_id != inventory.candidate_id:
        return (_worklist_context_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist requires the M100 result "
            "candidate id to match the M99 request inventory",
            result.source_location,
        ),)
    if result.source_location != inventory.source_location:
        return (_worklist_source_location_mismatch_diagnostic(
            "Stage 8 backend-boundary worklist requires the M100 result "
            "source location to match the M99 request inventory",
            result.source_location,
        ),)
    return ()


def _remap_diagnostic(
    diagnostic: Diagnostic,
    fallback_location: SourceLocation | None,
) -> Diagnostic:
    location = diagnostic.location or fallback_location
    if diagnostic.code.endswith("PROVENANCE-MISMATCH"):
        return _worklist_provenance_mismatch_diagnostic(diagnostic.message, location)
    if diagnostic.code.endswith("CONTEXT-MISMATCH"):
        return _worklist_context_mismatch_diagnostic(diagnostic.message, location)
    if diagnostic.code.endswith("SOURCE-LOCATION-MISMATCH"):
        return _worklist_source_location_mismatch_diagnostic(
            diagnostic.message,
            location,
        )
    if diagnostic.code.endswith("VALUE-MULTIPLE"):
        return _worklist_duplicate_value_diagnostic(diagnostic.message, location)
    if diagnostic.code.endswith("VALUE-MISSING"):
        return _worklist_missing_value_diagnostic(diagnostic.message, location)
    return _worklist_malformed_diagnostic(diagnostic.message, location)
