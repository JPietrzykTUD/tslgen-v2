from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from unittest.mock import patch
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
from tslgen.core.diagnostics import Diagnostic
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import (
    ArtifactDescriptor,
    ArtifactSet,
    artifact_plan_from_descriptors,
)
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering.translations import BackendTypeSpelling
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.testgen.cpp import (
    render_cpp_add_i32_test_source_plan,
    render_cpp_test_source_plan,
)
from tslgen.testgen.declarations import (
    ProductionTestCase,
    ProductionTestDeclaration,
    normalize_test_declarations,
)
from tslgen.testgen.planner import (
    PlannedTestCase,
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
CPP_ADD_I32_PARITY_GOLDEN = golden_artifact(
    "tests/add_i32_basic_test.cpp",
    "golden",
    "parity",
    "cpp",
    "add_i32_basic_test.cpp",
)
FUNDAMENTAL_TSL_PATH = (
    Path(__file__).resolve().parents[3]
    / "tsldata/primitives/arithmetic/fundamental.tsl"
).as_posix()


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


def add_i32_type_spelling(*, spelling: str = "int32_t") -> BackendTypeSpelling:
    return BackendTypeSpelling(
        backend_id="cpp",
        type_tag="si32",
        spelling=spelling,
        source_ref_kind="base.in",
    )


def add_i32_declaration_from_tsldata() -> ProductionTestDeclaration:
    catalog = catalog_from_paths(
        "tsldata/detail/flags.tsl",
        "tsldata/detail/types.tsl",
        "tsldata/detail/lane_sets.tsl",
        "tsldata/extensions/extension.tsl",
        "tsldata/detail/templates.tsl",
        "tsldata/primitives/arithmetic/fundamental.tsl",
    )
    declarations = normalize_test_declarations(catalog)
    if not declarations.is_ok:
        raise AssertionError(declarations.diagnostics)
    matches = tuple(
        declaration
        for declaration in declarations.unwrap()
        if declaration.primitive_name == "add"
        and declaration.test_name == "add_i32_basic"
        and declaration.type_tag == "si32"
    )
    if len(matches) != 1:
        raise AssertionError(f"expected one add_i32_basic declaration, got {matches!r}")
    return matches[0]


def make_add_i32_parity_plan(
    *,
    declaration: ProductionTestDeclaration | None = None,
    backend_id: str = "cpp",
    artifact_kind: str = "production_tests",
    logical_path: str = "tests/add_i32_basic_test.cpp",
    target_extension: str = "scalar",
    type_tag: str = "si32",
    cases: tuple[PlannedTestCase, ...] | None = None,
) -> TestSourcePlan:
    selected_declaration = declaration or add_i32_declaration_from_tsldata()
    request = TestSourcePlanningRequest(
        backend_id=backend_id,
        primitive_names=("add",),
        test_names=("add_i32_basic",),
        artifact_kind=artifact_kind,
        logical_path=PurePosixPath(logical_path),
    )
    planned_cases = cases
    if planned_cases is None:
        planned_cases = (
            PlannedTestCase(
                declaration=selected_declaration,
                candidate_id=(
                    "add<v:=(v,v)>[](left,right)|backend=cpp|target=scalar|"
                    "source=scalar|type=si32|flags=none|impl=scalar/arith/tsil"
                ),
                backend_id=backend_id,
                target_extension=target_extension,
                source_extension="scalar",
                type_tag=type_tag,
            ),
        )
    descriptor = ArtifactDescriptor(
        backend_id=backend_id,
        kind=artifact_kind,
        logical_path=PurePosixPath(logical_path),
        candidate_ids=tuple(case.candidate_id for case in planned_cases),
        metadata=FrozenMap(
            {
                "artifact_role": "production_test_sources",
                "backend_id": backend_id,
                "primitive_names": ("add",),
                "test_case_ids": tuple(case.test_case_id for case in planned_cases),
                "test_count": len(planned_cases),
                "test_names": ("add_i32_basic",),
            }
        ),
    )
    artifact_plan = artifact_plan_from_descriptors(
        backend_id,
        (descriptor,),
        metadata=FrozenMap(
            {
                "artifact_role": "production_test_sources",
                "backend_id": backend_id,
                "descriptor_count": 1,
                "planned_test_count": len(planned_cases),
            }
        ),
    )
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return TestSourcePlan(
        request=request,
        declarations=(selected_declaration,),
        test_cases=planned_cases,
        artifact_plan=artifact_plan.unwrap(),
    )


def render_add_i32_parity_plan(
    plan: TestSourcePlan | None = None,
    *,
    type_spellings: tuple[BackendTypeSpelling, ...] | None = None,
) -> ArtifactSet:
    result = render_cpp_add_i32_test_source_plan(
        plan or make_add_i32_parity_plan(),
        type_spellings or (add_i32_type_spelling(),),
    )
    if not result.is_ok:
        raise AssertionError(result.diagnostics)
    return result.unwrap()


def diagnostic_by_code(
    result_diagnostics: tuple[Diagnostic, ...],
    code: str,
) -> Diagnostic:
    for diagnostic in result_diagnostics:
        if getattr(diagnostic, "code") == code:
            return diagnostic
    raise AssertionError(f"missing diagnostic {code!r}: {result_diagnostics!r}")


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

    def test_renders_add_i32_parity_test_source_golden(self) -> None:
        artifacts = render_add_i32_parity_plan()

        artifact = assert_artifact_matches_golden(
            self,
            artifacts,
            CPP_ADD_I32_PARITY_GOLDEN,
        )
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["artifact_kind"], "production_tests")
        self.assertEqual(artifact.metadata["test_count"], 1)
        self.assertEqual(artifact.metadata["type_spelling"], "int32_t")

    def test_add_i32_parity_provenance_fixture_documents_evidence(self) -> None:
        provenance = (
            CPP_ADD_I32_PARITY_GOLDEN.fixture_path.with_suffix(".provenance.md")
            .read_text(encoding="utf-8")
        )

        self.assertIn("CPP-ADD-I32-TEST", provenance)
        self.assertIn("tsldata/primitives/arithmetic/fundamental.tsl:6", provenance)
        self.assertIn("frozen/jinja/cpp/test_file.j2:1-56", provenance)
        self.assertIn("frozen/jinja/cpp/partials/test_common.j2:1-13", provenance)
        self.assertIn("frozen/jinja/cpp/test_case.j2:51-63", provenance)
        self.assertIn("frozen/jinja/cpp/partials/test_vectors.j2:38-50", provenance)
        self.assertIn("frozen/generator_specs/tests.yaml:45-59", provenance)
        self.assertIn("BackendTypeSpelling", provenance)

    def test_add_i32_parity_rendering_is_deterministic(self) -> None:
        first = render_add_i32_parity_plan()
        second = render_add_i32_parity_plan()

        assert_artifact_digest_map_stable(self, first, second)
        self.assertEqual(first.artifacts, second.artifacts)

    def test_add_i32_parity_consumes_typed_plan_vectors(self) -> None:
        declaration = add_i32_declaration_from_tsldata()
        changed = replace(
            declaration,
            case=ProductionTestCase(
                inputs=((101, 102), (1, 2)),
                expected=(102, 104),
            ),
        )

        artifacts = render_add_i32_parity_plan(make_add_i32_parity_plan(declaration=changed))
        artifact = artifacts.artifacts_by_path["tests/add_i32_basic_test.cpp"]

        self.assertIn("const int32_t in_a[kCount] = {101, 102};", artifact.content)
        self.assertIn("const int32_t expected_values[kCount] = {102, 104};", artifact.content)

    def test_add_i32_parity_consumes_explicit_type_spelling(self) -> None:
        artifacts = render_add_i32_parity_plan(
            type_spellings=(add_i32_type_spelling(spelling="explicit_i32"),),
        )
        artifact = artifacts.artifacts_by_path["tests/add_i32_basic_test.cpp"]

        self.assertIn("using Vec = tsl::simd<explicit_i32, scalar>;", artifact.content)
        self.assertNotIn("tsl::simd<int32_t, scalar>", artifact.content)

    def test_add_i32_parity_rendering_does_not_read_tsl_or_frozen_templates(self) -> None:
        plan = make_add_i32_parity_plan()
        with patch("builtins.open", side_effect=AssertionError("unexpected file read")):
            result = render_cpp_add_i32_test_source_plan(
                plan,
                (add_i32_type_spelling(),),
            )

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["tests/add_i32_basic_test.cpp"]
        self.assertNotIn("frozen/", artifact.content)
        self.assertNotIn("tsldata/", artifact.content)

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

    def test_add_i32_parity_diagnoses_unsupported_backend(self) -> None:
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(backend_id="rust"),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(result.diagnostics, "TSL-TEST-RENDER-BACKEND")
        assert_diagnostic(self, diagnostic, code="TSL-TEST-RENDER-BACKEND", severity="error")
        self.assertIn("rust", diagnostic.message)

    def test_add_i32_parity_diagnoses_unsupported_artifact_kind(self) -> None:
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(artifact_kind="test_manifest"),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-ARTIFACT",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-ARTIFACT",
            severity="error",
        )
        self.assertIn("test_manifest", diagnostic.message)

    def test_add_i32_parity_diagnoses_unsupported_extension(self) -> None:
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(target_extension="avx2"),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-EXTENSION",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-EXTENSION",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("scalar", diagnostic.message)

    def test_add_i32_parity_diagnoses_unsupported_type(self) -> None:
        declaration = replace(add_i32_declaration_from_tsldata(), type_tag="ui32")
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration, type_tag="ui32"),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-TYPE",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-TYPE",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("si32", diagnostic.message)

    def test_add_i32_parity_diagnoses_unsupported_selected_case(self) -> None:
        declaration = replace(add_i32_declaration_from_tsldata(), test_name="add_i32_edge")
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-CASE",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-CASE",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("add_i32_basic", diagnostic.message)

    def test_add_i32_parity_diagnoses_unsupported_case_shape(self) -> None:
        declaration = replace(
            add_i32_declaration_from_tsldata(),
            case=ProductionTestCase(inputs=((1, 2),), expected=(3, 4)),
        )
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-CASE",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-CASE",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("exactly two input vectors", diagnostic.message)

    def test_add_i32_parity_diagnoses_extra_metadata(self) -> None:
        declaration = replace(
            add_i32_declaration_from_tsldata(),
            extra_fields=FrozenMap({"scale": 2}),
        )
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-UNSUPPORTED-METADATA",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-UNSUPPORTED-METADATA",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("metadata", diagnostic.message)

    def test_add_i32_parity_diagnoses_malformed_vector_values(self) -> None:
        declaration = replace(
            add_i32_declaration_from_tsldata(),
            case=ProductionTestCase(inputs=((1, "bad"), (2, 3)), expected=(3, 4)),
        )
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-MALFORMED-VECTOR",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-MALFORMED-VECTOR",
            severity="error",
            path=FUNDAMENTAL_TSL_PATH,
            line=2,
            column=1,
        )
        self.assertIn("integer-vector", diagnostic.message)

    def test_add_i32_parity_diagnoses_missing_type_spelling(self) -> None:
        result = render_cpp_add_i32_test_source_plan(make_add_i32_parity_plan(), ())

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-TYPE-SPELLING-MISSING",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-TYPE-SPELLING-MISSING",
            severity="error",
        )
        self.assertIn("BackendTypeSpelling", diagnostic.message)

    def test_add_i32_parity_diagnoses_ambiguous_type_spelling(self) -> None:
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(),
            (add_i32_type_spelling(), add_i32_type_spelling(spelling="also_i32")),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-TYPE-SPELLING-AMBIGUOUS",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-TYPE-SPELLING-AMBIGUOUS",
            severity="error",
        )
        self.assertIn("exactly one", diagnostic.message)

    def test_add_i32_parity_diagnoses_wrong_selected_case_cardinality(self) -> None:
        declaration = add_i32_declaration_from_tsldata()
        first = make_add_i32_parity_plan(declaration=declaration).test_cases[0]
        second = PlannedTestCase(
            declaration=declaration,
            candidate_id=f"{first.candidate_id}|duplicate",
            backend_id="cpp",
            target_extension="scalar",
            source_extension="scalar",
            type_tag="si32",
        )
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(declaration=declaration, cases=(first, second)),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-SELECTED-CASE-CARDINALITY",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-SELECTED-CASE-CARDINALITY",
            severity="error",
        )
        self.assertIn("exactly one", diagnostic.message)

    def test_add_i32_parity_diagnoses_zero_selected_cases(self) -> None:
        result = render_cpp_add_i32_test_source_plan(
            make_add_i32_parity_plan(cases=()),
            (add_i32_type_spelling(),),
        )

        self.assertFalse(result.is_ok)
        diagnostic = diagnostic_by_code(
            result.diagnostics,
            "TSL-TEST-RENDER-SELECTED-CASE-CARDINALITY",
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-TEST-RENDER-SELECTED-CASE-CARDINALITY",
            severity="error",
        )
        self.assertIn("received 0", diagnostic.message)


if __name__ == "__main__":
    unittest.main()
