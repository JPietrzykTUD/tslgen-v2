from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
)
from tslgen.lowering._lowering_completion_manifest import (
    Stage8LoweringCompletionManifestIr,
    Stage8LoweringCompletionManifestPackageRecordIr,
    Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr,
    validate_stage8_lowering_completion_manifest,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
    source_location_key,
)
from tslgen.lowering._operation_package_models import LoweringOperationPackageIr


type Stage8LoweringCompletionGapInventoryState = Literal[
    "no_known_gap",
    "has_unresolved_backend_handoff_dependencies",
]
type Stage8LoweringCompletionGapKind = Literal[
    "unresolved_backend_handoff_dependency",
]


@dataclass(frozen=True, slots=True)
class Stage8LoweringCompletionGapRecordIr:
    source_manifest: Stage8LoweringCompletionManifestIr
    source_package_record: Stage8LoweringCompletionManifestPackageRecordIr
    source_package: LoweringOperationPackageIr
    source_unresolved_dependency_record: (
        Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr
    )
    source_dependency_request: ExactArrayBackendHandoffUnresolvedDependencyRequestIr
    kind: Stage8LoweringCompletionGapKind = "unresolved_backend_handoff_dependency"

    def __post_init__(self) -> None:
        diagnostics = _validate_gap_record(
            self.source_manifest,
            self,
        )
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_manifest.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.source_dependency_request.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_lowering_completion_gap_record",
            self.kind,
            self.source_manifest.key,
            self.source_package_record.key,
            self.source_package.key,
            self.source_unresolved_dependency_record.key,
            self.source_dependency_request.key,
        )


@dataclass(frozen=True, slots=True)
class Stage8LoweringCompletionGapInventoryIr:
    candidate_id: str
    source_location: SourceLocation | None
    inventory_state: Stage8LoweringCompletionGapInventoryState
    source_manifest: Stage8LoweringCompletionManifestIr
    gap_records: tuple[Stage8LoweringCompletionGapRecordIr, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "Stage 8 lowering completion gap inventory candidate id must be "
                "non-empty"
            )
        object.__setattr__(self, "gap_records", tuple(self.gap_records))
        diagnostics = validate_stage8_lowering_completion_gap_inventory(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def has_known_gaps(self) -> bool:
        return bool(self.gap_records)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_lowering_completion_gap_inventory",
            self.candidate_id,
            source_location_key(self.source_location),
            self.inventory_state,
            self.source_manifest.key,
            tuple(record.key for record in self.gap_records),
        )


def lower_stage8_lowering_completion_gap_inventory(
    source: object,
    *,
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
) -> Result[Stage8LoweringCompletionGapInventoryIr]:
    if isinstance(source, Stage8LoweringCompletionGapInventoryIr):
        return _validate_existing_inventory(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
        )

    manifest_source = _manifest_source(source)
    if not manifest_source.is_ok:
        return Result.failure(manifest_source.diagnostics)
    manifest = manifest_source.unwrap()

    diagnostics = _validate_manifest_context(
        manifest,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    try:
        gap_records = tuple(
            _gap_record_for_dependency(manifest, dependency_record)
            for dependency_record in manifest.unresolved_dependency_records
        )
        inventory = Stage8LoweringCompletionGapInventoryIr(
            candidate_id=candidate_id or manifest.candidate_id,
            source_location=source_location or manifest.source_location,
            inventory_state=(
                "has_unresolved_backend_handoff_dependencies"
                if gap_records
                else "no_known_gap"
            ),
            source_manifest=manifest,
            gap_records=gap_records,
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _gap_inventory_malformed_diagnostic(
                    str(exc),
                    source_location
                    or manifest.source_location
                    or source_location_from_entries(manifest.package_records),
                ),
            )
        )
    return Result.ok(inventory)


