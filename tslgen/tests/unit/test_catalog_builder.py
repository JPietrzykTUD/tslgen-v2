from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, SourceSet, load_sources
from tslgen.syntax.ast import ParsedDocumentSet, SyntaxNode
from tslgen.syntax.parser import parse_document, parse_sources


def source_document(text: str, *, path: str = "fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_paths(*paths: str) -> Catalog:
    sources = load_sources(
        SourceConfig(
            explicit_paths=tuple(Path(path) for path in paths),
            include_standard_library=False,
        )
    )
    if not sources.is_ok:
        raise AssertionError(sources.diagnostics)
    parsed = parse_sources(sources.unwrap())
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    catalog = build_catalog(parsed.unwrap())
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


class CatalogBuilderTests(unittest.TestCase):
    def test_builds_type_groups_from_detail_types(self) -> None:
        catalog = catalog_from_paths("tsldata/detail/types.tsl")

        arith = catalog.type_groups_by_name["arith"]

        self.assertEqual(arith.members[:4], ("si8", "si16", "si32", "si64"))
        self.assertIn("f64", arith.members)
        self.assertIsInstance(arith.fields, FrozenMap)
        self.assertEqual(arith.fields["types"], arith.members)

    def test_builds_lane_sets_from_detail_lane_sets(self) -> None:
        catalog = catalog_from_paths("tsldata/detail/lane_sets.tsl")

        lanes_i32 = catalog.lane_sets_by_name["lanes_i32"]

        self.assertEqual(lanes_i32.lanes, (4, 8, 16))
        self.assertEqual(lanes_i32.type_names, ("si32", "ui32"))

    def test_builds_extensions_and_templates_from_detail_files(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
        )

        avx2 = catalog.extensions_by_name["avx2"]
        binary = catalog.templates_by_name["binary"]

        self.assertEqual(avx2.vendor, "intel")
        self.assertEqual(avx2.vector_bits, 256)
        self.assertEqual(avx2.fields["lscpu_flags"], ("avx2",))
        self.assertIsInstance(avx2.fields["rust"], FrozenMap)
        self.assertEqual(binary.shape, "(vector, vector) -> vector")
        self.assertEqual(binary.optional_fields[:2], ("intrinsic", "implementation"))

    def test_builds_representative_primitive_declarations(self) -> None:
        catalog = catalog_from_paths("tsldata/primitives/arithmetic/fundamental.tsl")

        add_declarations = catalog.primitive_declarations("add")
        unmasked_add = next(
            declaration
            for declaration in add_declarations
            if declaration.signature == "v:=(v,v)"
        )
        masked_add = next(
            declaration
            for declaration in add_declarations
            if declaration.attributes and declaration.attributes[0].value == "zero"
        )

        self.assertGreaterEqual(len(add_declarations), 3)
        self.assertEqual(unmasked_add.signature, "v:=(v,v)")
        self.assertEqual([parameter.name for parameter in unmasked_add.parameters], ["left", "right"])
        self.assertEqual(masked_add.attributes[0].key, "mask")
        self.assertIn("tests", unmasked_add.fields)
        self.assertIn("impls", unmasked_add.fields)
        self.assertIsInstance(unmasked_add.fields["tests"], tuple)
        self.assertIsInstance(unmasked_add.fields["impls"], FrozenMap)

    def test_preserves_extra_fields_as_constrained_catalog_values(self) -> None:
        catalog = build_catalog(
            parse_text(
                '''extension custom:
  vendor "lab"
  vector_bits 128
  extra:
    nested [1, true, token]
    attrs [mode=fast]
''',
                path="custom-extension.tsl",
            )
        )

        self.assertTrue(catalog.is_ok, catalog.diagnostics)
        custom = catalog.unwrap().extensions_by_name["custom"]
        extra = custom.fields["extra"]

        self.assertIsInstance(extra, FrozenMap)
        assert isinstance(extra, FrozenMap)
        self.assertEqual(extra["nested"], (1, True, "token"))
        self.assertEqual(extra["attrs"], FrozenMap({"mode": "fast"}))

    def test_preserves_duplicate_nested_extra_fields_without_semantic_merging(self) -> None:
        catalog = build_catalog(
            parse_text(
                '''extension custom:
  vendor "lab"
  extra:
    backend "first"
    backend "second"
''',
                path="nested-duplicate.tsl",
            )
        )

        self.assertTrue(catalog.is_ok, catalog.diagnostics)
        extra = catalog.unwrap().extensions_by_name["custom"].fields["extra"]

        self.assertIsInstance(extra, FrozenMap)
        assert isinstance(extra, FrozenMap)
        self.assertEqual(extra["backend"], ("first", "second"))

    def test_catalog_ordering_is_deterministic(self) -> None:
        second = source_document("lane_set z:\n  lanes [1]\n  types [si8]\n", path="z.tsl")
        first = source_document("lane_set a:\n  lanes [2]\n  types [si16]\n", path="a.tsl")
        parsed = parse_sources(SourceSet((second, first)))
        self.assertTrue(parsed.is_ok, parsed.diagnostics)

        catalog = build_catalog(parsed.unwrap())

        self.assertTrue(catalog.is_ok, catalog.diagnostics)
        self.assertEqual([lane_set.name for lane_set in catalog.unwrap().lane_sets], ["a", "z"])

    def test_reports_duplicate_catalog_entries(self) -> None:
        parsed = parse_text(
            """types:
  si8 {types [si8]}
  si8 {types [ui8]}
""",
            path="duplicate-types.tsl",
        )

        catalog = build_catalog(parsed)

        self.assertFalse(catalog.is_ok)
        self.assertEqual(len(catalog.diagnostics), 1)
        assert_diagnostic(
            self,
            catalog.diagnostics[0],
            code="TSL-CAT-DUPLICATE",
            severity="error",
            path="duplicate-types.tsl",
            line=3,
            column=3,
        )

    def test_catalog_layer_does_not_contain_syntax_nodes(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/primitives/arithmetic/fundamental.tsl",
        )

        self.assertFalse(_contains_syntax_node(catalog))


def _contains_syntax_node(value: object) -> bool:
    if isinstance(value, SyntaxNode):
        return True
    if isinstance(value, FrozenMap):
        return any(_contains_syntax_node(key) or _contains_syntax_node(item) for key, item in value.items())
    if isinstance(value, tuple):
        return any(_contains_syntax_node(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_contains_syntax_node(getattr(value, field.name)) for field in fields(value))
    return False


if __name__ == "__main__":
    unittest.main()
