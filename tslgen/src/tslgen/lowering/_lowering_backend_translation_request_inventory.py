from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
)
from tslgen.lowering._lowering_backend_translation_request_diagnostics import (
    _request_inventory_context_mismatch_diagnostic,
    _request_inventory_malformed_diagnostic,
    _request_inventory_provenance_mismatch_diagnostic,
    _request_inventory_source_location_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_translation_request_sources import (
    _gap_inventory_source,
)
from tslgen.lowering._lowering_completion_gap_inventory import (
    Stage8LoweringCompletionGapInventoryIr,
    Stage8LoweringCompletionGapRecordIr,
    validate_stage8_lowering_completion_gap_inventory,
)
from tslgen.lowering._lowering_completion_manifest import (
    Stage8LoweringCompletionManifestIr,
    Stage8LoweringCompletionManifestPackageRecordIr,
    Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr,
    validate_stage8_lowering_completion_manifest,
)
from tslgen.lowering._operation_package_diagnostics import source_location_key
from tslgen.lowering._operation_package_models import LoweringOperationPackageIr
from tslgen.lowering._operation_package_selected_body import (
    SelectedBodyDirectIntrinsicOperationPackageEntryIr,
)


type Stage8BackendTranslationRequestInventoryState = Literal[
    "has_accepted_backend_scoped_requests", "no_accepted_backend_scoped_requests"
]
type Stage8BackendTranslationRequestKind = Literal[
    "exact_array_backend_value_uninit_array", "selected_body_direct_intrinsic_handoff"
]
type Stage8BackendTranslationNoRequestReason = Literal["no_accepted_backend_scoped_request"]


class _KeyComparable:
    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and getattr(self, "key") == getattr(other, "key")

    def __hash__(self) -> int:
        return hash(getattr(self, "key"))


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationRequestRecordIr(_KeyComparable):
    source_manifest: Stage8LoweringCompletionManifestIr
    source_package_record: Stage8LoweringCompletionManifestPackageRecordIr
    source_package: LoweringOperationPackageIr
    kind: Stage8BackendTranslationRequestKind
    source_gap_inventory: Stage8LoweringCompletionGapInventoryIr | None = None
    source_gap_record: Stage8LoweringCompletionGapRecordIr | None = None
    source_unresolved_dependency_record: Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr | None = None
    source_dependency_request: ExactArrayBackendHandoffUnresolvedDependencyRequestIr | None = None
    source_selected_body_entry: SelectedBodyDirectIntrinsicOperationPackageEntryIr | None = None

    def __post_init__(self) -> None:
        diagnostics = _validate_request_record(self.source_manifest, self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_manifest.candidate_id

    @property
    def source_location(self) -> SourceLocation | None:
        return self.source_package.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_request_record",
            self.candidate_id,
            self.kind,
            self.source_package_record.source_family,
            source_location_key(self.source_package.source_location),
            None
            if self.source_dependency_request is None
            else (
                self.source_dependency_request.kind,
                self.source_dependency_request.request_kind,
                self.source_dependency_request.policy,
                self.source_dependency_request.source_location.sort_key(),
            ),
            None
            if self.source_selected_body_entry is None
            else source_location_key(self.source_selected_body_entry.source_location),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationNoRequestRecordIr(_KeyComparable):
    source_manifest: Stage8LoweringCompletionManifestIr
    source_package_record: Stage8LoweringCompletionManifestPackageRecordIr
    source_package: LoweringOperationPackageIr
    reason: Stage8BackendTranslationNoRequestReason = (
        "no_accepted_backend_scoped_request"
    )

    def __post_init__(self) -> None:
        diagnostics = _validate_no_request_record(self.source_manifest, self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_manifest.candidate_id

    @property
    def source_location(self) -> SourceLocation | None:
        return self.source_package.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_no_request_record",
            self.candidate_id,
            self.reason,
            self.source_package_record.source_family,
            source_location_key(self.source_package.source_location),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationRequestInventoryIr(_KeyComparable):
    candidate_id: str
    source_location: SourceLocation | None
    inventory_state: Stage8BackendTranslationRequestInventoryState
    source_manifest: Stage8LoweringCompletionManifestIr
    source_gap_inventory: Stage8LoweringCompletionGapInventoryIr
    request_records: tuple[Stage8BackendTranslationRequestRecordIr, ...] = ()
    no_request_records: tuple[Stage8BackendTranslationNoRequestRecordIr, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "Stage 8 backend-translation request inventory candidate id "
                "must be non-empty"
            )
        object.__setattr__(self, "request_records", tuple(self.request_records))
        object.__setattr__(self, "no_request_records", tuple(self.no_request_records))
        diagnostics = validate_stage8_backend_translation_request_inventory(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_request_inventory",
            self.candidate_id,
            source_location_key(self.source_location),
            self.inventory_state,
            tuple(record.key for record in self.request_records),
            tuple(record.key for record in self.no_request_records),
        )


def lower_stage8_backend_translation_request_inventory(
    source: object,
    *,
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    if isinstance(source, Stage8BackendTranslationRequestInventoryIr):
        return _validate_existing_inventory(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
        )

    source_result = _gap_inventory_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    manifest, gap_inventory = source_result.unwrap()

    diagnostics = _validate_source_context(
        manifest,
        gap_inventory,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    try:
        request_records, no_request_records = _inventory_records(
            manifest,
            gap_inventory,
        )
        inventory = Stage8BackendTranslationRequestInventoryIr(
            candidate_id=candidate_id or manifest.candidate_id,
            source_location=source_location or gap_inventory.source_location,
            inventory_state=(
                "has_accepted_backend_scoped_requests"
                if request_records
                else "no_accepted_backend_scoped_requests"
            ),
            source_manifest=manifest,
            source_gap_inventory=gap_inventory,
            request_records=request_records,
            no_request_records=no_request_records,
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _request_inventory_malformed_diagnostic(
                    str(exc),
                    source_location
                    or gap_inventory.source_location
                    or manifest.source_location,
                ),
            )
        )
    return Result.ok(inventory)


def validate_stage8_backend_translation_request_inventory(
    inventory: Stage8BackendTranslationRequestInventoryIr,
) -> tuple[Diagnostic, ...]:
    manifest = inventory.source_manifest
    gap_inventory = inventory.source_gap_inventory
    diagnostics = _validate_source_context(
        manifest,
        gap_inventory,
        explicit_candidate_id=inventory.candidate_id,
        explicit_source_location=inventory.source_location,
    )
    if diagnostics:
        return diagnostics

    expected_request_records, expected_no_request_records = _inventory_records(
        manifest,
        gap_inventory,
    )
    if len(inventory.request_records) != len(expected_request_records):
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory requires one "
                "request record for each accepted backend-scoped request fact",
                inventory.source_location,
            ),
        )
    if len(inventory.no_request_records) != len(expected_no_request_records):
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory requires one "
                "no-request record for each accepted package without a "
                "backend-scoped request fact",
                inventory.source_location,
            ),
        )
    expected_state: Stage8BackendTranslationRequestInventoryState = (
        "has_accepted_backend_scoped_requests"
        if expected_request_records
        else "no_accepted_backend_scoped_requests"
    )
    if inventory.inventory_state != expected_state:
        return (
            _request_inventory_context_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory state must "
                "match accepted backend-scoped request facts",
                inventory.source_location,
            ),
        )

    for actual, expected in zip(
        inventory.request_records,
        expected_request_records,
        strict=True,
    ):
        if actual is not expected:
            diagnostics = _validate_request_record_against_expected(
                actual,
                expected,
            )
            if diagnostics:
                return diagnostics
        diagnostics = _validate_request_record(manifest, actual)
        if diagnostics:
            return diagnostics
    for actual_no_request, expected_no_request in zip(
        inventory.no_request_records,
        expected_no_request_records,
        strict=True,
    ):
        if actual_no_request is not expected_no_request:
            diagnostics = _validate_no_request_record_against_expected(
                actual_no_request,
                expected_no_request,
            )
            if diagnostics:
                return diagnostics
        diagnostics = _validate_no_request_record(manifest, actual_no_request)
        if diagnostics:
            return diagnostics
    return ()


def _validate_existing_inventory(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
) -> Result[Stage8BackendTranslationRequestInventoryIr]:
    if candidate_id is not None and candidate_id != inventory.candidate_id:
        return Result.failure(
            (
                _request_inventory_context_mismatch_diagnostic(
                    "Stage 8 backend-translation request inventory candidate "
                    "context must match the existing inventory",
                    inventory.source_location,
                ),
            )
        )
    if source_location is not None and source_location != inventory.source_location:
        return Result.failure(
            (
                _request_inventory_source_location_mismatch_diagnostic(
                    "Stage 8 backend-translation request inventory source "
                    "location must match the existing inventory",
                    inventory.source_location,
                ),
            )
        )
    diagnostics = validate_stage8_backend_translation_request_inventory(inventory)
    if diagnostics:
        return Result.failure(diagnostics)
    return Result.ok(inventory)


def _validate_source_context(
    manifest: Stage8LoweringCompletionManifestIr,
    gap_inventory: Stage8LoweringCompletionGapInventoryIr,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    manifest_diagnostics = validate_stage8_lowering_completion_manifest(manifest)
    if manifest_diagnostics:
        return (
            _request_inventory_malformed_diagnostic(
                manifest_diagnostics[0].message,
                manifest.source_location,
            ),
        )
    gap_diagnostics = validate_stage8_lowering_completion_gap_inventory(
        gap_inventory,
    )
    if gap_diagnostics:
        return (
            _request_inventory_malformed_diagnostic(
                gap_diagnostics[0].message,
                gap_inventory.source_location,
            ),
        )
    if gap_inventory.source_manifest is not manifest:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory requires the "
                "gap inventory to preserve source manifest object identity",
                gap_inventory.source_location,
            ),
        )
    if explicit_candidate_id is not None and explicit_candidate_id != manifest.candidate_id:
        return (
            _request_inventory_context_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory candidate "
                "context must match the accepted manifest",
                manifest.source_location,
            ),
        )
    if (
        explicit_source_location is not None
        and explicit_source_location != gap_inventory.source_location
    ):
        return (
            _request_inventory_source_location_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory source "
                "location must match the accepted gap inventory",
                gap_inventory.source_location,
            ),
        )
    return ()


def _inventory_records(
    manifest: Stage8LoweringCompletionManifestIr,
    gap_inventory: Stage8LoweringCompletionGapInventoryIr,
) -> tuple[
    tuple[Stage8BackendTranslationRequestRecordIr, ...],
    tuple[Stage8BackendTranslationNoRequestRecordIr, ...],
]:
    request_records: list[Stage8BackendTranslationRequestRecordIr] = []
    no_request_records: list[Stage8BackendTranslationNoRequestRecordIr] = []
    for package_record in manifest.package_records:
        package = package_record.source_package
        if package.source_family == "exact_array_backend_handoff":
            gap_record = _gap_record_for_package(gap_inventory, package)
            request_records.append(
                Stage8BackendTranslationRequestRecordIr(
                    source_manifest=manifest,
                    source_package_record=package_record,
                    source_package=package,
                    kind="exact_array_backend_value_uninit_array",
                    source_gap_inventory=gap_inventory,
                    source_gap_record=gap_record,
                    source_unresolved_dependency_record=(
                        gap_record.source_unresolved_dependency_record
                    ),
                    source_dependency_request=gap_record.source_dependency_request,
                )
            )
        elif package.source_family == "selected_body_direct_intrinsic":
            if package.selected_body_direct_intrinsic is None:
                raise ValueError(
                    "selected-body direct-intrinsic request records require "
                    "an accepted selected-body package entry"
                )
            request_records.append(
                Stage8BackendTranslationRequestRecordIr(
                    source_manifest=manifest,
                    source_package_record=package_record,
                    source_package=package,
                    kind="selected_body_direct_intrinsic_handoff",
                    source_selected_body_entry=(
                        package.selected_body_direct_intrinsic
                    ),
                )
            )
        elif package.source_family == "mini_tsil_leaf_return":
            no_request_records.append(
                Stage8BackendTranslationNoRequestRecordIr(
                    source_manifest=manifest,
                    source_package_record=package_record,
                    source_package=package,
                )
            )
        else:
            raise ValueError(
                "Stage 8 backend-translation request inventory supports only "
                "accepted M86, M92, and M95 package families"
            )
    return (tuple(request_records), tuple(no_request_records))


def _gap_record_for_package(
    gap_inventory: Stage8LoweringCompletionGapInventoryIr,
    package: LoweringOperationPackageIr,
) -> Stage8LoweringCompletionGapRecordIr:
    matches = tuple(
        record
        for record in gap_inventory.gap_records
        if record.source_package is package
    )
    if len(matches) != 1:
        raise ValueError(
            "exact-array backend request records require exactly one accepted "
            "gap record preserving the package object identity"
        )
    return matches[0]


def _validate_request_record(
    manifest: Stage8LoweringCompletionManifestIr,
    record: Stage8BackendTranslationRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    diagnostics = _validate_record_package_identity(
        manifest,
        record.source_package_record,
        record.source_package,
        record.source_location,
    )
    if diagnostics:
        return diagnostics
    if record.kind == "exact_array_backend_value_uninit_array":
        return _validate_exact_array_request_record(manifest, record)
    if record.kind == "selected_body_direct_intrinsic_handoff":
        return _validate_selected_body_request_record(manifest, record)
    return (
        _request_inventory_malformed_diagnostic(
            "Stage 8 backend-translation request records support only "
            "accepted backend-scoped request kinds",
            record.source_location,
        ),
    )


def _validate_exact_array_request_record(
    manifest: Stage8LoweringCompletionManifestIr,
    record: Stage8BackendTranslationRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    package = record.source_package
    if package.source_family != "exact_array_backend_handoff":
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records require an exact-array "
                "backend-handoff operation package",
                record.source_location,
            ),
        )
    if record.source_gap_inventory is None or record.source_gap_record is None:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records require accepted gap inventory "
                "and gap record provenance",
                record.source_location,
            ),
        )
    if record.source_gap_inventory.source_manifest is not manifest:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records must preserve gap inventory to "
                "manifest object identity",
                record.source_location,
            ),
        )
    if record.source_gap_record.source_package is not package:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records must preserve gap record to "
                "package object identity",
                record.source_location,
            ),
        )
    if (
        record.source_unresolved_dependency_record
        is not record.source_gap_record.source_unresolved_dependency_record
    ):
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records must preserve manifest "
                "unresolved dependency record object identity",
                record.source_location,
            ),
        )
    if (
        record.source_dependency_request
        is not record.source_gap_record.source_dependency_request
    ):
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "exact-array request records must preserve source dependency "
                "request object identity",
                record.source_location,
            ),
        )
    if record.source_selected_body_entry is not None:
        return (
            _request_inventory_malformed_diagnostic(
                "exact-array request records must not carry selected-body "
                "direct-intrinsic entries",
                record.source_location,
            ),
        )
    return ()


def _validate_selected_body_request_record(
    manifest: Stage8LoweringCompletionManifestIr,
    record: Stage8BackendTranslationRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    package = record.source_package
    if package.source_family != "selected_body_direct_intrinsic":
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "selected-body request records require a selected-body "
                "direct-intrinsic operation package",
                record.source_location,
            ),
        )
    if record.source_selected_body_entry is not package.selected_body_direct_intrinsic:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "selected-body request records must preserve selected-body "
                "package entry object identity",
                record.source_location,
            ),
        )
    if (
        record.source_gap_inventory is not None
        or record.source_gap_record is not None
        or record.source_unresolved_dependency_record is not None
        or record.source_dependency_request is not None
    ):
        return (
            _request_inventory_malformed_diagnostic(
                "selected-body request records must not carry exact-array "
                "dependency provenance",
                record.source_location,
            ),
        )
    if record.source_package_record not in manifest.package_records:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "selected-body request records must come from manifest "
                "package records",
                record.source_location,
            ),
        )
    return ()


