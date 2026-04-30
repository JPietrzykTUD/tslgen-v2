from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.dependencies import plan_dependency_closure
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.backends import (
    ArtifactSpec,
    BackendManifest,
    BackendManifestSet,
)
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import (
    ArtifactDescriptor,
    artifact_plan_from_descriptors,
    descriptor_digest_map,
)
from tslgen.io.manifests import (
    backend_manifests_from_catalog,
    load_backend_manifests,
    parse_backend_manifest_text,
)
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "artifact-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "artifact-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "artifact-fixture.tsl") -> Catalog:
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


def cpp_manifest_set() -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id="cpp",
                language_id="cpp",
                artifacts=(
                    ArtifactSpec(
                        kind="generated",
                        logical_name="generated",
                        extension="hpp",
                    ),
                ),
            ),
        )
    )


class BackendArtifactModelTests(unittest.TestCase):
    def test_loads_representative_backend_manifests(self) -> None:
        result = load_backend_manifests(
            (
                Path("frozen/generator_specs/backend_cpp.yaml"),
                Path("frozen/generator_specs/backend_c17.yaml"),
                Path("frozen/generator_specs/backend_rust.yaml"),
            )
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        manifests = result.unwrap()
        self.assertEqual(manifests.backend_ids, ("c17", "cpp", "rust"))
        target_paths = {
            manifest.backend_id: manifest.artifacts[0].target_path.as_posix()
            for manifest in manifests.manifests
        }
        self.assertEqual(
            target_paths,
            {"c17": "generated.h", "cpp": "generated.hpp", "rust": "generated.rs"},
        )
        cpp = manifests.manifests_by_id["cpp"]
        rust = manifests.manifests_by_id["rust"]
        self.assertEqual(cpp.template_policy.specialization_default, "{template}_specialization.j2")
        self.assertEqual(cpp.template_policy.specialization_overrides["binary"], "spec_binary.j2")
        self.assertEqual(rust.template_policy.primary_fallback, "{template}_primary.j2")
        self.assertEqual(rust.template_policy.trait, "tsl_trait.j2")

    def test_rejects_bad_manifest_version_and_missing_fields(self) -> None:
        bad_version = parse_backend_manifest_text(
            """version: 2
backend: cpp
artifact:
  name: generated
  extension: hpp
"""
        )
        missing_field = parse_backend_manifest_text(
            """version: 1
backend: cpp
artifact:
  name: generated
"""
        )

        self.assertFalse(bad_version.is_ok)
        self.assertFalse(missing_field.is_ok)
        assert_diagnostic(
            self,
            bad_version.diagnostics[0],
            code="TSL-BACKEND-MANIFEST-VERSION",
            severity="error",
        )
        assert_diagnostic(
            self,
            missing_field.diagnostics[0],
            code="TSL-BACKEND-MANIFEST-MISSING",
            severity="error",
        )

    def test_derives_backend_ids_from_language_and_translation_catalog_entries(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/detail/lang/types/types_cpp.tsl",
            "tsldata/detail/lang/types/types_c17.tsl",
            "tsldata/detail/lang/types/types_rust.tsl",
            "tsldata/detail/lang/translate_cpp.tsl",
            "tsldata/detail/lang/translate_c17.tsl",
            "tsldata/detail/lang/translate_rust.tsl",
        )

        manifests = backend_manifests_from_catalog(catalog)

        self.assertTrue(manifests.is_ok, manifests.diagnostics)
        self.assertEqual(manifests.unwrap().backend_ids, ("c17", "cpp", "rust"))

    def test_diagnoses_duplicate_manifest_artifact_targets(self) -> None:
        result = parse_backend_manifest_text(
            """version: 1
backend: cpp
artifacts:
  - name: generated
    extension: hpp
  - kind: metadata
    name: generated
    extension: hpp
"""
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-MANIFEST-DUPLICATE-ARTIFACT",
            severity="error",
        )

    def test_diagnoses_duplicate_artifact_plan_targets(self) -> None:
        descriptor = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("generated.hpp"),
        )

        result = artifact_plan_from_descriptors("cpp", (descriptor, descriptor))

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-ARTIFACT-DUPLICATE-TARGET",
            severity="error",
        )

    def test_builds_content_free_artifact_plan_from_candidate_closure(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> render_root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=render_helper>(left, right));"
prim<v:=(v,v)> render_helper(left, right):
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
                primitive_names=("render_root",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        closure = plan_dependency_closure(selection, referenced.catalog)
        self.assertTrue(closure.is_ok, closure.diagnostics)

        result = build_artifact_plan(
            cpp_manifest_set(),
            "cpp",
            selection,
            closure.unwrap(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        descriptor = plan.descriptors[0]
        self.assertEqual(descriptor.logical_path.as_posix(), "generated.hpp")
        self.assertEqual(
            descriptor.candidate_ids,
            tuple(candidate.candidate_id for candidate in selection.candidates),
        )
        self.assertEqual(
            descriptor.dependency_primitive_names,
            ("render_helper", "render_root"),
        )
        self.assertEqual(plan.metadata["unplanned_primitive_names"], ("render_helper",))

    def test_unknown_backend_is_diagnostic(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> render_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("render_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = build_artifact_plan(cpp_manifest_set(), "rust", selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-ARTIFACT-UNKNOWN-BACKEND",
            severity="error",
        )

    def test_descriptor_digest_map_is_deterministic(self) -> None:
        descriptor = ArtifactDescriptor(
            backend_id="cpp",
            kind="generated",
            logical_path=PurePosixPath("generated.hpp"),
            candidate_ids=("b", "a"),
            dependency_primitive_names=("root", "helper"),
            metadata=FrozenMap({"language_id": "cpp"}),
        )
        first = artifact_plan_from_descriptors("cpp", (descriptor,))
        second = artifact_plan_from_descriptors("cpp", (descriptor,))
        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)

        self.assertEqual(
            descriptor_digest_map(first.unwrap()),
            descriptor_digest_map(second.unwrap()),
        )


if __name__ == "__main__":
    unittest.main()
