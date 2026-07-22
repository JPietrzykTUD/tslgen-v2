"""Parsed-source cursor context for editor authoring features."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal

from tslc.ir.scan import tsil_cursor_context
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
    ParsedTslAttributeListValue,
    ParsedTslQuoteForm,
    ParsedTopLevelDeclaration,
    ParsedTopLevelDeclarationKind,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
    ParsedTslValue,
)


AuthoringPositionKind = Literal[
    "field-name",
    "scalar-value",
    "list-value",
    "selector",
    "tsil-region-boundary",
    "tsil-region-shell",
    "tsil-raw",
    "unknown",
]
AuthoringContextSource = Literal["parsed", "incomplete-line", "lexical"]

_WORD_SUFFIX = re.compile(r"[@?A-Za-z_][@?A-Za-z0-9_.-]*$")
_FIELD_VALUE = re.compile(
    r'^(?P<key>"(?:\\.|[^"\\])*"|\[.*\]|[A-Za-z_?][A-Za-z0-9_?.]*)'
    r"\s*:?\s+(?P<value>.*)$"
)
_PRIMITIVE_SIGNATURE = re.compile(r"^\s*prim<(?P<signature>[^>]*)$")
@dataclass(frozen=True, slots=True)
class AuthoringTextRange:
    """Python-codepoint offsets replaced by one completion."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class AuthoringCursorContext:
    """Compiler-owned structural facts at one source cursor."""

    path: Path
    offset: int
    line: int
    column: int
    indentation: int
    replacement_range: AuthoringTextRange
    prefix: str
    declaration_kind: ParsedTopLevelDeclarationKind | None
    declaration_name: str | None
    block_path: tuple[str, ...]
    position_kind: AuthoringPositionKind
    current_field: str | None
    existing_fields: tuple[str, ...]
    sibling_scalars: tuple[tuple[str, str], ...] = ()
    primitive_parameters: tuple[str, ...] = ()
    primitive_attributes: tuple[str, ...] = ()
    generic_parameters: tuple[str, ...] = ()
    generic_parameter_kinds: tuple[tuple[str, str], ...] = ()
    extension_selector: str | None = None
    type_selector: str | None = None
    tsil_region_keyword: str | None = None
    tsil_selector_start: int | None = None
    tsil_selector_prefix: str | None = None
    tsil_region_path: tuple[str, ...] = ()
    tsil_argument_keyword: str | None = None
    tsil_argument_selector: str | None = None
    tsil_argument_start: int | None = None
    tsil_argument_prefix: str | None = None
    tsil_in_opaque_text: bool = False
    source: AuthoringContextSource = "lexical"


@dataclass(frozen=True, slots=True)
class _MappingNode:
    path: tuple[str, ...]
    source: ParsedTslSourceSpan
    fields: tuple[ParsedTslField, ...]


@dataclass(frozen=True, slots=True)
class _FieldSite:
    parent: _MappingNode
    field: ParsedTslField


