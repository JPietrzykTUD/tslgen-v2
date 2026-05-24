from __future__ import annotations

from typing import TYPE_CHECKING, cast

from tslgen.core.diagnostics import SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffRequestIr,
)
from tslgen.lowering._operation_package_diagnostics import (
    operation_package_context_mismatch_diagnostic,
    operation_package_duplicate_value_diagnostic,
    operation_package_malformed_diagnostic,
    operation_package_missing_value_diagnostic,
    operation_package_source_ambiguous_diagnostic,
    operation_package_source_family_mismatch_diagnostic,
    operation_package_source_location_mismatch_diagnostic,
    operation_package_source_unsupported_diagnostic,
    source_location_from_entries,
    source_location_from_object,
)
from tslgen.lowering._operation_package_exact_array import (
    validate_exact_array_backend_handoff_request,
)
from tslgen.lowering._operation_package_mini_tsil import (
    is_accepted_m86_tsil_return_statement,
    is_tsil_return_statement,
)
from tslgen.lowering._operation_package_models import (
    ExactArrayBackendHandoffOperationPackageEntryIr,
    LoweringOperationPackageIr,
    LoweringOperationPackageSourceFamily,
    MiniTsilLeafReturnOperationPackageEntryIr,
)
from tslgen.lowering._operation_package_selected_body import (
    SelectedBodyDirectIntrinsicOperationPackageEntryIr,
    is_generation_selected_body_envelope,
    validate_selected_body_direct_intrinsic_envelope,
)
from tslgen.lowering._selected_body_models import (
    NoSelectedBodyEnvelopeIr,
    SelectedBodyEnvelopeIr,
)

