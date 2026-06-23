"""Corpus guard for TSIL statement terminators."""

from __future__ import annotations

from pathlib import Path

from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.sources import SourceLoader
from tslc.syntax.ast import ParsedImplementationSelectorEntry
from tslc.syntax.parser import TslParser


def test_primitive_tsil_statement_regions_have_source_terminators(
    data_root: Path,
) -> None:
    documents = SourceLoader().load_dir(data_root / "primitives")
    assert documents.diagnostics == ()
    parsed = TslParser().parse(documents.documents)
    assert parsed.diagnostics == ()

    missing: list[str] = []
    for text, source in _unique_body_payloads(parsed.documents):
        _collect_missing_statement_terminators(scan(text, source=source), missing)

    assert missing == []


def _unique_body_payloads(documents):
    seen: set[tuple[str, int, int, str]] = set()
    for document in documents:
        for primitive in document.primitives:
            for envelope in primitive.body_envelopes:
                yield from _one_payload(envelope, seen)
            for entry in primitive.impl_entries:
                yield from _entry_payloads(entry, seen)


def _entry_payloads(
    entry: ParsedImplementationSelectorEntry,
    seen: set[tuple[str, int, int, str]],
):
    for envelope in entry.body_envelopes:
        yield from _one_payload(envelope, seen)
    for child in entry.children:
        yield from _entry_payloads(child, seen)


def _one_payload(envelope, seen: set[tuple[str, int, int, str]]):
    source = envelope.payload_source
    key = (source.path.as_posix(), source.line, source.column, envelope.payload_text)
    if key in seen:
        return
    seen.add(key)
    yield envelope.payload_text, source


def _collect_missing_statement_terminators(
    segments: tuple[Segment, ...] | None,
    missing: list[str],
) -> None:
    if segments is None:
        return
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        if _requires_source_terminator(segment) and not segment.has_statement_terminator:
            source = segment.source
            location = f"{source.path}:{source.line}" if source else "<unknown>"
            missing.append(f"{location}: {segment.full_text.strip()}")
        _collect_missing_statement_terminators(segment.body, missing)
        _collect_missing_statement_terminators(segment.block, missing)
        _collect_missing_statement_terminators(segment.else_block, missing)
        if segment.arms is not None:
            for _label, body in segment.arms:
                _collect_missing_statement_terminators(body, missing)


def _requires_source_terminator(region: Region) -> bool:
    selector = region.selector_text.strip()
    if region.keyword in {"var", "let", "emit_return", "io"}:
        return True
    if region.keyword == "mem" and selector in {"copy", "set", "free"}:
        return True
    if region.keyword == "mask" and (selector == "set" or selector.startswith("set:")):
        return True
    return False