def authoring_cursor_context(
    parsed: OuterTslParseResult | None,
    path: Path,
    text: str,
    offset: int,
) -> AuthoringCursorContext:
    """Project parsed structure and the active incomplete line into a cursor context."""

    bounded_offset = min(max(offset, 0), len(text))
    line_starts = _line_starts(text)
    line_index = _line_index(line_starts, bounded_offset)
    line_start = line_starts[line_index]
    line_end = text.find("\n", line_start)
    if line_end < 0:
        line_end = len(text)
    line_text = text[line_start:line_end].rstrip("\r")
    line_before = text[line_start:bounded_offset]
    indentation = len(line_text) - len(line_text.lstrip(" \t"))
    prefix_range, prefix = _replacement_range(line_before, line_start, bounded_offset)

    signature = _PRIMITIVE_SIGNATURE.match(line_before)
    if signature is not None:
        signature_start = line_start + signature.start("signature")
        return AuthoringCursorContext(
            path=path.resolve(),
            offset=bounded_offset,
            line=line_index + 1,
            column=bounded_offset - line_start + 1,
            indentation=indentation,
            replacement_range=AuthoringTextRange(signature_start, bounded_offset),
            prefix=signature.group("signature"),
            declaration_kind=None,
            declaration_name=None,
            block_path=(),
            position_kind="selector",
            current_field="$primitive_signature",
            existing_fields=(),
            source="lexical",
        )

    document = _document(parsed, path)
    declaration = _enclosing_declaration(document, text, bounded_offset, indentation)
    if declaration is None:
        return AuthoringCursorContext(
            path=path.resolve(),
            offset=bounded_offset,
            line=line_index + 1,
            column=bounded_offset - line_start + 1,
            indentation=indentation,
            replacement_range=prefix_range,
            prefix=prefix,
            declaration_kind=None,
            declaration_name=None,
            block_path=(),
            position_kind="field-name",
            current_field=None,
            existing_fields=(),
            source="lexical",
        )

    root, nodes, fields = _declaration_sites(declaration)
    parent = _mapping_at(nodes, text, bounded_offset, indentation) or root
    site, exact_kind = _exact_field_site(fields, text, bounded_offset)
    if site is not None:
        parent = site.parent

    current_field = site.field.key.text if site is not None else None
    position_kind: AuthoringPositionKind = exact_kind or "field-name"
    context_source: AuthoringContextSource = "parsed" if site is not None else "incomplete-line"

    tsil_region_keyword: str | None = None
    tsil_selector_start: int | None = None
    tsil_selector_prefix: str | None = None
    tsil_region_path: tuple[str, ...] = ()
    tsil_argument_keyword: str | None = None
    tsil_argument_selector: str | None = None
    tsil_argument_start: int | None = None
    tsil_argument_prefix: str | None = None
    tsil_in_opaque_text = False
    tsil_site = _tsil_payload_site(declaration, text, bounded_offset)
    if tsil_site is not None:
        payload_start, quote_form, context_source = tsil_site
        payload_prefix = text[payload_start:bounded_offset]
        if quote_form == "inline":
            payload_prefix = _normalize_inline_payload(payload_prefix)
        tsil = tsil_cursor_context(
            payload_prefix,
            bounded_offset - payload_start,
        )
        prefix_range = AuthoringTextRange(
            payload_start + tsil.replacement_start,
            payload_start + tsil.replacement_end,
        )
        prefix = tsil.prefix
        tsil_region_path = tsil.region_path
        tsil_argument_keyword = tsil.argument_keyword
        tsil_argument_selector = tsil.argument_selector
        tsil_argument_start = (
            None
            if tsil.argument_start is None
            else payload_start + tsil.argument_start
        )
        tsil_argument_prefix = tsil.argument_prefix
        tsil_in_opaque_text = tsil.in_opaque_text
        if tsil.kind == "region-boundary":
            current_field = "$region-keyword"
            position_kind = "tsil-region-boundary"
        elif tsil.kind == "region-shell":
            current_field = "$region-shell"
            position_kind = "tsil-region-shell"
            tsil_region_keyword = tsil.keyword
            tsil_selector_start = (
                None
                if tsil.selector_start is None
                else payload_start + tsil.selector_start
            )
            tsil_selector_prefix = tsil.selector_prefix
        else:
            current_field = None
            position_kind = "tsil-raw"
    elif site is None:
        current_field, position_kind = _incomplete_line_role(line_before)
        same_line = tuple(
            field
            for field in parent.fields
            if field.key.source.line == line_index + 1
            and field.key.source.column - 1 < len(line_before)
        )
        if same_line:
            nearest = max(same_line, key=lambda field: field.key.source.column)
            segment = line_before[nearest.key.source.column - 1 :]
            if segment.strip():
                inferred_field, inferred_kind = _incomplete_line_role(segment)
                current_field = inferred_field or nearest.key.text
                position_kind = inferred_kind

    block_path = parent.path
    primitive_parameters: tuple[str, ...] = ()
    primitive_attributes: tuple[str, ...] = ()
    generic_parameters: tuple[str, ...] = ()
    generic_parameter_kinds: tuple[tuple[str, str], ...] = ()
    if isinstance(declaration, ParsedPrimitiveDeclaration):
        primitive_parameters = declaration.parameters
        primitive_attributes = tuple(
            attribute.key.text for attribute in declaration.attributes
        )
        generic_parameters = _generic_parameter_names(declaration)
        generic_parameter_kinds = _generic_parameter_kinds(declaration)
    extension_selector, type_selector = _implementation_selectors(block_path)

    return AuthoringCursorContext(
        path=path.resolve(),
        offset=bounded_offset,
        line=line_index + 1,
        column=bounded_offset - line_start + 1,
        indentation=indentation,
        replacement_range=prefix_range,
        prefix=prefix,
        declaration_kind=_declaration_kind(declaration),
        declaration_name=_declaration_name(declaration),
        block_path=block_path,
        position_kind=position_kind,
        current_field=current_field,
        existing_fields=tuple(field.key.text for field in parent.fields),
        sibling_scalars=tuple(
            (field.key.text, field.value.text)
            for field in parent.fields
            if isinstance(field.value, ParsedTslScalarValue)
        ),
        primitive_parameters=primitive_parameters,
        primitive_attributes=primitive_attributes,
        generic_parameters=generic_parameters,
        generic_parameter_kinds=generic_parameter_kinds,
        extension_selector=extension_selector,
        type_selector=type_selector,
        tsil_region_keyword=tsil_region_keyword,
        tsil_selector_start=tsil_selector_start,
        tsil_selector_prefix=tsil_selector_prefix,
        tsil_region_path=tsil_region_path,
        tsil_argument_keyword=tsil_argument_keyword,
        tsil_argument_selector=tsil_argument_selector,
        tsil_argument_start=tsil_argument_start,
        tsil_argument_prefix=tsil_argument_prefix,
        tsil_in_opaque_text=tsil_in_opaque_text,
        source=context_source,
    )


