from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._lowering_backend_boundary_worklist import (
    validate_stage8_backend_boundary_worklist_inventory,
)
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    Stage8BackendBoundaryWorklistEntryIr,
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_expansion_diagnostics import (
    _translation_expansion_context_mismatch_diagnostic,
    _translation_expansion_duplicate_value_diagnostic,
    _translation_expansion_malformed_diagnostic,
    _translation_expansion_provenance_mismatch_diagnostic,
    _translation_expansion_request_unsupported_diagnostic,
    _translation_expansion_source_location_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_translation_expansion_models import (
    EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME,
    SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME,
    Stage8BackendTranslationExpansionRecordIr,
    Stage8BackendTranslationExpansionResultIr,
    Stage8BackendTranslationExpansionResultState,
    Stage8BackendTranslationExpansionRule,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestKind,
    Stage8BackendTranslationRequestRecordIr,
)
from tslgen.lowering._lowering_ir_contracts import (
    LoweringProvenanceIdentity,
    first_provenance_identity_mismatch,
    lowering_ir_key,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_object,
)


def validate_stage8_backend_translation_expansion_result(
    result: object,
) -> tuple[Diagnostic, ...]:
    if not isinstance(result, Stage8BackendTranslationExpansionResultIr):
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion validation requires an "
                "accepted Stage8BackendTranslationExpansionResultIr",
                source_location_from_object(result),
            ),
        )
    inventory = result.source_worklist_inventory
    diagnostics = _validate_worklist_context(
        inventory,
        explicit_candidate_id=result.candidate_id,
        explicit_source_location=result.source_location,
    )
    if diagnostics:
        return diagnostics
    expected_state: Stage8BackendTranslationExpansionResultState = (
        "has_backend_translation_expansion_records"
        if result.records
        else "no_backend_translation_expansion_records"
    )
    if result.result_state != expected_state:
        return (
            _translation_expansion_context_mismatch_diagnostic(
                "Stage 8 backend translation expansion result state must "
                "match accepted expansion records",
                result.source_location,
            ),
    )
    duplicate_key = _first_duplicate_record_key(result.records)
    if duplicate_key == ():
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion records must expose "
                "non-empty tuple keys",
                result.source_location,
            ),
        )
    if duplicate_key is not None:
        return (
            _translation_expansion_duplicate_value_diagnostic(
                "Stage 8 backend translation expansion records must have "
                f"unique keys; duplicate key {duplicate_key!r}",
                result.source_location,
            ),
        )
    entries = _accepted_expansion_entries(inventory)
    for entry in entries:
        if not any(record.source_worklist_entry is entry for record in result.records):
            return (
                _translation_expansion_provenance_mismatch_diagnostic(
                    "Stage 8 backend translation expansion results require "
                    "one deferred, unsupported, or resolved record for each "
                    "accepted M104 worklist entry",
                    entry.source_location,
                ),
            )
    for record in result.records:
        diagnostics = validate_stage8_backend_translation_expansion_record(
            inventory,
            record,
        )
        if diagnostics:
            return diagnostics
    if _has_deferred_record_conflict(result.records):
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion deferred records must "
                "not appear with rule-backed records for the same worklist entry",
                result.source_location,
            ),
        )
    return ()


def validate_stage8_backend_translation_expansion_record(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    record: object,
) -> tuple[Diagnostic, ...]:
    if not isinstance(record, Stage8BackendTranslationExpansionRecordIr):
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion records must be "
                "accepted Stage8BackendTranslationExpansionRecordIr values",
                source_location_from_object(record),
            ),
        )
    if lowering_ir_key(record) is None:
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion records must expose a "
                "non-empty tuple key",
                record.source_location,
            ),
        )
    if record.source_worklist_inventory is not inventory:
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                "Stage 8 backend translation expansion records must preserve "
                "M103 worklist inventory object identity",
                record.source_location,
            ),
        )
    entry = record.source_worklist_entry
    if not any(entry is accepted for accepted in _accepted_expansion_entries(inventory)):
        return (
            _translation_expansion_request_unsupported_diagnostic(
                "Stage 8 backend translation expansion records support only "
                "accepted unresolved exact-array and deferred selected-body "
                "worklist entries",
                record.source_location,
            ),
        )
    request = entry.source_request_record
    if request is None or record.source_request_record is not request:
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                "Stage 8 backend translation expansion records must preserve "
                "M99 request record object identity from the worklist entry",
                record.source_location,
            ),
        )
    expected_kind = _record_kind_for_request(request)
    if expected_kind is None or record.record_kind != expected_kind:
        return (
            _translation_expansion_request_unsupported_diagnostic(
                "Stage 8 backend translation expansion records support only "
                "accepted M99 exact-array and selected-body request kinds",
                record.source_location,
            ),
        )
    return _validate_record_state(record)


