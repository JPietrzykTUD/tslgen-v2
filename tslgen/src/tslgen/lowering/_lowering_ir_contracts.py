from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypeGuard


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


class LoweringIrNode(Protocol):
    ir_contract: LoweringIrContract


class LoweringKeyed(Protocol):
    @property
    def key(self) -> tuple[object, ...]: ...


class LoweringFact(LoweringIrNode, LoweringKeyed, Protocol): ...
class LoweringRequestIr(LoweringIrNode, LoweringKeyed, Protocol): ...
class TranslationRequestIr(LoweringRequestIr, Protocol): ...
class TranslationResultIr(LoweringIrNode, LoweringKeyed, Protocol): ...
class LoweringInventory(LoweringIrNode, LoweringKeyed, Protocol): ...
class LoweringProvenance(LoweringIrNode, LoweringKeyed, Protocol): ...
class LoweringRuleInput(LoweringIrNode, LoweringKeyed, Protocol): ...
class LoweringStageOutput(LoweringIrNode, LoweringKeyed, Protocol): ...


@dataclass(frozen=True, slots=True)
class DiagnosticBoundary:
    name: str
    code_prefix: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("diagnostic boundary name must be non-empty")
        if not self.code_prefix:
            raise ValueError("diagnostic boundary code prefix must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.code_prefix)


def lowering_ir_contract(value: object) -> LoweringIrContract | None:
    contract = getattr(value, "ir_contract", None)
    return contract if isinstance(contract, LoweringIrContract) else None


def lowering_ir_key(value: object) -> tuple[object, ...] | None:
    try:
        key = getattr(value, "key")
    except Exception:
        return None
    return key if isinstance(key, tuple) and key else None


def lowering_ir_category(value: object) -> LoweringIrCategory | None:
    contract = lowering_ir_contract(value)
    return None if contract is None else contract.category


def require_lowering_ir_key(value: object, *, label: str) -> tuple[object, ...]:
    key = lowering_ir_key(value)
    if key is None:
        raise ValueError(f"{label} must expose a non-empty tuple key")
    return key


def require_lowering_ir_category(
    value: object,
    category: LoweringIrCategory,
    *,
    label: str,
) -> LoweringIrContract:
    contract = lowering_ir_contract(value)
    if contract is None:
        raise ValueError(f"{label} must expose a typed LoweringIrContract")
    require_lowering_ir_key(value, label=label)
    if contract.category != category:
        raise ValueError(
            f"{label} must use lowering IR category {category!r}; "
            f"got {contract.category!r}"
        )
    return contract


def _is_backend_translation_owner(owner: str) -> bool:
    return owner == "lowering.backend_translation" or owner.startswith(
        "lowering.backend_translation."
    )


def _is_lowering_ir_category(
    value: object,
    category: LoweringIrCategory,
    label: str,
) -> bool:
    try:
        require_lowering_ir_category(value, category, label=label)
    except ValueError:
        return False
    return True


def require_translation_request_ir(
    value: object,
    *,
    label: str,
) -> LoweringIrContract:
    contract = require_lowering_ir_category(value, "request", label=label)
    if not _is_backend_translation_owner(contract.owner):
        raise ValueError(f"{label} must be owned by backend-translation lowering")
    return contract


def require_translation_result_ir(
    value: object,
    *,
    label: str,
) -> LoweringIrContract:
    contract = require_lowering_ir_category(value, "result", label=label)
    if not _is_backend_translation_owner(contract.owner):
        raise ValueError(f"{label} must be owned by backend-translation lowering")
    return contract


def is_lowering_fact(value: object) -> TypeGuard[LoweringFact]:
    return _is_lowering_ir_category(value, "semantic_fact", "lowering fact")


def is_lowering_request_ir(value: object) -> TypeGuard[LoweringRequestIr]:
    return _is_lowering_ir_category(value, "request", "lowering request IR")


def is_translation_request_ir(value: object) -> TypeGuard[TranslationRequestIr]:
    try:
        require_translation_request_ir(value, label="translation request IR")
    except ValueError:
        return False
    return True


def is_translation_result_ir(value: object) -> TypeGuard[TranslationResultIr]:
    try:
        require_translation_result_ir(value, label="translation result IR")
    except ValueError:
        return False
    return True


def is_lowering_inventory(value: object) -> TypeGuard[LoweringInventory]:
    return _is_lowering_ir_category(value, "inventory", "lowering inventory")


def is_lowering_provenance(value: object) -> TypeGuard[LoweringProvenance]:
    return _is_lowering_ir_category(value, "provenance", "lowering provenance")


def is_lowering_rule_input(value: object) -> TypeGuard[LoweringRuleInput]:
    return _is_lowering_ir_category(value, "rule_input", "lowering rule input")


def is_lowering_stage_output(value: object) -> TypeGuard[LoweringStageOutput]:
    return _is_lowering_ir_category(value, "stage_envelope", "lowering stage output")


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
