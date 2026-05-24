from __future__ import annotations

from tslgen.core.diagnostics import SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_boundary_worklist_diagnostics import (
    _worklist_malformed_diagnostic,
)
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT,
    STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT,
    Stage8BackendBoundaryWorklistClassification,
    Stage8BackendBoundaryWorklistEntryIr,
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_boundary_worklist_sources import (
    _source_request_inventory_and_result,
)
from tslgen.lowering._lowering_backend_boundary_worklist_validation import (
    _validate_source_context,
    _worklist_entries,
    validate_stage8_backend_boundary_worklist_entry,
    validate_stage8_backend_boundary_worklist_inventory,
)
from tslgen.lowering._lowering_backend_translation_result import (
    ExactArrayBackendUninitTranslationResultIr,
)


__all__ = (
    "STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT",
    "STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT",
    "Stage8BackendBoundaryWorklistClassification",
    "Stage8BackendBoundaryWorklistEntryIr",
    "Stage8BackendBoundaryWorklistInventoryIr",
    "lower_stage8_backend_boundary_worklist_inventory",
    "validate_stage8_backend_boundary_worklist_entry",
    "validate_stage8_backend_boundary_worklist_inventory",
)


def lower_stage8_backend_boundary_worklist_inventory(
    source: object,
    *,
    exact_array_backend_uninit_translation_result: ExactArrayBackendUninitTranslationResultIr | None = None,
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
) -> Result[Stage8BackendBoundaryWorklistInventoryIr]:
    source_result = _source_request_inventory_and_result(
        source,
        exact_array_backend_uninit_translation_result,
    )
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    inventory, translation_result = source_result.unwrap()

    diagnostics = _validate_source_context(
        inventory,
        translation_result,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    try:
        worklist = Stage8BackendBoundaryWorklistInventoryIr(
            candidate_id=candidate_id or inventory.candidate_id,
            source_location=source_location or inventory.source_location,
            source_request_inventory=inventory,
            source_exact_array_backend_uninit_translation_result=translation_result,
            entries=_worklist_entries(inventory, translation_result),
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    str(exc),
                    source_location or inventory.source_location,
                ),
            )
        )
    return Result.ok(worklist)
