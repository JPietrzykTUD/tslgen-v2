from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import SourceLocation


type GenerationBranchChoice = Literal["true", "false"]
type GenerationElseSyntax = Literal["else<generation>", "else"]
type GenerationTypeRefKind = Literal[
    "base.in",
    "base.signed_of",
    "base.unsigned_of",
]
type GenerationValueKind = Literal["type.size_bytes", "type.size_bits"]
type GenerationPredicateKind = Literal["type.size_bytes.equals"]
type GenerationRecognitionKind = Literal[
    "generation.value",
    "generation.predicate",
    "generation.control_flow",
]

_GENERATION_CONDITION_MARKER = "if<generation>"
_GENERATION_HELPER_MARKERS = (
    "if<generation>",
    "type<generation>",
    "value<generation>",
)
_GENERATION_TYPE_MARKER = "type<generation>"
_GENERATION_VALUE_MARKER = "value<generation>"


def _has_generation_helper(text: str) -> bool:
    return any(marker in text for marker in _GENERATION_HELPER_MARKERS)


@dataclass(frozen=True, slots=True)
class GenerationTypeRef:
    kind: GenerationTypeRefKind
    type_tag: str
    source_type_tag: str | None = None

    def __post_init__(self) -> None:
        if not self.type_tag:
            raise ValueError("generation type ref type tag must be non-empty")
        if self.source_type_tag == "":
            raise ValueError("generation type ref source type tag must be non-empty")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.type_tag, self.source_type_tag or "")


@dataclass(frozen=True, slots=True)
class GenerationValue:
    kind: GenerationValueKind
    value: int
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("generation value payload must be an integer")
        if not self.type_tag:
            raise ValueError("generation value type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.kind, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class GenerationPredicate:
    kind: GenerationPredicateKind
    literal: int
    value: bool
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.literal, bool) or not isinstance(self.literal, int):
            raise ValueError("generation predicate literal must be an integer")
        if self.literal not in (2, 4, 8):
            raise ValueError("generation predicate literal must be 2, 4, or 8")
        if not isinstance(self.value, bool):
            raise ValueError("generation predicate payload must be boolean")
        if not self.type_tag:
            raise ValueError("generation predicate type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, bool, str]:
        return (self.kind, self.literal, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class GenerationExpressionRecognition:
    kind: GenerationRecognitionKind
    source_text: str

    def __post_init__(self) -> None:
        if not self.source_text.strip():
            raise ValueError("generation recognition source text must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.source_text)


@dataclass(frozen=True, slots=True)
class TsilPrimitiveAttributeCondition:
    attribute_name: str

    def __post_init__(self) -> None:
        if not self.attribute_name:
            raise ValueError("primitive attribute condition name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("primitive_attribute", self.attribute_name)


@dataclass(frozen=True, slots=True)
class TsilTypeSignednessCondition:
    type_ref: GenerationTypeRef

    @property
    def key(self) -> tuple[object, ...]:
        return ("type_is_signed", self.type_ref.key)


type TsilGenerationCondition = (
    TsilPrimitiveAttributeCondition | TsilTypeSignednessCondition
)


@dataclass(frozen=True, slots=True)
class GenerationSizeByteBranchChainArm:
    literal: int
    predicate: GenerationPredicate
    statement_text: str

    def __post_init__(self) -> None:
        if self.literal not in (2, 4, 8):
            raise ValueError("size-byte branch-chain arm literal must be 2, 4, or 8")
        if self.predicate.kind != "type.size_bytes.equals":
            raise ValueError("size-byte branch-chain arm requires a size-byte predicate")
        if self.predicate.literal != self.literal:
            raise ValueError("size-byte branch-chain arm literal must match predicate")
        if not self.statement_text.strip():
            raise ValueError("size-byte branch-chain arm body must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (self.literal, self.predicate.key, self.statement_text)


@dataclass(frozen=True, slots=True)
class GenerationSizeByteBranchChainPruning:
    arms: tuple[GenerationSizeByteBranchChainArm, ...]
    type_tag: str
    selected_literal: int | None
    selected_statement_text: str | None = None
    condition_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arms", tuple(self.arms))
        if tuple(arm.literal for arm in self.arms) != (2, 4, 8):
            raise ValueError("size-byte branch chain must have == 2, == 4, == 8 arms")
        if not self.type_tag:
            raise ValueError("size-byte branch-chain type tag must be non-empty")
        if self.selected_literal is not None and self.selected_literal not in (2, 4, 8):
            raise ValueError("selected size-byte branch literal must be 2, 4, 8, or None")
        if self.selected_literal is None:
            if self.selected_statement_text is not None:
                raise ValueError("no-match branch chain must not have selected body text")
        elif not (self.selected_statement_text or "").strip():
            raise ValueError("matched branch chain must record selected body text")

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.condition_location.sort_key()
            if self.condition_location is not None
            else ()
        )
        return (
            tuple(arm.key for arm in self.arms),
            self.type_tag,
            self.selected_literal or 0,
            self.selected_statement_text or "",
            location_key,
        )


@dataclass(frozen=True, slots=True)
class PrunedGenerationBranch:
    condition: TsilGenerationCondition
    selected_branch: GenerationBranchChoice
    statement_text: str
    else_syntax: GenerationElseSyntax = "else<generation>"
    condition_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.statement_text.strip():
            raise ValueError("pruned generation branch statement text must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.condition_location.sort_key()
            if self.condition_location is not None
            else ()
        )
        return (
            self.condition.key,
            self.selected_branch,
            self.statement_text,
            self.else_syntax,
            location_key,
        )