def _document(
    parsed: OuterTslParseResult | None, path: Path
) -> ParsedOuterTslDocument | None:
    if parsed is None:
        return None
    resolved = path.resolve()
    return next(
        (document for document in parsed.documents if document.path.resolve() == resolved),
        None,
    )


def _enclosing_declaration(
    document: ParsedOuterTslDocument | None,
    text: str,
    offset: int,
    indentation: int,
) -> ParsedTopLevelDeclaration | None:
    if document is None or indentation == 0:
        return None
    candidates = [
        declaration
        for declaration in document.declarations
        if _span_offsets(_declaration_source(declaration), text)[0] <= offset
        and _declaration_anchor_matches(declaration, text)
    ]
    if not candidates:
        return None
    candidate = max(
        candidates,
        key=lambda item: _span_offsets(_declaration_source(item), text)[0],
    )
    start, end = _span_offsets(_declaration_source(candidate), text)
    if start <= offset <= end:
        return candidate
    # A failed parse retains the last valid declaration. Its line offsets can end
    # before a newly inserted line, but its start and the current indentation still
    # provide a safe enclosing mapping until another declaration begins.
    return candidate


def _declaration_sites(
    declaration: ParsedTopLevelDeclaration,
) -> tuple[_MappingNode, tuple[_MappingNode, ...], tuple[_FieldSite, ...]]:
    root_path: tuple[str, ...]
    if isinstance(declaration, ParsedPrimitiveDeclaration):
        declaration_fields = tuple(field.field for field in declaration.fields)
        root_path = ("primitive",)
    elif isinstance(declaration, ParsedBlockDeclaration):
        declaration_fields = declaration.fields
        root_path = (declaration.kind,)
    else:
        declaration_fields = (declaration.field,)
        root_path = ()
    root = _MappingNode(root_path, _declaration_source(declaration), declaration_fields)
    nodes: list[_MappingNode] = [root]
    sites: list[_FieldSite] = []
    _collect_fields(root, nodes, sites)
    return root, tuple(nodes), tuple(sites)


def _collect_fields(
    parent: _MappingNode,
    nodes: list[_MappingNode],
    sites: list[_FieldSite],
) -> None:
    for field in parent.fields:
        sites.append(_FieldSite(parent, field))
        entries = _field_entries(field)
        if entries:
            child = _MappingNode((*parent.path, field.key.text), field.source, entries)
            nodes.append(child)
            _collect_fields(child, nodes, sites)
        if isinstance(field.value, ParsedTslListValue):
            for item in field.value.items:
                if not isinstance(item, ParsedTslMapValue):
                    continue
                child = _MappingNode(
                    (*parent.path, field.key.text, "$item"),
                    item.source,
                    item.entries,
                )
                nodes.append(child)
                _collect_fields(child, nodes, sites)


def _field_entries(field: ParsedTslField) -> tuple[ParsedTslField, ...]:
    if field.children:
        return field.children
    if isinstance(field.value, ParsedTslMapValue):
        return field.value.entries
    return ()


def _mapping_at(
    nodes: tuple[_MappingNode, ...],
    text: str,
    offset: int,
    indentation: int,
) -> _MappingNode | None:
    starts = _line_starts(text)
    bounded = min(max(offset, 0), len(text))
    cursor_index = _line_index(starts, bounded)
    cursor_line = cursor_index + 1
    cursor_column = bounded - starts[cursor_index] + 1
    containing = [
        node
        for node in nodes
        if _contains(node.source, text, offset)
        and (
            node.source.column - 1 < indentation
            or node.source.line == cursor_line
        )
        and not (
            node.source.line == cursor_line
            and node.source.column - 1 == indentation
            and cursor_column <= node.source.column + len(node.path[-1]) + 1
            and not _span_matches(node.source, text)
        )
    ]
    if containing:
        return max(containing, key=lambda node: (len(node.path), node.source.column))
    preceding = [
        node
        for node in nodes
        if _span_offsets(node.source, text)[0] <= offset
        and max(node.source.column - 1, 0) < indentation
    ]
    return max(
        preceding,
        key=lambda node: (_span_offsets(node.source, text)[0], len(node.path)),
        default=None,
    )


