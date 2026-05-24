from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.domain.generation_rules import (
    ConcreteIntegerGenerationRuleSet,
    ScalarSizeBytesGenerationRuleSet,
    classify_concrete_integer_generation_type_tag,
    classify_scalar_size_bytes_generation_type_tag,
    is_non_integer_generation_type_tag,
)
import tslgen.lowering._generation_diagnostics as _generation_diagnostics
from tslgen.lowering._generation_models import (
    GenerationPredicate,
    GenerationTypeRef,
    GenerationTypeRefKind,
    GenerationValue,
    _GENERATION_TYPE_MARKER,
    _GENERATION_VALUE_MARKER,
)


class GenerationQueryContext(Protocol):
    @property
    def type_tag_override(self) -> str | None: ...

    @property
    def selected_type_tag(self) -> str | None: ...

    @property
    def concrete_integer_generation_rules(self) -> ConcreteIntegerGenerationRuleSet: ...

    @property
    def scalar_size_bytes_generation_rules(self) -> ScalarSizeBytesGenerationRuleSet: ...


def resolve_generation_type_query(
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationTypeRef]:
    query = query_text.strip()
    inner = _generation_type_query_inner(query, location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_type_ref_from_inner(
        inner.unwrap(),
        query,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )


def resolve_generation_value_query(
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationValue]:
    query = query_text.strip()
    size_bits = _generation_size_bits_value_expression(
        query,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if size_bits is not None:
        return size_bits
    inner = _generation_value_query_inner(query, location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_value_from_inner(
        inner.unwrap(),
        query,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )


def resolve_generation_predicate_query(
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationPredicate]:
    staged = _resolve_generation_predicate_query_staged(
        query_text,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if not staged.is_ok:
        return Result.failure(staged.diagnostics)
    return Result.ok(staged.unwrap().predicate)


@dataclass(frozen=True, slots=True)
class _StagedGenerationPredicate:
    predicate: GenerationPredicate
    generation_values: tuple[GenerationValue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation_values", tuple(self.generation_values))


@dataclass(frozen=True, slots=True)
class _ParsedGenerationValueArithmeticExpression:
    operator: str
    left_operand: str
    right_operand: str


@dataclass(frozen=True, slots=True)
class _ParsedGenerationValuePredicateExpression:
    operator: str
    left_operand: str
    right_operand: str


def _resolve_generation_predicate_query_staged(
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[_StagedGenerationPredicate]:
    query = query_text.strip()
    parsed = _parse_generation_value_predicate_expression(query, location)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    expression = parsed.unwrap()
    if not expression.left_operand or not expression.right_operand:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_predicate_diagnostic(query, location),)
        )
    if expression.operator != "==":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_operator_diagnostic(
                    query,
                    expression.operator,
                    location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    if expression.right_operand not in ("2", "4", "8"):
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_literal_diagnostic(
                    query,
                    expression.right_operand,
                    location,
                ),
            )
        )

    inner = _generation_value_query_inner(expression.left_operand, location)
    if not inner.is_ok:
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    inner_text = inner.unwrap()
    if _parse_generation_value_call(inner_text, "type::size_bytes") is None:
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    size_bytes = _generation_value_from_inner(
        inner_text,
        expression.left_operand,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if not size_bytes.is_ok:
        return Result.failure(size_bytes.diagnostics)

    value = size_bytes.unwrap()
    if value.kind != "type.size_bytes":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    literal = int(expression.right_operand)
    return Result.ok(
        _StagedGenerationPredicate(
            predicate=GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=value.value == literal,
                type_tag=value.type_tag,
            ),
            generation_values=(value,),
        )
    )


def _generation_type_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_TYPE_MARKER):
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_type_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_TYPE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_generation_diagnostics._malformed_generation_type_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_type_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_type_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_type_ref_from_inner(
    inner: str,
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationTypeRef]:
    if inner == "base::in":
        type_tag = _effective_generation_type_tag(
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            query_text=query_text,
            location=location,
        )
        if not type_tag.is_ok:
            return Result.failure(type_tag.diagnostics)
        return _base_in_type_ref(
            type_tag.unwrap(),
            context.concrete_integer_generation_rules,
            query_text,
            location,
        )

    helper_forms: tuple[tuple[str, GenerationTypeRefKind], ...] = (
        ("base::signed_of", "base.signed_of"),
        ("base::unsigned_of", "base.unsigned_of"),
    )
    for helper_name, kind in helper_forms:
        parsed = _parse_generation_type_call(inner, helper_name)
        if parsed is None:
            continue
        if len(parsed) != 1:
            return Result.failure(
                (_generation_diagnostics._malformed_generation_type_query_diagnostic(query_text, location),)
            )
        nested = parsed[0].strip()
        if nested == "base::in":
            return Result.failure(
                (
                    _generation_diagnostics._unsupported_generation_type_shorthand_diagnostic(
                        query_text,
                        helper_name,
                        location,
                    ),
                )
            )
        nested_inner = _generation_type_query_inner(nested, location)
        if not nested_inner.is_ok:
            return Result.failure(
                (
                    _generation_diagnostics._unsupported_nested_generation_type_query_diagnostic(
                        query_text,
                        nested,
                        location,
                    ),
                )
            )
        if nested_inner.unwrap() != "base::in":
            return Result.failure(
                (
                    _generation_diagnostics._unsupported_nested_generation_type_query_diagnostic(
                        query_text,
                        nested,
                        location,
                    ),
                )
            )
        source_type_tag = _effective_generation_type_tag(
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            query_text=query_text,
            location=location,
        )
        if not source_type_tag.is_ok:
            return Result.failure(source_type_tag.diagnostics)
        companion = _integer_companion_type_tag(
            source_type_tag.unwrap(),
            kind,
            context.concrete_integer_generation_rules,
            query_text,
            location,
        )
        if not companion.is_ok:
            return Result.failure(companion.diagnostics)
        return Result.ok(
            GenerationTypeRef(
                kind=kind,
                type_tag=companion.unwrap(),
                source_type_tag=source_type_tag.unwrap(),
            )
        )

    if "base::signed_of(base::in)" in inner:
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::signed_of",
                    location,
                ),
            )
        )
    if "base::unsigned_of(base::in)" in inner:
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::unsigned_of",
                    location,
                ),
            )
        )
    return Result.failure(
        (_generation_diagnostics._unsupported_generation_type_query_diagnostic(query_text, location),)
    )


