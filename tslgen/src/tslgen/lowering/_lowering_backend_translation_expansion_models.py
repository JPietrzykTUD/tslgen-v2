from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._lowering_backend_boundary_worklist_models import (
    Stage8BackendBoundaryWorklistEntryIr,
    Stage8BackendBoundaryWorklistInventoryIr,
)
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationRequestRecordIr,
)
from tslgen.lowering._lowering_ir_contracts import (
    LoweringIrContract,
    LoweringIrKeyComparable,
    lowering_ir_key,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_key,
)


type Stage8BackendTranslationExpansionRuleKind = Literal[
    "exact_array_backend_uninit",
    "selected_body_direct_intrinsic",
]
type Stage8BackendTranslationExpansionRecordState = Literal[
    "resolved",
    "deferred",
    "unsupported",
]
type Stage8BackendTranslationExpansionResultState = Literal[
    "has_backend_translation_expansion_records",
    "no_backend_translation_expansion_records",
]


EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME = "value_array_uninit"
SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME = "direct_intrinsic_call"

STAGE8_BACKEND_TRANSLATION_EXPANSION_RULE_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_expansion_rule",
    category="rule_input",
    owner="lowering.backend_translation.expansion",
)

STAGE8_BACKEND_TRANSLATION_EXPANSION_RECORD_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_expansion_record",
    category="result",
    owner="lowering.backend_translation.expansion",
)

STAGE8_BACKEND_TRANSLATION_EXPANSION_RESULT_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_expansion_result",
    category="result",
    owner="lowering.backend_translation.expansion",
)


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationExpansionRule(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        STAGE8_BACKEND_TRANSLATION_EXPANSION_RULE_CONTRACT
    )

    source_worklist_entry: Stage8BackendBoundaryWorklistEntryIr
    source_request_record: Stage8BackendTranslationRequestRecordIr
    rule_kind: str
    backend_id: str
    result_name: str
    translated_value: str
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_worklist_entry,
            Stage8BackendBoundaryWorklistEntryIr,
        ):
            raise ValueError(
                "backend translation expansion rules require accepted concrete "
                "M103 worklist entries"
            )
        if not isinstance(
            self.source_request_record,
            Stage8BackendTranslationRequestRecordIr,
        ):
            raise ValueError(
                "backend translation expansion rules require accepted concrete "
                "M99 request records"
            )
        if not self.rule_kind:
            raise ValueError(
                "backend translation expansion rule kind must be non-empty"
            )
        if not self.backend_id:
            raise ValueError("backend translation expansion backend id must be non-empty")
        if not self.result_name:
            raise ValueError(
                "backend translation expansion result name must be non-empty"
            )
        if self.translated_value == "":
            raise ValueError(
                "backend translation expansion translated value must be non-empty"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_expansion_rule",
            self.rule_kind,
            self.backend_id,
            self.result_name,
            self.translated_value,
            _required_key(self.source_worklist_entry),
            _required_key(self.source_request_record),
            source_location_key(self.source_location),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationExpansionRecordIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        STAGE8_BACKEND_TRANSLATION_EXPANSION_RECORD_CONTRACT
    )

    source_worklist_inventory: Stage8BackendBoundaryWorklistInventoryIr
    source_worklist_entry: Stage8BackendBoundaryWorklistEntryIr
    source_request_record: Stage8BackendTranslationRequestRecordIr
    record_kind: str
    record_state: Stage8BackendTranslationExpansionRecordState
    backend_id: str | None = None
    result_name: str | None = None
    translated_value: str | None = None
    source_rules: tuple[Stage8BackendTranslationExpansionRule, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_rules", tuple(self.source_rules))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        from tslgen.lowering._lowering_backend_translation_expansion_validation import (
            validate_stage8_backend_translation_expansion_record,
        )

        diagnostics = validate_stage8_backend_translation_expansion_record(
            self.source_worklist_inventory,
            self,
        )
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_worklist_inventory.candidate_id

    @property
    def source_location(self) -> SourceLocation | None:
        return self.source_worklist_entry.source_location

    @property
    def source_rule(self) -> Stage8BackendTranslationExpansionRule | None:
        return self.source_rules[0] if self.source_rules else None

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_expansion_record",
            self.candidate_id,
            self.record_kind,
            self.record_state,
            self.backend_id,
            self.result_name,
            self.translated_value,
            _required_key(self.source_worklist_inventory),
            _required_key(self.source_worklist_entry),
            _required_key(self.source_request_record),
            tuple(_required_key(rule) for rule in self.source_rules),
            tuple(diagnostic.sort_key() for diagnostic in self.diagnostics),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendTranslationExpansionResultIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        STAGE8_BACKEND_TRANSLATION_EXPANSION_RESULT_CONTRACT
    )

    candidate_id: str
    source_location: SourceLocation | None
    result_state: Stage8BackendTranslationExpansionResultState
    source_worklist_inventory: Stage8BackendBoundaryWorklistInventoryIr
    records: tuple[Stage8BackendTranslationExpansionRecordIr, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "Stage 8 backend translation expansion result candidate id "
                "must be non-empty"
            )
        object.__setattr__(self, "records", tuple(self.records))
        from tslgen.lowering._lowering_backend_translation_expansion_validation import (
            validate_stage8_backend_translation_expansion_result,
        )

        diagnostics = validate_stage8_backend_translation_expansion_result(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_translation_expansion_result",
            self.candidate_id,
            source_location_key(self.source_location),
            self.result_state,
            _required_key(self.source_worklist_inventory),
            tuple(record.key for record in self.records),
        )


def _required_key(value: object) -> tuple[object, ...]:
    key = lowering_ir_key(value)
    if key is None:
        raise ValueError("translation expansion values must expose non-empty tuple keys")
    return key
