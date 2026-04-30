from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic, fixture_path
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.backends.cpp.backend import CppBackend
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
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(left + right);"
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
    backend: str = "cpp",
) -> CandidateSelection:
    plan = plan_selection(
        referenced,
        SelectionRequest(
            backend=backend,
            primitive_names=("slice_add",),
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


def render_simple_fixture(*, selection_backend: str = "cpp", artifact_kind: str = "generated"):
    referenced = catalog_with_primitive(SIMPLE_PRIMITIVE)
    selection = candidate_selection_for(referenced, backend=selection_backend)
    artifact_plan = build_artifact_plan(
        manifest_set(artifact_kind=artifact_kind),
        "cpp",
        selection,
    )
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return CppBackend().render(artifact_plan.unwrap(), selection)


class CppBackendVerticalSliceTests(unittest.TestCase):
    def test_renders_minimal_cpp_generated_artifact(self) -> None:
        result = render_simple_fixture()

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact_set = result.unwrap()
        artifact = artifact_set.artifacts_by_path["generated.hpp"]
        golden = fixture_path("golden", "cpp", "minimal_generated.hpp").read_text(
            encoding="utf-8"
        )
        self.assertEqual(artifact.content, golden)
        self.assertEqual(artifact.metadata["backend_id"], "cpp")
        self.assertEqual(artifact.metadata["required_flags"], ("sse",))
        self.assertEqual(artifact.metadata["target_extensions"], ("scalar",))

    def test_rendering_is_deterministic(self) -> None:
        first = render_simple_fixture()
        second = render_simple_fixture()

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

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
