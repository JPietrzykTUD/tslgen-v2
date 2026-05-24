from __future__ import annotations

from typing import Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._generation_models import _GENERATION_HELPER_MARKERS


class SourceLocated(Protocol):
    @property
    def source_location(self) -> SourceLocation | None: ...


def _malformed_generation_if_diagnostic(
    item: SourceLocated,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-MALFORMED",
        "generation-time branch pruning supports only branches shaped as "
        "'if<generation>(<supported condition>) { ... } else<generation> "
        "{ ... }', plus plain 'else { ... }' for the exact signedness "
        "predicate branch form, and the exact no-final-else size-byte "
        "branch chain with == 2, == 4, then == 8 arms",
        location=item.source_location,
    )


def _unsupported_generation_condition_diagnostic(
    item: SourceLocated,
    condition_text: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-UNSUPPORTED",
        "generation-time branch pruning supports only conditions "
        "'value<generation>(primitive::attribute(aligned))' and "
        "'value<generation>(type::is_signed(type<generation>(base::in)))'; "
        "got "
        f"{condition_text!r}",
        location=item.source_location,
    )


def _unsupported_plain_else_generation_branch(
    item: SourceLocated,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-UNSUPPORTED",
        "plain 'else' generation branch syntax is supported only for "
        "'if<generation>(value<generation>(type::is_signed("
        "type<generation>(base::in))))'; use 'else<generation>' for other "
        "supported generation-time branch forms",
        location=item.source_location,
    )


def _malformed_generation_type_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-MALFORMED",
        "generation-time type query must be shaped as "
        "'type<generation>(...)'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_type_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-UNSUPPORTED",
        "generation-time type lowering supports only "
        "'type<generation>(base::in)', "
        "'type<generation>(base::signed_of(type<generation>(base::in)))', "
        "and "
        "'type<generation>(base::unsigned_of(type<generation>(base::in)))'; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_generation_type_shorthand_diagnostic(
    query_text: str,
    helper_name: str,
    location: SourceLocation | None,
) -> Diagnostic:
    exact_form = (
        f"type<generation>({helper_name}"
        "(type<generation>(base::in)))"
    )
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-UNSUPPORTED",
        "generation-time type lowering does not accept shorthand "
        f"{helper_name}(base::in); use exact nested form {exact_form!r}; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_nested_generation_type_query_diagnostic(
    query_text: str,
    nested_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED",
        "generation-time signed/unsigned companion lowering supports only "
        "nested 'type<generation>(base::in)' input; got nested query "
        f"{nested_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_value_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-MALFORMED",
        "generation-time value query must be shaped as "
        "'value<generation>(...)'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_value_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-UNSUPPORTED",
        "generation-time value lowering supports only "
        "'value<generation>(type::size_bytes("
        "type<generation>(base::in)))' and the exact "
        "'value<generation>(type::size_bytes("
        "type<generation>(base::in))) * 8' expression; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_nested_generation_value_query_diagnostic(
    query_text: str,
    nested_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED",
        "generation-time scalar size-bytes lowering supports only nested "
        "'type<generation>(base::in)' input; got nested query "
        f"{nested_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_value_arithmetic_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-MALFORMED",
        "generation-time scalar bit-width value arithmetic must be shaped as "
        "'value<generation>(type::size_bytes(type<generation>(base::in))) * 8'; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_operator_diagnostic(
    query_text: str,
    operator: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-OPERATOR",
        "generation-time scalar bit-width value arithmetic supports only the "
        f"exact '*' operator with right literal 8; got operator {operator!r} "
        f"in {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_literal_diagnostic(
    query_text: str,
    literal_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-LITERAL",
        "generation-time scalar bit-width value arithmetic supports only the "
        f"exact right literal '8'; got {literal_text!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_operand_diagnostic(
    query_text: str,
    operand_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-OPERAND",
        "generation-time scalar bit-width value arithmetic supports only "
        "the M55 scalar size-bytes query as the left operand; got "
        f"{operand_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_predicate_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-MALFORMED",
        "generation-time scalar size-byte equality predicate must be shaped as "
        "'value<generation>(type::size_bytes(type<generation>(base::in))) == "
        "2|4|8'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_operator_diagnostic(
    query_text: str,
    operator: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-OPERATOR",
        "generation-time scalar size-byte equality predicate supports only "
        f"the exact '==' operator; got operator {operator!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_literal_diagnostic(
    query_text: str,
    literal_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-LITERAL",
        "generation-time scalar size-byte equality predicate supports only "
        f"right literal '2', '4', or '8'; got {literal_text!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_operand_diagnostic(
    query_text: str,
    operand_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-OPERAND",
        "generation-time scalar size-byte equality predicate supports only "
        "the M55 scalar size-bytes query as the left operand; got "
        f"{operand_text!r} in {query_text!r}",
        location=location,
    )


def _unresolved_selected_branch_diagnostic(
    item: SourceLocated,
    branch_text: str,
) -> Diagnostic:
    helper_names = tuple(
        marker for marker in _GENERATION_HELPER_MARKERS if marker in branch_text
    )
    helper_message = (
        f"; unresolved helper marker(s): {', '.join(repr(name) for name in helper_names)}"
        if helper_names
        else ""
    )
    return Diagnostic.error(
        "TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH",
        "generation-time branch pruning selected a branch that still contains "
        f"unsupported generation-time helper text{helper_message}",
        location=item.source_location,
    )
