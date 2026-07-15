"""Authoring-depth acceptance tests for the typed catalog/source index."""

from __future__ import annotations

from pathlib import Path

from tslc.catalog.model import Catalog
from tslc.catalog_index import CatalogIndex, IndexedDocumentSymbol, build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.lsp.features import document_symbols, semantic_tokens
from tslc.sources import SourceDocument
from tslc.syntax.ast import OuterTslParseResult
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
types:
  arith {types [si32]}
extension ext:
  extension_name "ext"
extension ext:
  extension_name "ext-duplicate"
prim<v:=v> sample(data):
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
