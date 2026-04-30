from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.signatures import parse_signature
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import ValidatedCatalog, validate_catalog


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


def template_for(
    catalog: ValidatedCatalog,
    primitive_name: str,
    signature: str,
    **attributes: object,
) -> str:
    expected_attrs = {key: value for key, value in attributes.items()}
    for primitive in catalog.primitive_declarations(primitive_name):
        actual_attrs = {
            attribute.key: attribute.value for attribute in primitive.declaration.attributes
        }
        if primitive.signature.normalized == signature and actual_attrs == expected_attrs:
            return primitive.template_name
    raise AssertionError(
        f"missing validated primitive {primitive_name} {signature} {expected_attrs}"
    )


class SignatureValidationTests(unittest.TestCase):
    def test_signature_parser_normalizes_whitespace_and_preserves_single_parameter_style(
        self,
    ) -> None:
        binary = parse_signature(" v := ( v , v ) ")
        alloc = parse_signature(" ptr := ( s ) ")
        load = parse_signature(" v := ptr ")

        self.assertTrue(binary.is_ok, binary.diagnostics)
        self.assertTrue(alloc.is_ok, alloc.diagnostics)
        self.assertTrue(load.is_ok, load.diagnostics)
        self.assertEqual(binary.unwrap().normalized, "v:=(v,v)")
        self.assertEqual(alloc.unwrap().normalized, "ptr:=(s)")
        self.assertEqual(load.unwrap().normalized, "v:=ptr")

    def test_signature_parser_reports_unsupported_terms(self) -> None:
        signature = parse_signature("v:=mystery")

        self.assertFalse(signature.is_ok)
        self.assertEqual(len(signature.diagnostics), 1)
        self.assertEqual(signature.diagnostics[0].code, "TSL-SIG-SYNTAX")
        self.assertIn("unsupported signature term", signature.diagnostics[0].message)

    def test_resolves_representative_primitive_signatures_to_templates(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/detail/templates.tsl",
            "tsldata/primitives/arithmetic/fundamental.tsl",
            "tsldata/primitives/conversion/repr_change.tsl",
            "tsldata/primitives/load_store/load.tsl",
            "tsldata/primitives/load_store/construct.tsl",
        )

        result = validate_catalog(catalog)

        self.assertTrue(result.is_ok, result.diagnostics)
        validated = result.unwrap()
        self.assertEqual(template_for(validated, "add", "v:=(v,v)"), "binary")
        self.assertEqual(
            template_for(validated, "add", "v:=(m,v,v)", mask="zero"),
            "masked_binary",
        )
        self.assertEqual(
            template_for(validated, "blend_add", "v:=(m,v,v,v)", mask="pass_through"),
            "masked_ternary",
        )
        self.assertEqual(template_for(validated, "load", "v:=ptr", aligned="*"), "load")
        self.assertEqual(
            template_for(validated, "convert_up", "v:=(v,sImm)", cast="convert", direction="up"),
            "convert_up",
        )
        self.assertEqual(
            template_for(
                validated,
                "set",
                "v:=s...",
                **{"arg_count(args)": "return_vector_length"},
            ),
            "set",
        )

    def test_current_tsldata_passes_implemented_signature_and_attribute_validation(
        self,
    ) -> None:
        result = validate_catalog(standard_catalog())

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertGreater(len(result.unwrap().primitives), 100)

    def test_rejects_malformed_attribute_values_and_unknown_attributes(self) -> None:
        catalog = catalog_from_paths("tsldata/detail/templates.tsl")
        invalid = catalog_from_text(
            """prim<v:=(m,v,v)>[mask=maybe] bad_mask(mask, left, right):
  tests []
prim<v:=ptr>[aligned=maybe] bad_aligned(ptr):
  tests []
prim<void:=(ptr,m)>[aligned=true, packed=maybe] bad_packed(ptr, mask):
  tests []
prim<v:=(m,v)>[mask=zero, op=sideways] bad_op(mask, data):
  tests []
prim<v:=v>[cast=sideways] bad_cast(data):
  tests []
prim<v:=(v,sImm)>[cast=convert, direction=sideways] bad_direction(data, index):
  tests []
prim<v:=()>[value=bogus] bad_value():
  tests []
prim<v:=(v,v)>[mystery=true] bad_unknown(left, right):
  tests []
""",
            path="invalid-attributes.tsl",
        )
        combined = Catalog(
            templates=catalog.templates,
            primitives=invalid.primitives,
        )

        result = validate_catalog(combined)

        self.assertFalse(result.is_ok)
        codes = [diagnostic.code for diagnostic in result.diagnostics]
        self.assertEqual(codes.count("TSL-ATTR-VALUE"), 7)
        self.assertIn("TSL-ATTR-UNKNOWN", codes)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-ATTR-VALUE",
            severity="error",
            path="invalid-attributes.tsl",
            line=1,
            column=18,
        )

    def test_reports_required_attributes_duplicates_and_parameter_errors(self) -> None:
        templates = catalog_from_paths("tsldata/detail/templates.tsl")
        invalid = catalog_from_text(
            """prim<v:=(v,v)> add(left, left):
  tests []
prim<v:=ptr> load_missing(ptr):
  tests []
prim<v:=s...> set(args...):
  tests []
prim<v:=(m,v,v)>[mask=zero, mask=pass_through] dup(mask, left, right):
  tests []
prim<v:=(v,sImm)>[cast=convert] convert_missing_direction(data, index):
  tests []
""",
            path="invalid-required.tsl",
        )
        combined = Catalog(
            templates=templates.templates,
            primitives=invalid.primitives,
        )

        result = validate_catalog(combined)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-SIG-PARAM-DUPLICATE",
                "TSL-ATTR-REQUIRED",
                "TSL-ATTR-REQUIRED",
                "TSL-ATTR-DUPLICATE",
                "TSL-ATTR-REQUIRED",
            ],
        )
        assert_diagnostic(
            self,
            result.diagnostics[1],
            code="TSL-ATTR-REQUIRED",
            severity="error",
            path="invalid-required.tsl",
            line=3,
            column=1,
        )


if __name__ == "__main__":
    unittest.main()