def _exact_field_site(
    sites: tuple[_FieldSite, ...], text: str, offset: int
) -> tuple[_FieldSite | None, AuthoringPositionKind | None]:
    matches: list[tuple[int, _FieldSite, AuthoringPositionKind]] = []
    for site in sites:
        field = site.field
        if _span_matches(field.key.source, text) and _contains(
            field.key.source, text, offset
        ):
            matches.append((len(site.parent.path), site, "field-name"))
        value_kind = _value_position(field.value, text, offset)
        if value_kind is not None:
            matches.append((len(site.parent.path) + 1, site, value_kind))
    if not matches:
        return None, None
    _, site, kind = max(matches, key=lambda item: item[0])
    return site, kind


def _value_position(
    value: ParsedTslValue | None, text: str, offset: int
) -> AuthoringPositionKind | None:
    if (
        value is None
        or not _span_matches(value.source, text)
        or not _contains(value.source, text, offset)
    ):
        return None
    if isinstance(value, ParsedTslScalarValue):
        return "scalar-value"
    if isinstance(value, ParsedTslListValue):
        return "list-value"
    return None


def _incomplete_line_role(
    line_before: str,
) -> tuple[str | None, AuthoringPositionKind]:
    content = line_before.lstrip(" \t")
    match = _FIELD_VALUE.match(content)
    if match is None:
        return None, "field-name"
    key = match.group("key")
    value = match.group("value")
    if "[" in value and value.rfind("[") > value.rfind("]"):
        return key, "list-value"
    return key, "scalar-value"


def _tsil_payload_site(
    declaration: ParsedTopLevelDeclaration, text: str, offset: int
) -> tuple[int, ParsedTslQuoteForm, AuthoringContextSource] | None:
    if not isinstance(declaration, ParsedPrimitiveDeclaration):
        return None
    for envelope in declaration.body_envelopes:
        start, parsed_end = _span_offsets(envelope.payload_source, text)
        if not _payload_opener_matches(text, start, envelope.quote_form):
            continue
        current_end = _current_payload_end(
            text,
            start,
            parsed_end,
            envelope.quote_form,
        )
        if not start <= offset <= current_end:
            continue
        return start, envelope.quote_form, (
            "parsed"
            if _span_matches(envelope.payload_source, text)
            else "incomplete-line"
        )
    return None


def _normalize_inline_payload(text: str) -> str:
    """Expose outer-string-escaped target quotes without changing offsets."""

    normalized = list(text)
    index = 0
    while index < len(text):
        if text[index] != "\\":
            index += 1
            continue
        start = index
        while index < len(text) and text[index] == "\\":
            index += 1
        if index >= len(text) or text[index] != '"' or (index - start) % 2 == 0:
            continue
        decoded_backslashes = (index - start - 1) // 2
        keep_from = index - decoded_backslashes
        for position in range(start, keep_from):
            normalized[position] = " "
    return "".join(normalized)


def _payload_opener_matches(
    text: str,
    start: int,
    quote_form: ParsedTslQuoteForm,
) -> bool:
    if quote_form == "multiline":
        return start >= 3 and text[start - 3 : start] == '"""'
    if quote_form == "inline":
        return start >= 1 and text[start - 1] == '"'
    return True


def _current_payload_end(
    text: str,
    start: int,
    parsed_end: int,
    quote_form: ParsedTslQuoteForm,
) -> int:
    if quote_form == "multiline":
        close = text.find('"""', start)
        return len(text) if close < 0 else close
    if quote_form == "inline":
        index = start
        while index < len(text):
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == '"':
                return index
            index += 1
        return len(text)
    return parsed_end


def _generic_parameter_names(
    declaration: ParsedPrimitiveDeclaration,
) -> tuple[str, ...]:
    return tuple(
        child.key.text
        for field in declaration.fields
        if field.field.key.text == "generic_params"
        for child in field.field.children
    )


