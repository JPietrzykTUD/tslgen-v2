"""Audit and apply source metadata suggestions for primitive implementations.

This is a corpus-maintenance tool, not part of the compiler pipeline. It makes
typed suggestions for source-owned ``safety:`` and ``requires`` metadata and
can apply only suggestions with a narrow source edit. It deliberately avoids
rewriting broad scoped ``requires:`` maps.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Literal, TextIO, cast

from tslc.authoring import check_documents
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.model import ImplementationSafety
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, format_diagnostic, has_errors
from tslc.pipeline import GenerationRequest, generate
from tslc.sources import SourceDocument, SourceLoader, expand_source_paths
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)

SuggestionKind = Literal["safety", "requires"]
Confidence = Literal["high", "medium", "low"]
_DEFAULT_TYPES = DEFAULT_SCALAR_TYPE_TAGS
_DEFAULT_PROFILES = ("scalar", "sse2", "avx", "avx2", "skylake")


@dataclass(frozen=True, slots=True)
class TextEdit:
    path: Path
    start: int
    end: int
    replacement: str


@dataclass(frozen=True, slots=True)
class MetadataSuggestion:
    kind: SuggestionKind
    confidence: Confidence
    path: Path
    line: int
    subject: str
    reason: str
    before: str
    after: str
    edit: TextEdit | None = None
    scope: SourceSpan | None = None

    @property
    def applicable(self) -> bool:
        return self.edit is not None


@dataclass(frozen=True, slots=True)
class MetadataAuditResult:
    suggestions: tuple[MetadataSuggestion, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _AuditInputs:
    """One validated source snapshot: raw documents plus their parse."""

    source_paths: tuple[Path, ...]
    documents: Mapping[Path, SourceDocument]
    parsed: OuterTslParseResult


@dataclass(frozen=True, slots=True)
class _EntryRef:
    primitive: ParsedPrimitiveDeclaration
    entry: ParsedImplementationSelectorEntry
    selector_path: tuple[str, ...]


def audit_metadata(
    source_paths: Iterable[Path | str],
    *,
    checks: Iterable[SuggestionKind] = ("safety", "requires"),
    machine_profiles_path: Path | str | None = None,
    profiles: Iterable[str] = _DEFAULT_PROFILES,
    primitives: Iterable[str] | None = None,
    type_tags: Iterable[str] = _DEFAULT_TYPES,
    backends: Iterable[str] = registered_backend_ids(),
) -> MetadataAuditResult:
    """Return source metadata suggestions without writing files."""

    selected_checks = frozenset(checks)
    backend_ids = tuple(backends)
    inputs, diagnostics = _load_inputs(source_paths, backend_ids)
    if inputs is None:
        return MetadataAuditResult(suggestions=(), diagnostics=diagnostics)

    suggestions: list[MetadataSuggestion] = []
    if "safety" in selected_checks:
        suggestions.extend(_safety_suggestions(inputs))
    if "requires" in selected_checks and machine_profiles_path is not None:
        requires_suggestions, requires_diagnostics = _requires_suggestions(
            inputs,
            machine_profiles_path=Path(machine_profiles_path),
            profiles=tuple(profiles),
            primitives=tuple(primitives) if primitives is not None else None,
            type_tags=tuple(type_tags),
            backends=backend_ids,
        )
        suggestions.extend(requires_suggestions)
        diagnostics = (*diagnostics, *requires_diagnostics)
    return MetadataAuditResult(
        suggestions=tuple(sorted(suggestions, key=_suggestion_sort_key)),
        diagnostics=diagnostics,
    )


def apply_suggestions(
    suggestions: Iterable[MetadataSuggestion],
    *,
    kinds: Iterable[SuggestionKind] = ("safety", "requires"),
) -> int:
    """Apply every applicable suggestion of the requested kinds."""

    selected_kinds = frozenset(kinds)
    edits_by_path: dict[Path, list[TextEdit]] = defaultdict(list)
    for suggestion in suggestions:
        if suggestion.kind not in selected_kinds or suggestion.edit is None:
            continue
        edits_by_path[suggestion.edit.path].append(suggestion.edit)

    written = 0
    for path, edits in sorted(edits_by_path.items(), key=lambda item: item[0].as_posix()):
        text = path.read_text(encoding="utf-8")
        text = _apply_edits(text, edits)
        path.write_text(text, encoding="utf-8")
        written += len(edits)
    return written


def interactive_apply(
    suggestions: Sequence[MetadataSuggestion],
    *,
    input_func: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> int:
    """Prompt for each applicable suggestion and apply accepted edits."""

    accepted: list[MetadataSuggestion] = []
    for index, suggestion in enumerate(suggestions, start=1):
        print(_format_suggestion(index, suggestion), file=output)
        if suggestion.edit is None:
            print("  no automatic edit is available for this suggestion\n", file=output)
            continue
        while True:
            answer = input_func("[a]pply [s]kip [d]iff [q]uit: ").strip().lower()
            if answer in {"a", "apply"}:
                accepted.append(suggestion)
                print("  accepted\n", file=output)
                break
            if answer in {"s", "skip", ""}:
                print("  skipped\n", file=output)
                break
            if answer in {"d", "diff"}:
                print(f"--- before\n{suggestion.before}", file=output)
                print(f"+++ after\n{suggestion.after}\n", file=output)
                continue
            if answer in {"q", "quit"}:
                return apply_suggestions(accepted)
            print("  expected a, s, d, or q", file=output)
    return apply_suggestions(accepted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc audit metadata",
        description="Audit and optionally apply TSL safety/requires metadata suggestions.",
    )
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument(
        "--checks",
        default="safety,requires",
        help="comma-separated checks: safety,requires",
    )
    parser.add_argument(
        "--machine-profiles",
        default="supplementary/buildsystem/machine_profiles.json",
        help="machine profile JSON used for requires propagation",
    )
    parser.add_argument("--profiles", default="scalar,sse2,avx,avx2,skylake")
    parser.add_argument("--primitives", default=None, help="comma-separated primitive names")
    parser.add_argument("--types", default=",".join(_DEFAULT_TYPES))
    parser.add_argument("--backends", default="cpp,rust")
    parser.add_argument(
        "--apply",
        choices=("safety", "requires", "all"),
        default=None,
        help="automatically apply applicable suggestions of this kind",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="prompt before applying each applicable suggestion",
    )
    args = parser.parse_args(argv)

    checks = tuple(_split_csv(args.checks))
    invalid = sorted(set(checks) - {"safety", "requires"})
    if invalid:
        print(f"[error] unknown check(s): {', '.join(invalid)}", file=sys.stderr)
        return 2

    result = audit_metadata(
        [Path(path) for path in args.sources],
        checks=cast(tuple[SuggestionKind, ...], checks),
        machine_profiles_path=Path(args.machine_profiles),
        profiles=tuple(_split_csv(args.profiles)),
        primitives=tuple(_split_csv(args.primitives)) if args.primitives else None,
        type_tags=tuple(_split_csv(args.types)),
        backends=tuple(_split_csv(args.backends)),
    )
    for diagnostic in result.diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if has_errors(result.diagnostics):
        return 1

    for index, suggestion in enumerate(result.suggestions, start=1):
        print(_format_suggestion(index, suggestion))
    print(
        f"{len(result.suggestions)} suggestion(s), "
        f"{sum(1 for s in result.suggestions if s.applicable)} applicable"
    )

    if args.interactive:
        written = interactive_apply(result.suggestions)
        print(f"applied {written} edit(s)")
        return 0
    if args.apply is not None:
        kinds: tuple[SuggestionKind, ...] = (
            ("safety", "requires")
            if args.apply == "all"
            else (cast(SuggestionKind, args.apply),)
        )
        written = apply_suggestions(result.suggestions, kinds=kinds)
        print(f"applied {written} edit(s)")
        return 0
    return 1 if result.suggestions else 0


def _load_inputs(
    source_paths: Iterable[Path | str],
    backends: tuple[str, ...],
) -> tuple[_AuditInputs | None, tuple[Diagnostic, ...]]:
    """Load and validate one corpus snapshot through the authoring boundary."""

    expanded = expand_source_paths(source_paths)
    load = SourceLoader().load(expanded)
    if has_errors(load.diagnostics):
        return None, tuple(load.diagnostics)

    checked = check_documents(load.documents, required_backends=backends)
    diagnostics = (*load.diagnostics, *checked.diagnostics)
    if checked.catalog is None or checked.parsed is None or has_errors(diagnostics):
        return None, diagnostics
    return (
        _AuditInputs(
            source_paths=expanded,
            documents={document.path: document for document in load.documents},
            parsed=checked.parsed,
        ),
        diagnostics,
    )


def _safety_suggestions(inputs: _AuditInputs) -> tuple[MetadataSuggestion, ...]:
    return safety_metadata_suggestions(inputs.parsed, inputs.documents)


def safety_metadata_suggestions(
    parsed: OuterTslParseResult,
    documents: Mapping[Path, SourceDocument],
    *,
    path: Path | None = None,
) -> tuple[MetadataSuggestion, ...]:
    """Return the audit's exact direct-safety edits from an in-memory parse."""

    suggestions: list[MetadataSuggestion] = []
    selected_path = path.resolve() if path is not None else None
    for ref in _implementation_entries(parsed):
        primitive = ref.primitive
        entry = ref.entry
        if selected_path is not None and entry.source.path.resolve() != selected_path:
            continue
        if not entry.body_envelopes:
            continue
        required = _direct_safety_facts(primitive, entry)
        local = _entry_safety(entry)
        if _safety_contains(local, required):
            continue
        after = local.merge(required)
        edit = _safety_edit(documents, entry, after)
        suggestions.append(
            MetadataSuggestion(
                kind="safety",
                confidence="high",
                path=entry.source.path,
                line=entry.source.line,
                subject=f"{primitive.name} {'/'.join(ref.selector_path)}",
                reason="direct body/signature facts require safety metadata",
                before=_render_safety_block(_child_indent(entry), local).rstrip(),
                after=_render_safety_block(_child_indent(entry), after).rstrip(),
                edit=edit,
                scope=_entry_scope(entry),
            )
        )
    return tuple(suggestions)


def _direct_safety_facts(
    primitive: ParsedPrimitiveDeclaration,
    entry: ParsedImplementationSelectorEntry,
) -> ImplementationSafety:
    safety = ImplementationSafety()
    body_text = "\n".join(envelope.payload_text for envelope in entry.body_envelopes)
    if "intrin<" in body_text:
        safety = safety.merge(
            ImplementationSafety(internal_unsafe=True, reasons=frozenset({"intrinsic"}))
        )
    if "mem<" in body_text:
        safety = safety.merge(
            ImplementationSafety(internal_unsafe=True, reasons=frozenset({"raw_memory"}))
        )
    shape = parse_signature(primitive.signature)
    if shape is not None and DEFAULT_SUPPORT_POLICY.requires_unsafe_frame(shape):
        safety = safety.merge(
            ImplementationSafety(
                internal_unsafe=True,
                caller_unsafe=True,
                reasons=frozenset({"raw_pointer"}),
            )
        )
    return safety


def _requires_suggestions(
    inputs: _AuditInputs,
    *,
    machine_profiles_path: Path,
    profiles: tuple[str, ...],
    primitives: tuple[str, ...] | None,
    type_tags: tuple[str, ...],
    backends: tuple[str, ...],
) -> tuple[tuple[MetadataSuggestion, ...], tuple[Diagnostic, ...]]:
    """Derive requires suggestions from the pipeline's own closure facts.

    The non-rendering pipeline runs selection, lowering, dependency closure,
    pruning, and feature propagation; each emitted trace slot carries both the
    declared selection features and the propagated requirement set, so the
    delta is exactly what generation would add transitively.
    """

    result = generate(
        GenerationRequest(
            source_paths=inputs.source_paths,
            machine_profiles_path=machine_profiles_path,
            primitives=primitives if primitives else None,
            profiles=profiles,
            type_tags=type_tags,
            backends=backends,
            render_artifacts=False,
            collect_lowering_trace=True,
        )
    )
    errors = tuple(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.severity == "error"
    )
    trace = result.lowering_trace
    if errors or trace is None:
        return (), errors

    entry_index = _entry_index(inputs.parsed)
    missing_by_entry: dict[tuple[str, Path, int, int], set[str]] = defaultdict(set)
    reasons_by_entry: dict[tuple[str, Path, int, int], set[str]] = defaultdict(set)
    for slot in trace.slots:
        if not slot.emitted:
            continue
        spec = slot.specialization
        missing = spec.required_features - slot.selection_required_features
        if not missing:
            continue
        selector_source = slot.selector_source
        if selector_source is None:
            continue
        key = (
            spec.source_primitive_name,
            selector_source.path,
            selector_source.line,
            selector_source.column,
        )
        if key not in entry_index:
            continue
        missing_by_entry[key].update(missing)
        reasons_by_entry[key].add(
            f"{slot.profile}/{slot.backend}/{spec.type_tag}"
        )

    suggestions: list[MetadataSuggestion] = []
    for key, missing_features in sorted(
        missing_by_entry.items(), key=lambda item: item[0]
    ):
        primitive, _path, _line, _column = key
        ref = entry_index[key]
        entry = ref.entry
        local_flags, field = _local_requires_flags(entry)
        after_flags = frozenset(local_flags | frozenset(missing_features))
        edit = _requires_edit(inputs.documents, entry, after_flags, field)
        suggestions.append(
            MetadataSuggestion(
                kind="requires",
                confidence="medium" if edit is not None else "low",
                path=entry.source.path,
                line=entry.source.line,
                subject=f"{primitive} {'/'.join(ref.selector_path)}",
                reason=(
                    "transitive primitive calls require "
                    f"{_format_list(sorted(missing_features))} "
                    f"({', '.join(sorted(reasons_by_entry[key]))})"
                ),
                before=(
                    _render_requires_line(_child_indent(entry), sorted(local_flags)).rstrip()
                    if field is None
                    else field.source.text.rstrip()
                ),
                after=_render_requires_line(_child_indent(entry), sorted(after_flags)).rstrip(),
                edit=edit,
                scope=_entry_scope(entry),
            )
        )
    return tuple(suggestions), ()


def _safety_edit(
    documents: Mapping[Path, SourceDocument],
    entry: ParsedImplementationSelectorEntry,
    safety: ImplementationSafety,
) -> TextEdit | None:
    field = _first_field(entry, "safety")
    rendered = _render_safety_block(_child_indent(entry), safety)
    if field is not None:
        return _replace_field_edit(documents, field, rendered.rstrip())
    anchor = _first_field(entry, "implementation") or (
        entry.fields[0] if entry.fields else None
    )
    if anchor is None:
        return None
    return _insert_before_field_edit(documents, anchor, rendered)


def _requires_edit(
    documents: Mapping[Path, SourceDocument],
    entry: ParsedImplementationSelectorEntry,
    flags: frozenset[str],
    field: ParsedTslField | None,
) -> TextEdit | None:
    rendered = _render_requires_line(_child_indent(entry), sorted(flags))
    if field is not None:
        if not isinstance(field.value, ParsedTslListValue):
            return None
        return _replace_field_edit(documents, field, rendered.rstrip())
    if entry.children:
        return None
    anchor = _first_field(entry, "safety") or _first_field(entry, "implementation")
    if anchor is None:
        return None
    return _insert_before_field_edit(documents, anchor, rendered)


def _replace_field_edit(
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


def _insert_before_field_edit(
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
                reasons=frozenset(_list_text(children.get("reasons"))),
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


def _local_requires_flags(
    entry: ParsedImplementationSelectorEntry,
) -> tuple[frozenset[str], ParsedTslField | None]:
    field = _first_field(entry, "requires")
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return frozenset(), field
    return frozenset(_list_text(field)), field


def _bool_field(field: ParsedTslField | None) -> bool:
    text = _field_text(field)
    return text is not None and text.lower() == "true"


def _list_text(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    return tuple(
        item.text for item in field.value.items if isinstance(item, ParsedTslScalarValue)
    )


def _field_text(field: ParsedTslField | None) -> str | None:
    if field is None or not isinstance(field.value, ParsedTslScalarValue):
        return None
    return field.value.text


def _first_field(
    entry: ParsedImplementationSelectorEntry,
    name: str,
) -> ParsedTslField | None:
    return next((field for field in entry.fields if field.key.text == name), None)


def _implementation_entries(
    parsed: OuterTslParseResult,
) -> tuple[_EntryRef, ...]:
    result: list[_EntryRef] = []
    for document in parsed.documents:
        for primitive in document.primitives:
            result.extend(
                _EntryRef(primitive, entry, path)
                for entry, path in _walk_entries(primitive.impl_entries)
            )
    return tuple(result)


def _walk_entries(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    parent_path: tuple[str, ...] = (),
) -> tuple[tuple[ParsedImplementationSelectorEntry, tuple[str, ...]], ...]:
    result: list[tuple[ParsedImplementationSelectorEntry, tuple[str, ...]]] = []
    for entry in entries:
        path = (*parent_path, entry.selector.text)
        result.append((entry, path))
        result.extend(_walk_entries(entry.children, path))
    return tuple(result)


def _entry_index(
    parsed: OuterTslParseResult,
) -> dict[tuple[str, Path, int, int], _EntryRef]:
    return {
        (
            ref.primitive.name,
            ref.entry.source.path,
            ref.entry.source.line,
            ref.entry.source.column,
        ): ref
        for ref in _implementation_entries(parsed)
    }


def _child_indent(entry: ParsedImplementationSelectorEntry) -> str:
    return " " * (entry.source.column + 1)


def _entry_scope(entry: ParsedImplementationSelectorEntry) -> SourceSpan:
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


def _render_safety_block(indent: str, safety: ImplementationSafety) -> str:
    return (
        f"{indent}safety:\n"
        f"{indent}  internal_unsafe {_bool_text(safety.internal_unsafe)}\n"
        f"{indent}  caller_unsafe {_bool_text(safety.caller_unsafe)}\n"
        f"{indent}  reasons {_format_list(sorted(safety.reasons))}\n"
    )


def _render_requires_line(indent: str, flags: Sequence[str]) -> str:
    return f"{indent}requires {_format_list(flags)}\n"


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


def _apply_edits(text: str, edits: Sequence[TextEdit]) -> str:
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
    last_end = -1
    for edit in ordered:
        if edit.start < last_end:
            raise ValueError(f"overlapping metadata edit for {edit.path}")
        last_end = edit.end
    for edit in reversed(ordered):
        text = text[: edit.start] + edit.replacement + text[edit.end :]
    return text


def _format_suggestion(index: int, suggestion: MetadataSuggestion) -> str:
    auto = "applicable" if suggestion.applicable else "manual"
    return (
        f"{index}. {suggestion.kind} {suggestion.confidence} {auto} "
        f"{suggestion.path}:{suggestion.line}\n"
        f"   {suggestion.subject}\n"
        f"   {suggestion.reason}"
    )


def _suggestion_sort_key(
    suggestion: MetadataSuggestion,
) -> tuple[str, str, int, str, str]:
    return (
        suggestion.path.as_posix(),
        suggestion.kind,
        suggestion.line,
        suggestion.subject,
        suggestion.reason,
    )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
