from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection
from tslgen.analysis.selection import SelectionPlan, SelectionRequest
from tslgen.config.model import SourceConfig
from tslgen.domain.backends import (
    ArtifactSpec,
    BackendManifest,
    BackendManifestSet,
)
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.manifests import backend_manifests_from_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.backend_metadata import (
    backend_metadata_from_catalog,
    validate_backend_metadata_boundary,
)


def source_document(
    text: str,
    *,
    path: str = "backend-metadata-fixture.tsl",
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
    path: str = "backend-metadata-fixture.tsl",
) -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(
    text: str,
    *,
    path: str = "backend-metadata-fixture.tsl",
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


def manifest(
    backend_id: str,
    *,
    language_id: str | None = None,
    extension: str | None = None,
) -> BackendManifest:
    return BackendManifest(
        version=1,
        backend_id=backend_id,
        language_id=language_id or backend_id,
        artifacts=(
            ArtifactSpec(
                kind="generated",
                logical_name="generated",
                extension=extension or ("rs" if backend_id == "rust" else "hpp"),
            ),
        ),
    )


def empty_selection(backend: str = "cpp") -> CandidateSelection:
    return CandidateSelection(
        plan=SelectionPlan(
            request=SelectionRequest(backend=backend),
            variants=(),
            allowed_extensions=(),
            normalized_cpu_flags=(),
            implementation_plans=(),
        ),
        candidates=(),
    )


class BackendMetadataBoundaryTests(unittest.TestCase):
    def test_current_cpp_and_rust_metadata_promotes_to_typed_boundary(self) -> None:
        catalog = catalog_from_paths(
            "tsldata/detail/lang/types/types_cpp.tsl",
            "tsldata/detail/lang/types/types_c17.tsl",
            "tsldata/detail/lang/types/types_rust.tsl",
            "tsldata/detail/lang/translate_cpp.tsl",
            "tsldata/detail/lang/translate_c17.tsl",
            "tsldata/detail/lang/translate_rust.tsl",
        )

        metadata = backend_metadata_from_catalog(catalog)
        self.assertTrue(metadata.is_ok, metadata.diagnostics)
        metadata_value = metadata.unwrap()
        self.assertEqual(
            tuple(item.backend_id for item in metadata_value.language_maps),
            ("c17", "cpp", "rust"),
        )
        self.assertEqual(
            metadata_value.language_maps_by_backend["cpp"]
            .entries_by_type["s32"]
            .target_type,
            "int32_t",
        )
        self.assertEqual(
            metadata_value.language_maps_by_backend["rust"]
            .entries_by_type["s32"]
            .target_type,
            "i32",
        )
        self.assertEqual(
            metadata_value.translation_maps_by_backend["cpp"]
            .snippets_by_name["emit_return"]
            .template,
            "return {value}",
        )

        boundary = validate_backend_metadata_boundary(
            BackendManifestSet((manifest("cpp"), manifest("rust"))),
            metadata_value,
        )

        self.assertTrue(boundary.is_ok, boundary.diagnostics)
        self.assertEqual(boundary.unwrap().active_backend_ids, ("cpp", "rust"))

    def test_manifest_boundary_requires_language_map(self) -> None:
        catalog = catalog_from_text(
            """translation cpp:
  emit_return "return {value}"
"""
        )
        metadata = backend_metadata_from_catalog(catalog)
        self.assertTrue(metadata.is_ok, metadata.diagnostics)

        result = validate_backend_metadata_boundary(
            BackendManifestSet((manifest("cpp"),)),
            metadata.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-METADATA-MISSING-LANGUAGE",
            severity="error",
        )

    def test_manifest_boundary_requires_translation_map(self) -> None:
        catalog = catalog_from_text(
            """language rust:
  s32 {type "i32"}
"""
        )
        metadata = backend_metadata_from_catalog(catalog)
        self.assertTrue(metadata.is_ok, metadata.diagnostics)

        result = validate_backend_metadata_boundary(
            BackendManifestSet((manifest("rust"),)),
            metadata.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-METADATA-MISSING-TRANSLATION",
            severity="error",
        )

    def test_unsupported_manifest_backend_is_diagnostic(self) -> None:
        catalog = catalog_from_text(
            """language c17:
  s32 {type "int32_t"}
translation c17:
  emit_return "return {value}"
"""
        )
        metadata = backend_metadata_from_catalog(catalog)
        self.assertTrue(metadata.is_ok, metadata.diagnostics)

        result = validate_backend_metadata_boundary(
            BackendManifestSet((manifest("c17", extension="h"),)),
            metadata.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-METADATA-UNSUPPORTED-BACKEND",
            severity="error",
        )

    def test_manifest_language_id_must_be_active_and_mapped(self) -> None:
        catalog = catalog_from_text(
            """language cpp:
  s32 {type "int32_t"}
translation cpp:
  emit_return "return {value}"
"""
        )
        metadata = backend_metadata_from_catalog(catalog)
        self.assertTrue(metadata.is_ok, metadata.diagnostics)

        result = validate_backend_metadata_boundary(
            BackendManifestSet((manifest("cpp", language_id="zig"),)),
            metadata.unwrap(),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            tuple(diagnostic.code for diagnostic in result.diagnostics),
            (
                "TSL-BACKEND-METADATA-MISSING-LANGUAGE",
                "TSL-BACKEND-METADATA-UNSUPPORTED-LANGUAGE",
            ),
        )

    def test_language_and_translation_shapes_are_diagnostics(self) -> None:
        catalog = catalog_from_text(
            """language cpp:
  s32 "int32_t"
translation cpp:
  emit_return {type "return {value}"}
"""
        )

        result = backend_metadata_from_catalog(catalog)

        self.assertFalse(result.is_ok)
        self.assertEqual(
            tuple(diagnostic.code for diagnostic in result.diagnostics),
            (
                "TSL-BACKEND-LANGUAGE-MAP-EMPTY",
                "TSL-BACKEND-LANGUAGE-MAP-SHAPE",
                "TSL-BACKEND-TRANSLATION-MAP-EMPTY",
                "TSL-BACKEND-TRANSLATION-MAP-SHAPE",
            ),
        )

    def test_catalog_manifest_derivation_keeps_c17_deferred(self) -> None:
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
        self.assertEqual(manifests.unwrap().backend_ids, ("cpp", "rust"))

    def test_catalog_manifest_derivation_diagnoses_unknown_backend_id(self) -> None:
        catalog = catalog_from_text(
            """language zig:
  s32 {type "i32"}
translation zig:
  emit_return "return {value}"
"""
        )

        result = backend_manifests_from_catalog(catalog)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-BACKEND-MANIFEST-UNSUPPORTED-BACKEND",
            severity="error",
        )

    def test_artifact_planning_rejects_inactive_backend_before_rendering(self) -> None:
        result = build_artifact_plan(
            BackendManifestSet((manifest("c17", extension="h"),)),
            "c17",
            empty_selection("c17"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-ARTIFACT-UNSUPPORTED-BACKEND",
            severity="error",
        )

    def test_artifact_planning_rejects_inactive_language_id(self) -> None:
        result = build_artifact_plan(
            BackendManifestSet((manifest("cpp", language_id="zig"),)),
            "cpp",
            empty_selection("cpp"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-ARTIFACT-UNSUPPORTED-LANGUAGE",
            severity="error",
        )


if __name__ == "__main__":
    unittest.main()
