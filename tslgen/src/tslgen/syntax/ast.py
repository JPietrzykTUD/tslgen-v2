"""Parser-owned values for the M107 TSL source form."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedBody:
    operation: str
    arguments: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedImplementation:
    extension: str
    type_tag: str
    body: ParsedBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedPrimitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    implementations: tuple[ParsedImplementation, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    path: str
    primitives: tuple[ParsedPrimitive, ...]


@dataclass(frozen=True, slots=True)
class ParseResult:
    documents: tuple[ParsedDocument, ...]
    diagnostics: tuple[Diagnostic, ...]
