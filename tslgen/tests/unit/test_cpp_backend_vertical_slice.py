from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_set_matches_golden,
    golden_artifact,
)
from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.backends.cpp.backend import CppBackend
from tslgen.backends.cpp.naming import (
    cpp_production_function_name,
    cpp_production_parameter_names,
)
from tslgen.config.model import SourceConfig
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import ArtifactDescriptor, artifact_plan_from_descriptors
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


SIMPLE_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires [sse]
        implementation:
          tsil "emit_return(left + right);"
"""


SI32_ONLY_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(left + right);"
"""


UNSUPPORTED_DECLARATION_PRIMITIVE = """prim<v:=()> slice_zero():
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(0);"
"""


INVALID_PARAMETER_PRIMITIVE = """prim<v:=(v,v)> slice_add(class, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(class + right);"
"""


def source_document(text: str, *, path: str = "cpp-slice-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "cpp-slice-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "cpp-slice-fixture.tsl") -> Catalog:
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


def candidate_selection_for(
    referenced: ReferenceValidatedCatalog,
    *,
    backend: str | None = "cpp",
    primitive_name: str = "slice_add",
) -> CandidateSelection:
    plan = plan_selection(
        referenced,
        SelectionRequest(
            backend=backend,
            primitive_names=(primitive_name,),
            extension_names=("scalar",),
            cpu_flags=("sse",),
            include_support_extensions=False,
        ),
    )
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


def manifest_set(*, artifact_kind: str = "generated") -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id="cpp",
                language_id="cpp",
                artifacts=(
                    ArtifactSpec(
                        kind=artifact_kind,
                        logical_name="generated",
                        extension="hpp",
                    ),
                ),
            ),
        )
    )


def render_simple_fixture(
    *,
    primitive_text: str = SIMPLE_PRIMITIVE,
    selection_backend: str | None = "cpp",
    artifact_kind: str = "generated",
):
    referenced = catalog_with_primitive(primitive_text)
    selection = candidate_selection_for(referenced, backend=selection_backend)
    artifact_plan = build_artifact_plan(
        manifest_set(artifact_kind=artifact_kind),
        "cpp",
        selection,
    )
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return CppBackend().render(artifact_plan.unwrap(), selection)


def artifact_plan_for_selection(
    selection: CandidateSelection,
    *,
    plan_backend: str = "cpp",
    descriptor_backend: str = "cpp",
):
    descriptor = ArtifactDescriptor(
        backend_id=descriptor_backend,
        kind="generated",
        logical_path=PurePosixPath("generated.hpp"),
        candidate_ids=tuple(candidate.candidate_id for candidate in selection.candidates),
    )
    artifact_plan = artifact_plan_from_descriptors(plan_backend, (descriptor,))
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return artifact_plan.unwrap()


class CppNamingTests(unittest.TestCase):
    def test_production_function_name_uses_primitive_and_type_tag(self) -> None:
        name = cpp_production_function_name("slice_add", "ui32")

        self.assertTrue(name.is_ok, name.diagnostics)
        self.assertEqual(name.unwrap(), "slice_add_ui32")

    def test_production_parameter_names_preserve_signature_names(self) -> None:
        names = cpp_production_parameter_names(("left", "right"))

        self.assertTrue(names.is_ok, names.diagnostics)
        self.assertEqual(names.unwrap(), ("left", "right"))

    def test_invalid_function_name_is_diagnostic(self) -> None:
        name = cpp_production_function_name("slice-add", "ui32")

        self.assertFalse(name.is_ok)
        assert_diagnostic(
            self,
            name.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-FUNCTION-NAME",
            severity="error",
        )

    def test_invalid_parameter_name_is_diagnostic(self) -> None:
        names = cpp_production_parameter_names(("class", "right"))

        self.assertFalse(names.is_ok)
        assert_diagnostic(
            self,
            names.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-PARAMETER-NAME",
            severity="error",
        )


class CppBackendVerticalSliceTests(unittest.TestCase):
    def test_renders_minimal_cpp_generated_artifact(self) -> None:
        result = render_simple_fixture()

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact_set = result.unwrap()
        assert_artifact_set_matches_golden(
            self,
            artifact_set,
            (
                golden_artifact(
                    "generated.hpp",
                    "golden",
                    "cpp",
                    "minimal_generated.hpp",
                ),
            ),
        )
        artifact = artifact_set.artifacts_by_path["generated.hpp"]
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["required_flags"], ("sse",))
        self.assertEqual(artifact.metadata["target_extensions"], ("scalar",))
        self.assertEqual(artifact.metadata["candidate_count"], 2)
        self.assertIn("namespace production", artifact.content)
        self.assertIn(
            "inline std::int32_t slice_add_si32(std::int32_t left, "
            "std::int32_t right);",
            artifact.content,
        )
        self.assertIn(
            "inline std::uint32_t slice_add_ui32(std::uint32_t left, "
            "std::uint32_t right);",
            artifact.content,
        )

    def test_original_scalar_binary_si32_declaration_remains_stable(self) -> None:
        result = render_simple_fixture(primitive_text=SI32_ONLY_PRIMITIVE)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertIn(
            "inline std::int32_t slice_add_si32(std::int32_t left, "
            "std::int32_t right);",
            artifact.content,
        )
        self.assertNotIn("slice_add_ui32", artifact.content)

    def test_rendering_is_deterministic(self) -> None:
        first = render_simple_fixture()
        second = render_simple_fixture()

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        assert_artifact_digest_map_stable(self, first.unwrap(), second.unwrap())

    def test_accepts_generic_backend_none_candidates(self) -> None:
        result = render_simple_fixture(selection_backend=None)

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact = result.unwrap().artifacts_by_path["generated.hpp"]
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertIn('"slice_add"', artifact.content)

    def test_diagnoses_non_cpp_artifact_plan(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, plan_backend="rust")

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_non_cpp_descriptor(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, descriptor_backend="rust")

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_backend_mismatched_candidates(self) -> None:
        result = render_simple_fixture(selection_backend="rust")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-CANDIDATE-BACKEND",
            severity="error",
        )

    def test_diagnoses_unsupported_artifact_kind(self) -> None:
        result = render_simple_fixture(artifact_kind="metadata")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-UNSUPPORTED-ARTIFACT",
            severity="error",
        )

    def test_diagnoses_candidate_outside_production_declaration_slice(self) -> None:
        selection = candidate_selection_for(
            catalog_with_primitive(UNSUPPORTED_DECLARATION_PRIMITIVE),
            primitive_name="slice_zero",
        )
        artifact_plan = artifact_plan_for_selection(selection)

        result = CppBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-UNSUPPORTED",
            severity="error",
        )

    def test_diagnoses_invalid_declaration_parameter_name(self) -> None:
        result = render_simple_fixture(primitive_text=INVALID_PARAMETER_PRIMITIVE)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-DECLARATION-PARAMETER-NAME",
            severity="error",
        )

    def test_diagnoses_missing_candidate_reference(self) -> None:
        descriptor = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("generated.hpp"),
            candidate_ids=("missing",),
        )
        artifact_plan = artifact_plan_from_descriptors("cpp", (descriptor,))
        self.assertTrue(artifact_plan.is_ok, artifact_plan.diagnostics)
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))

        result = CppBackend().render(artifact_plan.unwrap(), selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CPP-RENDER-MISSING-CANDIDATE",
            severity="error",
        )


if __name__ == "__main__":
    unittest.main()
