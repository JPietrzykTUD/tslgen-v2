from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.dependencies import discover_dependency_graph
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.implementations import (
    ImplementationSpec,
    implementation_specs_from_primitive,
)
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering.boundary import prepare_lowering_inputs
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(
    text: str,
    *,
    path: str = "implementation-spec-fixture.tsl",
) -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(
    text: str,
    *,
    path: str = "implementation-spec-fixture.tsl",
) -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(
    text: str,
    *,
    path: str = "implementation-spec-fixture.tsl",
) -> Catalog:
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


def catalog_with_primitives(text: str) -> ReferenceValidatedCatalog:
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


def reference_validated(catalog: Catalog) -> ReferenceValidatedCatalog:
    validated = validate_catalog(catalog)
    if not validated.is_ok:
        raise AssertionError(validated.diagnostics)
    referenced = validate_references(validated.unwrap())
    if not referenced.is_ok:
        raise AssertionError(referenced.diagnostics)
    return referenced.unwrap()


def candidate_selection_for(
    referenced: ReferenceValidatedCatalog,
    request: SelectionRequest,
) -> CandidateSelection:
    plan = plan_selection(referenced, request)
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


SIMPLE_IMPLEMENTATION = """prim<v:=(v,v)> spec_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse2]
        note "preserved"
        implementation:
          tsil "emit_return(left + right);"
"""


UNRELATED_UNSUPPORTED_BRANCH = """prim<v:=(v,v)> spec_branch(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
    generic:
      si32:
        - {implementation {tsil "emit_return(left);"}}
        - {implementation {tsil "emit_return(right);"}}
"""


