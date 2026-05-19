from __future__ import annotations

from typing import Any

from tslgen.core.diagnostics import Diagnostic, SourceLocation

def _array_body_envelope_shape_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_slot_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_slot_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-MISSING",
        detail,
        location=location,
    )


def _array_initialization_slot_wrong_position_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-WRONG-POSITION",
        detail,
        location=location,
    )


def _array_initialization_slot_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED",
        detail,
        location=location,
    )


def _array_initialization_slot_helper_unsupported_diagnostic(
    slot: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-HELPER-UNSUPPORTED",
        "array-initialization slot form lowering preserves only the exact "
        "unresolved helper leaves type<generation>(base::in), "
        "value<generation>(vector::length), "
        "value<generation>(vector::alignment), and "
        "value<backend>(uninit::array)",
        location=slot.source_location,
    )


def _array_initialization_slot_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_request_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_request_missing_form_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-FORM-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_request_missing_leaf_diagnostic(
    spec: Any,
    form: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING",
        "array-initialization helper request lowering requires the M66 "
        f"{spec.field_name} field to carry the unresolved helper leaf "
        f"{spec.expected_leaf_kind!r}",
        location=form.source_location,
    )


def _array_initialization_helper_request_mismatched_leaf_diagnostic(
    spec: Any,
    leaf: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISMATCH",
        "array-initialization helper request lowering expected the M66 "
        f"{spec.field_name} field to carry leaf kind "
        f"{spec.expected_leaf_kind!r}, got {leaf.kind!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_duplicate_leaf_diagnostic(
    leaf: Any,
    form: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-DUPLICATE",
        "array-initialization helper request lowering requires each of the "
        "four M66 helper leaf kinds exactly once; duplicate leaf kind "
        f"{leaf.kind!r} appeared for variable {form.variable_token!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_unsupported_leaf_diagnostic(
    spec: Any,
    leaf: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-UNSUPPORTED",
        "array-initialization helper request lowering preserves only the "
        "exact M66 unresolved helper leaf text for "
        f"{spec.expected_leaf_kind!r}; got {leaf.source_text!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_duplicate_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_conflict_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-CONFLICT",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_duplicate_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_conflict_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-CONFLICT",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_set_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_set_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_helper_set_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_set_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_helper_set_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_set_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-MALFORMED",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_backend_policy_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-BACKEND-UNINIT-POLICY-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_body_structural_sequence_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
        detail,
        location=location,
    )


def _array_body_structural_sequence_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_body_structural_sequence_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_role_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-ROLE-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-MALFORMED",
        detail,
        location=location,
    )


def _predicate_path_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _predicate_path_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-IR-MISSING",
        detail,
        location=location,
    )


def _predicate_path_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-IR-MULTIPLE",
        detail,
        location=location,
    )


def _predicate_path_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _predicate_path_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _predicate_path_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-MALFORMED",
        detail,
        location=location,
    )


def _predicate_path_token_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-TOKEN-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _post_branch_call_site_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MISSING",
        detail,
        location=location,
    )


def _post_branch_call_site_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MULTIPLE",
        detail,
        location=location,
    )


def _post_branch_call_site_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_sequence_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-SEQUENCE-MISSING",
        detail,
        location=location,
    )


def _post_branch_call_site_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-MALFORMED",
        detail,
        location=location,
    )


def _post_branch_call_site_shape_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-SHAPE-UNSUPPORTED",
        detail,
        location=location,
    )


def _post_branch_call_site_call_head_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-CALL-HEAD-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_intrinsic_token_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-INTRINSIC-TOKEN-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_argument_count_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-ARGUMENT-COUNT-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_predicate_argument_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-PREDICATE-ARGUMENT-MISMATCH",
        detail,
        location=location,
    )


def _post_branch_call_site_member_access_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-MEMBER-ACCESS-UNSUPPORTED",
        detail,
        location=location,
    )


def _post_branch_call_site_source_operand_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-OPERAND-UNSUPPORTED",
        detail,
        location=location,
    )


def _duplicate_array_body_envelope_skeleton_diagnostic(
    lookup_key: Any,
    skeleton: Any,
    *,
    conflicting: bool,
) -> Diagnostic:
    code = (
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-CONFLICT"
        if conflicting
        else "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-DUPLICATE"
    )
    detail = "conflicting" if conflicting else "duplicate"
    return Diagnostic.error(
        code,
        f"array-body envelope skeleton input has a {detail} skeleton for "
        f"candidate {lookup_key.candidate_id!r}, selected type tag "
        f"{lookup_key.selected_type_tag!r}, and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}; provide exactly one "
        "typed skeleton for that envelope key",
        location=skeleton.source_location,
    )


def _missing_array_body_envelope_skeleton_diagnostic(
    requirement: Any,
    envelope: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-MISSING",
        "array-body envelope skeleton input is required for candidate "
        f"{envelope.candidate_id!r}, selected type tag "
        f"{envelope.selected_type_tag!r}, and branch-chain identity "
        f"{envelope.originating_branch_chain_id!r}, but no matching typed "
        "ExactArrayBodyEnvelopeSkeleton was supplied",
        location=requirement.source_location or envelope.source_location,
    )


def _orphan_array_body_envelope_skeleton_diagnostic(
    lookup_key: Any,
    skeleton: Any,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-ORPHAN",
        "array-body envelope skeleton input was supplied for candidate "
        f"{lookup_key.candidate_id!r}, selected type tag "
        f"{lookup_key.selected_type_tag!r}, and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}, but normal lowering "
        "produced no M63 selected-body envelope for that candidate",
        location=skeleton.source_location,
    )


def _mismatched_array_body_envelope_skeleton_diagnostic(
    lookup_key: Any,
    skeleton: Any,
    envelope_keys: tuple[Any, ...],
) -> Diagnostic:
    candidate_envelope_keys = tuple(
        envelope_key
        for envelope_key in envelope_keys
        if envelope_key.candidate_id == lookup_key.candidate_id
    )
    expected = tuple(
        (
            envelope_key.selected_type_tag,
            envelope_key.originating_branch_chain_id,
        )
        for envelope_key in candidate_envelope_keys
    )
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-PROVENANCE-MISMATCH",
        "array-body envelope skeleton input did not match the M63 envelope "
        "provenance for candidate "
        f"{lookup_key.candidate_id!r}; got selected type tag "
        f"{lookup_key.selected_type_tag!r} and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}, expected one of "
        f"{expected!r}",
        location=skeleton.source_location,
    )
