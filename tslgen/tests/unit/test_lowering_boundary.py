from __future__ import annotations

import ast
import builtins
from dataclasses import replace
import inspect
import os
from pathlib import Path, PurePosixPath
import platform
from typing import cast
import unittest
from unittest import mock

from _helpers import assert_diagnostic
import tslgen.lowering._array_body_diagnostics as lowering_array_body_diagnostics
import tslgen.lowering._array_body_lowering as lowering_array_body_lowering
import tslgen.lowering._array_body_models as lowering_array_body_models
import tslgen.lowering._array_body_pipeline as lowering_array_body_pipeline
import tslgen.lowering._array_body_shapes as lowering_array_body_shapes
import tslgen.lowering._array_body_sources as lowering_array_body_sources
import tslgen.lowering._array_body_validation as lowering_array_body_validation
import tslgen.lowering._exact_shapes as lowering_exact_shapes
import tslgen.lowering._generation_control_flow as lowering_generation_control_flow
import tslgen.lowering._generation_diagnostics as lowering_generation_diagnostics
import tslgen.lowering._generation_models as lowering_generation_models
import tslgen.lowering._generation_queries as lowering_generation_queries
import tslgen.lowering._lowering_inputs as lowering_inputs
import tslgen.lowering._mini_tsil_lowering as lowering_mini_tsil_lowering
import tslgen.lowering._pipeline as lowering_pipeline
import tslgen.lowering._return_emission as lowering_return_emission
import tslgen.lowering._selected_body_lowering as lowering_selected_body_lowering
import tslgen.lowering._selected_body_models as lowering_selected_body_models
import tslgen.lowering._stage_contracts as lowering_stage_contracts
import tslgen.lowering.boundary as lowering_boundary
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.generation_rules import (
    build_concrete_integer_generation_rule_set,
    build_scalar_size_bytes_generation_rule_set,
)
from tslgen.domain.types import TypeGroup
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.lowering import (
    ClassifiedPayload,
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyEnvelopeOpaqueSlot,
    ExactArrayBodyEnvelopeSelectedSlot,
    ExactArrayBodyEnvelopeSkeleton,
    ExactArrayBodyEnvelopeSkeletonRequirement,
    ExactArrayBodyEnvelopeSkeletonSlot,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationBaseTypeResolutionIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactArrayInitializationHelperRequestIr,
    ExactArrayInitializationHelperRequestRecord,
    ExactArrayInitializationSlotFormIr,
    ExactArrayInitializationVectorAlignmentMetadata,
    ExactArrayInitializationVectorAlignmentResolutionIr,
    ExactArrayInitializationVectorAlignmentValue,
    ExactArrayInitializationVectorLengthMetadata,
    ExactArrayInitializationVectorLengthResolutionIr,
    ExactArrayInitializationVectorLengthValue,
    ExactPredicatePathStructuralRequestIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
    GenerationContext,
    GenerationExpressionRecognition,
    GenerationLoweringStage,
    NoSelectedAssignmentDirectIntrinsicBodyIr,
    NoSelectedBodyEnvelopeIr,
    NoSelectedBranchBodyAssignmentFormRecognition,
    NoSelectedBranchBodyHandoff,
    OpaqueSelectedBranchBodyHandoff,
    GenerationPredicate,
    GenerationSizeByteBranchChainArm,
    GenerationSizeByteBranchChainPruning,
    GenerationTypeRef,
    GenerationValue,
    LoweredImplementation,
    LoweringInput,
    LoweringRequest,
    PrunedGenerationBranch,
    SelectedAssignmentDirectIntrinsicBodyIr,
    SelectedBodyEnvelopeEntry,
    SelectedBodyEnvelopeIr,
    SelectedBranchBodyAssignmentFormRecognition,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilPrimitiveAttributeCondition,
    TsilReturnStatement,
    TsilTypeSignednessCondition,
    assemble_exact_array_body_envelope,
    build_catalog_lowering_request,
    handoff_opaque_selected_branch_body,
    lower_candidates,
    lower_exact_array_body_structural_sequence,
    lower_exact_array_initialization_declaration_shell,
    lower_exact_array_initialization_base_type_request,
    lower_exact_array_initialization_helper_set_completion,
    lower_exact_array_initialization_helper_requests,
    lower_exact_array_initialization_slot_form,
    lower_exact_array_initialization_vector_alignment_request,
    lower_exact_array_initialization_vector_length_request,
    lower_exact_predicate_path_structural_request,
    lower_exact_post_branch_intrinsic_call_site_structural_request,
    lower_exact_return_emission_structural_request,
    lower_selected_branch_body_ir,
    lower_selected_body_envelope,
    prepare_lowering_inputs,
    recognize_selected_branch_body_assignment_form,
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

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_unsupported_selected_body(left, right):
  tests []
  impls:
    scalar:
      si16:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { emit_return(value<generation>(vector::length)); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { pg = intrin<svptrue_b32>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { pg = intrin<svptrue_b64>(); }"

prim<v:=(v,v)> lower_generation_size_byte_branch_chain_unselected_body_helpers(left, right):
  tests []
  impls:
    scalar:
      si16:
        requires []
        implementation:
          tsil "if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { pg = intrin<svptrue_b16>(); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { emit_return(value<generation>(vector::length)); } else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { pg = value<generation>(vector::length); }"

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
ARRAY_BODY_SLOT_LABELS = (
    "opaque_pre_branch_array_initialization",
    "opaque_pre_branch_predicate_initialization",
    "selected_body_envelope",
    "opaque_post_branch_store_call",
    "opaque_post_branch_return_emission",
)
ARRAY_BODY_OPAQUE_TEXT_BY_LABEL = {
    "opaque_pre_branch_array_initialization": (
        "var<typed>(array_type<type<generation>(base::in), "
        "value<generation>(vector::length), "
        "value<generation>(vector::alignment)>, tmp, "
        "value<backend>(uninit::array))"
    ),
    "opaque_pre_branch_predicate_initialization": (
        "svbool_t pg = intrin<svptrue_b8>();"
    ),
    "opaque_post_branch_store_call": "intrin<svst1>(pg, tmp.data(), a);",
    "opaque_post_branch_return_emission": " emit_return(tmp) ;",
}
ARRAY_BODY_SLOT_LINE_BY_LABEL = {
    "opaque_pre_branch_array_initialization": 105,
    "opaque_pre_branch_predicate_initialization": 106,
    "selected_body_envelope": 107,
    "opaque_post_branch_store_call": 110,
    "opaque_post_branch_return_emission": 111,
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

    def assignment_handoff(
        self,
        body_text: str,
        *,
        selected_literal: int = 2,
        selected_type_tag: str = "si16",
    ) -> OpaqueSelectedBranchBodyHandoff:
        return OpaqueSelectedBranchBodyHandoff(
            candidate_id="candidate-1",
            selected_type_tag=selected_type_tag,
            selected_literal=selected_literal,
            opaque_body_text=body_text,
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
        )

    def selected_body_ir(
        self,
        *,
        selected_type_tag: str = "si16",
        selected_literal: int = 2,
        token_text: str = "svptrue_b16",
        rhs_text: str = "intrin<svptrue_b16>()",
        original_body_text: str = "pg = intrin<svptrue_b16>();",
    ) -> SelectedAssignmentDirectIntrinsicBodyIr:
        return SelectedAssignmentDirectIntrinsicBodyIr(
            candidate_id="candidate-1",
            selected_type_tag=selected_type_tag,
            selected_literal=selected_literal,
            originating_branch_chain_id="candidate-1:chain",
            original_opaque_body_text=original_body_text,
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            assignment_target_text="pg",
            opaque_rhs_text=rhs_text,
            direct_intrinsic_token_text=token_text,
            direct_intrinsic_argument_texts=(),
        )

    def selected_body_envelope(
        self,
        *,
        selected_type_tag: str = "si16",
        selected_literal: int = 2,
        token_text: str = "svptrue_b16",
        rhs_text: str = "intrin<svptrue_b16>()",
        original_body_text: str = "pg = intrin<svptrue_b16>();",
        candidate_id: str = "candidate-1",
        branch_chain_id: str = "candidate-1:chain",
    ) -> SelectedBodyEnvelopeIr:
        body_ir = self.selected_body_ir(
            selected_type_tag=selected_type_tag,
            selected_literal=selected_literal,
            token_text=token_text,
            rhs_text=rhs_text,
            original_body_text=original_body_text,
        )
        if candidate_id != "candidate-1" or branch_chain_id != "candidate-1:chain":
            body_ir = replace(
                body_ir,
                candidate_id=candidate_id,
                originating_branch_chain_id=branch_chain_id,
            )
        result = lower_selected_body_envelope(body_ir)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        envelope = result.unwrap()
        assert isinstance(envelope, SelectedBodyEnvelopeIr)
        return envelope

    def no_selected_body_envelope(
        self,
        selected_type_tag: str = "si8",
    ) -> NoSelectedBodyEnvelopeIr:
        body_ir = NoSelectedAssignmentDirectIntrinsicBodyIr(
            candidate_id="candidate-1",
            selected_type_tag=selected_type_tag,
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
            attempted_literals=(2, 4, 8),
        )
        result = lower_selected_body_envelope(body_ir)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        envelope = result.unwrap()
        assert isinstance(envelope, NoSelectedBodyEnvelopeIr)
        return envelope

    def exact_array_body_skeleton(
        self,
        *,
        candidate_id: str = "candidate-1",
        selected_type_tag: str = "si16",
        branch_chain_id: str = "candidate-1:chain",
        labels: tuple[str, ...] = ARRAY_BODY_SLOT_LABELS,
        ordinals: tuple[int, ...] = (0, 1, 2, 3, 4),
        exact: bool = True,
    ) -> ExactArrayBodyEnvelopeSkeleton:
        slots = tuple(
            ExactArrayBodyEnvelopeSkeletonSlot(
                label=label,  # type: ignore[arg-type]
                ordinal=ordinal,
                source_location=SourceLocation(
                    Path("tsldata/primitives/load_store/array.tsl"),
                    ARRAY_BODY_SLOT_LINE_BY_LABEL.get(label, 105),
                    15,
                ),
                candidate_id=candidate_id,
                selected_type_tag=selected_type_tag,
                originating_branch_chain_id=branch_chain_id,
                opaque_source_text=ARRAY_BODY_OPAQUE_TEXT_BY_LABEL.get(label),
            )
            for ordinal, label in zip(ordinals, labels, strict=True)
        )
        return ExactArrayBodyEnvelopeSkeleton(
            candidate_id=candidate_id,
            selected_type_tag=selected_type_tag,
            source_location=SourceLocation(
                Path("tsldata/primitives/load_store/array.tsl"),
                105,
                15,
            ),
            originating_branch_chain_id=branch_chain_id,
            slots=slots,
            is_exact_array_body_shape=exact,
        )

    def exact_array_body_skeleton_for_envelope(
        self,
        envelope: SelectedBodyEnvelopeIr | NoSelectedBodyEnvelopeIr,
        *,
        exact: bool = True,
        branch_chain_id: str | None = None,
    ) -> ExactArrayBodyEnvelopeSkeleton:
        return self.exact_array_body_skeleton(
            candidate_id=envelope.candidate_id,
            selected_type_tag=envelope.selected_type_tag,
            branch_chain_id=branch_chain_id or envelope.originating_branch_chain_id,
            exact=exact,
        )

    def exact_array_body_envelope(
        self,
        *,
        selected_type_tag: str = "si16",
        selected_literal: int = 2,
        token_text: str = "svptrue_b16",
        rhs_text: str = "intrin<svptrue_b16>()",
        branch_chain_id: str = "candidate-1:chain",
    ) -> ExactArrayBodyEnvelopeIr:
        envelope = self.selected_body_envelope(
            selected_type_tag=selected_type_tag,
            selected_literal=selected_literal,
            token_text=token_text,
            rhs_text=rhs_text,
            original_body_text=f"pg = {rhs_text};",
            branch_chain_id=branch_chain_id,
        )
        result = assemble_exact_array_body_envelope(
            envelope,
            self.exact_array_body_skeleton(
                selected_type_tag=selected_type_tag,
                branch_chain_id=branch_chain_id,
            ),
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_array_initialization_helper_request_ir(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationHelperRequestIr:
        slot_form_result = lower_exact_array_initialization_slot_form(
            self.exact_array_body_envelope(selected_type_tag=selected_type_tag),
        )
        if not slot_form_result.is_ok:
            raise AssertionError(slot_form_result.diagnostics)
        helper_request_result = lower_exact_array_initialization_helper_requests(
            slot_form_result.unwrap(),
        )
        if not helper_request_result.is_ok:
            raise AssertionError(helper_request_result.diagnostics)
        return helper_request_result.unwrap()

    def exact_array_initialization_base_type_resolution(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationBaseTypeResolutionIr:
        result = lower_exact_array_initialization_base_type_request(
            self.exact_array_initialization_helper_request_ir(
                selected_type_tag=selected_type_tag,
            ),
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def vector_length_metadata(
        self,
        *,
        candidate_id: str = "candidate-1",
        target_extension: str = "sve",
        source_extension: str = "sve",
        selected_type_tag: str = "si16",
        lanes: int = 17,
        kind: str = "fixed_lanes",
    ) -> ExactArrayInitializationVectorLengthMetadata:
        value = (
            ExactArrayInitializationVectorLengthValue(
                kind="fixed_lanes",
                lanes=lanes,
            )
            if kind == "fixed_lanes"
            else ExactArrayInitializationVectorLengthValue(
                kind=kind,  # type: ignore[arg-type]
            )
        )
        return ExactArrayInitializationVectorLengthMetadata(
            candidate_id=candidate_id,
            target_extension=target_extension,
            source_extension=source_extension,
            selected_type_tag=selected_type_tag,
            vector_length=value,
            source_location=SourceLocation(Path("metadata.tsl"), 3, 5),
        )

    def vector_length_metadata_for_item(
        self,
        item,
        *,
        lanes: int = 17,
        kind: str = "fixed_lanes",
    ) -> ExactArrayInitializationVectorLengthMetadata:
        return self.vector_length_metadata(
            candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=item.candidate.type_tag,
            lanes=lanes,
            kind=kind,
        )

    def vector_alignment_metadata(
        self,
        *,
        candidate_id: str = "candidate-1",
        target_extension: str = "sve",
        source_extension: str = "sve",
        selected_type_tag: str = "si16",
        alignment_bytes: int = 64,
        kind: str = "fixed_bytes",
        unsupported_policy: str | None = None,
    ) -> ExactArrayInitializationVectorAlignmentMetadata:
        value = (
            ExactArrayInitializationVectorAlignmentValue(
                kind="fixed_bytes",
                bytes=alignment_bytes,
            )
            if kind == "fixed_bytes"
            else ExactArrayInitializationVectorAlignmentValue(
                kind=kind,  # type: ignore[arg-type]
                unsupported_policy=unsupported_policy or "unsupported-by-fixture",
            )
        )
        return ExactArrayInitializationVectorAlignmentMetadata(
            candidate_id=candidate_id,
            target_extension=target_extension,
            source_extension=source_extension,
            selected_type_tag=selected_type_tag,
            vector_alignment=value,
            source_location=SourceLocation(Path("metadata.tsl"), 4, 7),
        )

    def vector_alignment_metadata_for_item(
        self,
        item,
        *,
        alignment_bytes: int = 64,
        kind: str = "fixed_bytes",
    ) -> ExactArrayInitializationVectorAlignmentMetadata:
        return self.vector_alignment_metadata(
            candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=item.candidate.type_tag,
            alignment_bytes=alignment_bytes,
            kind=kind,
        )

    def exact_array_initialization_vector_length_resolution(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationVectorLengthResolutionIr:
        base_resolution = self.exact_array_initialization_base_type_resolution(
            selected_type_tag=selected_type_tag,
        )
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
        )
        result = lower_exact_array_initialization_vector_length_request(
            base_resolution,
            GenerationContext(
                array_initialization_vector_length_metadata=(metadata,),
            ),
            selected_candidate_id=base_resolution.candidate_id,
            target_extension=metadata.target_extension,
            source_extension=metadata.source_extension,
            selected_type_tag=base_resolution.selected_type_tag,
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_array_initialization_vector_alignment_resolution(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationVectorAlignmentResolutionIr:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution(
                selected_type_tag=selected_type_tag,
            )
        )
        metadata = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )
        result = lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            GenerationContext(
                array_initialization_vector_alignment_metadata=(metadata,),
            ),
            selected_candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_array_initialization_helper_set_completion(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationHelperSetCompletionIr:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution(
                selected_type_tag=selected_type_tag,
            )
        )
        result = lower_exact_array_initialization_helper_set_completion(
            vector_alignment_resolution,
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_array_initialization_declaration_shell(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayInitializationDeclarationShellIr:
        completion = self.exact_array_initialization_helper_set_completion(
            selected_type_tag=selected_type_tag,
        )
        result = lower_exact_array_initialization_declaration_shell(completion)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_array_body_structural_sequence(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactArrayBodyStructuralSequenceIr:
        shell = self.exact_array_initialization_declaration_shell(
            selected_type_tag=selected_type_tag,
        )
        result = lower_exact_array_body_structural_sequence(shell)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_predicate_path_structural_request(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactPredicatePathStructuralRequestIr:
        sequence = self.exact_array_body_structural_sequence(
            selected_type_tag=selected_type_tag,
        )
        result = lower_exact_predicate_path_structural_request(sequence)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_post_branch_intrinsic_call_site_structural_request(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactPostBranchIntrinsicCallSiteStructuralRequestIr:
        predicate_path = self.exact_predicate_path_structural_request(
            selected_type_tag=selected_type_tag,
        )
        result = lower_exact_post_branch_intrinsic_call_site_structural_request(
            predicate_path,
        )
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def exact_return_emission_structural_request(
        self,
        *,
        selected_type_tag: str = "si16",
    ) -> ExactReturnEmissionStructuralRequestIr:
        call_site = self.exact_post_branch_intrinsic_call_site_structural_request(
            selected_type_tag=selected_type_tag,
        )
        result = lower_exact_return_emission_structural_request(call_site)
        if not result.is_ok:
            raise AssertionError(result.diagnostics)
        return result.unwrap()

    def size_byte_branch_chain_item_and_envelope(
        self,
        selected_type_tag: str,
    ):
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        inputs = prepare_lowering_inputs(selection)
        self.assertTrue(inputs.is_ok, inputs.diagnostics)
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        implementation = next(
            implementation
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag
            == selected_type_tag
        )
        item = next(
            item
            for item in inputs.unwrap().inputs
            if item.candidate_id == implementation.candidate_id
        )
        return item, implementation.selected_body_envelopes[0]

    def exact_array_initialization_stage_pipeline(
        self,
        selected_type_tag: str,
        *,
        skeleton: ExactArrayBodyEnvelopeSkeleton | None = None,
        request: LoweringRequest | None = None,
    ):
        item, envelope = self.size_byte_branch_chain_item_and_envelope(
            selected_type_tag,
        )
        envelope_stage = GenerationLoweringStage(
            stage="selected_body_envelope_lowering",
            output=envelope,
        )
        if request is None:
            length_metadata = self.vector_length_metadata_for_item(item)
            alignment_metadata = self.vector_alignment_metadata_for_item(item)
            request = LoweringRequest(
                array_body_envelope_skeletons=(
                    skeleton or self.exact_array_body_skeleton_for_envelope(envelope),
                ),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=(length_metadata,),
                    array_initialization_vector_alignment_metadata=(
                        alignment_metadata,
                    ),
                ),
            )
        lookup = lowering_array_body_pipeline._build_array_body_envelope_skeleton_lookup(
            request,
        )
        self.assertTrue(lookup.is_ok, lookup.diagnostics)
        return lowering_array_body_pipeline._lower_exact_array_initialization_stage_pipeline(
            item,
            request,
            envelope_stage,
            lookup.unwrap(),
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
                self.assertEqual(len(implementation.selected_branch_body_handoffs), 1)
                handoff = implementation.selected_branch_body_handoffs[0]
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
                self.assertEqual(
                    len(implementation.selected_branch_body_assignment_forms),
                    1,
                )
                self.assertEqual(len(implementation.selected_branch_body_irs), 1)
                self.assertEqual(len(implementation.selected_body_envelopes), 1)
                assignment_form = implementation.selected_branch_body_assignment_forms[0]
                body_ir = implementation.selected_branch_body_irs[0]
                envelope = implementation.selected_body_envelopes[0]
                if expected_literal is None:
                    assert isinstance(handoff, NoSelectedBranchBodyHandoff)
                    self.assertEqual(handoff.selected_type_tag, type_tag)
                    assert isinstance(
                        assignment_form,
                        NoSelectedBranchBodyAssignmentFormRecognition,
                    )
                    self.assertEqual(assignment_form.selected_type_tag, type_tag)
                    assert isinstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr)
                    self.assertEqual(body_ir.selected_type_tag, type_tag)
                    assert isinstance(envelope, NoSelectedBodyEnvelopeIr)
                    self.assertEqual(envelope.selected_type_tag, type_tag)
                    self.assertEqual(envelope.entries, ())
                else:
                    assert isinstance(handoff, OpaqueSelectedBranchBodyHandoff)
                    self.assertEqual(handoff.selected_type_tag, type_tag)
                    self.assertEqual(handoff.selected_literal, expected_literal)
                    self.assertEqual(
                        handoff.opaque_body_text,
                        expected_body_by_literal[expected_literal],
                    )
                    assert isinstance(
                        assignment_form,
                        SelectedBranchBodyAssignmentFormRecognition,
                    )
                    self.assertEqual(assignment_form.selected_type_tag, type_tag)
                    self.assertEqual(assignment_form.selected_literal, expected_literal)
                    self.assertEqual(
                        assignment_form.original_opaque_body_text,
                        expected_body_by_literal[expected_literal],
                    )
                    assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
                    self.assertEqual(body_ir.selected_type_tag, type_tag)
                    self.assertEqual(body_ir.selected_literal, expected_literal)
                    self.assertEqual(
                        body_ir.original_opaque_body_text,
                        expected_body_by_literal[expected_literal],
                    )
                    assert isinstance(envelope, SelectedBodyEnvelopeIr)
                    self.assertEqual(envelope.selected_type_tag, type_tag)
                    self.assertEqual(len(envelope.entries), 1)
                    self.assertEqual(envelope.entries[0].source_body_ir, body_ir)
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
                        "selected_body_lowering",
                        "selected_body_form_recognition",
                        "selected_body_ir_lowering",
                        "selected_body_envelope_lowering",
                    ),
                )
                self.assertEqual(implementation.generation_stages[-5].output, chain)
                self.assertEqual(implementation.generation_stages[-4].output, handoff)
                self.assertEqual(
                    implementation.generation_stages[-3].output,
                    assignment_form,
                )
                self.assertEqual(implementation.generation_stages[-2].output, body_ir)
                self.assertEqual(implementation.generation_stages[-1].output, envelope)

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
        no_match_handoffs = tuple(
            implementation.selected_branch_body_handoffs[0]
            for implementation in result.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag in ("si8", "ui8")
        )
        self.assertEqual(len(no_match_handoffs), 2)
        for handoff in no_match_handoffs:
            assert isinstance(handoff, NoSelectedBranchBodyHandoff)
            self.assertEqual(handoff.attempted_literals, (2, 4, 8))
        no_match_forms = tuple(
            implementation.selected_branch_body_assignment_forms[0]
            for implementation in result.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag in ("si8", "ui8")
        )
        self.assertEqual(len(no_match_forms), 2)
        for form in no_match_forms:
            assert isinstance(form, NoSelectedBranchBodyAssignmentFormRecognition)
            self.assertEqual(form.attempted_literals, (2, 4, 8))
        no_match_body_irs = tuple(
            implementation.selected_branch_body_irs[0]
            for implementation in result.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag in ("si8", "ui8")
        )
        self.assertEqual(len(no_match_body_irs), 2)
        for body_ir in no_match_body_irs:
            assert isinstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr)
            self.assertEqual(body_ir.attempted_literals, (2, 4, 8))
        no_match_envelopes = tuple(
            implementation.selected_body_envelopes[0]
            for implementation in result.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag in ("si8", "ui8")
        )
        self.assertEqual(len(no_match_envelopes), 2)
        for envelope in no_match_envelopes:
            assert isinstance(envelope, NoSelectedBodyEnvelopeIr)
            self.assertEqual(envelope.attempted_literals, (2, 4, 8))
            self.assertEqual(envelope.entries, ())

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
            tuple(stage.output for stage in implementation.generation_stages[1:-4]),
            (value, *predicates, chain),
        )
        handoff = implementation.generation_stages[-4].output
        assert isinstance(handoff, OpaqueSelectedBranchBodyHandoff)
        self.assertEqual(handoff.candidate_id, implementation.candidate_id)
        self.assertEqual(handoff.selected_type_tag, "ui16")
        self.assertEqual(handoff.selected_literal, 2)
        self.assertEqual(handoff.opaque_body_text, "pg = intrin<svptrue_b16>();")
        self.assertEqual(handoff.source_location, chain.condition_location)
        self.assertIn(implementation.candidate_id, handoff.originating_branch_chain_id)
        form = implementation.generation_stages[-3].output
        assert isinstance(form, SelectedBranchBodyAssignmentFormRecognition)
        self.assertEqual(form.candidate_id, implementation.candidate_id)
        self.assertEqual(form.assignment_target_text, "pg")
        self.assertEqual(form.opaque_rhs_text, "intrin<svptrue_b16>()")
        self.assertEqual(form.direct_intrinsic_token_text, "svptrue_b16")
        body_ir = implementation.generation_stages[-2].output
        assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
        self.assertEqual(body_ir.candidate_id, implementation.candidate_id)
        self.assertEqual(body_ir.assignment_target_text, "pg")
        self.assertEqual(body_ir.opaque_rhs_text, "intrin<svptrue_b16>()")
        self.assertEqual(body_ir.direct_intrinsic_token_text, "svptrue_b16")
        self.assertEqual(body_ir.direct_intrinsic_argument_texts, ())

    def test_selected_size_byte_branch_bodies_are_opaque_handoffs(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation_by_tag = {
            implementation.generation_branch_chains[0].type_tag: implementation
            for implementation in result.unwrap().implementations
        }
        cases = (
            ("si16", 2, "pg = intrin<svptrue_b16>();"),
            ("ui32", 4, "pg = intrin<svptrue_b32>();"),
            ("f64", 8, "pg = intrin<svptrue_b64>();"),
        )
        for type_tag, literal, body_text in cases:
            with self.subTest(type_tag=type_tag):
                implementation = implementation_by_tag[type_tag]
                handoff = implementation.selected_branch_body_handoffs[0]
                chain = implementation.generation_branch_chains[0]

                assert isinstance(handoff, OpaqueSelectedBranchBodyHandoff)
                self.assertEqual(handoff.candidate_id, implementation.candidate_id)
                self.assertEqual(handoff.selected_type_tag, type_tag)
                self.assertEqual(handoff.selected_literal, literal)
                self.assertEqual(handoff.opaque_body_text, body_text)
                self.assertEqual(handoff.source_location, chain.condition_location)
                self.assertIn(
                    "generation-size-byte-branch-chain",
                    handoff.originating_branch_chain_id,
                )
                self.assertEqual(implementation.statements, ())

    def test_selected_size_byte_branch_assignment_forms_are_recognized(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation_by_tag = {
            implementation.generation_branch_chains[0].type_tag: implementation
            for implementation in result.unwrap().implementations
        }
        cases = (
            ("si16", 2, "intrin<svptrue_b16>()", "svptrue_b16"),
            ("ui32", 4, "intrin<svptrue_b32>()", "svptrue_b32"),
            ("f64", 8, "intrin<svptrue_b64>()", "svptrue_b64"),
        )
        for type_tag, literal, rhs_text, token_text in cases:
            with self.subTest(type_tag=type_tag):
                implementation = implementation_by_tag[type_tag]
                handoff = implementation.selected_branch_body_handoffs[0]
                form = implementation.selected_branch_body_assignment_forms[0]

                assert isinstance(handoff, OpaqueSelectedBranchBodyHandoff)
                assert isinstance(form, SelectedBranchBodyAssignmentFormRecognition)
                self.assertEqual(form.candidate_id, handoff.candidate_id)
                self.assertEqual(form.selected_type_tag, type_tag)
                self.assertEqual(form.selected_literal, literal)
                self.assertEqual(
                    form.originating_branch_chain_id,
                    handoff.originating_branch_chain_id,
                )
                self.assertEqual(
                    form.original_opaque_body_text,
                    handoff.opaque_body_text,
                )
                self.assertEqual(
                    form.selected_statement_location,
                    handoff.source_location,
                )
                self.assertEqual(form.assignment_target_text, "pg")
                self.assertEqual(form.opaque_rhs_text, rhs_text)
                self.assertEqual(form.direct_intrinsic_token_text, token_text)
                self.assertEqual(
                    implementation.generation_stages[-3],
                    GenerationLoweringStage(
                        stage="selected_body_form_recognition",
                        output=form,
                    ),
                )
                body_ir = implementation.selected_branch_body_irs[0]
                assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
                self.assertEqual(
                    implementation.generation_stages[-2],
                    GenerationLoweringStage(
                        stage="selected_body_ir_lowering",
                        output=body_ir,
                    ),
                )

    def test_assignment_form_recognition_does_not_map_literal_to_intrinsic(
        self,
    ) -> None:
        handoff = self.assignment_handoff(
            "pg = intrin<svptrue_b16>();",
            selected_literal=8,
            selected_type_tag="f64",
        )

        result = recognize_selected_branch_body_assignment_form(handoff)

        self.assertTrue(result.is_ok, result.diagnostics)
        form = result.unwrap()
        assert isinstance(form, SelectedBranchBodyAssignmentFormRecognition)
        self.assertEqual(form.selected_literal, 8)
        self.assertEqual(form.direct_intrinsic_token_text, "svptrue_b16")

    def test_selected_assignment_direct_intrinsic_body_ir_records_are_lowered(
        self,
    ) -> None:
        cases = (
            ("si16", 2, "svptrue_b16", "intrin<svptrue_b16>()"),
            ("ui32", 4, "svptrue_b32", "intrin<svptrue_b32>()"),
            ("f64", 8, "svptrue_b64", "intrin<svptrue_b64>()"),
        )

        for type_tag, literal, token_text, rhs_text in cases:
            with self.subTest(token_text=token_text):
                form = SelectedBranchBodyAssignmentFormRecognition(
                    candidate_id="candidate-1",
                    selected_type_tag=type_tag,
                    selected_literal=literal,
                    originating_branch_chain_id="candidate-1:chain",
                    original_opaque_body_text=f"pg = {rhs_text};",
                    selected_statement_location=SourceLocation(
                        Path("array.tsl"),
                        107,
                        15,
                    ),
                    assignment_target_text="pg",
                    opaque_rhs_text=rhs_text,
                    direct_intrinsic_token_text=token_text,
                )

                result = lower_selected_branch_body_ir(
                    GenerationLoweringStage(
                        stage="selected_body_form_recognition",
                        output=form,
                    )
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                body_ir = result.unwrap()
                assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
                self.assertEqual(body_ir.candidate_id, "candidate-1")
                self.assertEqual(body_ir.selected_type_tag, type_tag)
                self.assertEqual(body_ir.selected_literal, literal)
                self.assertEqual(
                    body_ir.originating_branch_chain_id,
                    "candidate-1:chain",
                )
                self.assertEqual(body_ir.original_opaque_body_text, f"pg = {rhs_text};")
                self.assertEqual(body_ir.assignment_target_text, "pg")
                self.assertEqual(body_ir.opaque_rhs_text, rhs_text)
                self.assertEqual(body_ir.direct_intrinsic_token_text, token_text)
                self.assertEqual(body_ir.direct_intrinsic_argument_texts, ())

    def test_no_selected_body_form_lowers_to_no_body_ir_for_byte_size_one(
        self,
    ) -> None:
        for type_tag in ("si8", "ui8"):
            with self.subTest(type_tag=type_tag):
                form = NoSelectedBranchBodyAssignmentFormRecognition(
                    candidate_id=f"{type_tag}-candidate",
                    selected_type_tag=type_tag,
                    source_location=SourceLocation(Path("array.tsl"), 107, 15),
                    originating_branch_chain_id=f"{type_tag}:chain",
                    attempted_literals=(2, 4, 8),
                )

                result = lower_selected_branch_body_ir(form)

                self.assertTrue(result.is_ok, result.diagnostics)
                body_ir = result.unwrap()
                assert isinstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr)
                self.assertEqual(body_ir.candidate_id, f"{type_tag}-candidate")
                self.assertEqual(body_ir.selected_type_tag, type_tag)
                self.assertEqual(body_ir.originating_branch_chain_id, f"{type_tag}:chain")
                self.assertEqual(body_ir.attempted_literals, (2, 4, 8))

    def test_body_ir_lowering_preserves_literal_token_mismatch(self) -> None:
        form = SelectedBranchBodyAssignmentFormRecognition(
            candidate_id="candidate-1",
            selected_type_tag="f64",
            selected_literal=8,
            originating_branch_chain_id="candidate-1:chain",
            original_opaque_body_text="pg = intrin<svptrue_b16>();",
            selected_statement_location=SourceLocation(Path("array.tsl"), 107, 15),
            assignment_target_text="pg",
            opaque_rhs_text="intrin<svptrue_b16>()",
            direct_intrinsic_token_text="svptrue_b16",
        )

        result = lower_selected_branch_body_ir(form)

        self.assertTrue(result.is_ok, result.diagnostics)
        body_ir = result.unwrap()
        assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
        self.assertEqual(body_ir.selected_literal, 8)
        self.assertEqual(body_ir.direct_intrinsic_token_text, "svptrue_b16")

    def test_body_ir_lowering_does_not_parse_original_body_text(self) -> None:
        form = SelectedBranchBodyAssignmentFormRecognition(
            candidate_id="candidate-1",
            selected_type_tag="si16",
            selected_literal=2,
            originating_branch_chain_id="candidate-1:chain",
            original_opaque_body_text="mask = value<generation>(vector::length);",
            selected_statement_location=SourceLocation(Path("array.tsl"), 107, 15),
            assignment_target_text="pg",
            opaque_rhs_text="intrin<svptrue_b16>()",
            direct_intrinsic_token_text="svptrue_b16",
        )

        result = lower_selected_branch_body_ir(form)

        self.assertTrue(result.is_ok, result.diagnostics)
        body_ir = result.unwrap()
        assert isinstance(body_ir, SelectedAssignmentDirectIntrinsicBodyIr)
        self.assertEqual(
            body_ir.original_opaque_body_text,
            "mask = value<generation>(vector::length);",
        )
        self.assertEqual(body_ir.assignment_target_text, "pg")
        self.assertEqual(body_ir.opaque_rhs_text, "intrin<svptrue_b16>()")
        self.assertEqual(body_ir.direct_intrinsic_token_text, "svptrue_b16")

    def test_body_ir_lowering_rejects_unsupported_source_stage(self) -> None:
        statement = TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            )
        )
        stage = GenerationLoweringStage(
            stage="selected_body_lowering",
            output=statement,
        )

        result = lower_selected_branch_body_ir(stage)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-IR-SOURCE-UNSUPPORTED",
            severity="error",
        )

    def test_size_byte_handoff_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            tuple(
                implementation.selected_branch_body_handoffs
                for implementation in first.unwrap().implementations
            ),
            tuple(
                implementation.selected_branch_body_handoffs
                for implementation in second.unwrap().implementations
            ),
        )

    def test_selected_body_ir_lowering_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            tuple(
                implementation.selected_branch_body_irs
                for implementation in first.unwrap().implementations
            ),
            tuple(
                implementation.selected_branch_body_irs
                for implementation in second.unwrap().implementations
            ),
        )

    def test_selected_body_envelope_records_are_lowered(self) -> None:
        cases = (
            ("si16", 2, "svptrue_b16", "intrin<svptrue_b16>()"),
            ("ui32", 4, "svptrue_b32", "intrin<svptrue_b32>()"),
            ("f64", 8, "svptrue_b64", "intrin<svptrue_b64>()"),
        )

        for type_tag, literal, token_text, rhs_text in cases:
            with self.subTest(token_text=token_text):
                body_ir = self.selected_body_ir(
                    selected_type_tag=type_tag,
                    selected_literal=literal,
                    token_text=token_text,
                    rhs_text=rhs_text,
                    original_body_text=f"pg = {rhs_text};",
                )

                result = lower_selected_body_envelope(
                    GenerationLoweringStage(
                        stage="selected_body_ir_lowering",
                        output=body_ir,
                    )
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                envelope = result.unwrap()
                assert isinstance(envelope, SelectedBodyEnvelopeIr)
                self.assertEqual(envelope.candidate_id, body_ir.candidate_id)
                self.assertEqual(envelope.selected_type_tag, type_tag)
                self.assertEqual(envelope.source_location, body_ir.source_location)
                self.assertEqual(
                    envelope.originating_branch_chain_id,
                    body_ir.originating_branch_chain_id,
                )
                self.assertEqual(len(envelope.entries), 1)
                entry = envelope.entries[0]
                assert isinstance(entry, SelectedBodyEnvelopeEntry)
                self.assertIs(entry.source_body_ir, body_ir)
                self.assertEqual(entry.selected_literal, literal)
                self.assertEqual(entry.assignment_target_text, "pg")
                self.assertEqual(entry.opaque_rhs_text, rhs_text)
                self.assertEqual(entry.direct_intrinsic_token_text, token_text)
                self.assertEqual(entry.direct_intrinsic_argument_texts, ())
                self.assertEqual(entry.original_opaque_body_text, f"pg = {rhs_text};")

    def test_no_body_ir_lowers_to_no_selected_body_envelope(self) -> None:
        for type_tag in ("si8", "ui8"):
            with self.subTest(type_tag=type_tag):
                body_ir = NoSelectedAssignmentDirectIntrinsicBodyIr(
                    candidate_id=f"{type_tag}-candidate",
                    selected_type_tag=type_tag,
                    source_location=SourceLocation(Path("array.tsl"), 107, 15),
                    originating_branch_chain_id=f"{type_tag}:chain",
                    attempted_literals=(2, 4, 8),
                )

                result = lower_selected_body_envelope(body_ir)

                self.assertTrue(result.is_ok, result.diagnostics)
                envelope = result.unwrap()
                assert isinstance(envelope, NoSelectedBodyEnvelopeIr)
                self.assertIs(envelope.source_body_ir, body_ir)
                self.assertEqual(envelope.candidate_id, f"{type_tag}-candidate")
                self.assertEqual(envelope.selected_type_tag, type_tag)
                self.assertEqual(envelope.attempted_literals, (2, 4, 8))
                self.assertEqual(envelope.entries, ())

    def test_selected_body_envelope_preserves_m62_facts_without_reparsing(
        self,
    ) -> None:
        body_ir = self.selected_body_ir(
            selected_type_tag="si16",
            selected_literal=2,
            token_text="svptrue_b16",
            rhs_text="intrin<svptrue_b16>()",
            original_body_text="mask = value<generation>(vector::length);",
        )

        result = lower_selected_body_envelope(body_ir)

        self.assertTrue(result.is_ok, result.diagnostics)
        envelope = result.unwrap()
        assert isinstance(envelope, SelectedBodyEnvelopeIr)
        entry = envelope.entries[0]
        self.assertEqual(
            entry.original_opaque_body_text,
            "mask = value<generation>(vector::length);",
        )
        self.assertEqual(entry.assignment_target_text, "pg")
        self.assertEqual(entry.opaque_rhs_text, "intrin<svptrue_b16>()")
        self.assertEqual(entry.direct_intrinsic_token_text, "svptrue_b16")

    def test_selected_body_envelope_preserves_literal_token_mismatch(self) -> None:
        body_ir = self.selected_body_ir(
            selected_type_tag="f64",
            selected_literal=8,
            token_text="svptrue_b16",
            rhs_text="intrin<svptrue_b16>()",
            original_body_text="pg = intrin<svptrue_b16>();",
        )

        result = lower_selected_body_envelope(body_ir)

        self.assertTrue(result.is_ok, result.diagnostics)
        envelope = result.unwrap()
        assert isinstance(envelope, SelectedBodyEnvelopeIr)
        entry = envelope.entries[0]
        self.assertEqual(entry.selected_literal, 8)
        self.assertEqual(entry.direct_intrinsic_token_text, "svptrue_b16")

    def test_selected_body_envelope_lowering_is_deterministic(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            tuple(
                implementation.selected_body_envelopes
                for implementation in first.unwrap().implementations
            ),
            tuple(
                implementation.selected_body_envelopes
                for implementation in second.unwrap().implementations
            ),
        )

    def test_selected_body_envelope_rejects_unsupported_source_stage(self) -> None:
        form = NoSelectedBranchBodyAssignmentFormRecognition(
            candidate_id="candidate-1",
            selected_type_tag="si8",
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
            attempted_literals=(2, 4, 8),
        )
        stage = GenerationLoweringStage(
            stage="selected_body_form_recognition",
            output=form,
        )

        result = lower_selected_body_envelope(stage)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )
        self.assertIn("M62 values", result.diagnostics[0].message)

    def test_selected_body_envelope_reports_inconsistent_boundary_state(
        self,
    ) -> None:
        body_ir = object.__new__(SelectedAssignmentDirectIntrinsicBodyIr)
        object.__setattr__(body_ir, "candidate_id", "candidate-1")
        object.__setattr__(body_ir, "selected_type_tag", "si16")
        object.__setattr__(body_ir, "selected_literal", 2)
        object.__setattr__(body_ir, "originating_branch_chain_id", "candidate-1:chain")
        object.__setattr__(
            body_ir,
            "original_opaque_body_text",
            "pg = intrin<svptrue_b16>();",
        )
        object.__setattr__(
            body_ir,
            "source_location",
            SourceLocation(Path("array.tsl"), 107, 15),
        )
        object.__setattr__(body_ir, "assignment_target_text", "pg")
        object.__setattr__(body_ir, "opaque_rhs_text", "intrin<svptrue_b16>()")
        object.__setattr__(body_ir, "direct_intrinsic_token_text", "svptrue_b16")
        object.__setattr__(body_ir, "direct_intrinsic_argument_texts", ("unexpected",))

        result = lower_selected_body_envelope(body_ir)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )
        self.assertIn("empty argument list", result.diagnostics[0].message)

    def test_lower_candidates_assembles_exact_array_body_envelopes_from_typed_skeletons(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        skeletons = tuple(
            self.exact_array_body_skeleton_for_envelope(envelope)
            for implementation in baseline.unwrap().implementations
            for envelope in implementation.selected_body_envelopes
            if envelope.selected_type_tag in CONCRETE_INTEGER_TAGS
        )
        length_metadata = tuple(
            self.vector_length_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
                lanes=17,
            )
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag
            in CONCRETE_INTEGER_TAGS
        )
        alignment_metadata = tuple(
            self.vector_alignment_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
                alignment_bytes=64,
            )
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag
            in CONCRETE_INTEGER_TAGS
        )

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=skeletons,
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=length_metadata,
                    array_initialization_vector_alignment_metadata=alignment_metadata,
                ),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        implementations = result.unwrap().implementations
        self.assertEqual(len(implementations), len(baseline.unwrap().implementations))
        selected_tokens: set[str] = set()
        no_body_tags: set[str] = set()
        for baseline_impl, implementation in zip(
            baseline.unwrap().implementations,
            implementations,
            strict=True,
        ):
            with self.subTest(candidate_id=implementation.candidate_id):
                baseline_envelope = baseline_impl.selected_body_envelopes[0]
                if baseline_envelope.selected_type_tag not in CONCRETE_INTEGER_TAGS:
                    self.assertEqual(implementation.array_body_envelopes, ())
                    self.assertEqual(
                        implementation.array_initialization_slot_forms,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_helper_requests,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_base_type_resolutions,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_vector_length_resolutions,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_vector_alignment_resolutions,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_helper_set_completions,
                        (),
                    )
                    self.assertEqual(
                        implementation.array_initialization_declaration_shells,
                        (),
                    )
                    self.assertEqual(implementation.array_body_structural_sequences, ())
                    self.assertEqual(
                        implementation.predicate_path_structural_requests,
                        (),
                    )
                    self.assertEqual(
                        implementation.post_branch_intrinsic_call_site_structural_requests,
                        (),
                    )
                    self.assertEqual(
                        tuple(stage.stage for stage in implementation.generation_stages),
                        tuple(stage.stage for stage in baseline_impl.generation_stages),
                    )
                    continue
                self.assertEqual(len(implementation.array_body_envelopes), 1)
                array_envelope = implementation.array_body_envelopes[0]
                self.assertEqual(
                    len(implementation.array_initialization_slot_forms),
                    1,
                )
                slot_form = implementation.array_initialization_slot_forms[0]
                self.assertIs(slot_form.source_envelope, array_envelope)
                self.assertEqual(
                    len(implementation.array_initialization_helper_requests),
                    1,
                )
                helper_request = implementation.array_initialization_helper_requests[0]
                self.assertIs(helper_request.source_form, slot_form)
                self.assertEqual(
                    len(implementation.array_initialization_base_type_resolutions),
                    1,
                )
                base_type_resolution = (
                    implementation.array_initialization_base_type_resolutions[0]
                )
                self.assertIs(base_type_resolution.source_request_ir, helper_request)
                self.assertEqual(
                    base_type_resolution.resolved_type_ref,
                    GenerationTypeRef(
                        kind="base.in",
                        type_tag=array_envelope.selected_type_tag,
                    ),
                )
                self.assertEqual(
                    base_type_resolution.unresolved_requests,
                    helper_request.requests[1:],
                )
                self.assertEqual(
                    len(implementation.array_initialization_vector_length_resolutions),
                    1,
                )
                vector_length_resolution = (
                    implementation.array_initialization_vector_length_resolutions[0]
                )
                self.assertIs(
                    vector_length_resolution.source_base_type_resolution,
                    base_type_resolution,
                )
                self.assertIs(
                    vector_length_resolution.source_vector_length_request,
                    helper_request.requests[1],
                )
                self.assertEqual(
                    vector_length_resolution.resolved_vector_length,
                    ExactArrayInitializationVectorLengthValue(
                        kind="fixed_lanes",
                        lanes=17,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in vector_length_resolution.unresolved_requests
                    ),
                    (
                        "value_generation_vector_alignment",
                        "value_backend_uninit_array",
                    ),
                )
                self.assertEqual(
                    len(
                        implementation.array_initialization_vector_alignment_resolutions
                    ),
                    1,
                )
                vector_alignment_resolution = (
                    implementation.array_initialization_vector_alignment_resolutions[0]
                )
                self.assertIs(
                    vector_alignment_resolution.source_vector_length_resolution,
                    vector_length_resolution,
                )
                self.assertIs(
                    vector_alignment_resolution.source_vector_alignment_request,
                    helper_request.requests[2],
                )
                self.assertEqual(
                    vector_alignment_resolution.resolved_vector_alignment,
                    ExactArrayInitializationVectorAlignmentValue(
                        kind="fixed_bytes",
                        bytes=64,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in (
                            vector_alignment_resolution.unresolved_requests
                        )
                    ),
                    ("value_backend_uninit_array",),
                )
                self.assertEqual(
                    len(implementation.array_initialization_helper_set_completions),
                    1,
                )
                helper_set_completion = (
                    implementation.array_initialization_helper_set_completions[0]
                )
                self.assertIs(
                    helper_set_completion.source_vector_alignment_resolution,
                    vector_alignment_resolution,
                )
                self.assertIs(
                    helper_set_completion.source_backend_uninit_request,
                    helper_request.requests[3],
                )
                self.assertEqual(
                    helper_set_completion.unresolved_backend_uninit.policy,
                    "deferred_backend_value",
                )
                self.assertEqual(
                    len(implementation.array_initialization_declaration_shells),
                    1,
                )
                declaration_shell = (
                    implementation.array_initialization_declaration_shells[0]
                )
                self.assertIs(
                    declaration_shell.source_helper_set_completion,
                    helper_set_completion,
                )
                self.assertIs(declaration_shell.source_slot_form, slot_form)
                self.assertIs(declaration_shell.source_envelope, array_envelope)
                self.assertEqual(declaration_shell.declaration_kind, "var<typed>")
                self.assertEqual(declaration_shell.array_type_kind, "array_type")
                self.assertIs(
                    declaration_shell.base_type_ref,
                    base_type_resolution.resolved_type_ref,
                )
                self.assertIs(
                    declaration_shell.vector_length,
                    vector_length_resolution.resolved_vector_length,
                )
                self.assertIs(
                    declaration_shell.vector_alignment,
                    vector_alignment_resolution.resolved_vector_alignment,
                )
                self.assertIs(
                    declaration_shell.unresolved_backend_uninit,
                    helper_set_completion.unresolved_backend_uninit,
                )
                self.assertEqual(len(implementation.array_body_structural_sequences), 1)
                structural_sequence = implementation.array_body_structural_sequences[0]
                self.assertIs(structural_sequence.source_envelope, array_envelope)
                self.assertIs(structural_sequence.declaration_shell, declaration_shell)
                self.assertEqual(
                    len(implementation.predicate_path_structural_requests),
                    1,
                )
                predicate_path = implementation.predicate_path_structural_requests[0]
                self.assertIs(predicate_path.source_sequence, structural_sequence)
                post_branch_requests = (
                    implementation.post_branch_intrinsic_call_site_structural_requests
                )
                self.assertEqual(len(post_branch_requests), 1)
                post_branch_call_site = post_branch_requests[0]
                self.assertIs(
                    post_branch_call_site.source_predicate_path,
                    predicate_path,
                )
                self.assertIs(
                    post_branch_call_site.source_sequence,
                    structural_sequence,
                )
                self.assertIs(
                    implementation.generation_stages[-12].output,
                    array_envelope,
                )
                self.assertEqual(
                    implementation.generation_stages[-12].stage,
                    "array_body_envelope_slot_assembly",
                )
                self.assertIs(implementation.generation_stages[-11].output, slot_form)
                self.assertEqual(
                    implementation.generation_stages[-11].stage,
                    "array_initialization_slot_form_lowering",
                )
                self.assertIs(
                    implementation.generation_stages[-10].output,
                    helper_request,
                )
                self.assertEqual(
                    implementation.generation_stages[-10].stage,
                    "array_initialization_helper_request_lowering",
                )
                self.assertIs(
                    implementation.generation_stages[-9].output,
                    base_type_resolution,
                )
                self.assertEqual(
                    implementation.generation_stages[-9].stage,
                    "array_initialization_base_type_request_resolution",
                )
                self.assertEqual(
                    implementation.generation_stages[-8].stage,
                    "array_initialization_vector_length_request_resolution",
                )
                self.assertIs(
                    implementation.generation_stages[-8].output,
                    vector_length_resolution,
                )
                self.assertEqual(
                    implementation.generation_stages[-7].stage,
                    "array_initialization_vector_alignment_request_resolution",
                )
                self.assertIs(
                    implementation.generation_stages[-7].output,
                    vector_alignment_resolution,
                )
                self.assertEqual(
                    implementation.generation_stages[-6].stage,
                    "array_initialization_helper_set_completion",
                )
                self.assertIs(
                    implementation.generation_stages[-6].output,
                    helper_set_completion,
                )
                self.assertEqual(
                    implementation.generation_stages[-5].stage,
                    "array_initialization_declaration_shell_lowering",
                )
                self.assertIs(
                    implementation.generation_stages[-5].output,
                    declaration_shell,
                )
                self.assertEqual(
                    implementation.generation_stages[-4].stage,
                    "array_body_structural_sequence_classification",
                )
                self.assertIs(
                    implementation.generation_stages[-4].output,
                    structural_sequence,
                )
                self.assertEqual(
                    implementation.generation_stages[-3].stage,
                    "predicate_path_structural_request_lowering",
                )
                self.assertIs(
                    implementation.generation_stages[-3].output,
                    predicate_path,
                )
                self.assertEqual(
                    implementation.generation_stages[-2].stage,
                    "post_branch_intrinsic_call_site_structural_request_lowering",
                )
                self.assertIs(
                    implementation.generation_stages[-2].output,
                    post_branch_call_site,
                )
                self.assertEqual(
                    implementation.generation_stages[-1].stage,
                    "return_emission_structural_request_lowering",
                )
                self.assertEqual(
                    tuple(stage.stage for stage in implementation.generation_stages[:-12]),
                    tuple(stage.stage for stage in baseline_impl.generation_stages),
                )
                self.assertEqual(
                    tuple(stage.output for stage in implementation.generation_stages[:-12]),
                    tuple(stage.output for stage in baseline_impl.generation_stages),
                )
                self.assertEqual(
                    implementation.generation_stages[-13].stage,
                    "selected_body_envelope_lowering",
                )
                self.assertEqual(slot_form.slot_ordinal, 0)
                self.assertEqual(
                    slot_form.original_slot_text,
                    ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                        "opaque_pre_branch_array_initialization"
                    ],
                )
                self.assertEqual(slot_form.variable_token, "tmp")
                self.assertEqual(
                    tuple(slot.label for slot in array_envelope.slots[1:]),
                    ARRAY_BODY_SLOT_LABELS[1:],
                )
                for slot in array_envelope.slots[1:]:
                    if isinstance(slot, ExactArrayBodyEnvelopeOpaqueSlot):
                        self.assertEqual(
                            slot.opaque_source_text,
                            ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[slot.label],
                        )
                nested = array_envelope.selected_body_slot.selected_body_envelope
                self.assertIs(nested, implementation.selected_body_envelopes[0])
                if isinstance(nested, SelectedBodyEnvelopeIr):
                    selected_tokens.add(nested.entries[0].direct_intrinsic_token_text)
                else:
                    self.assertIsInstance(nested, NoSelectedBodyEnvelopeIr)
                    self.assertEqual(nested.entries, ())
                    no_body_tags.add(nested.selected_type_tag)

        self.assertEqual(
            selected_tokens,
            {"svptrue_b16", "svptrue_b32", "svptrue_b64"},
        )
        self.assertEqual(no_body_tags, {"si8", "ui8"})

    def test_lower_candidates_without_skeletons_preserves_m63_only_behavior(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        for implementation in result.unwrap().implementations:
            with self.subTest(candidate_id=implementation.candidate_id):
                self.assertEqual(implementation.array_body_envelopes, ())
                self.assertEqual(implementation.array_initialization_slot_forms, ())
                self.assertEqual(
                    implementation.array_initialization_helper_requests,
                    (),
                )
                self.assertEqual(
                    implementation.array_initialization_base_type_resolutions,
                    (),
                )
                self.assertEqual(
                    implementation.array_initialization_vector_length_resolutions,
                    (),
                )
                self.assertEqual(
                    implementation.array_initialization_vector_alignment_resolutions,
                    (),
                )
                self.assertEqual(
                    implementation.array_initialization_helper_set_completions,
                    (),
                )
                self.assertEqual(
                    implementation.array_initialization_declaration_shells,
                    (),
                )
                self.assertEqual(implementation.array_body_structural_sequences, ())
                self.assertEqual(implementation.predicate_path_structural_requests, ())
                self.assertEqual(
                    implementation.post_branch_intrinsic_call_site_structural_requests,
                    (),
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
                        "selected_body_lowering",
                        "selected_body_form_recognition",
                        "selected_body_ir_lowering",
                        "selected_body_envelope_lowering",
                    ),
                )

    def test_lower_candidates_reports_missing_required_array_body_skeleton(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        envelope = next(
            implementation.selected_body_envelopes[0]
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes[0].selected_type_tag == "si16"
        )

        result = lower_candidates(
            selection,
            LoweringRequest(
                required_array_body_envelope_skeletons=(
                    ExactArrayBodyEnvelopeSkeletonRequirement(
                        candidate_id=envelope.candidate_id,
                        selected_type_tag=envelope.selected_type_tag,
                        originating_branch_chain_id=(
                            envelope.originating_branch_chain_id
                        ),
                        source_location=SourceLocation(Path("request.tsl"), 12, 3),
                    ),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-MISSING",
            severity="error",
            path="request.tsl",
            line=12,
            column=3,
        )
        self.assertIn(envelope.candidate_id, result.diagnostics[0].message)
        self.assertIn(envelope.selected_type_tag, result.diagnostics[0].message)

    def test_lower_candidates_reports_duplicate_and_conflicting_array_body_skeletons(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        envelope = baseline.unwrap().implementations[0].selected_body_envelopes[0]
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)

        cases = (
            (
                "duplicate",
                (skeleton, skeleton),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-DUPLICATE",
            ),
            (
                "conflict",
                (skeleton, replace(skeleton, is_exact_array_body_shape=False)),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-CONFLICT",
            ),
        )
        for name, skeletons, code in cases:
            with self.subTest(name=name):
                result = lower_candidates(
                    selection,
                    LoweringRequest(array_body_envelope_skeletons=skeletons),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=105,
                    column=15,
                )
                self.assertIn("exactly one", result.diagnostics[0].message)

    def test_lower_candidates_reports_orphan_array_body_skeletons(
        self,
    ) -> None:
        selection = self.selection_for("lower_add")

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(self.exact_array_body_skeleton(),),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-ORPHAN",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("no M63 selected-body envelope", result.diagnostics[0].message)

    def test_lower_candidates_reports_array_body_skeleton_provenance_mismatch(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        envelope = baseline.unwrap().implementations[0].selected_body_envelopes[0]
        skeleton = self.exact_array_body_skeleton_for_envelope(
            envelope,
            branch_chain_id="other-branch-chain",
        )

        result = lower_candidates(
            selection,
            LoweringRequest(array_body_envelope_skeletons=(skeleton,)),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("M63 envelope provenance", result.diagnostics[0].message)

    def test_lower_candidates_preserves_m64_non_exact_skeleton_diagnostic(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        envelope = baseline.unwrap().implementations[0].selected_body_envelopes[0]

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(
                    self.exact_array_body_skeleton_for_envelope(
                        envelope,
                        exact=False,
                    ),
                ),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("exact", result.diagnostics[0].message)

    def test_exact_array_initialization_stage_pipeline_lowers_selected_paths(
        self,
    ) -> None:
        cases = (
            ("si16", "svptrue_b16"),
            ("si32", "svptrue_b32"),
            ("si64", "svptrue_b64"),
        )

        for selected_type_tag, token_text in cases:
            with self.subTest(selected_type_tag=selected_type_tag):
                result = self.exact_array_initialization_stage_pipeline(
                    selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                pipeline = result.unwrap()
                self.assertEqual(len(pipeline.array_body_envelopes), 1)
                array_envelope = pipeline.array_body_envelopes[0]
                nested = array_envelope.selected_body_slot.selected_body_envelope
                assert isinstance(nested, SelectedBodyEnvelopeIr)
                self.assertEqual(
                    nested.entries[0].direct_intrinsic_token_text,
                    token_text,
                )
                self.assertEqual(len(pipeline.array_initialization_slot_forms), 1)
                slot_form = pipeline.array_initialization_slot_forms[0]
                self.assertIs(slot_form.source_envelope, array_envelope)
                self.assertEqual(
                    slot_form.original_slot_text,
                    ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                        "opaque_pre_branch_array_initialization"
                    ],
                )
                self.assertEqual(
                    len(pipeline.array_initialization_helper_requests),
                    1,
                )
                helper_request = pipeline.array_initialization_helper_requests[0]
                self.assertIs(helper_request.source_form, slot_form)
                self.assertEqual(
                    len(pipeline.array_initialization_base_type_resolutions),
                    1,
                )
                resolution = pipeline.array_initialization_base_type_resolutions[0]
                self.assertIs(resolution.source_request_ir, helper_request)
                self.assertEqual(
                    resolution.resolved_type_ref,
                    GenerationTypeRef(
                        kind="base.in",
                        type_tag=selected_type_tag,
                    ),
                )
                self.assertEqual(
                    len(pipeline.array_initialization_vector_length_resolutions),
                    1,
                )
                vector_length_resolution = (
                    pipeline.array_initialization_vector_length_resolutions[0]
                )
                self.assertIs(
                    vector_length_resolution.source_base_type_resolution,
                    resolution,
                )
                self.assertEqual(
                    vector_length_resolution.resolved_vector_length,
                    ExactArrayInitializationVectorLengthValue(
                        kind="fixed_lanes",
                        lanes=17,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in (
                            vector_length_resolution.unresolved_requests
                        )
                    ),
                    (
                        "value_generation_vector_alignment",
                        "value_backend_uninit_array",
                    ),
                )
                self.assertEqual(
                    len(pipeline.array_initialization_vector_alignment_resolutions),
                    1,
                )
                vector_alignment_resolution = (
                    pipeline.array_initialization_vector_alignment_resolutions[0]
                )
                self.assertIs(
                    vector_alignment_resolution.source_vector_length_resolution,
                    vector_length_resolution,
                )
                self.assertEqual(
                    vector_alignment_resolution.resolved_vector_alignment,
                    ExactArrayInitializationVectorAlignmentValue(
                        kind="fixed_bytes",
                        bytes=64,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in (
                            vector_alignment_resolution.unresolved_requests
                        )
                    ),
                    ("value_backend_uninit_array",),
                )
                self.assertEqual(
                    len(pipeline.array_initialization_helper_set_completions),
                    1,
                )
                helper_set_completion = (
                    pipeline.array_initialization_helper_set_completions[0]
                )
                self.assertIs(
                    helper_set_completion.source_vector_alignment_resolution,
                    vector_alignment_resolution,
                )
                self.assertIs(
                    helper_set_completion.source_backend_uninit_request,
                    helper_request.requests[3],
                )
                self.assertEqual(
                    helper_set_completion.unresolved_backend_uninit.policy,
                    "deferred_backend_value",
                )
                self.assertEqual(
                    len(pipeline.array_initialization_declaration_shells),
                    1,
                )
                declaration_shell = pipeline.array_initialization_declaration_shells[0]
                self.assertIs(
                    declaration_shell.source_helper_set_completion,
                    helper_set_completion,
                )
                self.assertIs(declaration_shell.source_slot_form, slot_form)
                self.assertEqual(declaration_shell.declaration_kind, "var<typed>")
                self.assertEqual(declaration_shell.array_type_kind, "array_type")
                self.assertIs(
                    declaration_shell.base_type_ref,
                    resolution.resolved_type_ref,
                )
                self.assertIs(
                    declaration_shell.vector_length,
                    vector_length_resolution.resolved_vector_length,
                )
                self.assertIs(
                    declaration_shell.vector_alignment,
                    vector_alignment_resolution.resolved_vector_alignment,
                )
                self.assertIs(
                    declaration_shell.unresolved_backend_uninit,
                    helper_set_completion.unresolved_backend_uninit,
                )
                self.assertEqual(len(pipeline.array_body_structural_sequences), 1)
                structural_sequence = pipeline.array_body_structural_sequences[0]
                self.assertIs(structural_sequence.source_envelope, array_envelope)
                self.assertIs(structural_sequence.declaration_shell, declaration_shell)
                self.assertEqual(len(pipeline.predicate_path_structural_requests), 1)
                predicate_path = pipeline.predicate_path_structural_requests[0]
                self.assertIs(predicate_path.source_sequence, structural_sequence)
                post_branch_requests = (
                    pipeline.post_branch_intrinsic_call_site_structural_requests
                )
                self.assertEqual(len(post_branch_requests), 1)
                post_branch_call_site = post_branch_requests[0]
                self.assertIs(
                    post_branch_call_site.source_predicate_path,
                    predicate_path,
                )
                self.assertEqual(
                    tuple(stage.stage for stage in pipeline.stages),
                    (
                        "array_body_envelope_slot_assembly",
                        "array_initialization_slot_form_lowering",
                        "array_initialization_helper_request_lowering",
                        "array_initialization_base_type_request_resolution",
                        "array_initialization_vector_length_request_resolution",
                        "array_initialization_vector_alignment_request_resolution",
                        "array_initialization_helper_set_completion",
                        "array_initialization_declaration_shell_lowering",
                        "array_body_structural_sequence_classification",
                        "predicate_path_structural_request_lowering",
                        "post_branch_intrinsic_call_site_structural_request_lowering",
                        "return_emission_structural_request_lowering",
                    ),
                )
                self.assertEqual(
                    tuple(stage.output for stage in pipeline.stages),
                    (
                        array_envelope,
                        slot_form,
                        helper_request,
                        resolution,
                        vector_length_resolution,
                        vector_alignment_resolution,
                        helper_set_completion,
                        declaration_shell,
                        structural_sequence,
                        predicate_path,
                        post_branch_call_site,
                        pipeline.return_emission_structural_requests[0],
                    ),
                )

    def test_exact_array_initialization_stage_pipeline_lowers_no_body_paths(
        self,
    ) -> None:
        for selected_type_tag in ("si8", "ui8"):
            with self.subTest(selected_type_tag=selected_type_tag):
                result = self.exact_array_initialization_stage_pipeline(
                    selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                pipeline = result.unwrap()
                self.assertEqual(len(pipeline.array_body_envelopes), 1)
                array_envelope = pipeline.array_body_envelopes[0]
                nested = array_envelope.selected_body_slot.selected_body_envelope
                self.assertIsInstance(nested, NoSelectedBodyEnvelopeIr)
                self.assertEqual(nested.entries, ())
                self.assertEqual(
                    pipeline.array_initialization_base_type_resolutions[
                        0
                    ].resolved_type_ref,
                    GenerationTypeRef(
                        kind="base.in",
                        type_tag=selected_type_tag,
                    ),
                )
                self.assertEqual(
                    len(pipeline.array_initialization_vector_length_resolutions),
                    1,
                )
                self.assertEqual(
                    len(pipeline.array_initialization_vector_alignment_resolutions),
                    1,
                )
                self.assertEqual(
                    len(pipeline.array_initialization_helper_set_completions),
                    1,
                )
                self.assertEqual(
                    len(pipeline.array_initialization_declaration_shells),
                    1,
                )
                self.assertEqual(len(pipeline.array_body_structural_sequences), 1)
                self.assertEqual(len(pipeline.predicate_path_structural_requests), 1)
                self.assertEqual(
                    len(
                        pipeline.post_branch_intrinsic_call_site_structural_requests
                    ),
                    1,
                )
                self.assertEqual(len(pipeline.return_emission_structural_requests), 1)
                self.assertEqual(len(pipeline.stages), 12)

    def test_exact_array_initialization_stage_pipeline_no_skeleton_is_empty(
        self,
    ) -> None:
        result = self.exact_array_initialization_stage_pipeline(
            "si16",
            request=LoweringRequest(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        pipeline = result.unwrap()
        self.assertEqual(pipeline.array_body_envelopes, ())
        self.assertEqual(pipeline.array_initialization_slot_forms, ())
        self.assertEqual(pipeline.array_initialization_helper_requests, ())
        self.assertEqual(pipeline.array_initialization_base_type_resolutions, ())
        self.assertEqual(pipeline.array_initialization_vector_length_resolutions, ())
        self.assertEqual(pipeline.array_initialization_vector_alignment_resolutions, ())
        self.assertEqual(pipeline.array_initialization_helper_set_completions, ())
        self.assertEqual(pipeline.array_initialization_declaration_shells, ())
        self.assertEqual(pipeline.array_body_structural_sequences, ())
        self.assertEqual(pipeline.predicate_path_structural_requests, ())
        self.assertEqual(
            pipeline.post_branch_intrinsic_call_site_structural_requests,
            (),
        )
        self.assertEqual(pipeline.return_emission_structural_requests, ())
        self.assertEqual(pipeline.stages, ())
        self.assertIsInstance(
            pipeline.pipeline_snapshot,
            lowering_pipeline.ExactArrayBodyPipelineSnapshot,
        )
        self.assertEqual(pipeline.pipeline_snapshot.steps, ())
        self.assertEqual(pipeline.pipeline_snapshot.pending_backfeed_requests, ())

    def test_exact_array_initialization_stage_pipeline_matches_lower_candidates_tail(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        request = LoweringRequest(
            array_body_envelope_skeletons=(skeleton,),
            generation_context=GenerationContext(
                array_initialization_vector_length_metadata=(
                    self.vector_length_metadata_for_item(item),
                ),
                array_initialization_vector_alignment_metadata=(
                    self.vector_alignment_metadata_for_item(item),
                ),
            ),
        )
        lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(request)
        self.assertTrue(lookup.is_ok, lookup.diagnostics)
        envelope_stage = GenerationLoweringStage(
            stage="selected_body_envelope_lowering",
            output=envelope,
        )
        pipeline = lowering_boundary._lower_exact_array_initialization_stage_pipeline(
            item,
            request,
            envelope_stage,
            lookup.unwrap(),
        )
        plan = lower_candidates(
            self.selection_for("lower_generation_size_byte_branch_chain"),
            request,
        )

        self.assertTrue(pipeline.is_ok, pipeline.diagnostics)
        self.assertTrue(plan.is_ok, plan.diagnostics)
        implementation = plan.unwrap().implementations_by_candidate_id[
            item.candidate_id
        ]
        pipeline_result = pipeline.unwrap()
        self.assertEqual(
            implementation.array_body_envelopes,
            pipeline_result.array_body_envelopes,
        )
        self.assertEqual(
            implementation.array_initialization_slot_forms,
            pipeline_result.array_initialization_slot_forms,
        )
        self.assertEqual(
            implementation.array_initialization_helper_requests,
            pipeline_result.array_initialization_helper_requests,
        )
        self.assertEqual(
            implementation.array_initialization_base_type_resolutions,
            pipeline_result.array_initialization_base_type_resolutions,
        )
        self.assertEqual(
            implementation.array_initialization_vector_length_resolutions,
            pipeline_result.array_initialization_vector_length_resolutions,
        )
        self.assertEqual(
            implementation.array_initialization_vector_alignment_resolutions,
            pipeline_result.array_initialization_vector_alignment_resolutions,
        )
        self.assertEqual(
            implementation.array_initialization_helper_set_completions,
            pipeline_result.array_initialization_helper_set_completions,
        )
        self.assertEqual(
            implementation.array_initialization_declaration_shells,
            pipeline_result.array_initialization_declaration_shells,
        )
        self.assertEqual(
            implementation.array_body_structural_sequences,
            pipeline_result.array_body_structural_sequences,
        )
        self.assertEqual(
            implementation.predicate_path_structural_requests,
            pipeline_result.predicate_path_structural_requests,
        )
        self.assertEqual(
            implementation.post_branch_intrinsic_call_site_structural_requests,
            pipeline_result.post_branch_intrinsic_call_site_structural_requests,
        )
        self.assertEqual(
            implementation.return_emission_structural_requests,
            pipeline_result.return_emission_structural_requests,
        )
        self.assertEqual(implementation.generation_stages[-12:], pipeline_result.stages)
        self.assertEqual(implementation.generation_stages[-13], envelope_stage)

    def test_m77_exact_array_pipeline_snapshot_records_stage_facts(self) -> None:
        result = self.exact_array_initialization_stage_pipeline("si32")

        self.assertTrue(result.is_ok, result.diagnostics)
        pipeline = result.unwrap()
        snapshot = pipeline.pipeline_snapshot
        self.assertIsInstance(snapshot, lowering_pipeline.ExactArrayBodyPipelineSnapshot)
        self.assertEqual(snapshot.stages, pipeline.stages)
        self.assertEqual(
            tuple(step.stage_name for step in snapshot.steps),
            tuple(stage.stage for stage in pipeline.stages),
        )
        self.assertEqual(
            tuple(step.produced_fact.kind for step in snapshot.steps),
            (
                "array_body_envelope",
                "array_initialization_slot_form",
                "array_initialization_helper_request",
                "array_initialization_base_type_resolution",
                "array_initialization_vector_length_resolution",
                "array_initialization_vector_alignment_resolution",
                "array_initialization_helper_set_completion",
                "array_initialization_declaration_shell",
                "array_body_structural_sequence",
                "predicate_path_structural_request",
                "post_branch_intrinsic_call_site_structural_request",
                "return_emission_structural_request",
            ),
        )
        self.assertEqual(
            snapshot.steps[-1].depends_on,
            (
                "array_body_structural_sequence",
                "post_branch_intrinsic_call_site_structural_request",
            ),
        )
        self.assertEqual(snapshot.pending_backfeed_requests, ())

    def test_m77_exact_shape_tokens_are_slice_local_evidence(self) -> None:
        shape = lowering_exact_shapes.EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE

        self.assertEqual(shape.target_text, "pg")
        self.assertEqual(
            lowering_exact_shapes.EXACT_PREDICATE_INIT_TYPE_TOKEN,
            "svbool_t",
        )
        self.assertEqual(lowering_exact_shapes.EXACT_PREDICATE_TOKEN, "pg")
        self.assertEqual(
            lowering_exact_shapes.EXACT_PREDICATE_INIT_DIRECT_INTRINSIC_TOKEN,
            "svptrue_b8",
        )
        self.assertIsNotNone(
            lowering_exact_shapes.EXACT_PREDICATE_INIT_SLOT_RE.match(
                "svbool_t pg = intrin<svptrue_b8>();",
            )
        )
        self.assertTrue(shape.supports_direct_intrinsic_token("svptrue_b16"))
        self.assertTrue(shape.supports_direct_intrinsic_token("svptrue_b32"))
        self.assertTrue(shape.supports_direct_intrinsic_token("svptrue_b64"))
        parsed = lowering_exact_shapes.parse_exact_selected_body_assignment_form(
            "pg = intrin<svptrue_b32>();",
            None,
        )

        self.assertTrue(parsed.is_ok, parsed.diagnostics)
        self.assertEqual(
            parsed.unwrap().direct_intrinsic_token_text,
            "svptrue_b32",
        )
        self.assertEqual(
            lowering_exact_shapes.EXACT_POST_BRANCH_INTRINSIC_TOKEN,
            "svst1",
        )
        self.assertEqual(
            lowering_exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_TEXT,
            "tmp.data()",
        )

    def test_m78_array_body_decomposition_keeps_public_facade_stable(self) -> None:
        self.assertIs(
            lowering_boundary.ExactArrayInitializationSlotFormIr,
            ExactArrayInitializationSlotFormIr,
        )
        self.assertIs(
            lowering_boundary.ExactPredicatePathStructuralRequestIr,
            ExactPredicatePathStructuralRequestIr,
        )
        self.assertIs(
            lowering_boundary.lower_exact_array_initialization_slot_form,
            lower_exact_array_initialization_slot_form,
        )
        self.assertIs(
            lowering_boundary.lower_exact_post_branch_intrinsic_call_site_structural_request,
            lower_exact_post_branch_intrinsic_call_site_structural_request,
        )

    def test_m78_array_body_package_moves_shapes_and_diagnostics(self) -> None:
        self.assertIs(
            lowering_boundary._array_body_shapes,
            lowering_array_body_shapes,
        )
        self.assertIs(
            lowering_boundary._array_body_diagnostics,
            lowering_array_body_diagnostics,
        )
        self.assertNotIn(
            "_EXACT_ARRAY_INITIALIZATION_SLOT_RE",
            lowering_boundary.__dict__,
        )
        self.assertNotIn(
            "_array_initialization_slot_malformed_diagnostic",
            lowering_boundary.__dict__,
        )

        slot_match = (
            lowering_array_body_shapes._EXACT_ARRAY_INITIALIZATION_SLOT_RE.match(
                "var<typed>(array_type<type<generation>(base::in), "
                "value<generation>(vector::length), "
                "value<generation>(vector::alignment)>, tmp, "
                "value<backend>(uninit::array))",
            )
        )
        self.assertIsNotNone(slot_match)
        diagnostic = (
            lowering_array_body_diagnostics
            ._array_initialization_slot_malformed_diagnostic(
                "malformed exact array-initialization slot",
                None,
            )
        )
        self.assertEqual(
            diagnostic.code,
            "TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED",
        )

    def test_m79_array_body_model_ownership_moves_exact_models(self) -> None:
        self.assertIs(
            lowering_boundary._array_body_models,
            lowering_array_body_models,
        )
        self.assertIs(
            lowering_boundary.ExactArrayBodyEnvelopeIr,
            lowering_array_body_models.ExactArrayBodyEnvelopeIr,
        )
        self.assertIs(
            lowering_boundary.ExactArrayInitializationHelperRequestIr,
            lowering_array_body_models.ExactArrayInitializationHelperRequestIr,
        )
        self.assertIs(
            lowering_boundary.ExactPredicatePathStructuralRequestIr,
            lowering_array_body_models.ExactPredicatePathStructuralRequestIr,
        )
        self.assertIs(
            lowering_boundary.ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
            (
                lowering_array_body_models
                .ExactPostBranchIntrinsicCallSiteStructuralRequestIr
            ),
        )

    def test_m79_array_body_shapes_share_helper_model_ownership(self) -> None:
        self.assertIs(
            lowering_array_body_shapes.ExactArrayInitializationHelperLeafKind,
            lowering_array_body_models.ExactArrayInitializationHelperLeafKind,
        )
        self.assertIs(
            (
                lowering_array_body_shapes
                ._EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS
            ),
            (
                lowering_array_body_models
                ._EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS
            ),
        )
        self.assertIs(
            (
                lowering_array_body_shapes
                ._EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE
            ),
            (
                lowering_array_body_models
                ._EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE
            ),
        )
        self.assertNotIn(
            "ExactArrayInitializationHelperLeafKind = Literal",
            inspect.getsource(lowering_boundary),
        )

    def test_m79_array_body_diagnostics_use_typed_protocols(self) -> None:
        self.assertNotIn("Any", lowering_array_body_diagnostics.__dict__)
        self.assertIs(
            lowering_array_body_diagnostics.ExactArrayInitializationHelperLeafSpecLike,
            (
                lowering_array_body_models
                .ExactArrayInitializationHelperLeafSpecLike
            ),
        )
        self.assertIs(
            lowering_array_body_diagnostics.ExactArrayInitializationSlotFormLike,
            lowering_array_body_models.ExactArrayInitializationSlotFormLike,
        )

    def test_m80_array_body_validation_ownership_moves_request_helpers(self) -> None:
        self.assertIs(
            lowering_boundary._array_body_validation,
            lowering_array_body_validation,
        )
        for helper_name in (
            "_validate_array_initialization_slot_position",
            "_array_initialization_base_type_request_record",
            "_array_initialization_vector_length_metadata_for_context",
            "_array_initialization_vector_alignment_metadata_for_context",
            "_validate_array_body_structural_sequence_inputs",
            "_validate_predicate_path_structural_request_input",
            "_validate_post_branch_intrinsic_call_site_input",
            "_structural_role_from_slot",
            "_array_initialization_leaf",
        ):
            self.assertIn(helper_name, lowering_array_body_validation.__dict__)
            self.assertNotIn(helper_name, lowering_boundary.__dict__)
        self.assertNotIn("SelectedBodyEnvelopeIr", lowering_array_body_validation.__dict__)
        self.assertNotIn(
            "NoSelectedBodyEnvelopeIr",
            lowering_array_body_validation.__dict__,
        )

    def test_m80_private_array_body_modules_do_not_import_boundary(self) -> None:
        private_modules = (
            lowering_array_body_diagnostics,
            lowering_array_body_models,
            lowering_array_body_shapes,
            lowering_array_body_validation,
            lowering_exact_shapes,
            lowering_pipeline,
        )
        for module in private_modules:
            imported_boundary: list[str] = []
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_boundary.extend(
                        alias.name
                        for alias in node.names
                        if alias.name == "tslgen.lowering.boundary"
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "tslgen.lowering.boundary":
                        imported_boundary.append(node.module)
                    if node.module == "tslgen.lowering":
                        imported_boundary.extend(
                            alias.name
                            for alias in node.names
                            if alias.name == "boundary"
                        )
                    if node.level and node.module in (None, "", "boundary"):
                        imported_boundary.extend(
                            alias.name
                            for alias in node.names
                            if node.module == "boundary" or alias.name == "boundary"
                        )
            self.assertEqual(imported_boundary, [], module.__name__)

    def test_m81_generation_core_ownership_moves_models_and_helpers(self) -> None:
        self.assertIs(
            lowering_boundary.GenerationTypeRef,
            lowering_generation_models.GenerationTypeRef,
        )
        self.assertIs(
            lowering_boundary.GenerationValue,
            lowering_generation_models.GenerationValue,
        )
        self.assertIs(
            lowering_boundary.GenerationPredicate,
            lowering_generation_models.GenerationPredicate,
        )
        self.assertIs(
            lowering_boundary.PrunedGenerationBranch,
            lowering_generation_models.PrunedGenerationBranch,
        )
        self.assertIs(
            lowering_boundary.TsilPrimitiveAttributeCondition,
            lowering_generation_models.TsilPrimitiveAttributeCondition,
        )
        self.assertIn(
            "_generation_type_query_inner",
            lowering_generation_queries.__dict__,
        )
        self.assertIn(
            "_prune_generation_size_byte_branch_chain",
            lowering_generation_control_flow.__dict__,
        )
        self.assertIn(
            "_malformed_generation_if_diagnostic",
            lowering_generation_diagnostics.__dict__,
        )
        self.assertNotIn("_generation_type_query_inner", lowering_boundary.__dict__)
        self.assertNotIn("_prune_generation_branch", lowering_boundary.__dict__)
        self.assertNotIn(
            "_malformed_generation_type_query_diagnostic",
            lowering_boundary.__dict__,
        )

    def test_m81_generation_public_imports_stay_stable(self) -> None:
        self.assertIs(lowering_boundary.GenerationTypeRef, GenerationTypeRef)
        self.assertIs(lowering_boundary.GenerationValue, GenerationValue)
        self.assertIs(lowering_boundary.GenerationPredicate, GenerationPredicate)
        self.assertIs(
            lowering_boundary.GenerationSizeByteBranchChainPruning,
            GenerationSizeByteBranchChainPruning,
        )
        self.assertIs(
            lowering_boundary.GenerationSizeByteBranchChainArm,
            GenerationSizeByteBranchChainArm,
        )
        self.assertIs(
            lowering_boundary.TsilTypeSignednessCondition,
            TsilTypeSignednessCondition,
        )
        self.assertIs(
            lowering_boundary.resolve_generation_type_query,
            resolve_generation_type_query,
        )
        self.assertIs(
            lowering_boundary.resolve_generation_value_query,
            resolve_generation_value_query,
        )
        self.assertIs(
            lowering_boundary.resolve_generation_predicate_query,
            resolve_generation_predicate_query,
        )

    def test_m81_private_generation_modules_do_not_import_boundary(self) -> None:
        private_modules = (
            lowering_generation_control_flow,
            lowering_generation_diagnostics,
            lowering_generation_models,
            lowering_generation_queries,
            lowering_array_body_diagnostics,
            lowering_array_body_models,
            lowering_array_body_shapes,
            lowering_array_body_validation,
            lowering_exact_shapes,
            lowering_pipeline,
        )
        for module in private_modules:
            imported_boundary: list[str] = []
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_boundary.extend(
                        alias.name
                        for alias in node.names
                        if alias.name == "tslgen.lowering.boundary"
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "tslgen.lowering.boundary":
                        imported_boundary.append(node.module)
                    if node.module == "tslgen.lowering":
                        imported_boundary.extend(
                            alias.name
                            for alias in node.names
                            if alias.name == "boundary"
                        )
                    if node.level and node.module in (None, "", "boundary"):
                        imported_boundary.extend(
                            alias.name
                            for alias in node.names
                            if node.module == "boundary" or alias.name == "boundary"
                        )
            self.assertEqual(imported_boundary, [], module.__name__)

    def test_m82_selected_body_model_ownership_moves_cluster(self) -> None:
        for name in (
            "OpaqueSelectedBranchBodyHandoff",
            "NoSelectedBranchBodyHandoff",
            "SelectedBranchBodyAssignmentFormRecognition",
            "NoSelectedBranchBodyAssignmentFormRecognition",
            "SelectedAssignmentDirectIntrinsicBodyIr",
            "NoSelectedAssignmentDirectIntrinsicBodyIr",
            "SelectedBodyEnvelopeEntry",
            "SelectedBodyEnvelopeIr",
            "NoSelectedBodyEnvelopeIr",
        ):
            self.assertIs(
                getattr(lowering_boundary, name),
                getattr(lowering_selected_body_models, name),
            )
            self.assertIs(
                globals()[name],
                getattr(lowering_selected_body_models, name),
            )

    def test_m82_array_body_consumers_use_concrete_selected_body_models(self) -> None:
        selected_envelope = self.selected_body_envelope(selected_type_tag="si16")
        no_selected_envelope = self.no_selected_body_envelope("si8")

        self.assertTrue(
            lowering_array_body_models._is_generation_selected_body_envelope(
                selected_envelope,
            ),
        )
        self.assertTrue(
            lowering_array_body_models._is_selected_body_envelope(
                selected_envelope,
            ),
        )
        self.assertFalse(
            lowering_array_body_models._is_selected_body_envelope(object()),
        )
        self.assertTrue(
            lowering_array_body_models._is_no_selected_body_envelope(
                no_selected_envelope,
            ),
        )
        self.assertFalse(
            lowering_array_body_models._is_no_selected_body_envelope(object()),
        )
        self.assertIsInstance(
            selected_envelope,
            lowering_selected_body_models.SelectedBodyEnvelopeIr,
        )
        self.assertIsInstance(
            no_selected_envelope,
            lowering_selected_body_models.NoSelectedBodyEnvelopeIr,
        )

    def test_m82_private_selected_body_module_does_not_import_facades(self) -> None:
        private_modules = (
            lowering_selected_body_models,
            lowering_generation_control_flow,
            lowering_generation_diagnostics,
            lowering_generation_models,
            lowering_generation_queries,
            lowering_array_body_diagnostics,
            lowering_array_body_models,
            lowering_array_body_shapes,
            lowering_array_body_validation,
            lowering_exact_shapes,
            lowering_pipeline,
        )
        for module in private_modules:
            imported_facade: list[str] = []
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_facade.extend(
                        alias.name
                        for alias in node.names
                        if alias.name
                        in ("tslgen.lowering.boundary", "tslgen.lowering")
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module in (
                        "tslgen.lowering.boundary",
                        "tslgen.lowering",
                    ):
                        imported_facade.append(node.module)
                    if node.level and node.module in (None, "", "boundary"):
                        imported_facade.extend(
                            alias.name
                            for alias in node.names
                            if node.module == "boundary" or alias.name == "boundary"
                        )
            self.assertEqual(imported_facade, [], module.__name__)

    def test_m83_stage_contract_ownership_moves_stage_models(self) -> None:
        for name in (
            "GenerationLoweringStage",
            "GenerationLoweringStageName",
            "GenerationLoweringStageOutput",
            "TsilParameterReference",
            "TsilBinaryExpression",
            "TsilIntrinsicComposeExpression",
            "TsilReturnStatement",
            "TsilStatement",
        ):
            self.assertIs(
                getattr(lowering_boundary, name),
                getattr(lowering_stage_contracts, name),
            )
        for name in (
            "GenerationLoweringStage",
            "TsilParameterReference",
            "TsilBinaryExpression",
            "TsilIntrinsicComposeExpression",
            "TsilReturnStatement",
        ):
            self.assertIs(globals()[name], getattr(lowering_stage_contracts, name))
        self.assertIn(
            "GenerationLoweringStageOutputContract",
            lowering_stage_contracts.__dict__,
        )
        self.assertNotIn(
            "class GenerationLoweringStage",
            inspect.getsource(lowering_boundary),
        )

    def test_m83_stage_contract_accepts_all_accepted_outputs(self) -> None:
        predicate = GenerationPredicate(
            kind="type.size_bytes.equals",
            literal=2,
            value=True,
            type_tag="si16",
        )
        branch = PrunedGenerationBranch(
            condition=TsilTypeSignednessCondition(
                GenerationTypeRef(kind="base.in", type_tag="si32"),
            ),
            selected_branch="true",
            statement_text="emit_return(left + right);",
        )
        chain = GenerationSizeByteBranchChainPruning(
            arms=tuple(
                GenerationSizeByteBranchChainArm(
                    literal=literal,
                    predicate=GenerationPredicate(
                        kind="type.size_bytes.equals",
                        literal=literal,
                        value=literal == 2,
                        type_tag="si16",
                    ),
                    statement_text=f"pg = intrin<svptrue_b{literal * 8}>();",
                )
                for literal in (2, 4, 8)
            ),
            type_tag="si16",
            selected_literal=2,
            selected_statement_text="pg = intrin<svptrue_b16>();",
        )
        statement = TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            ),
        )
        handoff = self.assignment_handoff("pg = intrin<svptrue_b16>();")
        no_handoff = NoSelectedBranchBodyHandoff(
            candidate_id="candidate-1",
            selected_type_tag="si8",
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
            attempted_literals=(2, 4, 8),
        )
        form_result = recognize_selected_branch_body_assignment_form(handoff)
        self.assertTrue(form_result.is_ok, form_result.diagnostics)
        no_form = NoSelectedBranchBodyAssignmentFormRecognition(
            candidate_id="candidate-1",
            selected_type_tag="si8",
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
            attempted_literals=(2, 4, 8),
        )
        body_ir = self.selected_body_ir()
        no_body_ir = NoSelectedAssignmentDirectIntrinsicBodyIr(
            candidate_id="candidate-1",
            selected_type_tag="si8",
            source_location=SourceLocation(Path("array.tsl"), 107, 15),
            originating_branch_chain_id="candidate-1:chain",
            attempted_literals=(2, 4, 8),
        )
        exact_array_envelope = self.exact_array_body_envelope()
        slot_form_result = lower_exact_array_initialization_slot_form(
            exact_array_envelope,
        )
        self.assertTrue(slot_form_result.is_ok, slot_form_result.diagnostics)
        slot_form = slot_form_result.unwrap()

        cases = (
            (
                "helper_expression_recognition",
                GenerationExpressionRecognition(
                    kind="generation.value",
                    source_text="value<generation>(vector::length)",
                ),
            ),
            (
                "typed_generation_value",
                GenerationValue(kind="type.size_bytes", value=2, type_tag="si16"),
            ),
            ("typed_generation_predicate", predicate),
            ("generation_control_flow_pruning", branch),
            ("generation_control_flow_pruning", chain),
            ("selected_body_lowering", statement),
            ("selected_body_lowering", handoff),
            ("selected_body_lowering", no_handoff),
            ("selected_body_form_recognition", form_result.unwrap()),
            ("selected_body_form_recognition", no_form),
            ("selected_body_ir_lowering", body_ir),
            ("selected_body_ir_lowering", no_body_ir),
            ("selected_body_envelope_lowering", self.selected_body_envelope()),
            ("selected_body_envelope_lowering", self.no_selected_body_envelope()),
            ("array_body_envelope_slot_assembly", exact_array_envelope),
            ("array_initialization_slot_form_lowering", slot_form),
            (
                "array_initialization_helper_request_lowering",
                self.exact_array_initialization_helper_request_ir(),
            ),
            (
                "array_initialization_base_type_request_resolution",
                self.exact_array_initialization_base_type_resolution(),
            ),
            (
                "array_initialization_vector_length_request_resolution",
                self.exact_array_initialization_vector_length_resolution(),
            ),
            (
                "array_initialization_vector_alignment_request_resolution",
                self.exact_array_initialization_vector_alignment_resolution(),
            ),
            (
                "array_initialization_helper_set_completion",
                self.exact_array_initialization_helper_set_completion(),
            ),
            (
                "array_initialization_declaration_shell_lowering",
                self.exact_array_initialization_declaration_shell(),
            ),
            (
                "array_body_structural_sequence_classification",
                self.exact_array_body_structural_sequence(),
            ),
            (
                "predicate_path_structural_request_lowering",
                self.exact_predicate_path_structural_request(),
            ),
            (
                "post_branch_intrinsic_call_site_structural_request_lowering",
                self.exact_post_branch_intrinsic_call_site_structural_request(),
            ),
            (
                "return_emission_structural_request_lowering",
                self.exact_return_emission_structural_request(),
            ),
        )

        for stage_name, output in cases:
            with self.subTest(stage_name=stage_name, output=type(output).__name__):
                stage = GenerationLoweringStage(
                    stage=cast(
                        lowering_stage_contracts.GenerationLoweringStageName,
                        stage_name,
                    ),
                    output=output,
                )

                self.assertIs(stage.output, output)
                self.assertEqual(stage.key, (stage_name, output.key))

    def test_m83_stage_contract_rejects_unknown_stage_and_wrong_output(self) -> None:
        output = GenerationValue(kind="type.size_bytes", value=2, type_tag="si16")
        with self.assertRaisesRegex(
            ValueError,
            "unknown generation lowering stage: 'unknown_stage'",
        ):
            GenerationLoweringStage(
                stage=cast(
                    lowering_stage_contracts.GenerationLoweringStageName,
                    "unknown_stage",
                ),
                output=output,
            )

        with self.assertRaisesRegex(
            TypeError,
            "typed_generation_value stage requires output type GenerationValue",
        ):
            GenerationLoweringStage(
                stage="typed_generation_value",
                output=GenerationPredicate(
                    kind="type.size_bytes.equals",
                    literal=2,
                    value=True,
                    type_tag="si16",
                ),
            )

    def test_m83_private_stage_contract_module_does_not_import_facades(self) -> None:
        private_modules = (
            lowering_stage_contracts,
            lowering_selected_body_models,
            lowering_generation_control_flow,
            lowering_generation_diagnostics,
            lowering_generation_models,
            lowering_generation_queries,
            lowering_array_body_diagnostics,
            lowering_array_body_models,
            lowering_array_body_shapes,
            lowering_array_body_validation,
            lowering_exact_shapes,
            lowering_pipeline,
        )
        for module in private_modules:
            imported_facade: list[str] = []
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_facade.extend(
                        alias.name
                        for alias in node.names
                        if alias.name
                        in ("tslgen.lowering.boundary", "tslgen.lowering")
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module in (
                        "tslgen.lowering.boundary",
                        "tslgen.lowering",
                    ):
                        imported_facade.append(node.module)
                    if node.level and node.module in (None, "", "boundary"):
                        imported_facade.extend(
                            alias.name
                            for alias in node.names
                            if node.module == "boundary" or alias.name == "boundary"
                        )
            self.assertEqual(imported_facade, [], module.__name__)

    def test_m84_private_array_body_modules_do_not_import_facades(
        self,
    ) -> None:
        private_modules = (
            lowering_array_body_sources,
            lowering_array_body_lowering,
            lowering_array_body_pipeline,
        )
        for module in private_modules:
            imported_facade: list[str] = []
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_facade.extend(
                        alias.name
                        for alias in node.names
                        if alias.name in ("tslgen.lowering.boundary", "tslgen.lowering")
                    )
                elif isinstance(node, ast.ImportFrom):
                    if node.module in ("tslgen.lowering.boundary", "tslgen.lowering"):
                        imported_facade.append(node.module)
                    if node.level and node.module in (None, "", "boundary"):
                        imported_facade.extend(
                            alias.name
                            for alias in node.names
                            if node.module == "boundary" or alias.name == "boundary"
                        )
            self.assertEqual(imported_facade, [], module.__name__)

    def test_m84_array_body_facade_exports_private_owners(self) -> None:
        self.assertIs(
            lowering_boundary.assemble_exact_array_body_envelope,
            lowering_array_body_lowering.assemble_exact_array_body_envelope,
        )
        self.assertIs(
            assemble_exact_array_body_envelope,
            lowering_array_body_lowering.assemble_exact_array_body_envelope,
        )
        self.assertIs(
            lowering_array_body_pipeline.assemble_exact_array_body_envelope,
            lowering_array_body_lowering.assemble_exact_array_body_envelope,
        )
        self.assertIs(
            lowering_boundary._lower_exact_array_initialization_stage_pipeline,
            lowering_array_body_pipeline._lower_exact_array_initialization_stage_pipeline,
        )
        self.assertIs(
            lowering_boundary._stage_output_location,
            lowering_array_body_sources._stage_output_location,
        )

    def test_m85_selected_body_lowerers_move_to_private_owner(self) -> None:
        public_imports = {
            "handoff_opaque_selected_branch_body": handoff_opaque_selected_branch_body,
            "recognize_selected_branch_body_assignment_form": (
                recognize_selected_branch_body_assignment_form
            ),
            "lower_selected_branch_body_ir": lower_selected_branch_body_ir,
            "lower_selected_body_envelope": lower_selected_body_envelope,
        }
        for name, public_function in public_imports.items():
            with self.subTest(name=name):
                private_function = getattr(lowering_selected_body_lowering, name)
                self.assertIs(getattr(lowering_boundary, name), private_function)
                self.assertIs(public_function, private_function)
                self.assertEqual(
                    private_function.__module__,
                    "tslgen.lowering._selected_body_lowering",
                )
                self.assertNotIn(name, lowering_array_body_sources.__dict__)
                self.assertNotIn(name, lowering_array_body_lowering.__dict__)
                self.assertNotIn(name, lowering_array_body_pipeline.__dict__)

    def test_m85_private_selected_body_lowering_does_not_import_forbidden_modules(
        self,
    ) -> None:
        forbidden_modules = (
            "tslgen.lowering.boundary",
            "tslgen.lowering",
            "tslgen.lowering._array_body_sources",
            "tslgen.lowering._array_body_lowering",
        )
        imported_forbidden: list[str] = []
        tree = ast.parse(inspect.getsource(lowering_selected_body_lowering))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_forbidden.extend(
                    alias.name for alias in node.names if alias.name in forbidden_modules
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_modules:
                    imported_forbidden.append(node.module)
                if node.level and node.module in (
                    None,
                    "",
                    "boundary",
                    "_array_body_sources",
                    "_array_body_lowering",
                ):
                    imported_forbidden.extend(
                        alias.name
                        for alias in node.names
                        if (
                            node.module
                            in ("boundary", "_array_body_sources", "_array_body_lowering")
                            or alias.name
                            in ("boundary", "_array_body_sources", "_array_body_lowering")
                        )
                    )
        self.assertEqual(imported_forbidden, [])

    def test_m85_public_selected_body_facade_calls_remain_stable(self) -> None:
        predicates = tuple(
            GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=literal == 2,
                type_tag="si16",
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
            type_tag="si16",
            selected_literal=2,
            selected_statement_text="pg = intrin<svptrue_b16>();",
            condition_location=SourceLocation(Path("array.tsl"), 107, 15),
        )
        stage = GenerationLoweringStage(
            stage="generation_control_flow_pruning",
            output=chain,
        )

        handoff_result = lowering_boundary.handoff_opaque_selected_branch_body(
            "candidate-1",
            stage,
        )
        self.assertTrue(handoff_result.is_ok, handoff_result.diagnostics)
        handoff = handoff_result.unwrap()
        self.assertEqual(
            handoff,
            handoff_opaque_selected_branch_body("candidate-1", stage).unwrap(),
        )
        form = lowering_boundary.recognize_selected_branch_body_assignment_form(
            handoff,
        ).unwrap()
        body_ir = lowering_boundary.lower_selected_branch_body_ir(form).unwrap()
        envelope = lowering_boundary.lower_selected_body_envelope(body_ir).unwrap()

        self.assertEqual(
            form,
            recognize_selected_branch_body_assignment_form(handoff).unwrap(),
        )
        self.assertEqual(body_ir, lower_selected_branch_body_ir(form).unwrap())
        self.assertEqual(envelope, lower_selected_body_envelope(body_ir).unwrap())
        self.assertEqual(
            tuple(item.__module__ for item in (handoff, form, body_ir, envelope)),
            (
                "tslgen.lowering._selected_body_models",
                "tslgen.lowering._selected_body_models",
                "tslgen.lowering._selected_body_models",
                "tslgen.lowering._selected_body_models",
            ),
        )

    def test_m85_selected_body_diagnostics_preserve_codes_and_locations(self) -> None:
        statement = TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            )
        )
        unsupported_stage = GenerationLoweringStage(
            stage="selected_body_lowering",
            output=statement,
        )
        assert_diagnostic(
            self,
            handoff_opaque_selected_branch_body(
                "candidate-1",
                unsupported_stage,
            ).diagnostics[0],
            code="TSL-LOWER-HANDOFF-SOURCE-UNSUPPORTED",
            severity="error",
        )
        unsupported_branch_location = SourceLocation(Path("array.tsl"), 109, 7)
        unsupported_branch_stage = GenerationLoweringStage(
            stage="generation_control_flow_pruning",
            output=PrunedGenerationBranch(
                condition=TsilPrimitiveAttributeCondition("aligned"),
                selected_branch="false",
                statement_text="emit_return(left + right);",
                condition_location=unsupported_branch_location,
            ),
        )
        assert_diagnostic(
            self,
            handoff_opaque_selected_branch_body(
                "candidate-1",
                unsupported_branch_stage,
            ).diagnostics[0],
            code="TSL-LOWER-HANDOFF-SOURCE-UNSUPPORTED",
            severity="error",
            path="array.tsl",
            line=109,
            column=7,
        )

        predicates = tuple(
            GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=literal == 2,
                type_tag="si16",
            )
            for literal in (2, 4, 8)
        )
        missing_provenance_chain = GenerationSizeByteBranchChainPruning(
            arms=tuple(
                GenerationSizeByteBranchChainArm(
                    literal=literal,
                    predicate=predicate,
                    statement_text="pg = intrin<svptrue_b16>();",
                )
                for literal, predicate in zip((2, 4, 8), predicates, strict=True)
            ),
            type_tag="si16",
            selected_literal=2,
            selected_statement_text="pg = intrin<svptrue_b16>();",
        )
        assert_diagnostic(
            self,
            handoff_opaque_selected_branch_body(
                "candidate-1",
                GenerationLoweringStage(
                    stage="generation_control_flow_pruning",
                    output=missing_provenance_chain,
                ),
            ).diagnostics[0],
            code="TSL-LOWER-HANDOFF-PROVENANCE-MISSING",
            severity="error",
        )

        body_missing_chain = object.__new__(GenerationSizeByteBranchChainPruning)
        object.__setattr__(body_missing_chain, "arms", missing_provenance_chain.arms)
        object.__setattr__(body_missing_chain, "type_tag", "si16")
        object.__setattr__(body_missing_chain, "selected_literal", 2)
        object.__setattr__(body_missing_chain, "selected_statement_text", "")
        object.__setattr__(
            body_missing_chain,
            "condition_location",
            SourceLocation(Path("array.tsl"), 107, 15),
        )
        assert_diagnostic(
            self,
            handoff_opaque_selected_branch_body(
                "candidate-1",
                GenerationLoweringStage(
                    stage="generation_control_flow_pruning",
                    output=body_missing_chain,
                ),
            ).diagnostics[0],
            code="TSL-LOWER-HANDOFF-BODY-MISSING",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )

        form_cases = (
            (
                "pg = intrin<svptrue_b16>(); emit_return(tmp);",
                "TSL-LOWER-SELECTED-BODY-FORM-EXTRA-STATEMENTS",
            ),
            (
                "pg = intrin<svptrue_b16()",
                "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
            ),
            (
                "mask = intrin<svptrue_b16>();",
                "TSL-LOWER-SELECTED-BODY-FORM-TARGET-UNSUPPORTED",
            ),
            (
                "pg = value<generation>(vector::length);",
                "TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED",
            ),
            (
                "pg = intrin<svptrue_b8>();",
                "TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED",
            ),
        )
        for body_text, code in form_cases:
            with self.subTest(code=code):
                diagnostic = recognize_selected_branch_body_assignment_form(
                    self.assignment_handoff(body_text)
                ).diagnostics[0]
                assert_diagnostic(
                    self,
                    diagnostic,
                    code=code,
                    severity="error",
                    path="array.tsl",
                    line=107,
                    column=15,
                )

        bad_body_ir = object.__new__(SelectedAssignmentDirectIntrinsicBodyIr)
        object.__setattr__(bad_body_ir, "candidate_id", "candidate-1")
        object.__setattr__(bad_body_ir, "selected_type_tag", "si16")
        object.__setattr__(bad_body_ir, "selected_literal", 2)
        object.__setattr__(bad_body_ir, "originating_branch_chain_id", "")
        object.__setattr__(
            bad_body_ir,
            "original_opaque_body_text",
            "pg = intrin<svptrue_b16>();",
        )
        object.__setattr__(
            bad_body_ir,
            "source_location",
            SourceLocation(Path("array.tsl"), 107, 15),
        )
        object.__setattr__(bad_body_ir, "assignment_target_text", "pg")
        object.__setattr__(bad_body_ir, "opaque_rhs_text", "intrin<svptrue_b16>()")
        object.__setattr__(bad_body_ir, "direct_intrinsic_token_text", "svptrue_b16")
        object.__setattr__(bad_body_ir, "direct_intrinsic_argument_texts", ())
        assert_diagnostic(
            self,
            lower_selected_body_envelope(bad_body_ir).diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )

    def test_m86_payload_and_mini_tsil_private_owners_back_facade(self) -> None:
        self.assertIs(lowering_boundary._lowering_inputs, lowering_inputs)
        self.assertIs(
            lowering_boundary._mini_tsil_lowering,
            lowering_mini_tsil_lowering,
        )
        self.assertIs(
            lowering_boundary.ClassifiedPayload,
            lowering_inputs.ClassifiedPayload,
        )
        self.assertIs(lowering_boundary.LoweringInput, lowering_inputs.LoweringInput)
        self.assertIs(
            lowering_boundary.LoweringStrategy,
            lowering_inputs.LoweringStrategy,
        )
        self.assertIs(
            lowering_boundary.PayloadClassification,
            lowering_inputs.PayloadClassification,
        )
        self.assertIs(ClassifiedPayload, lowering_inputs.ClassifiedPayload)
        self.assertIs(LoweringInput, lowering_inputs.LoweringInput)
        self.assertIs(
            lowering_boundary._classify_payload,
            lowering_inputs._classify_payload,
        )
        self.assertIs(
            lowering_boundary._unsupported_payload_diagnostic,
            lowering_inputs._unsupported_payload_diagnostic,
        )
        self.assertIs(
            lowering_boundary._mini_return_statement,
            lowering_mini_tsil_lowering._mini_return_statement,
        )
        self.assertEqual(
            lowering_boundary._mini_return_statement.__module__,
            "tslgen.lowering._mini_tsil_lowering",
        )
        self.assertNotIn("_DIRECT_PARAMETER_ADD_RETURN_RE", lowering_boundary.__dict__)
        self.assertNotIn(
            "_direct_parameter_add_return_statement",
            lowering_boundary.__dict__,
        )
        self.assertIn(
            "_DIRECT_PARAMETER_ADD_RETURN_RE",
            lowering_mini_tsil_lowering.__dict__,
        )
        self.assertIn(
            "_direct_parameter_add_return_statement",
            lowering_mini_tsil_lowering.__dict__,
        )

    def test_m86_private_lowering_modules_keep_intended_import_direction(self) -> None:
        lowering_inputs_imports: set[str] = set()
        tree = ast.parse(inspect.getsource(lowering_inputs))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                lowering_inputs_imports.update(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("tslgen.")
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("tslgen."):
                    lowering_inputs_imports.add(node.module)
        self.assertEqual(
            lowering_inputs_imports,
            {
                "tslgen.analysis.candidates",
                "tslgen.core.diagnostics",
                "tslgen.core.result",
                "tslgen.domain.values",
            },
        )

        mini_tsil_lowering_imports: set[str] = set()
        tree = ast.parse(inspect.getsource(lowering_mini_tsil_lowering))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mini_tsil_lowering_imports.update(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("tslgen.lowering")
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("tslgen.lowering"):
                    mini_tsil_lowering_imports.add(node.module)
        self.assertEqual(
            mini_tsil_lowering_imports,
            {
                "tslgen.lowering._lowering_inputs",
                "tslgen.lowering._stage_contracts",
            },
        )

    def test_m86_payload_classification_and_typed_opaque_behavior_stay_stable(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation")
        candidate = selection.candidates[0]

        private_classified = lowering_inputs._classify_payload(candidate)
        facade_classified = lowering_boundary._classify_payload(candidate)

        self.assertTrue(private_classified.is_ok, private_classified.diagnostics)
        self.assertTrue(facade_classified.is_ok, facade_classified.diagnostics)
        self.assertEqual(facade_classified.unwrap(), private_classified.unwrap())
        self.assertEqual(private_classified.unwrap().classification, "tsil")
        self.assertTrue(private_classified.unwrap().has_generation_condition)

        typed_opaque = lower_candidates(
            selection,
            LoweringRequest(strategy="typed_opaque", backend_id="cpp"),
        )

        self.assertFalse(typed_opaque.is_ok)
        assert_diagnostic(
            self,
            typed_opaque.diagnostics[0],
            code="TSL-LOWER-TSIL-UNSUPPORTED",
            severity="error",
        )
        self.assertIn("typed-opaque strategy", typed_opaque.diagnostics[0].message)
        self.assertIn("generation-time helpers", typed_opaque.diagnostics[0].message)
        self.assertEqual(
            typed_opaque.diagnostics[0].location,
            candidate.variant.source.declaration.source_span.location,
        )

    def test_m86_mini_tsil_private_lowerer_preserves_diagnostics_and_locations(
        self,
    ) -> None:
        prepared = prepare_lowering_inputs(
            self.selection_for("lower_intrin_expression_arg")
        )
        self.assertTrue(prepared.is_ok, prepared.diagnostics)
        item = prepared.unwrap().inputs[0]

        private_result = lowering_mini_tsil_lowering._mini_return_statement(item)
        facade_result = lowering_boundary._mini_return_statement(item)

        self.assertFalse(private_result.is_ok)
        self.assertEqual(facade_result.diagnostics, private_result.diagnostics)
        assert_diagnostic(
            self,
            private_result.diagnostics[0],
            code="TSL-LOWER-TSIL-INTRIN-ARGUMENT",
            severity="error",
        )
        self.assertEqual(private_result.diagnostics[0].location, item.source_location)
        self.assertIn("left + right", private_result.diagnostics[0].message)

    def test_m86_mini_tsil_pipeline_stage_identity_and_determinism(self) -> None:
        selection = self.selection_for("lower_intrin_add")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        first_impl = first.unwrap().implementations[0]
        second_impl = second.unwrap().implementations[0]
        self.assertEqual(first.unwrap(), second.unwrap())
        self.assertEqual(
            tuple(stage.stage for stage in first_impl.generation_stages),
            ("selected_body_lowering",),
        )
        self.assertIs(first_impl.generation_stages[0].output, first_impl.statements[0])
        self.assertEqual(
            tuple(stage.key for stage in first_impl.generation_stages),
            tuple(stage.key for stage in second_impl.generation_stages),
        )

    def test_m86_mini_tsil_leaf_lowering_consumes_only_selected_branch_body(
        self,
    ) -> None:
        selection = self.selection_for(
            "lower_generation_signedness_unselected_helper_si32"
        )

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(len(implementation.generation_branches), 1)
        self.assertEqual(implementation.generation_branches[0].selected_branch, "true")
        self.assertEqual(
            implementation.generation_branches[0].statement_text,
            "emit_return(left + right);",
        )
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
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages),
            (
                "helper_expression_recognition",
                "generation_control_flow_pruning",
                "selected_body_lowering",
            ),
        )
        self.assertIs(
            implementation.generation_stages[-1].output,
            implementation.statements[0],
        )

    def test_m85_selected_body_pipeline_snapshot_preserves_stage_identity(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")

        first = lower_candidates(selection)
        second = lower_candidates(selection)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        first_impl = next(
            implementation
            for implementation in first.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag == "si16"
        )
        second_impl = next(
            implementation
            for implementation in second.unwrap().implementations
            if implementation.generation_branch_chains[0].type_tag == "si16"
        )
        self.assertEqual(
            tuple(stage.stage for stage in first_impl.generation_stages[-4:]),
            (
                "selected_body_lowering",
                "selected_body_form_recognition",
                "selected_body_ir_lowering",
                "selected_body_envelope_lowering",
            ),
        )
        self.assertIs(
            first_impl.generation_stages[-4].output,
            first_impl.selected_branch_body_handoffs[0],
        )
        self.assertIs(
            first_impl.generation_stages[-3].output,
            first_impl.selected_branch_body_assignment_forms[0],
        )
        self.assertIs(
            first_impl.generation_stages[-2].output,
            first_impl.selected_branch_body_irs[0],
        )
        self.assertIs(
            first_impl.generation_stages[-1].output,
            first_impl.selected_body_envelopes[0],
        )
        self.assertEqual(
            tuple(stage.output.key for stage in first_impl.generation_stages[-4:]),
            tuple(stage.output.key for stage in second_impl.generation_stages[-4:]),
        )
        def selected_body_output_location_key(output: object) -> tuple[object, ...]:
            if isinstance(output, SelectedBranchBodyAssignmentFormRecognition):
                return output.selected_statement_location.sort_key()
            if isinstance(
                output,
                (
                    OpaqueSelectedBranchBodyHandoff,
                    NoSelectedBranchBodyHandoff,
                    NoSelectedBranchBodyAssignmentFormRecognition,
                    SelectedAssignmentDirectIntrinsicBodyIr,
                    NoSelectedAssignmentDirectIntrinsicBodyIr,
                    SelectedBodyEnvelopeIr,
                    NoSelectedBodyEnvelopeIr,
                ),
            ):
                return output.source_location.sort_key()
            raise AssertionError(f"unexpected selected-body output {output!r}")

        first_locations = tuple(
            selected_body_output_location_key(stage.output)
            for stage in first_impl.generation_stages[-4:]
        )
        second_locations = tuple(
            selected_body_output_location_key(stage.output)
            for stage in second_impl.generation_stages[-4:]
        )
        self.assertEqual(first_locations, second_locations)

    def test_m84_private_array_body_pipeline_preserves_snapshot_identity(self) -> None:
        result = self.exact_array_initialization_stage_pipeline("si32")
        self.assertTrue(result.is_ok, result.diagnostics)
        pipeline = result.unwrap()
        self.assertIsInstance(
            pipeline,
            lowering_array_body_pipeline._ExactArrayInitializationStagePipelineResult,
        )
        self.assertEqual(pipeline.pipeline_snapshot.stages, pipeline.stages)
        self.assertEqual(
            tuple(step.produced_fact.value for step in pipeline.pipeline_snapshot.steps),
            tuple(stage.output for stage in pipeline.stages),
        )

    def test_lower_candidates_structural_sequence_stage_follows_declaration_shell(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(skeleton,),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=(
                        self.vector_length_metadata_for_item(item),
                    ),
                    array_initialization_vector_alignment_metadata=(
                        self.vector_alignment_metadata_for_item(item),
                    ),
                ),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations_by_candidate_id[
            item.candidate_id
        ]
        self.assertEqual(
            implementation.generation_stages[-6].stage,
            "array_initialization_helper_set_completion",
        )
        self.assertEqual(
            implementation.generation_stages[-5].stage,
            "array_initialization_declaration_shell_lowering",
        )
        self.assertEqual(
            implementation.generation_stages[-4].stage,
            "array_body_structural_sequence_classification",
        )
        self.assertEqual(
            implementation.generation_stages[-3].stage,
            "predicate_path_structural_request_lowering",
        )
        self.assertEqual(
            implementation.generation_stages[-2].stage,
            "post_branch_intrinsic_call_site_structural_request_lowering",
        )
        self.assertEqual(
            implementation.generation_stages[-1].stage,
            "return_emission_structural_request_lowering",
        )
        helper_set_completion = implementation.array_initialization_helper_set_completions[
            0
        ]
        declaration_shell = implementation.array_initialization_declaration_shells[0]
        structural_sequence = implementation.array_body_structural_sequences[0]
        predicate_path = implementation.predicate_path_structural_requests[0]
        post_branch_call_site = (
            implementation.post_branch_intrinsic_call_site_structural_requests[0]
        )
        return_emission = implementation.return_emission_structural_requests[0]
        self.assertIs(implementation.generation_stages[-6].output, helper_set_completion)
        self.assertIs(implementation.generation_stages[-5].output, declaration_shell)
        self.assertIs(implementation.generation_stages[-4].output, structural_sequence)
        self.assertIs(implementation.generation_stages[-3].output, predicate_path)
        self.assertIs(
            implementation.generation_stages[-2].output,
            post_branch_call_site,
        )
        self.assertIs(implementation.generation_stages[-1].output, return_emission)
        self.assertIs(
            declaration_shell.source_helper_set_completion,
            helper_set_completion,
        )
        self.assertIs(
            declaration_shell.base_type_ref,
            implementation.array_initialization_base_type_resolutions[
                0
            ].resolved_type_ref,
        )
        self.assertIs(
            declaration_shell.vector_length,
            implementation.array_initialization_vector_length_resolutions[
                0
            ].resolved_vector_length,
        )
        self.assertIs(
            declaration_shell.vector_alignment,
            implementation.array_initialization_vector_alignment_resolutions[
                0
            ].resolved_vector_alignment,
        )
        self.assertEqual(
            declaration_shell.unresolved_backend_uninit.policy,
            "deferred_backend_value",
        )

    def test_lower_candidates_vector_length_metadata_order_is_deterministic(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        implementation = next(
            implementation
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag == "si32"
        )
        envelope = implementation.selected_body_envelopes[0]
        candidate = selection.candidates_by_id[implementation.candidate_id]
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        matching_metadata = self.vector_length_metadata(
            candidate_id=candidate.candidate_id,
            target_extension=candidate.target_extension,
            source_extension=candidate.source_extension,
            selected_type_tag=candidate.type_tag,
            lanes=29,
        )
        other_metadata = self.vector_length_metadata(
            candidate_id="other-candidate",
            selected_type_tag="si32",
            lanes=3,
        )
        matching_alignment = self.vector_alignment_metadata(
            candidate_id=candidate.candidate_id,
            target_extension=candidate.target_extension,
            source_extension=candidate.source_extension,
            selected_type_tag=candidate.type_tag,
            alignment_bytes=128,
        )
        other_alignment = self.vector_alignment_metadata(
            candidate_id="other-candidate",
            selected_type_tag="si32",
            alignment_bytes=32,
        )

        plans = []
        for length_metadata, alignment_metadata in (
            ((matching_metadata, other_metadata), (matching_alignment, other_alignment)),
            ((other_metadata, matching_metadata), (other_alignment, matching_alignment)),
        ):
            result = lower_candidates(
                selection,
                LoweringRequest(
                    array_body_envelope_skeletons=(skeleton,),
                    generation_context=GenerationContext(
                        array_initialization_vector_length_metadata=length_metadata,
                        array_initialization_vector_alignment_metadata=(
                            alignment_metadata
                        ),
                    ),
                ),
            )
            self.assertTrue(result.is_ok, result.diagnostics)
            plans.append(result.unwrap())

        first = plans[0].implementations_by_candidate_id[candidate.candidate_id]
        second = plans[1].implementations_by_candidate_id[candidate.candidate_id]
        self.assertEqual(first.key, second.key)

    def test_exact_array_initialization_stage_pipeline_propagates_diagnostics(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si16")
        envelope_stage = GenerationLoweringStage(
            stage="selected_body_envelope_lowering",
            output=envelope,
        )
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        malformed_skeleton = replace(
            skeleton,
            slots=(
                replace(
                    skeleton.slots[0],
                    opaque_source_text="var<typed>(unsupported)",
                ),
                *skeleton.slots[1:],
            ),
        )
        cases = (
            (
                "m64",
                LoweringRequest(
                    array_body_envelope_skeletons=(
                        replace(skeleton, is_exact_array_body_shape=False),
                    ),
                ),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
                "tsldata/primitives/load_store/array.tsl",
                105,
                15,
                "exact",
            ),
            (
                "m66",
                LoweringRequest(array_body_envelope_skeletons=(malformed_skeleton,)),
                "TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED",
                "tsldata/primitives/load_store/array.tsl",
                105,
                15,
                "array-initialization slot form",
            ),
        )
        for name, request, code, path, line, column, message in cases:
            with self.subTest(name=name):
                lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(
                    request,
                )
                self.assertTrue(lookup.is_ok, lookup.diagnostics)

                result = (
                    lowering_boundary._lower_exact_array_initialization_stage_pipeline(
                        item,
                        request,
                        envelope_stage,
                        lookup.unwrap(),
                    )
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path=path,
                    line=line,
                    column=column,
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_stage_pipeline_propagates_m67_diagnostic(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si16")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        request = LoweringRequest(
            array_body_envelope_skeletons=(skeleton,),
            generation_context=GenerationContext(
                array_initialization_vector_length_metadata=(
                    self.vector_length_metadata_for_item(item),
                ),
            ),
        )
        lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(request)
        self.assertTrue(lookup.is_ok, lookup.diagnostics)
        original = lowering_array_body_pipeline.lower_exact_array_initialization_helper_requests

        def fail_m67(*args: object, **kwargs: object):
            return lowering_boundary.Result.failure(
                (
                    Diagnostic.error(
                        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING",
                        "synthetic M67 propagation diagnostic",
                        location=skeleton.source_location,
                    ),
                )
            )

        lowering_array_body_pipeline.lower_exact_array_initialization_helper_requests = fail_m67  # type: ignore[assignment]
        try:
            result = lowering_boundary._lower_exact_array_initialization_stage_pipeline(
                item,
                request,
                GenerationLoweringStage(
                    stage="selected_body_envelope_lowering",
                    output=envelope,
                ),
                lookup.unwrap(),
            )
        finally:
            lowering_array_body_pipeline.lower_exact_array_initialization_helper_requests = original

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )

    def test_exact_array_initialization_stage_pipeline_propagates_m68_diagnostic(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("f32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        request = LoweringRequest(array_body_envelope_skeletons=(skeleton,))
        lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(request)
        self.assertTrue(lookup.is_ok, lookup.diagnostics)

        result = lowering_boundary._lower_exact_array_initialization_stage_pipeline(
            item,
            request,
            GenerationLoweringStage(
                stage="selected_body_envelope_lowering",
                output=envelope,
            ),
            lookup.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("concrete integer", result.diagnostics[0].message)

    def test_exact_array_initialization_stage_pipeline_reports_missing_m70_metadata(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si16")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        request = LoweringRequest(array_body_envelope_skeletons=(skeleton,))
        lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(request)
        self.assertTrue(lookup.is_ok, lookup.diagnostics)

        result = lowering_boundary._lower_exact_array_initialization_stage_pipeline(
            item,
            request,
            GenerationLoweringStage(
                stage="selected_body_envelope_lowering",
                output=envelope,
            ),
            lookup.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-MISSING",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("explicit typed vector-length metadata", result.diagnostics[0].message)

    def test_exact_array_initialization_stage_pipeline_reports_missing_m71_metadata(
        self,
    ) -> None:
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si16")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)
        request = LoweringRequest(
            array_body_envelope_skeletons=(skeleton,),
            generation_context=GenerationContext(
                array_initialization_vector_length_metadata=(
                    self.vector_length_metadata_for_item(item),
                ),
            ),
        )
        lookup = lowering_boundary._build_array_body_envelope_skeleton_lookup(request)
        self.assertTrue(lookup.is_ok, lookup.diagnostics)

        result = lowering_boundary._lower_exact_array_initialization_stage_pipeline(
            item,
            request,
            GenerationLoweringStage(
                stage="selected_body_envelope_lowering",
                output=envelope,
            ),
            lookup.unwrap(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-MISSING",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn(
            "explicit typed vector-alignment metadata",
            result.diagnostics[0].message,
        )

    def test_exact_array_initialization_stage_pipeline_is_deterministic(
        self,
    ) -> None:
        first = self.exact_array_initialization_stage_pipeline("si64")
        second = self.exact_array_initialization_stage_pipeline("si64")

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().key, second.unwrap().key)

    def test_exact_array_initialization_stage_pipeline_preserves_typed_boundary(
        self,
    ) -> None:
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        try:
            result = self.exact_array_initialization_stage_pipeline("si32")
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query

        self.assertTrue(result.is_ok, result.diagnostics)
        resolution = result.unwrap().array_initialization_base_type_resolutions[0]
        self.assertEqual(
            tuple(
                request.helper_leaf_kind
                for request in resolution.unresolved_requests
            ),
            (
                "value_generation_vector_length",
                "value_generation_vector_alignment",
                "value_backend_uninit_array",
            ),
        )
        vector_resolution = (
            result.unwrap().array_initialization_vector_length_resolutions[0]
        )
        self.assertEqual(
            tuple(
                request.helper_leaf_kind
                for request in vector_resolution.unresolved_requests
            ),
            (
                "value_generation_vector_alignment",
                "value_backend_uninit_array",
            ),
        )
        alignment_resolution = (
            result.unwrap().array_initialization_vector_alignment_resolutions[0]
        )
        self.assertEqual(
            tuple(
                request.helper_leaf_kind
                for request in alignment_resolution.unresolved_requests
            ),
            ("value_backend_uninit_array",),
        )

    def test_exact_array_body_envelopes_assemble_selected_m63_slots(
        self,
    ) -> None:
        cases = (
            ("si16", 2, "svptrue_b16", "intrin<svptrue_b16>()"),
            ("si32", 4, "svptrue_b32", "intrin<svptrue_b32>()"),
            ("si64", 8, "svptrue_b64", "intrin<svptrue_b64>()"),
        )

        for type_tag, literal, token_text, rhs_text in cases:
            with self.subTest(type_tag=type_tag):
                envelope = self.selected_body_envelope(
                    selected_type_tag=type_tag,
                    selected_literal=literal,
                    token_text=token_text,
                    rhs_text=rhs_text,
                    original_body_text=f"pg = {rhs_text};",
                )
                skeleton = self.exact_array_body_skeleton(
                    selected_type_tag=type_tag,
                )

                result = assemble_exact_array_body_envelope(
                    GenerationLoweringStage(
                        stage="selected_body_envelope_lowering",
                        output=envelope,
                    ),
                    skeleton,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                array_envelope = result.unwrap()
                assert isinstance(array_envelope, ExactArrayBodyEnvelopeIr)
                self.assertEqual(array_envelope.candidate_id, "candidate-1")
                self.assertEqual(array_envelope.selected_type_tag, type_tag)
                self.assertEqual(
                    array_envelope.originating_branch_chain_id,
                    "candidate-1:chain",
                )
                self.assertEqual(
                    tuple(slot.label for slot in array_envelope.slots),
                    ARRAY_BODY_SLOT_LABELS,
                )
                self.assertEqual(
                    tuple(slot.ordinal for slot in array_envelope.slots),
                    (0, 1, 2, 3, 4),
                )
                selected_slot = array_envelope.selected_body_slot
                self.assertIsInstance(
                    selected_slot,
                    ExactArrayBodyEnvelopeSelectedSlot,
                )
                self.assertIs(selected_slot.selected_body_envelope, envelope)
                self.assertEqual(
                    selected_slot.originating_branch_chain_id,
                    envelope.originating_branch_chain_id,
                )
                self.assertEqual(
                    envelope.entries[0].direct_intrinsic_token_text,
                    token_text,
                )
                for slot in array_envelope.slots:
                    self.assertEqual(slot.candidate_id, "candidate-1")
                    self.assertEqual(slot.selected_type_tag, type_tag)
                    self.assertEqual(
                        slot.originating_branch_chain_id,
                        "candidate-1:chain",
                    )
                    if isinstance(slot, ExactArrayBodyEnvelopeOpaqueSlot):
                        self.assertEqual(
                            slot.opaque_source_text,
                            ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[slot.label],
                        )
                        self.assertEqual(
                            slot.source_location.line,
                            ARRAY_BODY_SLOT_LINE_BY_LABEL[slot.label],
                        )

    def test_exact_array_body_envelope_carries_no_body_m63_without_synthesis(
        self,
    ) -> None:
        for type_tag in ("si8", "ui8"):
            with self.subTest(type_tag=type_tag):
                envelope = self.no_selected_body_envelope(type_tag)
                skeleton = self.exact_array_body_skeleton(
                    selected_type_tag=type_tag,
                )

                result = assemble_exact_array_body_envelope(envelope, skeleton)

                self.assertTrue(result.is_ok, result.diagnostics)
                array_envelope = result.unwrap()
                selected_slot = array_envelope.selected_body_slot
                self.assertIs(selected_slot.selected_body_envelope, envelope)
                self.assertIsInstance(
                    selected_slot.selected_body_envelope,
                    NoSelectedBodyEnvelopeIr,
                )
                self.assertEqual(envelope.entries, ())
                self.assertFalse(hasattr(selected_slot, "opaque_source_text"))
                self.assertEqual(
                    tuple(
                        slot.opaque_source_text
                        for slot in array_envelope.slots
                        if isinstance(slot, ExactArrayBodyEnvelopeOpaqueSlot)
                    ),
                    (
                        ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                            "opaque_pre_branch_array_initialization"
                        ],
                        ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                            "opaque_pre_branch_predicate_initialization"
                        ],
                        ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                            "opaque_post_branch_store_call"
                        ],
                        ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                            "opaque_post_branch_return_emission"
                        ],
                    ),
                )

    def test_exact_array_body_envelope_no_body_assembly_is_deterministic(
        self,
    ) -> None:
        for type_tag in ("si8", "ui8"):
            with self.subTest(type_tag=type_tag):
                envelope = self.no_selected_body_envelope(type_tag)
                skeleton = self.exact_array_body_skeleton(
                    selected_type_tag=type_tag,
                )

                first = assemble_exact_array_body_envelope(envelope, skeleton)
                second = assemble_exact_array_body_envelope(envelope, skeleton)

                self.assertTrue(first.is_ok, first.diagnostics)
                self.assertTrue(second.is_ok, second.diagnostics)
                first_envelope = first.unwrap()
                second_envelope = second.unwrap()
                self.assertEqual(first_envelope, second_envelope)
                self.assertEqual(
                    tuple(slot.label for slot in first_envelope.slots),
                    ARRAY_BODY_SLOT_LABELS,
                )
                self.assertIs(
                    first_envelope.selected_body_slot.selected_body_envelope,
                    envelope,
                )
                self.assertIsInstance(
                    first_envelope.selected_body_slot.selected_body_envelope,
                    NoSelectedBodyEnvelopeIr,
                )

    def test_exact_array_body_envelope_preserves_literal_token_mismatch(
        self,
    ) -> None:
        envelope = self.selected_body_envelope(
            selected_type_tag="f64",
            selected_literal=8,
            token_text="svptrue_b16",
            rhs_text="intrin<svptrue_b16>()",
            original_body_text="pg = intrin<svptrue_b16>();",
        )
        skeleton = self.exact_array_body_skeleton(selected_type_tag="f64")

        result = assemble_exact_array_body_envelope(envelope, skeleton)

        self.assertTrue(result.is_ok, result.diagnostics)
        array_envelope = result.unwrap()
        nested = array_envelope.selected_body_slot.selected_body_envelope
        assert isinstance(nested, SelectedBodyEnvelopeIr)
        self.assertIs(nested, envelope)
        self.assertEqual(nested.entries[0].selected_literal, 8)
        self.assertEqual(nested.entries[0].direct_intrinsic_token_text, "svptrue_b16")

    def test_exact_array_body_envelope_slot_assembly_is_deterministic(
        self,
    ) -> None:
        envelope = self.selected_body_envelope()
        skeleton = self.exact_array_body_skeleton()

        first = assemble_exact_array_body_envelope(envelope, skeleton)
        second = assemble_exact_array_body_envelope(envelope, skeleton)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        self.assertEqual(
            GenerationLoweringStage(
                stage="array_body_envelope_slot_assembly",
                output=first.unwrap(),
            ).output,
            first.unwrap(),
        )

    def test_exact_array_initialization_slot_form_lowers_exact_m65_slot(
        self,
    ) -> None:
        array_envelope = self.exact_array_body_envelope()

        result = lower_exact_array_initialization_slot_form(
            GenerationLoweringStage(
                stage="array_body_envelope_slot_assembly",
                output=array_envelope,
            )
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        form = result.unwrap()
        assert isinstance(form, ExactArrayInitializationSlotFormIr)
        self.assertIs(form.source_envelope, array_envelope)
        self.assertEqual(form.candidate_id, array_envelope.candidate_id)
        self.assertEqual(form.selected_type_tag, array_envelope.selected_type_tag)
        self.assertEqual(
            form.originating_branch_chain_id,
            array_envelope.originating_branch_chain_id,
        )
        self.assertEqual(form.slot_label, "opaque_pre_branch_array_initialization")
        self.assertEqual(form.slot_ordinal, 0)
        self.assertEqual(
            form.source_location,
            SourceLocation(
                Path("tsldata/primitives/load_store/array.tsl"),
                105,
                15,
            ),
        )
        slot_text = ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
            "opaque_pre_branch_array_initialization"
        ]
        self.assertEqual(form.original_slot_text, slot_text)
        self.assertEqual(form.variable_token, "tmp")
        self.assertEqual(
            form.variable_token_location,
            SourceLocation(
                Path("tsldata/primitives/load_store/array.tsl"),
                105,
                15 + slot_text.index("tmp"),
                end_line=105,
                end_column=15 + slot_text.index("tmp") + len("tmp"),
            ),
        )

        helper_cases = (
            (
                form.base_type_leaf,
                "type_generation_base_in",
                "type<generation>(base::in)",
            ),
            (
                form.vector_length_leaf,
                "value_generation_vector_length",
                "value<generation>(vector::length)",
            ),
            (
                form.vector_alignment_leaf,
                "value_generation_vector_alignment",
                "value<generation>(vector::alignment)",
            ),
            (
                form.backend_uninit_leaf,
                "value_backend_uninit_array",
                "value<backend>(uninit::array)",
            ),
        )
        for leaf, kind, source_text in helper_cases:
            with self.subTest(kind=kind):
                start = slot_text.index(source_text)
                self.assertEqual(leaf.kind, kind)
                self.assertEqual(leaf.source_text, source_text)
                self.assertEqual(
                    leaf.source_location,
                    SourceLocation(
                        Path("tsldata/primitives/load_store/array.tsl"),
                        105,
                        15 + start,
                        end_line=105,
                        end_column=15 + start + len(source_text),
                    ),
                )
        self.assertIs(
            GenerationLoweringStage(
                stage="array_initialization_slot_form_lowering",
                output=form,
            ).output,
            form,
        )

    def test_exact_array_initialization_slot_form_is_deterministic(
        self,
    ) -> None:
        array_envelope = self.exact_array_body_envelope()

        first = lower_exact_array_initialization_slot_form(array_envelope)
        second = lower_exact_array_initialization_slot_form(array_envelope)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())
        self.assertIs(first.unwrap().source_envelope, array_envelope)

    def test_exact_array_initialization_helper_requests_lower_m66_form(
        self,
    ) -> None:
        form_result = lower_exact_array_initialization_slot_form(
            self.exact_array_body_envelope(),
        )
        self.assertTrue(form_result.is_ok, form_result.diagnostics)
        form = form_result.unwrap()

        result = lower_exact_array_initialization_helper_requests(
            GenerationLoweringStage(
                stage="array_initialization_slot_form_lowering",
                output=form,
            )
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        helper_ir = result.unwrap()
        assert isinstance(helper_ir, ExactArrayInitializationHelperRequestIr)
        self.assertIs(helper_ir.source_form, form)
        self.assertIs(helper_ir.source_envelope, form.source_envelope)
        self.assertEqual(helper_ir.candidate_id, form.candidate_id)
        self.assertEqual(helper_ir.selected_type_tag, form.selected_type_tag)
        self.assertEqual(
            helper_ir.originating_branch_chain_id,
            form.originating_branch_chain_id,
        )
        self.assertEqual(helper_ir.slot_label, form.slot_label)
        self.assertEqual(helper_ir.slot_ordinal, 0)
        self.assertEqual(helper_ir.variable_token, "tmp")
        self.assertEqual(
            tuple(request.request_ordinal for request in helper_ir.requests),
            (0, 1, 2, 3),
        )
        request_cases = (
            (
                "generation_type",
                "type_generation_base_in",
                form.base_type_leaf,
            ),
            (
                "generation_value",
                "value_generation_vector_length",
                form.vector_length_leaf,
            ),
            (
                "generation_value",
                "value_generation_vector_alignment",
                form.vector_alignment_leaf,
            ),
            (
                "backend_value",
                "value_backend_uninit_array",
                form.backend_uninit_leaf,
            ),
        )
        for request, (request_kind, leaf_kind, leaf) in zip(
            helper_ir.requests,
            request_cases,
            strict=True,
        ):
            with self.subTest(leaf_kind=leaf_kind):
                assert isinstance(request, ExactArrayInitializationHelperRequestRecord)
                self.assertEqual(request.request_kind, request_kind)
                self.assertEqual(request.helper_leaf_kind, leaf_kind)
                self.assertEqual(request.leaf_source_text, leaf.source_text)
                self.assertEqual(
                    request.leaf_source_location,
                    leaf.source_location,
                )
                self.assertEqual(request.candidate_id, form.candidate_id)
                self.assertEqual(request.selected_type_tag, form.selected_type_tag)
                self.assertEqual(
                    request.originating_branch_chain_id,
                    form.originating_branch_chain_id,
                )
                self.assertEqual(request.slot_ordinal, form.slot_ordinal)
                self.assertEqual(request.variable_token, "tmp")
        self.assertIs(
            GenerationLoweringStage(
                stage="array_initialization_helper_request_lowering",
                output=helper_ir,
            ).output,
            helper_ir,
        )

    def test_exact_array_initialization_helper_requests_are_deterministic(
        self,
    ) -> None:
        form = lower_exact_array_initialization_slot_form(
            self.exact_array_body_envelope(),
        ).unwrap()

        first = lower_exact_array_initialization_helper_requests(form)
        second = lower_exact_array_initialization_helper_requests(form)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_exact_array_initialization_helper_requests_reject_invalid_sources(
        self,
    ) -> None:
        body_ir = self.selected_body_ir()
        implementation = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            selected_body_envelopes=(self.selected_body_envelope(),),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-SOURCE-UNSUPPORTED",
                "array.tsl",
                107,
                15,
                "M66",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-SOURCE-UNSUPPORTED",
                None,
                None,
                None,
                "M66",
            ),
            (
                "missing_form",
                implementation,
                "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-FORM-MISSING",
                "array.tsl",
                107,
                15,
                "array_initialization_slot_forms",
            ),
        )

        for name, source, code, path, line, column, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_helper_requests(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path=path,
                    line=line,
                    column=column,
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_helper_requests_reject_bad_leaves(
        self,
    ) -> None:
        cases = (
            ("missing", "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING"),
            ("duplicate", "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-DUPLICATE"),
            ("mismatch", "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISMATCH"),
            (
                "unsupported",
                "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-UNSUPPORTED",
            ),
        )

        for name, code in cases:
            with self.subTest(name=name):
                form = lower_exact_array_initialization_slot_form(
                    self.exact_array_body_envelope(),
                ).unwrap()
                if name == "missing":
                    object.__setattr__(form, "base_type_leaf", None)
                elif name == "duplicate":
                    object.__setattr__(
                        form,
                        "vector_length_leaf",
                        form.base_type_leaf,
                    )
                elif name == "mismatch":
                    bad_leaf = replace(form.vector_length_leaf)
                    object.__setattr__(
                        bad_leaf,
                        "kind",
                        "value_backend_uninit_array",
                    )
                    object.__setattr__(
                        bad_leaf,
                        "source_text",
                        "value<backend>(uninit::array)",
                    )
                    object.__setattr__(form, "vector_length_leaf", bad_leaf)
                else:
                    bad_leaf = replace(form.vector_length_leaf)
                    object.__setattr__(
                        bad_leaf,
                        "source_text",
                        "value<generation>(vector::lanes)",
                    )
                    object.__setattr__(form, "vector_length_leaf", bad_leaf)

                result = lower_exact_array_initialization_helper_requests(form)

                self.assertFalse(result.is_ok)
                self.assertTrue(any(diagnostic.code == code for diagnostic in result.diagnostics))
                first = next(
                    diagnostic
                    for diagnostic in result.diagnostics
                    if diagnostic.code == code
                )
                self.assertEqual(first.severity, "error")
                self.assertIsNotNone(first.location)

    def test_exact_array_initialization_helper_requests_report_provenance_mismatch(
        self,
    ) -> None:
        form = lower_exact_array_initialization_slot_form(
            self.exact_array_body_envelope(),
        ).unwrap()
        object.__setattr__(form, "candidate_id", "other-candidate")

        result = lower_exact_array_initialization_helper_requests(form)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_initialization_base_type_request_resolves_m67_request(
        self,
    ) -> None:
        for selected_type_tag in ("si16", "ui32"):
            with self.subTest(selected_type_tag=selected_type_tag):
                helper_ir = self.exact_array_initialization_helper_request_ir(
                    selected_type_tag=selected_type_tag,
                )
                sources = (
                    helper_ir,
                    GenerationLoweringStage(
                        stage="array_initialization_helper_request_lowering",
                        output=helper_ir,
                    ),
                    LoweredImplementation(
                        candidate_id=helper_ir.candidate_id,
                        status="lowered",
                        array_initialization_helper_requests=(helper_ir,),
                    ),
                )

                for source in sources:
                    result = lower_exact_array_initialization_base_type_request(
                        source,
                    )

                    self.assertTrue(result.is_ok, result.diagnostics)
                    resolution = result.unwrap()
                    assert isinstance(
                        resolution,
                        ExactArrayInitializationBaseTypeResolutionIr,
                    )
                    self.assertIs(resolution.source_request_ir, helper_ir)
                    self.assertIs(
                        resolution.source_base_type_request,
                        helper_ir.requests[0],
                    )
                    self.assertEqual(
                        resolution.resolved_type_ref,
                        GenerationTypeRef(
                            kind="base.in",
                            type_tag=selected_type_tag,
                        ),
                    )
                    self.assertEqual(
                        resolution.unresolved_requests,
                        helper_ir.requests[1:],
                    )
                    self.assertEqual(
                        tuple(
                            request.helper_leaf_kind
                            for request in resolution.unresolved_requests
                        ),
                        (
                            "value_generation_vector_length",
                            "value_generation_vector_alignment",
                            "value_backend_uninit_array",
                        ),
                    )
                    self.assertEqual(resolution.candidate_id, helper_ir.candidate_id)
                    self.assertEqual(resolution.selected_type_tag, selected_type_tag)
                    self.assertEqual(
                        resolution.originating_branch_chain_id,
                        helper_ir.originating_branch_chain_id,
                    )
                    self.assertEqual(
                        resolution.slot_label,
                        "opaque_pre_branch_array_initialization",
                    )
                    self.assertEqual(resolution.slot_ordinal, 0)
                    self.assertEqual(resolution.variable_token, "tmp")
                    self.assertIs(
                        GenerationLoweringStage(
                            stage=(
                                "array_initialization_base_type_request_resolution"
                            ),
                            output=resolution,
                        ).output,
                        resolution,
                    )

    def test_exact_array_initialization_base_type_request_rejects_invalid_sources(
        self,
    ) -> None:
        helper_ir = self.exact_array_initialization_helper_request_ir()
        body_ir = self.selected_body_ir()
        implementation_without_ir = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            selected_body_envelopes=(self.selected_body_envelope(),),
        )
        implementation_with_multiple = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_helper_requests=(helper_ir, helper_ir),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-SOURCE-UNSUPPORTED",
                "M67",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-SOURCE-UNSUPPORTED",
                "M67",
            ),
            (
                "missing_ir",
                implementation_without_ir,
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MISSING",
                "array_initialization_helper_requests",
            ),
            (
                "multiple_ir",
                implementation_with_multiple,
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_base_type_request(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_base_type_request_rejects_bad_records(
        self,
    ) -> None:
        cases = (
            (
                "missing",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISSING",
            ),
            (
                "duplicate",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-DUPLICATE",
            ),
            (
                "ordinal",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH",
            ),
            (
                "kind",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH",
            ),
            (
                "leaf_kind",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH",
            ),
            (
                "source_text",
                "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-UNSUPPORTED",
            ),
        )

        for name, code in cases:
            with self.subTest(name=name):
                helper_ir = self.exact_array_initialization_helper_request_ir()
                base_request = helper_ir.requests[0]
                if name == "missing":
                    object.__setattr__(helper_ir, "requests", helper_ir.requests[1:])
                elif name == "duplicate":
                    object.__setattr__(
                        helper_ir,
                        "requests",
                        (base_request, *helper_ir.requests),
                    )
                elif name == "ordinal":
                    object.__setattr__(base_request, "request_ordinal", 1)
                elif name == "kind":
                    object.__setattr__(base_request, "request_kind", "backend_value")
                elif name == "leaf_kind":
                    object.__setattr__(
                        base_request,
                        "helper_leaf_kind",
                        "value_generation_vector_length",
                    )
                else:
                    object.__setattr__(
                        base_request,
                        "leaf_source_text",
                        "type<generation>(base::out)",
                    )

                result = lower_exact_array_initialization_base_type_request(helper_ir)

                self.assertFalse(result.is_ok)
                self.assertTrue(
                    any(diagnostic.code == code for diagnostic in result.diagnostics),
                    result.diagnostics,
                )
                diagnostic = next(
                    diagnostic
                    for diagnostic in result.diagnostics
                    if diagnostic.code == code
                )
                self.assertEqual(diagnostic.severity, "error")
                self.assertIsNotNone(diagnostic.location)

    def test_exact_array_initialization_base_type_request_rejects_selected_type(
        self,
    ) -> None:
        helper_ir = self.exact_array_initialization_helper_request_ir(
            selected_type_tag="f32",
        )

        result = lower_exact_array_initialization_base_type_request(helper_ir)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("concrete integer", result.diagnostics[0].message)

    def test_exact_array_initialization_base_type_request_reports_provenance_mismatch(
        self,
    ) -> None:
        helper_ir = self.exact_array_initialization_helper_request_ir()
        object.__setattr__(helper_ir.requests[0], "candidate_id", "other-candidate")

        result = lower_exact_array_initialization_base_type_request(helper_ir)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_initialization_base_type_request_rejects_context_mismatch(
        self,
    ) -> None:
        helper_ir = self.exact_array_initialization_helper_request_ir(
            selected_type_tag="si16",
        )

        result = lower_exact_array_initialization_base_type_request(
            helper_ir,
            GenerationContext(type_tag_override="ui16"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("selected type tag", result.diagnostics[0].message)

    def test_exact_array_initialization_base_type_request_does_not_evaluate_raw_helper_text(
        self,
    ) -> None:
        helper_ir = self.exact_array_initialization_helper_request_ir(
            selected_type_tag="si32",
        )
        original = lowering_boundary.resolve_generation_type_query

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw generation type query evaluator was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        try:
            result = lower_exact_array_initialization_base_type_request(helper_ir)
        finally:
            lowering_boundary.resolve_generation_type_query = original

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().resolved_type_ref,
            GenerationTypeRef(kind="base.in", type_tag="si32"),
        )

    def test_exact_array_initialization_vector_length_request_resolves_m67_request(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution(
            selected_type_tag="si16",
        )
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            lanes=23,
        )
        context = GenerationContext(
            selected_candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            array_initialization_vector_length_metadata=(metadata,),
        )
        sources = (
            base_resolution,
            GenerationLoweringStage(
                stage="array_initialization_base_type_request_resolution",
                output=base_resolution,
            ),
            LoweredImplementation(
                candidate_id=base_resolution.candidate_id,
                status="lowered",
                array_initialization_base_type_resolutions=(base_resolution,),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_array_initialization_vector_length_request(
                    source,
                    context,
                    selected_candidate_id=base_resolution.candidate_id,
                    target_extension="sve",
                    source_extension="sve",
                    selected_type_tag=base_resolution.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                resolution = result.unwrap()
                assert isinstance(
                    resolution,
                    ExactArrayInitializationVectorLengthResolutionIr,
                )
                self.assertIs(resolution.source_base_type_resolution, base_resolution)
                self.assertIs(
                    resolution.source_vector_length_request,
                    base_resolution.unresolved_requests[0],
                )
                self.assertEqual(
                    resolution.resolved_vector_length,
                    ExactArrayInitializationVectorLengthValue(
                        kind="fixed_lanes",
                        lanes=23,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in resolution.unresolved_requests
                    ),
                    (
                        "value_generation_vector_alignment",
                        "value_backend_uninit_array",
                    ),
                )
                self.assertEqual(resolution.target_extension, "sve")
                self.assertEqual(resolution.source_extension, "sve")
                self.assertIs(
                    GenerationLoweringStage(
                        stage=(
                            "array_initialization_vector_length_request_resolution"
                        ),
                        output=resolution,
                    ).output,
                    resolution,
                )

    def test_exact_array_initialization_vector_length_request_preserves_runtime_policy(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            kind="scalable_lanes",
        )

        result = lower_exact_array_initialization_vector_length_request(
            base_resolution,
            GenerationContext(
                array_initialization_vector_length_metadata=(metadata,),
            ),
            selected_candidate_id=base_resolution.candidate_id,
            target_extension="sve",
            source_extension="sve",
            selected_type_tag=base_resolution.selected_type_tag,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().resolved_vector_length,
            ExactArrayInitializationVectorLengthValue(kind="scalable_lanes"),
        )

    def test_exact_array_initialization_vector_length_request_rejects_invalid_sources(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        body_ir = self.selected_body_ir()
        implementation_without_ir = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            selected_body_envelopes=(self.selected_body_envelope(),),
        )
        implementation_with_multiple = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_base_type_resolutions=(
                base_resolution,
                base_resolution,
            ),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-SOURCE-UNSUPPORTED",
                "M68",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-SOURCE-UNSUPPORTED",
                "M68",
            ),
            (
                "missing_ir",
                implementation_without_ir,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MISSING",
                "array_initialization_base_type_resolutions",
            ),
            (
                "multiple_ir",
                implementation_with_multiple,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_vector_length_request(
                    source,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_vector_length_request_rejects_metadata_issues(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            lanes=17,
        )
        conflicting = replace(
            metadata,
            vector_length=ExactArrayInitializationVectorLengthValue(
                kind="fixed_lanes",
                lanes=19,
            ),
        )
        runtime = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            kind="runtime_lanes",
        )
        cases = (
            (
                "missing",
                (),
                False,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-MISSING",
                "explicit typed vector-length metadata",
            ),
            (
                "duplicate",
                (metadata, metadata),
                False,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-DUPLICATE",
                "duplicate",
            ),
            (
                "conflict",
                (metadata, conflicting),
                False,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-CONFLICT",
                "conflicting",
            ),
            (
                "runtime_numeric",
                (runtime,),
                True,
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-UNSUPPORTED",
                "fixed numeric lanes",
            ),
        )

        for name, metadata_entries, require_fixed, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_vector_length_request(
                    base_resolution,
                    GenerationContext(
                        array_initialization_vector_length_metadata=metadata_entries,
                    ),
                    selected_candidate_id=base_resolution.candidate_id,
                    target_extension="sve",
                    source_extension="sve",
                    selected_type_tag=base_resolution.selected_type_tag,
                    require_fixed_lanes=require_fixed,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_vector_length_request_rejects_bad_records(
        self,
    ) -> None:
        cases = (
            (
                "missing",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISSING",
            ),
            (
                "duplicate",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-DUPLICATE",
            ),
            (
                "ordinal",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH",
            ),
            (
                "kind",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH",
            ),
            (
                "leaf_kind",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH",
            ),
            (
                "source_text",
                "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-UNSUPPORTED",
            ),
        )

        for name, code in cases:
            with self.subTest(name=name):
                base_resolution = (
                    self.exact_array_initialization_base_type_resolution()
                )
                vector_request = base_resolution.unresolved_requests[0]
                if name == "missing":
                    object.__setattr__(
                        base_resolution,
                        "unresolved_requests",
                        base_resolution.unresolved_requests[2:],
                    )
                elif name == "duplicate":
                    object.__setattr__(
                        base_resolution,
                        "unresolved_requests",
                        (vector_request, *base_resolution.unresolved_requests),
                    )
                elif name == "ordinal":
                    object.__setattr__(vector_request, "request_ordinal", 2)
                elif name == "kind":
                    object.__setattr__(vector_request, "request_kind", "backend_value")
                elif name == "leaf_kind":
                    object.__setattr__(
                        vector_request,
                        "helper_leaf_kind",
                        "value_backend_uninit_array",
                    )
                else:
                    object.__setattr__(
                        vector_request,
                        "leaf_source_text",
                        "value<generation>(vector::width)",
                    )

                result = lower_exact_array_initialization_vector_length_request(
                    base_resolution,
                )

                self.assertFalse(result.is_ok)
                self.assertTrue(
                    any(diagnostic.code == code for diagnostic in result.diagnostics),
                    result.diagnostics,
                )
                diagnostic = next(
                    diagnostic
                    for diagnostic in result.diagnostics
                    if diagnostic.code == code
                )
                self.assertEqual(diagnostic.severity, "error")
                self.assertIsNotNone(diagnostic.location)

    def test_exact_array_initialization_vector_length_request_rejects_context_mismatch(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
        )

        result = lower_exact_array_initialization_vector_length_request(
            base_resolution,
            GenerationContext(
                selected_candidate_id="other-candidate",
                array_initialization_vector_length_metadata=(metadata,),
            ),
            target_extension="sve",
            source_extension="sve",
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("selected candidate context", result.diagnostics[0].message)

    def test_exact_array_initialization_vector_length_request_reports_provenance_mismatch(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        object.__setattr__(
            base_resolution.unresolved_requests[0],
            "candidate_id",
            "other-candidate",
        )

        result = lower_exact_array_initialization_vector_length_request(
            base_resolution,
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_initialization_vector_length_request_is_deterministic(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        matching = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
            lanes=31,
        )
        other = self.vector_length_metadata(
            candidate_id="other-candidate",
            selected_type_tag=base_resolution.selected_type_tag,
            lanes=9,
        )
        contexts = (
            GenerationContext(
                array_initialization_vector_length_metadata=(matching, other),
            ),
            GenerationContext(
                array_initialization_vector_length_metadata=(other, matching),
            ),
        )

        first = lower_exact_array_initialization_vector_length_request(
            base_resolution,
            contexts[0],
            selected_candidate_id=base_resolution.candidate_id,
            target_extension="sve",
            source_extension="sve",
            selected_type_tag=base_resolution.selected_type_tag,
        )
        second = lower_exact_array_initialization_vector_length_request(
            base_resolution,
            contexts[1],
            selected_candidate_id=base_resolution.candidate_id,
            target_extension="sve",
            source_extension="sve",
            selected_type_tag=base_resolution.selected_type_tag,
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().key, second.unwrap().key)

    def test_exact_array_initialization_vector_length_request_does_not_evaluate_raw_helper_text(
        self,
    ) -> None:
        base_resolution = self.exact_array_initialization_base_type_resolution()
        metadata = self.vector_length_metadata(
            candidate_id=base_resolution.candidate_id,
            selected_type_tag=base_resolution.selected_type_tag,
        )
        original = lowering_boundary.resolve_generation_value_query

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw generation value query evaluator was called")

        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        try:
            result = lower_exact_array_initialization_vector_length_request(
                base_resolution,
                GenerationContext(
                    array_initialization_vector_length_metadata=(metadata,),
                ),
                selected_candidate_id=base_resolution.candidate_id,
                target_extension="sve",
                source_extension="sve",
                selected_type_tag=base_resolution.selected_type_tag,
            )
        finally:
            lowering_boundary.resolve_generation_value_query = original

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().resolved_vector_length,
            ExactArrayInitializationVectorLengthValue(kind="fixed_lanes", lanes=17),
        )

    def test_exact_array_initialization_vector_alignment_request_resolves_m67_request(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution(
                selected_type_tag="si16",
            )
        )
        metadata = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
            alignment_bytes=96,
        )
        context = GenerationContext(
            selected_candidate_id=vector_length_resolution.candidate_id,
            selected_type_tag=vector_length_resolution.selected_type_tag,
            array_initialization_vector_alignment_metadata=(metadata,),
        )
        sources = (
            vector_length_resolution,
            GenerationLoweringStage(
                stage="array_initialization_vector_length_request_resolution",
                output=vector_length_resolution,
            ),
            LoweredImplementation(
                candidate_id=vector_length_resolution.candidate_id,
                status="lowered",
                array_initialization_vector_length_resolutions=(
                    vector_length_resolution,
                ),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_array_initialization_vector_alignment_request(
                    source,
                    context,
                    selected_candidate_id=vector_length_resolution.candidate_id,
                    target_extension=vector_length_resolution.target_extension,
                    source_extension=vector_length_resolution.source_extension,
                    selected_type_tag=vector_length_resolution.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                resolution = result.unwrap()
                assert isinstance(
                    resolution,
                    ExactArrayInitializationVectorAlignmentResolutionIr,
                )
                self.assertIs(
                    resolution.source_vector_length_resolution,
                    vector_length_resolution,
                )
                self.assertIs(
                    resolution.source_vector_alignment_request,
                    vector_length_resolution.unresolved_requests[0],
                )
                self.assertEqual(
                    resolution.resolved_vector_alignment,
                    ExactArrayInitializationVectorAlignmentValue(
                        kind="fixed_bytes",
                        bytes=96,
                    ),
                )
                self.assertEqual(
                    tuple(
                        request.helper_leaf_kind
                        for request in resolution.unresolved_requests
                    ),
                    ("value_backend_uninit_array",),
                )
                self.assertEqual(resolution.target_extension, "sve")
                self.assertEqual(resolution.source_extension, "sve")
                self.assertIs(
                    GenerationLoweringStage(
                        stage=(
                            "array_initialization_vector_alignment_request_resolution"
                        ),
                        output=resolution,
                    ).output,
                    resolution,
                )

    def test_exact_array_initialization_vector_alignment_request_rejects_invalid_sources(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        body_ir = self.selected_body_ir()
        implementation_without_ir = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            selected_body_envelopes=(self.selected_body_envelope(),),
        )
        implementation_with_multiple = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_vector_length_resolutions=(
                vector_length_resolution,
                vector_length_resolution,
            ),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-SOURCE-UNSUPPORTED",
                "M70",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-SOURCE-UNSUPPORTED",
                "M70",
            ),
            (
                "missing_ir",
                implementation_without_ir,
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MISSING",
                "array_initialization_vector_length_resolutions",
            ),
            (
                "multiple_ir",
                implementation_with_multiple,
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_vector_alignment_request(
                    source,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_vector_alignment_request_rejects_metadata_issues(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        metadata = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
            alignment_bytes=64,
        )
        conflicting = replace(
            metadata,
            vector_alignment=ExactArrayInitializationVectorAlignmentValue(
                kind="fixed_bytes",
                bytes=128,
            ),
        )
        unsupported = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
            kind="unsupported",
            unsupported_policy="requires-later-backend-policy",
        )
        cases = (
            (
                "missing",
                (),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-MISSING",
                "explicit typed vector-alignment metadata",
            ),
            (
                "duplicate",
                (metadata, metadata),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-DUPLICATE",
                "duplicate",
            ),
            (
                "conflict",
                (metadata, conflicting),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-CONFLICT",
                "conflicting",
            ),
            (
                "unsupported",
                (unsupported,),
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-UNSUPPORTED",
                "unsupported",
            ),
        )

        for name, metadata_entries, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_vector_alignment_request(
                    vector_length_resolution,
                    GenerationContext(
                        array_initialization_vector_alignment_metadata=(
                            metadata_entries
                        ),
                    ),
                    selected_candidate_id=vector_length_resolution.candidate_id,
                    target_extension=vector_length_resolution.target_extension,
                    source_extension=vector_length_resolution.source_extension,
                    selected_type_tag=vector_length_resolution.selected_type_tag,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_vector_alignment_request_rejects_bad_records(
        self,
    ) -> None:
        cases = (
            (
                "missing",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISSING",
            ),
            (
                "duplicate",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-DUPLICATE",
            ),
            (
                "ordinal",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH",
            ),
            (
                "kind",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH",
            ),
            (
                "leaf_kind",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH",
            ),
            (
                "source_text",
                "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-UNSUPPORTED",
            ),
        )

        for name, code in cases:
            with self.subTest(name=name):
                vector_length_resolution = (
                    self.exact_array_initialization_vector_length_resolution()
                )
                vector_request = vector_length_resolution.unresolved_requests[0]
                if name == "missing":
                    object.__setattr__(
                        vector_length_resolution,
                        "unresolved_requests",
                        vector_length_resolution.unresolved_requests[1:],
                    )
                elif name == "duplicate":
                    object.__setattr__(
                        vector_length_resolution,
                        "unresolved_requests",
                        (vector_request, *vector_length_resolution.unresolved_requests),
                    )
                elif name == "ordinal":
                    object.__setattr__(vector_request, "request_ordinal", 3)
                elif name == "kind":
                    object.__setattr__(vector_request, "request_kind", "backend_value")
                elif name == "leaf_kind":
                    object.__setattr__(
                        vector_request,
                        "helper_leaf_kind",
                        "value_backend_uninit_array",
                    )
                else:
                    object.__setattr__(
                        vector_request,
                        "leaf_source_text",
                        "value<generation>(vector::align)",
                    )

                result = lower_exact_array_initialization_vector_alignment_request(
                    vector_length_resolution,
                )

                self.assertFalse(result.is_ok)
                self.assertTrue(
                    any(diagnostic.code == code for diagnostic in result.diagnostics),
                    result.diagnostics,
                )
                diagnostic = next(
                    diagnostic
                    for diagnostic in result.diagnostics
                    if diagnostic.code == code
                )
                self.assertEqual(diagnostic.severity, "error")
                self.assertIsNotNone(diagnostic.location)

    def test_exact_array_initialization_vector_alignment_request_rejects_context_mismatch(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        metadata = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )

        result = lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            GenerationContext(
                selected_candidate_id="other-candidate",
                array_initialization_vector_alignment_metadata=(metadata,),
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("selected candidate context", result.diagnostics[0].message)

    def test_exact_array_initialization_vector_alignment_request_reports_provenance_mismatch(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        object.__setattr__(
            vector_length_resolution.unresolved_requests[0],
            "candidate_id",
            "other-candidate",
        )

        result = lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_initialization_vector_alignment_request_is_deterministic(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        matching = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
            alignment_bytes=256,
        )
        other = self.vector_alignment_metadata(
            candidate_id="other-candidate",
            selected_type_tag=vector_length_resolution.selected_type_tag,
            alignment_bytes=32,
        )
        contexts = (
            GenerationContext(
                array_initialization_vector_alignment_metadata=(matching, other),
            ),
            GenerationContext(
                array_initialization_vector_alignment_metadata=(other, matching),
            ),
        )

        first = lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            contexts[0],
            selected_candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )
        second = lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            contexts[1],
            selected_candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().key, second.unwrap().key)

    def test_exact_array_initialization_vector_alignment_request_uses_no_raw_or_external_state(
        self,
    ) -> None:
        vector_length_resolution = (
            self.exact_array_initialization_vector_length_resolution()
        )
        metadata = self.vector_alignment_metadata(
            candidate_id=vector_length_resolution.candidate_id,
            target_extension=vector_length_resolution.target_extension,
            source_extension=vector_length_resolution.source_extension,
            selected_type_tag=vector_length_resolution.selected_type_tag,
        )
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw generation value query evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata read was called"
                    ),
                ),
            ):
                result = lower_exact_array_initialization_vector_alignment_request(
                    vector_length_resolution,
                    GenerationContext(
                        array_initialization_vector_alignment_metadata=(metadata,),
                    ),
                    selected_candidate_id=vector_length_resolution.candidate_id,
                    target_extension=vector_length_resolution.target_extension,
                    source_extension=vector_length_resolution.source_extension,
                    selected_type_tag=vector_length_resolution.selected_type_tag,
                )
        finally:
            lowering_boundary.resolve_generation_value_query = original_value_query
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().resolved_vector_alignment,
            ExactArrayInitializationVectorAlignmentValue(
                kind="fixed_bytes",
                bytes=64,
            ),
        )

    def test_exact_array_initialization_helper_set_completion_resolves_m71_request(
        self,
    ) -> None:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution(
                selected_type_tag="si16",
            )
        )
        sources = (
            vector_alignment_resolution,
            GenerationLoweringStage(
                stage="array_initialization_vector_alignment_request_resolution",
                output=vector_alignment_resolution,
            ),
            LoweredImplementation(
                candidate_id=vector_alignment_resolution.candidate_id,
                status="lowered",
                array_initialization_vector_alignment_resolutions=(
                    vector_alignment_resolution,
                ),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_array_initialization_helper_set_completion(
                    source,
                    GenerationContext(
                        selected_candidate_id=(
                            vector_alignment_resolution.candidate_id
                        ),
                        selected_type_tag=(
                            vector_alignment_resolution.selected_type_tag
                        ),
                    ),
                    selected_candidate_id=vector_alignment_resolution.candidate_id,
                    target_extension=vector_alignment_resolution.target_extension,
                    source_extension=vector_alignment_resolution.source_extension,
                    selected_type_tag=vector_alignment_resolution.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                completion = result.unwrap()
                assert isinstance(
                    completion,
                    ExactArrayInitializationHelperSetCompletionIr,
                )
                self.assertIs(
                    completion.source_vector_alignment_resolution,
                    vector_alignment_resolution,
                )
                self.assertIs(
                    completion.source_vector_length_resolution,
                    vector_alignment_resolution.source_vector_length_resolution,
                )
                self.assertIs(
                    completion.source_base_type_resolution,
                    vector_alignment_resolution.source_vector_length_resolution
                    .source_base_type_resolution,
                )
                self.assertIs(
                    completion.source_backend_uninit_request,
                    vector_alignment_resolution.unresolved_requests[0],
                )
                self.assertEqual(
                    completion.source_backend_uninit_request.request_ordinal,
                    3,
                )
                self.assertEqual(
                    completion.source_backend_uninit_request.request_kind,
                    "backend_value",
                )
                self.assertEqual(
                    completion.source_backend_uninit_request.helper_leaf_kind,
                    "value_backend_uninit_array",
                )
                self.assertEqual(
                    completion.unresolved_backend_uninit.policy,
                    "deferred_backend_value",
                )
                self.assertEqual(
                    completion.unresolved_backend_uninit.source_backend_uninit_request
                    .leaf_source_text,
                    "value<backend>(uninit::array)",
                )
                self.assertIs(
                    GenerationLoweringStage(
                        stage="array_initialization_helper_set_completion",
                        output=completion,
                    ).output,
                    completion,
                )

    def test_exact_array_initialization_helper_set_completion_rejects_invalid_sources(
        self,
    ) -> None:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution()
        )
        body_ir = self.selected_body_ir()
        implementation_without_ir = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_vector_length_resolutions=(
                vector_alignment_resolution.source_vector_length_resolution,
            ),
        )
        implementation_with_multiple = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_vector_alignment_resolutions=(
                vector_alignment_resolution,
                vector_alignment_resolution,
            ),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-SOURCE-UNSUPPORTED",
                "M71",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-SOURCE-UNSUPPORTED",
                "M71",
            ),
            (
                "missing_ir",
                implementation_without_ir,
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MISSING",
                "array_initialization_vector_alignment_resolutions",
            ),
            (
                "multiple_ir",
                implementation_with_multiple,
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_helper_set_completion(
                    source,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_helper_set_completion_rejects_bad_records(
        self,
    ) -> None:
        cases = (
            (
                "missing",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISSING",
            ),
            (
                "duplicate",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-DUPLICATE",
            ),
            (
                "ordinal",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISMATCH",
            ),
            (
                "kind",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISMATCH",
            ),
            (
                "leaf_kind",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISMATCH",
            ),
            (
                "source_text",
                "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-UNSUPPORTED",
            ),
        )

        for name, code in cases:
            with self.subTest(name=name):
                vector_alignment_resolution = (
                    self.exact_array_initialization_vector_alignment_resolution()
                )
                backend_request = vector_alignment_resolution.unresolved_requests[0]
                if name == "missing":
                    object.__setattr__(
                        vector_alignment_resolution,
                        "unresolved_requests",
                        (),
                    )
                elif name == "duplicate":
                    object.__setattr__(
                        vector_alignment_resolution,
                        "unresolved_requests",
                        (backend_request, backend_request),
                    )
                elif name == "ordinal":
                    object.__setattr__(backend_request, "request_ordinal", 2)
                elif name == "kind":
                    object.__setattr__(
                        backend_request,
                        "request_kind",
                        "generation_value",
                    )
                elif name == "leaf_kind":
                    object.__setattr__(
                        backend_request,
                        "helper_leaf_kind",
                        "value_generation_vector_alignment",
                    )
                else:
                    object.__setattr__(
                        backend_request,
                        "leaf_source_text",
                        "value<backend>(uninit::scalar)",
                    )

                result = lower_exact_array_initialization_helper_set_completion(
                    vector_alignment_resolution,
                )

                self.assertFalse(result.is_ok)
                self.assertTrue(
                    any(diagnostic.code == code for diagnostic in result.diagnostics),
                    result.diagnostics,
                )
                diagnostic = next(
                    diagnostic
                    for diagnostic in result.diagnostics
                    if diagnostic.code == code
                )
                self.assertEqual(diagnostic.severity, "error")
                self.assertIsNotNone(diagnostic.location)

    def test_exact_array_initialization_helper_set_completion_rejects_context_mismatch(
        self,
    ) -> None:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution()
        )

        result = lower_exact_array_initialization_helper_set_completion(
            vector_alignment_resolution,
            GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-HELPER-SET-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("selected candidate context", result.diagnostics[0].message)

    def test_exact_array_initialization_helper_set_completion_reports_provenance_mismatch(
        self,
    ) -> None:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution()
        )
        object.__setattr__(
            vector_alignment_resolution.unresolved_requests[0],
            "candidate_id",
            "other-candidate",
        )

        result = lower_exact_array_initialization_helper_set_completion(
            vector_alignment_resolution,
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-HELPER-SET-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_initialization_helper_set_completion_is_deterministic(
        self,
    ) -> None:
        first_source = self.exact_array_initialization_vector_alignment_resolution()
        second_source = self.exact_array_initialization_vector_alignment_resolution()

        first = lower_exact_array_initialization_helper_set_completion(first_source)
        second = lower_exact_array_initialization_helper_set_completion(second_source)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().key, second.unwrap().key)

    def test_exact_array_initialization_helper_set_completion_uses_no_raw_or_external_state(
        self,
    ) -> None:
        vector_alignment_resolution = (
            self.exact_array_initialization_vector_alignment_resolution()
        )
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = lower_exact_array_initialization_helper_set_completion(
                    vector_alignment_resolution,
                )
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().unresolved_backend_uninit.policy,
            "deferred_backend_value",
        )

    def test_exact_array_initialization_declaration_shell_lowers_m72_completion(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion(
            selected_type_tag="si32",
        )
        sources = (
            completion,
            GenerationLoweringStage(
                stage="array_initialization_helper_set_completion",
                output=completion,
            ),
            LoweredImplementation(
                candidate_id=completion.candidate_id,
                status="lowered",
                array_initialization_helper_set_completions=(completion,),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_array_initialization_declaration_shell(
                    source,
                    GenerationContext(
                        selected_candidate_id=completion.candidate_id,
                        selected_type_tag=completion.selected_type_tag,
                    ),
                    selected_candidate_id=completion.candidate_id,
                    target_extension=completion.target_extension,
                    source_extension=completion.source_extension,
                    selected_type_tag=completion.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                shell = result.unwrap()
                assert isinstance(shell, ExactArrayInitializationDeclarationShellIr)
                self.assertIs(shell.source_helper_set_completion, completion)
                self.assertIs(
                    shell.source_slot_form,
                    completion.source_base_type_resolution.source_request_ir.source_form,
                )
                self.assertIs(
                    shell.source_envelope,
                    completion.source_base_type_resolution.source_request_ir
                    .source_form.source_envelope,
                )
                self.assertEqual(shell.declaration_kind, "var<typed>")
                self.assertEqual(shell.array_type_kind, "array_type")
                self.assertIs(
                    shell.base_type_ref,
                    completion.source_base_type_resolution.resolved_type_ref,
                )
                self.assertEqual(shell.base_type_ref.type_tag, "si32")
                self.assertIs(
                    shell.vector_length,
                    completion.source_vector_length_resolution.resolved_vector_length,
                )
                self.assertIs(
                    shell.vector_alignment,
                    completion.source_vector_alignment_resolution
                    .resolved_vector_alignment,
                )
                self.assertIs(
                    shell.unresolved_backend_uninit,
                    completion.unresolved_backend_uninit,
                )
                self.assertEqual(
                    shell.unresolved_backend_uninit.policy,
                    "deferred_backend_value",
                )
                self.assertEqual(shell.variable_token, "tmp")
                self.assertEqual(shell.slot_ordinal, 0)
                self.assertIs(
                    GenerationLoweringStage(
                        stage="array_initialization_declaration_shell_lowering",
                        output=shell,
                    ).output,
                    shell,
                )

    def test_exact_array_initialization_declaration_shell_rejects_invalid_sources(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()
        body_ir = self.selected_body_ir()
        implementation_without_ir = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_vector_alignment_resolutions=(
                completion.source_vector_alignment_resolution,
            ),
        )
        implementation_with_multiple = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            array_initialization_helper_set_completions=(completion, completion),
        )
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-SOURCE-UNSUPPORTED",
                "M72",
            ),
            (
                "type",
                object(),
                "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-SOURCE-UNSUPPORTED",
                "M72",
            ),
            (
                "missing_ir",
                implementation_without_ir,
                "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MISSING",
                "array_initialization_helper_set_completions",
            ),
            (
                "multiple_ir",
                implementation_with_multiple,
                "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_declaration_shell(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_initialization_declaration_shell_rejects_context_mismatch(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()

        result = lower_exact_array_initialization_declaration_shell(
            completion,
            GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("selected candidate context", result.diagnostics[0].message)

    def test_exact_array_initialization_declaration_shell_reports_provenance_mismatch(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()
        object.__setattr__(
            completion.source_vector_length_resolution,
            "candidate_id",
            "other-candidate",
        )

        result = lower_exact_array_initialization_declaration_shell(completion)

        self.assertFalse(result.is_ok)
        self.assertTrue(
            any(
                diagnostic.code
                == "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-PROVENANCE-MISMATCH"
                for diagnostic in result.diagnostics
            ),
            result.diagnostics,
        )

    def test_exact_array_initialization_declaration_shell_reports_malformed_shell(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()
        source_form = (
            completion.source_base_type_resolution.source_request_ir.source_form
        )
        object.__setattr__(source_form, "variable_token", "scratch")

        result = lower_exact_array_initialization_declaration_shell(completion)

        self.assertFalse(result.is_ok)
        self.assertTrue(
            any(
                diagnostic.code
                == "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-MALFORMED"
                for diagnostic in result.diagnostics
            ),
            result.diagnostics,
        )

    def test_exact_array_initialization_declaration_shell_rejects_backend_policy_mismatch(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()
        object.__setattr__(
            completion.unresolved_backend_uninit,
            "policy",
            "translated_backend_value",
        )

        result = lower_exact_array_initialization_declaration_shell(completion)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code=(
                "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-"
                "BACKEND-UNINIT-POLICY-MISMATCH"
            ),
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )
        self.assertIn("deferred_backend_value", result.diagnostics[0].message)

    def test_exact_array_initialization_declaration_shell_is_deterministic(
        self,
    ) -> None:
        first_source = self.exact_array_initialization_helper_set_completion()
        second_source = self.exact_array_initialization_helper_set_completion()

        first = lower_exact_array_initialization_declaration_shell(first_source)
        second = lower_exact_array_initialization_declaration_shell(second_source)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().key, second.unwrap().key)

    def test_exact_array_initialization_declaration_shell_uses_no_raw_or_external_state(
        self,
    ) -> None:
        completion = self.exact_array_initialization_helper_set_completion()
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = lower_exact_array_initialization_declaration_shell(
                    completion,
                )
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().declaration_kind, "var<typed>")
        self.assertEqual(
            result.unwrap().unresolved_backend_uninit.policy,
            "deferred_backend_value",
        )

    def test_exact_array_body_structural_sequence_lowers_m65_m73_sources(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell(
            selected_type_tag="si32",
        )
        envelope = shell.source_envelope
        sources = (
            (shell, None),
            (
                GenerationLoweringStage(
                    stage="array_initialization_declaration_shell_lowering",
                    output=shell,
                ),
                None,
            ),
            (envelope, shell),
            (
                GenerationLoweringStage(
                    stage="array_body_envelope_slot_assembly",
                    output=envelope,
                ),
                GenerationLoweringStage(
                    stage="array_initialization_declaration_shell_lowering",
                    output=shell,
                ),
            ),
            (
                LoweredImplementation(
                    candidate_id=shell.candidate_id,
                    status="lowered",
                    array_body_envelopes=(envelope,),
                    array_initialization_declaration_shells=(shell,),
                ),
                None,
            ),
        )

        for source, declaration_source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_array_body_structural_sequence(
                    source,
                    declaration_source,
                    GenerationContext(
                        selected_candidate_id=shell.candidate_id,
                        selected_type_tag=shell.selected_type_tag,
                    ),
                    selected_candidate_id=shell.candidate_id,
                    target_extension=shell.target_extension,
                    source_extension=shell.source_extension,
                    selected_type_tag=shell.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                sequence = result.unwrap()
                assert isinstance(sequence, ExactArrayBodyStructuralSequenceIr)
                self.assertIs(sequence.source_envelope, envelope)
                self.assertIs(sequence.declaration_shell, shell)
                self.assertEqual(
                    tuple(role.role_label for role in sequence.roles),
                    (
                        "first_slot_declaration_shell",
                        "opaque_predicate_init_shaped_slot",
                        "selected_body_envelope_slot",
                        "opaque_post_branch_store_call_shaped_slot",
                        "opaque_return_emission_shaped_slot",
                    ),
                )
                self.assertEqual(
                    tuple(role.role_ordinal for role in sequence.roles),
                    (0, 1, 2, 3, 4),
                )
                self.assertIs(sequence.roles[0].declaration_shell, shell)
                self.assertTrue(
                    all(role.declaration_shell is None for role in sequence.roles[1:])
                )
                self.assertIs(
                    sequence.roles[2].selected_body_envelope,
                    envelope.selected_body_slot.selected_body_envelope,
                )
                for index in (0, 1, 3, 4):
                    self.assertIs(sequence.roles[index].selected_body_envelope, None)
                for index, label in (
                    (1, "opaque_pre_branch_predicate_initialization"),
                    (3, "opaque_post_branch_store_call"),
                    (4, "opaque_post_branch_return_emission"),
                ):
                    self.assertEqual(
                        sequence.roles[index].opaque_source_text,
                        ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[label],
                    )
                self.assertIs(sequence.roles[0].opaque_source_text, None)
                self.assertIs(sequence.roles[2].opaque_source_text, None)

    def test_exact_array_body_structural_sequence_preserves_no_body_slot(
        self,
    ) -> None:
        envelope = self.no_selected_body_envelope("si8")
        assembled = assemble_exact_array_body_envelope(
            envelope,
            self.exact_array_body_skeleton_for_envelope(envelope),
        )
        self.assertTrue(assembled.is_ok, assembled.diagnostics)
        array_envelope = assembled.unwrap()
        shell = self.exact_array_initialization_declaration_shell(
            selected_type_tag="si8",
        )
        object.__setattr__(shell, "source_envelope", array_envelope)

        result = lower_exact_array_body_structural_sequence(array_envelope, shell)

        self.assertTrue(result.is_ok, result.diagnostics)
        sequence = result.unwrap()
        selected_body_envelope = sequence.roles[2].selected_body_envelope
        self.assertIsInstance(selected_body_envelope, NoSelectedBodyEnvelopeIr)
        assert isinstance(selected_body_envelope, NoSelectedBodyEnvelopeIr)
        self.assertEqual(selected_body_envelope.entries, ())
        self.assertTrue(
            all(
                role.selected_body_envelope is None
                for role in (*sequence.roles[:2], *sequence.roles[3:])
            )
        )

    def test_exact_array_body_structural_sequence_rejects_invalid_sources(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()
        body_ir = self.selected_body_ir()
        missing = LoweredImplementation(
            candidate_id=shell.candidate_id,
            status="lowered",
            array_body_envelopes=(shell.source_envelope,),
        )
        missing_envelope_with_shell = LoweredImplementation(
            candidate_id=shell.candidate_id,
            status="lowered",
            array_initialization_declaration_shells=(shell,),
        )
        duplicate = LoweredImplementation(
            candidate_id=shell.candidate_id,
            status="lowered",
            array_body_envelopes=(shell.source_envelope, shell.source_envelope),
            array_initialization_declaration_shells=(shell,),
        )
        duplicate_shell_with_envelope = LoweredImplementation(
            candidate_id=shell.candidate_id,
            status="lowered",
            array_body_envelopes=(shell.source_envelope,),
            array_initialization_declaration_shells=(shell, shell),
        )
        cases = (
            (
                "bad_stage",
                GenerationLoweringStage(stage="selected_body_ir_lowering", output=body_ir),
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-SOURCE-UNSUPPORTED",
                "M65",
            ),
            (
                "bad_type",
                object(),
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-SOURCE-UNSUPPORTED",
                "typed sources",
            ),
            (
                "missing_shell",
                shell.source_envelope,
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
                "M73",
            ),
            (
                "missing_container_ir",
                missing,
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
                "array_initialization_declaration_shells",
            ),
            (
                "missing_envelope_with_shell",
                missing_envelope_with_shell,
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
                "array_body_envelopes",
            ),
            (
                "duplicate_envelope_container_ir",
                duplicate,
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MULTIPLE",
                "exactly one",
            ),
            (
                "duplicate_shell_with_envelope",
                duplicate_shell_with_envelope,
                None,
                "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MULTIPLE",
                "array_initialization_declaration_shells",
            ),
        )

        for name, source, declaration_source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_array_body_structural_sequence(
                    source,
                    declaration_source,
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

    def test_exact_array_body_structural_sequence_preserves_shell_location_for_missing_envelope(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()
        implementation = LoweredImplementation(
            candidate_id=shell.candidate_id,
            status="lowered",
            array_initialization_declaration_shells=(shell,),
        )

        result = lower_exact_array_body_structural_sequence(implementation)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
            severity="error",
            path=shell.source_location.path.as_posix(),
            line=shell.source_location.line,
            column=shell.source_location.column,
        )
        self.assertIn("array_body_envelopes", result.diagnostics[0].message)

    def test_exact_array_body_structural_sequence_reports_context_mismatch(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()

        result = lower_exact_array_body_structural_sequence(
            shell,
            context=GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )

    def test_exact_array_body_structural_sequence_reports_provenance_mismatch(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()
        other_envelope = self.exact_array_body_envelope(selected_type_tag="si32")

        result = lower_exact_array_body_structural_sequence(other_envelope, shell)

        self.assertFalse(result.is_ok)
        self.assertTrue(
            any(
                diagnostic.code
                == "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-PROVENANCE-MISMATCH"
                for diagnostic in result.diagnostics
            ),
            result.diagnostics,
        )

    def test_exact_array_body_structural_sequence_reports_role_and_shape_issues(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()
        envelope = shell.source_envelope

        original_slots = envelope.slots
        object.__setattr__(
            envelope,
            "slots",
            (envelope.slots[1], envelope.slots[0], *envelope.slots[2:]),
        )
        result = lower_exact_array_body_structural_sequence(envelope, shell)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-ROLE-MISMATCH",
            severity="error",
        )

        object.__setattr__(envelope, "slots", original_slots[:-1])
        result = lower_exact_array_body_structural_sequence(envelope, shell)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-MALFORMED",
            severity="error",
        )

        object.__setattr__(envelope, "slots", original_slots)
        object.__setattr__(shell, "slot_ordinal", 1)
        result = lower_exact_array_body_structural_sequence(envelope, shell)
        self.assertFalse(result.is_ok)
        self.assertTrue(
            any(
                diagnostic.code
                == "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-MALFORMED"
                for diagnostic in result.diagnostics
            ),
            result.diagnostics,
        )

    def test_exact_array_body_structural_sequence_is_deterministic(
        self,
    ) -> None:
        first = self.exact_array_body_structural_sequence(selected_type_tag="si32")
        second = self.exact_array_body_structural_sequence(selected_type_tag="si32")

        self.assertEqual(first.key, second.key)

    def test_exact_array_body_structural_sequence_uses_no_raw_or_external_state(
        self,
    ) -> None:
        shell = self.exact_array_initialization_declaration_shell()
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_predicate_query = lowering_boundary.resolve_generation_predicate_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_predicate_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = lower_exact_array_body_structural_sequence(shell)
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            lowering_boundary.resolve_generation_predicate_query = (
                original_predicate_query
            )
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().roles[1].opaque_source_text,
            ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
                "opaque_pre_branch_predicate_initialization"
            ],
        )

    def test_exact_predicate_path_lowers_m74_sources(
        self,
    ) -> None:
        sequence = self.exact_array_body_structural_sequence(selected_type_tag="si16")
        sources = (
            sequence,
            GenerationLoweringStage(
                stage="array_body_structural_sequence_classification",
                output=sequence,
            ),
            LoweredImplementation(
                candidate_id=sequence.candidate_id,
                status="lowered",
                array_body_structural_sequences=(sequence,),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_predicate_path_structural_request(
                    source,
                    GenerationContext(
                        selected_candidate_id=sequence.candidate_id,
                        selected_type_tag=sequence.selected_type_tag,
                    ),
                    selected_candidate_id=sequence.candidate_id,
                    target_extension=sequence.target_extension,
                    source_extension=sequence.source_extension,
                    selected_type_tag=sequence.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                predicate_path = result.unwrap()
                assert isinstance(
                    predicate_path,
                    ExactPredicatePathStructuralRequestIr,
                )
                self.assertIs(predicate_path.source_sequence, sequence)
                self.assertEqual(predicate_path.predicate_init_slot_ordinal, 1)
                self.assertEqual(predicate_path.predicate_type_token_text, "svbool_t")
                self.assertEqual(predicate_path.predicate_token_text, "pg")
                self.assertEqual(
                    predicate_path.predicate_init_direct_intrinsic_token_text,
                    "svptrue_b8",
                )
                self.assertEqual(predicate_path.selected_update_slot_ordinal, 2)
                self.assertEqual(
                    predicate_path.selected_update_state,
                    "accepted_selected_update",
                )
                self.assertEqual(
                    predicate_path.selected_update_assignment_target_text,
                    "pg",
                )
                self.assertEqual(
                    predicate_path.selected_update_direct_intrinsic_token_text,
                    "svptrue_b16",
                )
                self.assertEqual(predicate_path.store_call_slot_ordinal, 3)
                self.assertEqual(
                    predicate_path.store_call_predicate_argument_text,
                    "pg",
                )
                self.assertIs(
                    predicate_path.selected_body_envelope,
                    sequence.roles[2].selected_body_envelope,
                )

    def test_exact_predicate_path_preserves_selected_update_and_no_update(
        self,
    ) -> None:
        cases = (
            ("si16", "svptrue_b16"),
            ("si32", "svptrue_b32"),
            ("si64", "svptrue_b64"),
        )

        for selected_type_tag, token_text in cases:
            with self.subTest(selected_type_tag=selected_type_tag):
                pipeline = self.exact_array_initialization_stage_pipeline(
                    selected_type_tag=selected_type_tag,
                )
                self.assertTrue(pipeline.is_ok, pipeline.diagnostics)
                predicate_path = pipeline.unwrap().predicate_path_structural_requests[0]

                self.assertEqual(
                    predicate_path.selected_update_state,
                    "accepted_selected_update",
                )
                self.assertEqual(
                    predicate_path.selected_update_direct_intrinsic_token_text,
                    token_text,
                )
                self.assertEqual(
                    predicate_path.predicate_token_text,
                    predicate_path.selected_update_assignment_target_text,
                )
                self.assertEqual(
                    predicate_path.predicate_token_text,
                    predicate_path.store_call_predicate_argument_text,
                )

        pipeline = self.exact_array_initialization_stage_pipeline("si8")
        self.assertTrue(pipeline.is_ok, pipeline.diagnostics)
        predicate_path = pipeline.unwrap().predicate_path_structural_requests[0]
        self.assertEqual(predicate_path.selected_update_state, "accepted_no_update")
        self.assertIsNone(predicate_path.selected_update_assignment_target_text)
        self.assertIsNone(predicate_path.selected_update_direct_intrinsic_token_text)
        self.assertIsInstance(
            predicate_path.selected_body_envelope,
            NoSelectedBodyEnvelopeIr,
        )
        self.assertEqual(predicate_path.predicate_token_text, "pg")
        self.assertEqual(predicate_path.store_call_predicate_argument_text, "pg")

    def test_lower_candidates_predicate_path_stage_follows_m74(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(skeleton,),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=(
                        self.vector_length_metadata_for_item(item),
                    ),
                    array_initialization_vector_alignment_metadata=(
                        self.vector_alignment_metadata_for_item(item),
                    ),
                ),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations_by_candidate_id[
            item.candidate_id
        ]
        self.assertEqual(len(implementation.array_body_structural_sequences), 1)
        self.assertEqual(len(implementation.predicate_path_structural_requests), 1)
        self.assertEqual(
            len(implementation.post_branch_intrinsic_call_site_structural_requests),
            1,
        )
        structural_sequence = implementation.array_body_structural_sequences[0]
        predicate_path = implementation.predicate_path_structural_requests[0]
        post_branch_call_site = (
            implementation.post_branch_intrinsic_call_site_structural_requests[0]
        )
        self.assertIs(predicate_path.source_sequence, structural_sequence)
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages[-4:]),
            (
                "array_body_structural_sequence_classification",
                "predicate_path_structural_request_lowering",
                "post_branch_intrinsic_call_site_structural_request_lowering",
                "return_emission_structural_request_lowering",
            ),
        )
        self.assertIs(implementation.generation_stages[-4].output, structural_sequence)
        self.assertIs(implementation.generation_stages[-3].output, predicate_path)
        self.assertIs(
            implementation.generation_stages[-2].output,
            post_branch_call_site,
        )
        self.assertEqual(
            implementation.generation_stages[-5].stage,
            "array_initialization_declaration_shell_lowering",
        )

    def test_exact_predicate_path_reports_source_and_context_diagnostics(
        self,
    ) -> None:
        sequence = self.exact_array_body_structural_sequence()
        body_ir = self.selected_body_ir()
        duplicate = LoweredImplementation(
            candidate_id=sequence.candidate_id,
            status="lowered",
            array_body_structural_sequences=(sequence, sequence),
        )
        missing = LoweredImplementation(
            candidate_id=sequence.candidate_id,
            status="lowered",
        )
        cases = (
            (
                "bad_stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-PREDICATE-PATH-SOURCE-UNSUPPORTED",
                "M74",
            ),
            (
                "bad_type",
                object(),
                "TSL-LOWER-PREDICATE-PATH-SOURCE-UNSUPPORTED",
                "M74",
            ),
            (
                "missing",
                missing,
                "TSL-LOWER-PREDICATE-PATH-IR-MISSING",
                "array_body_structural_sequences",
            ),
            (
                "duplicate",
                duplicate,
                "TSL-LOWER-PREDICATE-PATH-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_predicate_path_structural_request(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

        result = lower_exact_predicate_path_structural_request(
            sequence,
            context=GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )

    def test_exact_predicate_path_reports_shape_token_and_provenance_diagnostics(
        self,
    ) -> None:
        sequence = self.exact_array_body_structural_sequence()

        init_malformed = self.exact_array_body_structural_sequence()
        object.__setattr__(
            init_malformed.roles[1],
            "opaque_source_text",
            "svbool_t p0 = intrin<svptrue_b8>();",
        )
        result = lower_exact_predicate_path_structural_request(init_malformed)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-MALFORMED",
            severity="error",
        )

        store_token_mismatch = self.exact_array_body_structural_sequence()
        store_role = store_token_mismatch.roles[3]
        store_slot = store_role.envelope_slot
        assert isinstance(store_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        object.__setattr__(
            store_slot,
            "opaque_source_text",
            "intrin<svst1>(p0, tmp.data(), a);",
        )
        object.__setattr__(
            store_role,
            "opaque_source_text",
            "intrin<svst1>(p0, tmp.data(), a);",
        )
        result = lower_exact_predicate_path_structural_request(
            store_token_mismatch,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-TOKEN-MISMATCH",
            severity="error",
        )

        store_malformed = self.exact_array_body_structural_sequence()
        store_role = store_malformed.roles[3]
        store_slot = store_role.envelope_slot
        assert isinstance(store_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        malformed_store_text = "intrin<svst1>(pg, tmp.data());"
        object.__setattr__(
            store_slot,
            "opaque_source_text",
            malformed_store_text,
        )
        object.__setattr__(
            store_role,
            "opaque_source_text",
            malformed_store_text,
        )
        result = lower_exact_predicate_path_structural_request(
            store_malformed,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-MALFORMED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=110,
            column=15,
        )

        selected_target_mismatch = self.exact_array_body_structural_sequence()
        selected_envelope = selected_target_mismatch.roles[2].selected_body_envelope
        assert isinstance(selected_envelope, SelectedBodyEnvelopeIr)
        object.__setattr__(
            selected_envelope.entries[0],
            "assignment_target_text",
            "p0",
        )
        result = lower_exact_predicate_path_structural_request(
            selected_target_mismatch,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-TOKEN-MISMATCH",
            severity="error",
        )

        provenance_mismatch = self.exact_array_body_structural_sequence()
        selected_envelope = provenance_mismatch.roles[2].selected_body_envelope
        assert isinstance(selected_envelope, SelectedBodyEnvelopeIr)
        object.__setattr__(
            selected_envelope.entries[0],
            "selected_type_tag",
            "other",
        )
        result = lower_exact_predicate_path_structural_request(provenance_mismatch)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-PROVENANCE-MISMATCH",
            severity="error",
        )

        m62_provenance_mismatch = self.exact_array_body_structural_sequence()
        selected_envelope = m62_provenance_mismatch.roles[2].selected_body_envelope
        assert isinstance(selected_envelope, SelectedBodyEnvelopeIr)
        object.__setattr__(
            selected_envelope.entries[0].source_body_ir,
            "selected_type_tag",
            "other",
        )
        result = lower_exact_predicate_path_structural_request(
            m62_provenance_mismatch,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-PROVENANCE-MISMATCH",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )

        object.__setattr__(sequence, "roles", (sequence.roles[0], *sequence.roles[2:]))
        result = lower_exact_predicate_path_structural_request(sequence)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-PREDICATE-PATH-MALFORMED",
            severity="error",
        )

    def test_exact_predicate_path_is_deterministic_for_reordered_pipeline_inputs(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        implementations = tuple(
            implementation
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag
            in ("si16", "si32")
        )
        skeletons = tuple(
            self.exact_array_body_skeleton_for_envelope(
                implementation.selected_body_envelopes[0],
            )
            for implementation in implementations
        )
        length_metadata = tuple(
            self.vector_length_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
            )
            for implementation in implementations
        )
        alignment_metadata = tuple(
            self.vector_alignment_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
            )
            for implementation in implementations
        )

        first = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=skeletons,
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=length_metadata,
                    array_initialization_vector_alignment_metadata=alignment_metadata,
                ),
            ),
        )
        second = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=tuple(reversed(skeletons)),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=tuple(
                        reversed(length_metadata),
                    ),
                    array_initialization_vector_alignment_metadata=tuple(
                        reversed(alignment_metadata),
                    ),
                ),
            ),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            {
                implementation.candidate_id: tuple(
                    request.key
                    for request in implementation.predicate_path_structural_requests
                )
                for implementation in first.unwrap().implementations
            },
            {
                implementation.candidate_id: tuple(
                    request.key
                    for request in implementation.predicate_path_structural_requests
                )
                for implementation in second.unwrap().implementations
            },
        )

    def test_exact_predicate_path_uses_no_raw_or_external_state(
        self,
    ) -> None:
        sequence = self.exact_array_body_structural_sequence()
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_predicate_query = lowering_boundary.resolve_generation_predicate_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_predicate_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = lower_exact_predicate_path_structural_request(sequence)
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            lowering_boundary.resolve_generation_predicate_query = (
                original_predicate_query
            )
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().predicate_token_text, "pg")
        self.assertEqual(
            result.unwrap().selected_update_direct_intrinsic_token_text,
            "svptrue_b16",
        )

    def test_lower_candidates_predicate_path_uses_no_raw_or_external_state(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si16")
        request = LoweringRequest(
            array_body_envelope_skeletons=(
                self.exact_array_body_skeleton_for_envelope(envelope),
            ),
            generation_context=GenerationContext(
                array_initialization_vector_length_metadata=(
                    self.vector_length_metadata_for_item(item),
                ),
                array_initialization_vector_alignment_metadata=(
                    self.vector_alignment_metadata_for_item(item),
                ),
            ),
        )
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_predicate_query = lowering_boundary.resolve_generation_predicate_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_predicate_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = lower_candidates(selection, request)
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            lowering_boundary.resolve_generation_predicate_query = (
                original_predicate_query
            )
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations_by_candidate_id[
            item.candidate_id
        ]
        self.assertEqual(len(implementation.predicate_path_structural_requests), 1)
        self.assertEqual(
            implementation.predicate_path_structural_requests[0].predicate_token_text,
            "pg",
        )

    def test_exact_post_branch_call_site_lowers_m75_sources(
        self,
    ) -> None:
        predicate_path = self.exact_predicate_path_structural_request(
            selected_type_tag="si16",
        )
        sources = (
            predicate_path,
            GenerationLoweringStage(
                stage="predicate_path_structural_request_lowering",
                output=predicate_path,
            ),
            LoweredImplementation(
                candidate_id=predicate_path.candidate_id,
                status="lowered",
                predicate_path_structural_requests=(predicate_path,),
            ),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = (
                    lower_exact_post_branch_intrinsic_call_site_structural_request(
                        source,
                        GenerationContext(
                            selected_candidate_id=predicate_path.candidate_id,
                            selected_type_tag=predicate_path.selected_type_tag,
                        ),
                        selected_candidate_id=predicate_path.candidate_id,
                        target_extension=predicate_path.target_extension,
                        source_extension=predicate_path.source_extension,
                        selected_type_tag=predicate_path.selected_type_tag,
                    )
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                call_site = result.unwrap()
                assert isinstance(
                    call_site,
                    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
                )
                self.assertIs(call_site.source_predicate_path, predicate_path)
                self.assertIs(call_site.source_sequence, predicate_path.source_sequence)
                self.assertEqual(call_site.post_branch_slot_ordinal, 3)
                self.assertEqual(
                    call_site.post_branch_role_label,
                    "opaque_post_branch_store_call_shaped_slot",
                )
                self.assertEqual(call_site.call_head_token_text, "intrin")
                self.assertEqual(call_site.unresolved_intrinsic_token_text, "svst1")
                self.assertEqual(call_site.predicate_argument_ordinal, 0)
                self.assertEqual(call_site.predicate_argument_token_text, "pg")
                self.assertEqual(call_site.predicate_argument_source_slot_ordinal, 3)
                self.assertEqual(
                    call_site.predicate_argument_source_token_text,
                    predicate_path.store_call_predicate_argument_text,
                )
                self.assertEqual(call_site.member_access_argument_ordinal, 1)
                self.assertEqual(call_site.member_access_argument_text, "tmp.data()")
                self.assertEqual(call_site.member_access_base_token_text, "tmp")
                self.assertEqual(call_site.member_access_member_token_text, "data")
                self.assertEqual(
                    call_site.member_access_source_variable_token_text,
                    predicate_path.source_sequence.declaration_shell.variable_token,
                )
                self.assertEqual(call_site.source_operand_argument_ordinal, 2)
                self.assertEqual(call_site.source_operand_argument_token_text, "a")
                self.assertEqual(call_site.candidate_id, predicate_path.candidate_id)
                self.assertEqual(
                    call_site.originating_branch_chain_id,
                    predicate_path.originating_branch_chain_id,
                )
                self.assertFalse(hasattr(call_site, "store_semantics"))
                self.assertFalse(hasattr(call_site, "backend_translation"))
                self.assertFalse(hasattr(call_site, "renderer_value"))

    def test_lower_candidates_post_branch_call_site_stage_follows_m75(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(skeleton,),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=(
                        self.vector_length_metadata_for_item(item),
                    ),
                    array_initialization_vector_alignment_metadata=(
                        self.vector_alignment_metadata_for_item(item),
                    ),
                ),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations_by_candidate_id[
            item.candidate_id
        ]
        self.assertEqual(len(implementation.predicate_path_structural_requests), 1)
        self.assertEqual(
            len(implementation.post_branch_intrinsic_call_site_structural_requests),
            1,
        )
        predicate_path = implementation.predicate_path_structural_requests[0]
        call_site = (
            implementation.post_branch_intrinsic_call_site_structural_requests[0]
        )
        self.assertIs(call_site.source_predicate_path, predicate_path)
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages[-4:]),
            (
                "array_body_structural_sequence_classification",
                "predicate_path_structural_request_lowering",
                "post_branch_intrinsic_call_site_structural_request_lowering",
                "return_emission_structural_request_lowering",
            ),
        )
        self.assertIs(implementation.generation_stages[-3].output, predicate_path)
        self.assertIs(implementation.generation_stages[-2].output, call_site)
        self.assertEqual(call_site.predicate_argument_token_text, "pg")
        self.assertEqual(call_site.member_access_argument_text, "tmp.data()")
        self.assertEqual(call_site.source_operand_argument_token_text, "a")

    def test_exact_post_branch_call_site_reports_source_and_context_diagnostics(
        self,
    ) -> None:
        predicate_path = self.exact_predicate_path_structural_request()
        body_ir = self.selected_body_ir()
        duplicate = LoweredImplementation(
            candidate_id=predicate_path.candidate_id,
            status="lowered",
            predicate_path_structural_requests=(predicate_path, predicate_path),
        )
        missing = LoweredImplementation(
            candidate_id=predicate_path.candidate_id,
            status="lowered",
        )
        cases = (
            (
                "bad_stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-UNSUPPORTED",
                "M75",
            ),
            (
                "bad_type",
                object(),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-UNSUPPORTED",
                "M75",
            ),
            (
                "missing",
                missing,
                "TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MISSING",
                "predicate_path_structural_requests",
            ),
            (
                "duplicate",
                duplicate,
                "TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = (
                    lower_exact_post_branch_intrinsic_call_site_structural_request(
                        source,
                    )
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

        result = lower_exact_post_branch_intrinsic_call_site_structural_request(
            predicate_path,
            context=GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-POST-BRANCH-CALL-SITE-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
        )

    def test_exact_post_branch_call_site_reports_shape_token_and_provenance_diagnostics(
        self,
    ) -> None:
        def with_store_text(text: str) -> ExactPredicatePathStructuralRequestIr:
            predicate_path = self.exact_predicate_path_structural_request()
            store_role = predicate_path.source_sequence.roles[3]
            store_slot = store_role.envelope_slot
            assert isinstance(store_slot, ExactArrayBodyEnvelopeOpaqueSlot)
            object.__setattr__(store_slot, "opaque_source_text", text)
            object.__setattr__(store_role, "opaque_source_text", text)
            return predicate_path

        cases = (
            (
                "shape_unsupported",
                with_store_text("emit_return(tmp);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-SHAPE-UNSUPPORTED",
            ),
            (
                "malformed",
                with_store_text("intrin<svst1>(pg, tmp.data(), a)"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-MALFORMED",
            ),
            (
                "call_head",
                with_store_text("store<svst1>(pg, tmp.data(), a);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-CALL-HEAD-MISMATCH",
            ),
            (
                "intrinsic",
                with_store_text("intrin<other>(pg, tmp.data(), a);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-INTRINSIC-TOKEN-MISMATCH",
            ),
            (
                "argument_count",
                with_store_text("intrin<svst1>(pg, tmp.data());"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-ARGUMENT-COUNT-MISMATCH",
            ),
            (
                "predicate_argument",
                with_store_text("intrin<svst1>(p0, tmp.data(), a);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-PREDICATE-ARGUMENT-MISMATCH",
            ),
            (
                "member_access",
                with_store_text("intrin<svst1>(pg, tmp.ptr(), a);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-MEMBER-ACCESS-UNSUPPORTED",
            ),
            (
                "source_operand",
                with_store_text("intrin<svst1>(pg, tmp.data(), b);"),
                "TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-OPERAND-UNSUPPORTED",
            ),
        )

        for name, predicate_path, code in cases:
            with self.subTest(name=name):
                result = (
                    lower_exact_post_branch_intrinsic_call_site_structural_request(
                        predicate_path,
                    )
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=110,
                    column=15,
                )

        provenance_mismatch = self.exact_predicate_path_structural_request()
        store_role = provenance_mismatch.source_sequence.roles[3]
        object.__setattr__(
            store_role,
            "opaque_source_text",
            "intrin<svst1>(pg, tmp.data(), a);",
        )
        store_slot = store_role.envelope_slot
        assert isinstance(store_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        object.__setattr__(
            store_slot,
            "opaque_source_text",
            "intrin<svst1>(pg, tmp.data(), b);",
        )
        result = lower_exact_post_branch_intrinsic_call_site_structural_request(
            provenance_mismatch,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-POST-BRANCH-CALL-SITE-PROVENANCE-MISMATCH",
            severity="error",
        )

        missing_sequence = self.exact_predicate_path_structural_request()
        object.__setattr__(
            missing_sequence.source_sequence,
            "roles",
            missing_sequence.source_sequence.roles[:3],
        )
        result = lower_exact_post_branch_intrinsic_call_site_structural_request(
            missing_sequence,
        )
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-POST-BRANCH-CALL-SITE-SEQUENCE-MISSING",
            severity="error",
        )

    def test_exact_post_branch_call_site_is_deterministic_for_reordered_inputs(
        self,
    ) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        baseline = lower_candidates(selection)
        self.assertTrue(baseline.is_ok, baseline.diagnostics)
        implementations = tuple(
            implementation
            for implementation in baseline.unwrap().implementations
            if implementation.selected_body_envelopes
            and implementation.selected_body_envelopes[0].selected_type_tag
            in ("si16", "si32")
        )
        skeletons = tuple(
            self.exact_array_body_skeleton_for_envelope(
                implementation.selected_body_envelopes[0],
            )
            for implementation in implementations
        )
        length_metadata = tuple(
            self.vector_length_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
            )
            for implementation in implementations
        )
        alignment_metadata = tuple(
            self.vector_alignment_metadata(
                candidate_id=implementation.candidate_id,
                target_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].target_extension,
                source_extension=selection.candidates_by_id[
                    implementation.candidate_id
                ].source_extension,
                selected_type_tag=selection.candidates_by_id[
                    implementation.candidate_id
                ].type_tag,
            )
            for implementation in implementations
        )

        first = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=skeletons,
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=length_metadata,
                    array_initialization_vector_alignment_metadata=alignment_metadata,
                ),
            ),
        )
        second = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=tuple(reversed(skeletons)),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=tuple(
                        reversed(length_metadata),
                    ),
                    array_initialization_vector_alignment_metadata=tuple(
                        reversed(alignment_metadata),
                    ),
                ),
            ),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)

        def call_site_keys(plan) -> dict[str, tuple[tuple[object, ...], ...]]:
            return {
                implementation.candidate_id: tuple(
                    request.key
                    for request in (
                        implementation.post_branch_intrinsic_call_site_structural_requests
                    )
                )
                for implementation in plan.unwrap().implementations
            }

        self.assertEqual(
            call_site_keys(first),
            call_site_keys(second),
        )

    def test_exact_post_branch_call_site_uses_no_raw_or_external_state(
        self,
    ) -> None:
        predicate_path = self.exact_predicate_path_structural_request()
        original_type_query = lowering_boundary.resolve_generation_type_query
        original_value_query = lowering_boundary.resolve_generation_value_query
        original_predicate_query = lowering_boundary.resolve_generation_predicate_query
        original_open = builtins.open
        original_cpu_count = os.cpu_count
        original_processor = platform.processor

        def fail_on_raw_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("raw helper evaluator was called")

        def fail_on_file_read(*args: object, **kwargs: object) -> object:
            raise AssertionError("file/catalog/tsldata/backend map read was called")

        def fail_on_cpu_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("host CPU query was called")

        lowering_boundary.resolve_generation_type_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_value_query = fail_on_raw_query  # type: ignore[assignment]
        lowering_boundary.resolve_generation_predicate_query = fail_on_raw_query  # type: ignore[assignment]
        builtins.open = fail_on_file_read  # type: ignore[assignment]
        os.cpu_count = fail_on_cpu_query  # type: ignore[assignment]
        platform.processor = fail_on_cpu_query  # type: ignore[assignment]
        try:
            with (
                mock.patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError(
                        "file/catalog/tsldata/backend map read was called"
                    ),
                ),
            ):
                result = (
                    lower_exact_post_branch_intrinsic_call_site_structural_request(
                        predicate_path,
                    )
                )
        finally:
            lowering_boundary.resolve_generation_type_query = original_type_query
            lowering_boundary.resolve_generation_value_query = original_value_query
            lowering_boundary.resolve_generation_predicate_query = (
                original_predicate_query
            )
            builtins.open = original_open
            os.cpu_count = original_cpu_count
            platform.processor = original_processor

        self.assertTrue(result.is_ok, result.diagnostics)
        call_site = result.unwrap()
        self.assertEqual(call_site.unresolved_intrinsic_token_text, "svst1")
        self.assertEqual(call_site.member_access_argument_text, "tmp.data()")

    def test_m87_exact_return_emission_lowers_m76_sources(self) -> None:
        call_site = self.exact_post_branch_intrinsic_call_site_structural_request(
            selected_type_tag="si16",
        )

        class M76OnlyLoweredImplementationSource:
            def __init__(
                self,
                call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
            ) -> None:
                self.post_branch_intrinsic_call_site_structural_requests = (
                    call_site,
                )

        sources = (
            call_site,
            GenerationLoweringStage(
                stage="post_branch_intrinsic_call_site_structural_request_lowering",
                output=call_site,
            ),
            LoweredImplementation(
                candidate_id=call_site.candidate_id,
                status="lowered",
                post_branch_intrinsic_call_site_structural_requests=(call_site,),
            ),
            M76OnlyLoweredImplementationSource(call_site),
        )

        for source in sources:
            with self.subTest(source=type(source).__name__):
                result = lower_exact_return_emission_structural_request(
                    source,
                    GenerationContext(
                        selected_candidate_id=call_site.candidate_id,
                        selected_type_tag=call_site.selected_type_tag,
                    ),
                    selected_candidate_id=call_site.candidate_id,
                    target_extension=call_site.target_extension,
                    source_extension=call_site.source_extension,
                    selected_type_tag=call_site.selected_type_tag,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                request = result.unwrap()
                self.assertIs(request.source_post_branch_call_site, call_site)
                self.assertIs(request.source_sequence, call_site.source_sequence)
                self.assertEqual(
                    request.return_role_label,
                    "opaque_return_emission_shaped_slot",
                )
                self.assertEqual(request.return_slot_ordinal, 4)
                self.assertEqual(request.return_source_location.line, 111)
                self.assertEqual(request.original_return_source_text, " emit_return(tmp) ;")
                self.assertEqual(request.emit_return_token_text, "emit_return")
                self.assertEqual(request.returned_token_text, "tmp")
                self.assertEqual(request.declaration_variable_token_text, "tmp")
                self.assertEqual(request.candidate_id, call_site.candidate_id)
                self.assertEqual(request.target_extension, call_site.target_extension)
                self.assertEqual(
                    request.originating_branch_chain_id,
                    call_site.originating_branch_chain_id,
                )
                self.assertFalse(hasattr(request, "return_semantics"))
                self.assertFalse(hasattr(request, "backend_translation"))
                self.assertFalse(hasattr(request, "renderer_value"))

    def test_m87_return_emission_reports_source_and_context_diagnostics(self) -> None:
        call_site = self.exact_post_branch_intrinsic_call_site_structural_request()
        duplicate = LoweredImplementation(
            candidate_id=call_site.candidate_id,
            status="lowered",
            post_branch_intrinsic_call_site_structural_requests=(call_site, call_site),
        )
        missing = LoweredImplementation(
            candidate_id=call_site.candidate_id,
            status="lowered",
        )
        cases = (
            (
                "bad_stage",
                GenerationLoweringStage(
                    stage="predicate_path_structural_request_lowering",
                    output=call_site.source_predicate_path,
                ),
                "TSL-LOWER-RETURN-EMISSION-SOURCE-UNSUPPORTED",
                "M76",
            ),
            (
                "bad_type",
                object(),
                "TSL-LOWER-RETURN-EMISSION-SOURCE-UNSUPPORTED",
                "M76",
            ),
            (
                "missing",
                missing,
                "TSL-LOWER-RETURN-EMISSION-IR-MISSING",
                "post_branch_intrinsic_call_site_structural_requests",
            ),
            (
                "duplicate",
                duplicate,
                "TSL-LOWER-RETURN-EMISSION-IR-MULTIPLE",
                "exactly one",
            ),
        )

        for name, source, code, message in cases:
            with self.subTest(name=name):
                result = lower_exact_return_emission_structural_request(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )
                self.assertIn(message, result.diagnostics[0].message)

        result = lower_exact_return_emission_structural_request(
            call_site,
            context=GenerationContext(selected_candidate_id="other-candidate"),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-RETURN-EMISSION-CONTEXT-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=110,
        )

    def test_m87_return_emission_reports_shape_token_and_provenance_diagnostics(
        self,
    ) -> None:
        def with_return_text(
            text: str,
        ) -> ExactPostBranchIntrinsicCallSiteStructuralRequestIr:
            call_site = self.exact_post_branch_intrinsic_call_site_structural_request()
            return_role = call_site.source_sequence.roles[4]
            return_slot = return_role.envelope_slot
            assert isinstance(return_slot, ExactArrayBodyEnvelopeOpaqueSlot)
            object.__setattr__(return_slot, "opaque_source_text", text)
            object.__setattr__(return_role, "opaque_source_text", text)
            return call_site

        cases = (
            (
                "missing_semicolon",
                with_return_text("emit_return(tmp)"),
                "TSL-LOWER-RETURN-EMISSION-MALFORMED",
            ),
            (
                "extra_argument",
                with_return_text("emit_return(tmp, other);"),
                "TSL-LOWER-RETURN-EMISSION-MALFORMED",
            ),
            (
                "expression",
                with_return_text("emit_return(tmp + other);"),
                "TSL-LOWER-RETURN-EMISSION-MALFORMED",
            ),
            (
                "member_access",
                with_return_text("emit_return(tmp.data());"),
                "TSL-LOWER-RETURN-EMISSION-MALFORMED",
            ),
            (
                "wrong_token",
                with_return_text("emit_return(other);"),
                "TSL-LOWER-RETURN-EMISSION-RETURNED-TOKEN-MISMATCH",
            ),
        )

        for name, call_site, code in cases:
            with self.subTest(name=name):
                result = lower_exact_return_emission_structural_request(call_site)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=111,
                    column=15,
                )

        missing_slot = self.exact_post_branch_intrinsic_call_site_structural_request()
        object.__setattr__(
            missing_slot.source_sequence,
            "roles",
            missing_slot.source_sequence.roles[:4],
        )
        result = lower_exact_return_emission_structural_request(missing_slot)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-RETURN-EMISSION-SLOT-MISSING",
            severity="error",
        )

        wrong_role = self.exact_post_branch_intrinsic_call_site_structural_request()
        object.__setattr__(
            wrong_role.source_sequence.roles[4],
            "role_label",
            "opaque_post_branch_store_call_shaped_slot",
        )
        result = lower_exact_return_emission_structural_request(wrong_role)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-RETURN-EMISSION-PROVENANCE-MISMATCH",
            severity="error",
        )

        provenance_mismatch = (
            self.exact_post_branch_intrinsic_call_site_structural_request()
        )
        return_role = provenance_mismatch.source_sequence.roles[4]
        return_slot = return_role.envelope_slot
        assert isinstance(return_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        object.__setattr__(return_role, "opaque_source_text", "emit_return(tmp);")
        object.__setattr__(return_slot, "opaque_source_text", "emit_return(other);")
        result = lower_exact_return_emission_structural_request(provenance_mismatch)
        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-RETURN-EMISSION-PROVENANCE-MISMATCH",
            severity="error",
        )

    def test_m87_return_emission_stage_follows_post_branch_call_site(self) -> None:
        selection = self.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = self.size_byte_branch_chain_item_and_envelope("si32")
        skeleton = self.exact_array_body_skeleton_for_envelope(envelope)

        result = lower_candidates(
            selection,
            LoweringRequest(
                array_body_envelope_skeletons=(skeleton,),
                generation_context=GenerationContext(
                    array_initialization_vector_length_metadata=(
                        self.vector_length_metadata_for_item(item),
                    ),
                    array_initialization_vector_alignment_metadata=(
                        self.vector_alignment_metadata_for_item(item),
                    ),
                ),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        plan = result.unwrap()
        implementation = plan.implementations_by_candidate_id[item.candidate_id]
        self.assertEqual(len(implementation.return_emission_structural_requests), 1)
        call_site = (
            implementation.post_branch_intrinsic_call_site_structural_requests[0]
        )
        return_emission = implementation.return_emission_structural_requests[0]
        self.assertIs(return_emission.source_post_branch_call_site, call_site)
        self.assertEqual(
            tuple(stage.stage for stage in implementation.generation_stages[-4:]),
            (
                "array_body_structural_sequence_classification",
                "predicate_path_structural_request_lowering",
                "post_branch_intrinsic_call_site_structural_request_lowering",
                "return_emission_structural_request_lowering",
            ),
        )
        self.assertIs(implementation.generation_stages[-2].output, call_site)
        self.assertIs(implementation.generation_stages[-1].output, return_emission)
        implementations_with_return = tuple(
            lowered.candidate_id
            for lowered in plan.implementations
            if lowered.return_emission_structural_requests
        )
        self.assertEqual(implementations_with_return, (item.candidate_id,))

    def test_m87_exact_array_body_pipeline_snapshot_preserves_return_identity(
        self,
    ) -> None:
        pipeline = self.exact_array_initialization_stage_pipeline("si32")

        self.assertTrue(pipeline.is_ok, pipeline.diagnostics)
        result = pipeline.unwrap()
        self.assertEqual(len(result.return_emission_structural_requests), 1)
        return_emission = result.return_emission_structural_requests[0]
        self.assertIs(result.stages[-1].output, return_emission)
        snapshot = result.pipeline_snapshot
        self.assertEqual(
            tuple(step.stage_name for step in snapshot.steps[-2:]),
            (
                "post_branch_intrinsic_call_site_structural_request_lowering",
                "return_emission_structural_request_lowering",
            ),
        )
        self.assertIs(snapshot.steps[-1].stage, result.stages[-1])
        self.assertEqual(
            snapshot.steps[-1].produced_fact.kind,
            "return_emission_structural_request",
        )
        self.assertIs(snapshot.steps[-1].produced_fact.value, return_emission)
        self.assertEqual(snapshot.steps[-1].produced_fact.key, return_emission.key)
        self.assertEqual(
            snapshot.steps[-1].depends_on,
            (
                "array_body_structural_sequence",
                "post_branch_intrinsic_call_site_structural_request",
            ),
        )

    def test_m87_return_emission_module_import_boundary(self) -> None:
        forbidden_modules = (
            "tslgen.lowering.boundary",
            "tslgen.lowering",
            "tslgen.backends",
            "tslgen.rendering",
        )
        imported_forbidden: list[str] = []
        tree = ast.parse(inspect.getsource(lowering_return_emission))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_forbidden.extend(
                    alias.name
                    for alias in node.names
                    if alias.name in forbidden_modules
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_modules:
                    imported_forbidden.append(node.module)
                if node.level and node.module in (None, "", "boundary"):
                    imported_forbidden.extend(
                        alias.name
                        for alias in node.names
                        if node.module == "boundary" or alias.name == "boundary"
                    )
        self.assertEqual(imported_forbidden, [])
        self.assertIs(
            lowering_boundary.lower_exact_return_emission_structural_request,
            lowering_return_emission.lower_exact_return_emission_structural_request,
        )
        self.assertIs(
            lower_exact_return_emission_structural_request,
            lowering_return_emission.lower_exact_return_emission_structural_request,
        )

    def test_exact_array_initialization_slot_form_api_uses_envelope_slot_only(
        self,
    ) -> None:
        parameters = inspect.signature(
            lower_exact_array_initialization_slot_form
        ).parameters

        self.assertNotIn("slot", parameters)

    def test_exact_array_initialization_slot_form_rejects_missing_slot(
        self,
    ) -> None:
        envelope = self.selected_body_envelope()
        implementation = LoweredImplementation(
            candidate_id="candidate-1",
            status="lowered",
            selected_body_envelopes=(envelope,),
        )

        result = lower_exact_array_initialization_slot_form(implementation)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-SLOT-MISSING",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )
        self.assertIn("array_body_envelopes", result.diagnostics[0].message)

    def test_exact_array_initialization_slot_form_rejects_wrong_label_or_ordinal(
        self,
    ) -> None:
        cases = (
            ("wrong_label", 110),
            ("wrong_ordinal", 105),
        )

        for name, line in cases:
            with self.subTest(name=name):
                array_envelope = self.exact_array_body_envelope()
                if name == "wrong_label":
                    slot = array_envelope.slots[3]
                else:
                    slot_zero = array_envelope.slots[0]
                    assert isinstance(slot_zero, ExactArrayBodyEnvelopeOpaqueSlot)
                    slot = replace(slot_zero, ordinal=1)
                object.__setattr__(
                    array_envelope,
                    "slots",
                    (slot, *array_envelope.slots[1:]),
                )

                result = lower_exact_array_initialization_slot_form(array_envelope)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-ARRAY-INIT-SLOT-WRONG-POSITION",
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=line,
                    column=15,
                )
                self.assertIn("ordinal 0", result.diagnostics[0].message)

    def test_exact_array_initialization_slot_form_rejects_malformed_text(
        self,
    ) -> None:
        envelope = self.selected_body_envelope()
        skeleton = self.exact_array_body_skeleton()
        malformed_slot = replace(
            skeleton.slots[0],
            opaque_source_text="var<typed>(tmp)",
        )
        skeleton = replace(skeleton, slots=(malformed_slot, *skeleton.slots[1:]))
        assembled = assemble_exact_array_body_envelope(envelope, skeleton)
        self.assertTrue(assembled.is_ok, assembled.diagnostics)

        result = lower_exact_array_initialization_slot_form(assembled.unwrap())

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("array.tsl:105", result.diagnostics[0].message)

    def test_exact_array_initialization_slot_form_rejects_helper_shape(
        self,
    ) -> None:
        envelope = self.selected_body_envelope()
        skeleton = self.exact_array_body_skeleton()
        helper_text = ARRAY_BODY_OPAQUE_TEXT_BY_LABEL[
            "opaque_pre_branch_array_initialization"
        ].replace(
            "value<generation>(vector::length)",
            "value<generation>(vector::lanes)",
        )
        helper_slot = replace(skeleton.slots[0], opaque_source_text=helper_text)
        skeleton = replace(skeleton, slots=(helper_slot, *skeleton.slots[1:]))
        assembled = assemble_exact_array_body_envelope(envelope, skeleton)
        self.assertTrue(assembled.is_ok, assembled.diagnostics)

        result = lower_exact_array_initialization_slot_form(assembled.unwrap())

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-SLOT-HELPER-UNSUPPORTED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("unresolved helper leaves", result.diagnostics[0].message)

    def test_exact_array_initialization_slot_form_rejects_unsupported_source(
        self,
    ) -> None:
        body_ir = self.selected_body_ir()
        cases = (
            (
                "stage",
                GenerationLoweringStage(
                    stage="selected_body_ir_lowering",
                    output=body_ir,
                ),
                "array.tsl",
                107,
                15,
            ),
            ("type", object(), None, None, None),
        )

        for name, source, path, line, column in cases:
            with self.subTest(name=name):
                result = lower_exact_array_initialization_slot_form(source)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-ARRAY-INIT-SLOT-SOURCE-UNSUPPORTED",
                    severity="error",
                    path=path,
                    line=line,
                    column=column,
                )
                self.assertIn("M65", result.diagnostics[0].message)

    def test_exact_array_initialization_slot_form_reports_provenance_mismatch(
        self,
    ) -> None:
        array_envelope = self.exact_array_body_envelope()
        slot_zero = array_envelope.slots[0]
        assert isinstance(slot_zero, ExactArrayBodyEnvelopeOpaqueSlot)
        mismatched_slot = replace(slot_zero, candidate_id="other-candidate")
        object.__setattr__(
            array_envelope,
            "slots",
            (mismatched_slot, *array_envelope.slots[1:]),
        )

        result = lower_exact_array_initialization_slot_form(array_envelope)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-INIT-SLOT-PROVENANCE-MISMATCH",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("provenance", result.diagnostics[0].message)

    def test_exact_array_body_envelope_rejects_unsupported_source_stage(
        self,
    ) -> None:
        body_ir = self.selected_body_ir()
        stage = GenerationLoweringStage(
            stage="selected_body_ir_lowering",
            output=body_ir,
        )

        result = assemble_exact_array_body_envelope(
            stage,
            self.exact_array_body_skeleton(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
            severity="error",
            path="array.tsl",
            line=107,
            column=15,
        )
        self.assertIn("M63", result.diagnostics[0].message)

    def test_exact_array_body_envelope_rejects_invalid_skeleton_shapes(
        self,
    ) -> None:
        cases = (
            (
                "missing",
                ARRAY_BODY_SLOT_LABELS[:-1],
                (0, 1, 2, 3),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            ),
            (
                "duplicate",
                (
                    "opaque_pre_branch_array_initialization",
                    "opaque_pre_branch_predicate_initialization",
                    "selected_body_envelope",
                    "opaque_post_branch_store_call",
                    "opaque_post_branch_store_call",
                ),
                (0, 1, 2, 3, 4),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            ),
            (
                "duplicate_selected_body_slot",
                (
                    "opaque_pre_branch_array_initialization",
                    "opaque_pre_branch_predicate_initialization",
                    "selected_body_envelope",
                    "selected_body_envelope",
                    "opaque_post_branch_return_emission",
                ),
                (0, 1, 2, 3, 4),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            ),
            (
                "extra",
                (
                    *ARRAY_BODY_SLOT_LABELS,
                    "opaque_post_branch_return_emission",
                ),
                (0, 1, 2, 3, 4, 5),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            ),
            (
                "reordered",
                (
                    "opaque_pre_branch_predicate_initialization",
                    "opaque_pre_branch_array_initialization",
                    "selected_body_envelope",
                    "opaque_post_branch_store_call",
                    "opaque_post_branch_return_emission",
                ),
                (0, 1, 2, 3, 4),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
            ),
            (
                "wrong_ordinal",
                ARRAY_BODY_SLOT_LABELS,
                (0, 1, 3, 2, 4),
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
            ),
        )
        envelope = self.selected_body_envelope()

        for name, labels, ordinals, code in cases:
            with self.subTest(name=name):
                skeleton = self.exact_array_body_skeleton(
                    labels=labels,
                    ordinals=ordinals,
                )

                result = assemble_exact_array_body_envelope(envelope, skeleton)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=105,
                    column=15,
                )
                if name == "duplicate_selected_body_slot":
                    self.assertIn(
                        "exactly one of each M64 slot label",
                        result.diagnostics[0].message,
                    )

    def test_exact_array_body_envelope_rejects_non_exact_skeleton(
        self,
    ) -> None:
        envelope = self.selected_body_envelope()
        skeleton = self.exact_array_body_skeleton(exact=False)

        result = assemble_exact_array_body_envelope(envelope, skeleton)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
            severity="error",
            path="tsldata/primitives/load_store/array.tsl",
            line=105,
            column=15,
        )
        self.assertIn("exact", result.diagnostics[0].message)

    def test_exact_array_body_envelope_reports_provenance_mismatch(
        self,
    ) -> None:
        cases = (
            ("other-candidate", "si16", "candidate-1:chain"),
            ("candidate-1", "ui16", "candidate-1:chain"),
            ("candidate-1", "si16", "other-chain"),
        )
        envelope = self.selected_body_envelope()

        for candidate_id, selected_type_tag, branch_chain_id in cases:
            with self.subTest(
                candidate_id=candidate_id,
                selected_type_tag=selected_type_tag,
                branch_chain_id=branch_chain_id,
            ):
                skeleton = self.exact_array_body_skeleton(
                    candidate_id=candidate_id,
                    selected_type_tag=selected_type_tag,
                    branch_chain_id=branch_chain_id,
                )

                result = assemble_exact_array_body_envelope(envelope, skeleton)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
                    severity="error",
                    path="tsldata/primitives/load_store/array.tsl",
                    line=105,
                    column=15,
                )

    def test_opaque_handoff_rejects_unsupported_source_stage(self) -> None:
        statement = TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            )
        )
        stage = GenerationLoweringStage(
            stage="selected_body_lowering",
            output=statement,
        )

        result = handoff_opaque_selected_branch_body("candidate-1", stage)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-HANDOFF-SOURCE-UNSUPPORTED",
            severity="error",
        )

    def test_opaque_handoff_requires_branch_chain_provenance(self) -> None:
        predicates = tuple(
            GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=literal == 2,
                type_tag="si16",
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
            type_tag="si16",
            selected_literal=2,
            selected_statement_text="pg = intrin<svptrue_b16>();",
        )
        stage = GenerationLoweringStage(
            stage="generation_control_flow_pruning",
            output=chain,
        )

        result = handoff_opaque_selected_branch_body("candidate-1", stage)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-HANDOFF-PROVENANCE-MISSING",
            severity="error",
        )

    def test_assignment_form_recognition_rejects_unsupported_source_stage(
        self,
    ) -> None:
        statement = TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            )
        )
        stage = GenerationLoweringStage(
            stage="selected_body_lowering",
            output=statement,
        )

        result = recognize_selected_branch_body_assignment_form(stage)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-FORM-SOURCE-UNSUPPORTED",
            severity="error",
        )

    def test_assignment_form_recognition_reports_boundary_diagnostics(
        self,
    ) -> None:
        cases = (
            (
                "pg = intrin<svptrue_b16>(); emit_return(tmp);",
                "TSL-LOWER-SELECTED-BODY-FORM-EXTRA-STATEMENTS",
            ),
            (
                "mask = intrin<svptrue_b16>();",
                "TSL-LOWER-SELECTED-BODY-FORM-TARGET-UNSUPPORTED",
            ),
            (
                "pg = value<generation>(vector::length);",
                "TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED",
            ),
            (
                "pg = intrin<svptrue_b16>()",
                "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
            ),
        )

        for body_text, code in cases:
            with self.subTest(code=code):
                result = recognize_selected_branch_body_assignment_form(
                    self.assignment_handoff(body_text)
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_selected_size_byte_unsupported_body_reports_diagnostic(self) -> None:
        selection = self.selection_for(
            "lower_generation_size_byte_branch_chain_unsupported_selected_body"
        )

        result = lower_candidates(selection)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
            severity="error",
        )
        self.assertIn("assignment", result.diagnostics[0].message)

    def test_unselected_size_byte_branch_bodies_remain_uninspected(self) -> None:
        selection = self.selection_for(
            "lower_generation_size_byte_branch_chain_unselected_body_helpers"
        )

        result = lower_candidates(selection)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = result.unwrap().implementations[0]
        self.assertEqual(implementation.statements, ())
        self.assertEqual(len(implementation.selected_branch_body_handoffs), 1)
        handoff = implementation.selected_branch_body_handoffs[0]
        assert isinstance(handoff, OpaqueSelectedBranchBodyHandoff)
        self.assertEqual(handoff.opaque_body_text, "pg = intrin<svptrue_b16>();")
        self.assertEqual(len(implementation.selected_branch_body_assignment_forms), 1)
        form = implementation.selected_branch_body_assignment_forms[0]
        assert isinstance(form, SelectedBranchBodyAssignmentFormRecognition)
        self.assertEqual(form.direct_intrinsic_token_text, "svptrue_b16")

    def test_no_match_size_byte_branch_bodies_remain_uninspected(self) -> None:
        selection = self.selection_for(
            "lower_generation_size_byte_branch_chain_body_helpers"
        )

        result = lower_candidates(
            selection,
            LoweringRequest(
                generation_context=GenerationContext(type_tag_override="si8"),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        for implementation in result.unwrap().implementations:
            self.assertEqual(implementation.statements, ())
            self.assertEqual(len(implementation.selected_branch_body_handoffs), 1)
            handoff = implementation.selected_branch_body_handoffs[0]
            self.assertIsInstance(handoff, NoSelectedBranchBodyHandoff)
            self.assertEqual(len(implementation.selected_branch_body_assignment_forms), 1)
            form = implementation.selected_branch_body_assignment_forms[0]
            self.assertIsInstance(form, NoSelectedBranchBodyAssignmentFormRecognition)
            self.assertEqual(len(implementation.selected_branch_body_irs), 1)
            body_ir = implementation.selected_branch_body_irs[0]
            self.assertIsInstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr)
            envelope = implementation.selected_body_envelopes[0]
            self.assertIs(implementation.generation_stages[-4].output, handoff)
            self.assertIs(implementation.generation_stages[-3].output, form)
            self.assertIs(implementation.generation_stages[-2].output, body_ir)
            self.assertIs(implementation.generation_stages[-1].output, envelope)
            self.assertNotIsInstance(
                handoff,
                TsilReturnStatement,
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
