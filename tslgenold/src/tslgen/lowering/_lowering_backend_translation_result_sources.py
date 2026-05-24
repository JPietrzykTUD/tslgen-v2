from __future__ import annotations

from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_result_diagnostics import (
    _translation_result_duplicate_value_diagnostic,
    _translation_result_malformed_diagnostic,
    _translation_result_missing_value_diagnostic,
    _translation_result_provenance_mismatch_diagnostic,
    _translation_result_source_unsupported_diagnostic,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
)
from tslgen.lowering._lowering_completion_gap_inventory import (
    Stage8LoweringCompletionGapInventoryIr,
)
from tslgen.lowering._lowering_completion_manifest import (
    Stage8LoweringCompletionManifestIr,
)


def _request_inventory_source(
    source: object,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    if isinstance(source, Stage8BackendTranslationRequestInventoryIr):
        return Result.ok(source)
    if _is_generation_stage_like(source):
        return _request_inventory_from_stage(source)
    if hasattr(source, "lowering_backend_translation_request_inventories"):
        return _request_inventory_from_container(source)
    return Result.failure(
        (
            _translation_result_source_unsupported_diagnostic(
                "exact-array backend-uninit translation results consume "
                "accepted backend-translation request inventories, matching "
                "request-inventory stages, or containers with "
                "lowering_backend_translation_request_inventories",
                source_location_from_object(source),
            ),
        )
    )


def _request_inventory_from_stage(
    source: object,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    stage = getattr(source, "stage")
    output = getattr(source, "output")
    if stage != "lowering_backend_translation_request_inventory":
        return Result.failure(
            (
                _translation_result_source_unsupported_diagnostic(
                    "exact-array backend-uninit translation results consume "
                    "only lowering_backend_translation_request_inventory "
                    "stages or accepted request inventories",
                    source_location_from_object(output),
                ),
            )
        )
    if not isinstance(output, Stage8BackendTranslationRequestInventoryIr):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result stage "
                    "output must be an accepted "
                    "Stage8BackendTranslationRequestInventoryIr",
                    source_location_from_object(output),
                ),
            )
        )
    return Result.ok(output)


def _request_inventory_from_container(
    source: object,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    raw_inventories = getattr(source, "lowering_backend_translation_request_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires lowering_backend_translation_request_inventories "
                    "to be a tuple",
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
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires every inventory entry to be an accepted "
                    "Stage8BackendTranslationRequestInventoryIr",
                    source_location_from_entries(raw_inventories),
                ),
            )
        )
    if not inventories:
        return Result.failure(
            (
                _translation_result_missing_value_diagnostic(
                    "exact-array backend-uninit translation result requires "
                    "exactly one accepted backend-translation request inventory",
                    source_location_from_object(source),
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _translation_result_duplicate_value_diagnostic(
                    "exact-array backend-uninit translation result requires "
                    "exactly one accepted backend-translation request inventory; "
                    f"got {len(inventories)}",
                    source_location_from_entries(inventories),
                ),
            )
        )
    inventory = inventories[0]
    if hasattr(source, "lowering_completion_manifests"):
        manifest_result = _single_manifest_from_container(source)
        if not manifest_result.is_ok:
            return Result.failure(manifest_result.diagnostics)
        manifest = manifest_result.unwrap()
        if inventory.source_manifest is not manifest:
            return Result.failure(
                (
                    _translation_result_provenance_mismatch_diagnostic(
                        "exact-array backend-uninit translation result "
                        "container must preserve request inventory to "
                        "manifest object identity",
                        inventory.source_location,
                    ),
                )
            )
    if hasattr(source, "lowering_completion_gap_inventories"):
        gap_inventory_result = _single_gap_inventory_from_container(source)
        if not gap_inventory_result.is_ok:
            return Result.failure(gap_inventory_result.diagnostics)
        gap_inventory = gap_inventory_result.unwrap()
        if inventory.source_gap_inventory is not gap_inventory:
            return Result.failure(
                (
                    _translation_result_provenance_mismatch_diagnostic(
                        "exact-array backend-uninit translation result "
                        "container must preserve request inventory to gap "
                        "inventory object identity",
                        inventory.source_location,
                    ),
                )
            )
    return Result.ok(inventory)


def _single_manifest_from_container(
    source: object,
) -> Result[Stage8LoweringCompletionManifestIr]:
    raw_manifests = getattr(source, "lowering_completion_manifests")
    if not isinstance(raw_manifests, tuple):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires lowering_completion_manifests to be a tuple",
                    source_location_from_object(raw_manifests),
                ),
            )
        )
    manifests = tuple(
        manifest
        for manifest in raw_manifests
        if isinstance(manifest, Stage8LoweringCompletionManifestIr)
    )
    if len(manifests) != len(raw_manifests):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires every manifest entry to be an accepted "
                    "Stage8LoweringCompletionManifestIr",
                    source_location_from_entries(raw_manifests),
                ),
            )
        )
    if not manifests:
        return Result.failure(
            (
                _translation_result_missing_value_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires exactly one accepted completion manifest",
                    source_location_from_object(source),
                ),
            )
        )
    if len(manifests) > 1:
        return Result.failure(
            (
                _translation_result_duplicate_value_diagnostic(
                    "exact-array backend-uninit translation result container "
                    f"requires exactly one accepted completion manifest; got "
                    f"{len(manifests)}",
                    source_location_from_entries(manifests),
                ),
            )
        )
    return Result.ok(manifests[0])


def _single_gap_inventory_from_container(
    source: object,
) -> Result[Stage8LoweringCompletionGapInventoryIr]:
    raw_inventories = getattr(source, "lowering_completion_gap_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires lowering_completion_gap_inventories to be a tuple",
                    source_location_from_object(raw_inventories),
                ),
            )
        )
    inventories = tuple(
        inventory
        for inventory in raw_inventories
        if isinstance(inventory, Stage8LoweringCompletionGapInventoryIr)
    )
    if len(inventories) != len(raw_inventories):
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires every gap inventory entry to be an accepted "
                    "Stage8LoweringCompletionGapInventoryIr",
                    source_location_from_entries(raw_inventories),
                ),
            )
        )
    if not inventories:
        return Result.failure(
            (
                _translation_result_missing_value_diagnostic(
                    "exact-array backend-uninit translation result container "
                    "requires exactly one accepted completion gap inventory",
                    source_location_from_object(source),
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _translation_result_duplicate_value_diagnostic(
                    "exact-array backend-uninit translation result container "
                    f"requires exactly one accepted completion gap inventory; "
                    f"got {len(inventories)}",
                    source_location_from_entries(inventories),
                ),
            )
        )
    return Result.ok(inventories[0])


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")
