from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_models import (
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationDeferredBackendUninitValue,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationHelperSetCompletionIr,
)
from tslgen.lowering._array_body_package import ExactArrayBodyStructuralPackageIr


type ExactArrayBackendDeferredRequestInventoryMemberKind = Literal[
    "value_backend_uninit_array",
]
type ExactArrayBackendDeferredRequestPolicy = Literal["deferred_backend_value"]
type ExactArrayBackendDeferredRequestKind = Literal["backend_value"]
type _InventorySlotIdentitySource = (
    ExactArrayInitializationHelperSetCompletionIr
    | ExactArrayInitializationDeclarationShellIr
    | ExactArrayInitializationDeferredBackendUninitValue
    | ExactArrayInitializationHelperRequestRecord
)


class _ArrayBackendDeferredRequestInventoryContext(Protocol):
    @property
    def selected_candidate_id(self) -> str | None: ...

    @property
    def selected_type_tag(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class _DefaultArrayBackendDeferredRequestInventoryContext:
    selected_candidate_id: str | None = None
    selected_type_tag: str | None = None


@runtime_checkable
class _ArrayBackendDeferredRequestPackageSource(Protocol):
    @property
    def array_body_structural_packages(
        self,
    ) -> tuple[ExactArrayBodyStructuralPackageIr, ...]: ...


@dataclass(frozen=True, slots=True)
class _ExactArrayBackendDeferredRequestRule:
    member_kind: ExactArrayBackendDeferredRequestInventoryMemberKind
    request_ordinal: int
    request_kind: ExactArrayBackendDeferredRequestKind
    policy: ExactArrayBackendDeferredRequestPolicy
    helper_leaf_kind: Literal["value_backend_uninit_array"]
    expected_leaf_source_text: str


_EXACT_ARRAY_BACKEND_UNINIT_DEFERRED_REQUEST_RULE = (
    _ExactArrayBackendDeferredRequestRule(
        member_kind="value_backend_uninit_array",
        request_ordinal=3,
        request_kind="backend_value",
        policy="deferred_backend_value",
        helper_leaf_kind="value_backend_uninit_array",
        expected_leaf_source_text="value<backend>(uninit::array)",
    )
)


@dataclass(frozen=True, slots=True)
class ExactArrayBackendDeferredRequestInventoryMemberIr:
    kind: ExactArrayBackendDeferredRequestInventoryMemberKind
    request_kind: ExactArrayBackendDeferredRequestKind
    policy: ExactArrayBackendDeferredRequestPolicy
    source_location: SourceLocation
    source_deferred_backend_uninit: ExactArrayInitializationDeferredBackendUninitValue
    source_request_record: ExactArrayInitializationHelperRequestRecord

    def __post_init__(self) -> None:
        if self.kind != "value_backend_uninit_array":
            raise ValueError(
                "array backend-deferred inventory member supports only "
                "value_backend_uninit_array"
            )
        if self.request_kind != "backend_value":
            raise ValueError(
                "array backend-deferred inventory member request kind must be "
                "backend_value"
            )
        if self.policy != "deferred_backend_value":
            raise ValueError(
                "array backend-deferred inventory member must preserve the "
                "deferred_backend_value policy"
            )
        if not isinstance(
            self.source_deferred_backend_uninit,
            ExactArrayInitializationDeferredBackendUninitValue,
        ):
            raise TypeError(
                "array backend-deferred inventory member requires the accepted "
                "M72 deferred backend-uninit value"
            )
        if not isinstance(
            self.source_request_record,
            ExactArrayInitializationHelperRequestRecord,
        ):
            raise TypeError(
                "array backend-deferred inventory member requires the accepted "
                "M67 backend-uninit request record"
            )
        if self.source_location != self.source_deferred_backend_uninit.source_location:
            raise ValueError(
                "array backend-deferred inventory member source location must "
                "match the accepted M72 deferred backend-uninit value"
            )
        if (
            self.source_deferred_backend_uninit.source_backend_uninit_request
            is not self.source_request_record
        ):
            raise ValueError(
                "array backend-deferred inventory member must preserve the "
                "M72-to-M67 request identity"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_deferred_request_inventory_member_ir",
            self.kind,
            self.request_kind,
            self.policy,
            self.source_location.sort_key(),
            self.source_deferred_backend_uninit.key,
            self.source_request_record.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBackendDeferredRequestInventoryIr:
    source_package: ExactArrayBodyStructuralPackageIr
    source_declaration_shell: ExactArrayInitializationDeclarationShellIr
    source_helper_set_completion: ExactArrayInitializationHelperSetCompletionIr
    value_backend_uninit_array: ExactArrayBackendDeferredRequestInventoryMemberIr
    members: tuple[ExactArrayBackendDeferredRequestInventoryMemberIr, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))
        _raise_first_inventory_validation_error(self)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_deferred_request_inventory_ir",
            self.source_package.key,
            self.source_declaration_shell.key,
            self.source_helper_set_completion.key,
            self.value_backend_uninit_array.key,
            tuple(member.key for member in self.members),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


def lower_exact_array_backend_deferred_request_inventory(
    source: object,
    context: _ArrayBackendDeferredRequestInventoryContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayBackendDeferredRequestInventoryIr]:
    package_result = _array_backend_deferred_request_package_source(source)
    if not package_result.is_ok:
        return Result.failure(package_result.diagnostics)
    package = package_result.unwrap()

    generation_context = (
        context or _DefaultArrayBackendDeferredRequestInventoryContext()
    )
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or package.candidate_id
    )
    effective_target_extension = target_extension or package.target_extension
    effective_source_extension = source_extension or package.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or package.selected_type_tag
    )
    if (
        effective_candidate_id != package.candidate_id
        or effective_target_extension != package.target_extension
        or effective_source_extension != package.source_extension
        or effective_type_tag != package.selected_type_tag
    ):
        return Result.failure(
            (
                _array_backend_deferred_inventory_context_mismatch_diagnostic(
                    "array backend-deferred request inventory requires the "
                    "typed selected candidate context to match the M88 "
                    "structural package candidate id, target extension, "
                    "source extension, and selected type tag",
                    package.source_location,
                ),
            )
        )

    diagnostics = _validate_exact_array_backend_deferred_request_package(package)
    if diagnostics:
        return Result.failure(diagnostics)

    helper_set_completion = package.helper_set_completion
    declaration_shell = package.declaration_shell
    deferred_backend_uninit = helper_set_completion.unresolved_backend_uninit
    request_record = helper_set_completion.source_backend_uninit_request
    try:
        member = ExactArrayBackendDeferredRequestInventoryMemberIr(
            kind="value_backend_uninit_array",
            request_kind="backend_value",
            policy="deferred_backend_value",
            source_location=deferred_backend_uninit.source_location,
            source_deferred_backend_uninit=deferred_backend_uninit,
            source_request_record=request_record,
        )
        return Result.ok(
            ExactArrayBackendDeferredRequestInventoryIr(
                source_package=package,
                source_declaration_shell=declaration_shell,
                source_helper_set_completion=helper_set_completion,
                value_backend_uninit_array=member,
                members=(member,),
                source_location=package.source_location,
                candidate_id=package.candidate_id,
                target_extension=package.target_extension,
                source_extension=package.source_extension,
                selected_type_tag=package.selected_type_tag,
                originating_branch_chain_id=package.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                    str(exc),
                    package.source_location,
                ),
            )
        )


