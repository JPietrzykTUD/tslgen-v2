from __future__ import annotations

from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_boundary_worklist_diagnostics import (
    _worklist_conflicting_entry_diagnostic,
    _worklist_duplicate_value_diagnostic,
    _worklist_malformed_diagnostic,
    _worklist_missing_value_diagnostic,
    _worklist_source_unsupported_diagnostic,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_result import (
    ExactArrayBackendUninitTranslationResultIr,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
)


def _source_request_inventory_and_result(
    source: object,
    explicit_result: ExactArrayBackendUninitTranslationResultIr | None,
) -> Result[
    tuple[
        Stage8BackendTranslationRequestInventoryIr,
        ExactArrayBackendUninitTranslationResultIr | None,
    ]
]:
    if explicit_result is not None and not isinstance(
        explicit_result,
        ExactArrayBackendUninitTranslationResultIr,
    ):
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    "Stage 8 backend-boundary worklist requires explicit "
                    "exact-array results to be accepted concrete "
                    "ExactArrayBackendUninitTranslationResultIr values",
                    source_location_from_object(explicit_result),
                ),
            )
        )
    if isinstance(source, Stage8BackendTranslationRequestInventoryIr):
        return Result.ok((source, explicit_result))
    if hasattr(source, "lowering_backend_translation_request_inventories"):
        return _source_from_container(source, explicit_result)
    return Result.failure(
        (
            _worklist_source_unsupported_diagnostic(
                "Stage 8 backend-boundary worklist inventories consume only "
                "accepted M99 backend-translation request inventories or "
                "containers with lowering_backend_translation_request_inventories",
                source_location_from_object(source),
            ),
        )
    )


def _source_from_container(
    source: object,
    explicit_result: ExactArrayBackendUninitTranslationResultIr | None,
) -> Result[
    tuple[
        Stage8BackendTranslationRequestInventoryIr,
        ExactArrayBackendUninitTranslationResultIr | None,
    ]
]:
    inventory_result = _single_request_inventory_from_container(source)
    if not inventory_result.is_ok:
        return Result.failure(inventory_result.diagnostics)
    inventory = inventory_result.unwrap()

    container_result = None
    if hasattr(source, "exact_array_backend_uninit_translation_results"):
        result_result = _single_translation_result_from_container(source)
        if not result_result.is_ok:
            return Result.failure(result_result.diagnostics)
        container_result = result_result.unwrap()
    if (
        explicit_result is not None
        and container_result is not None
        and explicit_result is not container_result
    ):
        return Result.failure(
            (
                _worklist_conflicting_entry_diagnostic(
                    "Stage 8 backend-boundary worklist source container and "
                    "explicit exact-array result must preserve object identity "
                    "when both are supplied",
                    inventory.source_location,
                ),
            )
        )
    return Result.ok((inventory, explicit_result or container_result))


def _single_request_inventory_from_container(
    source: object,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    raw_inventories = getattr(source, "lowering_backend_translation_request_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    "Stage 8 backend-boundary worklist container requires "
                    "lowering_backend_translation_request_inventories to be a tuple",
                    source_location_from_object(raw_inventories),
                ),
            )
        )
    inventories = tuple(
        inventory
        for inventory in raw_inventories
        if isinstance(inventory, Stage8BackendTranslationRequestInventoryIr)
    )
    if len(inventories) != len(raw_inventories):
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    "Stage 8 backend-boundary worklist container requires "
                    "every request inventory entry to be an accepted "
                    "Stage8BackendTranslationRequestInventoryIr",
                    source_location_from_entries(raw_inventories),
                ),
            )
        )
    if not inventories:
        return Result.failure(
            (
                _worklist_missing_value_diagnostic(
                    "Stage 8 backend-boundary worklist requires exactly one "
                    "accepted M99 backend-translation request inventory",
                    source_location_from_object(source),
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _worklist_duplicate_value_diagnostic(
                    "Stage 8 backend-boundary worklist requires exactly one "
                    "accepted M99 backend-translation request inventory; got "
                    f"{len(inventories)}",
                    source_location_from_entries(inventories),
                ),
            )
        )
    return Result.ok(inventories[0])


def _single_translation_result_from_container(
    source: object,
) -> Result[ExactArrayBackendUninitTranslationResultIr | None]:
    raw_results = getattr(source, "exact_array_backend_uninit_translation_results")
    if not isinstance(raw_results, tuple):
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    "Stage 8 backend-boundary worklist container requires "
                    "exact_array_backend_uninit_translation_results to be a tuple",
                    source_location_from_object(raw_results),
                ),
            )
        )
    results = tuple(
        result
        for result in raw_results
        if isinstance(result, ExactArrayBackendUninitTranslationResultIr)
    )
    if len(results) != len(raw_results):
        return Result.failure(
            (
                _worklist_malformed_diagnostic(
                    "Stage 8 backend-boundary worklist container requires "
                    "every exact-array result entry to be an accepted "
                    "ExactArrayBackendUninitTranslationResultIr",
                    source_location_from_entries(raw_results),
                ),
            )
        )
    if len(results) > 1:
        return Result.failure(
            (
                _worklist_duplicate_value_diagnostic(
                    "Stage 8 backend-boundary worklist accepts at most one "
                    "M100 exact-array backend-uninit translation result; got "
                    f"{len(results)}",
                    source_location_from_entries(results),
                ),
            )
        )
    return Result.ok(results[0] if results else None)
