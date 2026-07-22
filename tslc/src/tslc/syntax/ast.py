"""Typed outer TSL parser-boundary values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tslc.diagnostics import Diagnostic, SourceLocation


ParsedTslScalarKind = Literal[
    "bare",
    "bool",
    "multiline_string",
    "number",
    "string",
    "wildcard",
]
ParsedTslQuoteForm = Literal["none", "inline", "multiline"]
ParsedTopLevelDeclarationKind = Literal[
    "description",
    "extension",
    "flags",
    "language",
    "lane_set",
    "primitive",
    "template",
    "translation",
    "types",
    "field",
]
ParsedPrimitiveFieldKind = Literal[
    "benchmarks",
    "brief_description",
    "detailed_description",
    "generic_params",
    "impls",
    "operation",
    "overload",
    "return_type",
    "semantics",
    "simm_type",
    "tests",
    "preserved",
]


@dataclass(frozen=True, slots=True)
class ParsedTslSourceSpan:
    path: Path
    line: int
    column: int
    end_line: int
    end_column: int
    text: str

    @property
    def start(self) -> SourceLocation:
        return SourceLocation(self.path, self.line, self.column)


@dataclass(frozen=True, slots=True)
class ParsedTslKey:
    text: str
    source: ParsedTslSourceSpan


@dataclass(frozen=True, slots=True)
class ParsedTslScalarValue:
    kind: ParsedTslScalarKind
    text: str
    raw_text: str
    source: ParsedTslSourceSpan
    quote_form: ParsedTslQuoteForm = "none"
    payload_source: ParsedTslSourceSpan | None = None


@dataclass(frozen=True, slots=True)
class ParsedTslListValue:
    items: tuple["ParsedTslValue", ...]
    source: ParsedTslSourceSpan


@dataclass(frozen=True, slots=True)
class ParsedTslAttribute:
    key: ParsedTslKey
    value: "ParsedTslValue"
    source: ParsedTslSourceSpan
    key_argument: ParsedTslKey | None = None


@dataclass(frozen=True, slots=True)
class ParsedTslAttributeListValue:
    attributes: tuple[ParsedTslAttribute, ...]
    source: ParsedTslSourceSpan


@dataclass(frozen=True, slots=True)
class ParsedTslMapValue:
    entries: tuple["ParsedTslField", ...]
    source: ParsedTslSourceSpan


ParsedTslValue = (
    ParsedTslScalarValue
    | ParsedTslListValue
    | ParsedTslAttributeListValue
    | ParsedTslMapValue
)


@dataclass(frozen=True, slots=True)
class ParsedTslField:
    key: ParsedTslKey
    source: ParsedTslSourceSpan
    source_order: int
    value: ParsedTslValue | None = None
    children: tuple["ParsedTslField", ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedPrimitiveField:
    kind: ParsedPrimitiveFieldKind
    field: ParsedTslField


@dataclass(frozen=True, slots=True)
class ParsedRequiresValue:
    field: ParsedTslField


@dataclass(frozen=True, slots=True)
class ParsedImplementationBodyEnvelope:
    selector_path: tuple[str, ...]
    quote_form: ParsedTslQuoteForm
    payload_text: str
    envelope_source: ParsedTslSourceSpan
    payload_source: ParsedTslSourceSpan
    source_order: int


@dataclass(frozen=True, slots=True)
class ParsedImplementationVariant:
    name: str
    source: ParsedTslSourceSpan
    source_order: int
    fields: tuple[ParsedTslField, ...]
    body_envelopes: tuple[ParsedImplementationBodyEnvelope, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedImplementationSelectorEntry:
    selector: ParsedTslKey
    source: ParsedTslSourceSpan
    source_order: int
    fields: tuple[ParsedTslField, ...]
    children: tuple["ParsedImplementationSelectorEntry", ...] = ()
    requires: tuple[ParsedRequiresValue, ...] = ()
    body_envelopes: tuple[ParsedImplementationBodyEnvelope, ...] = ()
    variants: tuple[ParsedImplementationVariant, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedPrimitiveDeclaration:
    name: str
    signature: str
    parameters: tuple[str, ...]
    attributes: tuple[ParsedTslAttribute, ...]
    fields: tuple[ParsedPrimitiveField, ...]
    impl_entries: tuple[ParsedImplementationSelectorEntry, ...]
    body_envelopes: tuple[ParsedImplementationBodyEnvelope, ...]
    source: ParsedTslSourceSpan
    header_source: ParsedTslSourceSpan
    signature_source: ParsedTslSourceSpan
    source_order: int

    def fields_by_name(self, name: str) -> tuple[ParsedPrimitiveField, ...]:
        return tuple(field for field in self.fields if field.field.key.text == name)


@dataclass(frozen=True, slots=True)
class ParsedBlockDeclaration:
    kind: ParsedTopLevelDeclarationKind
    name: str | None
    fields: tuple[ParsedTslField, ...]
    source: ParsedTslSourceSpan
    source_order: int


@dataclass(frozen=True, slots=True)
class ParsedFieldDeclaration:
    kind: ParsedTopLevelDeclarationKind
    field: ParsedTslField
    source_order: int


ParsedTopLevelDeclaration = (
    ParsedPrimitiveDeclaration | ParsedBlockDeclaration | ParsedFieldDeclaration
)


@dataclass(frozen=True, slots=True)
class ParsedOuterTslDocument:
    path: Path
    declarations: tuple[ParsedTopLevelDeclaration, ...]

    @property
    def primitives(self) -> tuple[ParsedPrimitiveDeclaration, ...]:
        return tuple(
            declaration
            for declaration in self.declarations
            if isinstance(declaration, ParsedPrimitiveDeclaration)
        )

    @property
    def blocks(self) -> tuple[ParsedBlockDeclaration, ...]:
        return tuple(
            declaration
            for declaration in self.declarations
            if isinstance(declaration, ParsedBlockDeclaration)
        )

    @property
    def fields(self) -> tuple[ParsedFieldDeclaration, ...]:
        return tuple(
            declaration
            for declaration in self.declarations
            if isinstance(declaration, ParsedFieldDeclaration)
        )


@dataclass(frozen=True, slots=True)
class OuterTslParseResult:
    documents: tuple[ParsedOuterTslDocument, ...]
    diagnostics: tuple[Diagnostic, ...]
