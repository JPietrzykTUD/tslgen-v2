from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
import tslgen.lowering._generation_diagnostics as _generation_diagnostics
import tslgen.lowering._generation_queries as _generation_queries
from tslgen.lowering._generation_models import (
    GenerationBranchChoice,
    GenerationElseSyntax,
    GenerationPredicate,
    GenerationSizeByteBranchChainArm,
    GenerationSizeByteBranchChainPruning,
    GenerationValue,
    PrunedGenerationBranch,
    TsilGenerationCondition,
    TsilPrimitiveAttributeCondition,
    TsilTypeSignednessCondition,
    _GENERATION_CONDITION_MARKER,
)


class _VariantLike(Protocol):
    @property
    def attributes(self) -> FrozenMap[str, CatalogValue]: ...


class _CandidateLike(Protocol):
    @property
    def type_tag(self) -> str: ...

    @property
    def variant(self) -> _VariantLike: ...


class GenerationControlContext(_generation_queries.GenerationQueryContext, Protocol):
    @property
    def primitive_attributes(self) -> FrozenMap[str, CatalogValue] | None: ...

    @property
    def use_candidate_attributes(self) -> bool: ...

    @property
    def use_candidate_type_tag(self) -> bool: ...


class LoweringInputLike(Protocol):
    @property
    def candidate(self) -> _CandidateLike: ...

    @property
    def source_location(self) -> SourceLocation | None: ...


class LoweringRequestLike(Protocol):
    @property
    def generation_context(self) -> GenerationControlContext: ...


_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_PRIMITIVE_ATTRIBUTE_CONDITION_RE = re.compile(
    rf"\A\s*value<generation>\(\s*primitive::attribute\(\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*\)\s*\Z"
)


def _selected_candidate_type_tag(
    item: LoweringInputLike,
    context: GenerationControlContext,
) -> str | None:
    return item.candidate.type_tag if context.use_candidate_type_tag else None


@dataclass(frozen=True, slots=True)
class _StagedGenerationSizeByteBranchChain:
    pruning: GenerationSizeByteBranchChainPruning
    generation_values: tuple[GenerationValue, ...] = ()
    generation_predicates: tuple[GenerationPredicate, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation_values", tuple(self.generation_values))
        object.__setattr__(
            self,
            "generation_predicates",
            tuple(self.generation_predicates),
        )


@dataclass(frozen=True, slots=True)
class _ParsedGenerationIf:
    condition_text: str
    true_branch_text: str
    false_branch_text: str
    else_syntax: GenerationElseSyntax


@dataclass(frozen=True, slots=True)
class _ParsedSizeByteBranchChainArm:
    condition_text: str
    statement_text: str


@dataclass(frozen=True, slots=True)
class _ParsedSizeByteBranchChain:
    arms: tuple[_ParsedSizeByteBranchChainArm, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arms", tuple(self.arms))


@dataclass(frozen=True, slots=True)
class _ResolvedGenerationCondition:
    condition: TsilGenerationCondition
    value: bool


def _prune_generation_branch(
    item: LoweringInputLike,
    request: LoweringRequestLike,
    text: str,
) -> Result[PrunedGenerationBranch]:
    parsed = _parse_generation_if(item, text)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    parsed_branch = parsed.unwrap()

    condition = _generation_branch_condition(item, request, parsed_branch.condition_text)
    if not condition.is_ok:
        return Result.failure(condition.diagnostics)
    resolved_condition = condition.unwrap()
    if (
        parsed_branch.else_syntax == "else"
        and not isinstance(resolved_condition.condition, TsilTypeSignednessCondition)
    ):
        return Result.failure((_generation_diagnostics._unsupported_plain_else_generation_branch(item),))

    selected_branch: GenerationBranchChoice = (
        "true" if resolved_condition.value else "false"
    )
    statement_text = (
        parsed_branch.true_branch_text
        if resolved_condition.value
        else parsed_branch.false_branch_text
    ).strip()
    return Result.ok(
        PrunedGenerationBranch(
            condition=resolved_condition.condition,
            selected_branch=selected_branch,
            statement_text=statement_text,
            else_syntax=parsed_branch.else_syntax,
            condition_location=item.source_location,
        )
    )


def _prune_generation_size_byte_branch_chain(
    item: LoweringInputLike,
    request: LoweringRequestLike,
    text: str,
) -> Result[_StagedGenerationSizeByteBranchChain] | None:
    if "else if<generation>" not in text:
        return None

    parsed = _parse_generation_size_byte_branch_chain(item, text)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    context = request.generation_context
    selected_candidate_type_tag = _selected_candidate_type_tag(item, context)
    expected_literals = (2, 4, 8)
    values_by_key: dict[tuple[str, int, str], GenerationValue] = {}
    predicates: list[GenerationPredicate] = []
    arms: list[GenerationSizeByteBranchChainArm] = []

    for expected_literal, parsed_arm in zip(
        expected_literals,
        parsed.unwrap().arms,
        strict=True,
    ):
        staged = _generation_queries._resolve_generation_predicate_query_staged(
            parsed_arm.condition_text,
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            location=item.source_location,
        )
        if not staged.is_ok:
            return Result.failure(staged.diagnostics)

        staged_predicate = staged.unwrap()
        predicate = staged_predicate.predicate
        if predicate.kind != "type.size_bytes.equals" or predicate.literal != expected_literal:
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        for value in staged_predicate.generation_values:
            values_by_key.setdefault(value.key, value)
        predicates.append(predicate)
        arms.append(
            GenerationSizeByteBranchChainArm(
                literal=expected_literal,
                predicate=predicate,
                statement_text=parsed_arm.statement_text,
            )
        )

    type_tags = tuple(dict.fromkeys(predicate.type_tag for predicate in predicates))
    if len(type_tags) != 1:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))

    selected_arms = tuple(arm for arm in arms if arm.predicate.value)
    if len(selected_arms) > 1:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    selected_arm = selected_arms[0] if selected_arms else None
    return Result.ok(
        _StagedGenerationSizeByteBranchChain(
            pruning=GenerationSizeByteBranchChainPruning(
                arms=tuple(arms),
                type_tag=type_tags[0],
                selected_literal=(
                    selected_arm.literal if selected_arm is not None else None
                ),
                selected_statement_text=(
                    selected_arm.statement_text if selected_arm is not None else None
                ),
                condition_location=item.source_location,
            ),
            generation_values=tuple(values_by_key.values()),
            generation_predicates=tuple(predicates),
        )
    )