def _generation_value_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_value_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_VALUE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_generation_diagnostics._malformed_generation_value_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_value_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_value_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_size_bits_value_expression(
    query: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationValue] | None:
    parsed = _parse_generation_value_arithmetic_expression(query, location)
    if parsed is None:
        return None
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    expression = parsed.unwrap()
    if not expression.left_operand or not expression.right_operand:
        return Result.failure(
            (_generation_diagnostics._malformed_generation_value_arithmetic_diagnostic(query, location),)
        )
    if expression.operator != "*":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_value_arithmetic_operator_diagnostic(
                    query,
                    expression.operator,
                    location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_value_arithmetic_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    if expression.right_operand != "8":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_value_arithmetic_literal_diagnostic(
                    query,
                    expression.right_operand,
                    location,
                ),
            )
        )

    inner = _generation_value_query_inner(expression.left_operand, location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    size_bytes = _generation_value_from_inner(
        inner.unwrap(),
        expression.left_operand,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if not size_bytes.is_ok:
        return Result.failure(size_bytes.diagnostics)

    value = size_bytes.unwrap()
    if value.kind != "type.size_bytes":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_generation_value_arithmetic_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    return Result.ok(
        GenerationValue(
            kind="type.size_bits",
            value=value.value * 8,
            type_tag=value.type_tag,
        )
    )


def _parse_generation_value_arithmetic_expression(
    query: str,
    location: SourceLocation | None,
) -> Result[_ParsedGenerationValueArithmeticExpression] | None:
    depth = 0
    index = 0
    while index < len(query):
        character = query[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return Result.failure(
                    (_generation_diagnostics._malformed_generation_value_arithmetic_diagnostic(query, location),)
                )
        elif depth == 0:
            if query.startswith("==", index):
                return Result.ok(
                    _ParsedGenerationValueArithmeticExpression(
                        operator="==",
                        left_operand=query[:index].strip(),
                        right_operand=query[index + 2:].strip(),
                    )
                )
            if character in ("*", "/", "+", "-", "%"):
                return Result.ok(
                    _ParsedGenerationValueArithmeticExpression(
                        operator=character,
                        left_operand=query[:index].strip(),
                        right_operand=query[index + 1:].strip(),
                    )
                )
        index += 1
    return None


def _parse_generation_value_predicate_expression(
    query: str,
    location: SourceLocation | None,
) -> Result[_ParsedGenerationValuePredicateExpression]:
    parsed = _parse_top_level_generation_binary_expression(
        query,
        include_arithmetic=True,
    )
    if parsed is None:
        return Result.failure((_generation_diagnostics._malformed_generation_predicate_diagnostic(query, location),))
    operator, left_operand, right_operand = parsed
    return Result.ok(
        _ParsedGenerationValuePredicateExpression(
            operator=operator,
            left_operand=left_operand,
            right_operand=right_operand,
        )
    )


def _has_top_level_generation_comparison_operator(query: str) -> bool:
    parsed = _parse_top_level_generation_binary_expression(
        query,
        include_arithmetic=False,
    )
    return parsed is not None and parsed[0] in ("==", "!=", "<=", ">=", "<", ">")


def _parse_top_level_generation_binary_expression(
    query: str,
    *,
    include_arithmetic: bool,
) -> tuple[str, str, str] | None:
    depth = 0
    index = 0
    while index < len(query):
        if query.startswith(_GENERATION_VALUE_MARKER, index):
            index += len(_GENERATION_VALUE_MARKER)
            continue
        if query.startswith(_GENERATION_TYPE_MARKER, index):
            index += len(_GENERATION_TYPE_MARKER)
            continue

        character = query[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif depth == 0:
            for operator in ("==", "!=", "<=", ">="):
                if query.startswith(operator, index):
                    return (
                        operator,
                        query[:index].strip(),
                        query[index + len(operator):].strip(),
                    )
            if character in ("<", ">"):
                return (
                    character,
                    query[:index].strip(),
                    query[index + 1:].strip(),
                )
            if include_arithmetic and character in ("*", "/", "+", "-", "%"):
                return (
                    character,
                    query[:index].strip(),
                    query[index + 1:].strip(),
                )
        index += 1
    if depth != 0:
        return None
    return None


def _generation_value_from_inner(
    inner: str,
    query_text: str,
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationValue]:
    parsed = _parse_generation_value_call(inner, "type::size_bytes")
    if parsed is None:
        return Result.failure(
            (_generation_diagnostics._unsupported_generation_value_query_diagnostic(query_text, location),)
        )
    if len(parsed) != 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-ARITY",
                    "generation-time scalar size-bytes value query requires "
                    "exactly one nested type query argument; got "
                    f"{len(parsed)} in {query_text!r}",
                    location=location,
                ),
            )
        )

    nested = parsed[0].strip()
    nested_inner = _generation_type_query_inner(nested, location)
    if not nested_inner.is_ok or nested_inner.unwrap() != "base::in":
        return Result.failure(
            (
                _generation_diagnostics._unsupported_nested_generation_value_query_diagnostic(
                    query_text,
                    nested,
                    location,
                ),
            )
        )

    type_tag = _effective_generation_value_type_tag(
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        query_text=query_text,
        location=location,
    )
    if not type_tag.is_ok:
        return Result.failure(type_tag.diagnostics)
    return _type_size_bytes_generation_value(
        type_tag.unwrap(),
        context.scalar_size_bytes_generation_rules,
        query_text,
        location,
    )


def _parse_generation_type_call(text: str, function_name: str) -> tuple[str, ...] | None:
    stripped = text.strip()
    if not stripped.startswith(function_name):
        return None
    open_index = _skip_whitespace(stripped, len(function_name))
    if open_index >= len(stripped) or stripped[open_index] != "(":
        return None
    close_index = _matching_delimiter(stripped, open_index, "(", ")")
    if close_index is None or stripped[close_index + 1:].strip():
        return ()
    return _split_generation_type_arguments(stripped[open_index + 1:close_index])


def _parse_generation_value_call(text: str, function_name: str) -> tuple[str, ...] | None:
    stripped = text.strip()
    if not stripped.startswith(function_name):
        return None
    open_index = _skip_whitespace(stripped, len(function_name))
    if open_index >= len(stripped) or stripped[open_index] != "(":
        return None
    close_index = _matching_delimiter(stripped, open_index, "(", ")")
    if close_index is None or stripped[close_index + 1:].strip():
        return ()
    return _split_generation_value_arguments(stripped[open_index + 1:close_index])


def _split_generation_type_arguments(text: str) -> tuple[str, ...]:
    arguments: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return ()
        elif character == "," and depth == 0:
            arguments.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        return ()
    tail = text[start:].strip()
    if tail:
        arguments.append(tail)
    return tuple(arguments)


def _split_generation_value_arguments(text: str) -> tuple[str, ...]:
    arguments: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return ()
        elif character == "," and depth == 0:
            arguments.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        return ()
    tail = text[start:].strip()
    if tail or arguments:
        arguments.append(tail)
    return tuple(arguments)


def _effective_generation_type_tag(
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    type_tag = (
        context.type_tag_override
        or context.selected_type_tag
        or selected_candidate_type_tag
    )
    if type_tag is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-CONTEXT-MISSING",
                    "generation-time type query requires a selected candidate "
                    "type tag or GenerationContext.type_tag_override; query "
                    f"was {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.ok(type_tag)


def _effective_generation_value_type_tag(
    context: GenerationQueryContext,
    *,
    selected_candidate_type_tag: str | None,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    type_tag = (
        context.type_tag_override
        or context.selected_type_tag
        or selected_candidate_type_tag
    )
    if type_tag is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-CONTEXT-MISSING",
                    "generation-time scalar size-bytes value query requires a "
                    "selected candidate type tag or "
                    "GenerationContext.type_tag_override; query was "
                    f"{query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.ok(type_tag)


def _base_in_type_ref(
    type_tag: str,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[GenerationTypeRef]:
    supported = _supported_generation_type_tag(type_tag, rule_set, query_text, location)
    if not supported.is_ok:
        return Result.failure(supported.diagnostics)
    return Result.ok(GenerationTypeRef(kind="base.in", type_tag=type_tag))


def _supported_generation_type_tag(
    type_tag: str,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[None]:
    if rule_set.rule_for(type_tag) is not None:
        return Result.ok(None)
    status = classify_concrete_integer_generation_type_tag(type_tag)
    if status in ("selected", "unsupported"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
                    "generation-time base type query supports only concrete "
                    "integer type tags "
                    f"{_quoted_join(rule_set.supported_type_tags)}; got "
                    f"{type_tag!r} for query {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-GEN-TYPE-TAG-UNKNOWN",
                "generation-time base type query received unknown type tag "
                f"{type_tag!r} for query {query_text!r}",
                location=location,
            ),
        )
    )


def _type_size_bytes_generation_value(
    type_tag: str,
    rule_set: ScalarSizeBytesGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[GenerationValue]:
    rule = rule_set.rule_for(type_tag)
    if rule is not None:
        return Result.ok(
            GenerationValue(
                kind="type.size_bytes",
                value=rule.size_bytes,
                type_tag=rule.type_tag,
            )
        )
    status = classify_scalar_size_bytes_generation_type_tag(type_tag)
    if status in ("selected", "unsupported"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED",
                    "generation-time scalar size-bytes value query supports "
                    "only selected scalar type tags "
                    f"{_quoted_join(rule_set.supported_type_tags)}; got "
                    f"{type_tag!r} for query {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-GEN-VALUE-TAG-UNKNOWN",
                "generation-time scalar size-bytes value query received "
                f"unknown type tag {type_tag!r} for query {query_text!r}",
                location=location,
            ),
        )
    )


def _integer_companion_type_tag(
    source_type_tag: str,
    kind: GenerationTypeRefKind,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    rule = rule_set.rule_for(source_type_tag)
    if rule is not None:
        if kind == "base.signed_of":
            return Result.ok(rule.signed_type_tag)
        if kind == "base.unsigned_of":
            return Result.ok(rule.unsigned_type_tag)
    if is_non_integer_generation_type_tag(source_type_tag):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-NON-INTEGER",
                    "generation-time signed/unsigned companion query requires "
                    f"a concrete integer type tag; got {source_type_tag!r} "
                    f"for query {query_text!r}",
                    location=location,
                ),
            )
        )
    supported = _supported_generation_type_tag(
        source_type_tag,
        rule_set,
        query_text,
        location,
    )
    if supported.is_ok:
        raise AssertionError("supported companion type tags must be handled directly")
    return Result.failure(supported.diagnostics)


def _quoted_join(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


def _skip_whitespace(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _matching_delimiter(
    text: str,
    opening_index: int,
    opening: str,
    closing: str,
) -> int | None:
    if opening_index >= len(text) or text[opening_index] != opening:
        return None
    depth = 0
    for index in range(opening_index, len(text)):
        char = text[index]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return None