class ImplementationSpecTests(unittest.TestCase):
    def test_normalizes_scalar_tsil_implementation_spec(self) -> None:
        catalog = catalog_from_text(SIMPLE_IMPLEMENTATION)

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertTrue(result.is_ok, result.diagnostics)
        specs = result.unwrap().specs
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec.extension_selector.raw, "scalar")
        self.assertEqual(spec.extension_selector.names, ("scalar",))
        self.assertEqual(spec.type_selector.raw, "si32")
        self.assertEqual(spec.type_selector.names, ("si32",))
        self.assertEqual(spec.body.kind, "tsil")
        self.assertEqual(spec.body.classification, "tsil")
        self.assertEqual(spec.body.text, "emit_return(left + right);")
        self.assertEqual(spec.requires_value, ("sse2",))
        self.assertEqual(spec.extra_fields.to_dict(), {"note": "preserved"})

    def test_missing_body_is_spec_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """prim<v:=(v,v)> spec_missing(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
"""
        )

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-BODY-MISSING"],
        )
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-IMPLEMENTATION-SPEC-BODY-MISSING",
            severity="error",
            path="implementation-spec-fixture.tsl",
            line=1,
            column=1,
        )

    def test_list_backed_variants_are_spec_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """prim<v:=(v,v)> spec_ambiguous(left, right):
  tests []
  impls:
    scalar:
      si32:
        - {implementation {tsil "emit_return(left);"}}
        - {implementation {tsil "emit_return(right);"}}
"""
        )

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-LIST-VARIANTS"],
        )

    def test_body_shape_is_spec_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """prim<v:=(v,v)> spec_body_shape(left, right):
  tests []
  impls:
    scalar:
      si32:
        implementation "not-a-body-map"
"""
        )

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-BODY-SHAPE"],
        )

    def test_ambiguous_body_is_spec_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """prim<v:=(v,v)> spec_body_ambiguous(left, right):
  tests []
  impls:
    scalar:
      si32:
        implementation:
          tsil "emit_return(left);"
          cpp "return left;"
"""
        )

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-BODY-AMBIGUOUS"],
        )

    def test_nested_selector_shape_is_spec_shape_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """prim<v:=(v,v)> spec_nested(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        ToType:
          ui32:
            implementation:
              tsil "emit_return(left);"
"""
        )

        result = implementation_specs_from_primitive(catalog.primitives[0])

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-SHAPE"],
        )
        self.assertIn("nested implementation selector", result.diagnostics[0].message)

    def test_selector_filter_ignores_unselected_unsupported_branch(self) -> None:
        catalog = catalog_from_text(UNRELATED_UNSUPPORTED_BRANCH)

        result = implementation_specs_from_primitive(
            catalog.primitives[0],
            include_extension_selector=lambda selector: selector.raw == "scalar",
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(spec.extension_selector.raw for spec in result.unwrap().specs),
            ("scalar",),
        )

    def test_selector_filter_reports_selected_unsupported_branch(self) -> None:
        catalog = catalog_from_text(UNRELATED_UNSUPPORTED_BRANCH)

        result = implementation_specs_from_primitive(
            catalog.primitives[0],
            include_extension_selector=lambda selector: selector.raw == "generic",
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-LIST-VARIANTS"],
        )

    def test_scalar_blend_selection_ignores_unselected_current_corpus_shapes(self) -> None:
        referenced = planning_catalog("tsldata/primitives/misc/blend.tsl")

        plan = plan_selection(
            referenced,
            SelectionRequest(
                primitive_names=("blend",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        self.assertTrue(plan.is_ok, plan.diagnostics)
        candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)

        self.assertTrue(candidates.is_ok, candidates.diagnostics)
        self.assertGreater(len(candidates.unwrap().candidates), 0)
        self.assertEqual(
            {candidate.source_extension for candidate in candidates.unwrap().candidates},
            {"scalar"},
        )

    def test_unselected_list_backed_branch_does_not_block_valid_branch(self) -> None:
        referenced = catalog_with_primitives(UNRELATED_UNSUPPORTED_BRANCH)

        scalar_plan = plan_selection(
            referenced,
            SelectionRequest(
                primitive_names=("spec_branch",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        generic_plan = plan_selection(
            referenced,
            SelectionRequest(
                primitive_names=("spec_branch",),
                extension_names=("generic",),
                include_support_extensions=False,
            ),
        )

        self.assertTrue(scalar_plan.is_ok, scalar_plan.diagnostics)
        self.assertFalse(generic_plan.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in generic_plan.diagnostics],
            ["TSL-IMPLEMENTATION-SPEC-LIST-VARIANTS"],
        )

    def test_candidate_selection_exposes_promoted_spec(self) -> None:
        referenced = catalog_with_primitives(SIMPLE_IMPLEMENTATION)
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("spec_add",),
                extension_names=("scalar",),
                cpu_flags=("sse2",),
                include_support_extensions=False,
            ),
        )

        candidate = selection.candidates[0]

        self.assertIsInstance(candidate.implementation, ImplementationSpec)
        self.assertEqual(candidate.implementation.body.text, "emit_return(left + right);")
        self.assertEqual(candidate.implementation.extra_fields.to_dict(), {"note": "preserved"})

    def test_dependency_and_lowering_consume_promoted_body(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> spec_root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=spec_leaf>(left, right));"
prim<v:=(v,v)> spec_leaf(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("spec_root", "spec_leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        dependencies = discover_dependency_graph(selection, referenced.catalog)
        lowering_inputs = prepare_lowering_inputs(selection)

        self.assertTrue(dependencies.is_ok, dependencies.diagnostics)
        self.assertTrue(lowering_inputs.is_ok, lowering_inputs.diagnostics)
        root_dependencies = next(
            item
            for item in dependencies.unwrap().candidate_dependencies
            if item.candidate.source_primitive_name == "spec_root"
        )
        self.assertEqual(root_dependencies.direct_primitive_names, ("spec_leaf",))
        self.assertTrue(
            all(item.payload.text is not None for item in lowering_inputs.unwrap().inputs)
        )


if __name__ == "__main__":
    unittest.main()