def validate_stage8_lowering_completion_gap_inventory(
    inventory: Stage8LoweringCompletionGapInventoryIr,
) -> tuple[Diagnostic, ...]:
    manifest = inventory.source_manifest
    diagnostics = _validate_manifest_context(
        manifest,
        explicit_candidate_id=inventory.candidate_id,
        explicit_source_location=inventory.source_location,
    )
    if diagnostics:
        return diagnostics

    expected_dependency_records = tuple(manifest.unresolved_dependency_records)
    if len(inventory.gap_records) != len(expected_dependency_records):
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap inventory requires one gap "
                "record for each manifest unresolved dependency record",
                inventory.source_location,
            ),
        )
    expected_state: Stage8LoweringCompletionGapInventoryState = (
        "has_unresolved_backend_handoff_dependencies"
        if expected_dependency_records
        else "no_known_gap"
    )
    if inventory.inventory_state != expected_state:
        return (
            _gap_inventory_context_mismatch_diagnostic(
                "Stage 8 lowering completion gap inventory state must match "
                "the accepted manifest unresolved dependency facts",
                inventory.source_location,
            ),
        )
    for actual, expected in zip(
        inventory.gap_records,
        expected_dependency_records,
        strict=True,
    ):
        if actual.source_manifest is not manifest:
            return (
                _gap_inventory_provenance_mismatch_diagnostic(
                    "Stage 8 lowering completion gap records must preserve "
                    "the source manifest object identity",
                    actual.source_location,
                ),
            )
        if actual.source_unresolved_dependency_record is not expected:
            return (
                _gap_inventory_provenance_mismatch_diagnostic(
                    "Stage 8 lowering completion gap records must preserve "
                    "manifest unresolved dependency record object identity",
                    actual.source_location,
                ),
            )
        diagnostics = _validate_gap_record(manifest, actual)
        if diagnostics:
            return diagnostics
    return ()