def _validate_no_request_record(
    manifest: Stage8LoweringCompletionManifestIr,
    record: Stage8BackendTranslationNoRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    diagnostics = _validate_record_package_identity(
        manifest,
        record.source_package_record,
        record.source_package,
        record.source_location,
    )
    if diagnostics:
        return diagnostics
    if record.reason != "no_accepted_backend_scoped_request":
        return (
            _request_inventory_malformed_diagnostic(
                "Stage 8 backend-translation no-request records support only "
                "no_accepted_backend_scoped_request",
                record.source_location,
            ),
        )
    if record.source_package.source_family != "mini_tsil_leaf_return":
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation no-request records are reserved "
                "for accepted packages with no backend-scoped request facts",
                record.source_location,
            ),
        )
    return ()


def _validate_record_package_identity(
    manifest: Stage8LoweringCompletionManifestIr,
    package_record: Stage8LoweringCompletionManifestPackageRecordIr,
    package: LoweringOperationPackageIr,
    location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    if package_record not in manifest.package_records or not any(
        package_record is accepted_record
        for accepted_record in manifest.package_records
    ):
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory records must "
                "preserve manifest package record object identity",
                location,
            ),
        )
    if package_record.source_package is not package:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request inventory records must "
                "preserve package record to package object identity",
                location,
            ),
        )
    return ()


def _validate_request_record_against_expected(
    actual: Stage8BackendTranslationRequestRecordIr,
    expected: Stage8BackendTranslationRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    if actual.kind != expected.kind:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation request record kind must match "
                "accepted package facts",
                actual.source_location,
            ),
        )
    identity_pairs: tuple[tuple[object | None, object | None, str], ...] = (
        (
            actual.source_manifest,
            expected.source_manifest,
            "source manifest object identity",
        ),
        (
            actual.source_package_record,
            expected.source_package_record,
            "manifest package record object identity",
        ),
        (actual.source_package, expected.source_package, "source package identity"),
        (
            actual.source_gap_inventory,
            expected.source_gap_inventory,
            "gap inventory object identity",
        ),
        (
            actual.source_gap_record,
            expected.source_gap_record,
            "gap record object identity",
        ),
        (
            actual.source_unresolved_dependency_record,
            expected.source_unresolved_dependency_record,
            "unresolved dependency record object identity",
        ),
        (
            actual.source_dependency_request,
            expected.source_dependency_request,
            "source dependency request object identity",
        ),
        (
            actual.source_selected_body_entry,
            expected.source_selected_body_entry,
            "selected-body package entry object identity",
        ),
    )
    for actual_value, expected_value, label in identity_pairs:
        if actual_value is not expected_value:
            return (
                _request_inventory_provenance_mismatch_diagnostic(
                    "Stage 8 backend-translation request records must "
                    f"preserve {label}",
                    actual.source_location,
                ),
            )
    return ()


def _validate_no_request_record_against_expected(
    actual: Stage8BackendTranslationNoRequestRecordIr,
    expected: Stage8BackendTranslationNoRequestRecordIr,
) -> tuple[Diagnostic, ...]:
    if actual.reason != expected.reason:
        return (
            _request_inventory_provenance_mismatch_diagnostic(
                "Stage 8 backend-translation no-request record reason must "
                "match accepted package facts",
                actual.source_location,
            ),
        )
    identity_pairs: tuple[tuple[object, object, str], ...] = (
        (
            actual.source_manifest,
            expected.source_manifest,
            "source manifest object identity",
        ),
        (
            actual.source_package_record,
            expected.source_package_record,
            "manifest package record object identity",
        ),
        (actual.source_package, expected.source_package, "source package identity"),
    )
    for actual_value, expected_value, label in identity_pairs:
        if actual_value is not expected_value:
            return (
                _request_inventory_provenance_mismatch_diagnostic(
                    "Stage 8 backend-translation no-request records must "
                    f"preserve {label}",
                    actual.source_location,
                ),
            )
    return ()

