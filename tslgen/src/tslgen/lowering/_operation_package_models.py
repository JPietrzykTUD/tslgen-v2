from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering._array_body_backend_handoff import (
    ExactArrayBackendHandoffRequestIr,
)
from tslgen.lowering._operation_package_diagnostics import source_location_key

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
        from tslgen.lowering._operation_package_mini_tsil import (
            is_accepted_m86_tsil_return_statement,
        )

        if not self.candidate_id:
            raise ValueError(
                "mini-TSIL leaf-return operation package candidate id "
                "must be non-empty"
            )
        if not is_accepted_m86_tsil_return_statement(self.source_statement):
            raise TypeError(
                "mini-TSIL leaf-return operation package requires an accepted "
                "M86 TsilReturnStatement"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "mini_tsil_leaf_return_operation",
            self.candidate_id,
            source_location_key(self.source_location),
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
            source_location_key(self.source_location),
            self.source_entry.key,
        )
