from __future__ import annotations

from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_expansion_diagnostics import (
    _translation_expansion_duplicate_value_diagnostic,
    _translation_expansion_malformed_diagnostic,
    _translation_expansion_missing_value_diagnostic,
    _translation_expansion_source_unsupported_diagnostic,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
)


def _worklist_inventory_source(
    source: object,
) -> Result[Stage8BackendBoundaryWorklistInventoryIr]:
    if isinstance(source, Stage8BackendBoundaryWorklistInventoryIr):
        return Result.ok(source)
    if hasattr(source, "lowering_backend_boundary_worklist_inventories"):
        return _worklist_inventory_from_container(source)
    return Result.failure(
        (
            _translation_expansion_source_unsupported_diagnostic(
                "Stage 8 backend translation expansion consumes only "
                "accepted M103 backend-boundary worklist inventories or "
                "containers with lowering_backend_boundary_worklist_inventories",
                source_location_from_object(source),
            ),
        )
    )


def _worklist_inventory_from_container(
    source: object,
) -> Result[Stage8BackendBoundaryWorklistInventoryIr]:
    raw_inventories = getattr(source, "lowering_backend_boundary_worklist_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _translation_expansion_malformed_diagnostic(
                    "Stage 8 backend translation expansion container requires "
                    "lowering_backend_boundary_worklist_inventories to be a tuple",
                    source_location_from_object(raw_inventories),
                ),
            )
        )
    inventories = tuple(
        inventory
        for inventory in raw_inventories
        if isinstance(inventory, Stage8BackendBoundaryWorklistInventoryIr)
    )
    if len(inventories) != len(raw_inventories):
        return Result.failure(
            (
                _translation_expansion_malformed_diagnostic(
                    "Stage 8 backend translation expansion container requires "
                    "every worklist inventory entry to be an accepted "
                    "Stage8BackendBoundaryWorklistInventoryIr",
                    source_location_from_entries(raw_inventories),
                ),
            )
        )
    if not inventories:
        return Result.failure(
            (
                _translation_expansion_missing_value_diagnostic(
                    "Stage 8 backend translation expansion requires exactly "
                    "one accepted M103 backend-boundary worklist inventory",
                    source_location_from_object(source),
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _translation_expansion_duplicate_value_diagnostic(
                    "Stage 8 backend translation expansion requires exactly "
                    "one accepted M103 backend-boundary worklist inventory; "
                    f"got {len(inventories)}",
                    source_location_from_entries(inventories),
                ),
            )
        )
    return Result.ok(inventories[0])
