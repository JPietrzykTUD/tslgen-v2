"""Parser-owned values for the tiny clean TSL source forms."""

from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation


PARSED_TSIL_BODY_ENVELOPE = "tsil"
ParsedImplementationBodyEnvelope = Literal["unknown", "tsil"]
ParsedReturnTypeBindingKind = Literal["base", "extension"]


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
    envelope: ParsedImplementationBodyEnvelope = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedImplementation:
    extension: str
    type_tag: str
    body: ParsedImplementationBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedPrimitiveAttribute:
    key: str
    value: str
    source: SourceLocation
    key_argument: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedReturnTypeBinding:
    kind: ParsedReturnTypeBindingKind
    name: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedGenericParameter:
    name: str
    kind: str
    default: str | None
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedPrimitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    implementations: tuple[ParsedImplementation, ...]
    source: SourceLocation
    attributes: tuple[ParsedPrimitiveAttribute, ...] = ()
    return_type_binding: ParsedReturnTypeBinding | None = None
    generic_parameters: tuple[ParsedGenericParameter, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedExtensionField:
    key: str
    raw_value: str | None
    children: tuple["ParsedExtensionField", ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedExtension:
    name: str
    fields: tuple[ParsedExtensionField, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedTypeGroup:
    name: str
    type_tags: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    path: str
    primitives: tuple[ParsedPrimitive, ...] = ()
    extensions: tuple[ParsedExtension, ...] = ()
    type_groups: tuple[ParsedTypeGroup, ...] = ()


@dataclass(frozen=True, slots=True)
class ParseResult:
    documents: tuple[ParsedDocument, ...]
    diagnostics: tuple[Diagnostic, ...]
