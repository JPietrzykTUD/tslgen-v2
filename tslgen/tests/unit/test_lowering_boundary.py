from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.generation_rules import (
    build_concrete_integer_generation_rule_set,
    build_scalar_size_bytes_generation_rule_set,
)
from tslgen.domain.types import TypeGroup
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    GenerationContext,
    GenerationExpressionRecognition,
    GenerationLoweringStage,
    GenerationPredicate,
    GenerationSizeByteBranchChainArm,
    GenerationSizeByteBranchChainPruning,
    GenerationTypeRef,
    GenerationValue,
    LoweringRequest,
    PrunedGenerationBranch,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilPrimitiveAttributeCondition,
    TsilReturnStatement,
    TsilTypeSignednessCondition,
    build_catalog_lowering_request,
    lower_candidates,
    prepare_lowering_inputs,
    resolve_generation_predicate_query,
    resolve_generation_type_query,
    resolve_generation_value_query,
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


def catalog_with_type_groups(
    catalog: Catalog,
    type_groups: tuple[TypeGroup, ...],
) -> Catalog:
    return Catalog(
        type_groups=type_groups,
        lane_sets=catalog.lane_sets,
        extensions=catalog.extensions,
        templates=catalog.templates,
        primitives=catalog.primitives,
        entries=catalog.entries,
        source_metadata=catalog.source_metadata,
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
      ?i?:
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
      ?i?:
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
      ?i?:
        requires []
        implementation:
          tsil "type<generation>(base::in)"

prim<v:=(v,v)> lower_generation_type_signed(left, right):
  tests []
  impls:
    scalar:
      ?i?:
        requires []
        implementation:
          tsil "type<generation>(base::signed_of(type<generation>(base::in)))"

prim<v:=(v,v)> lower_generation_type_unsigned(left, right):
  tests []
  impls:
    scalar:
      ?i?:
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

prim<v:=(v,v)> lower_generation_size_bytes(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))"

prim<v:=(v,v)> lower_generation_size_bytes_override(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))"

prim<v:=(v,v)> lower_generation_size_bits(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))*8"

prim<v:=(v,v)> lower_generation_size_bits_override(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in)))*8"

prim<v:=(v,v)> lower_generation_size_byte_equals_2(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in))) == 2"

prim<v:=(v,v)> lower_generation_size_byte_equals_4(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in))) == 4"

prim<v:=(v,v)> lower_generation_size_byte_equals_8(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in))) == 8"

prim<v:=(v,v)> lower_generation_size_byte_equals_override(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "value<generation>(type::size_bytes(type<generation>(base::in))) == 8"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { pg = intrin<svptrue_b64>(); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_body_helpers(left, right):
  tests []
  impls:
    scalar:
      arith:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { emit_return(value<generation>(vector::length)); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { emit_return(value<generation>(vector::length)); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { emit_return(value<generation>(vector::length)); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_missing_arm(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_reordered(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { pg = intrin<svptrue_b64>(); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_duplicate(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32_again>(); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_final_else(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { pg = intrin<svptrue_b64>(); } else { pg = intrin<svptrue_b8>(); }"

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

CONCRETE_INTEGER_TAGS = (
    "si8",
    "ui8",
    "si16",
    "ui16",
    "si32",
    "ui32",
    "si64",
    "ui64",
)
CONCRETE_INTEGER_LOWERING_ORDER = (
    "si16",
    "si32",
    "si64",
    "si8",
    "ui16",
    "ui32",
    "ui64",
    "ui8",
)
SIGNED_COMPANION_BY_TAG = {
    "si8": "si8",
    "ui8": "si8",
    "si16": "si16",
    "ui16": "si16",
    "si32": "si32",
    "ui32": "si32",
    "si64": "si64",
    "ui64": "si64",
}
UNSIGNED_COMPANION_BY_TAG = {
    "si8": "ui8",
    "ui8": "ui8",
    "si16": "ui16",
    "ui16": "ui16",
    "si32": "ui32",
    "ui32": "ui32",
    "si64": "ui64",
    "ui64": "ui64",
}
IS_SIGNED_BY_TAG = {
    "si8": True,
    "ui8": False,
    "si16": True,
    "ui16": False,
    "si32": True,
    "ui32": False,
    "si64": True,
    "ui64": False,
}
SCALAR_SIZE_BYTES_BY_TAG = {
    "si8": 1,
    "ui8": 1,
    "si16": 2,
    "ui16": 2,
    "si32": 4,
    "ui32": 4,
    "f32": 4,
    "si64": 8,
    "ui64": 8,
    "f64": 8,
}
SCALAR_SIZE_BITS_BY_TAG = {
    type_tag: size_bytes * 8
    for type_tag, size_bytes in SCALAR_SIZE_BYTES_BY_TAG.items()
}
SIZE_BYTE_EQUALITY_LITERALS = (2, 4, 8)
SIZE_BYTE_EQUALITY_PRIMITIVE_BY_LITERAL = {
    2: "lower_generation_size_byte_equals_2",
    4: "lower_generation_size_byte_equals_4",
    8: "lower_generation_size_byte_equals_8",
}


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

    def test_builds_lowering_request_with_catalog_derived_generation_rules(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        selection = self.selection_for("lower_generation_type_unsigned")

        request = build_catalog_lowering_request(catalog, backend_id="cpp")

        self.assertTrue(request.is_ok, request.diagnostics)
        lowering_request = request.unwrap()
        self.assertEqual(lowering_request.backend_id, "cpp")
        rule_set = (
            lowering_request.generation_context.concrete_integer_generation_rules
        )
        self.assertEqual(
            rule_set.supported_type_tags,
            CONCRETE_INTEGER_TAGS,
        )

        result = lower_candidates(selection, lowering_request)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertIs(
            result.unwrap().request.generation_context.concrete_integer_generation_rules,
            rule_set,
        )
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            tuple(
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag=UNSIGNED_COMPANION_BY_TAG[type_tag],
                    source_type_tag=type_tag,
                )
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )

    def test_catalog_lowering_request_preserves_request_local_context(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        selection = self.selection_for("lower_generation_type_override")
        base_context = GenerationContext(
            type_tag_override="ui64",
            use_candidate_type_tag=False,
        )

        request = build_catalog_lowering_request(
            catalog,
            backend_id="cpp",
            generation_context=base_context,
        )

        self.assertTrue(request.is_ok, request.diagnostics)
        result = lower_candidates(selection, request.unwrap())

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().implementations[0].generation_type_refs,
            (GenerationTypeRef(kind="base.in", type_tag="ui64"),),
        )

    def test_catalog_lowering_request_reports_missing_rule_data_without_default(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        missing_ui64 = catalog_with_type_groups(
            catalog,
            tuple(group for group in catalog.type_groups if group.name != "ui64"),
        )

        request = build_catalog_lowering_request(missing_ui64, backend_id="cpp")

        self.assertFalse(request.is_ok)
        self.assertIn(
            "TSL-DOMAIN-GEN-RULE-SINGLETON-MISSING",
            {diagnostic.code for diagnostic in request.diagnostics},
        )
        self.assertTrue(
            any("ui64" in diagnostic.message for diagnostic in request.diagnostics)
        )

    def test_catalog_lowering_request_reports_inconsistent_rule_data_without_default(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        inconsistent = catalog_with_type_groups(
            catalog,
            tuple(
                replace(group, members=("ui32",))
                if group.name == "si32"
                else group
                for group in catalog.type_groups
            ),
        )

        request = build_catalog_lowering_request(inconsistent, backend_id="cpp")

        self.assertFalse(request.is_ok)
        self.assertIn(
            "TSL-DOMAIN-GEN-RULE-SINGLETON-INCONSISTENT",
            {diagnostic.code for diagnostic in request.diagnostics},
        )

    def test_explicit_catalog_derived_rules_do_not_fall_back_to_default(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        pair_rules = build_concrete_integer_generation_rule_set(
            tuple(
                group
                for group in catalog.type_groups
                if group.name in ("si32", "ui32")
            ),
            selected_type_tags=("si32", "ui32"),
        )
        if not pair_rules.is_ok:
            raise AssertionError(pair_rules.diagnostics)
        selection = self.selection_for("lower_generation_type_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    type_tag_override="si64",
                    concrete_integer_generation_rules=pair_rules.unwrap(),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("'si32', 'ui32'", result.diagnostics[0].message)
        self.assertNotIn("'ui64'", result.diagnostics[0].message)

    def test_catalog_lowering_request_wires_scalar_size_byte_rules(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        selection = self.selection_for("lower_generation_size_bytes")

        request = build_catalog_lowering_request(catalog, backend_id="cpp")

        self.assertTrue(request.is_ok, request.diagnostics)
        lowering_request = request.unwrap()
        rule_set = (
            lowering_request.generation_context.scalar_size_bytes_generation_rules
        )
        self.assertEqual(
            rule_set.supported_type_tags,
            tuple(SCALAR_SIZE_BYTES_BY_TAG),
        )

        result = lower_candidates(selection, lowering_request)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertIs(
            result.unwrap().request.generation_context.scalar_size_bytes_generation_rules,
            rule_set,
        )
        self.assertEqual(
            {
                implementation.generation_values[0].type_tag: (
                    implementation.generation_values[0].value
                )
                for implementation in result.unwrap().implementations
            },
            SCALAR_SIZE_BYTES_BY_TAG,
        )

    def test_catalog_lowering_request_reports_missing_scalar_size_rule_data_without_default(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        missing_f64 = catalog_with_type_groups(
            catalog,
            tuple(group for group in catalog.type_groups if group.name != "f64"),
        )

        request = build_catalog_lowering_request(missing_f64, backend_id="cpp")

        self.assertFalse(request.is_ok)
        self.assertIn(
            "TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-MISSING",
            {diagnostic.code for diagnostic in request.diagnostics},
        )
        self.assertTrue(
            any("f64" in diagnostic.message for diagnostic in request.diagnostics)
        )

    def test_explicit_scalar_size_rules_do_not_fall_back_to_default(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        si32_size_rules = build_scalar_size_bytes_generation_rule_set(
            tuple(group for group in catalog.type_groups if group.name == "si32"),
            selected_type_tags=("si32",),
        )
        if not si32_size_rules.is_ok:
            raise AssertionError(si32_size_rules.diagnostics)
        selection = self.selection_for("lower_generation_size_bytes_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    type_tag_override="f64",
                    scalar_size_bytes_generation_rules=si32_size_rules.unwrap(),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("'si32'", result.diagnostics[0].message)
        self.assertIn("'f64'", result.diagnostics[0].message)
        self.assertNotIn("'ui64'", result.diagnostics[0].message)

    def test_lowers_base_generation_type_query_for_concrete_integers(self) -> None:
        selection = self.selection_for("lower_generation_type_base")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            tuple(
                GenerationTypeRef(kind="base.in", type_tag=type_tag)
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )

    def test_lowers_signed_generation_type_query_for_concrete_integers(self) -> None:
        selection = self.selection_for("lower_generation_type_signed")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            tuple(
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag=SIGNED_COMPANION_BY_TAG[type_tag],
                    source_type_tag=type_tag,
                )
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )

    def test_lowers_unsigned_generation_type_query_for_concrete_integers(self) -> None:
        selection = self.selection_for("lower_generation_type_unsigned")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(
                implementation.generation_type_refs[0]
                for implementation in result.unwrap().implementations
            ),
            tuple(
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag=UNSIGNED_COMPANION_BY_TAG[type_tag],
                    source_type_tag=type_tag,
                )
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
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

    def test_resolves_base_generation_type_query_for_each_concrete_integer(
        self,
    ) -> None:
        for type_tag in CONCRETE_INTEGER_TAGS:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_type_query(
                    "type<generation>(base::in)",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(
                    result.unwrap(),
                    GenerationTypeRef(kind="base.in", type_tag=type_tag),
                )

    def test_resolves_signed_generation_type_query_for_each_concrete_integer(
        self,
    ) -> None:
        for type_tag in CONCRETE_INTEGER_TAGS:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_type_query(
                    "type<generation>(base::signed_of(type<generation>(base::in)))",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(
                    result.unwrap(),
                    GenerationTypeRef(
                        kind="base.signed_of",
                        type_tag=SIGNED_COMPANION_BY_TAG[type_tag],
                        source_type_tag=type_tag,
                    ),
                )

    def test_resolves_unsigned_generation_type_query_for_each_concrete_integer(
        self,
    ) -> None:
        for type_tag in CONCRETE_INTEGER_TAGS:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_type_query(
                    "type<generation>(base::unsigned_of(type<generation>(base::in)))",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(
                    result.unwrap(),
                    GenerationTypeRef(
                        kind="base.unsigned_of",
                        type_tag=UNSIGNED_COMPANION_BY_TAG[type_tag],
                        source_type_tag=type_tag,
                    ),
                )

    def test_generation_type_query_si32_ui32_regression_is_unchanged(self) -> None:
        cases = (
            (
                "si32",
                "type<generation>(base::unsigned_of(type<generation>(base::in)))",
                GenerationTypeRef(
                    kind="base.unsigned_of",
                    type_tag="ui32",
                    source_type_tag="si32",
                ),
            ),
            (
                "ui32",
                "type<generation>(base::signed_of(type<generation>(base::in)))",
                GenerationTypeRef(
                    kind="base.signed_of",
                    type_tag="si32",
                    source_type_tag="ui32",
                ),
            ),
        )

        for type_tag, query, expected in cases:
            with self.subTest(type_tag=type_tag, query=query):
                result = resolve_generation_type_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(result.unwrap(), expected)

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
            ("f64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("imask", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("si128", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
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
        for type_tag in ("f32", "f64", "ptr", "mask", "imask"):
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_type_query(
                    "type<generation>(base::signed_of(type<generation>(base::in)))",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-NON-INTEGER",
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

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

    def test_lowers_size_bytes_generation_value_query_for_selected_scalar_tags(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_bytes")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), len(SCALAR_SIZE_BYTES_BY_TAG))
        for implementation in implementations:
            self.assertEqual(implementation.statements, ())
            self.assertEqual(implementation.generation_type_refs, ())
            self.assertEqual(len(implementation.generation_values), 1)
            value = implementation.generation_values[0]
            self.assertEqual(value.kind, "type.size_bytes")
            self.assertEqual(value.value, SCALAR_SIZE_BYTES_BY_TAG[value.type_tag])

        self.assertEqual(
            {
                implementation.generation_values[0].type_tag: (
                    implementation.generation_values[0].value
                )
                for implementation in implementations
            },
            SCALAR_SIZE_BYTES_BY_TAG,
        )

    def test_size_bytes_value_is_visible_through_stage_contract(self) -> None:
        selection = self.selection_for("lower_generation_size_bytes_override")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        value = GenerationValue(kind="type.size_bytes", value=4, type_tag="si32")
        self.assertEqual(implementation.generation_values, (value,))
        self.assertEqual(implementation.generation_predicates, ())
        self.assertEqual(
            implementation.generation_stages,
            (
                GenerationLoweringStage(
                    stage="helper_expression_recognition",
                    output=GenerationExpressionRecognition(
                        kind="generation.value",
                        source_text=(
                            "value<generation>(type::size_bytes("
                            "type<generation>(base::in)))"
                        ),
                    ),
                ),
                GenerationLoweringStage(
                    stage="typed_generation_value",
                    output=value,
                ),
            ),
        )

    def test_resolves_size_bytes_generation_value_query_for_each_selected_scalar(
        self,
    ) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in)))"

        for type_tag, size_bytes in SCALAR_SIZE_BYTES_BY_TAG.items():
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(
                    result.unwrap(),
                    GenerationValue(
                        kind="type.size_bytes",
                        value=size_bytes,
                        type_tag=type_tag,
                    ),
                )

    def test_size_bytes_query_accepts_floats_without_broadening_type_queries(
        self,
    ) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in)))"

        for type_tag, size_bytes in (("f32", 4), ("f64", 8)):
            with self.subTest(type_tag=type_tag):
                value = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )
                base_type = resolve_generation_type_query(
                    "type<generation>(base::in)",
                    GenerationContext(type_tag_override=type_tag),
                )
                signed_type = resolve_generation_type_query(
                    "type<generation>(base::signed_of(type<generation>(base::in)))",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(value.is_ok, value.diagnostics)
                self.assertEqual(value.unwrap().value, size_bytes)
                self.assertFalse(base_type.is_ok)
                assert_diagnostic(
                    self,
                    base_type.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
                    severity="error",
                )
                self.assertFalse(signed_type.is_ok)
                assert_diagnostic(
                    self,
                    signed_type.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-NON-INTEGER",
                    severity="error",
                )

    def test_size_bytes_generation_value_query_uses_context_precedence(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_bytes_override")
        query = "value<generation>(type::size_bytes(type<generation>(base::in)))"

        override_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    selected_type_tag="ui16",
                    type_tag_override="f64",
                ),
            ),
        )
        selected_context_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(selected_type_tag="ui16"),
            ),
        )
        candidate_default_result = lower_candidates(selection)
        direct_candidate_result = resolve_generation_value_query(
            query,
            GenerationContext(),
            selected_candidate_type_tag="si8",
        )

        self.assertTrue(override_result.is_ok, override_result.diagnostics)
        self.assertEqual(
            override_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bytes", value=8, type_tag="f64"),),
        )
        self.assertTrue(
            selected_context_result.is_ok,
            selected_context_result.diagnostics,
        )
        self.assertEqual(
            selected_context_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bytes", value=2, type_tag="ui16"),),
        )
        self.assertTrue(
            candidate_default_result.is_ok,
            candidate_default_result.diagnostics,
        )
        self.assertEqual(
            candidate_default_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bytes", value=4, type_tag="si32"),),
        )
        self.assertTrue(direct_candidate_result.is_ok, direct_candidate_result.diagnostics)
        self.assertEqual(
            direct_candidate_result.unwrap(),
            GenerationValue(kind="type.size_bytes", value=1, type_tag="si8"),
        )

    def test_size_bytes_generation_value_query_reports_missing_type_context(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_bytes_override")

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
            code="TSL-LOWER-GEN-VALUE-CONTEXT-MISSING",
            severity="error",
        )

    def test_size_bytes_generation_value_query_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_bytes")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_size_bytes_generation_value_query_reports_malformed_query(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(type::size_bytes(type<generation>(base::in))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-MALFORMED",
            severity="error",
        )

    def test_size_bytes_generation_value_query_reports_wrong_arity(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(type::size_bytes("
            "type<generation>(base::in), type<generation>(base::in)))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-ARITY",
            severity="error",
        )

    def test_size_bytes_generation_value_query_rejects_trailing_comma(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(type::size_bytes("
            "type<generation>(base::in),))",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-ARITY",
            severity="error",
        )

    def test_size_bytes_generation_value_query_reports_unsupported_nested_operands(
        self,
    ) -> None:
        cases = (
            "type<generation>(base::signed_of(type<generation>(base::in)))",
            "type<generation>(base::unsigned_of(type<generation>(base::in)))",
            "type<generation>(vector::register)",
            "base::in",
        )

        for nested in cases:
            with self.subTest(nested=nested):
                result = resolve_generation_value_query(
                    f"value<generation>(type::size_bytes({nested}))",
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED",
                    severity="error",
                )
                self.assertIn(nested, result.diagnostics[0].message)

    def test_size_bytes_generation_value_query_reports_unsupported_value_forms(
        self,
    ) -> None:
        result = resolve_generation_value_query(
            "value<generation>(vector::length)",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-UNSUPPORTED",
            severity="error",
        )

    def test_size_bytes_generation_value_query_reports_unsupported_tags(self) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            ("ptr", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("imask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("f?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("arith", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("qword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si128", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mystery", "TSL-LOWER-GEN-VALUE-TAG-UNKNOWN"),
        )

        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_value_query(
                    query,
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

    def test_lowers_size_bytes_times_eight_generation_value_for_selected_scalars(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_bits")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), len(SCALAR_SIZE_BITS_BY_TAG))
        for implementation in implementations:
            self.assertEqual(implementation.statements, ())
            self.assertEqual(implementation.generation_type_refs, ())
            self.assertEqual(len(implementation.generation_values), 1)
            value = implementation.generation_values[0]
            self.assertEqual(value.kind, "type.size_bits")
            self.assertEqual(value.value, SCALAR_SIZE_BITS_BY_TAG[value.type_tag])

        self.assertEqual(
            {
                implementation.generation_values[0].type_tag: (
                    implementation.generation_values[0].value
                )
                for implementation in implementations
            },
            SCALAR_SIZE_BITS_BY_TAG,
        )

    def test_size_bits_value_is_visible_through_stage_contract(self) -> None:
        selection = self.selection_for("lower_generation_size_bits_override")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        value = GenerationValue(kind="type.size_bits", value=32, type_tag="si32")
        self.assertEqual(implementation.generation_values, (value,))
        self.assertEqual(implementation.generation_predicates, ())
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages),
            ("helper_expression_recognition", "typed_generation_value"),
        )
        self.assertEqual(implementation.generation_stages[1].output, value)

    def test_resolves_size_bytes_times_eight_generation_value_for_each_scalar(
        self,
    ) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in)))*8"

        for type_tag, size_bits in SCALAR_SIZE_BITS_BY_TAG.items():
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(
                    result.unwrap(),
                    GenerationValue(
                        kind="type.size_bits",
                        value=size_bits,
                        type_tag=type_tag,
                    ),
                )

    def test_size_bits_expression_accepts_floats_without_broadening_type_queries(
        self,
    ) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) * 8"

        for type_tag, size_bits in (("f32", 32), ("f64", 64)):
            with self.subTest(type_tag=type_tag):
                value = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )
                base_type = resolve_generation_type_query(
                    "type<generation>(base::in)",
                    GenerationContext(type_tag_override=type_tag),
                )
                signed_type = resolve_generation_type_query(
                    "type<generation>(base::signed_of(type<generation>(base::in)))",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(value.is_ok, value.diagnostics)
                self.assertEqual(value.unwrap().value, size_bits)
                self.assertEqual(value.unwrap().kind, "type.size_bits")
                self.assertFalse(base_type.is_ok)
                assert_diagnostic(
                    self,
                    base_type.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
                    severity="error",
                )
                self.assertFalse(signed_type.is_ok)
                assert_diagnostic(
                    self,
                    signed_type.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-NON-INTEGER",
                    severity="error",
                )

    def test_size_bits_expression_uses_context_precedence(self) -> None:
        selection = self.selection_for("lower_generation_size_bits_override")
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) * 8"

        override_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    selected_type_tag="ui16",
                    type_tag_override="f64",
                ),
            ),
        )
        selected_context_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(selected_type_tag="ui16"),
            ),
        )
        candidate_default_result = lower_candidates(selection)
        direct_candidate_result = resolve_generation_value_query(
            query,
            GenerationContext(),
            selected_candidate_type_tag="si8",
        )

        self.assertTrue(override_result.is_ok, override_result.diagnostics)
        self.assertEqual(
            override_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bits", value=64, type_tag="f64"),),
        )
        self.assertTrue(
            selected_context_result.is_ok,
            selected_context_result.diagnostics,
        )
        self.assertEqual(
            selected_context_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bits", value=16, type_tag="ui16"),),
        )
        self.assertTrue(
            candidate_default_result.is_ok,
            candidate_default_result.diagnostics,
        )
        self.assertEqual(
            candidate_default_result.unwrap().implementations[0].generation_values,
            (GenerationValue(kind="type.size_bits", value=32, type_tag="si32"),),
        )
        self.assertTrue(direct_candidate_result.is_ok, direct_candidate_result.diagnostics)
        self.assertEqual(
            direct_candidate_result.unwrap(),
            GenerationValue(kind="type.size_bits", value=8, type_tag="si8"),
        )

    def test_size_bits_expression_reports_missing_type_context(self) -> None:
        selection = self.selection_for("lower_generation_size_bits_override")

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
            code="TSL-LOWER-GEN-VALUE-CONTEXT-MISSING",
            severity="error",
        )

    def test_size_bits_expression_uses_explicit_scalar_size_rules(self) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        si32_size_rules = build_scalar_size_bytes_generation_rule_set(
            tuple(group for group in catalog.type_groups if group.name == "si32"),
            selected_type_tags=("si32",),
        )
        if not si32_size_rules.is_ok:
            raise AssertionError(si32_size_rules.diagnostics)
        selection = self.selection_for("lower_generation_size_bits_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    type_tag_override="f64",
                    scalar_size_bytes_generation_rules=si32_size_rules.unwrap(),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("'si32'", result.diagnostics[0].message)
        self.assertIn("'f64'", result.diagnostics[0].message)

    def test_size_bits_expression_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_bits")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_size_bits_expression_reports_malformed_arithmetic(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(type::size_bytes(type<generation>(base::in))) *",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-ARITH-MALFORMED",
            severity="error",
        )

    def test_size_bits_expression_reports_unsupported_operators(self) -> None:
        left = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"{left} / 8",
            f"{left} + 8",
            f"{left} - 8",
            f"{left} % 8",
            f"{left} == 8",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-VALUE-ARITH-OPERATOR",
                    severity="error",
                )

    def test_size_bits_expression_reports_unsupported_literals(self) -> None:
        left = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"{left} * 4",
            f"{left} * 16",
            f"{left} * (8)",
            f"{left} * value<generation>(type::size_bytes(type<generation>(base::in)))",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-VALUE-ARITH-LITERAL",
                    severity="error",
                )

    def test_size_bits_expression_reports_unsupported_operands(self) -> None:
        value_query = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"8 * {value_query}",
            f"({value_query}) * 8",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_value_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-VALUE-ARITH-OPERAND",
                    severity="error",
                )

    def test_size_bits_expression_reports_unsupported_nested_operand(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(type::size_bytes("
            "type<generation>(base::signed_of(type<generation>(base::in))))) * 8",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED",
            severity="error",
        )

    def test_size_bits_expression_reports_unsupported_value_forms(self) -> None:
        result = resolve_generation_value_query(
            "value<generation>(vector::length) * 8",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-UNSUPPORTED",
            severity="error",
        )

    def test_size_bits_expression_reports_unsupported_tags(self) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) * 8"
        cases = (
            ("ptr", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("imask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("f?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("arith", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("qword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si128", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mystery", "TSL-LOWER-GEN-VALUE-TAG-UNKNOWN"),
        )

        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_value_query(
                    query,
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

    def test_lowers_size_byte_equality_generation_predicates_for_selected_scalars(
        self,
    ) -> None:
        for literal, primitive_name in SIZE_BYTE_EQUALITY_PRIMITIVE_BY_LITERAL.items():
            with self.subTest(literal=literal):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertTrue(result.is_ok, result.diagnostics)
                implementations = result.unwrap().implementations
                self.assertEqual(len(implementations), len(SCALAR_SIZE_BYTES_BY_TAG))
                for implementation in implementations:
                    self.assertEqual(implementation.statements, ())
                    self.assertEqual(implementation.generation_type_refs, ())
                    self.assertEqual(implementation.generation_values, ())
                    self.assertEqual(len(implementation.generation_predicates), 1)
                    predicate = implementation.generation_predicates[0]
                    self.assertEqual(predicate.kind, "type.size_bytes.equals")
                    self.assertEqual(predicate.literal, literal)
                    self.assertEqual(
                        predicate.value,
                        SCALAR_SIZE_BYTES_BY_TAG[predicate.type_tag] == literal,
                    )

    def test_size_byte_predicate_stage_exposes_typed_value_then_predicate(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_equals_override")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        value = GenerationValue(kind="type.size_bytes", value=4, type_tag="si32")
        predicate = GenerationPredicate(
            kind="type.size_bytes.equals",
            literal=8,
            value=False,
            type_tag="si32",
        )
        self.assertEqual(implementation.generation_values, ())
        self.assertEqual(implementation.generation_predicates, (predicate,))
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages),
            (
                "helper_expression_recognition",
                "typed_generation_value",
                "typed_generation_predicate",
            ),
        )
        self.assertEqual(implementation.generation_stages[1].output, value)
        self.assertEqual(implementation.generation_stages[2].output, predicate)

    def test_resolves_size_byte_equality_generation_predicate_truth_table(
        self,
    ) -> None:
        left = "value<generation>(type::size_bytes(type<generation>(base::in)))"

        for type_tag, size_bytes in SCALAR_SIZE_BYTES_BY_TAG.items():
            for literal in SIZE_BYTE_EQUALITY_LITERALS:
                with self.subTest(type_tag=type_tag, literal=literal):
                    result = resolve_generation_predicate_query(
                        f"{left} == {literal}",
                        GenerationContext(type_tag_override=type_tag),
                    )

                    self.assertTrue(result.is_ok, result.diagnostics)
                    self.assertEqual(
                        result.unwrap(),
                        GenerationPredicate(
                            kind="type.size_bytes.equals",
                            literal=literal,
                            value=size_bytes == literal,
                            type_tag=type_tag,
                        ),
                    )

    def test_size_byte_equality_predicate_accepts_floats_without_broadening_type_queries(
        self,
    ) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) == 4"

        for type_tag, expected in (("f32", True), ("f64", False)):
            with self.subTest(type_tag=type_tag):
                predicate = resolve_generation_predicate_query(
                    query,
                    GenerationContext(type_tag_override=type_tag),
                )
                base_type = resolve_generation_type_query(
                    "type<generation>(base::in)",
                    GenerationContext(type_tag_override=type_tag),
                )

                self.assertTrue(predicate.is_ok, predicate.diagnostics)
                self.assertEqual(predicate.unwrap().value, expected)
                self.assertFalse(base_type.is_ok)
                assert_diagnostic(
                    self,
                    base_type.diagnostics[0],
                    code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
                    severity="error",
                )

    def test_size_byte_equality_predicate_uses_context_precedence(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_equals_override")
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) == 8"

        override_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    selected_type_tag="ui16",
                    type_tag_override="f64",
                ),
            ),
        )
        selected_context_result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(selected_type_tag="ui16"),
            ),
        )
        candidate_default_result = lower_candidates(selection)
        direct_candidate_result = resolve_generation_predicate_query(
            query,
            GenerationContext(),
            selected_candidate_type_tag="si64",
        )

        self.assertTrue(override_result.is_ok, override_result.diagnostics)
        self.assertEqual(
            override_result.unwrap().implementations[0].generation_predicates,
            (
                GenerationPredicate(
                    kind="type.size_bytes.equals",
                    literal=8,
                    value=True,
                    type_tag="f64",
                ),
            ),
        )
        self.assertTrue(
            selected_context_result.is_ok,
            selected_context_result.diagnostics,
        )
        self.assertEqual(
            selected_context_result.unwrap().implementations[0].generation_predicates,
            (
                GenerationPredicate(
                    kind="type.size_bytes.equals",
                    literal=8,
                    value=False,
                    type_tag="ui16",
                ),
            ),
        )
        self.assertTrue(
            candidate_default_result.is_ok,
            candidate_default_result.diagnostics,
        )
        self.assertEqual(
            candidate_default_result.unwrap().implementations[0].generation_predicates,
            (
                GenerationPredicate(
                    kind="type.size_bytes.equals",
                    literal=8,
                    value=False,
                    type_tag="si32",
                ),
            ),
        )
        self.assertTrue(
            direct_candidate_result.is_ok,
            direct_candidate_result.diagnostics,
        )
        self.assertEqual(
            direct_candidate_result.unwrap(),
            GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=8,
                value=True,
                type_tag="si64",
            ),
        )

    def test_size_byte_equality_predicate_reports_missing_type_context(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_equals_override")

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
            code="TSL-LOWER-GEN-VALUE-CONTEXT-MISSING",
            severity="error",
        )

    def test_size_byte_equality_predicate_uses_explicit_scalar_size_rules(
        self,
    ) -> None:
        catalog = catalog_with_primitives(LOWERING_FIXTURE)
        si32_size_rules = build_scalar_size_bytes_generation_rule_set(
            tuple(group for group in catalog.type_groups if group.name == "si32"),
            selected_type_tags=("si32",),
        )
        if not si32_size_rules.is_ok:
            raise AssertionError(si32_size_rules.diagnostics)
        selection = self.selection_for("lower_generation_size_byte_equals_override")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(
                    type_tag_override="f64",
                    scalar_size_bytes_generation_rules=si32_size_rules.unwrap(),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("'si32'", result.diagnostics[0].message)
        self.assertIn("'f64'", result.diagnostics[0].message)

    def test_size_byte_equality_predicate_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_equals_4")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        self.assertEqual(
            first.unwrap().implementations[0].generation_stages,
            second.unwrap().implementations[0].generation_stages,
        )

    def test_size_byte_equality_predicate_reports_malformed_syntax(self) -> None:
        result = resolve_generation_predicate_query(
            "value<generation>(type::size_bytes(type<generation>(base::in))) ==",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-PREDICATE-MALFORMED",
            severity="error",
        )

    def test_size_byte_equality_predicate_reports_unsupported_operators(self) -> None:
        left = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"{left} != 4",
            f"{left} < 4",
            f"{left} > 4",
            f"{left} * 8",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_predicate_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-PREDICATE-OPERATOR",
                    severity="error",
                )

    def test_size_byte_equality_predicate_reports_unsupported_literals(self) -> None:
        left = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"{left} == 1",
            f"{left} == 16",
            f"{left} == (4)",
            f"{left} == {left}",
            f"{left} == 4 == 8",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_predicate_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-PREDICATE-LITERAL",
                    severity="error",
                )

    def test_size_byte_equality_predicate_reports_unsupported_operands(self) -> None:
        value_query = "value<generation>(type::size_bytes(type<generation>(base::in)))"
        cases = (
            f"4 == {value_query}",
            f"({value_query}) == 4",
            "value<generation>(vector::length) == 4",
        )

        for query in cases:
            with self.subTest(query=query):
                result = resolve_generation_predicate_query(
                    query,
                    GenerationContext(type_tag_override="si32"),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-PREDICATE-OPERAND",
                    severity="error",
                )

    def test_size_byte_equality_predicate_reports_unsupported_nested_operand(
        self,
    ) -> None:
        result = resolve_generation_predicate_query(
            "value<generation>(type::size_bytes("
            "type<generation>(base::signed_of(type<generation>(base::in))))) == 4",
            GenerationContext(type_tag_override="si32"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED",
            severity="error",
        )

    def test_size_byte_equality_predicate_reports_unsupported_tags(self) -> None:
        query = "value<generation>(type::size_bytes(type<generation>(base::in))) == 4"
        cases = (
            ("ptr", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("imask", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("f?", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("arith", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("qword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("dqword", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("si128", "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED"),
            ("mystery", "TSL-LOWER-GEN-VALUE-TAG-UNKNOWN"),
        )

        for type_tag, code in cases:
            with self.subTest(type_tag=type_tag):
                result = resolve_generation_predicate_query(
                    query,
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

    def test_prunes_size_byte_equality_branch_chain_for_matching_scalar_sizes(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), len(SCALAR_SIZE_BYTES_BY_TAG))
        expected_body_by_literal = {
            2: "pg = intrin<svptrue_b16>();",
            4: "pg = intrin<svptrue_b32>();",
            8: "pg = intrin<svptrue_b64>();",
        }
        implementation_by_tag = {
            implementation.generation_branch_chains[0].type_tag: implementation
            for implementation in implementations
        }

        for type_tag, size_bytes in SCALAR_SIZE_BYTES_BY_TAG.items():
            with self.subTest(type_tag=type_tag):
                implementation = implementation_by_tag[type_tag]
                self.assertEqual(implementation.statements, ())
                self.assertEqual(implementation.generation_branches, ())
                self.assertEqual(len(implementation.generation_branch_chains), 1)
                chain = implementation.generation_branch_chains[0]
                expected_literal = size_bytes if size_bytes in (2, 4, 8) else None
                self.assertEqual(chain.selected_literal, expected_literal)
                self.assertEqual(
                    chain.selected_statement_text,
                    (
                        expected_body_by_literal[expected_literal]
                        if expected_literal is not None
                        else None
                    ),
                )
                self.assertEqual(tuple(arm.literal for arm in chain.arms), (2, 4, 8))
                self.assertEqual(
                    tuple(predicate.literal for predicate in implementation.generation_predicates),
                    (2, 4, 8),
                )
                self.assertEqual(
                    tuple(predicate.value for predicate in implementation.generation_predicates),
                    tuple(literal == size_bytes for literal in (2, 4, 8)),
                )
                self.assertEqual(
                    tuple(stage.stage for stage in implementation.generation_stages),
                    (
                        "helper_expression_recognition",
                        "typed_generation_value",
                        "typed_generation_predicate",
                        "typed_generation_predicate",
                        "typed_generation_predicate",
                        "generation_control_flow_pruning",
                    ),
                )
                self.assertEqual(implementation.generation_stages[-1].output, chain)

    def test_size_byte_branch_chain_records_no_match_without_final_else(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        no_match_chains = tuple(
            implementation.generation_branch_chains[0]
            for implementation in result.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag in ("si8", "ui8")
        )
        self.assertEqual(len(no_match_chains), 2)
        for chain in no_match_chains:
            self.assertIsNone(chain.selected_literal)
            self.assertIsNone(chain.selected_statement_text)
            self.assertEqual(tuple(arm.literal for arm in chain.arms), (2, 4, 8))

    def test_size_byte_branch_chain_uses_typed_stage_predicates(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(type_tag_override="ui16"),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        value = GenerationValue(kind="type.size_bytes", value=2, type_tag="ui16")
        predicates = tuple(
            GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=literal == 2,
                type_tag="ui16",
            )
            for literal in (2, 4, 8)
        )
        chain = GenerationSizeByteBranchChainPruning(
            arms=tuple(
                GenerationSizeByteBranchChainArm(
                    literal=literal,
                    predicate=predicate,
                    statement_text={
                        2: "pg = intrin<svptrue_b16>();",
                        4: "pg = intrin<svptrue_b32>();",
                        8: "pg = intrin<svptrue_b64>();",
                    }[literal],
                )
                for literal, predicate in zip((2, 4, 8), predicates, strict=True)
            ),
            type_tag="ui16",
            selected_literal=2,
            selected_statement_text="pg = intrin<svptrue_b16>();",
            condition_location=selection.candidates[0]
            .variant.source.declaration.source_span.location,
        )
        self.assertEqual(implementation.generation_predicates, predicates)
        self.assertEqual(
            tuple(stage.output for stage in implementation.generation_stages[1:]),
            (value, *predicates, chain),
        )

    def test_size_byte_branch_chain_bodies_remain_opaque(self) -> None:
        selection = self.selection_for(
            "lower_generation_size_byte_branch_chain_body_helpers"
        )

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        for implementation in result.unwrap().implementations:
            self.assertEqual(implementation.statements, ())
            self.assertNotIn(
                "selected_body_lowering",
                tuple(stage.stage for stage in implementation.generation_stages),
            )

    def test_size_byte_branch_chain_pruning_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_size_byte_branch_chain_rejects_unsupported_shapes(self) -> None:
        for primitive_name in (
            "lower_generation_size_byte_branch_chain_missing_arm",
            "lower_generation_size_byte_branch_chain_reordered",
            "lower_generation_size_byte_branch_chain_duplicate",
            "lower_generation_size_byte_branch_chain_final_else",
        ):
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(selection)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-GEN-IF-MALFORMED",
                    severity="error",
                )

    def test_size_byte_branch_chain_preserves_standalone_predicate_stage(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_equals_override")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(implementation.generation_branch_chains, ())
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages),
            (
                "helper_expression_recognition",
                "typed_generation_value",
                "typed_generation_predicate",
            ),
        )

    def test_prunes_signedness_generation_branch_for_concrete_integers(self) -> None:
        selection = self.selection_for("lower_generation_signedness")

        result = lower_candidates(selection, LoweringRequest(backend_id="cpp"))

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), 8)
        signed_statement = (
            TsilReturnStatement(
                TsilBinaryExpression(
                    operator="+",
                    left=TsilParameterReference("left"),
                    right=TsilParameterReference("right"),
                )
            ),
        )
        unsigned_statement = (
            TsilReturnStatement(
                TsilBinaryExpression(
                    operator="+",
                    left=TsilParameterReference("right"),
                    right=TsilParameterReference("left"),
                )
            ),
        )
        self.assertEqual(
            tuple(implementation.statements for implementation in implementations),
            tuple(
                signed_statement if IS_SIGNED_BY_TAG[type_tag] else unsigned_statement
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0]
                for implementation in implementations
            ),
            tuple(
                PrunedGenerationBranch(
                    condition=TsilTypeSignednessCondition(
                        GenerationTypeRef(kind="base.in", type_tag=type_tag)
                    ),
                    selected_branch=(
                        "true" if IS_SIGNED_BY_TAG[type_tag] else "false"
                    ),
                    statement_text=(
                        "emit_return(left + right);"
                        if IS_SIGNED_BY_TAG[type_tag]
                        else "emit_return(right + left);"
                    ),
                    condition_location=selection.candidates[
                        index
                    ].variant.source.declaration.source_span.location,
                )
                for index, type_tag in enumerate(CONCRETE_INTEGER_LOWERING_ORDER)
            ),
        )

    def test_signedness_generation_branch_si32_ui32_regression_is_unchanged(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_signedness")

        cases = (("si32", "true"), ("ui32", "false"))
        for type_tag, selected_branch in cases:
            with self.subTest(type_tag=type_tag):
                result = lower_candidates(
                    selection,
                    LoweringRequest(
                        generation_context=GenerationContext(
                            type_tag_override=type_tag,
                        ),
                    ),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                branch = result.unwrap().implementations[0].generation_branches[0]
                self.assertEqual(branch.selected_branch, selected_branch)
                self.assertEqual(
                    branch.condition,
                    TsilTypeSignednessCondition(
                        GenerationTypeRef(kind="base.in", type_tag=type_tag)
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
            ("f64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
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

    def test_prunes_plain_else_signedness_generation_branch_for_concrete_integers(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_signedness_plain_else")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), 8)
        signed_statement = (
            TsilReturnStatement(
                TsilBinaryExpression(
                    operator="+",
                    left=TsilParameterReference("left"),
                    right=TsilParameterReference("right"),
                )
            ),
        )
        unsigned_statement = (
            TsilReturnStatement(
                TsilBinaryExpression(
                    operator="+",
                    left=TsilParameterReference("right"),
                    right=TsilParameterReference("left"),
                )
            ),
        )
        self.assertEqual(
            tuple(implementation.statements for implementation in implementations),
            tuple(
                signed_statement if IS_SIGNED_BY_TAG[type_tag] else unsigned_statement
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0].else_syntax
                for implementation in implementations
            ),
            tuple("else" for _ in CONCRETE_INTEGER_LOWERING_ORDER),
        )
        self.assertEqual(
            tuple(
                implementation.generation_branches[0].selected_branch
                for implementation in implementations
            ),
            tuple(
                "true" if IS_SIGNED_BY_TAG[type_tag] else "false"
                for type_tag in CONCRETE_INTEGER_LOWERING_ORDER
            ),
        )

    def test_signedness_branch_stage_contract_preserves_m48_and_m51_outputs(
        self,
    ) -> None:
        cases = (
            (
                "lower_generation_signedness",
                "ui32",
                "else<generation>",
                "false",
                "emit_return(right + left);",
            ),
            (
                "lower_generation_signedness_plain_else",
                "si32",
                "else",
                "true",
                "emit_return(left + right);",
            ),
        )

        for primitive_name, type_tag, else_syntax, choice, statement_text in cases:
            with self.subTest(primitive_name=primitive_name):
                selection = self.selection_for(primitive_name)

                result = lower_candidates(
                    selection,
                    LoweringRequest(
                        generation_context=GenerationContext(
                            type_tag_override=type_tag,
                        ),
                    ),
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                implementation = result.unwrap().implementations[0]
                branch = implementation.generation_branches[0]
                self.assertEqual(branch.else_syntax, else_syntax)
                self.assertEqual(branch.selected_branch, choice)
                self.assertEqual(branch.statement_text, statement_text)
                self.assertEqual(
                    tuple(stage.stage for stage in implementation.generation_stages),
                    (
                        "helper_expression_recognition",
                        "generation_control_flow_pruning",
                        "selected_body_lowering",
                    ),
                )
                self.assertEqual(implementation.generation_stages[1].output, branch)
                self.assertEqual(
                    implementation.generation_stages[2].output,
                    implementation.statements[0],
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
            ("f64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ptr", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("mask", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("?i64", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("si?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("ui?", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
            ("idqword", "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED"),
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
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages),
            (
                "helper_expression_recognition",
                "generation_control_flow_pruning",
                "selected_body_lowering",
            ),
        )
        self.assertEqual(
            implementation.generation_stages[1].output,
            implementation.generation_branches[0],
        )
        self.assertEqual(
            implementation.generation_stages[2].output,
            implementation.statements[0],
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
