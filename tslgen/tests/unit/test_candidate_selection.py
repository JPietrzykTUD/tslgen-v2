from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import select_implementation_candidates
from tslgen.analysis.expansion import expand_variants
from tslgen.analysis.selection import SelectionPlan, SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "candidate-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "candidate-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "candidate-fixture.tsl") -> Catalog:
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


def base_catalog() -> Catalog:
    return catalog_from_paths(
        "tsldata/detail/flags.tsl",
        "tsldata/detail/types.tsl",
        "tsldata/detail/lane_sets.tsl",
        "tsldata/extensions/extension.tsl",
        "tsldata/detail/templates.tsl",
    )


def planning_catalog(*primitive_paths: str) -> ReferenceValidatedCatalog:
    return reference_validated(
        catalog_from_paths(
            "tsldata/detail/flags.tsl",
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
            *primitive_paths,
        )
    )


def catalog_with_primitive(text: str) -> ReferenceValidatedCatalog:
    base = base_catalog()
    primitive_catalog = catalog_from_text(text)
    catalog = Catalog(
        type_groups=base.type_groups,
        lane_sets=base.lane_sets,
        extensions=base.extensions,
        templates=base.templates,
        primitives=primitive_catalog.primitives,
        entries=base.entries,
    )
    return reference_validated(catalog)


def reference_validated(catalog: Catalog) -> ReferenceValidatedCatalog:
    validated = validate_catalog(catalog)
    if not validated.is_ok:
        raise AssertionError(validated.diagnostics)
    referenced = validate_references(validated.unwrap())
    if not referenced.is_ok:
        raise AssertionError(referenced.diagnostics)
    return referenced.unwrap()


def selection_for(
    referenced: ReferenceValidatedCatalog,
    request: SelectionRequest,
):
    plan = plan_selection(referenced, request)
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    return select_implementation_candidates(plan.unwrap(), referenced.catalog)


SIMPLE_PRIMITIVE = """prim<v:=(v,v)> candidate_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
    generic:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


class ImplementationCandidateSelectionTests(unittest.TestCase):
    def test_selects_scalar_and_generic_candidates_for_small_fixture(self) -> None:
        result = selection_for(
            catalog_with_primitive(SIMPLE_PRIMITIVE),
            SelectionRequest(primitive_names=("candidate_add",)),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        candidates = result.unwrap().candidates
        self.assertEqual(
            tuple(
                (
                    candidate.target_extension,
                    candidate.source_extension,
                    candidate.type_tag,
                    candidate.implementation.body.kind,
                )
                for candidate in candidates
            ),
            (
                ("generic", "generic", "si32", "tsil"),
                ("scalar", "scalar", "si32", "tsil"),
            ),
        )
        self.assertEqual(candidates[0].implementation.body.payload, "emit_return(left + right);")

    def test_selects_avx_and_sse_candidates_from_normalized_flags(self) -> None:
        result = selection_for(
            planning_catalog("tsldata/primitives/arithmetic/fundamental.tsl"),
            SelectionRequest(
                primitive_names=("add",),
                template_names=("binary",),
                cpu_flags=("sse", "sse2", "avx", "avx2"),
                include_support_extensions=False,
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        candidates = result.unwrap().candidates
        candidate_keys = {
            (
                candidate.target_extension,
                candidate.source_extension,
                candidate.type_tag,
                tuple(flag.name for flag in candidate.required_flags),
            )
            for candidate in candidates
        }
        self.assertIn(("avx2", "avx2", "si32", ("avx", "avx2")), candidate_keys)
        self.assertIn(("sse", "sse", "f32", ("sse",)), candidate_keys)

    def test_uses_extension_fallback_when_target_inherits_source_extension(self) -> None:
        referenced = catalog_with_primitive(
            """prim<v:=(v,v)> fallback_add(left, right):
  tests []
  impls:
    avx2:
      si32:
        requires [avx2]
        implementation:
          tsil "emit_return(left + right);"
"""
        )

        result = selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("fallback_add",),
                extension_names=("avx2_vl",),
                cpu_flags=("avx2",),
                include_support_extensions=False,
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        candidates = result.unwrap().candidates
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].target_extension, "avx2_vl")
        self.assertEqual(candidates[0].source_extension, "avx2")

    def test_filters_explicitly_unsupported_backend_entries(self) -> None:
        referenced = catalog_with_primitive(
            """prim<v:=(v,v)> sve_add(left, right):
  tests []
  impls:
    sve:
      si32:
        requires [sve]
        implementation:
          tsil "emit_return(left + right);"
"""
        )

        cpp_result = selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("sve_add",),
                extension_names=("sve",),
                cpu_flags=("sve",),
                include_support_extensions=False,
            ),
        )
        rust_result = selection_for(
            referenced,
            SelectionRequest(
                backend="rust",
                primitive_names=("sve_add",),
                extension_names=("sve",),
                cpu_flags=("sve",),
                include_support_extensions=False,
            ),
        )

        self.assertTrue(cpp_result.is_ok, cpp_result.diagnostics)
        self.assertEqual(len(cpp_result.unwrap().candidates), 1)
        self.assertFalse(rust_result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in rust_result.diagnostics],
            ["TSL-CANDIDATE-NONE"],
        )

    def test_diagnoses_no_candidate_for_requested_extension(self) -> None:
        result = selection_for(
            catalog_with_primitive(SIMPLE_PRIMITIVE),
            SelectionRequest(
                primitive_names=("candidate_add",),
                extension_names=("neon",),
                cpu_flags=("neon",),
                include_support_extensions=False,
            ),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-CANDIDATE-NONE"],
        )
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CANDIDATE-NONE",
            severity="error",
            path="candidate-fixture.tsl",
            line=1,
            column=1,
        )

    def test_list_backed_implementation_variant_is_diagnostic(self) -> None:
        referenced = catalog_with_primitive(
            """prim<v:=(v,v)> ambiguous_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        - {implementation {tsil "emit_return(left);"}}
        - {implementation {tsil "emit_return(right);"}}
"""
        )
        expanded = expand_variants(referenced)
        self.assertTrue(expanded.is_ok, expanded.diagnostics)
        plan = SelectionPlan(
            request=SelectionRequest(
                primitive_names=("ambiguous_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
            variants=expanded.unwrap().variants,
            allowed_extensions=("scalar",),
            normalized_cpu_flags=(),
            implementation_plans=(),
        )

        result = select_implementation_candidates(plan, referenced.catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-CANDIDATE-AMBIGUOUS-IMPLEMENTATION"],
        )

    def test_candidate_selection_output_is_deterministic(self) -> None:
        referenced = catalog_with_primitive(SIMPLE_PRIMITIVE)
        request = SelectionRequest(primitive_names=("candidate_add",))

        first = selection_for(referenced, request)
        second = selection_for(referenced, request)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            tuple(candidate.candidate_id for candidate in first.unwrap().candidates),
            tuple(candidate.candidate_id for candidate in second.unwrap().candidates),
        )


if __name__ == "__main__":
    unittest.main()