def _array_backend_deferred_request_package_source(
    source: object,
) -> Result[ExactArrayBodyStructuralPackageIr]:
    if isinstance(source, ExactArrayBodyStructuralPackageIr):
        return Result.ok(source)

    if _is_generation_stage_like(source):
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if (
            stage == "array_body_structural_package_assembly"
            and isinstance(output, ExactArrayBodyStructuralPackageIr)
        ):
            return Result.ok(output)
        return Result.failure(
            (
                _array_backend_deferred_inventory_source_unsupported_diagnostic(
                    "array backend-deferred request inventory consumes "
                    "accepted M88 ExactArrayBodyStructuralPackageIr values, "
                    "the array_body_structural_package_assembly stage output, "
                    "or a source carrying exactly one accepted M88 package",
                    _source_location_from_object(output),
                ),
            )
        )

    if isinstance(source, _ArrayBackendDeferredRequestPackageSource):
        raw_packages = source.array_body_structural_packages
        if not isinstance(raw_packages, tuple):
            return Result.failure(
                (
                    _array_backend_deferred_inventory_source_unsupported_diagnostic(
                        "array backend-deferred request inventory requires "
                        "array_body_structural_packages to be a tuple "
                        "carrying exactly one accepted M88 "
                        "ExactArrayBodyStructuralPackageIr value",
                        _source_location_from_object(raw_packages),
                    ),
                )
            )
        packages: tuple[object, ...] = raw_packages
        location = _source_location_from_package_entries(packages)
        if len(packages) == 0:
            return Result.failure(
                (
                    _array_backend_deferred_inventory_package_missing_diagnostic(
                        "array backend-deferred request inventory requires a "
                        "source carrying one accepted M88 "
                        "array_body_structural_packages entry",
                        location,
                    ),
                )
            )
        if len(packages) > 1:
            return Result.failure(
                (
                    _array_backend_deferred_inventory_package_multiple_diagnostic(
                        "array backend-deferred request inventory requires "
                        "exactly one M88 array_body_structural_packages entry; "
                        f"got {len(packages)}",
                        location,
                    ),
                )
            )
        package = packages[0]
        if not isinstance(package, ExactArrayBodyStructuralPackageIr):
            return Result.failure(
                (
                    _array_backend_deferred_inventory_source_unsupported_diagnostic(
                        "array backend-deferred request inventory requires the "
                        "single array_body_structural_packages entry to be an "
                        "accepted M88 ExactArrayBodyStructuralPackageIr value",
                        location or _source_location_from_object(package),
                    ),
                )
            )
        return Result.ok(package)

    return Result.failure(
        (
            _array_backend_deferred_inventory_source_unsupported_diagnostic(
                "array backend-deferred request inventory consumes only "
                "accepted M88 structural-package typed sources",
                None,
            ),
        )
    )


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _source_location_from_package_entries(
    packages: tuple[object, ...],
) -> SourceLocation | None:
    for package in packages:
        if isinstance(package, ExactArrayBodyStructuralPackageIr):
            return package.source_location
        location = _source_location_from_object(package)
        if location is not None:
            return location
    return None


