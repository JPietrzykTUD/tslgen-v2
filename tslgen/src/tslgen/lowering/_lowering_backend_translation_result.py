from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._lowering_ir_contracts import (
    EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RECORD_CONTRACT,
    EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RESULT_CONTRACT,
    EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RULE_CONTRACT,
    LoweringIrContract,
    LoweringIrKeyComparable,
    LoweringProvenanceIdentity,
    first_provenance_identity_mismatch,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestInventoryIr,
    Stage8BackendTranslationRequestRecordIr,
    validate_stage8_backend_translation_request_inventory,
)
from tslgen.lowering._lowering_backend_translation_result_diagnostics import (
    _translation_result_backend_unsupported_diagnostic,
    _translation_result_conflicting_rule_diagnostic,
    _translation_result_context_mismatch_diagnostic,
    _translation_result_duplicate_value_diagnostic,
    _translation_result_malformed_diagnostic,
    _translation_result_missing_value_diagnostic,
    _translation_result_provenance_mismatch_diagnostic,
    _translation_result_request_unsupported_diagnostic,
    _translation_result_source_location_mismatch_diagnostic,
)
from tslgen.lowering._lowering_backend_translation_result_sources import (
    _request_inventory_source,
)
from tslgen.lowering._operation_package_diagnostics import source_location_key


type ExactArrayBackendUninitTranslationResultState = Literal[
    "has_exact_array_backend_uninit_translation_result",
    "no_exact_array_backend_uninit_translation_result",
]
type ExactArrayBackendUninitTranslationRuleName = Literal["value_array_uninit"]


@dataclass(frozen=True, slots=True, eq=False)
class ExactArrayBackendUninitTranslationRule(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RULE_CONTRACT
    )

    backend_id: str
    rule_name: str
    translated_value: str
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("backend-uninit translation rule backend id must be non-empty")
        if not self.rule_name:
            raise ValueError("backend-uninit translation rule name must be non-empty")
        if self.translated_value == "":
            raise ValueError(
                "backend-uninit translation rule value must be non-empty"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_uninit_translation_rule",
            self.backend_id,
            self.rule_name,
            self.translated_value,
            source_location_key(self.source_location),
        )


@dataclass(frozen=True, slots=True, eq=False)
class ExactArrayBackendUninitTranslationRecordIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RECORD_CONTRACT
    )

    source_request_inventory: Stage8BackendTranslationRequestInventoryIr
    source_request_record: Stage8BackendTranslationRequestRecordIr
    source_rule: ExactArrayBackendUninitTranslationRule

    def __post_init__(self) -> None:
        diagnostics = _validate_translation_record(
            self.source_request_inventory,
            self,
        )
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_request_inventory.candidate_id

    @property
    def backend_id(self) -> str:
        return self.source_rule.backend_id

    @property
    def value_key(self) -> str:
        return self.source_rule.rule_name

    @property
    def translated_value(self) -> str:
        return self.source_rule.translated_value

    @property
    def source_location(self) -> SourceLocation | None:
        return self.source_request_record.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_uninit_translation_record",
            self.candidate_id,
            self.backend_id,
            self.value_key,
            self.source_request_inventory.key,
            self.source_request_record.key,
            self.source_rule.key,
        )


@dataclass(frozen=True, slots=True, eq=False)
class ExactArrayBackendUninitTranslationResultIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RESULT_CONTRACT
    )

    candidate_id: str
    source_location: SourceLocation | None
    result_state: ExactArrayBackendUninitTranslationResultState
    source_request_inventory: Stage8BackendTranslationRequestInventoryIr
    result_records: tuple[ExactArrayBackendUninitTranslationRecordIr, ...] = ()
    deferred_request_records: tuple[Stage8BackendTranslationRequestRecordIr, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "exact-array backend-uninit translation result candidate id "
                "must be non-empty"
            )
        object.__setattr__(self, "result_records", tuple(self.result_records))
        object.__setattr__(
            self,
            "deferred_request_records",
            tuple(self.deferred_request_records),
        )
        diagnostics = validate_exact_array_backend_uninit_translation_result(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_backend_uninit_translation_result",
            self.candidate_id,
            source_location_key(self.source_location),
            self.result_state,
            self.source_request_inventory.key,
            tuple(record.key for record in self.result_records),
            tuple(record.key for record in self.deferred_request_records),
        )


def lower_exact_array_backend_uninit_translation_result(
    source: object,
    *,
    cpp_value_array_uninit_rules: tuple[
        ExactArrayBackendUninitTranslationRule,
        ...,
    ] = (),
    candidate_id: str | None = None,
    source_location: SourceLocation | None = None,
    require_result: bool = False,
) -> Result[ExactArrayBackendUninitTranslationResultIr]:
    if isinstance(source, ExactArrayBackendUninitTranslationResultIr):
        return _validate_existing_result(
            source,
            candidate_id=candidate_id,
            source_location=source_location,
        )

    inventory_result = _request_inventory_source(source)
    if not inventory_result.is_ok:
        return Result.failure(inventory_result.diagnostics)
    inventory = inventory_result.unwrap()

    diagnostics = _validate_inventory_context(
        inventory,
        explicit_candidate_id=candidate_id,
        explicit_source_location=source_location,
    )
    if diagnostics:
        return Result.failure(diagnostics)

    exact_records = _exact_array_request_records(inventory)
    deferred_records = tuple(
        record
        for record in inventory.request_records
        if record.kind != "exact_array_backend_value_uninit_array"
    )
    if require_result and not exact_records:
        return Result.failure(
            (
                _translation_result_request_unsupported_diagnostic(
                    "exact-array backend-uninit translation result requires "
                    "an accepted exact-array backend-value request record",
                    inventory.source_location,
                ),
            )
        )
    rule: ExactArrayBackendUninitTranslationRule | None = None
    if exact_records:
        rule_result = _single_cpp_value_array_uninit_rule(
            tuple(cpp_value_array_uninit_rules),
        )
        if not rule_result.is_ok:
            return Result.failure(rule_result.diagnostics)
        rule = rule_result.unwrap()

    try:
        result_records = (
            tuple(
                ExactArrayBackendUninitTranslationRecordIr(
                    source_request_inventory=inventory,
                    source_request_record=record,
                    source_rule=rule,
                )
                for record in exact_records
            )
            if rule is not None
            else ()
        )
        result = ExactArrayBackendUninitTranslationResultIr(
            candidate_id=candidate_id or inventory.candidate_id,
            source_location=source_location or inventory.source_location,
            result_state=(
                "has_exact_array_backend_uninit_translation_result"
                if result_records
                else "no_exact_array_backend_uninit_translation_result"
            ),
            source_request_inventory=inventory,
            result_records=result_records,
            deferred_request_records=deferred_records,
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    str(exc),
                    source_location or inventory.source_location,
                ),
            )
        )
    return Result.ok(result)


def validate_exact_array_backend_uninit_translation_result(
    result: ExactArrayBackendUninitTranslationResultIr,
) -> tuple[Diagnostic, ...]:
    inventory = result.source_request_inventory
    diagnostics = _validate_inventory_context(
        inventory,
        explicit_candidate_id=result.candidate_id,
        explicit_source_location=result.source_location,
    )
    if diagnostics:
        return diagnostics

    expected_exact_records = _exact_array_request_records(inventory)
    expected_deferred_records = tuple(
        record
        for record in inventory.request_records
        if record.kind != "exact_array_backend_value_uninit_array"
    )
    expected_state: ExactArrayBackendUninitTranslationResultState = (
        "has_exact_array_backend_uninit_translation_result"
        if result.result_records
        else "no_exact_array_backend_uninit_translation_result"
    )
    if result.result_state != expected_state:
        return (
            _translation_result_context_mismatch_diagnostic(
                "exact-array backend-uninit translation result state must "
                "match accepted exact-array result records",
                result.source_location,
            ),
        )
    if len(result.result_records) != len(expected_exact_records):
        return (
            _translation_result_provenance_mismatch_diagnostic(
                "exact-array backend-uninit translation result requires one "
                "result record for each accepted exact-array backend-value "
                "request",
                result.source_location,
            ),
        )
    if len(result.deferred_request_records) != len(expected_deferred_records):
        return (
            _translation_result_provenance_mismatch_diagnostic(
                "exact-array backend-uninit translation result must preserve "
                "non-exact-array request records as deferred request records",
                result.source_location,
            ),
        )
    for actual, expected_record in zip(
        result.result_records,
        expected_exact_records,
        strict=True,
    ):
        identity_mismatch = first_provenance_identity_mismatch(
            (
                LoweringProvenanceIdentity(
                    actual.source_request_record,
                    expected_record,
                    "accepted M99 request record object identity",
                ),
            )
        )
        if identity_mismatch is not None:
            return (
                _translation_result_provenance_mismatch_diagnostic(
                    "exact-array backend-uninit translation records must "
                    f"preserve {identity_mismatch}",
                    actual.source_location,
                ),
            )
        diagnostics = _validate_translation_record(inventory, actual)
        if diagnostics:
            return diagnostics
    for actual_deferred, expected_deferred in zip(
        result.deferred_request_records,
        expected_deferred_records,
        strict=True,
    ):
        identity_mismatch = first_provenance_identity_mismatch(
            (
                LoweringProvenanceIdentity(
                    actual_deferred,
                    expected_deferred,
                    "deferred request record object identity",
                ),
            )
        )
        if identity_mismatch is not None:
            return (
                _translation_result_provenance_mismatch_diagnostic(
                    "exact-array backend-uninit translation results must "
                    f"preserve {identity_mismatch}",
                    actual_deferred.source_location,
                ),
            )
    return ()


def _validate_existing_result(
    result: ExactArrayBackendUninitTranslationResultIr,
    *,
    candidate_id: str | None,
    source_location: SourceLocation | None,
) -> Result[ExactArrayBackendUninitTranslationResultIr]:
    if candidate_id is not None and candidate_id != result.candidate_id:
        return Result.failure(
            (
                _translation_result_context_mismatch_diagnostic(
                    "exact-array backend-uninit translation result candidate "
                    "context must match the existing result",
                    result.source_location,
                ),
            )
        )
    if source_location is not None and source_location != result.source_location:
        return Result.failure(
            (
                _translation_result_source_location_mismatch_diagnostic(
                    "exact-array backend-uninit translation result source "
                    "location must match the existing result",
                    result.source_location,
                ),
            )
        )
    diagnostics = validate_exact_array_backend_uninit_translation_result(result)
    if diagnostics:
        return Result.failure(diagnostics)
    return Result.ok(result)


def _validate_inventory_context(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    *,
    explicit_candidate_id: str | None,
    explicit_source_location: SourceLocation | None,
) -> tuple[Diagnostic, ...]:
    inventory_diagnostics = validate_stage8_backend_translation_request_inventory(
        inventory,
    )
    if inventory_diagnostics:
        first = inventory_diagnostics[0]
        if first.code.endswith("PROVENANCE-MISMATCH"):
            return (
                _translation_result_provenance_mismatch_diagnostic(
                    first.message,
                    first.location or inventory.source_location,
                ),
            )
        if first.code.endswith("CONTEXT-MISMATCH"):
            return (
                _translation_result_context_mismatch_diagnostic(
                    first.message,
                    first.location or inventory.source_location,
                ),
            )
        if first.code.endswith("SOURCE-LOCATION-MISMATCH"):
            return (
                _translation_result_source_location_mismatch_diagnostic(
                    first.message,
                    first.location or inventory.source_location,
                ),
            )
        return (
            _translation_result_malformed_diagnostic(
                first.message,
                first.location or inventory.source_location,
            ),
        )
    if (
        explicit_candidate_id is not None
        and explicit_candidate_id != inventory.candidate_id
    ):
        return (
            _translation_result_context_mismatch_diagnostic(
                "exact-array backend-uninit translation result candidate "
                "context must match the accepted request inventory",
                inventory.source_location,
            ),
        )
    if (
        explicit_source_location is not None
        and explicit_source_location != inventory.source_location
    ):
        return (
            _translation_result_source_location_mismatch_diagnostic(
                "exact-array backend-uninit translation result source "
                "location must match the accepted request inventory",
                inventory.source_location,
            ),
        )
    return ()


def _single_cpp_value_array_uninit_rule(
    rules: tuple[ExactArrayBackendUninitTranslationRule, ...],
) -> Result[ExactArrayBackendUninitTranslationRule]:
    malformed = tuple(
        rule
        for rule in rules
        if not isinstance(rule, ExactArrayBackendUninitTranslationRule)
    )
    if malformed:
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation rules must be "
                    "typed ExactArrayBackendUninitTranslationRule values",
                    None,
                ),
            )
        )
    cpp_rules = tuple(
        rule
        for rule in rules
        if rule.backend_id == "cpp" and rule.rule_name == "value_array_uninit"
    )
    malformed_rule_names = tuple(
        rule
        for rule in rules
        if rule.backend_id == "cpp" and rule.rule_name != "value_array_uninit"
    )
    unsupported_backend_rules = tuple(
        rule
        for rule in rules
        if rule.backend_id != "cpp" and rule.rule_name == "value_array_uninit"
    )
    if malformed_rule_names:
        first = malformed_rule_names[0]
        return Result.failure(
            (
                _translation_result_malformed_diagnostic(
                    "exact-array backend-uninit translation result supports "
                    "only the value_array_uninit rule name for cpp rules",
                    first.source_location,
                ),
            )
        )
    if unsupported_backend_rules:
        first = unsupported_backend_rules[0]
        return Result.failure(
            (
                _translation_result_backend_unsupported_diagnostic(
                    "exact-array backend-uninit translation result supports "
                    "only the cpp value_array_uninit rule",
                    first.source_location,
                ),
            )
        )
    if not cpp_rules:
        return Result.failure(
            (
                _translation_result_missing_value_diagnostic(
                    "exact-array backend-uninit translation result requires "
                    "one typed cpp value_array_uninit rule",
                    None,
                ),
            )
        )
    if len(cpp_rules) > 1:
        translated_values = {rule.translated_value for rule in cpp_rules}
        if len(translated_values) > 1:
            return Result.failure(
                (
                    _translation_result_conflicting_rule_diagnostic(
                        "exact-array backend-uninit translation result "
                        "requires one unambiguous cpp value_array_uninit rule",
                        cpp_rules[0].source_location,
                    ),
                )
            )
        return Result.failure(
            (
                _translation_result_duplicate_value_diagnostic(
                    "exact-array backend-uninit translation result requires "
                    "exactly one cpp value_array_uninit rule; got "
                    f"{len(cpp_rules)}",
                    cpp_rules[0].source_location,
                ),
            )
        )
    return Result.ok(cpp_rules[0])


def _exact_array_request_records(
    inventory: Stage8BackendTranslationRequestInventoryIr,
) -> tuple[Stage8BackendTranslationRequestRecordIr, ...]:
    return tuple(
        record
        for record in inventory.request_records
        if record.kind == "exact_array_backend_value_uninit_array"
    )


def _validate_translation_record(
    inventory: Stage8BackendTranslationRequestInventoryIr,
    record: ExactArrayBackendUninitTranslationRecordIr,
) -> tuple[Diagnostic, ...]:
    identity_mismatch = first_provenance_identity_mismatch(
        (
            LoweringProvenanceIdentity(
                record.source_request_inventory,
                inventory,
                "source request inventory object identity",
            ),
        )
    )
    if identity_mismatch is not None:
        return (
            _translation_result_provenance_mismatch_diagnostic(
                "exact-array backend-uninit translation records must preserve "
                f"{identity_mismatch}",
                record.source_location,
            ),
        )
    if not any(
        record.source_request_record is accepted_record
        for accepted_record in inventory.request_records
    ):
        return (
            _translation_result_provenance_mismatch_diagnostic(
                "exact-array backend-uninit translation records must preserve "
                "accepted request record object identity",
                record.source_location,
            ),
        )
    if record.source_request_record.kind != "exact_array_backend_value_uninit_array":
        return (
            _translation_result_request_unsupported_diagnostic(
                "exact-array backend-uninit translation records support only "
                "the exact-array backend-value request kind",
                record.source_location,
            ),
        )
    rule = record.source_rule
    if rule.backend_id != "cpp":
        return (
            _translation_result_backend_unsupported_diagnostic(
                "exact-array backend-uninit translation records support only "
                "cpp backend-uninit rules",
                rule.source_location or record.source_location,
            ),
        )
    if rule.rule_name != "value_array_uninit":
        return (
            _translation_result_malformed_diagnostic(
                "exact-array backend-uninit translation records require the "
                "value_array_uninit rule",
                rule.source_location or record.source_location,
            ),
        )
    return ()
