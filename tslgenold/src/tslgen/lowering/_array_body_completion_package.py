from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
    ExactArrayBackendDeferredRequestInventoryMemberIr,
)
from tslgen.lowering._array_body_models import (
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
)
from tslgen.lowering._array_body_package import (
    ExactArrayBodyStructuralPackageIr,
    ExactArrayBodyStructuralPackageMember,
)


type ExactArrayLoweringUnresolvedDependencyKind = Literal[
    "value_backend_uninit_array",
]
type ExactArrayLoweringUnresolvedDependencyPolicy = Literal[
    "deferred_backend_value",
]
type ExactArrayLoweringUnresolvedDependencyRequestKind = Literal["backend_value"]


class _ArrayLoweringCompletionPackageContext(Protocol):
    @property
    def selected_candidate_id(self) -> str | None: ...

    @property
    def selected_type_tag(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class _DefaultArrayLoweringCompletionPackageContext:
    selected_candidate_id: str | None = None
    selected_type_tag: str | None = None


@dataclass(frozen=True, slots=True)
class ExactArrayLoweringUnresolvedDependencyIr:
    kind: ExactArrayLoweringUnresolvedDependencyKind
    request_kind: ExactArrayLoweringUnresolvedDependencyRequestKind
    policy: ExactArrayLoweringUnresolvedDependencyPolicy
    source_location: SourceLocation
    source_inventory_member: ExactArrayBackendDeferredRequestInventoryMemberIr
    source_deferred_backend_uninit: ExactArrayInitializationDeferredBackendUninitValue
    source_request_record: ExactArrayInitializationHelperRequestRecord

    def __post_init__(self) -> None:
        if self.kind != "value_backend_uninit_array":
            raise ValueError(
                "array lowering unresolved dependency supports only "
                "value_backend_uninit_array"
            )
        if self.request_kind != "backend_value":
            raise ValueError(
                "array lowering unresolved dependency request kind must be "
                "backend_value"
            )
        if self.policy != "deferred_backend_value":
            raise ValueError(
                "array lowering unresolved dependency must preserve the "
                "deferred_backend_value policy"
            )
        if not isinstance(
            self.source_inventory_member,
            ExactArrayBackendDeferredRequestInventoryMemberIr,
        ):
            raise TypeError(
                "array lowering unresolved dependency requires the accepted "
                "M89 backend-deferred inventory member"
            )
        member = self.source_inventory_member
        if self.source_deferred_backend_uninit is not (
            member.source_deferred_backend_uninit
        ):
            raise ValueError(
                "array lowering unresolved dependency must preserve the "
                "M89-to-M72 deferred backend-uninit identity"
            )
        if self.source_request_record is not member.source_request_record:
            raise ValueError(
                "array lowering unresolved dependency must preserve the "
                "M89-to-M67 backend-value request identity"
            )
        if self.source_location != member.source_location:
            raise ValueError(
                "array lowering unresolved dependency source location must "
                "match the accepted M89 inventory member"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_lowering_unresolved_dependency_ir",
            self.kind,
            self.request_kind,
            self.policy,
            self.source_location.sort_key(),
            self.source_inventory_member.key,
            self.source_deferred_backend_uninit.key,
            self.source_request_record.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayLoweringCompletionPackageIr:
    source_package: ExactArrayBodyStructuralPackageIr
    source_inventory: ExactArrayBackendDeferredRequestInventoryIr
    source_declaration_shell: ExactArrayInitializationDeclarationShellIr
    source_helper_set_completion: ExactArrayInitializationHelperSetCompletionIr
    package_members: tuple[ExactArrayBodyStructuralPackageMember, ...]
    value_backend_uninit_array_dependency: ExactArrayLoweringUnresolvedDependencyIr
    unresolved_dependencies: tuple[ExactArrayLoweringUnresolvedDependencyIr, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_members", tuple(self.package_members))
        object.__setattr__(
            self,
            "unresolved_dependencies",
            tuple(self.unresolved_dependencies),
        )
        _raise_first_completion_package_validation_error(self)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_lowering_completion_package_ir",
            self.source_package.key,
            self.source_inventory.key,
            self.source_declaration_shell.key,
            self.source_helper_set_completion.key,
            tuple(member.key for member in self.package_members),
            self.value_backend_uninit_array_dependency.key,
            tuple(dependency.key for dependency in self.unresolved_dependencies),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


def lower_exact_array_lowering_completion_package(
    source: object,
    context: _ArrayLoweringCompletionPackageContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayLoweringCompletionPackageIr]:
    source_result = _array_lowering_completion_package_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    package, inventory = source_result.unwrap()

    generation_context = (
        context or _DefaultArrayLoweringCompletionPackageContext()
    )
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or inventory.candidate_id
    )
    effective_target_extension = target_extension or inventory.target_extension
    effective_source_extension = source_extension or inventory.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or inventory.selected_type_tag
    )
    if (
        effective_candidate_id != inventory.candidate_id
        or effective_target_extension != inventory.target_extension
        or effective_source_extension != inventory.source_extension
        or effective_type_tag != inventory.selected_type_tag
    ):
        return Result.failure(
            (
                _array_lowering_completion_context_mismatch_diagnostic(
                    "array lowering completion package requires the typed "
                    "selected candidate context to match the M89 inventory "
                    "candidate id, target extension, source extension, and "
                    "selected type tag",
                    inventory.source_location,
                ),
            )
        )

    diagnostics = _validate_completion_package_inputs(package, inventory)
    if diagnostics:
        return Result.failure(diagnostics)

    member = inventory.value_backend_uninit_array
    try:
        dependency = ExactArrayLoweringUnresolvedDependencyIr(
            kind="value_backend_uninit_array",
            request_kind=member.request_kind,
            policy=member.policy,
            source_location=member.source_location,
            source_inventory_member=member,
            source_deferred_backend_uninit=member.source_deferred_backend_uninit,
            source_request_record=member.source_request_record,
        )
        return Result.ok(
            ExactArrayLoweringCompletionPackageIr(
                source_package=package,
                source_inventory=inventory,
                source_declaration_shell=package.declaration_shell,
                source_helper_set_completion=package.helper_set_completion,
                package_members=package.members,
                value_backend_uninit_array_dependency=dependency,
                unresolved_dependencies=(dependency,),
                source_location=inventory.source_location,
                candidate_id=inventory.candidate_id,
                target_extension=inventory.target_extension,
                source_extension=inventory.source_extension,
                selected_type_tag=inventory.selected_type_tag,
                originating_branch_chain_id=inventory.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_lowering_completion_provenance_mismatch_diagnostic(
                    str(exc),
                    inventory.source_location,
                ),
            )
        )


def _array_lowering_completion_package_source(
    source: object,
) -> Result[
    tuple[ExactArrayBodyStructuralPackageIr, ExactArrayBackendDeferredRequestInventoryIr]
]:
    if isinstance(source, ExactArrayBackendDeferredRequestInventoryIr):
        return _package_and_inventory_from_inventory(source)

    if _is_generation_stage_like(source):
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if (
            stage == "array_backend_deferred_request_inventory"
            and isinstance(output, ExactArrayBackendDeferredRequestInventoryIr)
        ):
            return _package_and_inventory_from_inventory(output)
        return Result.failure(
            (
                _array_lowering_completion_source_unsupported_diagnostic(
                    "array lowering completion package consumes accepted M89 "
                    "ExactArrayBackendDeferredRequestInventoryIr values, the "
                    "array_backend_deferred_request_inventory stage output, "
                    "or a source carrying exactly one accepted M88 package "
                    "and one matching accepted M89 inventory",
                    _source_location_from_object(output),
                ),
            )
        )

    has_packages = hasattr(source, "array_body_structural_packages")
    has_inventories = hasattr(source, "array_backend_deferred_request_inventories")
    if has_packages or has_inventories:
        package_result = _single_package_from_source(source, has_packages)
        if not package_result.is_ok:
            return Result.failure(package_result.diagnostics)
        inventory_result = _single_inventory_from_source(source, has_inventories)
        if not inventory_result.is_ok:
            return Result.failure(inventory_result.diagnostics)
        package = package_result.unwrap()
        inventory = inventory_result.unwrap()
        if inventory.source_package is not package:
            return Result.failure(
                (
                    _array_lowering_completion_package_inventory_mismatch_diagnostic(
                        "array lowering completion package requires the "
                        "single M89 inventory to reference the same accepted "
                        "M88 package object carried by the source",
                        _source_location_from_object(inventory)
                        or _source_location_from_object(package),
                    ),
                )
            )
        return Result.ok((package, inventory))

    return Result.failure(
        (
            _array_lowering_completion_source_unsupported_diagnostic(
                "array lowering completion package consumes only accepted "
                "M89 backend-deferred inventory typed sources",
                None,
            ),
        )
    )


def _package_and_inventory_from_inventory(
    inventory: ExactArrayBackendDeferredRequestInventoryIr,
) -> Result[
    tuple[ExactArrayBodyStructuralPackageIr, ExactArrayBackendDeferredRequestInventoryIr]
]:
    package = inventory.source_package
    if not isinstance(package, ExactArrayBodyStructuralPackageIr):
        return Result.failure(
            (
                _array_lowering_completion_provenance_mismatch_diagnostic(
                    "array lowering completion package requires the accepted "
                    "M89 inventory to reference an accepted M88 structural "
                    "package",
                    inventory.source_location,
                ),
            )
        )
    return Result.ok((package, inventory))


def _single_package_from_source(
    source: object,
    has_packages: bool,
) -> Result[ExactArrayBodyStructuralPackageIr]:
    if not has_packages:
        return Result.failure(
            (
                _array_lowering_completion_package_missing_diagnostic(
                    "array lowering completion package requires a source "
                    "carrying one accepted M88 array_body_structural_packages "
                    "entry",
                    _source_location_from_object(source),
                ),
            )
        )
    raw_packages = getattr(source, "array_body_structural_packages")
    if not isinstance(raw_packages, tuple):
        return Result.failure(
            (
                _array_lowering_completion_source_unsupported_diagnostic(
                    "array lowering completion package requires "
                    "array_body_structural_packages to be a tuple carrying "
                    "exactly one accepted M88 ExactArrayBodyStructuralPackageIr "
                    "value",
                    _source_location_from_object(raw_packages),
                ),
            )
        )
    packages: tuple[object, ...] = raw_packages
    location = _source_location_from_entries(packages)
    if len(packages) == 0:
        return Result.failure(
            (
                _array_lowering_completion_package_missing_diagnostic(
                    "array lowering completion package requires one accepted "
                    "M88 array_body_structural_packages entry",
                    location,
                ),
            )
        )
    if len(packages) > 1:
        return Result.failure(
            (
                _array_lowering_completion_package_multiple_diagnostic(
                    "array lowering completion package requires exactly one "
                    f"M88 array_body_structural_packages entry; got {len(packages)}",
                    location,
                ),
            )
        )
    package = packages[0]
    if not isinstance(package, ExactArrayBodyStructuralPackageIr):
        return Result.failure(
            (
                _array_lowering_completion_source_unsupported_diagnostic(
                    "array lowering completion package requires the single "
                    "array_body_structural_packages entry to be an accepted "
                    "M88 ExactArrayBodyStructuralPackageIr value",
                    location or _source_location_from_object(package),
                ),
            )
        )
    return Result.ok(package)


def _single_inventory_from_source(
    source: object,
    has_inventories: bool,
) -> Result[ExactArrayBackendDeferredRequestInventoryIr]:
    if not has_inventories:
        return Result.failure(
            (
                _array_lowering_completion_inventory_missing_diagnostic(
                    "array lowering completion package requires a source "
                    "carrying one accepted M89 "
                    "array_backend_deferred_request_inventories entry",
                    _source_location_from_object(source),
                ),
            )
        )
    raw_inventories = getattr(source, "array_backend_deferred_request_inventories")
    if not isinstance(raw_inventories, tuple):
        return Result.failure(
            (
                _array_lowering_completion_source_unsupported_diagnostic(
                    "array lowering completion package requires "
                    "array_backend_deferred_request_inventories to be a tuple "
                    "carrying exactly one accepted M89 "
                    "ExactArrayBackendDeferredRequestInventoryIr value",
                    _source_location_from_object(raw_inventories),
                ),
            )
        )
    inventories: tuple[object, ...] = raw_inventories
    location = _source_location_from_entries(inventories)
    if len(inventories) == 0:
        return Result.failure(
            (
                _array_lowering_completion_inventory_missing_diagnostic(
                    "array lowering completion package requires one accepted "
                    "M89 array_backend_deferred_request_inventories entry",
                    location,
                ),
            )
        )
    if len(inventories) > 1:
        return Result.failure(
            (
                _array_lowering_completion_inventory_multiple_diagnostic(
                    "array lowering completion package requires exactly one "
                    "M89 array_backend_deferred_request_inventories entry; "
                    f"got {len(inventories)}",
                    location,
                ),
            )
        )
    inventory = inventories[0]
    if not isinstance(inventory, ExactArrayBackendDeferredRequestInventoryIr):
        return Result.failure(
            (
                _array_lowering_completion_source_unsupported_diagnostic(
                    "array lowering completion package requires the single "
                    "array_backend_deferred_request_inventories entry to be "
                    "an accepted M89 ExactArrayBackendDeferredRequestInventoryIr "
                    "value",
                    location or _source_location_from_object(inventory),
                ),
            )
        )
    return Result.ok(inventory)


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


def _validate_completion_package_inputs(
    package: ExactArrayBodyStructuralPackageIr,
    inventory: ExactArrayBackendDeferredRequestInventoryIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if inventory.source_package is not package:
        diagnostics.append(
            _array_lowering_completion_package_inventory_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "inventory source_package identity to match the accepted M88 "
                "package",
                inventory.source_location,
            )
        )
    if inventory.source_location != package.source_location:
        diagnostics.append(
            _array_lowering_completion_source_location_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "inventory source location to match the accepted M88 package",
                inventory.source_location,
            )
        )

    expected_context = (
        package.candidate_id,
        package.target_extension,
        package.source_extension,
        package.selected_type_tag,
        package.originating_branch_chain_id,
    )
    actual_context = (
        inventory.candidate_id,
        inventory.target_extension,
        inventory.source_extension,
        inventory.selected_type_tag,
        inventory.originating_branch_chain_id,
    )
    if actual_context != expected_context:
        diagnostics.append(
            _array_lowering_completion_context_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "inventory candidate id, target extension, source extension, "
                "selected type tag, and branch-chain id to match the M88 "
                "package context",
                inventory.source_location,
            )
        )

    if inventory.source_declaration_shell is not package.declaration_shell:
        diagnostics.append(
            _array_lowering_completion_provenance_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "inventory to preserve the M88 declaration-shell identity",
                inventory.source_location,
            )
        )
    if inventory.source_helper_set_completion is not package.helper_set_completion:
        diagnostics.append(
            _array_lowering_completion_provenance_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "inventory to preserve the M88 helper-set completion identity",
                inventory.source_location,
            )
        )
    if tuple(package.members) != package.members:
        diagnostics.append(
            _array_lowering_completion_provenance_mismatch_diagnostic(
                "array lowering completion package requires stable M88 package "
                "member references",
                package.source_location,
            )
        )

    member = inventory.value_backend_uninit_array
    if not isinstance(member, ExactArrayBackendDeferredRequestInventoryMemberIr):
        diagnostics.append(
            _array_lowering_completion_member_set_mismatch_diagnostic(
                "array lowering completion package requires the accepted M89 "
                "value_backend_uninit_array inventory member",
                inventory.source_location,
            )
        )
        return tuple(diagnostics)
    if inventory.members != (member,):
        diagnostics.append(
            _array_lowering_completion_member_set_mismatch_diagnostic(
                "array lowering completion package supports exactly one "
                "accepted M89 value_backend_uninit_array inventory member",
                inventory.source_location,
            )
        )
    if (
        member.kind != "value_backend_uninit_array"
        or member.request_kind != "backend_value"
    ):
        diagnostics.append(
            _array_lowering_completion_member_set_mismatch_diagnostic(
                "array lowering completion package supports only the accepted "
                "M89 value_backend_uninit_array backend-value member",
                member.source_location,
            )
        )
    if member.policy != "deferred_backend_value":
        diagnostics.append(
            _array_lowering_completion_policy_mismatch_diagnostic(
                "array lowering completion package preserves only the accepted "
                "M89 deferred_backend_value policy as unresolved dependency "
                "provenance",
                member.source_location,
            )
        )
    request_record = member.source_request_record
    expected_request_record = (
        package.helper_set_completion.source_backend_uninit_request
    )
    if (
        member.source_deferred_backend_uninit
        is not package.helper_set_completion.unresolved_backend_uninit
        or request_record is not expected_request_record
    ):
        diagnostics.append(
            _array_lowering_completion_provenance_mismatch_diagnostic(
                "array lowering completion package must preserve the accepted "
                "M89 member references to the M72 deferred value and M67 "
                "backend-value request from the M88 package",
                member.source_location,
            )
        )
    if (
        isinstance(request_record, ExactArrayInitializationHelperRequestRecord)
        and request_record is expected_request_record
        and member.source_location != request_record.leaf_source_location
    ):
        diagnostics.append(
            _array_lowering_completion_source_location_mismatch_diagnostic(
                "array lowering completion package requires the M89 member "
                "source location to match the M67 backend-value request leaf "
                "source location",
                member.source_location,
            )
        )
    return tuple(diagnostics)