def _primitive_attributes_for(
    item: LoweringInputLike,
    request: LoweringRequestLike,
) -> FrozenMap[str, CatalogValue] | None:
    request_attributes = request.generation_context.primitive_attributes
    if request_attributes is not None:
        return request_attributes
    if request.generation_context.use_candidate_attributes:
        return item.candidate.variant.attributes
    return None


def _parse_generation_if(
    item: LoweringInputLike,
    text: str,
) -> Result[_ParsedGenerationIf]:
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_CONDITION_MARKER):
        return Result.failure((_generation_diagnostics._unsupported_generation_condition_diagnostic(item, text),))

    cursor = len(_GENERATION_CONDITION_MARKER)
    cursor = _generation_queries._skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "(":
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    condition_end = _generation_queries._matching_delimiter(stripped, cursor, "(", ")")
    if condition_end is None:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    condition_text = stripped[cursor + 1:condition_end].strip()

    cursor = _generation_queries._skip_whitespace(stripped, condition_end + 1)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    true_end = _generation_queries._matching_delimiter(stripped, cursor, "{", "}")
    if true_end is None:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    true_branch_text = stripped[cursor + 1:true_end].strip()

    cursor = _generation_queries._skip_whitespace(stripped, true_end + 1)
    else_syntax: GenerationElseSyntax
    else_generation_marker = "else<generation>"
    plain_else_marker = "else"
    if stripped.startswith(else_generation_marker, cursor):
        else_syntax = "else<generation>"
        cursor += len(else_generation_marker)
    elif stripped.startswith(plain_else_marker, cursor):
        else_syntax = "else"
        cursor += len(plain_else_marker)
    else:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    cursor = _generation_queries._skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    false_end = _generation_queries._matching_delimiter(stripped, cursor, "{", "}")
    if false_end is None:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    false_branch_text = stripped[cursor + 1:false_end].strip()

    tail = stripped[false_end + 1:].strip()
    if tail:
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    return Result.ok(
        _ParsedGenerationIf(
            condition_text=condition_text,
            true_branch_text=true_branch_text,
            false_branch_text=false_branch_text,
            else_syntax=else_syntax,
        )
    )


def _parse_generation_size_byte_branch_chain(
    item: LoweringInputLike,
    text: str,
) -> Result[_ParsedSizeByteBranchChain]:
    stripped = text.strip()
    cursor = 0
    arms: list[_ParsedSizeByteBranchChainArm] = []
    for marker in ("if<generation>", "else if<generation>", "else if<generation>"):
        if not stripped.startswith(marker, cursor):
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        cursor += len(marker)
        cursor = _generation_queries._skip_whitespace(stripped, cursor)
        if cursor >= len(stripped) or stripped[cursor] != "(":
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        condition_end = _generation_queries._matching_delimiter(stripped, cursor, "(", ")")
        if condition_end is None:
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        condition_text = stripped[cursor + 1:condition_end].strip()

        cursor = _generation_queries._skip_whitespace(stripped, condition_end + 1)
        if cursor >= len(stripped) or stripped[cursor] != "{":
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        body_end = _generation_queries._matching_delimiter(stripped, cursor, "{", "}")
        if body_end is None:
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        statement_text = stripped[cursor + 1:body_end].strip()
        if not statement_text or _GENERATION_CONDITION_MARKER in statement_text:
            return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
        arms.append(
            _ParsedSizeByteBranchChainArm(
                condition_text=condition_text,
                statement_text=statement_text,
            )
        )
        cursor = _generation_queries._skip_whitespace(stripped, body_end + 1)

    if stripped[cursor:].strip():
        return Result.failure((_generation_diagnostics._malformed_generation_if_diagnostic(item),))
    return Result.ok(_ParsedSizeByteBranchChain(tuple(arms)))


