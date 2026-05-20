from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_deferred_requests import (
    ExactArrayBackendDeferredRequestInventoryIr,
)
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffRequestIr,
    ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
)
from tslgen.lowering._array_body_completion_package import (
    ExactArrayLoweringCompletionPackageIr,
)
from tslgen.lowering._array_body_package import ExactArrayBodyStructuralPackageIr

if TYPE_CHECKING:
    from tslgen.lowering._stage_contracts import TsilReturnStatement


type LoweringOperationPackageSourceFamily = Literal[
    "mini_tsil_leaf_return",
    "exact_array_backend_handoff",
]


@dataclass(frozen=True, slots=True)
class MiniTsilLeafReturnOperationPackageEntryIr:
    candidate_id: str
    source_location: SourceLocation | None
    source_statement: TsilReturnStatement

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "mini-TSIL leaf-return operation package candidate id "
                "must be non-empty"
            )
        if not _is_accepted_m86_tsil_return_statement(self.source_statement):
            raise TypeError(
                "mini-TSIL leaf-return operation package requires an accepted "
                "M86 TsilReturnStatement"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "mini_tsil_leaf_return_operation",
            self.candidate_id,
            _source_location_key(self.source_location),
            self.source_statement.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBackendHandoffOperationPackageEntryIr:
    source_request: ExactArrayBackendHandoffRequestIr

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, ExactArrayBackendHandoffRequestIr):
            raise TypeError(
                "exact-array backend-handoff operation package requires an "
                "accepted M92 ExactArrayBackendHandoffRequestIr"
            )

    @property
    def candidate_id(self) -> str:
        return self.source_request.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.source_request.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_handoff_operation",
            self.source_request.key,
        )


@dataclass(frozen=True, slots=True)
class LoweringOperationPackageIr:
    source_family: LoweringOperationPackageSourceFamily
    candidate_id: str
    source_location: SourceLocation | None
    mini_tsil_leaf_return: MiniTsilLeafReturnOperationPackageEntryIr | None = None
    exact_array_backend_handoff: (
        ExactArrayBackendHandoffOperationPackageEntryIr | None
    ) = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowering operation package candidate id must be non-empty")
        entries = tuple(
            entry
            for entry in (
                self.mini_tsil_leaf_return,
                self.exact_array_backend_handoff,
            )
            if entry is not None
        )
        if len(entries) != 1:
            raise ValueError(
                "lowering operation package requires exactly one source entry"
            )
        if (
            self.source_family == "mini_tsil_leaf_return"
            and self.mini_tsil_leaf_return is None
        ):
            raise ValueError(
                "mini_tsil_leaf_return package requires a mini-TSIL entry"
            )
        if (
            self.source_family == "exact_array_backend_handoff"
            and self.exact_array_backend_handoff is None
        ):
            raise ValueError(
                "exact_array_backend_handoff package requires an exact-array entry"
            )
        entry = entries[0]
        entry_candidate_id = getattr(entry, "candidate_id")
        if self.candidate_id != entry_candidate_id:
            raise ValueError(
                "lowering operation package candidate id must match its entry"
            )
        entry_location = getattr(entry, "source_location")
        if self.source_location != entry_location:
            raise ValueError(
                "lowering operation package source location must match its entry"
            )

    @property
    def source_entry(
        self,
    ) -> (
        MiniTsilLeafReturnOperationPackageEntryIr
        | ExactArrayBackendHandoffOperationPackageEntryIr
    ):
        if self.mini_tsil_leaf_return is not None:
            return self.mini_tsil_leaf_return
        if self.exact_array_backend_handoff is not None:
            return self.exact_array_backend_handoff
        raise AssertionError("validated operation package lost its source entry")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "lowering_operation_package",
            self.source_family,
            self.candidate_id,
            _source_location_key(self.source_location),
            self.source_entry.key,
        )


