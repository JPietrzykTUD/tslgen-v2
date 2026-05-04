from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering.boundary import (
    GenerationTypeRef,
    GenerationTypeRefKind,
    TsilParameterReference,
)


type BackendIntrinsicModifierKind = Literal["suffix"]


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifierRequest:
    kind: str
    backend_id: str
    extension: str
    intrinsic: str
    type_ref: GenerationTypeRef | None = None
    source_location: SourceLocation | None = None
    raw_helper_text: str | None = None


@dataclass(frozen=True, slots=True)
class BackendIntrinsicModifier:
    kind: BackendIntrinsicModifierKind
    backend_id: str
    extension: str
    intrinsic: str
    value: str
    source_type_tag: str
    source_ref_kind: GenerationTypeRefKind

    def __post_init__(self) -> None:
        if self.kind != "suffix":
            raise ValueError(f"unsupported backend intrinsic modifier kind: {self.kind!r}")
        if not self.backend_id:
            raise ValueError("backend intrinsic modifier backend id must be non-empty")
        if not self.extension:
            raise ValueError("backend intrinsic modifier extension must be non-empty")
        if not self.intrinsic:
            raise ValueError("backend intrinsic modifier intrinsic must be non-empty")
        if not self.value:
            raise ValueError("backend intrinsic modifier value must be non-empty")
        if not self.source_type_tag:
            raise ValueError("backend intrinsic modifier source type tag must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.kind,
            self.backend_id,
            self.extension,
            self.intrinsic,
            self.value,
            self.source_type_tag,
            self.source_ref_kind,
        )


@dataclass(frozen=True, slots=True)
class TranslatedIntrinsicCall:
    candidate_id: str
    backend_id: str
    intrinsic: str
    extension: str
    type_tag: str
    backend_type: str
    function_name: str
    arguments: tuple[TsilParameterReference, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("translated intrinsic call candidate id must be non-empty")
        if not self.backend_id:
            raise ValueError("translated intrinsic call backend id must be non-empty")
        if not self.intrinsic:
            raise ValueError("translated intrinsic call intrinsic must be non-empty")
        if not self.extension:
            raise ValueError("translated intrinsic call extension must be non-empty")
        if not self.type_tag:
            raise ValueError("translated intrinsic call type tag must be non-empty")
        if not self.backend_type:
            raise ValueError("translated intrinsic call backend type must be non-empty")
        if not self.function_name:
            raise ValueError("translated intrinsic call function name must be non-empty")
        object.__setattr__(self, "arguments", tuple(self.arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate_id,
            self.backend_id,
            self.intrinsic,
            self.extension,
            self.type_tag,
            self.backend_type,
            self.function_name,
            tuple(argument.key for argument in self.arguments),
        )
