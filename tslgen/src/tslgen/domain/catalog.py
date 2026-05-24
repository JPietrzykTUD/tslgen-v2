"""Minimal typed catalog values for the tiny clean restart slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation


@dataclass(frozen=True, slots=True)
class BinaryOperationBody:
    operation: str
    left_parameter: str
    right_parameter: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class UnaryOperationBody:
    operation: str
    value_parameter: str
    source: SourceLocation


OperationBody = BinaryOperationBody | UnaryOperationBody


@dataclass(frozen=True, slots=True)
class Implementation:
    extension: str
    type_tag: str
    body: OperationBody
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
