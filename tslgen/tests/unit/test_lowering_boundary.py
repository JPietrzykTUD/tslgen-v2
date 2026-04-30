from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    LoweringRequest,
    lower_candidates,
    prepare_lowering_inputs,
)
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "lowering-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "lowering-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "lowering-fixture.tsl") -> Catalog:
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


LOWERING_FIXTURE = """prim<v:=(v,v)> lower_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"

prim<v:=(v,v)> lower_generation(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(vector::length) > 4) { emit_return(left); }"

prim<v:=(v,v)> lower_intrinsic(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          intrinsic "_mm_add_epi32"

prim<v:=(v,v)> lower_bad_tsil(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil [1, 2]
"""


class LoweringBoundaryTests(unittest.TestCase):
    def test_prepares_typed_lowering_inputs_from_selected_candidates(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = prepare_lowering_inputs(
            selection,
            LoweringRequest(backend_id="cpp"),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        input_set = result.unwrap()
        self.assertEqual(input_set.request.backend_id, "cpp")
        self.assertEqual(len(input_set.inputs), 1)
        lowering_input = input_set.inputs[0]
        self.assertIs(lowering_input.candidate, selection.candidates[0])
        self.assertEqual(lowering_input.payload.body_kind, "tsil")
        self.assertEqual(lowering_input.payload.classification, "tsil")
        self.assertEqual(lowering_input.payload.text, "emit_return(left + right);")
        self.assertFalse(lowering_input.payload.has_generation_condition)

    def test_classifies_generation_time_conditions_without_evaluating_them(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_generation",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = prepare_lowering_inputs(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        lowering_input = result.unwrap().inputs[0]
        self.assertEqual(lowering_input.payload.classification, "tsil")
        self.assertTrue(lowering_input.payload.has_generation_condition)

    def test_reports_unsupported_tsil_without_silently_lowering(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_add",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-UNSUPPORTED",
            severity="error",
            path="lowering-fixture.tsl",
            line=1,
            column=1,
        )

    def test_reports_generation_time_conditions_as_deferred_lowering_work(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_generation",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-LOWER-TSIL-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("generation-time conditions", diagnostic.message)

    def test_classifies_and_reports_non_tsil_payloads_as_unsupported(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_intrinsic",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        prepared = prepare_lowering_inputs(selection)
        lowered = lower_candidates(selection)

        self.assertTrue(prepared.is_ok, prepared.diagnostics)
        self.assertEqual(prepared.unwrap().inputs[0].payload.classification, "intrinsic")
        self.assertFalse(lowered.is_ok)
        assert_diagnostic(
            self,
            lowered.diagnostics[0],
            code="TSL-LOWER-PAYLOAD-UNSUPPORTED",
            severity="error",
        )

    def test_rejects_malformed_tsil_payload_shape_before_lowering(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_bad_tsil",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = prepare_lowering_inputs(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PAYLOAD-SHAPE",
            severity="error",
        )

    def test_lowering_diagnostics_are_deterministic(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_add", "lower_intrinsic"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertFalse(first.is_ok)
        self.assertFalse(second.is_ok)
        self.assertEqual(first.diagnostics, second.diagnostics)
        self.assertEqual(
            tuple(diagnostic.code for diagnostic in first.diagnostics),
            ("TSL-LOWER-TSIL-UNSUPPORTED", "TSL-LOWER-PAYLOAD-UNSUPPORTED"),
        )


if __name__ == "__main__":
    unittest.main()
