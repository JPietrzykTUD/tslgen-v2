"""Typed, version-checked source actions for editor clients."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from tslc.syntax.access import source_span
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.sources import SourceDocument
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedImplementationSelectorEntry,
    ParsedTslField,
)
from tslc.syntax.authoring import AuthoringTextRange

if TYPE_CHECKING:
    from tslc.maintenance.metadata_audit import TextEdit

ActionKind = Literal["quickfix", "help"]

_PRIMITIVE_GUIDE = (
    "https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/add-primitive.md"
)
_EXTENSION_GUIDE = (
    "https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/add-extension.md"
)
_EDITOR_GUIDE = (
    "https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/tsl-editor.md"
)
_EXTENSION_DIAGNOSTIC_TERMS = (
    "COMPILE-GUARD",
    "DATAPARALLEL",
    "INHERITS",
    "SUPERSEDES",
    "TARGET-FAMILIES",
)


@dataclass(frozen=True, slots=True)
class ExpectedDocument:
    path: Path
    version: int | None
    digest: str


@dataclass(frozen=True, slots=True)
class AuthoringEdit:
    range: AuthoringTextRange
    replacement: str
    expected_text: str


@dataclass(frozen=True, slots=True)
class AuthoringAction:
    title: str
    kind: ActionKind
    diagnostic_identity: str
    expected_document: ExpectedDocument
    edit: AuthoringEdit | None = None
    diagnostic: Diagnostic | None = None
    guide_url: str | None = None
    preferred: bool = False


def authoring_actions(
    *,
    parsed: OuterTslParseResult | None,
    diagnostics: tuple[Diagnostic, ...],
    path: Path,
    text: str,
    version: int | None,
    request_range: AuthoringTextRange,
) -> tuple[AuthoringAction, ...]:
    """Return exact edits and help actions for the current document snapshot."""

    if parsed is None:
        return ()
    resolved = path.resolve()
    expected = ExpectedDocument(resolved, version, _digest(text))
    document = SourceDocument(resolved, text, expected.digest, "tsl")
    actions: list[AuthoringAction] = []
    occupied_edits: set[tuple[int, int]] = set()

    # The audit also supports selection/lowering workflows. Import its exact
    # source-edit projection only when a code action is requested so ordinary
    # language-server startup does not load that heavier maintenance boundary.
    from tslc.maintenance.metadata_audit import safety_metadata_suggestions

    for suggestion in safety_metadata_suggestions(
        parsed, {resolved: document}, path=resolved
    ):
        edit = suggestion.edit
        if (
            edit is None
            or edit.path.resolve() != resolved
            or suggestion.scope is None
            or not _span_intersects_range(text, suggestion.scope, request_range)
        ):
            continue
        action_edit = AuthoringEdit(
            range=AuthoringTextRange(edit.start, edit.end),
            replacement=edit.replacement,
            expected_text=text[edit.start : edit.end],
        )
        occupied_edits.add((edit.start, edit.end))
        actions.append(
            AuthoringAction(
                title=f"Add required safety metadata for {suggestion.subject}",
                kind="quickfix",
                diagnostic_identity=_metadata_identity(suggestion.subject, edit),
                expected_document=expected,
                edit=action_edit,
                preferred=True,
            )
        )

    selected_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.span is not None
        and diagnostic.span.path.resolve() == resolved
        and _span_intersects_range(text, diagnostic.span, request_range)
    )
    safety_fields = _safety_fields(parsed, resolved)
    for diagnostic in selected_diagnostics:
        if diagnostic.code == "TSL-CATALOG-MALFORMED-SAFETY":
            action = _missing_safety_fields_action(
                diagnostic, safety_fields, expected, text
            )
            if (
                action is not None
                and action.edit is not None
                and (action.edit.range.start, action.edit.range.end)
                not in occupied_edits
            ):
                occupied_edits.add((action.edit.range.start, action.edit.range.end))
                actions.append(action)
                continue
        guide_url = _diagnostic_guide(diagnostic)
        if guide_url is not None:
            actions.append(
                AuthoringAction(
                    title=_guide_title(diagnostic),
                    kind="help",
                    diagnostic_identity=diagnostic_identity(diagnostic),
                    expected_document=expected,
                    diagnostic=diagnostic,
                    guide_url=guide_url,
                )
            )

    unique = {
        (
            action.kind,
            action.title,
            action.diagnostic_identity,
            action.edit.range.start if action.edit is not None else -1,
            action.edit.range.end if action.edit is not None else -1,
        ): action
        for action in actions
    }
    return tuple(unique[key] for key in sorted(unique))


def validated_edit(
    action: AuthoringAction,
    *,
    path: Path,
    text: str,
    version: int | None,
) -> AuthoringEdit | None:
    """Reject an edit if its document version, digest, or original text is stale."""

    edit = action.edit
    expected = action.expected_document
    if (
        edit is None
        or path.resolve() != expected.path
        or version != expected.version
        or _digest(text) != expected.digest
        or edit.range.start < 0
        or edit.range.end < edit.range.start
        or edit.range.end > len(text)
        or text[edit.range.start : edit.range.end] != edit.expected_text
    ):
        return None
    return edit


def diagnostic_identity(diagnostic: Diagnostic) -> str:
    span = diagnostic.span
    location = (
        ""
        if span is None
        else (
            f"{span.path.resolve().as_posix()}:{span.line}:{span.column}:"
            f"{span.end_line}:{span.end_column}"
        )
    )
    value = f"{diagnostic.code}\0{diagnostic.message}\0{location}"
    return sha256(value.encode("utf-8")).hexdigest()


def _missing_safety_fields_action(
    diagnostic: Diagnostic,
    fields: tuple[ParsedTslField, ...],
    expected: ExpectedDocument,
    text: str,
) -> AuthoringAction | None:
    span = diagnostic.span
    if span is None or "must contain safety fields" not in diagnostic.message:
        return None
    field = next(
        (
            item
            for item in fields
            if not item.children and source_span(item.source) == span
        ),
        None,
    )
    if field is None:
        return None
    start = _offset(text, span.line, span.column)
    end = start + len(field.source.text)
    indent = " " * (field.source.column - 1)
    child_indent = f"{indent}  "
    variant = "variant" in diagnostic.message
    lines = [
        f"{indent}safety:",
        f"{child_indent}internal_unsafe false",
    ]
    if not variant:
        lines.append(f"{child_indent}caller_unsafe false")
    lines.append(f"{child_indent}reasons []")
    return AuthoringAction(
        title="Add required safety fields",
        kind="quickfix",
        diagnostic_identity=diagnostic_identity(diagnostic),
        expected_document=expected,
        edit=AuthoringEdit(
            range=AuthoringTextRange(start, end),
            replacement="\n".join(lines),
            expected_text=text[start:end],
        ),
        diagnostic=diagnostic,
        preferred=True,
    )


def _safety_fields(
    parsed: OuterTslParseResult,
    path: Path,
) -> tuple[ParsedTslField, ...]:
    fields: list[ParsedTslField] = []
    for document in parsed.documents:
        if document.path.resolve() != path:
            continue
        for primitive in document.primitives:
            for entry in primitive.impl_entries:
                _append_safety_fields(fields, entry)
    return tuple(fields)


def _append_safety_fields(
    result: list[ParsedTslField],
    entry: ParsedImplementationSelectorEntry,
) -> None:
    result.extend(field for field in entry.fields if field.key.text == "safety")
    for variant in entry.variants:
        result.extend(field for field in variant.fields if field.key.text == "safety")
    for child in entry.children:
        _append_safety_fields(result, child)


def _diagnostic_guide(diagnostic: Diagnostic) -> str | None:
    if _is_extension_diagnostic(diagnostic):
        return _EXTENSION_GUIDE
    if any(
        term in diagnostic.code
        for term in (
            "ATTRIBUTE",
            "BENCHMARK",
            "IMPLEMENTATION",
            "PARAM-TYPES",
            "SAFETY",
            "SIGNATURE",
            "TEST",
            "VARIANT",
        )
    ):
        return _PRIMITIVE_GUIDE
    if diagnostic.code.startswith(("TSL-CATALOG-", "TSL-OUTER-")):
        return _EDITOR_GUIDE
    return None


def _guide_title(diagnostic: Diagnostic) -> str:
    if _is_extension_diagnostic(diagnostic):
        return "Open extension authoring guide"
    if diagnostic.code.startswith("TSL-CATALOG-TEST-"):
        return "Open primitive test authoring guide"
    if "SAFETY" in diagnostic.code:
        return "Open primitive safety authoring guide"
    return "Open TSL authoring guide"


def _is_extension_diagnostic(diagnostic: Diagnostic) -> bool:
    return any(term in diagnostic.code for term in _EXTENSION_DIAGNOSTIC_TERMS)


def _metadata_identity(subject: str, edit: TextEdit) -> str:
    value = (
        f"TSL-AUDIT-SAFETY\0{subject}\0{edit.path.resolve().as_posix()}\0"
        f"{edit.start}\0{edit.end}\0{edit.replacement}"
    )
    return sha256(value.encode("utf-8")).hexdigest()


def _span_intersects_range(
    text: str,
    span: SourceSpan,
    range_: AuthoringTextRange,
) -> bool:
    start = _offset(text, span.line, span.column)
    end = _offset(text, span.end_line, span.end_column)
    return start <= range_.end and range_.start <= end


def _offset(text: str, line: int, column: int) -> int:
    if line <= 1:
        return min(max(column - 1, 0), len(text))
    offset = 0
    for _ in range(line - 1):
        newline = text.find("\n", offset)
        if newline < 0:
            return len(text)
        offset = newline + 1
    return min(offset + max(column - 1, 0), len(text))


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


__all__ = (
    "ActionKind",
    "AuthoringAction",
    "AuthoringEdit",
    "ExpectedDocument",
    "authoring_actions",
    "diagnostic_identity",
    "validated_edit",
)
