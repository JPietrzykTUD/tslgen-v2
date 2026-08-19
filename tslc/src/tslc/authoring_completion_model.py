"""Editor-neutral completion records shared by authoring projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.syntax.authoring import AuthoringTextRange

AuthoringCompletionKind = Literal[
    "field",
    "keyword",
    "value",
    "function",
    "class",
    "type",
]


@dataclass(frozen=True, slots=True)
class AuthoringCompletion:
    """Editor-neutral completion information returned by compiler semantics."""

    label: str
    kind: AuthoringCompletionKind
    replacement_range: AuthoringTextRange
    insert_text: str
    detail: str
    documentation: str | None = None
    snippet: bool = False
    sort_group: int = 0
    commit_characters: tuple[str, ...] = ()


def completion_key(completion: AuthoringCompletion) -> tuple[int, str, str]:
    return completion.sort_group, completion.label, completion.insert_text


__all__ = (
    "AuthoringCompletion",
    "AuthoringCompletionKind",
    "completion_key",
)
