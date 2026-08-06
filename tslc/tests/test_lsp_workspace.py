"""Editor workspace state and index-only LSP feature tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from tslc.catalog.selector_paths import selector_head_extensions
from tslc.diagnostics import SourceSpan
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS
from tslc.lsp.features import (
    completions,
    definition_locations,
    document_symbols,
    hover,
    lsp_diagnostic,
    reference_locations,
    semantic_tokens,
)
from tslc.lsp.implementation_preview import implementation_preview_sites
from tslc.lsp.positions import (
    offset_position,
    position_offset,
    source_position,
    span_to_range,
)
from tslc.lsp.primitive_explorer import PrimitiveExplorerCache, primitive_explorer
from tslc.lsp.server import (
    _check_and_publish,
    _publish,
    _ServerState,
    _snapshot_document_version,
    _workspace_with_index,
)
from tslc.lsp.specialization_context import specialization_context
from tslc.lsp.workspace import AuthoringWorkspace, WorkspaceSnapshot
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


_COMPLETION_PATH = Path("tslctmp/lsp-completion.tsl").resolve()


def test_index_requests_wait_for_a_completed_initial_check() -> None:
    async def exercise() -> None:
        state = _ServerState()
        workspace = SimpleNamespace(
            latest=WorkspaceSnapshot(0, None, None, (), (), {})
        )
        state.workspace = cast(AuthoringWorkspace, workspace)

        request = asyncio.create_task(_workspace_with_index(state))
        await asyncio.sleep(0)
        assert not request.done()

        state.initial_check_complete.set()
        assert await request is workspace

    asyncio.run(exercise())


def test_completed_check_releases_index_requests_without_an_index() -> None:
    state = _ServerState()
    workspace = SimpleNamespace(
        latest=WorkspaceSnapshot(0, None, None, (), (), {})
    )
    state.workspace = cast(AuthoringWorkspace, workspace)
    snapshot = WorkspaceSnapshot(0, None, None, (), (), {})

    _publish(cast(LanguageServer, object()), state, snapshot)

    assert state.initial_check_complete.is_set()


def test_failed_initial_check_releases_requests_and_reports() -> None:
    async def exercise() -> None:
        state = _ServerState()

        def raising_check(generation: int) -> WorkspaceSnapshot | None:
            del generation
            raise RuntimeError("boom")

        workspace = SimpleNamespace(
            latest=WorkspaceSnapshot(0, None, None, (), (), {}),
            generation=1,
            check=raising_check,
        )
        state.workspace = cast(AuthoringWorkspace, workspace)
        logged: list[str] = []
        shown: list[str] = []
        server = SimpleNamespace(
            window_log_message=lambda params: logged.append(params.message),
            window_show_message=lambda params: shown.append(params.message),
        )

        request = asyncio.create_task(_workspace_with_index(state))
        await asyncio.sleep(0)
        assert not request.done()

        await _check_and_publish(
            cast(LanguageServer, server), state, 1, debounce=False
        )

        assert state.initial_check_complete.is_set()
        assert await request is workspace
        assert any("boom" in message for message in logged)
        assert shown

    asyncio.run(exercise())


def test_utf16_position_round_trip() -> None:
    text = "alpha 😀 value\n"
    span = SourceSpan(Path("unicode.tsl"), 1, 7, 1, 8)

    range_ = span_to_range(span, text)

    assert range_.start.character == 6
    assert range_.end.character == 8
    assert source_position(text, range_.end) == (1, 8)
    assert offset_position(text, 7) == range_.end
    assert position_offset(text, range_.end) == 7


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
    assert malformed.parsed is not None
    retained = next(
        document
        for document in malformed.parsed.documents
        if document.path.resolve() == path.resolve()
    )
    assert retained.declarations
    assert workspace.cache.last_reparsed == (path.resolve(),)
    # Failed checks retain the last successful index; no new fragment is published.

    fixed_generation = workspace.change(path, original, 3)
    fixed = workspace.check(fixed_generation)
    assert fixed is not None
    assert fixed.diagnostics == ()
    assert workspace.cache.last_reparsed == (path.resolve(),)
    assert workspace.cache.index_cache.last_reindexed == (path.resolve(),)


def test_code_lens_projection_requires_the_current_checked_document_version(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    initial = workspace.check()
    assert initial is not None
    path = next(iter(sorted(data_root.rglob("*.tsl"))))
    original = path.read_text(encoding="utf-8")

    workspace.open(path, original, 1)
    assert _snapshot_document_version(workspace, initial, path) is None

    checked = workspace.check()
    assert checked is not None
    assert _snapshot_document_version(workspace, checked, path) == 1

    workspace.change(path, f"{original}\n", 2)
    assert _snapshot_document_version(workspace, checked, path) is None


def test_initial_invalid_overlay_seeds_last_valid_parsed_context(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    path = next(iter(sorted(data_root.rglob("*.tsl"))))
    original = path.read_text(encoding="utf-8")

    generation = workspace.open(path, original + "\nprim<v:=\n", 1)
    snapshot = workspace.check(generation)

    assert snapshot is not None
    assert snapshot.diagnostics
    assert snapshot.catalog is not None
    assert snapshot.parsed is not None
    retained = next(
        document
        for document in snapshot.parsed.documents
        if document.path.resolve() == path.resolve()
    )
    assert retained.declarations


def test_specialization_context_uses_cursor_scope_and_selector_slots(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"
    lines = path.read_text(encoding="utf-8").splitlines()

    sse_line = lines.index("    sse:")
    exact_line = next(
        index
        for index, line in enumerate(lines[sse_line + 1 :], sse_line + 2)
        if 'tsil "complete(intrin<add, build>(left, right));"' in line
    )
    exact = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=exact_line,
        column=lines[exact_line - 1].index("complete") + 1,
    )

    assert exact.primitive == "add"
    assert exact.extension == "sse"
    assert exact.type_tag == "f32"
    assert any(
        slot.extension == "sse" and slot.type_tag == "f32"
        for slot in exact.slots
    )

    group_line = 84
    grouped = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=group_line,
        column=15,
    )

    assert grouped.primitive == "add"
    assert grouped.extension == "avx512"
    assert grouped.type_tag is None
    assert grouped.contextual_types == (
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    )


def test_implementation_preview_sites_are_physical_promoted_bodies(
    data_root: Path,
    monkeypatch,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"

    def unexpected_selection(*args, **kwargs):
        raise AssertionError("CodeLens discovery triggered profile selection")

    monkeypatch.setattr(Selector, "select_profile", unexpected_selection)
    sites = implementation_preview_sites(snapshot.catalog, snapshot.parsed, path)

    expected_selectors = {
        implementation.selector_source
        for primitive in snapshot.catalog.primitives
        for implementation in primitive.implementations
        if implementation.selector_source is not None
        and implementation.selector_source.path.resolve() == path.resolve()
    }
    assert {site.selector for site in sites} == expected_selectors
    assert len(sites) == len(expected_selectors)
    assert list(sites) == sorted(
        sites,
        key=lambda site: (
            site.anchor.line,
            site.anchor.column,
            site.selector.line,
            site.selector.column,
        ),
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert all(
        lines[site.anchor.line - 1][site.anchor.column - 1 :].startswith(
            "implementation"
        )
        for site in sites
    )


def test_implementation_context_only_offers_slots_where_that_body_wins(
    data_root: Path,
    monkeypatch,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    path = data_root / "primitives" / "arithmetic" / "select.tsl"
    lines = path.read_text(encoding="utf-8").splitlines()
    extension_group_line = next(
        line
        for line, text in enumerate(lines, 1)
        if text.strip() == (
            "[scalar, generic, clang_v128, oneapi_fpga, avx512, avx2_vl, "
            "avx2, sse_vl, sse, neon, sve]:"
        )
    )
    implementation_line = next(
        line
        for line, text in enumerate(lines, 1)
        if line > extension_group_line and text.strip() == "arith:"
    )
    body_line = next(
        line
        for line, text in enumerate(lines, 1)
        if line > implementation_line and text.strip() == "complete("
    )

    def unexpected_lowering(*args, **kwargs):
        raise AssertionError("specialization context triggered concrete lowering")

    monkeypatch.setattr(Lowerer, "lower", unexpected_lowering)
    context = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=body_line,
        column=lines[body_line - 1].index("complete") + 1,
    )

    assert context.primitive == "max"
    assert context.implementation_source is not None
    assert context.implementation_source.line == implementation_line
    assert context.slots
    assert any(
        slot.profile == "avx2"
        and slot.extension == "generic"
        and slot.type_tag == "si8"
        for slot in context.slots
    )
    assert not any(
        slot.extension == "clang_v128" and slot.type_tag == "si8"
        for slot in context.slots
    )


def test_implementation_context_distinguishes_profile_from_rendered_extension(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    path = data_root / "primitives" / "mask" / "special.tsl"
    lines = path.read_text(encoding="utf-8").splitlines()
    primitive_line = next(
        line
        for line, text in enumerate(lines, 1)
        if text.startswith("prim<") and " extract_imask(" in text
    )
    type_selector_line = next(
        line
        for line, text in enumerate(lines, 1)
        if line > primitive_line and text == "      ?i16:"
    )
    implementation_line = next(
        line
        for line, text in enumerate(lines, 1)
        if line > type_selector_line and text.strip() == "implementation:"
    )

    context = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=implementation_line,
        column=lines[implementation_line - 1].index("implementation") + 1,
    )

    assert context.primitive == "extract_imask"
    assert context.contextual_types == ("si16", "ui16")
    assert {
        slot.extension
        for slot in context.slots
        if slot.profile == "sve"
        and slot.extension in context.contextual_extensions
        and slot.type_tag in context.contextual_types
    } == {"clang_v128"}


def test_primitive_explorer_projects_file_slots_counts_and_dependencies(
    data_root: Path,
    monkeypatch,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    assert snapshot.index is not None
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"

    def unexpected_lowering(*args, **kwargs):
        raise AssertionError("the explorer triggered concrete lowering")

    monkeypatch.setattr(Lowerer, "lower", unexpected_lowering)

    cache = PrimitiveExplorerCache()
    explorer = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        path=path,
        selected_primitive="add",
        cache=cache,
    )

    names = {primitive.name for primitive in explorer.primitives}
    assert "add" in names
    assert "load" not in names
    add = next(item for item in explorer.primitives if item.name == "add")
    assert 0 < add.available_slots < add.total_slots
    assert add.calls
    assert "mov" in add.calls
    assert "mul" in add.called_by
    assert all(span.path.resolve() == path.resolve() for span in add.definitions)

    avx2_si32 = next(
        slot
        for slot in explorer.slots
        if slot.extension == "avx2" and slot.type_tag == "si32"
    )
    assert avx2_si32.available is True
    assert "broader" in avx2_si32.origins
    assert avx2_si32.implementations
    assert all(item.source.path.is_absolute() for item in avx2_si32.implementations)

    avx512_si32 = next(
        slot
        for slot in explorer.slots
        if slot.extension == "avx512" and slot.type_tag == "si32"
    )
    assert avx512_si32.available is False
    assert avx512_si32.status == "not-selected"
    assert avx512_si32.implementations
    assert "does not select it" in (avx512_si32.detail or "")

    rust = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="rust",
        path=path,
        selected_primitive="add",
        cache=PrimitiveExplorerCache(),
    )
    clang_si8 = next(
        slot
        for slot in rust.slots
        if slot.extension == "clang_v128" and slot.type_tag == "si8"
    )
    assert clang_si8.status == "backend-unsupported"
    assert clang_si8.implementations

    corpus = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        selected_primitive="div",
        cache=PrimitiveExplorerCache(),
    )
    allocate = next(item for item in corpus.primitives if item.name == "allocate")
    assert (allocate.available_slots, allocate.total_slots) == (1, 1)
    assert any(slot.status == "missing" for slot in corpus.slots)

    def unexpected_selection(*args, **kwargs):
        raise AssertionError("a selected primitive caused the explorer matrix to rebuild")

    monkeypatch.setattr(Selector, "select_profile", unexpected_selection)
    cached = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        path=path,
        selected_primitive="sub",
        cache=cache,
    )
    assert cached.selected_primitive == "sub"
    assert cached.slots


def test_primitive_explorer_carries_selector_rejection_reasons(
    data_root: Path,
) -> None:
    """A body on the slot's extension chain for the slot's type, dropped only
    by a selector rule (unsatisfied `requires`), must surface the selector's
    own rejection reason — not a generic missing-implementation message."""

    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    assert snapshot.index is not None

    explorer = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        selected_primitive="add",
    )
    avx512_si32 = next(
        slot
        for slot in explorer.slots
        if slot.extension == "avx512" and slot.type_tag == "si32"
    )
    assert avx512_si32.status == "not-selected"
    assert avx512_si32.implementations
    detail = avx512_si32.detail or ""
    assert (
        "requires [avx512f] not satisfied by profile 'avx2' (missing: avx512f)"
        in detail
    )
    assert "No implementation is authored" not in detail


def test_specialization_context_extensions_agree_with_selector_path_projection(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    path = data_root / "primitives" / "arithmetic" / "fundamental.tsl"
    lines = path.read_text(encoding="utf-8").splitlines()
    head = "[avx512, avx2_vl, sse_vl]"
    head_line = next(
        index for index, line in enumerate(lines, 1) if line.strip() == f"{head}:"
    )

    context = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=head_line + 1,
        column=lines[head_line].index("?i?") + 1,
    )

    assert context.primitive == "add"
    assert context.contextual_extensions == tuple(
        sorted(
            snapshot.catalog.extensions[name].isa_name
            for name in selector_head_extensions(head)
        )
    )


def test_primitive_explorer_keeps_authored_candidates_and_splits_resolved_callables(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    assert snapshot.index is not None

    default = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        backend="cpp",
        selected_primitive="max",
        preferred_profiles=workspace.config.preferred_profiles,
    )
    assert default.mode == "authored"
    assert default.profile == ""
    assert {"sse", "avx2", "avx512"} <= {
        slot.extension for slot in default.slots
    }

    avx512_slot = next(
        slot
        for slot in default.slots
        if slot.extension == "avx512" and slot.type_tag == "si32"
    )
    assert avx512_slot.status == "authored"
    assert avx512_slot.available is True

    max_slot = next(
        slot
        for slot in default.slots
        if slot.extension == "clang_v128" and slot.type_tag == "si8"
    )
    assert len(max_slot.implementations) == 2
    max_implementation = next(
        implementation
        for implementation in max_slot.implementations
        if implementation.type_group == "?i?"
    )
    assert max_implementation.primitive == "max"
    assert max_implementation.signature == "v:=(v,v)"
    assert max_implementation.parameters == ("vec_a", "vec_b")
    assert max_implementation.source.path.name == "select.tsl"

    hmax = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        selected_primitive="hmax",
    )
    hmax_slots = tuple(
        slot
        for slot in hmax.slots
        if slot.extension == "clang_v128" and slot.type_tag == "si8"
    )
    assert {
        (slot.signature, slot.parameters)
        for slot in hmax_slots
    } == {
        ("s:=v", ("vec",)),
        ("s:=(m,v)", ("mask", "vec")),
    }
    assert all(len(slot.implementations) == 1 for slot in hmax_slots)
    assert all(
        slot.implementations[0].signature == slot.signature for slot in hmax_slots
    )

    add = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        selected_primitive="add",
    )
    add_slots = tuple(
        slot
        for slot in add.slots
        if slot.extension == "clang_v128" and slot.type_tag == "si8"
    )
    assert {
        (slot.signature, slot.attributes) for slot in add_slots
    } == {
        ("v:=(v,v)", ()),
        ("v:=(m,v,v)", (("mask", "zero"),)),
        ("v:=(m,v,v)", (("mask", "pass_through"),)),
    }
    assert all(slot.status == "selected" for slot in add_slots)
    assert all(len(slot.implementations) == 1 for slot in add_slots)

    resolved = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        backend="cpp",
        preferred_profiles=workspace.config.preferred_profiles,
    )
    assert resolved.profile == "avx2"


def test_primitive_explorer_keeps_representation_targets_as_distinct_slots(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    assert snapshot.index is not None

    authored = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        backend="cpp",
        selected_primitive="insert_imask",
    )
    assert {
        slot.target.dimension
        for slot in authored.slots
        if slot.target is not None
    } == {"base", "extension"}

    resolved = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="avx2",
        backend="cpp",
        selected_primitive="insert_imask",
    )
    avx2_si64 = tuple(
        slot
        for slot in resolved.slots
        if slot.extension == "avx2"
        and slot.type_tag == "si64"
        and slot.status == "selected"
    )
    targets = {
        (slot.target.dimension, slot.target.value)
        for slot in avx2_si64
        if slot.target is not None
    }
    assert {("base", "ui8"), ("extension", "avx512")} <= targets
    assert all(len(slot.implementations) == 1 for slot in avx2_si64)


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
    completion_snapshot = _snapshot_with_parsed_source(
        snapshot,
        completion_text + 'l"\n',
    )
    completed = completions(
        completion_snapshot,
        _COMPLETION_PATH,
        completion_text,
        types.Position(line=5, character=len('          tsil "cal')),
    )
    all_regions = _completion_labels(
        snapshot,
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      si32:\n        implementation:\n          tsil "',
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      si32:\n        implementation:\n          tsil "complete(value);"\n',
    )
    outer = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n  bri",
        'prim<v:=v> x(v):\n  brief_description "x"\n',
    )
    extensions = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n  impls:\n    sca",
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
    )
    type_groups = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      ari",
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
    )
    implementation_fields = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        ",
        "prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        requires []\n",
    )
    primitive_call_text = (
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        implementation:\n'
        '          tsil "complete(call<primitive=ad'
    )
    primitive_call_baseline = (
        'prim<v:=v> x(v):\n  impls:\n    scalar:\n      arith:\n        implementation:\n'
        '          tsil "complete(call<primitive=add>(v));"\n'
    )
    primitive_call_completion = completions(
        _snapshot_with_parsed_source(snapshot, primitive_call_baseline),
        _COMPLETION_PATH,
        primitive_call_text,
        types.Position(
            line=5,
            character=len('          tsil "complete(call<primitive=ad'),
        ),
    )
    primitive_calls = {item.label for item in primitive_call_completion.items}
    query_continuations = _completion_labels(
        snapshot,
        "prim<v:=v> x(data):\n  impls:\n    scalar:\n      arith:\n"
        '        implementation:\n          tsil "complete(base::s',
        "prim<v:=v> x(data):\n  impls:\n    scalar:\n      arith:\n"
        '        implementation:\n          tsil "complete(base::in);"\n',
    )
    primitive_scope = _completion_labels(
        snapshot,
        "prim<v:=v> x(data):\n  impls:\n    scalar:\n      arith:\n"
        '        implementation:\n          tsil "complete(da',
        "prim<v:=v> x(data):\n  impls:\n    scalar:\n      arith:\n"
        '        implementation:\n          tsil "complete(data);"\n',
    )
    required_features = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n"
        "  impls:\n"
        "    avx512:\n"
        "      arith:\n"
        "        requires [avx512_",
        "prim<v:=v> x(v):\n"
        "  impls:\n"
        "    avx512:\n"
        "      arith:\n"
        "        requires [avx512f]\n",
    )
    nested_required_features = _completion_labels(
        snapshot,
        "prim<v:=v> x(v):\n"
        "  impls:\n"
        "    avx512:\n"
        "      arith:\n"
        "        requires:\n"
        "          avx512:\n"
        "            dword [avx512_",
        "prim<v:=v> x(v):\n"
        "  impls:\n"
        "    avx512:\n"
        "      arith:\n"
        "        requires:\n"
        "          avx512:\n"
        "            dword [avx512f]\n",
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
    assert {
        "implementation",
        "safety",
        "unroll_variants",
        "variants",
    } <= implementation_fields
    assert "si32" not in implementation_fields
    assert "add" in primitive_calls
    assert "signed_of" in query_continuations
    assert "select" not in query_continuations
    assert "data" in primitive_scope
    add_completion = next(
        item for item in primitive_call_completion.items if item.label == "add"
    )
    assert add_completion.text_edit is not None
    assert add_completion.text_edit.range.start.character == len(
        '          tsil "complete(call<primitive='
    )
    assert add_completion.text_edit.range.end.character == len(
        '          tsil "complete(call<primitive=ad'
    )
    assert "avx512_fp16" in required_features
    assert "avx512_fp16" in nested_required_features
    assert "arith" not in required_features
    assert "si32" not in required_features


def test_overload_live_features_project_the_latest_catalog_index(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.index is not None

    occurrence = next(
        item
        for occurrences in snapshot.index.occurrences_by_path.values()
        for item in occurrences
        if item.kind == "overload-value"
        and item.name == "uniform"
        and not item.definition
    )
    text = workspace.document_text(occurrence.span.path)
    assert text is not None
    position = span_to_range(occurrence.span, text).start

    definitions = definition_locations(
        snapshot.index,
        occurrence.span.path,
        text,
        position,
        workspace,
    )
    references = reference_locations(
        snapshot.index,
        occurrence.span.path,
        text,
        position,
        workspace,
        include_declaration=True,
    )
    hovered = hover(
        snapshot.index,
        occurrence.span.path,
        text,
        position,
    )

    assert len(definitions) == 1
    assert definitions[0].uri.endswith("/tsldata/detail/overload_axes.tsl")
    assert len(references) > len(definitions)
    assert hovered is not None
    assert isinstance(hovered.contents, types.MarkupContent)
    assert "count_distribution=uniform" in hovered.contents.value
    assert "Accepted operand kinds" in hovered.contents.value

    baseline = (
        "prim<v:=(v,s)> probe(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
    )
    assert _completion_labels(
        snapshot,
        "prim<v:=(v,s)> probe(data, count):\n  overload:\n    axis pay",
        baseline,
    ) == {"payload_extent"}
    assert _completion_labels(
        snapshot,
        (
            "prim<v:=(v,s)> probe(data, count):\n"
            "  overload:\n"
            "    axis count_distribution\n"
            "    value "
        ),
        baseline,
    ) == {"per_lane", "uniform"}


def test_overload_diagnostics_retain_related_locations_and_last_valid_index(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    initial = workspace.check()
    assert initial is not None
    assert initial.index is not None
    path = data_root / "primitives" / "bitwise" / "shifts.tsl"
    original = path.read_text(encoding="utf-8")

    invalid_pair = original.replace("    value uniform", "    value vector", 1)
    invalid = workspace.check(workspace.open(path, invalid_pair, 1))
    assert invalid is not None
    assert invalid.index is initial.index
    assert any(
        item.code == "TSL-CATALOG-OVERLOAD-INVALID-VALUE"
        for item in invalid.diagnostics
    )

    duplicate_source = original.replace(
        "    value uniform\n",
        "    value uniform\n    primary true\n",
        1,
    )
    duplicate = workspace.check(workspace.change(path, duplicate_source, 2))
    assert duplicate is not None
    assert duplicate.index is initial.index
    diagnostic = next(
        item
        for item in duplicate.diagnostics
        if item.code == "TSL-CATALOG-OVERLOAD-DUPLICATE-PRIMARY"
    )
    assert diagnostic.related
    converted = lsp_diagnostic(diagnostic, workspace)
    assert converted.related_information
    assert all(
        item.location.uri.endswith("/tsldata/primitives/bitwise/shifts.tsl")
        for item in converted.related_information
    )


def _completion_labels(snapshot, text: str, baseline: str) -> set[str]:
    lines = text.splitlines()
    parsed_snapshot = _snapshot_with_parsed_source(snapshot, baseline)
    completed = completions(
        parsed_snapshot,
        _COMPLETION_PATH,
        text,
        types.Position(line=len(lines) - 1, character=len(lines[-1])),
    )
    return {item.label for item in completed.items}


def _snapshot_with_parsed_source(
    snapshot: WorkspaceSnapshot, text: str
) -> WorkspaceSnapshot:
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_COMPLETION_PATH, text, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return replace(snapshot, parsed=parsed)


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


def test_unsaved_unknown_implementation_metadata_is_diagnosed(
    data_root: Path,
) -> None:
    path = data_root / "primitives" / "load_store" / "array.tsl"
    original = path.read_text(encoding="utf-8")
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    changed = original.replace(
        "        implementation:\n",
        '        hello: "test"\n        implementation:\n',
        1,
    )

    snapshot = workspace.check(workspace.open(path, changed, 1))

    assert snapshot is not None
    assert any(
        item.code == "TSL-CATALOG-UNKNOWN-FIELD" and "'hello'" in item.message
        for item in snapshot.diagnostics
    )
    assert snapshot.index is not None
    call_line = next(
        line
        for line, content in enumerate(changed.splitlines())
        if "call<primitive=store[Vec]" in content
    )
    call_character = changed.splitlines()[call_line].index("store")

    definitions = definition_locations(
        snapshot.index,
        path,
        changed,
        types.Position(line=call_line, character=call_character),
        workspace,
    )

    assert definitions
    assert all(location.uri.endswith("/store.tsl") for location in definitions)


def test_compiler_capability_frontier_is_shared_by_context_and_explorer(
    data_root: Path,
) -> None:
    workspace = AuthoringWorkspace.from_root(data_root.parent)
    snapshot = workspace.check()
    assert snapshot is not None
    assert snapshot.catalog is not None
    assert snapshot.index is not None
    path = data_root / "primitives" / "bitwise" / "bit_counts.tsl"
    lines = path.read_text(encoding="utf-8").splitlines()
    builtin_line = next(
        line
        for line, content in enumerate(lines, 1)
        if "__builtin_elementwise_clzg" in content
    )

    context = specialization_context(
        snapshot.catalog,
        snapshot.parsed,
        workspace.config.profiles,
        backend="cpp",
        path=path,
        line=builtin_line,
        column=lines[builtin_line - 1].index("__builtin_elementwise_clzg") + 1,
    )

    assert context.primitive == "lzc"
    assert any(
        slot.profile == "sse2"
        and slot.extension == "clang_v128"
        and slot.type_tag == "ui32"
        for slot in context.slots
    )

    explorer = primitive_explorer(
        snapshot.catalog,
        snapshot.index,
        workspace.config.profiles,
        workspace.config.backends,
        mode="resolved",
        profile="sse2",
        backend="cpp",
        path=path,
        selected_primitive="lzc",
    )
    slot = next(
        item
        for item in explorer.slots
        if item.signature == "v:=v"
        and item.attributes == ()
        and item.extension == "clang_v128"
        and item.type_tag == "ui32"
    )

    assert slot.status == "selected"
    assert len(slot.implementations) == 2