def _raise_first_completion_package_validation_error(
    package: ExactArrayLoweringCompletionPackageIr,
) -> None:
    if not isinstance(package.source_package, ExactArrayBodyStructuralPackageIr):
        raise TypeError("array lowering completion package requires an M88 package")
    if not isinstance(
        package.source_inventory,
        ExactArrayBackendDeferredRequestInventoryIr,
    ):
        raise TypeError("array lowering completion package requires an M89 inventory")
    if package.source_inventory.source_package is not package.source_package:
        raise ValueError(
            "array lowering completion package must preserve M88/M89 identity"
        )
    if package.source_declaration_shell is not package.source_package.declaration_shell:
        raise ValueError(
            "array lowering completion package must preserve M73 shell identity"
        )
    if (
        package.source_helper_set_completion
        is not package.source_package.helper_set_completion
    ):
        raise ValueError(
            "array lowering completion package must preserve M72 completion identity"
        )
    if package.package_members != package.source_package.members:
        raise ValueError(
            "array lowering completion package must preserve M88 package members"
        )
    if not isinstance(
        package.value_backend_uninit_array_dependency,
        ExactArrayLoweringUnresolvedDependencyIr,
    ):
        raise TypeError(
            "array lowering completion package requires one unresolved "
            "backend-uninit dependency"
        )
    if package.unresolved_dependencies != (
        package.value_backend_uninit_array_dependency,
    ):
        raise ValueError(
            "array lowering completion package supports exactly one unresolved "
            "backend-uninit dependency"
        )
    member = package.source_inventory.value_backend_uninit_array
    dependency = package.value_backend_uninit_array_dependency
    if (
        dependency.source_inventory_member is not member
        or dependency.source_deferred_backend_uninit
        is not member.source_deferred_backend_uninit
        or dependency.source_request_record is not member.source_request_record
    ):
        raise ValueError(
            "array lowering completion package must preserve M89/M72/M67 "
            "unresolved dependency identity"
        )
    if package.source_location != package.source_inventory.source_location:
        raise ValueError(
            "array lowering completion package source location must match the "
            "M89 inventory"
        )
    expected_context = (
        package.source_inventory.candidate_id,
        package.source_inventory.target_extension,
        package.source_inventory.source_extension,
        package.source_inventory.selected_type_tag,
        package.source_inventory.originating_branch_chain_id,
    )
    actual_context = (
        package.candidate_id,
        package.target_extension,
        package.source_extension,
        package.selected_type_tag,
        package.originating_branch_chain_id,
    )
    if actual_context != expected_context:
        raise ValueError(
            "array lowering completion package context must match the M89 "
            "inventory"
        )


def _array_lowering_completion_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_lowering_completion_package_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-PACKAGE-MISSING",
        detail,
        location=location,
    )


def _array_lowering_completion_package_multiple_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-PACKAGE-MULTIPLE",
        detail,
        location=location,
    )


def _array_lowering_completion_inventory_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-INVENTORY-MISSING",
        detail,
        location=location,
    )


def _array_lowering_completion_inventory_multiple_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-INVENTORY-MULTIPLE",
        detail,
        location=location,
    )


def _array_lowering_completion_package_inventory_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-PACKAGE-INVENTORY-MISMATCH",
        detail,
        location=location,
    )


def _array_lowering_completion_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_lowering_completion_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def _array_lowering_completion_member_set_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-MEMBER-SET-MISMATCH",
        detail,
        location=location,
    )


def _array_lowering_completion_policy_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-POLICY-MISMATCH",
        detail,
        location=location,
    )


def _array_lowering_completion_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-COMPLETION-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )
