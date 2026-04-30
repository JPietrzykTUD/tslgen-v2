from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import descriptor_digest_map
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.testgen.declarations import (
    ProductionTestCase,
    ProductionTestDeclaration,
    normalize_test_declarations,
)
from tslgen.testgen.planner import (
    TestSourcePlanningRequest,
    plan_test_sources,
    plan_test_sources_for_declarations,
)
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "testgen-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "testgen-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "testgen-fixture.tsl") -> Catalog:
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


def catalog_with_primitives(text: str) -> Catalog:
    base = base_catalog()
    primitive_catalog = catalog_from_text(text)
    return Catalog(
        type_groups=base.type_groups,
        lane_sets=base.lane_sets,
        extensions=base.extensions,
        templates=base.templates,
        primitives=primitive_catalog.primitives,
        entries=base.entries,
        source_metadata=base.source_metadata,
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


TEST_PRIMITIVES = """prim<v:=(v,v)> planned_add(left, right):
  tests:
    - {test_name "planned_add_i32", type "si32", lane_set "lanes_i32", lanes 8, case {inputs [[1, 2], [3, 4]], expected [4, 6]}}
    - {test_name "planned_add_avx2_i32", extension "avx2", type "si32", lane_set "lanes_i32", lanes 8, scale 2, case {inputs [[10, 20], [1, 2]], expected [11, 22]}}
    - {test_name "planned_add_ui32", type "ui32", lane_set "lanes_i32", lanes 8, case {inputs [[1], [2]], expected [3]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
    avx2:
      si32:
        requires [avx2]
        implementation:
          tsil "emit_return(left + right);"

prim<v:=ptr>[aligned=*] planned_load(ptr):
  tests:
    - {test_name "planned_load_aligned", attrs [aligned=true], type "si32", lane_set "lanes_i32", lanes 4, offset 0, case {inputs [[1, 2, 3, 4]], expected [1, 2, 3, 4]}}
    - {test_name "planned_load_unaligned", attrs [aligned=false], type "si32", lane_set "lanes_i32", lanes 4, offset 1, case {inputs [[0, 1, 2, 3, 4]], expected [1, 2, 3, 4]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(ptr);"
"""


class TestSourcePlanningTests(unittest.TestCase):
    def test_normalizes_representative_current_tsl_tests(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/detail/flags.tsl",
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
            "tsldata/primitives/load_store/store.tsl",
        )

        result = normalize_test_declarations(catalog)

        self.assertTrue(result.is_ok, result.diagnostics)
        declarations = {
            declaration.test_name: declaration for declaration in result.unwrap()
        }
        aligned = declarations["store_scalar_aligned_ui8_basic"]
        self.assertEqual(aligned.primitive_name, "store")
        self.assertEqual(aligned.type_tag, "ui8")
        self.assertIsNone(aligned.lane_set_name)
        self.assertEqual(aligned.attributes["aligned"], True)
        self.assertEqual(aligned.extra_fields["offset"], 0)

    def test_plans_artifact_descriptor_for_selected_candidates_deterministically(
        self,
    ) -> None:
        referenced = reference_validated(catalog_with_primitives(TEST_PRIMITIVES))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("planned_add",),
                extension_names=("avx2",),
                include_support_extensions=False,
            ),
        )
        request = TestSourcePlanningRequest(
            backend_id="cpp",
            primitive_names=("planned_add",),
        )

        first = plan_test_sources(referenced.catalog, selection, request)
        second = plan_test_sources(referenced.catalog, selection, request)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        first_plan = first.unwrap()
        second_plan = second.unwrap()
        self.assertEqual(first_plan.descriptors, second_plan.descriptors)
        self.assertEqual(
            descriptor_digest_map(first_plan.artifact_plan),
            descriptor_digest_map(second_plan.artifact_plan),
        )
        self.assertEqual(
            tuple(case.declaration.test_name for case in first_plan.test_cases),
            ("planned_add_avx2_i32", "planned_add_i32"),
        )
        self.assertEqual(len(first_plan.descriptors), 1)
        descriptor = first_plan.descriptors[0]
        self.assertEqual(descriptor.kind, "production_tests")
        self.assertEqual(descriptor.logical_path.as_posix(), "tests/production_tests.plan")
        self.assertEqual(descriptor.metadata["test_count"], 2)
        self.assertEqual(
            descriptor.metadata["test_names"],
            ("planned_add_avx2_i32", "planned_add_i32"),
        )

    def test_filters_test_declaration_attributes_against_selected_variants(self) -> None:
        referenced = reference_validated(catalog_with_primitives(TEST_PRIMITIVES))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("planned_load",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = plan_test_sources(
            referenced.catalog,
            selection,
            TestSourcePlanningRequest(backend_id="cpp"),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        self.assertEqual(len(plan.test_cases), 2)
        self.assertEqual(
            tuple(case.declaration.test_name for case in plan.test_cases),
            ("planned_load_aligned", "planned_load_unaligned"),
        )

    def test_filters_by_candidate_backend(self) -> None:
        referenced = reference_validated(catalog_with_primitives(TEST_PRIMITIVES))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("planned_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = plan_test_sources(
            referenced.catalog,
            selection,
            TestSourcePlanningRequest(backend_id="rust"),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        self.assertEqual(plan.test_cases, ())
        self.assertEqual(plan.descriptors, ())

    def test_diagnoses_unsupported_declaration_shape(self) -> None:
        catalog = catalog_with_primitives(
            """prim<v:=(v,v)> bad_tests(left, right):
  tests:
    - {test_name "bad_attrs", attrs ["aligned"], type "si32", case {inputs [[1], [2]], expected [3]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""
        )

        result = normalize_test_declarations(catalog)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-DECL-SHAPE",
            severity="error",
        )

    def test_diagnoses_unknown_test_references(self) -> None:
        catalog = catalog_with_primitives(
            """prim<v:=(v,v)> unresolved_tests(left, right):
  tests:
    - {test_name "bad_refs", extension "missing_ext", type "missing_type", lane_set "missing_lanes", case {inputs [[1], [2]], expected [3]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""
        )

        result = normalize_test_declarations(catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            tuple(diagnostic.code for diagnostic in result.diagnostics),
            (
                "TSL-TEST-DECL-REFERENCE",
                "TSL-TEST-DECL-REFERENCE",
                "TSL-TEST-DECL-REFERENCE",
            ),
        )

    def test_diagnoses_unknown_primitive_reference_in_planner(self) -> None:
        referenced = reference_validated(catalog_with_primitives(TEST_PRIMITIVES))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("planned_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        declaration = ProductionTestDeclaration(
            primitive_name="missing_primitive",
            test_name="dangling_test",
            type_tag="si32",
            case=ProductionTestCase(inputs=(1,), expected=1),
            attributes=FrozenMap.empty(),
            extra_fields=FrozenMap.empty(),
        )

        result = plan_test_sources_for_declarations(
            referenced.catalog,
            selection,
            (declaration,),
            TestSourcePlanningRequest(backend_id="cpp"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-PLAN-UNKNOWN-PRIMITIVE",
            severity="error",
        )


if __name__ == "__main__":
    unittest.main()
