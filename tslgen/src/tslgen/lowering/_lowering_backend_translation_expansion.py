from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT,
    STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT,
    Stage8BackendBoundaryWorklistEntryIr,
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_expansion_diagnostics import (
    _translation_expansion_conflicting_rule_diagnostic,
    _translation_expansion_context_mismatch_diagnostic,
    _translation_expansion_duplicate_value_diagnostic,
    _translation_expansion_malformed_diagnostic,
    _translation_expansion_provenance_mismatch_diagnostic,
    _translation_expansion_request_unsupported_diagnostic,
    _translation_expansion_rule_mismatch_diagnostic,
    _translation_expansion_rule_missing_diagnostic,
    _translation_expansion_source_location_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_translation_expansion_models import (
    EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME,
    SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME,
    STAGE8_BACKEND_TRANSLATION_EXPANSION_RECORD_CONTRACT,
    STAGE8_BACKEND_TRANSLATION_EXPANSION_RESULT_CONTRACT,
    STAGE8_BACKEND_TRANSLATION_EXPANSION_RULE_CONTRACT,
    Stage8BackendTranslationExpansionRecordIr,
    Stage8BackendTranslationExpansionResultIr,
    Stage8BackendTranslationExpansionRule,
)
from tslgen.lowering._lowering_backend_translation_expansion_sources import (
    _worklist_inventory_source,
)
from tslgen.lowering._lowering_backend_translation_expansion_validation import (
    _accepted_expansion_entries,
    _record_kind_for_request,
    _validate_worklist_context,
    validate_stage8_backend_translation_expansion_record,
    validate_stage8_backend_translation_expansion_result,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestRecordIr,
)
from tslgen.lowering._lowering_ir_contracts import lowering_ir_key
from tslgen.lowering._operation_package_diagnostics import (
    source_location_from_entries,
)


__all__ = (
    "EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME",
    "SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME",
    "STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT",
    "STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT",
    "STAGE8_BACKEND_TRANSLATION_EXPANSION_RECORD_CONTRACT",
    "STAGE8_BACKEND_TRANSLATION_EXPANSION_RESULT_CONTRACT",
    "STAGE8_BACKEND_TRANSLATION_EXPANSION_RULE_CONTRACT",
    "Stage8BackendTranslationExpansionRecordIr",
    "Stage8BackendTranslationExpansionResultIr",
    "Stage8BackendTranslationExpansionRule",
    "lower_stage8_backend_translation_expansion_result",
    "validate_stage8_backend_translation_expansion_record",
    "validate_stage8_backend_translation_expansion_result",
)


def lower_stage8_backend_translation_expansion_result(
    source: object,
    *,
    rules: tuple[Stage8BackendTranslationExpansionRule, ...] = (),
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
) -> Result[Stage8BackendTranslationExpansionResultIr]:
    source_result = _worklist_inventory_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    inventory = source_result.unwrap()

    diagnostics = _validate_context(
        inventory,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    rule_result = _validated_rules_tuple(rules, inventory)
    if not rule_result.is_ok:
        return Result.failure(rule_result.diagnostics)
    typed_rules = rule_result.unwrap()

    try:
        records = _expansion_records(inventory, typed_rules)
        result = Stage8BackendTranslationExpansionResultIr(
            candidate_id=candidate_id or inventory.candidate_id,
            source_location=source_location or inventory.source_location,
            result_state=(
                "has_backend_translation_expansion_records"
                if records
                else "no_backend_translation_expansion_records"
            ),
            source_worklist_inventory=inventory,
            records=records,
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _translation_expansion_malformed_diagnostic(
                    str(exc),
                    source_location or inventory.source_location,
                ),
            )
        )
    return Result.ok(result)


def _validate_context(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    diagnostics = _validate_worklist_context(
        inventory,
        explicit_candidate_id=explicit_candidate_id,
        explicit_source_location=explicit_source_location,
    )
    if not diagnostics:
        return ()
    first = diagnostics[0]
    if first.code.endswith("PROVENANCE-MISMATCH"):
        return (
            _translation_expansion_provenance_mismatch_diagnostic(
                first.message,
                first.location or inventory.source_location,
            ),
        )
    if first.code.endswith("CONTEXT-MISMATCH"):
        return (
            _translation_expansion_context_mismatch_diagnostic(
                first.message,
                first.location or inventory.source_location,
            ),
        )
    if first.code.endswith("SOURCE-LOCATION-MISMATCH"):
        return (
            _translation_expansion_source_location_mismatch_diagnostic(
                first.message,
                first.location or inventory.source_location,
            ),
        )
    return diagnostics


def _validated_rules_tuple(
    rules: object,
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
) -> Result[tuple[Stage8BackendTranslationExpansionRule, ...]]:
    if not isinstance(rules, tuple):
        return Result.failure(
            (
                _translation_expansion_malformed_diagnostic(
                    "Stage 8 backend translation expansion rules must be a tuple",
                    None,
                ),
            )
        )
    malformed = tuple(
        rule
        for rule in rules
        if not isinstance(rule, Stage8BackendTranslationExpansionRule)
    )
    if malformed:
        return Result.failure(
            (
                _translation_expansion_malformed_diagnostic(
                    "Stage 8 backend translation expansion rules must be "
                    "typed Stage8BackendTranslationExpansionRule values",
                    source_location_from_entries(malformed),
                ),
            )
        )
    typed_rules = tuple(rules)
    entry_ids = {id(entry) for entry in _accepted_expansion_entries(inventory)}
    for rule in typed_rules:
        if id(rule.source_worklist_entry) not in entry_ids:
            return Result.failure(
                (
                    _translation_expansion_provenance_mismatch_diagnostic(
                        "Stage 8 backend translation expansion rules must "
                        "reference accepted M104 worklist entries by object "
                        "identity",
                        rule.source_location or rule.source_worklist_entry.source_location,
                    ),
                )
            )
        if lowering_ir_key(rule) is None:
            return Result.failure(
                (
                    _translation_expansion_malformed_diagnostic(
                        "Stage 8 backend translation expansion rules must "
                        "expose non-empty tuple keys",
                        rule.source_location,
                    ),
                )
            )
    return Result.ok(typed_rules)


def _expansion_records(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    rules: tuple[Stage8BackendTranslationExpansionRule, ...],
) -> tuple[Stage8BackendTranslationExpansionRecordIr, ...]:
    records: list[Stage8BackendTranslationExpansionRecordIr] = []
    for entry in _accepted_expansion_entries(inventory):
        entry_rules = tuple(
            rule for rule in rules if rule.source_worklist_entry is entry
        )
        if not entry_rules:
            records.append(_deferred_record(inventory, entry))
            continue
        for group in _rule_groups(entry_rules):
            records.append(_record_for_rule_group(inventory, entry, group))
    return tuple(records)


def _deferred_record(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> Stage8BackendTranslationExpansionRecordIr:
    request = _entry_request(entry)
    return Stage8BackendTranslationExpansionRecordIr(
        source_worklist_inventory=inventory,
        source_worklist_entry=entry,
        source_request_record=request,
        record_kind=_record_kind_for_request(request) or "unsupported_request",
        record_state="deferred",
        diagnostics=(
            _translation_expansion_rule_missing_diagnostic(
                "Stage 8 backend translation expansion deferred because no "
                "explicit typed rule was supplied for the accepted worklist entry",
                entry.source_location,
            ),
        ),
    )


def _record_for_rule_group(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
    rules: tuple[Stage8BackendTranslationExpansionRule, ...],
) -> Stage8BackendTranslationExpansionRecordIr:
    request = _entry_request(entry)
    first = rules[0]
    record_kind = _record_kind_for_request(request) or "unsupported_request"
    if len(rules) > 1:
        translated_values = {rule.translated_value for rule in rules}
        diagnostic = (
            _translation_expansion_conflicting_rule_diagnostic(
                "Stage 8 backend translation expansion requires unambiguous "
                "typed rules for each worklist entry backend result",
                first.source_location or entry.source_location,
            )
            if len(translated_values) > 1
            else _translation_expansion_duplicate_value_diagnostic(
                "Stage 8 backend translation expansion requires exactly one "
                "typed rule for each worklist entry backend result",
                first.source_location or entry.source_location,
            )
        )
        return _unsupported_record(
            inventory,
            entry,
            request,
            record_kind=record_kind,
            backend_id=first.backend_id,
            result_name=first.result_name,
            rules=rules,
            diagnostic=diagnostic,
        )
    rule = first
    rule_diagnostic = _rule_issue(entry, request, rule)
    if rule_diagnostic is not None:
        return _unsupported_record(
            inventory,
            entry,
            request,
            record_kind=record_kind,
            backend_id=rule.backend_id,
            result_name=rule.result_name,
            rules=(rule,),
            diagnostic=rule_diagnostic,
        )
    return Stage8BackendTranslationExpansionRecordIr(
        source_worklist_inventory=inventory,
        source_worklist_entry=entry,
        source_request_record=request,
        record_kind=record_kind,
        record_state="resolved",
        backend_id=rule.backend_id,
        result_name=rule.result_name,
        translated_value=rule.translated_value,
        source_rules=(rule,),
    )


def _unsupported_record(
    inventory: Stage8BackendBoundaryWorklistInventoryIr,
    entry: Stage8BackendBoundaryWorklistEntryIr,
    request: Stage8BackendTranslationRequestRecordIr,
    *,
    record_kind: str,
    backend_id: str | None,
    result_name: str | None,
    rules: tuple[Stage8BackendTranslationExpansionRule, ...],
    diagnostic: Diagnostic,
) -> Stage8BackendTranslationExpansionRecordIr:
    return Stage8BackendTranslationExpansionRecordIr(
        source_worklist_inventory=inventory,
        source_worklist_entry=entry,
        source_request_record=request,
        record_kind=record_kind,
        record_state="unsupported",
        backend_id=backend_id,
        result_name=result_name,
        source_rules=rules,
        diagnostics=(diagnostic,),
    )


def _rule_issue(
    entry: Stage8BackendBoundaryWorklistEntryIr,
    request: Stage8BackendTranslationRequestRecordIr,
    rule: Stage8BackendTranslationExpansionRule,
) -> Diagnostic | None:
    if rule.source_request_record is not request:
        return _translation_expansion_provenance_mismatch_diagnostic(
            "Stage 8 backend translation expansion rules must preserve M99 "
            "request record object identity from the accepted worklist entry",
            rule.source_location or entry.source_location,
        )
    if _record_kind_for_request(rule.source_request_record) != rule.rule_kind:
        return _translation_expansion_rule_mismatch_diagnostic(
            "Stage 8 backend translation expansion rules must match the typed "
            "request kind carried by the accepted M99 request record",
            rule.source_location or entry.source_location,
        )
    expected_name = (
        EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME
        if rule.rule_kind == "exact_array_backend_uninit"
        else SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME
        if rule.rule_kind == "selected_body_direct_intrinsic"
        else None
    )
    if rule.result_name != expected_name:
        return _translation_expansion_request_unsupported_diagnostic(
            "Stage 8 backend translation expansion rules must name an "
            "accepted typed backend result for the request kind",
            rule.source_location or entry.source_location,
        )
    return None


def _rule_groups(
    rules: tuple[Stage8BackendTranslationExpansionRule, ...],
) -> tuple[tuple[Stage8BackendTranslationExpansionRule, ...], ...]:
    ordered = sorted(rules, key=lambda rule: rule.key)
    groups: list[tuple[Stage8BackendTranslationExpansionRule, ...]] = []
    while ordered:
        first = ordered[0]
        matching = tuple(
            rule
            for rule in ordered
            if (rule.backend_id, rule.result_name) == (first.backend_id, first.result_name)
        )
        groups.append(matching)
        ordered = [
            rule
            for rule in ordered
            if (rule.backend_id, rule.result_name) != (first.backend_id, first.result_name)
        ]
    return tuple(groups)


def _entry_request(
    entry: Stage8BackendBoundaryWorklistEntryIr,
) -> Stage8BackendTranslationRequestRecordIr:
    request = entry.source_request_record
    if request is None:
        raise ValueError(
            "translation expansion entries require accepted M99 request records"
        )
    return request
