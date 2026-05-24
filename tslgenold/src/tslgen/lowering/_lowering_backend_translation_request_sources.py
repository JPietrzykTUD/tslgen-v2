from __future__ import annotations

from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_translation_request_diagnostics import (
    _request_inventory_duplicate_value_diagnostic,
    _request_inventory_malformed_diagnostic,
    _request_inventory_missing_value_diagnostic,
    _request_inventory_provenance_mismatch_diagnostic,
    _request_inventory_source_unsupported_diagnostic,
)
from tslgen.lowering._lowering_completion_gap_inventory import (
    Stage8LoweringCompletionGapInventoryIr,
)
from tslgen.lowering._lowering_completion_manifest import (
    Stage8LoweringCompletionManifestIr,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
)


def _gap_inventory_source(
    source: object,
) -> Result[
    tuple[Stage8LoweringCompletionManifestIr, Stage8LoweringCompletionGapInventoryIr]
]:
    if isinstance(source, Stage8LoweringCompletionGapInventoryIr):
        return Result.ok((source.source_manifest, source))
    if _is_generation_stage_like(source):
        return _gap_inventory_from_stage(source)
    if hasattr(source, "lowering_completion_gap_inventories"):
        return _gap_inventory_from_container(source)
    return Result.failure(
        (
            _request_inventory_source_unsupported_diagnostic(
                "Stage 8 backend-translation request inventory consumes "
                "accepted completion gap inventories, "
                "lowering_completion_gap_inventory stages, or containers with "
                "lowering_completion_gap_inventories",
                source_location_from_object(source),
            ),
        )
    )


def _gap_inventory_from_stage(
    source: object,
) -> Result[
    tuple[Stage8LoweringCompletionManifestIr, Stage8LoweringCompletionGapInventoryIr]
]:
    stage = getattr(source, "stage")
    output = getattr(source, "output")
    if stage != "lowering_completion_gap_inventory":
        return Result.failure(
            (
                _request_inventory_source_unsupported_diagnostic(
                    "Stage 8 backend-translation request inventory consumes "
                    "only lowering_completion_gap_inventory stages or "
                    "accepted gap inventories",
                    source_location_from_object(output),
                ),
            )
        )
    if not isinstance(output, Stage8LoweringCompletionGapInventoryIr):
        return Result.failure(
            (
                _request_inventory_malformed_diagnostic(
                    "Stage 8 backend-translation request inventory stage "
                    "output must be an accepted "
                    "Stage8LoweringCompletionGapInventoryIr",
                    source_location_from_object(output),
                ),
            )
        )
    return Result.ok((output.source_manifest, output))


def _gap_inventory_from_container(
    source: object,
) -> Result[
    tuple[Stage8LoweringCompletionManifestIr, Stage8LoweringCompletionGapInventoryIr]
]:
    raw_inventories = getattr(source, "lowering_completion_gap_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _request_inventory_malformed_diagnostic(
                    "Stage 8 backend-translation request inventory container "
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
                _request_inventory_malformed_diagnostic(
                    "Stage 8 backend-translation request inventory container "
                    "requires every inventory entry to be an accepted "
                    "Stage8LoweringCompletionGapInventoryIr",
                    source_location_from_entries(raw_inventories),
                ),
            )
        )
    if not inventories:
        return Result.failure(
            (
                _request_inventory_missing_value_diagnostic(
                    "Stage 8 backend-translation request inventory requires "
                    "exactly one accepted completion gap inventory",
                    source_location_from_object(source),
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _request_inventory_duplicate_value_diagnostic(
                    "Stage 8 backend-translation request inventory requires "
                    "exactly one accepted completion gap inventory; got "
                    f"{len(inventories)}",
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
                    _request_inventory_provenance_mismatch_diagnostic(
                        "Stage 8 backend-translation request inventory "
                        "container must preserve gap inventory to manifest "
                        "object identity",
                        inventory.source_location,
                    ),
                )
            )
    return Result.ok((inventory.source_manifest, inventory))


def _single_manifest_from_container(
    source: object,
) -> Result[Stage8LoweringCompletionManifestIr]:
    raw_manifests = getattr(source, "lowering_completion_manifests")
    if not isinstance(raw_manifests, tuple):
        return Result.failure(
            (
                _request_inventory_malformed_diagnostic(
                    "Stage 8 backend-translation request inventory container "
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
                _request_inventory_malformed_diagnostic(
                    "Stage 8 backend-translation request inventory container "
                    "requires every manifest entry to be an accepted "
                    "Stage8LoweringCompletionManifestIr",
                    source_location_from_entries(raw_manifests),
                ),
            )
        )
    if not manifests:
        return Result.failure(
            (
                _request_inventory_missing_value_diagnostic(
                    "Stage 8 backend-translation request inventory container "
                    "requires exactly one accepted completion manifest",
                    source_location_from_object(source),
                ),
            )
        )
    if len(manifests) > 1:
        return Result.failure(
            (
                _request_inventory_duplicate_value_diagnostic(
                    "Stage 8 backend-translation request inventory container "
                    f"requires exactly one accepted completion manifest; got "
                    f"{len(manifests)}",
                    source_location_from_entries(manifests),
                ),
            )
        )
    return Result.ok(manifests[0])


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")