def _manifest_source(
    source: object,
) -> Result[Stage8LoweringCompletionManifestIr]:
    if isinstance(source, Stage8LoweringCompletionManifestIr):
        return Result.ok(source)
    if _is_generation_stage_like(source):
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if stage != "lowering_completion_manifest":
            return Result.failure(
                (
                    _gap_inventory_source_unsupported_diagnostic(
                        "Stage 8 lowering completion gap inventory consumes "
                        "only lowering_completion_manifest stages or accepted "
                        "Stage8LoweringCompletionManifestIr values",
                        source_location_from_object(output),
                    ),
                )
            )
        if not isinstance(output, Stage8LoweringCompletionManifestIr):
            return Result.failure(
                (
                    _gap_inventory_malformed_diagnostic(
                        "Stage 8 lowering completion gap inventory stage "
                        "output must be an accepted "
                        "Stage8LoweringCompletionManifestIr",
                        source_location_from_object(output),
                    ),
                )
            )
        return Result.ok(output)
    if hasattr(source, "lowering_completion_manifests"):
        raw_manifests = getattr(source, "lowering_completion_manifests")
        if not isinstance(raw_manifests, tuple):
            return Result.failure(
                (
                    _gap_inventory_malformed_diagnostic(
                        "Stage 8 lowering completion gap inventory container "
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
                    _gap_inventory_malformed_diagnostic(
                        "Stage 8 lowering completion gap inventory container "
                        "requires every manifest entry to be an accepted "
                        "Stage8LoweringCompletionManifestIr",
                        source_location_from_entries(raw_manifests),
                    ),
                )
            )
        if not manifests:
            return Result.failure(
                (
                    _gap_inventory_missing_value_diagnostic(
                        "Stage 8 lowering completion gap inventory requires "
                        "exactly one accepted completion manifest",
                        source_location_from_object(source),
                    ),
                )
            )
        if len(manifests) > 1:
            return Result.failure(
                (
                    _gap_inventory_duplicate_value_diagnostic(
                        "Stage 8 lowering completion gap inventory requires "
                        f"exactly one accepted completion manifest; got "
                        f"{len(manifests)}",
                        source_location_from_entries(manifests),
                    ),
                )
            )
        return Result.ok(manifests[0])
    return Result.failure(
        (
            _gap_inventory_source_unsupported_diagnostic(
                "Stage 8 lowering completion gap inventory consumes accepted "
                "completion manifests, lowering_completion_manifest stages, "
                "or containers with lowering_completion_manifests",
                source_location_from_object(source),
            ),
        )
    )


def _validate_existing_inventory(
    inventory: Stage8LoweringCompletionGapInventoryIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
) -> Result[Stage8LoweringCompletionGapInventoryIr]:
    if candidate_id is not None and candidate_id != inventory.candidate_id:
        return Result.failure(
            (
                _gap_inventory_context_mismatch_diagnostic(
                    "Stage 8 lowering completion gap inventory candidate "
                    "context must match the existing inventory",
                    inventory.source_location,
                ),
            )
        )
    if source_location is not None and source_location != inventory.source_location:
        return Result.failure(
            (
                _gap_inventory_source_location_mismatch_diagnostic(
                    "Stage 8 lowering completion gap inventory source "
                    "location must match the existing inventory",
                    inventory.source_location,
                ),
            )
        )
    diagnostics = validate_stage8_lowering_completion_gap_inventory(inventory)
    if diagnostics:
        return Result.failure(diagnostics)
    return Result.ok(inventory)


def _validate_manifest_context(
    manifest: Stage8LoweringCompletionManifestIr,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    manifest_diagnostics = validate_stage8_lowering_completion_manifest(manifest)
    if manifest_diagnostics:
        return (
            _gap_inventory_malformed_diagnostic(
                manifest_diagnostics[0].message,
                manifest.source_location,
            ),
        )
    if explicit_candidate_id is not None and explicit_candidate_id != manifest.candidate_id:
        return (
            _gap_inventory_context_mismatch_diagnostic(
                "Stage 8 lowering completion gap inventory candidate context "
                "must match the accepted manifest",
                manifest.source_location,
            ),
        )
    if (
        explicit_source_location is not None
        and explicit_source_location != manifest.source_location
    ):
        return (
            _gap_inventory_source_location_mismatch_diagnostic(
                "Stage 8 lowering completion gap inventory source location "
                "must match the accepted manifest",
                manifest.source_location,
            ),
        )
    return ()


def _gap_record_for_dependency(
    manifest: Stage8LoweringCompletionManifestIr,
    dependency_record: Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr,
) -> Stage8LoweringCompletionGapRecordIr:
    package_record = _package_record_for_dependency(manifest, dependency_record)
    return Stage8LoweringCompletionGapRecordIr(
        source_manifest=manifest,
        source_package_record=package_record,
        source_package=dependency_record.source_package,
        source_unresolved_dependency_record=dependency_record,
        source_dependency_request=dependency_record.source_dependency_request,
    )


def _package_record_for_dependency(
    manifest: Stage8LoweringCompletionManifestIr,
    dependency_record: Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr,
) -> Stage8LoweringCompletionManifestPackageRecordIr:
    for package_record in manifest.package_records:
        if package_record.source_package is dependency_record.source_package:
            return package_record
    raise ValueError(
        "Stage 8 lowering completion gap records require a manifest package "
        "record preserving the unresolved dependency package identity"
    )


def _validate_gap_record(
    manifest: Stage8LoweringCompletionManifestIr,
    record: Stage8LoweringCompletionGapRecordIr,
) -> tuple[Diagnostic, ...]:
    if record.kind != "unresolved_backend_handoff_dependency":
        return (
            _gap_inventory_malformed_diagnostic(
                "Stage 8 lowering completion gap records support only "
                "unresolved backend-handoff dependency facts",
                record.source_location,
            ),
        )
    if record.source_unresolved_dependency_record not in (
        manifest.unresolved_dependency_records
    ):
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must come from "
                "manifest unresolved dependency records",
                record.source_location,
            ),
        )
    if not any(
        record.source_unresolved_dependency_record is manifest_record
        for manifest_record in manifest.unresolved_dependency_records
    ):
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must preserve "
                "manifest unresolved dependency record object identity",
                record.source_location,
            ),
        )
    if record.source_package_record not in manifest.package_records or not any(
        record.source_package_record is package_record
        for package_record in manifest.package_records
    ):
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must preserve "
                "manifest package record object identity",
                record.source_location,
            ),
        )
    dependency_record = record.source_unresolved_dependency_record
    if record.source_package is not dependency_record.source_package:
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must preserve "
                "source package object identity",
                record.source_location,
            ),
        )
    if record.source_package_record.source_package is not record.source_package:
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must preserve the "
                "manifest package record to package object identity",
                record.source_location,
            ),
        )
    if record.source_dependency_request is not dependency_record.source_dependency_request:
        return (
            _gap_inventory_provenance_mismatch_diagnostic(
                "Stage 8 lowering completion gap records must preserve "
                "source dependency request object identity",
                record.source_location,
            ),
        )
    return ()


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _gap_inventory_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _gap_inventory_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-VALUE-MISSING",
        detail,
        location=location,
    )


def _gap_inventory_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-VALUE-MULTIPLE",
        detail,
        location=location,
    )


def _gap_inventory_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-MALFORMED",
        detail,
        location=location,
    )


def _gap_inventory_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _gap_inventory_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def _gap_inventory_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-GAP-INVENTORY-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )
