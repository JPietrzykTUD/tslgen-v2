"""Document-symbol and semantic-token facts derived from parsed TSL source."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal

from tslc.catalog.arithmetic import (
    arithmetic_guarantee_values,
    arithmetic_operation_values,
)
from tslc.catalog.conversion import (
    conversion_kind_values,
    lane_count_relation_values,
)
from tslc.catalog.memory import memory_access_values, memory_addressing_values
from tslc.catalog.semantics import primitive_operation_values
from tslc.catalog.shift import shift_count_rule_values, shift_lane_rule_values
from tslc.catalog.validation._schema_benchmarks import KNOWN_OPERAND_DOMAINS
from tslc.catalog.validation._schema_common import KNOWN_BOOLEAN_VALUES
from tslc.catalog.validation._schema_implementation import (
    KNOWN_TARGET_FAMILY_RELATIONS,
    KNOWN_TARGET_WIDTH_RELATIONS,
)
from tslc.catalog.validation._schema_primitives import (
    KNOWN_GENERIC_PARAM_KINDS,
    KNOWN_PRIMITIVE_ATTRIBUTES,
)
from tslc.catalog.validation._schema_tests import KNOWN_TEST_ROLES
from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.ir.region_syntax import parse_call_selector
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.lower.query_authoring import DEFAULT_QUERY_AUTHORING_INDEX
from tslc.syntax.access import child, children
from tslc.syntax.ast import (
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedImplementationVariant,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
    ParsedTslAttributeListValue,
    ParsedTslField,
    ParsedTslKey,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
    ParsedTslValue,
)


DocumentSymbolKind = Literal[
    "primitive",
    "extension",
    "type-group",
    "block",
    "field",
    "implementation",
    "variant",
    "parameter",
    "generic-parameter",
    "target-axis",
    "test-case",
]
SemanticTokenKind = Literal[
    "function",
    "class",
    "type",
    "keyword",
    "property",
    "parameter",
    "typeParameter",
    "enumMember",
    "namespace",
]

_CLOSED_ENUM_VALUES = frozenset(
    (
        *KNOWN_BOOLEAN_VALUES,
        *KNOWN_GENERIC_PARAM_KINDS,
        *KNOWN_OPERAND_DOMAINS,
        *KNOWN_TARGET_FAMILY_RELATIONS,
        *KNOWN_TARGET_WIDTH_RELATIONS,
        *KNOWN_TEST_ROLES,
        *arithmetic_operation_values(),
        *arithmetic_guarantee_values(),
        *shift_count_rule_values(),
        *shift_lane_rule_values(),
        *(value for values in KNOWN_PRIMITIVE_ATTRIBUTES.values() for value in values),
    )
)
_SELECTOR_TOKEN = re.compile(r"@?[A-Za-z_][A-Za-z0-9_?]*")
_QUERY_ROOT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*(?:::|\())")


@dataclass(frozen=True, slots=True)
class IndexedDocumentSymbol:
    name: str
    kind: DocumentSymbolKind
    span: SourceSpan
    selection_span: SourceSpan
    detail: str = ""
    children: tuple["IndexedDocumentSymbol", ...] = ()


@dataclass(frozen=True, slots=True)
class IndexedSemanticToken:
    kind: SemanticTokenKind
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class DocumentAuthoringIndex:
    symbols: tuple[IndexedDocumentSymbol, ...]
    semantic_tokens: tuple[IndexedSemanticToken, ...]


def build_document_authoring_index(
    document: ParsedOuterTslDocument,
) -> DocumentAuthoringIndex:
    symbols: list[IndexedDocumentSymbol] = []
    tokens: list[IndexedSemanticToken] = []
    for declaration in document.declarations:
        tokens.append(IndexedSemanticToken("keyword", _declaration_keyword_span(declaration)))
        if isinstance(declaration, ParsedPrimitiveDeclaration):
            symbols.append(_primitive_symbol(declaration))
            tokens.extend(_primitive_semantic_tokens(declaration))
            tokens.append(
                IndexedSemanticToken(
                    "function", _name_in_source(declaration.header_source, declaration.name)
                )
            )
            _index_implementation_tokens(declaration.impl_entries, tokens, _result_target(declaration))
            for envelope in declaration.body_envelopes:
                source = _source_span(envelope.payload_source)
                for region in _regions(scan(envelope.payload_text, source=source)):
                    tokens.extend(_region_semantic_tokens(region))
            continue
        if isinstance(declaration, ParsedBlockDeclaration):
            symbols.append(_block_symbol(declaration))
            tokens.extend(_block_semantic_tokens(declaration))
            if declaration.kind == "extension" and declaration.name:
                tokens.append(
                    IndexedSemanticToken(
                        "class", _name_in_source(declaration.source, declaration.name)
                    )
                )
            elif declaration.kind == "types":
                tokens.extend(
                    IndexedSemanticToken("type", _source_span(field.key.source))
                    for field in declaration.fields
                )
            continue
        assert isinstance(declaration, ParsedFieldDeclaration)
        symbols.append(_field_declaration_symbol(declaration))
        tokens.extend(_field_semantic_tokens(declaration.field))
        if declaration.field.key.text == "overload_axes":
            tokens.extend(_overload_registry_semantic_tokens(declaration.field))
    return DocumentAuthoringIndex(tuple(symbols), _deduplicated_tokens(tokens))


def selector_items(key: ParsedTslKey) -> tuple[tuple[str, SourceSpan], ...]:
    source = _source_span(key.source)
    text = key.source.text
    if not (key.text.startswith("[") and key.text.endswith("]")):
        return ((key.text, source),)
    return tuple(
        (match.group(0), _subspan(source, text, match.start(), match.end()))
        for match in _SELECTOR_TOKEN.finditer(text)
    )


def _primitive_symbol(primitive: ParsedPrimitiveDeclaration) -> IndexedDocumentSymbol:
    children: list[IndexedDocumentSymbol] = []
    children.extend(
        IndexedDocumentSymbol(name, "parameter", span, span, "primitive parameter")
        for name, span in _parameter_spans(primitive)
    )
    for primitive_field in primitive.fields_by_name("generic_params"):
        children.extend(
            IndexedDocumentSymbol(
                parameter.key.text,
                "generic-parameter",
                _source_span(parameter.source),
                _source_span(parameter.key.source),
                "generic parameter",
            )
            for parameter in primitive_field.field.children
        )
    result_target = _result_target(primitive)
    if result_target is not None:
        dimension, name, selection = result_target
        target_field = next(
            (
                field
                for primitive_field in primitive.fields_by_name("return_type")
                for field in primitive_field.field.children
                if field.key.text == dimension
            ),
            None,
        )
        children.append(
            IndexedDocumentSymbol(
                name,
                "target-axis",
                _source_span(target_field.source) if target_field is not None else selection,
                selection,
                f"{dimension} result selector",
            )
        )
    children.extend(_implementation_symbols(primitive.impl_entries))
    children.extend(_named_test_symbols(primitive))
    return IndexedDocumentSymbol(
        primitive.name,
        "primitive",
        _source_span(primitive.source),
        _name_in_source(primitive.header_source, primitive.name),
        f"prim<{primitive.signature}>",
        tuple(sorted(children, key=_document_symbol_key)),
    )


def _implementation_symbols(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
) -> tuple[IndexedDocumentSymbol, ...]:
    def symbol(entry: ParsedImplementationSelectorEntry) -> IndexedDocumentSymbol:
        children = [symbol(child) for child in entry.children]
        children.extend(_variant_symbol(variant) for variant in entry.variants)
        return IndexedDocumentSymbol(
            entry.selector.text,
            "implementation",
            _source_span(entry.source),
            _source_span(entry.selector.source),
            "implementation selector",
            tuple(sorted(children, key=_document_symbol_key)),
        )

    return tuple(symbol(entry) for entry in entries)


def _variant_symbol(variant: ParsedImplementationVariant) -> IndexedDocumentSymbol:
    return IndexedDocumentSymbol(
        variant.name,
        "variant",
        _source_span(variant.source),
        _name_in_source(variant.source, variant.name),
        "implementation variant",
    )


def _named_test_symbols(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[IndexedDocumentSymbol, ...]:
    symbols: list[IndexedDocumentSymbol] = []
    for primitive_field in primitive.fields_by_name("tests"):
        value = primitive_field.field.value
        if not isinstance(value, ParsedTslListValue):
            continue
        for item in value.items:
            if not isinstance(item, ParsedTslMapValue):
                continue
            name_value = next(
                (
                    entry.value
                    for entry in item.entries
                    if entry.key.text == "name"
                    and isinstance(entry.value, ParsedTslScalarValue)
                ),
                None,
            )
            if not isinstance(name_value, ParsedTslScalarValue):
                continue
            selection = name_value.payload_source or name_value.source
            symbols.append(
                IndexedDocumentSymbol(
                    name_value.text,
                    "test-case",
                    _source_span(item.source),
                    _source_span(selection),
                    "named value test",
                )
            )
    return tuple(symbols)


def _block_symbol(block: ParsedBlockDeclaration) -> IndexedDocumentSymbol:
    selection = (
        _name_in_source(block.source, block.name)
        if block.name is not None
        else _declaration_keyword_span(block)
    )
    children = tuple(
        IndexedDocumentSymbol(
            field.key.text,
            "type-group" if block.kind == "types" else "field",
            _source_span(field.source),
            _source_span(field.key.source),
            "type group" if block.kind == "types" else f"{block.kind} field",
        )
        for field in block.fields
    )
    return IndexedDocumentSymbol(
        block.name or block.kind,
        "extension" if block.kind == "extension" else "block",
        _source_span(block.source),
        selection,
        block.kind,
        children,
    )


def _field_declaration_symbol(
    declaration: ParsedFieldDeclaration,
) -> IndexedDocumentSymbol:
    field = declaration.field
    nested: tuple[IndexedDocumentSymbol, ...] = ()
    if field.key.text == "overload_axes":
        nested = tuple(
            IndexedDocumentSymbol(
                axis.key.text,
                "field",
                _source_span(axis.source),
                _source_span(axis.key.source),
                "overload axis",
                tuple(
                    IndexedDocumentSymbol(
                        value.key.text,
                        "field",
                        _source_span(value.source),
                        _source_span(value.key.source),
                        "overload value",
                    )
                    for value in children(child(axis, "values"))
                ),
            )
            for axis in children(field)
        )
    return IndexedDocumentSymbol(
        field.key.text,
        "field",
        _source_span(field.source),
        _source_span(field.key.source),
        declaration.kind,
        nested,
    )


def _primitive_semantic_tokens(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[IndexedSemanticToken, ...]:
    tokens = [IndexedSemanticToken("parameter", span) for _, span in _parameter_spans(primitive)]
    for attribute in primitive.attributes:
        tokens.append(IndexedSemanticToken("property", _source_span(attribute.key.source)))
        tokens.extend(_value_semantic_tokens(attribute.value))
    for primitive_field in primitive.fields:
        field = primitive_field.field
        tokens.extend(_field_semantic_tokens(field, descend=primitive_field.kind != "impls"))
        if primitive_field.kind == "generic_params":
            tokens.extend(
                IndexedSemanticToken("typeParameter", _source_span(item.key.source))
                for item in field.children
            )
        elif primitive_field.kind == "return_type":
            for item in field.children:
                if isinstance(item.value, ParsedTslScalarValue):
                    source = item.value.payload_source or item.value.source
                    tokens.append(IndexedSemanticToken("typeParameter", _source_span(source)))
        elif primitive_field.kind == "overload":
            axis = child(field, "axis")
            value = child(field, "value")
            if axis is not None and isinstance(axis.value, ParsedTslScalarValue):
                source = axis.value.payload_source or axis.value.source
                tokens.append(IndexedSemanticToken("class", _source_span(source)))
            if value is not None and isinstance(value.value, ParsedTslScalarValue):
                source = value.value.payload_source or value.value.source
                tokens.append(IndexedSemanticToken("enumMember", _source_span(source)))
        elif primitive_field.kind == "arithmetic":
            roles = child(field, "operand_roles")
            for role in children(roles):
                tokens.append(
                    IndexedSemanticToken("enumMember", _source_span(role.key.source))
                )
                if isinstance(role.value, ParsedTslScalarValue):
                    source = role.value.payload_source or role.value.source
                    tokens.append(IndexedSemanticToken("parameter", _source_span(source)))
        elif primitive_field.kind == "operand_roles":
            for role in children(field):
                tokens.append(
                    IndexedSemanticToken("enumMember", _source_span(role.key.source))
                )
                if isinstance(role.value, ParsedTslScalarValue):
                    source = role.value.payload_source or role.value.source
                    tokens.append(IndexedSemanticToken("parameter", _source_span(source)))
        elif primitive_field.kind == "operation":
            if (
                isinstance(field.value, ParsedTslScalarValue)
                and field.value.text in primitive_operation_values()
            ):
                source = field.value.payload_source or field.value.source
                tokens.append(IndexedSemanticToken("enumMember", _source_span(source)))
        elif primitive_field.kind == "memory":
            tokens.extend(
                _closed_contract_value_tokens(
                    field,
                    {
                        "access": memory_access_values(),
                        "addressing": memory_addressing_values(),
                    },
                )
            )
        elif primitive_field.kind == "conversion":
            tokens.extend(
                _closed_contract_value_tokens(
                    field,
                    {
                        "kind": conversion_kind_values(),
                        "lane_count": lane_count_relation_values(),
                    },
                )
            )
        elif primitive_field.kind == "shift":
            tokens.extend(
                _closed_contract_value_tokens(
                    field,
                    {
                        "count_rule": shift_count_rule_values(),
                        "lane_rule": shift_lane_rule_values(),
                    },
                )
            )
            scalar_count_types = child(field, "scalar_count_types")
            if scalar_count_types is not None and isinstance(
                scalar_count_types.value,
                ParsedTslListValue,
            ):
                tokens.extend(
                    IndexedSemanticToken(
                        "type",
                        _source_span(item.payload_source or item.source),
                    )
                    for item in scalar_count_types.value.items
                    if isinstance(item, ParsedTslScalarValue)
                )
    return tuple(tokens)


def _closed_contract_value_tokens(
    field: ParsedTslField,
    values_by_field: dict[str, tuple[str, ...]],
) -> tuple[IndexedSemanticToken, ...]:
    tokens: list[IndexedSemanticToken] = []
    for member in children(field):
        if not isinstance(member.value, ParsedTslScalarValue):
            continue
        if member.value.text not in values_by_field.get(member.key.text, ()):
            continue
        source = member.value.payload_source or member.value.source
        tokens.append(IndexedSemanticToken("enumMember", _source_span(source)))
    return tuple(tokens)


def _overload_registry_semantic_tokens(
    field: ParsedTslField,
) -> tuple[IndexedSemanticToken, ...]:
    tokens: list[IndexedSemanticToken] = []
    for axis in children(field):
        tokens.append(IndexedSemanticToken("class", _source_span(axis.key.source)))
        for value in children(child(axis, "values")):
            tokens.append(
                IndexedSemanticToken("enumMember", _source_span(value.key.source))
            )
    return tuple(tokens)


def _index_implementation_tokens(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    tokens: list[IndexedSemanticToken],
    result_target: tuple[str, str, SourceSpan] | None,
) -> None:
    def visit(entry: ParsedImplementationSelectorEntry, depth: int) -> None:
        kind: SemanticTokenKind = (
            "class"
            if depth == 0
            else "type"
            if depth == 1 or (depth == 3 and result_target is not None)
            else "typeParameter"
            if depth == 2 and result_target is not None
            else "enumMember"
        )
        tokens.extend(IndexedSemanticToken(kind, span) for _, span in selector_items(entry.selector))
        child_keys = {
            (child.selector.source.path.resolve(), child.selector.source.line, child.selector.source.column)
            for child in entry.children
        }
        for field in entry.fields:
            key = (field.key.source.path.resolve(), field.key.source.line, field.key.source.column)
            if key not in child_keys:
                tokens.extend(_field_semantic_tokens(field, descend=field.key.text != "variants"))
        for variant in entry.variants:
            tokens.append(IndexedSemanticToken("property", _name_in_source(variant.source, variant.name)))
            for field in variant.fields:
                tokens.extend(_field_semantic_tokens(field))
        for child in entry.children:
            visit(child, depth + 1)

    for entry in entries:
        visit(entry, 0)


def _block_semantic_tokens(block: ParsedBlockDeclaration) -> tuple[IndexedSemanticToken, ...]:
    return tuple(token for field in block.fields for token in _field_semantic_tokens(field))


def _field_semantic_tokens(
    field: ParsedTslField,
    *,
    descend: bool = True,
) -> tuple[IndexedSemanticToken, ...]:
    tokens = [IndexedSemanticToken("property", _source_span(field.key.source))]
    tokens.extend(_value_semantic_tokens(field.value, descend=descend))
    if descend:
        for child in field.children:
            tokens.extend(_field_semantic_tokens(child))
    return tuple(tokens)


def _value_semantic_tokens(
    value: ParsedTslValue | None,
    *,
    descend: bool = True,
) -> tuple[IndexedSemanticToken, ...]:
    if value is None:
        return ()
    if isinstance(value, ParsedTslScalarValue):
        if value.text not in _CLOSED_ENUM_VALUES:
            return ()
        return (
            IndexedSemanticToken("enumMember", _source_span(value.payload_source or value.source)),
        )
    if not descend:
        return ()
    tokens: list[IndexedSemanticToken] = []
    if isinstance(value, ParsedTslListValue):
        for item in value.items:
            tokens.extend(_value_semantic_tokens(item))
    elif isinstance(value, ParsedTslMapValue):
        for entry in value.entries:
            tokens.extend(_field_semantic_tokens(entry))
    elif isinstance(value, ParsedTslAttributeListValue):
        for attribute in value.attributes:
            tokens.append(IndexedSemanticToken("property", _source_span(attribute.key.source)))
            if attribute.key_argument is not None:
                tokens.append(
                    IndexedSemanticToken("property", _source_span(attribute.key_argument.source))
                )
            tokens.extend(_value_semantic_tokens(attribute.value))
    return tuple(tokens)


def _region_semantic_tokens(region: Region) -> tuple[IndexedSemanticToken, ...]:
    if region.source is None:
        return ()
    tokens = [
        IndexedSemanticToken(
            "keyword", _subspan(region.source, region.full_text, 0, len(region.keyword))
        )
    ]
    tokens.extend(_region_shell_semantic_tokens(region))
    tokens.extend(_query_root_semantic_tokens(region))
    if region.keyword == "call":
        call = parse_call_selector(region.selector_text)
        if call is not None:
            span = _region_selector_name_span(region, call.primitive_ref)
            if span is not None:
                tokens.append(IndexedSemanticToken("function", span))
    return tuple(tokens)


def _region_shell_semantic_tokens(region: Region) -> tuple[IndexedSemanticToken, ...]:
    if region.source is None or not region.selector_text:
        return ()
    descriptor = next(
        (item for item in DEFAULT_TSIL_REGION_DESCRIPTORS if item.keyword == region.keyword),
        None,
    )
    if descriptor is None:
        return ()
    keys: set[str] = set()
    values: set[str] = set()
    for form in descriptor.authoring.selector_forms:
        for term in form:
            if term.name is not None:
                keys.add(term.name)
            values.update(term.values)
            for option in term.options:
                keys.add(option.name)
                values.update(option.values)
    selector_offset = region.full_text.find(region.selector_text)
    if selector_offset < 0:
        return ()
    tokens: list[IndexedSemanticToken] = []
    for match in _SELECTOR_TOKEN.finditer(region.selector_text):
        name = match.group(0)
        kind: SemanticTokenKind | None = (
            "property" if name in keys else "enumMember" if name in values else None
        )
        if kind is not None:
            start = selector_offset + match.start()
            tokens.append(
                IndexedSemanticToken(
                    kind,
                    _subspan(region.source, region.full_text, start, start + len(name)),
                )
            )
    return tuple(tokens)


def _query_root_semantic_tokens(region: Region) -> tuple[IndexedSemanticToken, ...]:
    if region.source is None or region.keyword not in {"type", "value"}:
        return ()
    open_paren = region.full_text.find("(")
    close_paren = region.full_text.rfind(")")
    if open_paren < 0 or close_paren <= open_paren:
        return ()
    query = region.full_text[open_paren + 1 : close_paren]
    namespaces = set(DEFAULT_QUERY_AUTHORING_INDEX.namespace_children.get("", ()))
    root_functions = {name for name in DEFAULT_QUERY_AUTHORING_INDEX.functions if "::" not in name}
    tokens: list[IndexedSemanticToken] = []
    for match in _QUERY_ROOT.finditer(query):
        name = match.group(0)
        kind: SemanticTokenKind | None = (
            "namespace" if name in namespaces else "function" if name in root_functions else None
        )
        if kind is not None:
            start = open_paren + 1 + match.start()
            tokens.append(
                IndexedSemanticToken(
                    kind,
                    _subspan(region.source, region.full_text, start, start + len(name)),
                )
            )
    return tuple(tokens)


def _result_target(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[str, str, SourceSpan] | None:
    for primitive_field in primitive.fields_by_name("return_type"):
        for field in primitive_field.field.children:
            if isinstance(field.value, ParsedTslScalarValue):
                source = field.value.payload_source or field.value.source
                return field.key.text, field.value.text, _source_span(source)
    return None


def _parameter_spans(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[tuple[str, SourceSpan], ...]:
    text = primitive.header_source.text
    name_offset = text.find(primitive.name)
    open_paren = text.find("(", max(name_offset, 0) + len(primitive.name))
    close_paren = text.find(")", open_paren + 1)
    if open_paren < 0 or close_paren < 0:
        return ()
    cursor = open_paren + 1
    spans: list[tuple[str, SourceSpan]] = []
    source = _source_span(primitive.header_source)
    for parameter in primitive.parameters:
        offset = text.find(parameter, cursor, close_paren)
        if offset >= 0:
            spans.append((parameter, _subspan(source, text, offset, offset + len(parameter))))
            cursor = offset + len(parameter)
    return tuple(spans)


def _declaration_keyword_span(
    declaration: ParsedPrimitiveDeclaration | ParsedBlockDeclaration | ParsedFieldDeclaration,
) -> SourceSpan:
    if isinstance(declaration, ParsedPrimitiveDeclaration):
        return _subspan(
            _source_span(declaration.header_source), declaration.header_source.text, 0, len("prim")
        )
    if isinstance(declaration, ParsedBlockDeclaration):
        return _subspan(
            _source_span(declaration.source), declaration.source.text, 0, len(declaration.kind)
        )
    return _source_span(declaration.field.key.source)


def _regions(segments: Iterable[Segment]) -> Iterable[Region]:
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        yield segment
        yield from _regions(segment.body)
        if segment.block is not None:
            yield from _regions(segment.block)
        if segment.else_block is not None:
            yield from _regions(segment.else_block)
        if segment.arms is not None:
            for _, body in segment.arms:
                yield from _regions(body)


def _region_selector_name_span(region: Region, name: str) -> SourceSpan | None:
    if region.source is None:
        return None
    selector_offset = region.full_text.find(region.selector_text)
    name_offset = region.selector_text.find(name)
    if selector_offset < 0 or name_offset < 0:
        return region.source
    start = selector_offset + name_offset
    return _subspan(region.source, region.full_text, start, start + len(name))


def _deduplicated_tokens(
    tokens: Iterable[IndexedSemanticToken],
) -> tuple[IndexedSemanticToken, ...]:
    priority = {
        "keyword": 9,
        "function": 8,
        "class": 7,
        "type": 6,
        "typeParameter": 5,
        "parameter": 4,
        "namespace": 3,
        "enumMember": 2,
        "property": 1,
    }
    by_span: dict[SourceSpan, IndexedSemanticToken] = {}
    for token in tokens:
        existing = by_span.get(token.span)
        if existing is None or priority[token.kind] > priority[existing.kind]:
            by_span[token.span] = token
    return tuple(sorted(by_span.values(), key=lambda token: (*_span_key(token.span), token.kind)))


def _name_in_source(source: ParsedTslSourceSpan, name: str) -> SourceSpan:
    offset = source.text.find(name)
    if offset < 0:
        return _source_span(source)
    return _subspan(_source_span(source), source.text, offset, offset + len(name))


def _subspan(source: SourceSpan, text: str, start: int, end: int) -> SourceSpan:
    start_line, start_column = _offset_position(source, text, start)
    end_line, end_column = _offset_position(source, text, end)
    return SourceSpan(source.path, start_line, start_column, end_line, end_column)


def _offset_position(source: SourceSpan, text: str, offset: int) -> tuple[int, int]:
    before = text[:offset]
    line_offset = before.count("\n")
    if line_offset == 0:
        return source.line, source.column + offset
    return source.line + line_offset, len(before.rsplit("\n", 1)[-1]) + 1


def _source_span(source: ParsedTslSourceSpan) -> SourceSpan:
    return SourceSpan(
        source.path.resolve(),
        source.line,
        source.column,
        source.end_line,
        source.end_column,
    )


def _span_key(span: SourceSpan) -> tuple[str, int, int, int, int]:
    return (span.path.as_posix(), span.line, span.column, span.end_line, span.end_column)


def _document_symbol_key(
    symbol: IndexedDocumentSymbol,
) -> tuple[str, int, int, str, str]:
    span = symbol.selection_span
    return (span.path.as_posix(), span.line, span.column, symbol.kind, symbol.name)


__all__ = (
    "DocumentAuthoringIndex",
    "DocumentSymbolKind",
    "IndexedDocumentSymbol",
    "IndexedSemanticToken",
    "SemanticTokenKind",
    "build_document_authoring_index",
    "selector_items",
)
