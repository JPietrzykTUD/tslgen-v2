"""Compiler-owned source suggestions for direct implementation metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from tslc.catalog.model import ImplementationSafety
from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.lower.region_safety import direct_implementation_safety
from tslc.sources import SourceDocument
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)


@dataclass(frozen=True, slots=True)
class TextEdit:
    """One deterministic replacement in a specific source document."""

    path: Path
    start: int
    end: int
    replacement: str


@dataclass(frozen=True, slots=True)
class ImplementationEntryRef:
    """An implementation selector entry with its primitive and selector path."""

    primitive: ParsedPrimitiveDeclaration
    entry: ParsedImplementationSelectorEntry
    selector_path: tuple[str, ...]

    @property
    def identity(self) -> tuple[str, Path, int, int]:
        return (
            self.primitive.name,
            self.entry.source.path,
            self.entry.source.line,
            self.entry.source.column,
        )

    @property
    def subject(self) -> str:
        return f"{self.primitive.name} {'/'.join(self.selector_path)}"


@dataclass(frozen=True, slots=True)
class SafetyMetadataSuggestion:
    """A source-owned safety fact delta and its exact optional edit."""

    path: Path
    line: int
    subject: str
    reason: str
    before: str
    after: str
    edit: TextEdit | None
    scope: SourceSpan


def safety_metadata_suggestions(
    parsed: OuterTslParseResult,
    documents: Mapping[Path, SourceDocument],
    *,
    path: Path | None = None,
) -> tuple[SafetyMetadataSuggestion, ...]:
    """Return exact edits for missing direct implementation-safety facts."""

    suggestions: list[SafetyMetadataSuggestion] = []
    selected_path = path.resolve() if path is not None else None
    for ref in implementation_entries(parsed):
        entry = ref.entry
        if selected_path is not None and entry.source.path.resolve() != selected_path:
            continue
        if not entry.body_envelopes:
            continue
        required = _direct_safety_facts(entry)
        local = _entry_safety(entry)
        if _safety_contains(local, required):
            continue
        after = local.merge(required)
        suggestions.append(
            SafetyMetadataSuggestion(
                path=entry.source.path,
                line=entry.source.line,
                subject=ref.subject,
                reason="typed implementation-body facts require safety metadata",
                before=_render_safety_block(child_indent(entry), local).rstrip(),
                after=_render_safety_block(child_indent(entry), after).rstrip(),
                edit=_safety_edit(documents, entry, after),
                scope=entry_scope(entry),
            )
        )
    return tuple(suggestions)


def implementation_entries(
    parsed: OuterTslParseResult,
) -> tuple[ImplementationEntryRef, ...]:
    """Return every implementation selector entry in deterministic source order."""

    result: list[ImplementationEntryRef] = []
    for document in parsed.documents:
        for primitive in document.primitives:
            result.extend(
                ImplementationEntryRef(primitive, entry, selector_path)
                for entry, selector_path in _walk_entries(primitive.impl_entries)
            )
    return tuple(result)


def implementation_entry_index(
    parsed: OuterTslParseResult,
) -> dict[tuple[str, Path, int, int], ImplementationEntryRef]:
    """Index implementation entries by the identity used in lowering traces."""

    return {ref.identity: ref for ref in implementation_entries(parsed)}


def child_indent(entry: ParsedImplementationSelectorEntry) -> str:
    return " " * (entry.source.column + 1)


def entry_scope(entry: ParsedImplementationSelectorEntry) -> SourceSpan:
    """Return the complete selector-entry range used by authoring actions."""

    spans = [entry.source]
    spans.extend(field.source for field in entry.fields)
    spans.extend(envelope.envelope_source for envelope in entry.body_envelopes)
    for variant in entry.variants:
        spans.append(variant.source)
        spans.extend(field.source for field in variant.fields)
        spans.extend(envelope.envelope_source for envelope in variant.body_envelopes)
    end = max(spans, key=lambda span: (span.end_line, span.end_column))
    return SourceSpan(
        path=entry.source.path,
        line=entry.source.line,
        column=entry.source.column,
        end_line=end.end_line,
        end_column=end.end_column,
    )


def first_field(
    entry: ParsedImplementationSelectorEntry,
    name: str,
) -> ParsedTslField | None:
    return next((field for field in entry.fields if field.key.text == name), None)


def list_text(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    return tuple(
        item.text
        for item in field.value.items
        if isinstance(item, ParsedTslScalarValue)
    )


def replace_field_edit(
    documents: Mapping[Path, SourceDocument],
    field: ParsedTslField,
    replacement: str,
) -> TextEdit | None:
    document = documents.get(field.source.path)
    if document is None:
        return None
    start = _offset(document.text, field.source)
    return TextEdit(
        path=field.source.path,
        start=start,
        end=start + len(field.source.text),
        replacement=replacement,
    )


def insert_before_field_edit(
    documents: Mapping[Path, SourceDocument],
    field: ParsedTslField,
    replacement: str,
) -> TextEdit | None:
    document = documents.get(field.source.path)
    if document is None:
        return None
    start = _line_start(document.text, field.source.line)
    return TextEdit(
        path=field.source.path,
        start=start,
        end=start,
        replacement=replacement,
    )


def _direct_safety_facts(
    entry: ParsedImplementationSelectorEntry,
) -> ImplementationSafety:
    safety = ImplementationSafety()
    for envelope in entry.body_envelopes:
        safety = safety.merge(
            direct_implementation_safety(scan(envelope.payload_text))
        )
    return safety


def _safety_edit(
    documents: Mapping[Path, SourceDocument],
    entry: ParsedImplementationSelectorEntry,
    safety: ImplementationSafety,
) -> TextEdit | None:
    field = first_field(entry, "safety")
    rendered = _render_safety_block(child_indent(entry), safety)
    if field is not None:
        return replace_field_edit(documents, field, rendered.rstrip())
    anchor = first_field(entry, "implementation") or (
        entry.fields[0] if entry.fields else None
    )
    if anchor is None:
        return None
    return insert_before_field_edit(documents, anchor, rendered)


def _entry_safety(entry: ParsedImplementationSelectorEntry) -> ImplementationSafety:
    safety = ImplementationSafety()
    for field in entry.fields:
        if field.key.text != "safety":
            continue
        children = {child.key.text: child for child in field.children}
        safety = safety.merge(
            ImplementationSafety(
                internal_unsafe=_bool_field(children.get("internal_unsafe")),
                caller_unsafe=_bool_field(children.get("caller_unsafe")),
                reasons=frozenset(list_text(children.get("reasons"))),
            )
        )
    return safety


def _safety_contains(
    actual: ImplementationSafety,
    required: ImplementationSafety,
) -> bool:
    return (
        (actual.internal_unsafe or not required.internal_unsafe)
        and (actual.caller_unsafe or not required.caller_unsafe)
        and required.reasons <= actual.reasons
    )


def _bool_field(field: ParsedTslField | None) -> bool:
    if field is None or not isinstance(field.value, ParsedTslScalarValue):
        return False
    return field.value.text.lower() == "true"


def _walk_entries(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    parent_path: tuple[str, ...] = (),
) -> tuple[tuple[ParsedImplementationSelectorEntry, tuple[str, ...]], ...]:
    result: list[tuple[ParsedImplementationSelectorEntry, tuple[str, ...]]] = []
    for entry in entries:
        selector_path = (*parent_path, entry.selector.text)
        result.append((entry, selector_path))
        result.extend(_walk_entries(entry.children, selector_path))
    return tuple(result)


def _render_safety_block(indent: str, safety: ImplementationSafety) -> str:
    return (
        f"{indent}safety:\n"
        f"{indent}  internal_unsafe {_bool_text(safety.internal_unsafe)}\n"
        f"{indent}  caller_unsafe {_bool_text(safety.caller_unsafe)}\n"
        f"{indent}  reasons {_format_list(sorted(safety.reasons))}\n"
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _format_list(items: Sequence[str]) -> str:
    return "[" + ", ".join(items) + "]" if items else "[]"


def _offset(text: str, span: ParsedTslSourceSpan) -> int:
    return _line_start(text, span.line) + span.column - 1


def _line_start(text: str, line: int) -> int:
    if line <= 1:
        return 0
    offset = 0
    for _ in range(line - 1):
        next_newline = text.find("\n", offset)
        if next_newline < 0:
            return len(text)
        offset = next_newline + 1
    return offset


__all__ = (
    "ImplementationEntryRef",
    "SafetyMetadataSuggestion",
    "TextEdit",
    "child_indent",
    "entry_scope",
    "first_field",
    "implementation_entries",
    "implementation_entry_index",
    "insert_before_field_edit",
    "list_text",
    "replace_field_edit",
    "safety_metadata_suggestions",
)