def _source_location_from_object(source: object) -> SourceLocation | None:
    location = getattr(source, "source_location", None)
    if isinstance(location, SourceLocation):
        return location
    return None


def _validate_exact_array_backend_deferred_request_package(
    package: ExactArrayBodyStructuralPackageIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    rule = _EXACT_ARRAY_BACKEND_UNINIT_DEFERRED_REQUEST_RULE
    declaration_shell = package.declaration_shell
    helper_set_completion = package.helper_set_completion
    if not isinstance(
        declaration_shell,
        ExactArrayInitializationDeclarationShellIr,
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                "array backend-deferred request inventory requires the "
                "accepted M73 declaration-shell member from the M88 package",
                package.source_location,
            )
        )
    if not isinstance(
        helper_set_completion,
        ExactArrayInitializationHelperSetCompletionIr,
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_backend_uninit_missing_diagnostic(
                "array backend-deferred request inventory requires the "
                "accepted M72 helper-set completion from the M88 package",
                package.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)

    deferred_backend_uninit = helper_set_completion.unresolved_backend_uninit
    request_record = helper_set_completion.source_backend_uninit_request
    if not isinstance(
        deferred_backend_uninit,
        ExactArrayInitializationDeferredBackendUninitValue,
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_backend_uninit_missing_diagnostic(
                "array backend-deferred request inventory requires the "
                "accepted M72 deferred backend-uninit boundary",
                package.source_location,
            )
        )
    if not isinstance(request_record, ExactArrayInitializationHelperRequestRecord):
        diagnostics.append(
            _array_backend_deferred_inventory_backend_uninit_missing_diagnostic(
                "array backend-deferred request inventory requires the "
                "accepted M67 backend-uninit request record",
                package.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)

    request_location = request_record.leaf_source_location
    if deferred_backend_uninit.policy != rule.policy:
        diagnostics.append(
            _array_backend_deferred_inventory_policy_mismatch_diagnostic(
                "array backend-deferred request inventory preserves only the "
                "accepted M72 deferred_backend_value policy",
                deferred_backend_uninit.source_location,
            )
        )
    if (
        request_record.request_ordinal != rule.request_ordinal
        or request_record.request_kind != rule.request_kind
        or request_record.helper_leaf_kind != rule.helper_leaf_kind
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_backend_uninit_mismatch_diagnostic(
                "array backend-deferred request inventory expected the M67 "
                "backend-uninit request to carry ordinal "
                f"{rule.request_ordinal}, kind {rule.request_kind!r}, and "
                f"leaf kind {rule.helper_leaf_kind!r}; got ordinal "
                f"{request_record.request_ordinal}, kind "
                f"{request_record.request_kind!r}, and leaf kind "
                f"{request_record.helper_leaf_kind!r}",
                request_location,
            )
        )
    if request_record.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_backend_deferred_inventory_backend_uninit_mismatch_diagnostic(
                "array backend-deferred request inventory preserves the M67 "
                "backend-uninit leaf source text only as provenance and "
                "accepts only the exact value<backend>(uninit::array) leaf; "
                f"got {request_record.leaf_source_text!r}",
                request_location,
            )
        )
    if deferred_backend_uninit.source_location != request_location:
        diagnostics.append(
            _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                "array backend-deferred request inventory requires the M72 "
                "backend-uninit source location to match the M67 request "
                "leaf source location",
                deferred_backend_uninit.source_location,
            )
        )
    if (
        declaration_shell.source_helper_set_completion is not helper_set_completion
        or declaration_shell.unresolved_backend_uninit is not deferred_backend_uninit
        or helper_set_completion.unresolved_backend_uninit
        is not deferred_backend_uninit
        or helper_set_completion.source_backend_uninit_request is not request_record
        or deferred_backend_uninit.source_backend_uninit_request
        is not request_record
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                "array backend-deferred request inventory preserves only the "
                "accepted M88 package, M73 declaration-shell, M72 "
                "deferred-value, and M67 request identity chain",
                package.source_location,
            )
        )

    expected_context = (
        package.candidate_id,
        package.target_extension,
        package.source_extension,
        package.selected_type_tag,
        package.originating_branch_chain_id,
    )
    for label, value in (
        ("M72 helper-set completion", helper_set_completion),
        ("M73 declaration shell", declaration_shell),
        ("M72 deferred backend-uninit boundary", deferred_backend_uninit),
    ):
        actual_context = (
            value.candidate_id,
            value.target_extension,
            value.source_extension,
            value.selected_type_tag,
            value.originating_branch_chain_id,
        )
        if actual_context != expected_context:
            diagnostics.append(
                _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                    "array backend-deferred request inventory requires the "
                    f"{label} context to match the M88 package context",
                    value.source_location,
                )
            )
    request_context = (
        request_record.candidate_id,
        request_record.selected_type_tag,
        request_record.originating_branch_chain_id,
    )
    if request_context != (
        package.candidate_id,
        package.selected_type_tag,
        package.originating_branch_chain_id,
    ):
        diagnostics.append(
            _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                "array backend-deferred request inventory requires the M67 "
                "backend-uninit request candidate id, selected type tag, and "
                "branch-chain id to match the M88 package context",
                request_location,
            )
        )

    expected_slot = (
        "opaque_pre_branch_array_initialization",
        0,
        "tmp",
    )
    slot_sources: tuple[tuple[str, _InventorySlotIdentitySource], ...] = (
        ("M72 helper-set completion", helper_set_completion),
        ("M73 declaration shell", declaration_shell),
        ("M72 deferred backend-uninit boundary", deferred_backend_uninit),
        ("M67 backend-uninit request", request_record),
    )
    for label, slot_source in slot_sources:
        actual_slot = (
            slot_source.slot_label,
            slot_source.slot_ordinal,
            slot_source.variable_token,
        )
        if actual_slot != expected_slot:
            diagnostics.append(
                _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
                    "array backend-deferred request inventory supports only "
                    "the exact first-slot tmp backend-uninit boundary; "
                    f"{label} carried slot {actual_slot!r}",
                    _source_location_from_object(slot_source) or request_location,
                )
            )

    return tuple(diagnostics)


