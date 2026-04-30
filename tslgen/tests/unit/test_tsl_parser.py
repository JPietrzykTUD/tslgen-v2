from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.io.sources import SourceDocument, SourceKind, SourceSet, load_sources
from tslgen.syntax.ast import ParsedDocument, SyntaxNode
from tslgen.syntax.parser import parse_document, parse_sources


def source_document(text: str, *, path: str = "fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def first_node(document: ParsedDocument, kind: str) -> SyntaxNode:
    matches = document.root.find_all(kind)
    if not matches:
        raise AssertionError(f"expected syntax node {kind!r}")
    return matches[0]


class TslParserTests(unittest.TestCase):
    def test_parses_representative_detail_files(self) -> None:
        for path in (
            Path("tsldata/detail/types.tsl"),
            Path("tsldata/detail/lane_sets.tsl"),
            Path("tsldata/detail/templates.tsl"),
        ):
            source = source_document(
                path.read_text(encoding="utf-8"),
                path=path.as_posix(),
            )

            result = parse_document(source)

            self.assertTrue(result.is_ok, result.diagnostics)
            self.assertEqual(result.unwrap().root.kind, "start")

    def test_parses_primitive_declaration_attributes_and_multiline_tsil(self) -> None:
        text = '''prim<v:=(v,v)>[mask=zero] add(left, right):
  implementation:
    tsil """
      emit_return(left + right);
    """
'''
        result = parse_document(source_document(text))

        self.assertTrue(result.is_ok, result.diagnostics)
        document = result.unwrap()
        primitive = first_node(document, "primitive_block")
        self.assertEqual(primitive.span.location.line, 1)
        self.assertEqual(primitive.span.location.column, 1)
        self.assertEqual(primitive.span.location.end_line, 6)
        self.assertEqual(first_node(document, "SIGNATURE").text, "v:=(v,v)")
        self.assertEqual([node.text for node in document.root.find_all("NAME")[:4]], ["mask", "zero", "add", "left"])
        multiline = first_node(document, "MULTILINE_STRING")
        self.assertIn("emit_return(left + right);", multiline.text or "")
        self.assertEqual(multiline.span.location.line, 3)

    def test_parses_inline_and_multiline_maps_key_lists_and_parameterized_attributes(self) -> None:
        text = '''translation cpp:
  [generic, oneAPIfpga, oneAPIfpgaRTL]:
    rules {
      [generic, oneAPIfpga<128>] {types [si8, ui8]},
      scalar "i8",
    }
prim<v:=s...>[arg_count(values)=return_vector_length] set(values):
  tests []
'''
        result = parse_document(source_document(text))

        self.assertTrue(result.is_ok, result.diagnostics)
        document = result.unwrap()
        self.assertEqual(len(document.root.find_all("key_list")), 2)
        self.assertEqual(len(document.root.find_all("key_list_parameterized_item")), 1)
        self.assertEqual(len(document.root.find_all("attr_key")), 1)
        self.assertEqual(len(document.root.find_all("map_inline")), 2)
        self.assertGreaterEqual(len(document.root.find_all("pair")), 3)

    def test_reports_syntax_error_with_file_line_and_column(self) -> None:
        result = parse_document(source_document("types:\n  si8 {types [si8]\n", path="bad.tsl"))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-PARSE-SYNTAX",
            severity="error",
            path="bad.tsl",
            line=2,
            column=19,
        )
        self.assertIn("expected one of", diagnostic.message)

    def test_reports_invalid_indentation(self) -> None:
        result = parse_document(source_document("types:\nsi8 {types [si8]}\n", path="bad-indent.tsl"))

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-PARSE-SYNTAX",
            severity="error",
            path="bad-indent.tsl",
            line=2,
            column=1,
        )

    def test_reports_unterminated_string(self) -> None:
        result = parse_document(source_document('description "missing close\n', path="bad-string.tsl"))

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-PARSE-SYNTAX",
            severity="error",
            path="bad-string.tsl",
            line=1,
            column=13,
        )

    def test_parse_sources_orders_results_by_logical_path(self) -> None:
        first = source_document("types:\n  si8 {types [si8]}\n", path="b.tsl")
        second = source_document("flags:\n  avx3f avx512f\n", path="a.tsl")

        parsed = parse_sources(SourceSet((first, second)))

        self.assertTrue(parsed.is_ok, parsed.diagnostics)
        self.assertEqual(
            [document.logical_path.as_posix() for document in parsed.unwrap()],
            ["a.tsl", "b.tsl"],
        )

    def test_all_current_tsldata_files_parse(self) -> None:
        sources = load_sources(SourceConfig.standard_library(Path("tsldata"))).unwrap()

        result = parse_sources(sources)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(len(result.unwrap().documents), 41)


if __name__ == "__main__":
    unittest.main()
