from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


type LoweringIrCategory = Literal[
    "semantic_fact",
    "request",
    "result",
    "inventory",
    "provenance",
    "rule_input",
    "stage_envelope",
]

LOWERING_IR_CATEGORIES: tuple[LoweringIrCategory, ...] = (
    "semantic_fact",
    "request",
    "result",
    "inventory",
    "provenance",
    "rule_input",
    "stage_envelope",
)


@dataclass(frozen=True, slots=True)
class LoweringIrContract:
    name: str
    category: LoweringIrCategory
    owner: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("lowering IR contract name must be non-empty")
        if self.category not in LOWERING_IR_CATEGORIES:
            raise ValueError("lowering IR contract category must be known")
        if not self.owner:
            raise ValueError("lowering IR contract owner must be non-empty")

    @property
    def key(self) -> tuple[str, LoweringIrCategory, str]:
        return (self.name, self.category, self.owner)


@dataclass(frozen=True, slots=True)
class LoweringProvenanceIdentity:
    actual: object | None
    expected: object | None
    label: str

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("lowering provenance identity label must be non-empty")

    @property
    def is_preserved(self) -> bool:
        return self.actual is self.expected


class LoweringIrKeyComparable:
    @property
    def key(self) -> tuple[object, ...]:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and getattr(self, "key") == getattr(
            other,
            "key",
        )

    def __hash__(self) -> int:
        return hash(getattr(self, "key"))


def first_provenance_identity_mismatch(
    identities: tuple[LoweringProvenanceIdentity, ...],
) -> str | None:
    for identity in identities:
        if not identity.is_preserved:
            return identity.label
    return None


STAGE8_BACKEND_TRANSLATION_REQUEST_RECORD_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_request_record",
    category="request",
    owner="lowering.backend_translation.request_inventory",
)

STAGE8_BACKEND_TRANSLATION_NO_REQUEST_RECORD_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_no_request_record",
    category="provenance",
    owner="lowering.backend_translation.request_inventory",
)

STAGE8_BACKEND_TRANSLATION_REQUEST_INVENTORY_CONTRACT = LoweringIrContract(
    name="stage8_backend_translation_request_inventory",
    category="inventory",
    owner="lowering.backend_translation.request_inventory",
)

EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RULE_CONTRACT = LoweringIrContract(
    name="exact_array_backend_uninit_translation_rule",
    category="rule_input",
    owner="lowering.backend_translation.exact_array_uninit_result",
)

EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RECORD_CONTRACT = LoweringIrContract(
    name="exact_array_backend_uninit_translation_record",
    category="result",
    owner="lowering.backend_translation.exact_array_uninit_result",
)

EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RESULT_CONTRACT = LoweringIrContract(
    name="exact_array_backend_uninit_translation_result",
    category="result",
    owner="lowering.backend_translation.exact_array_uninit_result",
)