def _raise_first_inventory_validation_error(
    inventory: ExactArrayBackendDeferredRequestInventoryIr,
) -> None:
    if not isinstance(inventory.source_package, ExactArrayBodyStructuralPackageIr):
        raise TypeError(
            "array backend-deferred request inventory requires an M88 package"
        )
    if not isinstance(
        inventory.source_declaration_shell,
        ExactArrayInitializationDeclarationShellIr,
    ):
        raise TypeError(
            "array backend-deferred request inventory requires an M73 "
            "declaration shell"
        )
    if not isinstance(
        inventory.source_helper_set_completion,
        ExactArrayInitializationHelperSetCompletionIr,
    ):
        raise TypeError(
            "array backend-deferred request inventory requires an M72 "
            "helper-set completion"
        )
    if not isinstance(
        inventory.value_backend_uninit_array,
        ExactArrayBackendDeferredRequestInventoryMemberIr,
    ):
        raise TypeError(
            "array backend-deferred request inventory requires one typed "
            "backend-uninit member"
        )
    if inventory.members != (inventory.value_backend_uninit_array,):
        raise ValueError(
            "array backend-deferred request inventory supports exactly one "
            "value_backend_uninit_array member"
        )
    package = inventory.source_package
    if (
        inventory.source_declaration_shell is not package.declaration_shell
        or inventory.source_helper_set_completion is not package.helper_set_completion
        or inventory.value_backend_uninit_array.source_deferred_backend_uninit
        is not package.helper_set_completion.unresolved_backend_uninit
        or inventory.value_backend_uninit_array.source_request_record
        is not package.helper_set_completion.source_backend_uninit_request
    ):
        raise ValueError(
            "array backend-deferred request inventory must preserve accepted "
            "package, declaration-shell, deferred-value, and request identity"
        )
    if inventory.source_location != package.source_location:
        raise ValueError(
            "array backend-deferred request inventory source location must "
            "match the M88 package"
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
        raise ValueError(
            "array backend-deferred request inventory context must match the "
            "M88 package"
        )


def _array_backend_deferred_inventory_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_package_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-PACKAGE-MISSING",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_package_multiple_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-PACKAGE-MULTIPLE",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_backend_uninit_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-BACKEND-UNINIT-MISSING",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_backend_uninit_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-BACKEND-UNINIT-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_policy_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-POLICY-MISMATCH",
        detail,
        location=location,
    )


def _array_backend_deferred_inventory_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BACKEND-DEFERRED-INVENTORY-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )
