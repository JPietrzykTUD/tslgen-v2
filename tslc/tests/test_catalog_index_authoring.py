"""Authoring-depth acceptance tests for the typed catalog/source index."""

from __future__ import annotations

from pathlib import Path

from tslc.authoring_completion import authoring_completions
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.catalog.validation import validate_catalog
from tslc.catalog_index import CatalogIndex, IndexedDocumentSymbol, build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.lsp.features import document_symbols, semantic_tokens
from tslc.sources import SourceDocument
from tslc.syntax.ast import OuterTslParseResult
from tslc.syntax.authoring import authoring_cursor_context
from tslc.syntax.parser import TslParser


_PATH = Path("tslctmp/catalog-index-authoring.tsl").resolve()
_SOURCE = '''description "demo"
flags:
  feat {normalized "feat"}
lane_set lanes_i32:
  lanes [4]
  types [si32]
translation demo:
  call "{name}({args})"
language demo:
  s32 {type "int"}
template unary:
  description "demo"
target_families:
  known_extension_families [demo]
overload_axes:
  count_distribution:
    values:
      uniform:
        operand_kinds [s, sImm]
      per_lane:
        operand_kinds [v]
types:
  arith {types [si32]}
extension ext:
  extension_name "ext"
extension ext:
  extension_name "ext-duplicate"
prim<v:=v> sample(data):
  overload:
    axis count_distribution
    value uniform
    primary true
  generic_params:
    N {kind int}
  return_type:
    base: ToBase
  tests:
    - {name "basic", tags [basic], type "si32", case {inputs [[1]], expected [1]}}
  impls:
    [ext, missing]:
      arith:
        ToBase:
          arith:
            implementation:
              tsil "raw_function(base::in); complete(value(vector::length)); complete(call<primitive=sample[Vec], attrs[aligned=false]>(data));"
            variants:
              fallback:
                tsil "complete(data);"
    ext:
      arith:
        requires []
'''


def _index(catalog: Catalog, source: str = _SOURCE) -> tuple[CatalogIndex, OuterTslParseResult]:
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(_PATH, source, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    return build_catalog_index(catalog, parsed), parsed


def _flatten(
    symbols: tuple[IndexedDocumentSymbol, ...],
) -> tuple[IndexedDocumentSymbol, ...]:
    return tuple(
        symbol
        for root in symbols
        for symbol in (root, *_flatten(root.children))
    )


def _span_text(source: str, line: int, column: int, end_column: int) -> str:
    return source.splitlines()[line - 1][column - 1 : end_column - 1]


def _indexed_token_snapshot(
    index: CatalogIndex, source: str
) -> tuple[tuple[int, int, str, str], ...]:
    return tuple(
        (
            token.span.line,
            token.span.column,
            token.kind,
            _span_text(
                source,
                token.span.line,
                token.span.column,
                token.span.end_column,
            ),
        )
        for token in index.semantic_tokens_by_path[_PATH]
    )


def test_document_symbol_hierarchy_covers_outer_and_nested_declarations(
    catalog: Catalog,
) -> None:
    index, _ = _index(catalog)
    roots = index.document_symbols_by_path[_PATH]
    flattened = _flatten(roots)

    assert {(symbol.name, symbol.detail) for symbol in roots} >= {
        ("description", "description"),
        ("flags", "flags"),
        ("lanes_i32", "lane_set"),
        ("demo", "translation"),
        ("demo", "language"),
        ("unary", "template"),
        ("target_families", "field"),
        ("overload_axes", "field"),
        ("types", "types"),
        ("ext", "extension"),
        ("sample", "prim<v:=v>"),
    }
    assert {(symbol.kind, symbol.name) for symbol in flattened} >= {
        ("parameter", "data"),
        ("generic-parameter", "N"),
        ("target-axis", "ToBase"),
        ("implementation", "[ext, missing]"),
        ("implementation", "arith"),
        ("implementation", "ToBase"),
        ("variant", "fallback"),
        ("test-case", "basic"),
        ("type-group", "arith"),
        ("field", "count_distribution"),
        ("field", "uniform"),
        ("field", "per_lane"),
    }
    assert all(
        (symbol.span.line, symbol.span.column)
        <= (symbol.selection_span.line, symbol.selection_span.column)
        < (symbol.span.end_line, symbol.span.end_column)
        for symbol in flattened
    )

    projected = document_symbols(index, _PATH, _SOURCE)
    sample = next(symbol for symbol in projected if symbol.name == "sample")
    assert sample.children is not None
    assert {child.name for child in sample.children} >= {
        "data",
        "N",
        "ToBase",
        "[ext, missing]",
        "basic",
    }


def test_selector_navigation_indexes_list_items_and_local_target_axes(
    catalog: Catalog,
) -> None:
    index, _ = _index(catalog)
    occurrences = index.occurrences_by_path[_PATH]
    ext = next(
        item
        for item in occurrences
        if item.kind == "extension" and item.name == "ext" and not item.definition
    )
    single_ext = next(
        item
        for item in occurrences
        if item.kind == "extension"
        and item.name == "ext"
        and not item.definition
        and item.span.line != ext.span.line
    )
    missing = next(
        item
        for item in occurrences
        if item.kind == "extension" and item.name == "missing"
    )
    target = next(
        item
        for item in occurrences
        if item.kind == "target-axis" and not item.definition
    )

    assert _span_text(
        _SOURCE, ext.span.line, ext.span.column, ext.span.end_column
    ) == "ext"
    assert len(index.definitions(ext)) == 2
    assert len(index.definitions(single_ext)) == 2
    assert index.definitions(missing) == ()
    assert len(index.definitions(target)) == 1
    assert len(index.references(target, include_declaration=True)) == 2
    assert _span_text(
        _SOURCE,
        index.definitions(target)[0].line,
        index.definitions(target)[0].column,
        index.definitions(target)[0].end_column,
    ) == "ToBase"
    assert "[ext, missing]" not in index.extension_references
    assert len(index.type_group_references["arith"]) == 3


def test_overload_navigation_hover_and_references_share_registry_owner(
    catalog: Catalog,
) -> None:
    index, _ = _index(catalog)
    occurrences = index.occurrences_by_path[_PATH]
    axis_definition = next(
        item
        for item in occurrences
        if item.kind == "overload-axis" and item.definition
    )
    axis_reference = next(
        item
        for item in occurrences
        if item.kind == "overload-axis" and not item.definition
    )
    value_definition = next(
        item
        for item in occurrences
        if item.kind == "overload-value"
        and item.name == "uniform"
        and item.definition
    )
    value_reference = next(
        item
        for item in occurrences
        if item.kind == "overload-value"
        and item.name == "uniform"
        and not item.definition
    )

    assert index.definitions(axis_reference) == (axis_definition.span,)
    assert index.definitions(value_reference) == (value_definition.span,)
    assert index.references(axis_definition, include_declaration=True) == (
        axis_definition.span,
        axis_reference.span,
    )
    assert index.references(value_definition, include_declaration=True) == (
        value_definition.span,
        value_reference.span,
    )
    assert index.hover(axis_reference) == (
        "**Overload axis** `count_distribution`\n\n"
        "**Values:** `per_lane`, `uniform`"
    )
    assert index.hover(value_reference) == (
        "**Overload value** `count_distribution=uniform`\n\n"
        "**Accepted operand kinds:** `s`, `sImm`"
    )


def test_synthetic_overload_axis_projects_one_owner_through_all_editor_facts() -> None:
    path = Path("tslctmp/synthetic-overload-authoring.tsl").resolve()
    source = (
        "overload_axes:\n"
        "  synthetic_axis:\n"
        "    values:\n"
        "      alpha:\n"
        "        operand_kinds [s]\n"
        "      beta:\n"
        "        operand_kinds [v]\n"
        "prim<v:=(v,s)> synthetic(data, payload):\n"
        "  overload:\n"
        "    axis synthetic_axis\n"
        "    value alpha\n"
        "    primary true\n"
        "prim<v:=(v,v)> synthetic(data, payload):\n"
        "  overload:\n"
        "    axis synthetic_axis\n"
        "    value beta\n"
    )
    parsed = TslParser(load_default_tsl_grammar()).parse(
        (SourceDocument(path, source, "", "tsl"),)
    )
    assert parsed.diagnostics == ()
    built = CatalogBuilder().build(parsed)
    assert built.catalog is not None
    catalog = built.catalog
    assert not any(
        "OVERLOAD" in item.code
        for item in validate_catalog(catalog, parsed, required_backends=())
    )
    index = build_catalog_index(catalog, parsed)

    registry_axis = catalog.overload_registry.axes["synthetic_axis"]
    assert tuple(registry_axis.values) == ("alpha", "beta")
    assert set(index.overload_axis_definitions) == set(catalog.overload_registry.axes)
    assert {
        value
        for axis, value in index.overload_value_definitions
        if axis == "synthetic_axis"
    } == set(registry_axis.values)

    axis_edit = source.split("    axis synthetic_axis", 1)[0] + "    axis synth"
    axis_context = authoring_cursor_context(parsed, path, axis_edit, len(axis_edit))
    assert {item.label for item in authoring_completions(axis_context, catalog)} == {
        "synthetic_axis"
    }
    value_edit = source.split("    value alpha", 1)[0] + "    value "
    value_context = authoring_cursor_context(parsed, path, value_edit, len(value_edit))
    assert {item.label for item in authoring_completions(value_context, catalog)} == {
        "alpha",
        "beta",
    }

    occurrences = index.occurrences_by_path[path]
    for value_name, value_spec in registry_axis.values.items():
        definition = next(
            item
            for item in occurrences
            if item.kind == "overload-value"
            and item.name == value_name
            and item.definition
        )
        references = tuple(
            item
            for item in occurrences
            if item.kind == "overload-value"
            and item.name == value_name
            and not item.definition
        )
        assert references
        assert index.definitions(references[0]) == (definition.span,)
        hover_text = index.hover(definition)
        assert hover_text is not None
        assert "synthetic_axis" in hover_text
        assert all(kind in hover_text for kind in value_spec.operand_kinds)
        token = next(
            item
            for item in index.semantic_tokens_by_path[path]
            if item.span == definition.span
        )
        assert token.kind == "enumMember"

    symbols = _flatten(index.document_symbols_by_path[path])
    assert {(item.name, item.detail) for item in symbols} >= {
        ("synthetic_axis", "overload axis"),
        ("alpha", "overload value"),
        ("beta", "overload value"),
    }


def test_semantic_tokens_cover_typed_sites_but_not_raw_target_text(
    catalog: Catalog,
) -> None:
    index, _ = _index(catalog)
    snapshot = _indexed_token_snapshot(index, _SOURCE)
    values = {(kind, text) for _, _, kind, text in snapshot}

    assert {
        ("keyword", "prim"),
        ("property", "implementation"),
        ("parameter", "data"),
        ("typeParameter", "N"),
        ("typeParameter", "ToBase"),
        ("class", "ext"),
        ("type", "arith"),
        ("enumMember", "int"),
        ("namespace", "vector"),
        ("property", "primitive"),
        ("property", "attrs"),
        ("property", "aligned"),
        ("enumMember", "false"),
        ("class", "count_distribution"),
        ("enumMember", "uniform"),
        ("enumMember", "per_lane"),
    } <= values

    body_line = next(
        line_number
        for line_number, line in enumerate(_SOURCE.splitlines(), start=1)
        if "raw_function" in line
    )
    raw_base_column = _SOURCE.splitlines()[body_line - 1].index("base::in") + 1
    assert not any(
        line == body_line and column == raw_base_column and text == "base"
        for line, column, _, text in snapshot
    )
    assert semantic_tokens(index, _PATH, _SOURCE).data


def test_semantic_tokens_retain_partial_declaration_facts(catalog: Catalog) -> None:
    source = '''prim<v:=v> partial(data):
  brief_description "in progress"
  impls:
    ext:
      arith:
        requires []
'''
    index, _ = _index(catalog, source)

    assert _indexed_token_snapshot(index, source) == (
        (1, 1, "keyword", "prim"),
        (1, 12, "function", "partial"),
        (1, 20, "parameter", "data"),
        (2, 3, "property", "brief_description"),
        (3, 3, "property", "impls"),
        (4, 5, "class", "ext"),
        (5, 7, "type", "arith"),
        (6, 9, "property", "requires"),
    )


def test_selector_where_levels_are_constraints_not_type_group_references(
    catalog: Catalog,
) -> None:
    """One selector-path projection classifies every level: list heads split
    into per-extension spans, target levels stay on the target axis, and a
    `where` constraint level is never indexed as a type group."""

    source = '''description "demo"
types:
  arith {types [si32]}
extension sse:
  extension_name "sse"
extension avx2:
  extension_name "avx2"
prim<v:=v> narrow(data):
  return_type:
    base: ToBase
  impls:
    [sse, avx2]:
      arith:
        ToBase:
          where:
            family same_as
            width smaller_than
            implementation:
              tsil "complete(data);"
          arith:
            implementation:
              tsil "complete(data);"
'''
    index, _ = _index(catalog, source)

    head_line = next(
        line_number
        for line_number, line in enumerate(source.splitlines(), start=1)
        if line.strip() == "[sse, avx2]:"
    )
    head_refs = {
        (occurrence.name, occurrence.span.line, occurrence.span.column)
        for occurrence in index.occurrences_by_path[_PATH]
        if occurrence.kind == "extension"
        and not occurrence.definition
        and occurrence.span.line == head_line
    }
    head_text = source.splitlines()[head_line - 1]
    assert head_refs == {
        ("sse", head_line, head_text.index("sse") + 1),
        ("avx2", head_line, head_text.index("avx2") + 1),
    }
    assert "[sse, avx2]" not in index.extension_references

    assert "where" not in index.type_group_references
    assert not any(
        occurrence.name == "where"
        for occurrence in index.occurrences_by_path[_PATH]
    )

    target_axis_refs = [
        occurrence
        for occurrence in index.occurrences_by_path[_PATH]
        if occurrence.kind == "target-axis" and not occurrence.definition
    ]
    assert [occurrence.name for occurrence in target_axis_refs] == ["ToBase"]
    assert "ToBase" not in index.type_group_references

    # The source type-group level and the concrete-target level both
    # reference `arith`; the `where` constraint level contributes nothing.
    assert len(index.type_group_references["arith"]) == 2


def test_selector_path_projection_classifies_levels_and_splits_targets() -> None:
    from tslc.catalog.selector_paths import (
        classify_selector_path,
        selector_head_extensions,
        split_target_selector,
    )

    where_path = ("[sse, avx2]", "arith", "ToBase", "where")
    levels = classify_selector_path(where_path, "ToBase")
    assert [level.kind for level in levels] == [
        "extensions",
        "source-type-group",
        "target-axis",
        "where-constraint",
    ]
    assert levels[0].names == ("sse", "avx2")
    assert levels[3].names == ()

    assert selector_head_extensions("sse") == ("sse",)
    assert split_target_selector(where_path, "ToBase") == ("arith", None)
    assert split_target_selector(
        ("[sse, avx2]", "arith", "ToBase", "f?"), "ToBase"
    ) == ("arith", "f?")
    assert split_target_selector(("sse", "?i?"), None) == ("?i?", None)
    assert split_target_selector(("sse", "?i?"), "ToBase") == ("?i?", None)