def _validate_worklist_context(
    inventory: object,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    if not isinstance(inventory, Stage8BackendBoundaryWorklistInventoryIr):
        return (
            _translation_expansion_malformed_diagnostic(
                "Stage 8 backend translation expansion requires an accepted "
                "concrete M103 Stage8BackendBoundaryWorklistInventoryIr",
                source_location_from_object(inventory),
            ),
        )
    diagnostics = validate_stage8_backend_boundary_worklist_inventory(inventory)
    if diagnostics:
        return (_remap_diagnostic(diagnostics[0], inventory.source_location),)
    if explicit_candidate_id is not None and explicit_candidate_id != inventory.candidate_id:
        return (
            _translation_expansion_context_mismatch_diagnostic(
                "Stage 8 backend translation expansion candidate context "
                "must match the accepted M103 worklist inventory",
                inventory.source_location,
            ),
        )
    if (
        explicit_source_location is not None
        and explicit_source_location != inventory.source_location
    ):
        return (
            _translation_expansion_source_location_mismatch_diagnostic(
                "Stage 8 backend translation expansion source location must "
                "match the accepted M103 worklist inventory",
                inventory.source_location,
            ),
        )
    return ()


def _accepted_expansion_entries(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
) -> tuple[Stage8BackendBoundaryWorklistEntryIr, ...]:
    return tuple(
        entry
        for entry in inventory.entries
        if (
            entry.classification == "exact_array_backend_uninit_unresolved"
            and _record_kind_for_request(entry.source_request_record)
            == "exact_array_backend_uninit"
        )
        or (
            entry.classification == "selected_body_direct_intrinsic_deferred"
            and _record_kind_for_request(entry.source_request_record)
            == "selected_body_direct_intrinsic"
        )
    )


def _record_kind_for_request(
    request: Stage8BackendTranslationRequestRecordIr | None,
) -> str | None:
    if request is None:
        return None
    if request.kind == "exact_array_backend_value_uninit_array":
        return "exact_array_backend_uninit"
    if request.kind == "selected_body_direct_intrinsic_handoff":
        return "selected_body_direct_intrinsic"
    return None


def _expected_result_name_for_request_kind(
    kind: Stage8BackendTranslationRequestKind,
) -> str | None:
    if kind == "exact_array_backend_value_uninit_array":
        return EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME
    if kind == "selected_body_direct_intrinsic_handoff":
        return SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME
    return None


def _validate_record_state(
    record: Stage8BackendTranslationExpansionRecordIr,
) -> tuple[Diagnostic, ...]:
    if record.record_state == "resolved":
        return _validate_resolved_record(record)
    if record.record_state == "deferred":
        return _validate_deferred_record(record)
    if record.record_state == "unsupported":
        return _validate_unsupported_record(record)
    return (
        _translation_expansion_malformed_diagnostic(
            "Stage 8 backend translation expansion records support only "
            "resolved, deferred, or unsupported states",
            record.source_location,
        ),
    )


def _validate_resolved_record(
    record: Stage8BackendTranslationExpansionRecordIr,
) -> tuple[Diagnostic, ...]:
    if len(record.source_rules) != 1:
        return (
            _translation_expansion_malformed_diagnostic(
                "resolved backend translation expansion records require "
                "exactly one typed source rule",
                record.source_location,
            ),
        )
    rule = record.source_rules[0]
    diagnostics = _validate_rule_against_record(record, rule)
    if diagnostics:
        return diagnostics
    if record.translated_value != rule.translated_value:
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                "resolved backend translation expansion records must preserve "
                "the explicit rule translated value",
                record.source_location,
            ),
        )
    if record.diagnostics:
        return (
            _translation_expansion_malformed_diagnostic(
                "resolved backend translation expansion records must not "
                "carry diagnostics",
                record.source_location,
            ),
        )
    return ()


def _validate_deferred_record(
    record: Stage8BackendTranslationExpansionRecordIr,
) -> tuple[Diagnostic, ...]:
    if record.source_rules or record.backend_id or record.result_name:
        return (
            _translation_expansion_malformed_diagnostic(
                "deferred backend translation expansion records must not "
                "carry source rules or backend result context",
                record.source_location,
            ),
        )
    if record.translated_value is not None:
        return (
            _translation_expansion_malformed_diagnostic(
                "deferred backend translation expansion records must not "
                "carry translated values",
                record.source_location,
            ),
        )
    return _validate_record_diagnostics(record)


