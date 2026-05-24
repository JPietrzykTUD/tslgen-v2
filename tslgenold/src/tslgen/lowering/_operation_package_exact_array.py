from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic
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
from tslgen.lowering._operation_package_diagnostics import (
    operation_package_context_mismatch_diagnostic,
    operation_package_dependency_provenance_mismatch_diagnostic,
    operation_package_provenance_mismatch_diagnostic,
    operation_package_source_location_mismatch_diagnostic,
)


def validate_exact_array_backend_handoff_request(
    request: ExactArrayBackendHandoffRequestIr,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    completion_package = request.source_completion_package
    if not isinstance(
        completion_package,
        ExactArrayLoweringCompletionPackageIr,
    ):
        return (
            operation_package_provenance_mismatch_diagnostic(
                "operation package requires the M92 handoff request to "
                "preserve the accepted M90 completion package",
                request.source_location,
            ),
        )
    if not isinstance(request.source_package, ExactArrayBodyStructuralPackageIr):
        diagnostics.append(
            operation_package_provenance_mismatch_diagnostic(
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
            operation_package_provenance_mismatch_diagnostic(
                "operation package requires the M92 handoff request to "
                "preserve the accepted M89 deferred-request inventory",
                request.source_location,
            )
        )
    if diagnostics:
        return tuple(diagnostics)
    if request.source_package is not completion_package.source_package:
        diagnostics.append(
            operation_package_provenance_mismatch_diagnostic(
                "operation package must preserve the M92-to-M90-to-M88 "
                "package identity chain",
                request.source_location,
            )
        )
    if request.source_inventory is not completion_package.source_inventory:
        diagnostics.append(
            operation_package_provenance_mismatch_diagnostic(
                "operation package must preserve the M92-to-M90-to-M89 "
                "inventory identity chain",
                request.source_location,
            )
        )
    if request.source_location != completion_package.source_location:
        diagnostics.append(
            operation_package_source_location_mismatch_diagnostic(
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
            operation_package_context_mismatch_diagnostic(
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
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package requires the M92 value_backend_uninit_array "
                "dependency request",
                request.source_location,
            )
        )
        return tuple(diagnostics)
    if request.unresolved_dependency_requests != (dependency_request,):
        diagnostics.append(
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package supports exactly one accepted M92 "
                "unresolved dependency request",
                request.source_location,
            )
        )
    completion_dependency = completion_package.value_backend_uninit_array_dependency
    if dependency_request.source_completion_dependency is not completion_dependency:
        diagnostics.append(
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M90 unresolved dependency",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_inventory_member is not (
        completion_package.source_inventory.value_backend_uninit_array
    ):
        diagnostics.append(
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M89 inventory member",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_deferred_backend_uninit is not (
        completion_dependency.source_deferred_backend_uninit
    ):
        diagnostics.append(
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M72 deferred backend value",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_request_record is not (
        completion_dependency.source_request_record
    ):
        diagnostics.append(
            operation_package_dependency_provenance_mismatch_diagnostic(
                "operation package must preserve the M92 dependency request "
                "identity back to the accepted M67 request record",
                dependency_request.source_location,
            )
        )
    if dependency_request.source_location != completion_dependency.source_location:
        diagnostics.append(
            operation_package_source_location_mismatch_diagnostic(
                "operation package dependency source location must match the "
                "accepted M90 unresolved dependency",
                dependency_request.source_location,
            )
        )
    return tuple(diagnostics)
