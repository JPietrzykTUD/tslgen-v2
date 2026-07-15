"""Parsed-source cursor context for editor authoring features."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Literal

from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
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
_CALL_CONTEXT = re.compile(r"call\s*<\s*primitive\s*=\s*(@?[A-Za-z0-9_]*)$")
_REGION_SHELL_CONTEXT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*<([^>]*)$")


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
    primitive_parameters: tuple[str, ...] = ()
    generic_parameters: tuple[str, ...] = ()
    extension_selector: str | None = None
    type_selector: str | None = None
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

    tsil_source = _tsil_payload_source(declaration, text, bounded_offset)
    if tsil_source is not None:
        current_field, position_kind, prefix_range, prefix = _tsil_line_role(
            line_before,
            line_start,
            bounded_offset,
        )
        context_source = tsil_source
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
    generic_parameters: tuple[str, ...] = ()
    if isinstance(declaration, ParsedPrimitiveDeclaration):
        primitive_parameters = declaration.parameters
        generic_parameters = _generic_parameter_names(declaration)
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
        primitive_parameters=primitive_parameters,
        generic_parameters=generic_parameters,
        extension_selector=extension_selector,
        type_selector=type_selector,
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


def _tsil_line_role(
    line_before: str,
    line_start: int,
    offset: int,
) -> tuple[str | None, AuthoringPositionKind, AuthoringTextRange, str]:
    call = _CALL_CONTEXT.search(line_before)
    if call is not None:
        return (
            "$primitive-call",
            "tsil-region-shell",
            AuthoringTextRange(line_start + call.start(1), offset),
            call.group(1),
        )
    shell = _REGION_SHELL_CONTEXT.search(line_before)
    if shell is not None and shell.group(1) in {"cast", "var"}:
        selector = shell.group(2).rsplit(",", 1)[-1].strip()
        return (
            f"${shell.group(1)}-selector",
            "tsil-region-shell",
            AuthoringTextRange(offset - len(selector), offset),
            selector,
        )
    replacement, prefix = _replacement_range(line_before, line_start, offset)
    return "$region-keyword", "tsil-region-boundary", replacement, prefix


def _tsil_payload_source(
    declaration: ParsedTopLevelDeclaration, text: str, offset: int
) -> AuthoringContextSource | None:
    if not isinstance(declaration, ParsedPrimitiveDeclaration):
        return None
    for envelope in declaration.body_envelopes:
        if not _contains(envelope.payload_source, text, offset):
            continue
        return (
            "parsed"
            if _span_matches(envelope.payload_source, text)
            else "incomplete-line"
        )
    return None


def _generic_parameter_names(
    declaration: ParsedPrimitiveDeclaration,
) -> tuple[str, ...]:
    return tuple(
        child.key.text
        for field in declaration.fields
        if field.field.key.text == "generic_params"
        for child in field.field.children
    )


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
