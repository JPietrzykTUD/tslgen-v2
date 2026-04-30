from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_matches_golden,
    golden_artifact,
)
from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import ArtifactSet
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.testgen.cpp import render_cpp_test_source_plan
from tslgen.testgen.planner import (
    TestSourcePlanningRequest,
    TestSourcePlan,
    plan_test_sources,
)
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


CPP_PRODUCTION_TEST_GOLDEN = golden_artifact(
    "tests/production_tests.cpp",
    "golden",
    "cpp",
    "production_tests.cpp",
)


SUPPORTED_TEST_PRIMITIVES = """prim<v:=(v,v)> planned_add(left, right):
  tests:
    - {test_name "planned_add_i32_basic", type "si32", lane_set "lanes_i32", lanes 8, case {inputs [[1, 2], [3, 4]], expected [4, 6]}}
    - {test_name "planned_add_ui32_basic", type "ui32", lane_set "lanes_i32", lanes 8, case {inputs [[5, 6], [7, 8]], expected [12, 14]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
      ui32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


UNSUPPORTED_TYPE_PRIMITIVE = """prim<v:=(v,v)> planned_float_add(left, right):
  tests:
    - {test_name "planned_add_f32_basic", type "f32", lane_set "lanes_f32", lanes 4, case {inputs [[1, 2], [3, 4]], expected [4, 6]}}
  impls:
    scalar:
      f32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


UNSUPPORTED_METADATA_PRIMITIVE = """prim<v:=(v,v)> planned_scaled_add(left, right):
  tests:
    - {test_name "planned_scaled_i32", type "si32", lane_set "lanes_i32", lanes 8, scale 2, case {inputs [[1, 2], [3, 4]], expected [4, 6]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


UNSUPPORTED_SHAPE_PRIMITIVE = """prim<v:=(v,v)> planned_bad_add(left, right):
  tests:
    - {test_name "planned_bad_i32", type "si32", lane_set "lanes_i32", lanes 8, case {inputs [[1, 2]], expected [4, 6]}}
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


def source_document(text: str, *, path: str = "cpp-test-render-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "cpp-test-render-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "cpp-test-render-fixture.tsl") -> Catalog:
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
    *,
    primitive_name: str,
) -> CandidateSelection:
    plan = plan_selection(
        referenced,
        SelectionRequest(
            backend="cpp",
            primitive_names=(primitive_name,),
            extension_names=("scalar",),
            include_support_extensions=False,
        ),
    )
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


def make_test_source_plan(
    primitive_text: str,
    *,
    primitive_name: str,
    artifact_kind: str = "production_tests",
) -> TestSourcePlan:
    referenced = reference_validated(catalog_with_primitives(primitive_text))
    selection = candidate_selection_for(referenced, primitive_name=primitive_name)
    planned = plan_test_sources(
        referenced.catalog,
        selection,
        TestSourcePlanningRequest(
            backend_id="cpp",
            primitive_names=(primitive_name,),
            artifact_kind=artifact_kind,
            logical_path=PurePosixPath("tests/production_tests.cpp"),
        ),
    )
    if not planned.is_ok:
        raise AssertionError(planned.diagnostics)
    return planned.unwrap()


def render_supported_plan() -> ArtifactSet:
    result = render_cpp_test_source_plan(
        make_test_source_plan(
            SUPPORTED_TEST_PRIMITIVES,
            primitive_name="planned_add",
        )
    )
    if not result.is_ok:
        raise AssertionError(result.diagnostics)
    return result.unwrap()


class CppProductionTestRenderingTests(unittest.TestCase):
    def test_renders_cpp_production_test_source_golden(self) -> None:
        artifacts = render_supported_plan()

        artifact = assert_artifact_matches_golden(
            self,
            artifacts,
            CPP_PRODUCTION_TEST_GOLDEN,
        )
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["artifact_kind"], "production_tests")
        self.assertEqual(artifact.metadata["test_count"], 2)
        self.assertEqual(
            artifact.metadata["test_names"],
            ("planned_add_i32_basic", "planned_add_ui32_basic"),
        )

    def test_cpp_production_test_rendering_is_deterministic(self) -> None:
        first = render_supported_plan()
        second = render_supported_plan()

        assert_artifact_digest_map_stable(self, first, second)
        self.assertEqual(first.artifacts, second.artifacts)

    def test_diagnoses_unsupported_test_artifact_kind(self) -> None:
        plan = make_test_source_plan(
            SUPPORTED_TEST_PRIMITIVES,
            primitive_name="planned_add",
            artifact_kind="test_manifest",
        )

        result = render_cpp_test_source_plan(plan)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-RENDER-UNSUPPORTED-ARTIFACT",
            severity="error",
        )

    def test_diagnoses_unsupported_type_tag(self) -> None:
        plan = make_test_source_plan(
            UNSUPPORTED_TYPE_PRIMITIVE,
            primitive_name="planned_float_add",
        )

        result = render_cpp_test_source_plan(plan)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-RENDER-UNSUPPORTED-TYPE",
            severity="error",
        )

    def test_diagnoses_unsupported_extra_metadata(self) -> None:
        plan = make_test_source_plan(
            UNSUPPORTED_METADATA_PRIMITIVE,
            primitive_name="planned_scaled_add",
        )

        result = render_cpp_test_source_plan(plan)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-RENDER-UNSUPPORTED-METADATA",
            severity="error",
        )

    def test_diagnoses_unsupported_case_shape(self) -> None:
        plan = make_test_source_plan(
            UNSUPPORTED_SHAPE_PRIMITIVE,
            primitive_name="planned_bad_add",
        )

        result = render_cpp_test_source_plan(plan)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-TEST-RENDER-UNSUPPORTED-CASE",
            severity="error",
        )


if __name__ == "__main__":
    unittest.main()
