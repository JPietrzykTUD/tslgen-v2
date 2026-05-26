"""Parser-owned values for the tiny clean TSL source forms."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedLowerableOperationFragment:
    operation: str
    arguments: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedRawStringToken:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedLowerableDirective:
    name: str
    arguments: tuple[str, ...]
    source: SourceLocation


ParsedBodySegment = (
    ParsedRawStringToken
    | ParsedLowerableOperationFragment
    | ParsedLowerableDirective
)


@dataclass(frozen=True, slots=True)
class ParsedRawStringLine:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedSegmentedLine:
    segments: tuple[ParsedBodySegment, ...]
    source: SourceLocation


ParsedBodyLine = ParsedRawStringLine | ParsedSegmentedLine


@dataclass(frozen=True, slots=True)
class ParsedImplementationBody:
    lines: tuple[ParsedBodyLine, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedImplementation:
    extension: str
    type_tag: str
    body: ParsedImplementationBody
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