def _generation_branch_condition(
    item: LoweringInputLike,
    request: LoweringRequestLike,
    condition_text: str,
) -> Result[_ResolvedGenerationCondition]:
    primitive_condition = _primitive_attribute_condition(condition_text)
    if primitive_condition is not None:
        return _resolve_primitive_attribute_condition(
            item,
            request,
            primitive_condition,
        )
    return _resolve_type_signedness_condition(item, request, condition_text)


def _primitive_attribute_condition(
    condition_text: str,
) -> TsilPrimitiveAttributeCondition | None:
    match = _PRIMITIVE_ATTRIBUTE_CONDITION_RE.fullmatch(condition_text)
    if match is None:
        return None
    return TsilPrimitiveAttributeCondition(match.group(1))


def _resolve_primitive_attribute_condition(
    item: LoweringInputLike,
    request: LoweringRequestLike,
    attribute_condition: TsilPrimitiveAttributeCondition,
) -> Result[_ResolvedGenerationCondition]:
    attributes = _primitive_attributes_for(item, request)
    if attributes is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-CONTEXT-MISSING",
                    "generation-time primitive-attribute lowering requires "
                    "primitive attributes in GenerationContext or on the "
                    "selected candidate",
                    location=item.source_location,
                ),
            )
        )

    if attribute_condition.attribute_name != "aligned":
        if attribute_condition.attribute_name not in attributes:
            return Result.failure(
                (
                    Diagnostic.error(
                        "TSL-LOWER-GEN-ATTRIBUTE-UNKNOWN",
                        "generation-time primitive-attribute condition "
                        f"references unknown primitive attribute "
                        f"{attribute_condition.attribute_name!r}",
                        location=item.source_location,
                    ),
                )
            )
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-IF-UNSUPPORTED",
                    "generation-time branch pruning supports only primitive "
                    "attribute 'aligned'; got "
                    f"{attribute_condition.attribute_name!r}",
                    location=item.source_location,
                ),
            )
        )

    if attribute_condition.attribute_name not in attributes:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-ATTRIBUTE-MISSING",
                    "generation-time branch pruning requires primitive "
                    "attribute 'aligned'",
                    location=item.source_location,
                ),
            )
        )
    value = attributes[attribute_condition.attribute_name]
    if not isinstance(value, bool):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-ATTRIBUTE-TYPE",
                    "generation-time branch pruning requires primitive "
                    f"attribute 'aligned' to be boolean; got {value!r}",
                    location=item.source_location,
                ),
            )
        )

    return Result.ok(
        _ResolvedGenerationCondition(
            condition=attribute_condition,
            value=value,
        )
    )


def _resolve_type_signedness_condition(
    item: LoweringInputLike,
    request: LoweringRequestLike,
    condition_text: str,
) -> Result[_ResolvedGenerationCondition]:
    value_call = _generation_queries._parse_generation_type_call(condition_text, "value<generation>")
    if value_call is None or len(value_call) != 1:
        return Result.failure(
            (_generation_diagnostics._unsupported_generation_condition_diagnostic(item, condition_text),)
        )
    predicate_call = _generation_queries._parse_generation_type_call(value_call[0], "type::is_signed")
    if predicate_call is None or len(predicate_call) != 1:
        return Result.failure(
            (_generation_diagnostics._unsupported_generation_condition_diagnostic(item, condition_text),)
        )

    type_query = predicate_call[0].strip()
    context = request.generation_context
    selected_candidate_type_tag = _selected_candidate_type_tag(item, context)
    type_ref = _generation_queries.resolve_generation_type_query(
        type_query,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )
    if not type_ref.is_ok:
        return Result.failure(type_ref.diagnostics)

    resolved_type_ref = type_ref.unwrap()
    if resolved_type_ref.kind != "base.in":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-IF-UNSUPPORTED",
                    "generation-time signedness branch pruning supports only "
                    "'type::is_signed(type<generation>(base::in))'; got "
                    f"{condition_text!r}",
                    location=item.source_location,
                ),
            )
        )

    rule = context.concrete_integer_generation_rules.rule_for(resolved_type_ref.type_tag)
    if rule is None:
        supported = _generation_queries._supported_generation_type_tag(
            resolved_type_ref.type_tag,
            context.concrete_integer_generation_rules,
            type_query,
            item.source_location,
        )
        if not supported.is_ok:
            return Result.failure(supported.diagnostics)
        raise AssertionError("supported signedness type tags must be handled directly")

    return Result.ok(
        _ResolvedGenerationCondition(
            condition=TsilTypeSignednessCondition(resolved_type_ref),
            value=rule.is_signed,
        )
    )
