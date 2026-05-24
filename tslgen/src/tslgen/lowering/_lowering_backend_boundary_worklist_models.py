from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering._lowering_backend_translation_request_inventory import (
    Stage8BackendTranslationNoRequestRecordIr,
    Stage8BackendTranslationRequestInventoryIr,
    Stage8BackendTranslationRequestRecordIr,
)
from tslgen.lowering._lowering_backend_translation_result import (
    ExactArrayBackendUninitTranslationRecordIr,
    ExactArrayBackendUninitTranslationResultIr,
)
from tslgen.lowering._lowering_ir_contracts import (
    LoweringIrContract,
    LoweringIrKeyComparable,
    lowering_ir_key,
)
from tslgen.lowering._operation_package_diagnostics import (
    source_location_key,
)


type Stage8BackendBoundaryWorklistClassification = Literal[
    "exact_array_backend_uninit_translated",
    "exact_array_backend_uninit_unresolved",
    "selected_body_direct_intrinsic_deferred",
    "no_accepted_backend_boundary_fact",
]


STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT = LoweringIrContract(
    name="stage8_backend_boundary_worklist_entry",
    category="provenance",
    owner="lowering.backend_translation.boundary_worklist",
)

STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT = LoweringIrContract(
    name="stage8_backend_boundary_worklist_inventory",
    category="inventory",
    owner="lowering.backend_translation.boundary_worklist",
)


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendBoundaryWorklistEntryIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT
    )

    source_request_inventory: Stage8BackendTranslationRequestInventoryIr
    classification: Stage8BackendBoundaryWorklistClassification
    source_request_record: Stage8BackendTranslationRequestRecordIr | None = None
    source_no_request_record: Stage8BackendTranslationNoRequestRecordIr | None = None
    source_exact_array_backend_uninit_translation_result: ExactArrayBackendUninitTranslationResultIr | None = None
    source_exact_array_backend_uninit_translation_record: ExactArrayBackendUninitTranslationRecordIr | None = None
    source_deferred_request_record: Stage8BackendTranslationRequestRecordIr | None = None

    def __post_init__(self) -> None:
        from tslgen.lowering._lowering_backend_boundary_worklist_validation import (
            validate_stage8_backend_boundary_worklist_entry,
        )

        diagnostics = validate_stage8_backend_boundary_worklist_entry(
            self.source_request_inventory,
            self,
        )
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def candidate_id(self) -> str:
        return self.source_request_inventory.candidate_id

    @property
    def source_location(self) -> SourceLocation | None:
        if self.source_request_record is not None:
            return self.source_request_record.source_location
        if self.source_no_request_record is not None:
            return self.source_no_request_record.source_location
        return self.source_request_inventory.source_location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_boundary_worklist_entry",
            self.candidate_id,
            self.classification,
            source_location_key(self.source_location),
            _key_or_none(self.source_request_record),
            _key_or_none(self.source_no_request_record),
            _key_or_none(self.source_exact_array_backend_uninit_translation_result),
            _key_or_none(self.source_exact_array_backend_uninit_translation_record),
            _key_or_none(self.source_deferred_request_record),
        )


@dataclass(frozen=True, slots=True, eq=False)
class Stage8BackendBoundaryWorklistInventoryIr(LoweringIrKeyComparable):
    ir_contract: ClassVar[LoweringIrContract] = (
        STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT
    )

    candidate_id: str
    source_location: SourceLocation | None
    source_request_inventory: Stage8BackendTranslationRequestInventoryIr
    source_exact_array_backend_uninit_translation_result: ExactArrayBackendUninitTranslationResultIr | None = None
    entries: tuple[Stage8BackendBoundaryWorklistEntryIr, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "Stage 8 backend-boundary worklist inventory candidate id "
                "must be non-empty"
            )
        object.__setattr__(self, "entries", tuple(self.entries))
        from tslgen.lowering._lowering_backend_boundary_worklist_validation import (
            validate_stage8_backend_boundary_worklist_inventory,
        )

        diagnostics = validate_stage8_backend_boundary_worklist_inventory(self)
        if diagnostics:
            raise ValueError(diagnostics[0].message)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "stage8_backend_boundary_worklist_inventory",
            self.candidate_id,
            source_location_key(self.source_location),
            self.source_request_inventory.key,
            _key_or_none(self.source_exact_array_backend_uninit_translation_result),
            tuple(entry.key for entry in self.entries),
        )


def _key_or_none(value: object | None) -> tuple[object, ...] | None:
    if value is None:
        return None
    key = lowering_ir_key(value)
    if key is None:
        raise ValueError("worklist provenance values must expose non-empty tuple keys")
    return key