def _validate_unsupported_record(
    record: Stage8BackendTranslationExpansionRecordIr,
) -> tuple[Diagnostic, ...]:
    if record.translated_value is not None:
        return (
            _translation_expansion_malformed_diagnostic(
                "unsupported backend translation expansion records must not "
                "carry translated values",
                record.source_location,
            ),
        )
    for rule in record.source_rules:
        if not isinstance(rule, Stage8BackendTranslationExpansionRule):
            return (
                _translation_expansion_malformed_diagnostic(
                    "unsupported backend translation expansion records require "
                    "typed source rule values",
                    record.source_location,
                ),
            )
        if rule.source_worklist_entry is not record.source_worklist_entry:
            return (
                _translation_expansion_provenance_mismatch_diagnostic(
                    "unsupported backend translation expansion records must "
                    "preserve source rule to worklist entry object identity",
                    record.source_location,
                ),
            )
    return _validate_record_diagnostics(record)


def _validate_rule_against_record(
    record: Stage8BackendTranslationExpansionRecordIr,
    rule: object,
) -> tuple[Diagnostic, ...]:
    if not isinstance(rule, Stage8BackendTranslationExpansionRule):
        return (
            _translation_expansion_malformed_diagnostic(
                "backend translation expansion records require typed source "
                "rule values",
                record.source_location,
            ),
        )
    request = record.source_request_record
    expected_kind = _record_kind_for_request(request)
    expected_result_name = _expected_result_name_for_request_kind(request.kind)
    identity_mismatch = first_provenance_identity_mismatch(
        (
            LoweringProvenanceIdentity(
                rule.source_worklist_entry,
                record.source_worklist_entry,
                "source worklist entry object identity",
            ),
            LoweringProvenanceIdentity(
                rule.source_request_record,
                request,
                "source request record object identity",
            ),
        )
    )
    if identity_mismatch is not None:
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                "backend translation expansion rules must preserve "
                f"{identity_mismatch}",
                rule.source_location or record.source_location,
            ),
        )
    if rule.rule_kind != expected_kind or rule.result_name != expected_result_name:
        return (
            _translation_expansion_request_unsupported_diagnostic(
                "backend translation expansion rules must match the accepted "
                "typed request kind and result name",
                rule.source_location or record.source_location,
            ),
        )
    if record.backend_id != rule.backend_id or record.result_name != rule.result_name:
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                "backend translation expansion records must preserve explicit "
                "rule backend and result names",
                rule.source_location or record.source_location,
            ),
        )
    return ()


def _validate_record_diagnostics(
    record: Stage8BackendTranslationExpansionRecordIr,
) -> tuple[Diagnostic, ...]:
    if not record.diagnostics:
        return (
            _translation_expansion_malformed_diagnostic(
                "deferred and unsupported backend translation expansion "
                "records require diagnostics",
                record.source_location,
            ),
        )
    if not all(isinstance(diagnostic, Diagnostic) for diagnostic in record.diagnostics):
        return (
            _translation_expansion_malformed_diagnostic(
                "backend translation expansion record diagnostics must be "
                "typed Diagnostic values",
                record.source_location,
            ),
        )
    return ()


def _first_duplicate_record_key(
    records: tuple[Stage8BackendTranslationExpansionRecordIr, ...],
) -> tuple[object, ...] | None:
    seen: set[tuple[object, ...]] = set()
    for record in records:
        key = lowering_ir_key(record)
        if key is None:
            return ()
        if key in seen:
            return key
        seen.add(key)
    return None


def _has_deferred_record_conflict(
    records: tuple[Stage8BackendTranslationExpansionRecordIr, ...],
) -> bool:
    seen_rule_backed: set[int] = set()
    seen_deferred: set[int] = set()
    for record in records:
        entry_id = id(record.source_worklist_entry)
        if record.record_state == "deferred":
            seen_deferred.add(entry_id)
        else:
            seen_rule_backed.add(entry_id)
    return bool(seen_rule_backed & seen_deferred)


def _remap_diagnostic(
    diagnostic: Diagnostic,
    fallback_location: SourceLocation | None,
) -> Diagnostic:
    location = diagnostic.location or fallback_location
    if diagnostic.code.endswith("PROVENANCE-MISMATCH"):
        return _translation_expansion_provenance_mismatch_diagnostic(
            diagnostic.message,
            location,
        )
    if diagnostic.code.endswith("CONTEXT-MISMATCH"):
        return _translation_expansion_context_mismatch_diagnostic(
            diagnostic.message,
            location,
        )
    if diagnostic.code.endswith("SOURCE-LOCATION-MISMATCH"):
        return _translation_expansion_source_location_mismatch_diagnostic(
            diagnostic.message,
            location,
        )
    if diagnostic.code.endswith("VALUE-MULTIPLE"):
        return _translation_expansion_duplicate_value_diagnostic(
            diagnostic.message,
            location,
        )
    return _translation_expansion_malformed_diagnostic(diagnostic.message, location)
