"""Minimal typed catalog values for the tiny clean restart slice."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation


@dataclass(frozen=True, slots=True)
class LowerableOperationFragment:
    operation: str
    arguments: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RawStringToken:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelfPrimitiveReference:
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class NamedPrimitiveReference:
    name: str
    source: SourceLocation


PrimitiveCallTarget = SelfPrimitiveReference | NamedPrimitiveReference


@dataclass(frozen=True, slots=True)
class PrimitiveCallSelector:
    target: PrimitiveCallTarget
    specialization: str | None
    attrs: str | None
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCall:
    selector: PrimitiveCallSelector
    payload: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class LowerableDirective:
    name: str
    arguments: tuple[str, ...]
    source: SourceLocation
    primitive_call: PrimitiveCall | None = None
    payload_tokens: tuple[PayloadToken, ...] = ()


PayloadToken = RawStringToken | LowerableDirective
BodyToken = RawStringToken | LowerableOperationFragment | LowerableDirective


@dataclass(frozen=True, slots=True)
class ImplementationBody:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Implementation:
    extension: str
    type_tag: str
    body: ImplementationBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    template: str
    implementations: tuple[Implementation, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Catalog:
    primitives: tuple[Primitive, ...]
