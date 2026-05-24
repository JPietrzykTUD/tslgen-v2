"""Minimal typed catalog values for M107."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation


@dataclass(frozen=True, slots=True)
class BinaryAddBody:
    left_parameter: str
    right_parameter: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Implementation:
    extension: str
    type_tag: str
    body: BinaryAddBody
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