def _generic_parameter_kinds(
    declaration: ParsedPrimitiveDeclaration,
) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for field in declaration.fields:
        if field.field.key.text != "generic_params":
            continue
        for parameter in field.field.children:
            kind = next(
                (
                    child.value.text
                    for child in parameter.children
                    if child.key.text == "kind"
                    and isinstance(child.value, ParsedTslScalarValue)
                ),
                None,
            )
            if kind is None and isinstance(
                parameter.value,
                ParsedTslAttributeListValue,
            ):
                kind = next(
                    (
                        attribute.value.text
                        for attribute in parameter.value.attributes
                        if attribute.key.text == "kind"
                        and isinstance(attribute.value, ParsedTslScalarValue)
                    ),
                    None,
                )
            if kind is None and isinstance(parameter.value, ParsedTslMapValue):
                kind = next(
                    (
                        entry.value.text
                        for entry in parameter.value.entries
                        if entry.key.text == "kind"
                        and isinstance(entry.value, ParsedTslScalarValue)
                    ),
                    None,
                )
            if kind is not None:
                result.append((parameter.key.text, kind))
    return tuple(result)


def _implementation_selectors(
    block_path: tuple[str, ...],
) -> tuple[str | None, str | None]:
    try:
        impls = block_path.index("impls")
    except ValueError:
        return None, None
    following = block_path[impls + 1 :]
    extension = following[0] if following else None
    type_selector = following[1] if len(following) > 1 else None
    return extension, type_selector


def _declaration_kind(
    declaration: ParsedTopLevelDeclaration,
) -> ParsedTopLevelDeclarationKind:
    if isinstance(declaration, ParsedPrimitiveDeclaration):
        return "primitive"
    return declaration.kind


def _declaration_name(declaration: ParsedTopLevelDeclaration) -> str | None:
    if isinstance(declaration, (ParsedPrimitiveDeclaration, ParsedBlockDeclaration)):
        return declaration.name
    return declaration.field.key.text


def _declaration_source(
    declaration: ParsedTopLevelDeclaration,
) -> ParsedTslSourceSpan:
    if isinstance(declaration, ParsedFieldDeclaration):
        return declaration.field.source
    return declaration.source


def _declaration_anchor_matches(
    declaration: ParsedTopLevelDeclaration,
    text: str,
) -> bool:
    source = _declaration_source(declaration)
    anchor = (
        declaration.header_source.text
        if isinstance(declaration, ParsedPrimitiveDeclaration)
        else source.text.splitlines()[0]
    )
    starts = _line_starts(text)
    if source.line < 1 or source.line > len(starts):
        return False
    start = _source_offset(starts, text, source.line, source.column)
    return text.startswith(anchor, start)


def _replacement_range(
    line_before: str, line_start: int, offset: int
) -> tuple[AuthoringTextRange, str]:
    match = _WORD_SUFFIX.search(line_before)
    if match is None:
        return AuthoringTextRange(offset, offset), ""
    return AuthoringTextRange(line_start + match.start(), offset), match.group(0)


def _span_offsets(span: ParsedTslSourceSpan, text: str) -> tuple[int, int]:
    starts = _line_starts(text)
    start = _source_offset(starts, text, span.line, span.column)
    end = _source_offset(starts, text, span.end_line, span.end_column)
    return start, max(start, end)


def _contains(span: ParsedTslSourceSpan, text: str, offset: int) -> bool:
    starts = _line_starts(text)
    line_index = _line_index(starts, min(max(offset, 0), len(text)))
    position = (line_index + 1, offset - starts[line_index] + 1)
    return (span.line, span.column) <= position <= (
        span.end_line,
        span.end_column,
    )


def _span_matches(span: ParsedTslSourceSpan, text: str) -> bool:
    start, end = _span_offsets(span, text)
    return text[start:end] == span.text


def _source_offset(
    starts: tuple[int, ...], text: str, line: int, column: int
) -> int:
    if not starts:
        return 0
    line_index = min(max(line - 1, 0), len(starts) - 1)
    return min(starts[line_index] + max(column - 1, 0), len(text))


@lru_cache(maxsize=8)
def _line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    starts.extend(index + 1 for index, character in enumerate(text) if character == "\n")
    return tuple(starts)


def _line_index(starts: tuple[int, ...], offset: int) -> int:
    low = 0
    high = len(starts)
    while low + 1 < high:
        middle = (low + high) // 2
        if starts[middle] <= offset:
            low = middle
        else:
            high = middle
    return low


__all__ = (
    "AuthoringContextSource",
    "AuthoringCursorContext",
    "AuthoringPositionKind",
    "AuthoringTextRange",
    "authoring_cursor_context",
)