def lower_lowering_operation_package(
    source: object,
    *,
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
    source_family: LoweringOperationPackageSourceFamily | None = None,
) -> Result[LoweringOperationPackageIr]:
    if isinstance(source, LoweringOperationPackageIr):
        return _validate_existing_package(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if _is_generation_stage_like(source):
        return _operation_package_from_stage(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if isinstance(source, ExactArrayBackendHandoffRequestIr):
        return _exact_array_backend_handoff_package(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if _is_tsil_return_statement(source):
        return _mini_tsil_leaf_return_package(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if _is_operation_package_container(source):
        return _operation_package_from_existing_package_container(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if _is_packageable_value_container(source):
        return _operation_package_from_value_container(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    return Result.failure(
        (
            _operation_package_source_unsupported_diagnostic(
                "lowering operation package consumes only accepted M86 "
                "TsilReturnStatement values, selected_body_lowering stages, "
                "accepted M92 ExactArrayBackendHandoffRequestIr values, "
                "array_backend_handoff_request stages, or containers carrying "
                "exactly one such accepted value",
                None,
            ),
        )
    )


def _operation_package_from_stage(
    stage_source: object,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    stage = getattr(stage_source, "stage")
    output = getattr(stage_source, "output")
    if stage == "selected_body_lowering" and _is_tsil_return_statement(output):
        return _mini_tsil_leaf_return_package(
            output,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if stage == "array_backend_handoff_request" and isinstance(
        output,
        ExactArrayBackendHandoffRequestIr,
    ):
        return _exact_array_backend_handoff_package(
            output,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    return Result.failure(
        (
            _operation_package_source_unsupported_diagnostic(
                "lowering operation package consumes only selected_body_lowering "
                "stages carrying accepted M86 TsilReturnStatement values or "
                "array_backend_handoff_request stages carrying accepted M92 "
                "ExactArrayBackendHandoffRequestIr values",
                _source_location_from_object(output),
            ),
        )
    )


def _operation_package_from_existing_package_container(
    source: object,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    raw_packages = getattr(source, "operation_packages")
    if not isinstance(raw_packages, tuple):
        return Result.failure(
            (
                _operation_package_malformed_diagnostic(
                    "lowering operation package container requires "
                    "operation_packages to be a tuple",
                    _source_location_from_object(raw_packages),
                ),
            )
        )
    if raw_packages:
        packages = tuple(
            package
            for package in raw_packages
            if isinstance(package, LoweringOperationPackageIr)
        )
        if len(packages) != len(raw_packages):
            return Result.failure(
                (
                    _operation_package_malformed_diagnostic(
                        "lowering operation package container requires every "
                        "operation_packages entry to be a typed M93 package",
                        _source_location_from_entries(raw_packages),
                    ),
                )
            )
        if len(packages) > 1:
            return Result.failure(
                (
                    _operation_package_duplicate_value_diagnostic(
                        "lowering operation package container requires exactly "
                        f"one typed M93 package entry; got {len(packages)}",
                        _source_location_from_entries(raw_packages),
                    ),
                )
            )
        context_result = _merged_candidate_context(
            explicit_candidate_id=candidate_id,
            container_candidate_id=_candidate_id_from_object(source),
            location=packages[0].source_location,
        )
        if not context_result.is_ok:
            return Result.failure(context_result.diagnostics)
        return _validate_existing_package(
            packages[0],
            candidate_id=context_result.unwrap(),
            source_location=source_location,
            source_family=source_family,
        )
    return _operation_package_from_value_container(
        source,
        candidate_id=candidate_id,
        source_location=source_location,
        source_family=source_family,
    )


def _operation_package_from_value_container(
    source: object,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    statements_result = _container_tsil_return_statements(source)
    if not statements_result.is_ok:
        return Result.failure(statements_result.diagnostics)
    handoffs_result = _container_exact_array_backend_handoffs(source)
    if not handoffs_result.is_ok:
        return Result.failure(handoffs_result.diagnostics)
    statements = statements_result.unwrap()
    handoffs = handoffs_result.unwrap()

    container_location = source_location or _source_location_from_object(source)
    if source_family is None and statements and handoffs:
        return Result.failure(
            (
                _operation_package_source_ambiguous_diagnostic(
                    "lowering operation package source carries both accepted "
                    "M86 mini-TSIL return values and accepted M92 exact-array "
                    "handoff values; pass source_family to choose one",
                    container_location
                    or _source_location_from_entries((*statements, *handoffs)),
                ),
            )
        )
    if source_family == "mini_tsil_leaf_return" or (
        source_family is None and statements
    ):
        if not statements:
            return Result.failure(
                (
                    _operation_package_missing_value_diagnostic(
                        "lowering operation package requires one accepted M86 "
                        "TsilReturnStatement entry",
                        container_location,
                    ),
                )
            )
        if len(statements) > 1:
            return Result.failure(
                (
                    _operation_package_duplicate_value_diagnostic(
                        "lowering operation package requires exactly one "
                        f"accepted M86 TsilReturnStatement; got {len(statements)}",
                        _source_location_from_entries(statements)
                        or container_location,
                    ),
                )
            )
        context_result = _merged_candidate_context(
            explicit_candidate_id=candidate_id,
            container_candidate_id=_candidate_id_from_object(source),
            location=container_location,
        )
        if not context_result.is_ok:
            return Result.failure(context_result.diagnostics)
        return _mini_tsil_leaf_return_package(
            statements[0],
            candidate_id=context_result.unwrap(),
            source_location=container_location,
            source_family=source_family,
        )
    if source_family == "exact_array_backend_handoff" or (
        source_family is None and handoffs
    ):
        if not handoffs:
            return Result.failure(
                (
                    _operation_package_missing_value_diagnostic(
                        "lowering operation package requires one accepted M92 "
                        "ExactArrayBackendHandoffRequestIr entry",
                        container_location,
                    ),
                )
            )
        if len(handoffs) > 1:
            return Result.failure(
                (
                    _operation_package_duplicate_value_diagnostic(
                        "lowering operation package requires exactly one "
                        "accepted M92 ExactArrayBackendHandoffRequestIr; got "
                        f"{len(handoffs)}",
                        _source_location_from_entries(handoffs)
                        or container_location,
                    ),
                )
            )
        context_result = _merged_candidate_context(
            explicit_candidate_id=candidate_id,
            container_candidate_id=_candidate_id_from_object(source),
            location=container_location or handoffs[0].source_location,
        )
        if not context_result.is_ok:
            return Result.failure(context_result.diagnostics)
        return _exact_array_backend_handoff_package(
            handoffs[0],
            candidate_id=context_result.unwrap(),
            source_location=container_location,
            source_family=source_family,
        )
    return Result.failure(
        (
            _operation_package_missing_value_diagnostic(
                "lowering operation package source does not carry an accepted "
                "M86 TsilReturnStatement or accepted M92 "
                "ExactArrayBackendHandoffRequestIr",
                container_location,
            ),
        )
    )


def _mini_tsil_leaf_return_package(
    statement: object,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    family_result = _validate_source_family(
        "mini_tsil_leaf_return",
        source_family,
        source_location,
    )
    if not family_result.is_ok:
        return Result.failure(family_result.diagnostics)
    if not candidate_id:
        return Result.failure(
            (
                _operation_package_context_mismatch_diagnostic(
                    "mini-TSIL leaf-return operation package requires an "
                    "explicit selected candidate id",
                    source_location,
                ),
            )
        )
    if not _is_accepted_m86_tsil_return_statement(statement):
        return Result.failure(
            (
                _operation_package_malformed_diagnostic(
                    "mini-TSIL leaf-return operation package requires an "
                    "accepted M86 TsilReturnStatement value: either "
                    "emit_return(<parameter> + <parameter>) or "
                    "emit_return(intrin_compose<add>(<parameter>, "
                    "<parameter>))",
                    source_location,
                ),
            )
        )
    entry = MiniTsilLeafReturnOperationPackageEntryIr(
        candidate_id=candidate_id,
        source_location=source_location,
        source_statement=cast("TsilReturnStatement", statement),
    )
    return Result.ok(
        LoweringOperationPackageIr(
            source_family="mini_tsil_leaf_return",
            candidate_id=candidate_id,
            source_location=source_location,
            mini_tsil_leaf_return=entry,
        )
    )


def _exact_array_backend_handoff_package(
    request: ExactArrayBackendHandoffRequestIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    family_result = _validate_source_family(
        "exact_array_backend_handoff",
        source_family,
        request.source_location,
    )
    if not family_result.is_ok:
        return Result.failure(family_result.diagnostics)
    if candidate_id is not None and candidate_id != request.candidate_id:
        return Result.failure(
            (
                _operation_package_context_mismatch_diagnostic(
                    "exact-array backend-handoff operation package candidate "
                    "context must match the accepted M92 request",
                    request.source_location,
                ),
            )
        )
    if source_location is not None and source_location != request.source_location:
        return Result.failure(
            (
                _operation_package_source_location_mismatch_diagnostic(
                    "exact-array backend-handoff operation package source "
                    "location must match the accepted M92 request",
                    request.source_location,
                ),
            )
        )
    diagnostics = _validate_exact_array_backend_handoff_request(request)
    if diagnostics:
        return Result.failure(diagnostics)
    entry = ExactArrayBackendHandoffOperationPackageEntryIr(request)
    return Result.ok(
        LoweringOperationPackageIr(
            source_family="exact_array_backend_handoff",
            candidate_id=request.candidate_id,
            source_location=request.source_location,
            exact_array_backend_handoff=entry,
        )
    )


def _validate_existing_package(
    package: LoweringOperationPackageIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    family_result = _validate_source_family(
        package.source_family,
        source_family,
        package.source_location,
    )
    if not family_result.is_ok:
        return Result.failure(family_result.diagnostics)
    if candidate_id is not None and candidate_id != package.candidate_id:
        return Result.failure(
            (
                _operation_package_context_mismatch_diagnostic(
                    "lowering operation package candidate context must match "
                    "the existing M93 package",
                    package.source_location,
                ),
            )
        )
    if source_location is not None and source_location != package.source_location:
        return Result.failure(
            (
                _operation_package_source_location_mismatch_diagnostic(
                    "lowering operation package source location must match "
                    "the existing M93 package",
                    package.source_location,
                ),
            )
        )
    if package.exact_array_backend_handoff is not None:
        diagnostics = _validate_exact_array_backend_handoff_request(
            package.exact_array_backend_handoff.source_request,
        )
        if diagnostics:
            return Result.failure(diagnostics)
    return Result.ok(package)


def _validate_source_family(
    actual: LoweringOperationPackageSourceFamily,
    expected: LoweringOperationPackageSourceFamily | None,
    location: SourceLocation | None,
) -> Result[None]:
    if expected is not None and expected != actual:
        return Result.failure(
            (
                _operation_package_source_family_mismatch_diagnostic(
                    "lowering operation package source family "
                    f"{expected!r} does not match accepted source family "
                    f"{actual!r}",
                    location,
                ),
            )
        )
    return Result.ok(None)


def _container_tsil_return_statements(
    source: object,
) -> Result[tuple[TsilReturnStatement, ...]]:
    if not hasattr(source, "statements"):
        return Result.ok(())
    raw_statements = getattr(source, "statements")
    if not isinstance(raw_statements, tuple):
        return Result.failure(
            (
                _operation_package_malformed_diagnostic(
                    "lowering operation package source requires statements "
                    "to be a tuple",
                    _source_location_from_object(raw_statements),
                ),
            )
        )
    statements: list[TsilReturnStatement] = []
    for entry in raw_statements:
        if not _is_tsil_return_statement(entry):
            return Result.failure(
                (
                    _operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "statements entry to be an accepted M86 "
                        "TsilReturnStatement",
                        _source_location_from_object(entry),
                    ),
                )
            )
        if not _is_accepted_m86_tsil_return_statement(entry):
            return Result.failure(
                (
                    _operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "statements entry to match an accepted M86 mini-TSIL "
                        "leaf-return shape",
                        _source_location_from_object(entry),
                    ),
                )
            )
        statements.append(entry)
    return Result.ok(tuple(statements))


def _container_exact_array_backend_handoffs(
    source: object,
) -> Result[tuple[ExactArrayBackendHandoffRequestIr, ...]]:
    if not hasattr(source, "array_backend_handoff_requests"):
        return Result.ok(())
    raw_handoffs = getattr(source, "array_backend_handoff_requests")
    if not isinstance(raw_handoffs, tuple):
        return Result.failure(
            (
                _operation_package_malformed_diagnostic(
                    "lowering operation package source requires "
                    "array_backend_handoff_requests to be a tuple",
                    _source_location_from_object(raw_handoffs),
                ),
            )
        )
    handoffs: list[ExactArrayBackendHandoffRequestIr] = []
    for entry in raw_handoffs:
        if not isinstance(entry, ExactArrayBackendHandoffRequestIr):
            return Result.failure(
                (
                    _operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "array_backend_handoff_requests entry to be an "
                        "accepted M92 ExactArrayBackendHandoffRequestIr",
                        _source_location_from_object(entry),
                    ),
                )
            )
        handoffs.append(entry)
    return Result.ok(tuple(handoffs))


def _validate_exact_array_backend_handoff_request(
    request: ExactArrayBackendHandoffRequestIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    completion_package = request.source_completion_package
    if not isinstance(
        completion_package,
        ExactArrayLoweringCompletionPackageIr,
    ):
        return (
            _operation_package_provenance_mismatch_diagnostic(
                "operation package requires the M92 handoff request to "
                "preserve the accepted M90 completion package",
                request.source_location,
            ),
        )
    if not isinstance(request.source_package, ExactArrayBodyStructuralPackageIr):
        diagnostics.append(
            _operation_package_provenance_mismatch_diagnostic(
                "operation package requires the M92 handoff request to "
                "preserve the accepted M88 structural package",
                request.source_location,
            )
        )
    if not isinstance(
        request.source_inventory,
        ExactArrayBackendDeferredRequestInventoryIr,
    ):
        diagnostics.append(
            _operation_package_provenance_mismatch_diagnostic(
                "operation package requires the M92 handoff request to "
                "preserve the accepted M89 deferred-request inventory",
                request.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)
    if request.source_package is not completion_package.source_package:
        diagnostics.append(
            _operation_package_provenance_mismatch_diagnostic(
                "operation package must preserve the M92-to-M90-to-M88 "
                "package identity chain",
                request.source_location,
            )
        )
    if request.source_inventory is not completion_package.source_inventory:
        diagnostics.append(
            _operation_package_provenance_mismatch_diagnostic(
                "operation package must preserve the M92-to-M90-to-M89 "
                "inventory identity chain",
                request.source_location,
            )
        )
    if request.source_location != completion_package.source_location:
        diagnostics.append(
            _operation_package_source_location_mismatch_diagnostic(
                "operation package source location must match the accepted "
                "M90 completion package",
                request.source_location,
            )
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
        diagnostics.append(
            _operation_package_context_mismatch_diagnostic(
                "operation package requires the M92 handoff request context "
                "to match its accepted M90 completion package",
                request.source_location,
            )
        )
    dependency_request = request.value_backend_uninit_array_request
    if not isinstance(
        dependency_request,
        ExactArrayBackendHandoffUnresolvedDependencyRequestIr,
    ):
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package requires the M92 value_backend_uninit_array "
                "dependency request",
                request.source_location,
            )
        )
        return tuple(diagnostics)
    if request.unresolved_dependency_requests != (dependency_request,):
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package supports exactly one accepted M92 "
                "unresolved dependency request",
                request.source_location,
            )
        )
    completion_dependency = completion_package.value_backend_uninit_array_dependency
    if dependency_request.source_completion_dependency is not completion_dependency:
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M90 unresolved dependency",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_inventory_member is not (
        completion_package.source_inventory.value_backend_uninit_array
    ):
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M89 inventory member",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_deferred_backend_uninit is not (
        completion_dependency.source_deferred_backend_uninit
    ):
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M72 deferred backend value",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_request_record is not (
        completion_dependency.source_request_record
    ):
        diagnostics.append(
            _operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M67 request record",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_location != completion_dependency.source_location:
        diagnostics.append(
            _operation_package_source_location_mismatch_diagnostic(
                "operation package dependency source location must match the "
                "accepted M90 unresolved dependency",
                dependency_request.source_location,
            )
        )
    return tuple(diagnostics)


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _is_operation_package_container(source: object) -> bool:
    return hasattr(source, "operation_packages")


def _is_packageable_value_container(source: object) -> bool:
    return hasattr(source, "statements") or hasattr(
        source,
        "array_backend_handoff_requests",
    )


def _is_tsil_return_statement(source: object) -> bool:
    from tslgen.lowering._stage_contracts import TsilReturnStatement

    return isinstance(source, TsilReturnStatement)


def _is_accepted_m86_tsil_return_statement(source: object) -> bool:
    from tslgen.lowering._stage_contracts import (
        TsilBinaryExpression,
        TsilIntrinsicComposeExpression,
        TsilParameterReference,
        TsilReturnStatement,
    )

    if not isinstance(source, TsilReturnStatement):
        return False
    expression = source.expression
    if isinstance(expression, TsilBinaryExpression):
        return (
            expression.operator == "+"
            and isinstance(expression.left, TsilParameterReference)
            and isinstance(expression.right, TsilParameterReference)
        )
    if isinstance(expression, TsilIntrinsicComposeExpression):
        return (
            expression.intrinsic == "add"
            and len(expression.arguments) == 2
            and all(
                isinstance(argument, TsilParameterReference)
                for argument in expression.arguments
            )
        )
    return False


def _candidate_id_from_object(source: object) -> str | None:
    candidate_id = getattr(source, "candidate_id", None)
    if isinstance(candidate_id, str) and candidate_id:
        return candidate_id
    return None


def _merged_candidate_context(
    *,
    explicit_candidate_id: str | None,
    container_candidate_id: str | None,
    location: SourceLocation | None,
) -> Result[str | None]:
    if (
        explicit_candidate_id is not None
        and container_candidate_id is not None
        and explicit_candidate_id != container_candidate_id
    ):
        return Result.failure(
            (
                _operation_package_context_mismatch_diagnostic(
                    "lowering operation package explicit candidate context "
                    "must match the narrow source container candidate id",
                    location,
                ),
            )
        )
    return Result.ok(explicit_candidate_id or container_candidate_id)


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


def _source_location_key(location: SourceLocation | None) -> tuple[object, ...]:
    if location is None:
        return ("none",)
    return ("source_location", *location.sort_key())


def _operation_package_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _operation_package_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-VALUE-MISSING",
        detail,
        location=location,
    )


def _operation_package_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-VALUE-MULTIPLE",
        detail,
        location=location,
    )


def _operation_package_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-MALFORMED",
        detail,
        location=location,
    )


def _operation_package_source_family_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-FAMILY-MISMATCH",
        detail,
        location=location,
    )


def _operation_package_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _operation_package_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def _operation_package_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _operation_package_dependency_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-DEPENDENCY-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _operation_package_source_ambiguous_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-AMBIGUOUS",
        detail,
        location=location,
    )
