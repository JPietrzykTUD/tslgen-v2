from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
    ExactArrayBackendDeferredRequestInventoryMemberIr,
)
from tslgen.lowering._array_body_completion_package import (
    ExactArrayLoweringCompletionPackageIr,
    ExactArrayLoweringUnresolvedDependencyIr,
)
from tslgen.lowering._array_body_models import (
    ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperRequestRecord,
)
from tslgen.lowering._array_body_package import ExactArrayBodyStructuralPackageIr


type ExactArrayBackendHandoffDependencyKind = Literal[
    "value_backend_uninit_array",
]
type ExactArrayBackendHandoffDependencyPolicy = Literal[
    "deferred_backend_value",
]
type ExactArrayBackendHandoffDependencyRequestKind = Literal["backend_value"]


class _ArrayBackendHandoffContext(Protocol):
    @property
    def selected_candidate_id(self) -> str | None: ...

    @property
    def selected_type_tag(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class _DefaultArrayBackendHandoffContext:
    selected_candidate_id: str | None = None
    selected_type_tag: str | None = None


@dataclass(frozen=True, slots=True)
class ExactArrayBackendHandoffUnresolvedDependencyRequestIr:
    kind: ExactArrayBackendHandoffDependencyKind
    request_kind: ExactArrayBackendHandoffDependencyRequestKind
    policy: ExactArrayBackendHandoffDependencyPolicy
    source_location: SourceLocation
    source_completion_dependency: ExactArrayLoweringUnresolvedDependencyIr
    source_inventory_member: ExactArrayBackendDeferredRequestInventoryMemberIr
    source_deferred_backend_uninit: ExactArrayInitializationDeferredBackendUninitValue
    source_request_record: ExactArrayInitializationHelperRequestRecord

    def __post_init__(self) -> None:
        if self.kind != "value_backend_uninit_array":
            raise ValueError(
                "array backend handoff unresolved dependency supports only "
                "value_backend_uninit_array"
            )
        if self.request_kind != "backend_value":
            raise ValueError(
                "array backend handoff unresolved dependency request kind "
                "must be backend_value"
            )
        if self.policy != "deferred_backend_value":
            raise ValueError(
                "array backend handoff unresolved dependency must preserve "
                "the deferred_backend_value policy"
            )
        if not isinstance(
            self.source_completion_dependency,
            ExactArrayLoweringUnresolvedDependencyIr,
        ):
            raise TypeError(
                "array backend handoff dependency request requires the "
                "accepted M90 unresolved dependency"
            )
        dependency = self.source_completion_dependency
        if self.source_inventory_member is not dependency.source_inventory_member:
            raise ValueError(
                "array backend handoff dependency request must preserve the "
                "M90-to-M89 inventory member identity"
            )
        if (
            self.source_deferred_backend_uninit
            is not dependency.source_deferred_backend_uninit
        ):
            raise ValueError(
                "array backend handoff dependency request must preserve the "
                "M90-to-M72 deferred backend-uninit identity"
            )
        if self.source_request_record is not dependency.source_request_record:
            raise ValueError(
                "array backend handoff dependency request must preserve the "
                "M90-to-M67 backend-value request identity"
            )
        if self.source_location != dependency.source_location:
            raise ValueError(
                "array backend handoff dependency request source location "
                "must match the accepted M90 dependency"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_handoff_unresolved_dependency_request_ir",
            self.kind,
            self.request_kind,
            self.policy,
            self.source_location.sort_key(),
            self.source_completion_dependency.key,
            self.source_inventory_member.key,
            self.source_deferred_backend_uninit.key,
            self.source_request_record.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBackendHandoffRequestIr:
    source_completion_package: ExactArrayLoweringCompletionPackageIr
    source_package: ExactArrayBodyStructuralPackageIr
    source_inventory: ExactArrayBackendDeferredRequestInventoryIr
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    value_backend_uninit_array_request: (
        ExactArrayBackendHandoffUnresolvedDependencyRequestIr
    )
    unresolved_dependency_requests: tuple[
        ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
        ...,
    ]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "unresolved_dependency_requests",
            tuple(self.unresolved_dependency_requests),
        )
        _raise_first_handoff_request_validation_error(self)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_handoff_request_ir",
            self.source_completion_package.key,
            self.source_package.key,
            self.source_inventory.key,
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.value_backend_uninit_array_request.key,
            tuple(request.key for request in self.unresolved_dependency_requests),
        )


def lower_exact_array_backend_handoff_request(
    source: object,
    context: _ArrayBackendHandoffContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayBackendHandoffRequestIr]:
    completion_result = _array_backend_handoff_completion_source(source)
    if not completion_result.is_ok:
        return Result.failure(completion_result.diagnostics)
    completion_package = completion_result.unwrap()

    generation_context = context or _DefaultArrayBackendHandoffContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or completion_package.candidate_id
    )
    effective_target_extension = target_extension or completion_package.target_extension
    effective_source_extension = source_extension or completion_package.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or completion_package.selected_type_tag
    )
    if (
        effective_candidate_id != completion_package.candidate_id
        or effective_target_extension != completion_package.target_extension
        or effective_source_extension != completion_package.source_extension
        or effective_type_tag != completion_package.selected_type_tag
    ):
        return Result.failure(
            (
                _array_backend_handoff_context_mismatch_diagnostic(
                    "array backend handoff request requires the typed "
                    "selected candidate context to match the M90 completion "
                    "package candidate id, target extension, source extension, "
                    "and selected type tag",
                    completion_package.source_location,
                ),
            )
        )

    diagnostics = _validate_handoff_completion_package(completion_package)
    if diagnostics:
        return Result.failure(diagnostics)

    completion_dependency = completion_package.value_backend_uninit_array_dependency
    try:
        dependency_request = ExactArrayBackendHandoffUnresolvedDependencyRequestIr(
            kind=completion_dependency.kind,
            request_kind=completion_dependency.request_kind,
            policy=completion_dependency.policy,
            source_location=completion_dependency.source_location,
            source_completion_dependency=completion_dependency,
            source_inventory_member=completion_dependency.source_inventory_member,
            source_deferred_backend_uninit=(
                completion_dependency.source_deferred_backend_uninit
            ),
            source_request_record=completion_dependency.source_request_record,
        )
        return Result.ok(
            ExactArrayBackendHandoffRequestIr(
                source_completion_package=completion_package,
                source_package=completion_package.source_package,
                source_inventory=completion_package.source_inventory,
                source_location=completion_package.source_location,
                candidate_id=completion_package.candidate_id,
                target_extension=completion_package.target_extension,
                source_extension=completion_package.source_extension,
                selected_type_tag=completion_package.selected_type_tag,
                originating_branch_chain_id=(
                    completion_package.originating_branch_chain_id
                ),
                value_backend_uninit_array_request=dependency_request,
                unresolved_dependency_requests=(dependency_request,),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_backend_handoff_provenance_mismatch_diagnostic(
                    str(exc),
                    completion_package.source_location,
                ),
            )
        )


def _array_backend_handoff_completion_source(
    source: object,
) -> Result[ExactArrayLoweringCompletionPackageIr]:
    if isinstance(source, ExactArrayLoweringCompletionPackageIr):
        return Result.ok(source)

    if _is_generation_stage_like(source):
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if (
            stage == "array_lowering_completion_package"
            and isinstance(output, ExactArrayLoweringCompletionPackageIr)
        ):
            return Result.ok(output)
        return Result.failure(
            (
                _array_backend_handoff_source_unsupported_diagnostic(
                    "array backend handoff request consumes accepted M90 "
                    "ExactArrayLoweringCompletionPackageIr values, the "
                    "array_lowering_completion_package stage output, or a "
                    "source carrying exactly one accepted M90 completion "
                    "package",
                    _source_location_from_object(output),
                ),
            )
        )

    if hasattr(source, "array_lowering_completion_packages"):
        raw_packages = getattr(source, "array_lowering_completion_packages")
        if not isinstance(raw_packages, tuple):
            return Result.failure(
                (
                    _array_backend_handoff_source_unsupported_diagnostic(
                        "array backend handoff request requires "
                        "array_lowering_completion_packages to be a tuple "
                        "carrying exactly one accepted M90 "
                        "ExactArrayLoweringCompletionPackageIr value",
                        _source_location_from_object(raw_packages),
                    ),
                )
            )
        packages: tuple[object, ...] = raw_packages
        location = _source_location_from_entries(packages)
        if len(packages) == 0:
            return Result.failure(
                (
                    _array_backend_handoff_completion_missing_diagnostic(
                        "array backend handoff request requires one accepted "
                        "M90 array_lowering_completion_packages entry",
                        location,
                    ),
                )
            )
        if len(packages) > 1:
            return Result.failure(
                (
                    _array_backend_handoff_completion_multiple_diagnostic(
                        "array backend handoff request requires exactly one "
                        "M90 array_lowering_completion_packages entry; got "
                        f"{len(packages)}",
                        location,
                    ),
                )
            )
        package = packages[0]
        if not isinstance(package, ExactArrayLoweringCompletionPackageIr):
            return Result.failure(
                (
                    _array_backend_handoff_source_unsupported_diagnostic(
                        "array backend handoff request requires the single "
                        "array_lowering_completion_packages entry to be an "
                        "accepted M90 ExactArrayLoweringCompletionPackageIr "
                        "value",
                        location or _source_location_from_object(package),
                    ),
                )
            )
        return Result.ok(package)

    return Result.failure(
        (
            _array_backend_handoff_source_unsupported_diagnostic(
                "array backend handoff request consumes only accepted M90 "
                "completion-package typed sources",
                None,
            ),
        )
    )


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _source_location_from_entries(entries: tuple[object, ...]) -> SourceLocation | None:
    for entry in entries:
        location = _source_location_from_object(entry)
        if location is not None:
            return location
    return None


def _source_location_from_object(source: object) -> SourceLocation | None:
    location = getattr(source, "source_location", None)
    if isinstance(location, SourceLocation):
        return location
    return None


def _validate_handoff_completion_package(
    completion_package: ExactArrayLoweringCompletionPackageIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(
        completion_package.source_package,
        ExactArrayBodyStructuralPackageIr,
    ):
        diagnostics.append(
            _array_backend_handoff_provenance_mismatch_diagnostic(
                "array backend handoff request requires the accepted M88 "
                "structural package from the M90 completion package",
                completion_package.source_location,
            )
        )
    if not isinstance(
        completion_package.source_inventory,
        ExactArrayBackendDeferredRequestInventoryIr,
    ):
        diagnostics.append(
            _array_backend_handoff_provenance_mismatch_diagnostic(
                "array backend handoff request requires the accepted M89 "
                "inventory from the M90 completion package",
                completion_package.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)

    if completion_package.source_inventory.source_package is not (
        completion_package.source_package
    ):
        diagnostics.append(
            _array_backend_handoff_provenance_mismatch_diagnostic(
                "array backend handoff request must preserve the accepted "
                "M90-to-M89-to-M88 package identity chain",
                completion_package.source_location,
            )
        )
    if completion_package.source_location != completion_package.source_inventory.source_location:
        diagnostics.append(
            _array_backend_handoff_source_location_mismatch_diagnostic(
                "array backend handoff request source location must match "
                "the accepted M89 inventory source location",
                completion_package.source_location,
            )
        )

    expected_context = (
        completion_package.source_inventory.candidate_id,
        completion_package.source_inventory.target_extension,
        completion_package.source_inventory.source_extension,
        completion_package.source_inventory.selected_type_tag,
        completion_package.source_inventory.originating_branch_chain_id,
    )
    actual_context = (
        completion_package.candidate_id,
        completion_package.target_extension,
        completion_package.source_extension,
        completion_package.selected_type_tag,
        completion_package.originating_branch_chain_id,
    )
    if actual_context != expected_context:
        diagnostics.append(
            _array_backend_handoff_context_mismatch_diagnostic(
                "array backend handoff request requires the accepted M90 "
                "completion package context to match the M89 inventory",
                completion_package.source_location,
            )
        )

    dependency = completion_package.value_backend_uninit_array_dependency
    if not isinstance(dependency, ExactArrayLoweringUnresolvedDependencyIr):
        diagnostics.append(
            _array_backend_handoff_dependency_set_mismatch_diagnostic(
                "array backend handoff request requires the accepted M90 "
                "value_backend_uninit_array unresolved dependency",
                completion_package.source_location,
            )
        )
        return tuple(diagnostics)
    if completion_package.unresolved_dependencies != (dependency,):
        diagnostics.append(
            _array_backend_handoff_dependency_set_mismatch_diagnostic(
                "array backend handoff request supports exactly one accepted "
                "M90 unresolved dependency",
                completion_package.source_location,
            )
        )
    if dependency.kind != "value_backend_uninit_array" or (
        dependency.request_kind != "backend_value"
    ):
        diagnostics.append(
            _array_backend_handoff_dependency_set_mismatch_diagnostic(
                "array backend handoff request supports only the accepted M90 "
                "value_backend_uninit_array backend-value dependency",
                dependency.source_location,
            )
        )
    if dependency.policy != "deferred_backend_value":
        diagnostics.append(
            _array_backend_handoff_policy_mismatch_diagnostic(
                "array backend handoff request preserves only the accepted "
                "M90 deferred_backend_value policy as unresolved dependency "
                "provenance",
                dependency.source_location,
            )
        )
    inventory_member = completion_package.source_inventory.value_backend_uninit_array
    if (
        dependency.source_inventory_member is not inventory_member
        or dependency.source_deferred_backend_uninit
        is not inventory_member.source_deferred_backend_uninit
        or dependency.source_request_record is not inventory_member.source_request_record
    ):
        diagnostics.append(
            _array_backend_handoff_provenance_mismatch_diagnostic(
                "array backend handoff request must preserve the accepted "
                "M90 unresolved dependency references to M89, M72, and M67 "
                "objects",
                dependency.source_location,
            )
        )
    if dependency.source_location != inventory_member.source_location:
        diagnostics.append(
            _array_backend_handoff_source_location_mismatch_diagnostic(
                "array backend handoff request dependency source location "
                "must match the accepted M89 member source location",
                dependency.source_location,
            )
        )
    return tuple(diagnostics)


def _raise_first_handoff_request_validation_error(
    request: ExactArrayBackendHandoffRequestIr,
) -> None:
    if not isinstance(
        request.source_completion_package,
        ExactArrayLoweringCompletionPackageIr,
    ):
        raise TypeError("array backend handoff request requires an M90 package")
    completion_package = request.source_completion_package
    if request.source_package is not completion_package.source_package:
        raise ValueError(
            "array backend handoff request must preserve M90-to-M88 identity"
        )
    if request.source_inventory is not completion_package.source_inventory:
        raise ValueError(
            "array backend handoff request must preserve M90-to-M89 identity"
        )
    if request.source_location != completion_package.source_location:
        raise ValueError(
            "array backend handoff request source location must match M90 package"
        )
    expected_context = (
        completion_package.candidate_id,
        completion_package.target_extension,
        completion_package.source_extension,
        completion_package.selected_type_tag,
        completion_package.originating_branch_chain_id,
    )
    actual_context = (
        request.candidate_id,
        request.target_extension,
        request.source_extension,
        request.selected_type_tag,
        request.originating_branch_chain_id,
    )
    if actual_context != expected_context:
        raise ValueError(
            "array backend handoff request context must match M90 package"
        )
    if not isinstance(
        request.value_backend_uninit_array_request,
        ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
    ):
        raise TypeError(
            "array backend handoff request requires one unresolved dependency "
            "request"
        )
    if request.unresolved_dependency_requests != (
        request.value_backend_uninit_array_request,
    ):
        raise ValueError(
            "array backend handoff request supports exactly one unresolved "
            "dependency request"
        )
    completion_dependency = (
        completion_package.value_backend_uninit_array_dependency
    )
    dependency_request = request.value_backend_uninit_array_request
    if dependency_request.source_completion_dependency is not completion_dependency:
        raise ValueError(
            "array backend handoff request must preserve M90 dependency identity"
        )
    if dependency_request.source_inventory_member is not (
        completion_package.source_inventory.value_backend_uninit_array
    ):
        raise ValueError(
            "array backend handoff request must preserve M89 member identity"
        )
    if dependency_request.source_deferred_backend_uninit is not (
        completion_dependency.source_deferred_backend_uninit
    ):
        raise ValueError(
            "array backend handoff request must preserve M72 deferred value identity"
        )
    if dependency_request.source_request_record is not (
        completion_dependency.source_request_record
    ):
        raise ValueError(
            "array backend handoff request must preserve M67 request identity"
        )


def _array_backend_handoff_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_backend_handoff_completion_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-COMPLETION-MISSING",
        detail,
        location=location,
    )


def _array_backend_handoff_completion_multiple_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-COMPLETION-MULTIPLE",
        detail,
        location=location,
    )


def _array_backend_handoff_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_handoff_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_handoff_dependency_set_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-DEPENDENCY-SET-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_handoff_policy_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-POLICY-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_handoff_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-HANDOFF-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )
