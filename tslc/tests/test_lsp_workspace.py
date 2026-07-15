"""Editor workspace state and index-only LSP feature tests."""

from __future__ import annotations

from pathlib import Path

from lsprotocol import types

from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS
from tslc.lsp.features import (
    completions,
    definition_locations,
    document_symbols,
    hover,
    reference_locations,
    semantic_tokens,
)
from tslc.lsp.positions import source_position, span_to_range
from tslc.lsp.workspace import AuthoringWorkspace


def test_utf16_position_round_trip() -> None:
    text = "alpha 😀 value\n"
    span = SourceSpan(Path("unicode.tsl"), 1, 7, 1, 8)

    range_ = span_to_range(span, text)

    assert range_.start.character == 6
    assert range_.end.character == 8
    assert source_position(text, range_.end) == (1, 8)


def test_workspace_reuses_unchanged_documents_and_suppresses_stale_results(
    data_root: Path,
) -> None:
    root = data_root.parent
    workspace = AuthoringWorkspace.from_root(root)
    initial = workspace.check()
    assert initial is not None
    assert initial.diagnostics == ()
    assert initial.index is not None
    baseline_index = initial.index

    path = next(iter(sorted(data_root.rglob("*.tsl"))))
    original = path.read_text(encoding="utf-8")
    stale_generation = workspace.open(path, original + "\nprim<\n", 1)
    current_generation = workspace.change(path, original + "\nprim<v:=\n", 2)

    assert workspace.check(stale_generation) is None
    malformed = workspace.check(current_generation)
    assert malformed is not None
    assert malformed.diagnostics
    assert malformed.index is baseline_index
    assert workspace.cache.last_reparsed == (path.resolve(),)
    # Failed checks retain the last successful index; no new fragment is published.

    fixed_generation = workspace.change(path, original, 3)
    fixed = workspace.check(fixed_generation)
    assert fixed is not None
    assert fixed.diagnostics == ()
    assert workspace.cache.last_reparsed == (path.resolve(),)
    assert workspace.cache.index_cache.last_reindexed == (path.resolve(),)


def test_navigation_hover_completion_and_tokens_use_latest_index(
    data_root: Path,
    monkeypatch,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.index is not None
    call_region = next(
        occurrence
        for occurrences in snapshot.index.occurrences_by_path.values()
        for occurrence in occurrences
        if occurrence.kind == "region" and occurrence.name == "call"
    )
    assert snapshot.index.hover(call_region) is not None
    reference = next(
        span
        for spans in snapshot.index.primitive_references.values()
        for span in spans
    )
    text = workspace.document_text(reference.path)
    assert text is not None
    position = span_to_range(reference, text).start

    def unexpected_check(*args, **kwargs):
        raise AssertionError("an index-backed live feature triggered a corpus check")

    monkeypatch.setattr(AuthoringWorkspace, "check", unexpected_check)

    definitions = definition_locations(
        snapshot.index, reference.path, text, position, workspace
    )
    references = reference_locations(
        snapshot.index,
        reference.path,
        text,
        position,
        workspace,
        include_declaration=True,
    )
    hovered = hover(snapshot.index, reference.path, text, position)
    symbols = document_symbols(snapshot.index, reference.path, text)
    tokens = semantic_tokens(snapshot.index, reference.path, text)
    completion_text = 'prim<v:=v> x(v):\n  impls:\n    scalar:\n      si32:\n        implementation:\n          tsil "cal'
    completed = completions(
        snapshot,
        completion_text,
        types.Position(line=5, character=len('          tsil "cal')),
    )
    all_regions = _completion_labels(
        snapshot,
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      si32:\n        implementation:\n          tsil "',
    )
    outer = _completion_labels(snapshot, "prim<v:=v> x(v):\n  bri")
    extensions = _completion_labels(snapshot, "prim<v:=v> x(v):\n  impls:\n    sca")
    type_groups = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      ari",
    )
    primitive_calls = _completion_labels(
        snapshot,
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        implementation:\n          tsil "complete(call<primitive=ad',
    )

    assert definitions
    assert len(references) > len(definitions)
    assert all(location.uri.startswith("file:") for location in references)
    assert hovered is not None
    assert symbols
    assert tokens.data
    assert "call" in {item.label for item in completed.items}
    assert all_regions == TSIL_REGION_KEYWORDS
    assert "brief_description" in outer
    assert "scalar" in extensions
    assert "arith" in type_groups
    assert "add" in primitive_calls


def _completion_labels(snapshot, text: str) -> set[str]:
    lines = text.splitlines()
    completed = completions(
        snapshot,
        text,
        types.Position(line=len(lines) - 1, character=len(lines[-1])),
    )
    return {item.label for item in completed.items}


def test_unsaved_parser_catalog_and_tsil_errors_are_checked(
    data_root: Path,
) -> None:
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"
    original = path.read_text(encoding="utf-8")
    workspace = AuthoringWorkspace.from_root(data_root.parent)

    generation = workspace.open(path, original + "\nprim<v:=\n", 1)
    parsed = workspace.check(generation)
    assert parsed is not None
    assert parsed.diagnostics

    generation = workspace.change(
        path,
        original.replace("brief_description", "brief_descriptino", 1),
        2,
    )
    catalog = workspace.check(generation)
    assert catalog is not None
    assert any(
        item.code == "TSL-CATALOG-UNKNOWN-FIELD" for item in catalog.diagnostics
    )

    generation = workspace.change(
        path,
        original.replace("call<primitive=mov", "call<primitive=>", 1),
        3,
    )
    tsil = workspace.check(generation)
    assert tsil is not None
    assert any(item.code == "TSL-BODY-MALFORMED-REGION" for item in tsil.diagnostics)
