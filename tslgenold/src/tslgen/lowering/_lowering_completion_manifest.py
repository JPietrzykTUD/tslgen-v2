from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
    source_location_from_object,
    source_location_key,
)
from tslgen.lowering._operation_package_models import (
    ExactArrayBackendHandoffOperationPackageEntryIr,
    LoweringOperationPackageIr,
    LoweringOperationPackageSourceFamily,
    MiniTsilLeafReturnOperationPackageEntryIr,
)
from tslgen.lowering._operation_package_selected_body import (
    SelectedBodyDirectIntrinsicOperationPackageEntryIr,
)


type Stage8LoweringCompletionManifestState = Literal[
    "stage8_package_provenance_assembled",
]
_SUPPORTED_PACKAGE_FAMILIES: tuple[LoweringOperationPackageSourceFamily, ...] = (
    "mini_tsil_leaf_return",
    "exact_array_backend_handoff",
    "selected_body_direct_intrinsic",
)


@dataclass(frozen=True, slots=True)
class Stage8LoweringCompletionManifestPackageRecordIr:
    source_package: LoweringOperationPackageIr

    def __post_init__(self) -> None:
        if not isinstance(self.source_package, LoweringOperationPackageIr):
            raise TypeError(
                "Stage 8 lowering manifest package records require accepted "
                "LoweringOperationPackageIr values"
            )
        _raise_first_package_validation_error(self.source_package)

    @property
    def candidate_id(self) -> str:
        return self.source_package.candidate_id

    @property
    def source_family(self) -> LoweringOperationPackageSourceFamily:
        return self.source_package.source_family

    @property
    def source_location(self) -> SourceLocation | None:
        return self.source_package.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_lowering_completion_manifest_package_record",
            self.source_package.key,
        )


@dataclass(frozen=True, slots=True)
class Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr:
    source_package: LoweringOperationPackageIr
    source_dependency_request: ExactArrayBackendHandoffUnresolvedDependencyRequestIr

    def __post_init__(self) -> None:
        if not isinstance(self.source_package, LoweringOperationPackageIr):
            raise TypeError(
                "Stage 8 lowering manifest dependency records require accepted "
                "LoweringOperationPackageIr values"
            )
        if not isinstance(
            self.source_dependency_request,
            ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
        ):
            raise TypeError(
                "Stage 8 lowering manifest dependency records require accepted "
                "M92 unresolved dependency requests"
            )
        diagnostics = _validate_exact_array_dependency_record(
            self.source_package,
            self.source_dependency_request,
        )
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_package.candidate_id

    @property
    def kind(self) -> str:
        return self.source_dependency_request.kind

    @property
    def request_kind(self) -> str:
        return self.source_dependency_request.request_kind

    @property
    def policy(self) -> str:
        return self.source_dependency_request.policy

    @property
    def source_location(self) -> SourceLocation:
        return self.source_dependency_request.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_lowering_completion_manifest_unresolved_dependency_record",
            self.source_package.key,
            self.source_dependency_request.key,
        )


@dataclass(frozen=True, slots=True)
class Stage8LoweringCompletionManifestIr:
    candidate_id: str
    source_location: SourceLocation | None
    completion_state: Stage8LoweringCompletionManifestState
    source_packages: tuple[LoweringOperationPackageIr, ...]
    package_records: tuple[Stage8LoweringCompletionManifestPackageRecordIr, ...]
    unresolved_dependency_records: tuple[
        Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr,
        ...,
    ] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("Stage 8 lowering manifest candidate id must be non-empty")
        if self.completion_state != "stage8_package_provenance_assembled":
            raise ValueError(
                "Stage 8 lowering manifest completion state must be "
                "stage8_package_provenance_assembled"
            )
        object.__setattr__(self, "source_packages", tuple(self.source_packages))
        object.__setattr__(self, "package_records", tuple(self.package_records))
        object.__setattr__(
            self,
            "unresolved_dependency_records",
            tuple(self.unresolved_dependency_records),
        )
        diagnostics = validate_stage8_lowering_completion_manifest(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def package_families(self) -> tuple[LoweringOperationPackageSourceFamily, ...]:
        return tuple(record.source_family for record in self.package_records)

    @property
    def has_unresolved_backend_dependencies(self) -> bool:
        return bool(self.unresolved_dependency_records)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_lowering_completion_manifest",
            self.candidate_id,
            source_location_key(self.source_location),
            self.completion_state,
            tuple(package.key for package in self.source_packages),
            tuple(record.key for record in self.package_records),
            tuple(record.key for record in self.unresolved_dependency_records),
        )


def lower_stage8_lowering_completion_manifest(
    source: object,
    *,
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
) -> Result[Stage8LoweringCompletionManifestIr]:
    if isinstance(source, Stage8LoweringCompletionManifestIr):
        return _validate_existing_manifest(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
        )

    package_source = _manifest_package_source(source)
    if not package_source.is_ok:
        return Result.failure(package_source.diagnostics)
    packages = package_source.unwrap()
    if not packages:
        return Result.failure(
            (
                _manifest_missing_value_diagnostic(
                    "Stage 8 lowering manifest requires at least one accepted "
                    "LoweringOperationPackageIr",
                    source_location or source_location_from_object(source),
                ),
            )
        )

    diagnostics = _validate_package_set(
        packages,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    ordered_packages = tuple(sorted(packages, key=lambda package: package.key))
    try:
        package_records = tuple(
            Stage8LoweringCompletionManifestPackageRecordIr(package)
            for package in ordered_packages
        )
        dependency_records = tuple(
            record
            for package in ordered_packages
            for record in _unresolved_dependency_records(package)
        )
        manifest = Stage8LoweringCompletionManifestIr(
            candidate_id=candidate_id or ordered_packages[0].candidate_id,
            source_location=(
                source_location
                or source_location_from_object(source)
                or source_location_from_entries(ordered_packages)
            ),
            completion_state="stage8_package_provenance_assembled",
            source_packages=ordered_packages,
            package_records=package_records,
            unresolved_dependency_records=dependency_records,
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _manifest_malformed_diagnostic(
                    str(exc),
                    source_location
                    or source_location_from_entries(ordered_packages)
                    or source_location_from_object(source),
                ),
            )
        )
    return Result.ok(manifest)


def validate_stage8_lowering_completion_manifest(
    manifest: Stage8LoweringCompletionManifestIr,
) -> tuple[Diagnostic, ...]:
    packages = tuple(manifest.source_packages)
    diagnostics = _validate_package_set(
        packages,
        explicit_candidate_id=manifest.candidate_id,
    )
    if diagnostics:
        return diagnostics
    if len(manifest.package_records) != len(packages):
        return (
            _manifest_malformed_diagnostic(
                "Stage 8 lowering manifest requires one package record for "
                "each source package",
                manifest.source_location,
            ),
        )
    for package, record in zip(packages, manifest.package_records, strict=True):
        if record.source_package is not package:
            return (
                _manifest_provenance_mismatch_diagnostic(
                    "Stage 8 lowering manifest package records must preserve "
                    "source package object identity",
                    manifest.source_location or package.source_location,
                ),
            )
        if record.candidate_id != manifest.candidate_id:
            return (
                _manifest_context_mismatch_diagnostic(
                    "Stage 8 lowering manifest package records must match the "
                    "manifest candidate id",
                    manifest.source_location or record.source_location,
                ),
            )
    expected_dependency_records = tuple(
        record
        for package in packages
        for record in _unresolved_dependency_records(package)
    )
    actual_dependency_records = tuple(manifest.unresolved_dependency_records)
    if len(actual_dependency_records) != len(expected_dependency_records):
        return (
            _manifest_dependency_provenance_mismatch_diagnostic(
                "Stage 8 lowering manifest unresolved dependency records must "
                "preserve the accepted package dependency references",
                manifest.source_location,
            ),
        )
    for actual, expected in zip(
        actual_dependency_records,
        expected_dependency_records,
        strict=True,
    ):
        if (
            actual.source_package is not expected.source_package
            or actual.source_dependency_request
            is not expected.source_dependency_request
        ):
            return (
                _manifest_dependency_provenance_mismatch_diagnostic(
                    "Stage 8 lowering manifest unresolved dependency records "
                    "must preserve source package and dependency request "
                    "object identity",
                    actual.source_location,
                ),
            )
    return ()


def _manifest_package_source(
    source: object,
) -> Result[tuple[LoweringOperationPackageIr, ...]]:
    if isinstance(source, LoweringOperationPackageIr):
        return Result.ok((source,))
    if _is_generation_stage_like(source):
        if _has_operation_package_container(source):
            return Result.failure(
                (
                    _manifest_source_ambiguous_diagnostic(
                        "Stage 8 lowering manifest source must be either a "
                        "lowering_operation_package stage or an operation "
                        "package container, not both",
                        source_location_from_object(source),
                    ),
                )
            )
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if stage != "lowering_operation_package":
            return Result.failure(
                (
                    _manifest_source_unsupported_diagnostic(
                        "Stage 8 lowering manifest consumes only "
                        "lowering_operation_package stages or accepted "
                        "LoweringOperationPackageIr values",
                        source_location_from_object(output),
                    ),
                )
            )
        if not isinstance(output, LoweringOperationPackageIr):
            return Result.failure(
                (
                    _manifest_malformed_diagnostic(
                        "Stage 8 lowering manifest stage output must be an "
                        "accepted LoweringOperationPackageIr",
                        source_location_from_object(output),
                    ),
                )
            )
        return Result.ok((output,))
    if isinstance(source, tuple):
        return _packages_from_tuple(source)
    if _has_operation_package_container(source):
        raw_packages = getattr(source, "operation_packages")
        if not isinstance(raw_packages, tuple):
            return Result.failure(
                (
                    _manifest_malformed_diagnostic(
                        "Stage 8 lowering manifest container requires "
                        "operation_packages to be a tuple",
                        source_location_from_object(raw_packages),
                    ),
                )
            )
        return _packages_from_tuple(raw_packages)
    return Result.failure(
        (
            _manifest_source_unsupported_diagnostic(
                "Stage 8 lowering manifest consumes accepted "
                "LoweringOperationPackageIr values, lowering_operation_package "
                "stages, tuples of packages, or containers with "
                "operation_packages",
                source_location_from_object(source),
            ),
        )
    )


def _packages_from_tuple(
    values: tuple[object, ...],
) -> Result[tuple[LoweringOperationPackageIr, ...]]:
    if not values:
        return Result.ok(())
    packages = tuple(
        value for value in values if isinstance(value, LoweringOperationPackageIr)
    )
    if len(packages) != len(values):
        return Result.failure(
            (
                _manifest_malformed_diagnostic(
                    "Stage 8 lowering manifest package tuples must contain "
                    "only accepted LoweringOperationPackageIr values",
                    source_location_from_entries(values),
                ),
            )
        )
    return Result.ok(packages)


def _validate_existing_manifest(
    manifest: Stage8LoweringCompletionManifestIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
) -> Result[Stage8LoweringCompletionManifestIr]:
    if candidate_id is not None and candidate_id != manifest.candidate_id:
        return Result.failure(
            (
                _manifest_context_mismatch_diagnostic(
                    "Stage 8 lowering manifest candidate context must match "
                    "the existing manifest",
                    manifest.source_location,
                ),
            )
        )
    if source_location is not None and source_location != manifest.source_location:
        return Result.failure(
            (
                _manifest_source_location_mismatch_diagnostic(
                    "Stage 8 lowering manifest source location must match the "
                    "existing manifest",
                    manifest.source_location,
                ),
            )
        )
    diagnostics = validate_stage8_lowering_completion_manifest(manifest)
    if diagnostics:
        return Result.failure(diagnostics)
    return Result.ok(manifest)


def _validate_package_set(
    packages: tuple[LoweringOperationPackageIr, ...],
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None = None,
) -> tuple[Diagnostic, ...]:
    if not packages:
        return (
            _manifest_missing_value_diagnostic(
                "Stage 8 lowering manifest requires at least one accepted "
                "LoweringOperationPackageIr",
                None,
            ),
        )
    candidate_ids = {package.candidate_id for package in packages}
    if len(candidate_ids) != 1:
        return (
            _manifest_context_mismatch_diagnostic(
                "Stage 8 lowering manifest packages must share one candidate id",
                source_location_from_entries(packages),
            ),
        )
    candidate_id = next(iter(candidate_ids))
    if explicit_candidate_id is not None and explicit_candidate_id != candidate_id:
        return (
            _manifest_context_mismatch_diagnostic(
                "Stage 8 lowering manifest candidate context must match the "
                "accepted packages",
                source_location_from_entries(packages),
            ),
        )
    if explicit_source_location is not None:
        package_locations = {package.source_location for package in packages}
        if package_locations != {explicit_source_location}:
            return (
                _manifest_source_location_mismatch_diagnostic(
                    "Stage 8 lowering manifest source location must match the "
                    "accepted packages",
                    source_location_from_entries(packages),
                ),
            )
    for package in packages:
        diagnostics = _validate_manifest_package(package)
        if diagnostics:
            return diagnostics
    package_keys = tuple(package.key for package in packages)
    if len(set(package_keys)) != len(package_keys):
        return (
            _manifest_duplicate_value_diagnostic(
                "Stage 8 lowering manifest requires unique package keys",
                source_location_from_entries(packages),
            ),
        )
    return ()


def _validate_manifest_package(
    package: LoweringOperationPackageIr,
) -> tuple[Diagnostic, ...]:
    if package.source_family not in _SUPPORTED_PACKAGE_FAMILIES:
        return (
            _manifest_source_family_mismatch_diagnostic(
                "Stage 8 lowering manifest supports only accepted M86, M92, "
                "and M95 operation package families",
                package.source_location,
            ),
        )
    try:
        source_entry = package.source_entry
    except (AttributeError, AssertionError, TypeError, ValueError) as exc:
        return (
            _manifest_malformed_diagnostic(
                str(exc),
                package.source_location,
            ),
        )
    if getattr(source_entry, "candidate_id", None) != package.candidate_id:
        return (
            _manifest_context_mismatch_diagnostic(
                "Stage 8 lowering manifest package entry candidate id must "
                "match its package",
                package.source_location,
            ),
        )
    if getattr(source_entry, "source_location", None) != package.source_location:
        return (
            _manifest_source_location_mismatch_diagnostic(
                "Stage 8 lowering manifest package entry source location must "
                "match its package",
                package.source_location,
            ),
        )
    if package.source_family == "mini_tsil_leaf_return" and not isinstance(
        source_entry,
        MiniTsilLeafReturnOperationPackageEntryIr,
    ):
        return _wrong_entry_family_diagnostic(package)
    if package.source_family == "exact_array_backend_handoff":
        if not isinstance(source_entry, ExactArrayBackendHandoffOperationPackageEntryIr):
            return _wrong_entry_family_diagnostic(package)
        return _validate_exact_array_manifest_package(package, source_entry)
    if package.source_family == "selected_body_direct_intrinsic" and not isinstance(
        source_entry,
        SelectedBodyDirectIntrinsicOperationPackageEntryIr,
    ):
        return _wrong_entry_family_diagnostic(package)
    return ()


def _validate_exact_array_manifest_package(
    package: LoweringOperationPackageIr,
    entry: ExactArrayBackendHandoffOperationPackageEntryIr,
) -> tuple[Diagnostic, ...]:
    request = entry.source_request
    if request.candidate_id != package.candidate_id:
        return (
            _manifest_context_mismatch_diagnostic(
                "Stage 8 lowering manifest exact-array package candidate id "
                "must match its M92 request",
                package.source_location,
            ),
        )
    if request.source_location != package.source_location:
        return (
            _manifest_source_location_mismatch_diagnostic(
                "Stage 8 lowering manifest exact-array package source "
                "location must match its M92 request",
                package.source_location,
            ),
        )
    dependency = request.value_backend_uninit_array_request
    return _validate_exact_array_dependency_record(package, dependency)


def _validate_exact_array_dependency_record(
    package: LoweringOperationPackageIr,
    dependency: ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
) -> tuple[Diagnostic, ...]:
    entry = package.exact_array_backend_handoff
    if entry is None:
        return (
            _manifest_dependency_provenance_mismatch_diagnostic(
                "Stage 8 lowering manifest dependency records require an "
                "exact-array backend-handoff package",
                package.source_location,
            ),
        )
    request = entry.source_request
    if not any(
        dependency is unresolved_dependency
        for unresolved_dependency in request.unresolved_dependency_requests
    ):
        return (
            _manifest_dependency_provenance_mismatch_diagnostic(
                "Stage 8 lowering manifest dependency records must preserve "
                "the accepted M92 unresolved dependency request object identity",
                dependency.source_location,
            ),
        )
    completion_dependency = request.source_completion_package
    if (
        dependency.source_completion_dependency
        is not completion_dependency.value_backend_uninit_array_dependency
    ):
        return (
            _manifest_dependency_provenance_mismatch_diagnostic(
                "Stage 8 lowering manifest dependency records must preserve "
                "the M92-to-M90 unresolved dependency identity",
                dependency.source_location,
            ),
        )
    if (
        dependency.source_inventory_member
        is not dependency.source_completion_dependency.source_inventory_member
        or dependency.source_request_record
        is not dependency.source_completion_dependency.source_request_record
    ):
        return (
            _manifest_dependency_provenance_mismatch_diagnostic(
                "Stage 8 lowering manifest dependency records must preserve "
                "the accepted M90/M89/M67 dependency provenance",
                dependency.source_location,
            ),
        )
    return ()


def _unresolved_dependency_records(
    package: LoweringOperationPackageIr,
) -> tuple[Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr, ...]:
    entry = package.exact_array_backend_handoff
    if entry is None:
        return ()
    return tuple(
        Stage8LoweringCompletionManifestUnresolvedDependencyRecordIr(
            source_package=package,
            source_dependency_request=request,
        )
        for request in entry.source_request.unresolved_dependency_requests
    )


def _wrong_entry_family_diagnostic(
    package: LoweringOperationPackageIr,
) -> tuple[Diagnostic, ...]:
    return (
        _manifest_source_family_mismatch_diagnostic(
            "Stage 8 lowering manifest package source family must match its "
            "typed source entry",
            package.source_location,
        ),
    )


def _raise_first_package_validation_error(package: LoweringOperationPackageIr) -> None:
    diagnostics = _validate_manifest_package(package)
    if diagnostics:
        raise ValueError(diagnostics[0].message)


def _has_operation_package_container(source: object) -> bool:
    return hasattr(source, "operation_packages")


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _manifest_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _manifest_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-VALUE-MISSING",
        detail,
        location=location,
    )


def _manifest_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-VALUE-MULTIPLE",
        detail,
        location=location,
    )


def _manifest_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-MALFORMED",
        detail,
        location=location,
    )


def _manifest_source_family_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-SOURCE-FAMILY-MISMATCH",
        detail,
        location=location,
    )


def _manifest_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _manifest_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def _manifest_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _manifest_dependency_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-DEPENDENCY-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _manifest_source_ambiguous_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-COMPLETION-MANIFEST-SOURCE-AMBIGUOUS",
        detail,
        location=location,
    )
