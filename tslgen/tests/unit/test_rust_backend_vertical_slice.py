from __future__ import annotations

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_set_matches_golden,
    golden_artifact,
)
from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.api import PipelineConfig, run_pipeline
from tslgen.backends.registry import BackendRegistry
from tslgen.backends.rust.backend import RustBackend
from tslgen.config.model import SourceConfig
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifacts import ArtifactDescriptor, artifact_plan_from_descriptors
from tslgen.io.manifests import parse_backend_manifest_text
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


SVE_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    sve:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


BASE_SOURCE_PATHS = (
    Path("tsldata/detail/flags.tsl"),
    Path("tsldata/detail/types.tsl"),
    Path("tsldata/detail/lane_sets.tsl"),
    Path("tsldata/extensions/extension.tsl"),
    Path("tsldata/detail/templates.tsl"),
)


def source_document(text: str, *, path: str = "rust-slice-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "rust-slice-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "rust-slice-fixture.tsl") -> Catalog:
    catalog = build_catalog(parse_text(text, path=path))
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


def catalog_from_paths(*paths: Path | str) -> Catalog:
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
    return catalog_from_paths(*BASE_SOURCE_PATHS)


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
    backend: str | None = "rust",
    extension_names: tuple[str, ...] = ("scalar",),
    cpu_flags: tuple[str, ...] = ("sse",),
) -> CandidateSelection:
    plan = plan_selection(
        referenced,
        SelectionRequest(
            backend=backend,
            primitive_names=("slice_add",),
            extension_names=extension_names,
            cpu_flags=cpu_flags,
            include_support_extensions=False,
        ),
    )
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


def rust_manifest_set(*, artifact_kind: str = "generated") -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id="rust",
                language_id="rust",
                artifacts=(
                    ArtifactSpec(
                        kind=artifact_kind,
                        logical_name="generated",
                        extension="rs",
                    ),
                ),
            ),
        )
    )


def render_simple_fixture(
    *,
    selection_backend: str | None = "rust",
    artifact_kind: str = "generated",
):
    referenced = catalog_with_primitive(SIMPLE_PRIMITIVE)
    selection = candidate_selection_for(referenced, backend=selection_backend)
    artifact_plan = build_artifact_plan(
        rust_manifest_set(artifact_kind=artifact_kind),
        "rust",
        selection,
    )
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return RustBackend().render(artifact_plan.unwrap(), selection)


def artifact_plan_for_selection(
    selection: CandidateSelection,
    *,
    plan_backend: str = "rust",
    descriptor_backend: str = "rust",
):
    descriptor = ArtifactDescriptor(
        backend_id=descriptor_backend,
        kind="generated",
        logical_path=PurePosixPath("generated.rs"),
        candidate_ids=tuple(candidate.candidate_id for candidate in selection.candidates),
    )
    artifact_plan = artifact_plan_from_descriptors(plan_backend, (descriptor,))
    if not artifact_plan.is_ok:
        raise AssertionError(artifact_plan.diagnostics)
    return artifact_plan.unwrap()


class RustBackendVerticalSliceTests(unittest.TestCase):
    def test_renders_minimal_rust_generated_artifact(self) -> None:
        result = render_simple_fixture()

        self.assertTrue(result.is_ok, result.diagnostics)
        artifact_set = result.unwrap()
        assert_artifact_set_matches_golden(
            self,
            artifact_set,
            (
                golden_artifact(
                    "generated.rs",
                    "golden",
                    "rust",
                    "minimal_generated.rs",
                ),
            ),
        )
        artifact = artifact_set.artifacts_by_path["generated.rs"]
        self.assertEqual(artifact.metadata["backend_id"], "rust")
        self.assertEqual(artifact.metadata["required_flags"], ("sse",))
        self.assertEqual(artifact.metadata["target_extensions"], ("scalar",))

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
        artifact = result.unwrap().artifacts_by_path["generated.rs"]
        self.assertEqual(artifact.metadata["backend_id"], "rust")
        self.assertIn('primitive: "slice_add"', artifact.content)

    def test_diagnoses_non_rust_artifact_plan(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, plan_backend="cpp")

        result = RustBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-RUST-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_non_rust_descriptor(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = artifact_plan_for_selection(selection, descriptor_backend="cpp")

        result = RustBackend().render(artifact_plan, selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-RUST-RENDER-BACKEND",
            severity="error",
        )

    def test_diagnoses_backend_mismatched_candidates(self) -> None:
        result = render_simple_fixture(selection_backend="cpp")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-RUST-RENDER-CANDIDATE-BACKEND",
            severity="error",
        )

    def test_diagnoses_unsupported_artifact_kind(self) -> None:
        result = render_simple_fixture(artifact_kind="metadata")

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-RUST-RENDER-UNSUPPORTED-ARTIFACT",
            severity="error",
        )

    def test_diagnoses_missing_candidate_reference(self) -> None:
        descriptor = ArtifactDescriptor(
            backend_id="rust",
            kind="generated",
            logical_path=PurePosixPath("generated.rs"),
            candidate_ids=("missing",),
        )
        artifact_plan = artifact_plan_from_descriptors("rust", (descriptor,))
        self.assertTrue(artifact_plan.is_ok, artifact_plan.diagnostics)
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))

        result = RustBackend().render(artifact_plan.unwrap(), selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-RUST-RENDER-MISSING-CANDIDATE",
            severity="error",
        )

    def test_rust_backend_support_filters_unsupported_extensions(self) -> None:
        referenced = catalog_with_primitive(SVE_PRIMITIVE)
        plan = plan_selection(
            referenced,
            SelectionRequest(
                backend="rust",
                primitive_names=("slice_add",),
                extension_names=("sve",),
                include_support_extensions=False,
            ),
        )
        self.assertTrue(plan.is_ok, plan.diagnostics)

        candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)

        self.assertFalse(candidates.is_ok)
        assert_diagnostic(
            self,
            candidates.diagnostics[0],
            code="TSL-CANDIDATE-NONE",
            severity="error",
        )

    def test_registry_diagnoses_unknown_backend_renderer(self) -> None:
        selection = candidate_selection_for(catalog_with_primitive(SIMPLE_PRIMITIVE))
        artifact_plan = build_artifact_plan(rust_manifest_set(), "rust", selection)
        self.assertTrue(artifact_plan.is_ok, artifact_plan.diagnostics)

        result = BackendRegistry(()).render("rust", artifact_plan.unwrap(), selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-RENDERER-UNKNOWN",
            severity="error",
        )

    def test_rust_manifest_template_policy_fields_are_preserved(self) -> None:
        result = parse_backend_manifest_text(
            """version: 1
backend: rust
artifact:
  name: generated
  extension: rs
primary:
  default: primary.j2
  fallback: "{template}_primary.j2"
specialization:
  default: specialization.j2
wrappers: wrappers.j2
tsl_trait: tsl_trait.j2
"""
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        manifest = result.unwrap()
        self.assertEqual(manifest.artifacts[0].target_path.as_posix(), "generated.rs")
        self.assertEqual(manifest.template_policy.primary_fallback, "{template}_primary.j2")
        self.assertEqual(manifest.template_policy.trait, "tsl_trait.j2")

    def test_api_loads_manifest_path_and_dispatches_to_rust_renderer(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_rust_slice.tsl"
            manifest_path = temp_path / "backend_rust.yaml"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path.write_text(
                """version: 1
backend: rust
artifact:
  name: generated
  extension: rs
""",
                encoding="utf-8",
            )
            config = PipelineConfig(
                source_config=SourceConfig(
                    explicit_paths=(*BASE_SOURCE_PATHS, primitive_path),
                    include_standard_library=False,
                ),
                selection_request=SelectionRequest(
                    backend="rust",
                    primitive_names=("slice_add",),
                    extension_names=("scalar",),
                    cpu_flags=("sse",),
                    include_support_extensions=False,
                ),
                backend_manifest_paths=(manifest_path,),
                render_backend="rust",
            )

            result = run_pipeline(config)

            self.assertTrue(result.is_ok, result.diagnostics)
            self.assertIsNotNone(result.artifacts)
            assert result.artifacts is not None
            self.assertEqual(
                tuple(
                    artifact.logical_path.as_posix()
                    for artifact in result.artifacts.artifacts
                ),
                ("generated.rs",),
            )
            self.assertEqual(
                tuple(sorted(path.name for path in temp_path.iterdir())),
                ("api_rust_slice.tsl", "backend_rust.yaml"),
            )


if __name__ == "__main__":
    unittest.main()