if TYPE_CHECKING:
    from tslgen.lowering._stage_contracts import TsilReturnStatement


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
    if is_generation_selected_body_envelope(source):
        return _selected_body_direct_intrinsic_package(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    if is_tsil_return_statement(source):
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
            operation_package_source_unsupported_diagnostic(
                "lowering operation package consumes only accepted M86 "
                "TsilReturnStatement values, selected_body_lowering stages, "
                "accepted M92 ExactArrayBackendHandoffRequestIr values, "
                "array_backend_handoff_request stages, accepted M63 "
                "SelectedBodyEnvelopeIr values, selected_body_envelope_lowering "
                "stages, or containers carrying exactly one such accepted value",
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
    if stage == "selected_body_lowering" and is_tsil_return_statement(output):
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
    if stage == "selected_body_envelope_lowering" and (
        is_generation_selected_body_envelope(output)
    ):
        return _selected_body_direct_intrinsic_package(
            output,
            candidate_id=candidate_id,
            source_location=source_location,
            source_family=source_family,
        )
    return Result.failure(
        (
            operation_package_source_unsupported_diagnostic(
                "lowering operation package consumes only selected_body_lowering "
                "stages carrying accepted M86 TsilReturnStatement values or "
                "array_backend_handoff_request stages carrying accepted M92 "
                "ExactArrayBackendHandoffRequestIr values or "
                "selected_body_envelope_lowering stages carrying accepted M63 "
                "SelectedBodyEnvelopeIr values",
                source_location_from_object(output),
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
                operation_package_malformed_diagnostic(
                    "lowering operation package container requires "
                    "operation_packages to be a tuple",
                    source_location_from_object(raw_packages),
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
                    operation_package_malformed_diagnostic(
                        "lowering operation package container requires every "
                        "operation_packages entry to be a typed M93 package",
                        source_location_from_entries(raw_packages),
                    ),
                )
            )
        if len(packages) > 1:
            return Result.failure(
                (
                    operation_package_duplicate_value_diagnostic(
                        "lowering operation package container requires exactly "
                        f"one typed M93 package entry; got {len(packages)}",
                        source_location_from_entries(raw_packages),
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
    generation_selected_body_result = _container_selected_body_envelopes(source)
    if not generation_selected_body_result.is_ok:
        return Result.failure(generation_selected_body_result.diagnostics)
    statements = statements_result.unwrap()
    handoffs = handoffs_result.unwrap()
    generation_selected_body_envelopes = generation_selected_body_result.unwrap()
    selected_body_envelopes = tuple(
        envelope
        for envelope in generation_selected_body_envelopes
        if isinstance(envelope, SelectedBodyEnvelopeIr)
    )

    container_location = source_location or source_location_from_object(source)
    active_families = tuple(
        family
        for family, values in (
            ("mini_tsil_leaf_return", statements),
            ("exact_array_backend_handoff", handoffs),
            ("selected_body_direct_intrinsic", selected_body_envelopes),
        )
        if values
    )
    if source_family is None and len(active_families) > 1:
        return Result.failure(
            (
                operation_package_source_ambiguous_diagnostic(
                    "lowering operation package source carries multiple "
                    "accepted packageable value families "
                    f"{active_families!r}; pass source_family to choose one",
                    container_location
                    or source_location_from_entries(
                        (
                            *statements,
                            *handoffs,
                            *selected_body_envelopes,
                        ),
                    ),
                ),
            )
        )
    if source_family == "mini_tsil_leaf_return" or (
        source_family is None and statements
    ):
        if not statements:
            return Result.failure(
                (
                    operation_package_missing_value_diagnostic(
                        "lowering operation package requires one accepted M86 "
                        "TsilReturnStatement entry",
                        container_location,
                    ),
                )
            )
        if len(statements) > 1:
            return Result.failure(
                (
                    operation_package_duplicate_value_diagnostic(
                        "lowering operation package requires exactly one "
                        f"accepted M86 TsilReturnStatement; got {len(statements)}",
                        source_location_from_entries(statements)
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
                    operation_package_missing_value_diagnostic(
                        "lowering operation package requires one accepted M92 "
                        "ExactArrayBackendHandoffRequestIr entry",
                        container_location,
                    ),
                )
            )
        if len(handoffs) > 1:
            return Result.failure(
                (
                    operation_package_duplicate_value_diagnostic(
                        "lowering operation package requires exactly one "
                        "accepted M92 ExactArrayBackendHandoffRequestIr; got "
                        f"{len(handoffs)}",
                        source_location_from_entries(handoffs)
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
    if source_family == "selected_body_direct_intrinsic" or (
        source_family is None and selected_body_envelopes
    ):
        if not selected_body_envelopes:
            if generation_selected_body_envelopes:
                return _selected_body_direct_intrinsic_package(
                    generation_selected_body_envelopes[0],
                    candidate_id=candidate_id,
                    source_location=source_location,
                    source_family=source_family,
                )
            return Result.failure(
                (
                    operation_package_missing_value_diagnostic(
                        "lowering operation package requires one accepted M63 "
                        "SelectedBodyEnvelopeIr selected-body entry",
                        container_location,
                    ),
                )
            )
        if len(selected_body_envelopes) > 1:
            return Result.failure(
                (
                    operation_package_duplicate_value_diagnostic(
                        "lowering operation package requires exactly one "
                        "accepted M63 SelectedBodyEnvelopeIr; got "
                        f"{len(selected_body_envelopes)}",
                        source_location_from_entries(selected_body_envelopes)
                        or container_location,
                    ),
                )
            )
        context_result = _merged_candidate_context(
            explicit_candidate_id=candidate_id,
            container_candidate_id=_candidate_id_from_object(source),
            location=container_location or selected_body_envelopes[0].source_location,
        )
        if not context_result.is_ok:
            return Result.failure(context_result.diagnostics)
        return _selected_body_direct_intrinsic_package(
            selected_body_envelopes[0],
            candidate_id=context_result.unwrap(),
            source_location=container_location,
            source_family=source_family,
        )
    return Result.failure(
        (
            operation_package_missing_value_diagnostic(
                "lowering operation package source does not carry an accepted "
                "M86 TsilReturnStatement or accepted M92 "
                "ExactArrayBackendHandoffRequestIr or accepted M63 "
                "SelectedBodyEnvelopeIr",
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
                operation_package_context_mismatch_diagnostic(
                    "mini-TSIL leaf-return operation package requires an "
                    "explicit selected candidate id",
                    source_location,
                ),
            )
        )
    if not is_accepted_m86_tsil_return_statement(statement):
        return Result.failure(
            (
                operation_package_malformed_diagnostic(
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
                operation_package_context_mismatch_diagnostic(
                    "exact-array backend-handoff operation package candidate "
                    "context must match the accepted M92 request",
                    request.source_location,
                ),
            )
        )
    if source_location is not None and source_location != request.source_location:
        return Result.failure(
            (
                operation_package_source_location_mismatch_diagnostic(
                    "exact-array backend-handoff operation package source "
                    "location must match the accepted M92 request",
                    request.source_location,
                ),
            )
        )
    diagnostics = validate_exact_array_backend_handoff_request(request)
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


def _selected_body_direct_intrinsic_package(
    envelope: object,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
    source_family: LoweringOperationPackageSourceFamily | None,
) -> Result[LoweringOperationPackageIr]:
    if isinstance(envelope, NoSelectedBodyEnvelopeIr):
        return Result.failure(
            (
                operation_package_missing_value_diagnostic(
                    "selected-body direct-intrinsic operation package requires "
                    "an accepted M63 SelectedBodyEnvelopeIr selected case; "
                    "got a no-selected-body envelope",
                    envelope.source_location,
                ),
            )
        )
    family_result = _validate_source_family(
        "selected_body_direct_intrinsic",
        source_family,
        source_location_from_object(envelope),
    )
    if not family_result.is_ok:
        return Result.failure(family_result.diagnostics)
    if not isinstance(envelope, SelectedBodyEnvelopeIr):
        return Result.failure(
            (
                operation_package_malformed_diagnostic(
                    "selected-body direct-intrinsic operation package requires "
                    "an accepted M63 SelectedBodyEnvelopeIr",
                    source_location_from_object(envelope),
                ),
            )
        )
    if candidate_id is not None and candidate_id != envelope.candidate_id:
        return Result.failure(
            (
                operation_package_context_mismatch_diagnostic(
                    "selected-body direct-intrinsic operation package candidate "
                    "context must match the accepted M63 envelope",
                    envelope.source_location,
                ),
            )
        )
    if source_location is not None and source_location != envelope.source_location:
        return Result.failure(
            (
                operation_package_source_location_mismatch_diagnostic(
                    "selected-body direct-intrinsic operation package source "
                    "location must match the accepted M63 envelope",
                    envelope.source_location,
                ),
            )
        )
    diagnostics = validate_selected_body_direct_intrinsic_envelope(envelope)
    if diagnostics:
        return Result.failure(diagnostics)
    entry = SelectedBodyDirectIntrinsicOperationPackageEntryIr(envelope)
    return Result.ok(
        LoweringOperationPackageIr(
            source_family="selected_body_direct_intrinsic",
            candidate_id=envelope.candidate_id,
            source_location=envelope.source_location,
            selected_body_direct_intrinsic=entry,
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
                operation_package_context_mismatch_diagnostic(
                    "lowering operation package candidate context must match "
                    "the existing M93 package",
                    package.source_location,
                ),
            )
        )
    if source_location is not None and source_location != package.source_location:
        return Result.failure(
            (
                operation_package_source_location_mismatch_diagnostic(
                    "lowering operation package source location must match "
                    "the existing M93 package",
                    package.source_location,
                ),
            )
        )
    if package.exact_array_backend_handoff is not None:
        diagnostics = validate_exact_array_backend_handoff_request(
            package.exact_array_backend_handoff.source_request,
        )
        if diagnostics:
            return Result.failure(diagnostics)
    if package.selected_body_direct_intrinsic is not None:
        diagnostics = validate_selected_body_direct_intrinsic_envelope(
            package.selected_body_direct_intrinsic.source_envelope,
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
                operation_package_source_family_mismatch_diagnostic(
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
                operation_package_malformed_diagnostic(
                    "lowering operation package source requires statements "
                    "to be a tuple",
                    source_location_from_object(raw_statements),
                ),
            )
        )
    statements: list[TsilReturnStatement] = []
    for entry in raw_statements:
        if not is_tsil_return_statement(entry):
            return Result.failure(
                (
                    operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "statements entry to be an accepted M86 "
                        "TsilReturnStatement",
                        source_location_from_object(entry),
                    ),
                )
            )
        if not is_accepted_m86_tsil_return_statement(entry):
            return Result.failure(
                (
                    operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "statements entry to match an accepted M86 mini-TSIL "
                        "leaf-return shape",
                        source_location_from_object(entry),
                    ),
                )
            )
        statements.append(cast("TsilReturnStatement", entry))
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
                operation_package_malformed_diagnostic(
                    "lowering operation package source requires "
                    "array_backend_handoff_requests to be a tuple",
                    source_location_from_object(raw_handoffs),
                ),
            )
        )
    handoffs: list[ExactArrayBackendHandoffRequestIr] = []
    for entry in raw_handoffs:
        if not isinstance(entry, ExactArrayBackendHandoffRequestIr):
            return Result.failure(
                (
                    operation_package_malformed_diagnostic(
                        "lowering operation package source requires every "
                        "array_backend_handoff_requests entry to be an "
                        "accepted M92 ExactArrayBackendHandoffRequestIr",
                        source_location_from_object(entry),
                    ),
                )
            )
        handoffs.append(entry)
    return Result.ok(tuple(handoffs))


def _container_selected_body_envelopes(
    source: object,
) -> Result[tuple[SelectedBodyEnvelopeIr | NoSelectedBodyEnvelopeIr, ...]]:
    if not hasattr(source, "selected_body_envelopes"):
        return Result.ok(())
    raw_envelopes = getattr(source, "selected_body_envelopes")
    if not isinstance(raw_envelopes, tuple):
        return Result.failure(
            (
                operation_package_malformed_diagnostic(
                    "lowering operation package source requires "
                    "selected_body_envelopes to be a tuple",
                    source_location_from_object(raw_envelopes),
                ),
            )
        )
    selected_body_envelopes: list[
        SelectedBodyEnvelopeIr | NoSelectedBodyEnvelopeIr
    ] = []
    for entry in raw_envelopes:
        if isinstance(entry, SelectedBodyEnvelopeIr):
            selected_body_envelopes.append(entry)
            continue
        if isinstance(entry, NoSelectedBodyEnvelopeIr):
            selected_body_envelopes.append(entry)
            continue
        return Result.failure(
            (
                operation_package_malformed_diagnostic(
                    "lowering operation package source requires every "
                    "selected_body_envelopes entry to be an accepted M63 "
                    "selected/no-selected body envelope",
                    source_location_from_object(entry),
                ),
            )
        )
    return Result.ok(tuple(selected_body_envelopes))


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _is_operation_package_container(source: object) -> bool:
    return hasattr(source, "operation_packages")


def _is_packageable_value_container(source: object) -> bool:
    return hasattr(source, "statements") or hasattr(
        source,
        "array_backend_handoff_requests",
    ) or hasattr(
        source,
        "selected_body_envelopes",
    )


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
                operation_package_context_mismatch_diagnostic(
                    "lowering operation package explicit candidate context "
                    "must match the narrow source container candidate id",
                    location,
                ),
            )
        )
    return Result.ok(explicit_candidate_id or container_candidate_id)
