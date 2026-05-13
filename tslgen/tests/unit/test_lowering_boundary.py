from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    GenerationContext,
    GenerationTypeRef,
    LoweringRequest,
    PrunedGenerationBranch,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilPrimitiveAttributeCondition,
    TsilReturnStatement,
    TsilTypeSignednessCondition,
    lower_candidates,
    prepare_lowering_inputs,
    resolve_generation_type_query,
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
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_unselected_helper_si32(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else<generation> { emit_return(value<generation>(vector::length)); }"

prim<v:=(v,v)> lower_generation_signedness_unselected_helper_ui32(left, right):
  tests []
  impls:
    scalar:
      ui32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(value<generation>(vector::length)); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_selected_helper(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(value<generation>(vector::length)); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_unsupported_predicate(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_integral(type<generation>(base::in)))) { emit_return(left + right); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_nested_type(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::signed_of(type<generation>(vector::register)))))) { emit_return(left + right); } else<generation> { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_unselected_helper_si32(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else { emit_return(value<generation>(vector::length)); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_unselected_helper_ui32(left, right):
  tests []
  impls:
    scalar:
      ui32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(value<generation>(vector::length)); } else { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_selected_helper(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(value<generation>(vector::length)); } else { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_unsupported_predicate(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_integral(type<generation>(base::in)))) { emit_return(left + right); } else { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_nested_type(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::signed_of(type<generation>(vector::register)))))) { emit_return(left + right); } else { emit_return(right + left); }"

prim<v:=(v,v)> lower_generation_signedness_plain_else_malformed(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { emit_return(left + right); } else emit_return(right + left);"

prim<v:=(v,v)> lower_generation_type_base(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "type<generation>(base::in)"

prim<v:=(v,v)> lower_generation_type_signed(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "type<generation>(base::signed_of(type<generation>(base::in)))"

prim<v:=(v,v)> lower_generation_type_unsigned(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "type<generation>(base::unsigned_of(type<generation>(base::in)))"

prim<v:=(v,v)> lower_generation_type_override(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "type<generation>(base::in)"

prim<v:=ptr>[aligned=true] lower_generation_aligned_true(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(aligned))) { emit_return(ptr + ptr); } else<generation> { emit_return(value<generation>(vector::length)); }"

prim<v:=ptr>[aligned=false] lower_generation_aligned_false(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(aligned))) { emit_return(value<generation>(vector::length)); } else<generation> { emit_return(intrin_compose<add>(ptr, ptr)); }"

prim<v:=ptr>[aligned=true] lower_generation_selected_branch_helper(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(aligned))) { emit_return(value<generation>(vector::length)); } else<generation> { emit_return(ptr + ptr); }"

prim<v:=ptr>[aligned=true] lower_generation_unknown_attribute(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(unknown))) { emit_return(ptr + ptr); } else<generation> { emit_return(ptr + ptr); }"

prim<v:=ptr>[aligned=true] lower_generation_malformed_branch(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(aligned))) { emit_return(ptr + ptr); }"

prim<v:=ptr>[aligned=true] lower_generation_aligned_plain_else(ptr):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(primitive::attribute(aligned))) { emit_return(ptr + ptr); } else { emit_return(ptr + ptr); }"

prim<v:=(v,v)> lower_subtract(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left - right);"

prim<v:=(v,v)> lower_bad_return(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left +);"

prim<v:=(v,v)> lower_unknown_name(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + missing);"

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

prim<v:=(v,v)> lower_intrin_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left, right));"

prim<v:=(v,v)> lower_intrin_sub(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<sub>(left, right));"

prim<v:=(v,v)> lower_intrin_one_arg(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left));"

prim<v:=(v,v)> lower_intrin_three_args(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left, right, extra));"

prim<v:=(v,v)> lower_intrin_unknown(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left, missing));"

prim<v:=(v,v)> lower_intrin_expression_arg(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left + right));"

prim<v:=(v,v)> lower_intrin_nested(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(intrin_compose<add>(left, right), right));"

prim<v:=(v,v)> lower_intrin_malformed(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(intrin_compose<add>(left, right);"

prim<v:=(v,v)> lower_call(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(foo(left, right));"
"""


class LoweringBoundaryTests(unittest.TestCase):
    def selection_for(self, primitive_name: str) -> CandidateSelection:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        return candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=(primitive_name,),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

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

    def test_lowers_base_generation_type_query_for_si32_and_ui32(self) -> None:
        selection = self.selection_for("lower_generation_type_base")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            (
                GenerationTypeRef(kind="base.in", type_tag="si32"),
                GenerationTypeRef(kind="base.in", type_tag="ui32"),
            ),
        )

    def test_lowers_signed_generation_type_query_for_si32_and_ui32(self) -> None:
        selection = self.selection_for("lower_generation_type_signed")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            (
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="si32",
                ),
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="ui32",
                ),
            ),
        )

    def test_lowers_unsigned_generation_type_query_for_si32_and_ui32(self) -> None:
        selection = self.selection_for("lower_generation_type_unsigned")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            (
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag="ui32",
                    source_type_tag="si32",
                ),
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag="ui32",
                    source_type_tag="ui32",
                ),
            ),
        )

    def test_generation_type_query_defaults_to_selected_candidate_type_tag(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_type_override")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().implementations[0].generation_type_refs,
            (GenerationTypeRef(kind="base.in", type_tag="si32"),),
        )

    def test_generation_type_query_uses_explicit_type_tag_override(self) -> None:
        selection = self.selection_for("lower_generation_type_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(type_tag_override="ui32"),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().implementations[0].generation_type_refs,
            (GenerationTypeRef(kind="base.in", type_tag="ui32"),),
        )

    def test_generation_type_query_reports_missing_type_context(self) -> None:
        selection = self.selection_for("lower_generation_type_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(use_candidate_type_tag=False),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-CONTEXT-MISSING",
            severity="error",
        )

    def test_generation_type_query_lowering_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_type_unsigned")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_resolves_generation_type_query_with_explicit_context(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::unsigned_of(type<generation>(base::in)))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap(),
            GenerationTypeRef(
                kind="base.unsigned_of",
                type_tag="ui32",
                source_type_tag="si32",
            ),
        )

    def test_generation_type_query_reports_unsupported_shorthand(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::signed_of(base::in))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("shorthand", result.diagnostics[0].message)
        self.assertIn("type<generation>(base::in)", result.diagnostics[0].message)

    def test_generation_type_query_reports_unsupported_tags(self) -> None:
        cases = (
            ("f32", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
        )
        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_type_query(
                    "type<generation>(base::in)",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

    def test_generation_type_query_reports_non_integer_companion_tag(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::signed_of(type<generation>(base::in)))",
            GenerationContext(type_tag_override="f32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-NON-INTEGER",
            severity="error",
        )
        self.assertIn("f32", result.diagnostics[0].message)

    def test_generation_type_query_reports_unknown_type_tag(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::in)",
            GenerationContext(type_tag_override="mystery"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-TAG-UNKNOWN",
            severity="error",
        )
        self.assertIn("mystery", result.diagnostics[0].message)

    def test_generation_type_query_reports_malformed_query(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::in",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-MALFORMED",
            severity="error",
        )

    def test_generation_type_query_reports_unsupported_nested_query(self) -> None:
        result = resolve_generation_type_query(
            "type<generation>(base::signed_of(type<generation>(vector::register)))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("vector::register", result.diagnostics[0].message)

    def test_prunes_signedness_generation_branch_for_si32_and_ui32(self) -> None:
        selection = self.selection_for("lower_generation_signedness")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), 2)
        self.assertEqual(
            tuple(implementation.statements for implementation in implementations),
            (
                (
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("left"),
                            right=TsilParameterReference("right"),
                        )
                    ),
                ),
                (
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("right"),
                            right=TsilParameterReference("left"),
                        )
                    ),
                ),
            ),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0]
                for implementation in implementations
            ),
            (
                PrunedGenerationBranch(
                    condition=TsilTypeSignednessCondition(
                        GenerationTypeRef(kind="base.in", type_tag="si32")
                    ),
                    selected_branch="true",
                    statement_text="emit_return(left + right);",
                    condition_location=selection.candidates[
                        0
                    ].variant.source.declaration.source_span.location,
                ),
                PrunedGenerationBranch(
                    condition=TsilTypeSignednessCondition(
                        GenerationTypeRef(kind="base.in", type_tag="ui32")
                    ),
                    selected_branch="false",
                    statement_text="emit_return(right + left);",
                    condition_location=selection.candidates[
                        1
                    ].variant.source.declaration.source_span.location,
                ),
            ),
        )

    def test_signedness_generation_branch_pruning_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_signedness")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_signedness_unselected_branch_helper_does_not_poison_selection(
        self,
    ) -> None:
        for primitive_name in (
            "lower_generation_signedness_unselected_helper_si32",
            "lower_generation_signedness_unselected_helper_ui32",
        ):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertTrue(result.is_ok, result.diagnostics)

    def test_signedness_selected_branch_helper_reports_diagnostic(self) -> None:
        selection = self.selection_for("lower_generation_signedness_selected_helper")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH",
            severity="error",
        )
        self.assertIn("value<generation>", result.diagnostics[0].message)

    def test_signedness_generation_branch_reports_missing_type_context(self) -> None:
        selection = self.selection_for("lower_generation")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(use_candidate_type_tag=False),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-CONTEXT-MISSING",
            severity="error",
        )

    def test_signedness_generation_branch_reports_unsupported_type_tags(self) -> None:
        selection = self.selection_for("lower_generation")
        cases = (
            ("f32", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("mystery", "TSL-LOWER-GEN-TYPE-TAG-UNKNOWN"),
        )

        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = lower_candidates(
                    selection,
                    LoweringRequest(
                        generation_context=GenerationContext(
                            type_tag_override=type_tag,
                        ),
                    ),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

    def test_signedness_generation_branch_reports_unsupported_predicate(self) -> None:
        selection = self.selection_for("lower_generation_signedness_unsupported_predicate")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-IF-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("type::is_integral", result.diagnostics[0].message)

    def test_signedness_generation_branch_reports_unsupported_nested_type(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_signedness_nested_type")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("vector::register", result.diagnostics[0].message)

    def test_prunes_plain_else_signedness_generation_branch_for_si32_and_ui32(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_signedness_plain_else")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), 2)
        self.assertEqual(
            tuple(implementation.statements for implementation in implementations),
            (
                (
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("left"),
                            right=TsilParameterReference("right"),
                        )
                    ),
                ),
                (
                    TsilReturnStatement(
                        TsilBinaryExpression(
                            operator="+",
                            left=TsilParameterReference("right"),
                            right=TsilParameterReference("left"),
                        )
                    ),
                ),
            ),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0].else_syntax
                for implementation in implementations
            ),
            ("else", "else"),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0].selected_branch
                for implementation in implementations
            ),
            ("true", "false"),
        )

    def test_plain_else_signedness_branch_pruning_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_signedness_plain_else")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_plain_else_signedness_unselected_branch_helper_is_ignored(
        self,
    ) -> None:
        for primitive_name in (
            "lower_generation_signedness_plain_else_unselected_helper_si32",
            "lower_generation_signedness_plain_else_unselected_helper_ui32",
        ):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertTrue(result.is_ok, result.diagnostics)

    def test_plain_else_signedness_selected_branch_helper_reports_diagnostic(
        self,
    ) -> None:
        selection = self.selection_for(
            "lower_generation_signedness_plain_else_selected_helper"
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH",
            severity="error",
        )
        self.assertIn("value<generation>", result.diagnostics[0].message)

    def test_plain_else_signedness_branch_reports_missing_type_context(self) -> None:
        selection = self.selection_for("lower_generation_signedness_plain_else")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(use_candidate_type_tag=False),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-CONTEXT-MISSING",
            severity="error",
        )

    def test_plain_else_signedness_branch_reports_unsupported_type_tags(self) -> None:
        selection = self.selection_for("lower_generation_signedness_plain_else")
        cases = (
            ("f32", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("mystery", "TSL-LOWER-GEN-TYPE-TAG-UNKNOWN"),
        )

        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = lower_candidates(
                    selection,
                    LoweringRequest(
                        generation_context=GenerationContext(
                            type_tag_override=type_tag,
                        ),
                    ),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

    def test_plain_else_signedness_branch_reports_unsupported_predicate(self) -> None:
        selection = self.selection_for(
            "lower_generation_signedness_plain_else_unsupported_predicate"
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-IF-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("type::is_integral", result.diagnostics[0].message)

    def test_plain_else_signedness_branch_reports_unsupported_nested_type(
        self,
    ) -> None:
        selection = self.selection_for(
            "lower_generation_signedness_plain_else_nested_type"
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("vector::register", result.diagnostics[0].message)

    def test_plain_else_signedness_branch_reports_malformed_syntax(self) -> None:
        selection = self.selection_for(
            "lower_generation_signedness_plain_else_malformed"
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-IF-MALFORMED",
            severity="error",
        )

    def test_plain_else_generation_branch_rejects_primitive_attribute_form(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_aligned_plain_else")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-IF-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("plain 'else'", result.diagnostics[0].message)

    def test_prunes_generation_branch_when_aligned_true(self) -> None:
        selection = self.selection_for("lower_generation_aligned_true")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(
            implementation.statements,
            (
                TsilReturnStatement(
                    TsilBinaryExpression(
                        operator="+",
                        left=TsilParameterReference("ptr"),
                        right=TsilParameterReference("ptr"),
                    )
                ),
            ),
        )
        self.assertEqual(len(implementation.generation_branches), 1)
        branch = implementation.generation_branches[0]
        self.assertEqual(
            branch.condition,
            TsilPrimitiveAttributeCondition("aligned"),
        )
        self.assertEqual(branch.selected_branch, "true")
        self.assertEqual(branch.statement_text, "emit_return(ptr + ptr);")

    def test_prunes_generation_branch_when_aligned_false(self) -> None:
        selection = self.selection_for("lower_generation_aligned_false")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(
            implementation.statements,
            (
                TsilReturnStatement(
                    TsilIntrinsicComposeExpression(
                        intrinsic="add",
                        arguments=(
                            TsilParameterReference("ptr"),
                            TsilParameterReference("ptr"),
                        ),
                    )
                ),
            ),
        )
        self.assertEqual(len(implementation.generation_branches), 1)
        self.assertEqual(
            implementation.generation_branches[0],
            PrunedGenerationBranch(
                condition=TsilPrimitiveAttributeCondition("aligned"),
                selected_branch="false",
                statement_text="emit_return(intrin_compose<add>(ptr, ptr));",
                condition_location=selection.candidates[
                    0
                ].variant.source.declaration.source_span.location,
            ),
        )

    def test_generation_branch_pruning_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_aligned_true")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_unselected_branch_generation_helper_does_not_poison_selection(
        self,
    ) -> None:
        for primitive_name in (
            "lower_generation_aligned_true",
            "lower_generation_aligned_false",
        ):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertTrue(result.is_ok, result.diagnostics)

    def test_selected_branch_generation_helper_reports_diagnostic(self) -> None:
        selection = self.selection_for("lower_generation_selected_branch_helper")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH",
            severity="error",
        )
        self.assertIn("value<generation>", result.diagnostics[0].message)

    def test_reports_missing_aligned_attribute(self) -> None:
        selection = self.selection_for("lower_generation_aligned_true")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    primitive_attributes=FrozenMap.empty(),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-ATTRIBUTE-MISSING",
            severity="error",
        )

    def test_reports_non_boolean_aligned_attribute(self) -> None:
        selection = self.selection_for("lower_generation_aligned_true")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    primitive_attributes=FrozenMap({"aligned": "maybe"}),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-ATTRIBUTE-TYPE",
            severity="error",
        )
        self.assertIn("maybe", result.diagnostics[0].message)

    def test_reports_unknown_primitive_attribute_condition(self) -> None:
        selection = self.selection_for("lower_generation_unknown_attribute")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-ATTRIBUTE-UNKNOWN",
            severity="error",
        )
        self.assertIn("unknown", result.diagnostics[0].message)

    def test_reports_malformed_generation_branch(self) -> None:
        selection = self.selection_for("lower_generation_malformed_branch")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-IF-MALFORMED",
            severity="error",
        )

    def test_reports_missing_generation_context(self) -> None:
        selection = self.selection_for("lower_generation_aligned_true")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(use_candidate_attributes=False),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-CONTEXT-MISSING",
            severity="error",
        )

    def test_lowers_direct_parameter_add_return(self) -> None:
        selection = self.selection_for("lower_add")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        self.assertEqual(plan.request.strategy, "mini_tsil")
        self.assertEqual(len(plan.implementations), 1)
        implementation = plan.implementations[0]
        self.assertEqual(implementation.status, "lowered")
        self.assertEqual(implementation.candidate_id, selection.candidates[0].candidate_id)
        self.assertEqual(
            implementation.statements,
            (
                TsilReturnStatement(
                    TsilBinaryExpression(
                        operator="+",
                        left=TsilParameterReference("left"),
                        right=TsilParameterReference("right"),
                    )
                ),
            ),
        )

    def test_lowers_intrinsic_compose_add_return(self) -> None:
        selection = self.selection_for("lower_intrin_add")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(implementation.status, "lowered")
        self.assertEqual(implementation.candidate_id, selection.candidates[0].candidate_id)
        self.assertEqual(
            implementation.statements,
            (
                TsilReturnStatement(
                    TsilIntrinsicComposeExpression(
                        intrinsic="add",
                        arguments=(
                            TsilParameterReference("left"),
                            TsilParameterReference("right"),
                        ),
                    )
                ),
            ),
        )

    def test_intrinsic_compose_lowering_is_deterministic(self) -> None:
        selection = self.selection_for("lower_intrin_add")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_typed_opaque_strategy_reports_intrinsic_compose_tsil_as_unsupported(
        self,
    ) -> None:
        selection = self.selection_for("lower_intrin_add")

        result = lower_candidates(
            selection,
            LoweringRequest(strategy="typed_opaque", backend_id="cpp"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-UNSUPPORTED",
            severity="error",
        )

    def test_typed_opaque_strategy_still_reports_tsil_as_unsupported(self) -> None:
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

        result = lower_candidates(
            selection,
            LoweringRequest(strategy="typed_opaque", backend_id="cpp"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-UNSUPPORTED",
            severity="error",
        )

    def test_reports_unsupported_generation_time_condition(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_generation_signedness_unsupported_predicate",),
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
            code="TSL-LOWER-GEN-IF-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("type::is_integral", diagnostic.message)

    def test_reports_unsupported_nearby_return_form(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_subtract",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-RETURN-SHAPE",
            severity="error",
        )

    def test_reports_malformed_direct_return_form(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_bad_return",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-RETURN-SHAPE",
            severity="error",
        )

    def test_reports_unsupported_intrinsic_compose_name(self) -> None:
        selection = self.selection_for("lower_intrin_sub")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-INTRIN-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("'sub'", result.diagnostics[0].message)

    def test_reports_wrong_intrinsic_compose_arity(self) -> None:
        for primitive_name in ("lower_intrin_one_arg", "lower_intrin_three_args"):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-TSIL-INTRIN-ARITY",
                    severity="error",
                )

    def test_reports_unknown_intrinsic_compose_operand(self) -> None:
        selection = self.selection_for("lower_intrin_unknown")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
            severity="error",
        )

    def test_reports_intrinsic_compose_expression_argument(self) -> None:
        selection = self.selection_for("lower_intrin_expression_arg")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-INTRIN-ARGUMENT",
            severity="error",
        )

    def test_reports_malformed_or_nested_intrinsic_compose(self) -> None:
        for primitive_name in ("lower_intrin_malformed", "lower_intrin_nested"):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-TSIL-INTRIN-MALFORMED",
                    severity="error",
                )

    def test_reports_general_call_form_as_unsupported_return_shape(self) -> None:
        selection = self.selection_for("lower_call")

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-RETURN-SHAPE",
            severity="error",
        )

    def test_reports_unknown_parameter_in_direct_return_form(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=("lower_unknown_name",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
            severity="error",
        )

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

    def test_lowered_results_are_deterministic(self) -> None:
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

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_lowering_diagnostics_are_deterministic(self) -> None:
        referenced = reference_validated(catalog_with_primitives(LOWERING_FIXTURE))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                backend="cpp",
                primitive_names=(
                    "lower_generation_signedness_unsupported_predicate",
                    "lower_intrinsic",
                ),
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
            ("TSL-LOWER-GEN-IF-UNSUPPORTED", "TSL-LOWER-PAYLOAD-UNSUPPORTED"),
        )


if __name__ == "__main__":
    unittest.main()
