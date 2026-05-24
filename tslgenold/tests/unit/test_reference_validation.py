from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import validate_references


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


def catalog_from_text(text: str, *, path: str = "fixture.tsl") -> Catalog:
    catalog = build_catalog(parse_text(text, path=path))
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


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


def standard_catalog() -> Catalog:
    sources = load_sources(SourceConfig.standard_library(Path("tsldata")))
    if not sources.is_ok:
        raise AssertionError(sources.diagnostics)
    parsed = parse_sources(sources.unwrap())
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    catalog = build_catalog(parsed.unwrap())
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


class ReferenceValidationTests(unittest.TestCase):
    def test_current_tsldata_passes_reference_validation(self) -> None:
        signature_result = validate_catalog(standard_catalog())
        self.assertTrue(signature_result.is_ok, signature_result.diagnostics)

        result = validate_references(signature_result.unwrap())

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertIsNotNone(result.unwrap().validated_catalog)

    def test_reports_unknown_type_group_member_and_lane_set_type(self) -> None:
        catalog = catalog_from_text(
            """types:
  si8:
    types [si8]
  bad_group:
    types [missing_member]
lane_set bad_lane:
  lanes [1, 2]
  types [missing_lane_type]
""",
            path="bad-types.tsl",
        )

        result = validate_references(catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-REF-UNKNOWN-TYPE-GROUP", "TSL-REF-UNKNOWN-TYPE-GROUP"],
        )
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-REF-UNKNOWN-TYPE-GROUP",
            severity="error",
            path="bad-types.tsl",
            line=4,
            column=3,
        )
        assert_diagnostic(
            self,
            result.diagnostics[1],
            code="TSL-REF-UNKNOWN-TYPE-GROUP",
            severity="error",
            path="bad-types.tsl",
            line=6,
            column=1,
        )

    def test_reports_extension_inheritance_errors_in_source_order(self) -> None:
        catalog = catalog_from_text(
            """extension missing_parent:
  inherits "missing_extension"
extension self_parent:
  inherits "self_parent"
extension cycle_a:
  inherits "cycle_b"
extension cycle_b:
  inherits "cycle_a"
""",
            path="bad-extensions.tsl",
        )

        result = validate_references(catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-REF-UNKNOWN-EXTENSION",
                "TSL-REF-EXTENSION-SELF",
                "TSL-REF-EXTENSION-CYCLE",
            ],
        )
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-REF-UNKNOWN-EXTENSION",
            severity="error",
            path="bad-extensions.tsl",
            line=1,
            column=1,
        )
        assert_diagnostic(
            self,
            result.diagnostics[1],
            code="TSL-REF-EXTENSION-SELF",
            severity="error",
            path="bad-extensions.tsl",
            line=3,
            column=1,
        )
        assert_diagnostic(
            self,
            result.diagnostics[2],
            code="TSL-REF-EXTENSION-CYCLE",
            severity="error",
            path="bad-extensions.tsl",
            line=5,
            column=1,
        )

    def test_reports_extension_metadata_reference_errors(self) -> None:
        catalog = catalog_from_text(
            """template known_template:
  required_fields []
  optional_fields []
extension meta_refs:
  rust:
    generation_support ["missing_generation_extension"]
  test_filter:
    exclude_templates ["missing_template"]
""",
            path="bad-extension-metadata.tsl",
        )

        result = validate_references(catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-REF-UNKNOWN-EXTENSION", "TSL-REF-UNKNOWN-TEMPLATE"],
        )
        self.assertIn("generation_support", result.diagnostics[0].message)
        self.assertIn("exclude_templates", result.diagnostics[1].message)

    def test_reports_unknown_primitive_test_and_implementation_references(self) -> None:
        base = catalog_from_paths(
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
        )
        invalid = catalog_from_text(
            """prim<v:=(v,v)> bad_refs(left, right):
  tests:
    - {test_name "bad_refs", extension "missing_test_extension", to_extension "missing_to_extension", type "missing_type", to_type "missing_to_type", lane_set "missing_lane_set", template "missing_template", case {inputs [[1], [2]], expected [3]}}
  impls:
    scalar:
      arith:
        requires:
          [si8, missing_requires_type] [some_flag]
        implementation:
          tsil "emit_return(left);"
    missing_impl_extension:
      missing_impl_type:
        requires:
          missing_requires_type [some_flag]
        implementation:
          tsil "emit_return(left);"
""",
            path="bad-primitive-refs.tsl",
        )
        catalog = Catalog(
            type_groups=base.type_groups,
            lane_sets=base.lane_sets,
            extensions=base.extensions,
            templates=base.templates,
            primitives=invalid.primitives,
        )
        signature_result = validate_catalog(catalog)
        self.assertTrue(signature_result.is_ok, signature_result.diagnostics)

        result = validate_references(signature_result.unwrap())

        self.assertFalse(result.is_ok)
        codes = [diagnostic.code for diagnostic in result.diagnostics]
        self.assertEqual(codes.count("TSL-REF-UNKNOWN-EXTENSION"), 3)
        self.assertEqual(codes.count("TSL-REF-UNKNOWN-TYPE-GROUP"), 4)
        self.assertEqual(codes.count("TSL-REF-UNKNOWN-LANE-SET"), 1)
        self.assertEqual(codes.count("TSL-REF-UNKNOWN-TEMPLATE"), 1)
        for diagnostic in result.diagnostics:
            assert_diagnostic(
                self,
                diagnostic,
                code=diagnostic.code,
                severity="error",
                path="bad-primitive-refs.tsl",
                line=1,
                column=1,
            )


if __name__ == "__main__":
    unittest.main()
