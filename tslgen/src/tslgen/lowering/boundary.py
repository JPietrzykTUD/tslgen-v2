from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.generation_rules import (
    ConcreteIntegerGenerationRuleSet,
    ScalarSizeBytesGenerationRuleSet,
    build_concrete_integer_generation_rule_set_from_catalog,
    build_scalar_size_bytes_generation_rule_set_from_catalog,
    classify_concrete_integer_generation_type_tag,
    classify_scalar_size_bytes_generation_type_tag,
    default_concrete_integer_generation_rule_set,
    default_scalar_size_bytes_generation_rule_set,
    is_non_integer_generation_type_tag,
)
from tslgen.domain.values import CatalogValue


type LoweringStrategy = Literal["mini_tsil", "typed_opaque"]
type PayloadClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]
type LoweringStatus = Literal["lowered", "unsupported"]
type GenerationBranchChoice = Literal["true", "false"]
type GenerationElseSyntax = Literal["else<generation>", "else"]
type GenerationTypeRefKind = Literal[
    "base.in",
    "base.signed_of",
    "base.unsigned_of",
]
type GenerationValueKind = Literal["type.size_bytes", "type.size_bits"]
type GenerationPredicateKind = Literal["type.size_bytes.equals"]
type TsilBinaryOperator = Literal["+"]
type TsilExpression = (
    TsilParameterReference | TsilBinaryExpression | TsilIntrinsicComposeExpression
)
type TsilStatement = TsilReturnStatement

_GENERATION_CONDITION_MARKER = "if<generation>"
_GENERATION_HELPER_MARKERS = (
    "if<generation>",
    "type<generation>",
    "value<generation>",
)
_GENERATION_TYPE_MARKER = "type<generation>"
_GENERATION_VALUE_MARKER = "value<generation>"
_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_TSIL_IDENTIFIER_RE = re.compile(rf"\A{_TSIL_IDENTIFIER}\Z")
_PRIMITIVE_ATTRIBUTE_CONDITION_RE = re.compile(
    rf"\A\s*value<generation>\(\s*primitive::attribute\(\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*\)\s*\Z"
)
_DIRECT_PARAMETER_ADD_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*({_TSIL_IDENTIFIER})\s*\+\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*intrin_compose\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*"
    r"\(([^()]*)\)\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_MARKER_RE = re.compile(r"\bintrin_compose\s*<")
_EMIT_RETURN_HEAD_RE = re.compile(r"\A\s*emit_return\s*\(")


@dataclass(frozen=True, slots=True)
class GenerationContext:
    values: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    primitive_attributes: FrozenMap[str, CatalogValue] | None = None
    use_candidate_attributes: bool = True
    selected_primitive_name: str | None = None
    emitted_primitive_name: str | None = None
    selected_candidate_id: str | None = None
    normalized_signature: str | None = None
    parameters: tuple[str, ...] = ()
    selected_type_tag: str | None = None
    type_tag_override: str | None = None
    use_candidate_type_tag: bool = True
    concrete_integer_generation_rules: ConcreteIntegerGenerationRuleSet = field(
        default_factory=default_concrete_integer_generation_rule_set
    )
    scalar_size_bytes_generation_rules: ScalarSizeBytesGenerationRuleSet = field(
        default_factory=default_scalar_size_bytes_generation_rule_set
    )
    implementation_source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", FrozenMap(self.values.items()))
        if self.primitive_attributes is not None:
            object.__setattr__(
                self,
                "primitive_attributes",
                FrozenMap(self.primitive_attributes.items()),
            )
        object.__setattr__(self, "parameters", tuple(self.parameters))
        for field_name in (
            "selected_primitive_name",
            "emitted_primitive_name",
            "selected_candidate_id",
            "normalized_signature",
            "selected_type_tag",
            "type_tag_override",
        ):
            value = getattr(self, field_name)
            if value == "":
                raise ValueError(f"generation context {field_name} must be non-empty")
        for parameter in self.parameters:
            if not parameter:
                raise ValueError("generation context parameters must be non-empty")


@dataclass(frozen=True, slots=True)
class LoweringRequest:
    strategy: LoweringStrategy = "mini_tsil"
    backend_id: str | None = None
    generation_context: GenerationContext = field(default_factory=GenerationContext)

    def __post_init__(self) -> None:
        if self.strategy not in ("mini_tsil", "typed_opaque"):
            raise ValueError(f"unknown lowering strategy: {self.strategy!r}")
        if self.backend_id is not None and not self.backend_id:
            raise ValueError("lowering backend id must be non-empty when provided")


@dataclass(frozen=True, slots=True)
class ClassifiedPayload:
    body_kind: str
    classification: PayloadClassification
    raw_payload: CatalogValue
    text: str | None = None
    has_generation_condition: bool = False

    def __post_init__(self) -> None:
        if not self.body_kind:
            raise ValueError("classified payload body kind must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.classification,
            self.body_kind,
            self.text or "",
            self.has_generation_condition,
        )


@dataclass(frozen=True, slots=True)
class LoweringInput:
    candidate: ImplementationCandidate
    payload: ClassifiedPayload

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.candidate.variant.source.declaration.source_span.location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate.candidate_id,
            self.payload.key,
        )


@dataclass(frozen=True, slots=True)
class LoweringInputSet:
    request: LoweringRequest
    inputs: tuple[LoweringInput, ...]
    inputs_by_candidate_id: FrozenMap[str, LoweringInput] = field(init=False)

    def __post_init__(self) -> None:
        inputs = tuple(sorted(self.inputs, key=lambda item: item.key))
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(
            self,
            "inputs_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in inputs),
        )


def build_catalog_lowering_request(
    catalog: Catalog,
    *,
    strategy: LoweringStrategy = "mini_tsil",
    backend_id: str | None = None,
    generation_context: GenerationContext | None = None,
) -> Result[LoweringRequest]:
    """Build a lowering request with generation rules derived before evaluation."""

    concrete_rules = build_concrete_integer_generation_rule_set_from_catalog(catalog)
    scalar_size_rules = build_scalar_size_bytes_generation_rule_set_from_catalog(catalog)
    diagnostics = (*concrete_rules.diagnostics, *scalar_size_rules.diagnostics)
    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    concrete_rule_set = concrete_rules.unwrap()
    scalar_size_rule_set = scalar_size_rules.unwrap()
    context = (
        GenerationContext(
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
        if generation_context is None
        else replace(
            generation_context,
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
    )
    return Result.ok(
        LoweringRequest(
            strategy=strategy,
            backend_id=backend_id,
            generation_context=context,
        )
    )


@dataclass(frozen=True, slots=True)
class TsilParameterReference:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TSIL parameter reference name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("parameter", self.name)


@dataclass(frozen=True, slots=True)
class TsilBinaryExpression:
    operator: TsilBinaryOperator
    left: TsilParameterReference
    right: TsilParameterReference

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "binary",
            self.operator,
            self.left.key,
            self.right.key,
        )


@dataclass(frozen=True, slots=True)
class TsilIntrinsicComposeExpression:
    intrinsic: str
    arguments: tuple[TsilParameterReference, ...]

    def __post_init__(self) -> None:
        if not self.intrinsic:
            raise ValueError("TSIL intrinsic-compose intrinsic must be non-empty")
        object.__setattr__(self, "arguments", tuple(self.arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "intrin_compose",
            self.intrinsic,
            tuple(argument.key for argument in self.arguments),
        )


@dataclass(frozen=True, slots=True)
class TsilReturnStatement:
    expression: TsilExpression

    @property
    def key(self) -> tuple[object, ...]:
        return ("return", self.expression.key)


@dataclass(frozen=True, slots=True)
class TsilPrimitiveAttributeCondition:
    attribute_name: str

    def __post_init__(self) -> None:
        if not self.attribute_name:
            raise ValueError("primitive attribute condition name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("primitive_attribute", self.attribute_name)


@dataclass(frozen=True, slots=True)
class TsilTypeSignednessCondition:
    type_ref: GenerationTypeRef

    @property
    def key(self) -> tuple[object, ...]:
        return ("type_is_signed", self.type_ref.key)


type TsilGenerationCondition = (
    TsilPrimitiveAttributeCondition | TsilTypeSignednessCondition
)


@dataclass(frozen=True, slots=True)
class PrunedGenerationBranch:
    condition: TsilGenerationCondition
    selected_branch: GenerationBranchChoice
    statement_text: str
    else_syntax: GenerationElseSyntax = "else<generation>"
    condition_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.statement_text.strip():
            raise ValueError("pruned generation branch statement text must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.condition_location.sort_key()
            if self.condition_location is not None
            else ()
        )
        return (
            self.condition.key,
            self.selected_branch,
            self.statement_text,
            self.else_syntax,
            location_key,
        )


@dataclass(frozen=True, slots=True)
class GenerationTypeRef:
    kind: GenerationTypeRefKind
    type_tag: str
    source_type_tag: str | None = None

    def __post_init__(self) -> None:
        if not self.type_tag:
            raise ValueError("generation type ref type tag must be non-empty")
        if self.source_type_tag == "":
            raise ValueError("generation type ref source type tag must be non-empty")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.type_tag, self.source_type_tag or "")


@dataclass(frozen=True, slots=True)
class GenerationValue:
    kind: GenerationValueKind
    value: int
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("generation value payload must be an integer")
        if not self.type_tag:
            raise ValueError("generation value type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.kind, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class GenerationPredicate:
    kind: GenerationPredicateKind
    literal: int
    value: bool
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.literal, bool) or not isinstance(self.literal, int):
            raise ValueError("generation predicate literal must be an integer")
        if self.literal not in (2, 4, 8):
            raise ValueError("generation predicate literal must be 2, 4, or 8")
        if not isinstance(self.value, bool):
            raise ValueError("generation predicate payload must be boolean")
        if not self.type_tag:
            raise ValueError("generation predicate type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, bool, str]:
        return (self.kind, self.literal, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class LoweredImplementation:
    candidate_id: str
    status: LoweringStatus
    statements: tuple[TsilStatement, ...] = ()
    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    generation_type_refs: tuple[GenerationTypeRef, ...] = ()
    generation_values: tuple[GenerationValue, ...] = ()
    generation_predicates: tuple[GenerationPredicate, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowered implementation candidate id must be non-empty")
        object.__setattr__(self, "statements", tuple(self.statements))
        object.__setattr__(
            self,
            "generation_branches",
            tuple(self.generation_branches),
        )
        object.__setattr__(
            self,
            "generation_type_refs",
            tuple(self.generation_type_refs),
        )
        object.__setattr__(
            self,
            "generation_values",
            tuple(self.generation_values),
        )
        object.__setattr__(
            self,
            "generation_predicates",
            tuple(self.generation_predicates),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate_id,
            self.status,
            tuple(statement.key for statement in self.statements),
            tuple(branch.key for branch in self.generation_branches),
            tuple(type_ref.key for type_ref in self.generation_type_refs),
            tuple(value.key for value in self.generation_values),
            tuple(predicate.key for predicate in self.generation_predicates),
        )


@dataclass(frozen=True, slots=True)
class LoweringPlan:
    request: LoweringRequest
    input_set: LoweringInputSet
    implementations: tuple[LoweredImplementation, ...]
    implementations_by_candidate_id: FrozenMap[str, LoweredImplementation] = field(
        init=False
    )

    def __post_init__(self) -> None:
        implementations = tuple(sorted(self.implementations, key=lambda item: item.key))
        object.__setattr__(self, "implementations", implementations)
        object.__setattr__(
            self,
            "implementations_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in implementations),
        )


def prepare_lowering_inputs(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringInputSet]:
    lowering_request = request or LoweringRequest()
    diagnostics: list[Diagnostic] = []
    inputs: list[LoweringInput] = []
    for candidate in selection.candidates:
        classified = _classify_payload(candidate)
        diagnostics.extend(classified.diagnostics)
        if classified.is_ok:
            inputs.append(
                LoweringInput(
                    candidate=candidate,
                    payload=classified.unwrap(),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringInputSet(request=lowering_request, inputs=tuple(inputs)),
        diagnostics=ordered,
    )


def lower_candidates(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringPlan]:
    input_set = prepare_lowering_inputs(selection, request)
    if not input_set.is_ok:
        return Result.failure(input_set.diagnostics)

    lowering_inputs = input_set.unwrap()
    if lowering_inputs.request.strategy == "typed_opaque":
        unsupported_diagnostics = tuple(
            _unsupported_payload_diagnostic(item, strategy="typed_opaque")
            for item in lowering_inputs.inputs
        )
        ordered = sort_diagnostics(unsupported_diagnostics)
        if has_errors(ordered):
            return Result.failure(ordered)
        return Result.ok(
            LoweringPlan(
                request=lowering_inputs.request,
                input_set=lowering_inputs,
                implementations=(),
            ),
            diagnostics=ordered,
        )

    diagnostics: list[Diagnostic] = []
    implementations: list[LoweredImplementation] = []
    for item in lowering_inputs.inputs:
        lowered = _lower_input(item, lowering_inputs.request)
        diagnostics.extend(lowered.diagnostics)
        if lowered.is_ok:
            implementations.append(lowered.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringPlan(
            request=lowering_inputs.request,
            input_set=lowering_inputs,
            implementations=tuple(implementations),
        ),
        diagnostics=ordered,
    )


def resolve_generation_type_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationTypeRef]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    query = query_text.strip()
    inner = _generation_type_query_inner(query, diagnostic_location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_type_ref_from_inner(
        inner.unwrap(),
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_value_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationValue]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    query = query_text.strip()
    size_bits = _generation_size_bits_value_expression(
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )
    if size_bits is not None:
        return size_bits
    inner = _generation_value_query_inner(query, diagnostic_location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_value_from_inner(
        inner.unwrap(),
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_predicate_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationPredicate]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    query = query_text.strip()
    parsed = _parse_generation_value_predicate_expression(query, diagnostic_location)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    expression = parsed.unwrap()
    if not expression.left_operand or not expression.right_operand:
        return Result.failure(
            (_malformed_generation_predicate_diagnostic(query, diagnostic_location),)
        )
    if expression.operator != "==":
        return Result.failure(
            (
                _unsupported_generation_predicate_operator_diagnostic(
                    query,
                    expression.operator,
                    diagnostic_location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    diagnostic_location,
                ),
            )
        )
    if expression.right_operand not in ("2", "4", "8"):
        return Result.failure(
            (
                _unsupported_generation_predicate_literal_diagnostic(
                    query,
                    expression.right_operand,
                    diagnostic_location,
                ),
            )
        )

    inner = _generation_value_query_inner(expression.left_operand, diagnostic_location)
    if not inner.is_ok:
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    diagnostic_location,
                ),
            )
        )
    inner_text = inner.unwrap()
    if _parse_generation_value_call(inner_text, "type::size_bytes") is None:
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    diagnostic_location,
                ),
            )
        )
    size_bytes = _generation_value_from_inner(
        inner_text,
        expression.left_operand,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )
    if not size_bytes.is_ok:
        return Result.failure(size_bytes.diagnostics)

    value = size_bytes.unwrap()
    if value.kind != "type.size_bytes":
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    diagnostic_location,
                ),
            )
        )
    literal = int(expression.right_operand)
    return Result.ok(
        GenerationPredicate(
            kind="type.size_bytes.equals",
            literal=literal,
            value=value.value == literal,
            type_tag=value.type_tag,
        )
    )


def _classify_payload(candidate: ImplementationCandidate) -> Result[ClassifiedPayload]:
    body = candidate.implementation.body
    text = body.text
    if body.kind == "tsil" and text is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-PAYLOAD-SHAPE",
                    f"candidate {candidate.candidate_id!r} has a TSIL payload "
                    "that is not text",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    return Result.ok(
        ClassifiedPayload(
            body_kind=body.kind,
            classification=body.classification,
            raw_payload=body.payload,
            text=text,
            has_generation_condition=(
                text is not None
                and _has_generation_helper(text)
            ),
        )
    )


def _lower_input(
    item: LoweringInput,
    request: LoweringRequest,
) -> Result[LoweredImplementation]:
    if item.payload.classification != "tsil":
        return Result.failure((_unsupported_payload_diagnostic(item),))

    text = item.payload.text or ""
    type_ref = _lower_generation_type_query_payload(item, request, text)
    if type_ref is not None:
        if not type_ref.is_ok:
            return Result.failure(type_ref.diagnostics)
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_type_refs=(type_ref.unwrap(),),
            )
        )

    generation_predicate = _lower_generation_predicate_query_payload(
        item,
        request,
        text,
    )
    if generation_predicate is not None:
        if not generation_predicate.is_ok:
            return Result.failure(generation_predicate.diagnostics)
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_predicates=(generation_predicate.unwrap(),),
            )
        )

    generation_value = _lower_generation_value_query_payload(item, request, text)
    if generation_value is not None:
        if not generation_value.is_ok:
            return Result.failure(generation_value.diagnostics)
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_values=(generation_value.unwrap(),),
            )
        )

    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    if item.payload.has_generation_condition:
        if _GENERATION_CONDITION_MARKER not in text:
            return Result.failure((_unresolved_selected_branch_diagnostic(item, text),))
        pruned = _prune_generation_branch(item, request, text)
        if not pruned.is_ok:
            return Result.failure(pruned.diagnostics)
        branch = pruned.unwrap()
        text = branch.statement_text
        generation_branches = (branch,)
        if _has_generation_helper(text):
            return Result.failure((_unresolved_selected_branch_diagnostic(item, text),))

    statement = _mini_return_statement(item, text)
    if not statement.is_ok:
        return Result.failure(statement.diagnostics)

    return Result.ok(
        LoweredImplementation(
            candidate_id=item.candidate_id,
            status="lowered",
            statements=(statement.unwrap(),),
            generation_branches=generation_branches,
        )
    )


def _lower_generation_type_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationTypeRef] | None:
    if _GENERATION_TYPE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_TYPE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_type_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_predicate_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationPredicate] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    if not _has_top_level_generation_comparison_operator(stripped):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_predicate_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_value_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationValue] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_value_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _mini_return_statement(
    item: LoweringInput,
    text: str | None = None,
) -> Result[TsilReturnStatement]:
    text = item.payload.text or "" if text is None else text
    match = _DIRECT_PARAMETER_ADD_RETURN_RE.fullmatch(text)
    if match is not None:
        return _direct_parameter_add_return_statement(item, match)
    if _INTRIN_COMPOSE_MARKER_RE.search(text):
        return _intrinsic_compose_return_statement(item, text)
    if _EMIT_RETURN_HEAD_RE.match(text):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-RETURN-SHAPE",
                    "mini TSIL lowering supports only direct parameter addition "
                    "returns shaped as 'emit_return(<parameter> + <parameter>);' "
                    "or intrinsic-compose returns shaped as "
                    "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
                    location=item.source_location,
                ),
            )
        )
    return Result.failure((_unsupported_payload_diagnostic(item),))


@dataclass(frozen=True, slots=True)
class _ParsedGenerationIf:
    condition_text: str
    true_branch_text: str
    false_branch_text: str
    else_syntax: GenerationElseSyntax


@dataclass(frozen=True, slots=True)
class _ResolvedGenerationCondition:
    condition: TsilGenerationCondition
    value: bool


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


def _prune_generation_branch(
    item: LoweringInput,
    request: LoweringRequest,
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
        return Result.failure((_unsupported_plain_else_generation_branch(item),))

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


def _primitive_attributes_for(
    item: LoweringInput,
    request: LoweringRequest,
) -> FrozenMap[str, CatalogValue] | None:
    request_attributes = request.generation_context.primitive_attributes
    if request_attributes is not None:
        return request_attributes
    if request.generation_context.use_candidate_attributes:
        return item.candidate.variant.attributes
    return None


def _context_for_candidate(
    item: LoweringInput,
    request: LoweringRequest,
) -> GenerationContext:
    context = request.generation_context
    parameters = context.parameters or tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    selected_type_tag = context.selected_type_tag
    if selected_type_tag is None and context.use_candidate_type_tag:
        selected_type_tag = item.candidate.type_tag
    return GenerationContext(
        values=context.values,
        primitive_attributes=context.primitive_attributes,
        use_candidate_attributes=context.use_candidate_attributes,
        selected_primitive_name=(
            context.selected_primitive_name or item.candidate.source_primitive_name
        ),
        emitted_primitive_name=(
            context.emitted_primitive_name or item.candidate.emitted_primitive_name
        ),
        selected_candidate_id=context.selected_candidate_id or item.candidate_id,
        normalized_signature=(
            context.normalized_signature
            or item.candidate.variant.source.signature.normalized
        ),
        parameters=parameters,
        selected_type_tag=selected_type_tag,
        type_tag_override=context.type_tag_override,
        use_candidate_type_tag=context.use_candidate_type_tag,
        concrete_integer_generation_rules=context.concrete_integer_generation_rules,
        scalar_size_bytes_generation_rules=(
            context.scalar_size_bytes_generation_rules
        ),
        implementation_source_location=(
            context.implementation_source_location or item.source_location
        ),
    )


def _generation_type_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_TYPE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_type_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_TYPE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_type_ref_from_inner(
    inner: str,
    query_text: str,
    context: GenerationContext,
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
                (_malformed_generation_type_query_diagnostic(query_text, location),)
            )
        nested = parsed[0].strip()
        if nested == "base::in":
            return Result.failure(
                (
                    _unsupported_generation_type_shorthand_diagnostic(
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
                    _unsupported_nested_generation_type_query_diagnostic(
                        query_text,
                        nested,
                        location,
                    ),
                )
            )
        if nested_inner.unwrap() != "base::in":
            return Result.failure(
                (
                    _unsupported_nested_generation_type_query_diagnostic(
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
                _unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::signed_of",
                    location,
                ),
            )
        )
    if "base::unsigned_of(base::in)" in inner:
        return Result.failure(
            (
                _unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::unsigned_of",
                    location,
                ),
            )
        )
    return Result.failure(
        (_unsupported_generation_type_query_diagnostic(query_text, location),)
    )


def _generation_value_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_value_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_VALUE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_size_bits_value_expression(
    query: str,
    context: GenerationContext,
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
            (_malformed_generation_value_arithmetic_diagnostic(query, location),)
        )
    if expression.operator != "*":
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_operator_diagnostic(
                    query,
                    expression.operator,
                    location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    if expression.right_operand != "8":
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_literal_diagnostic(
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
                _unsupported_generation_value_arithmetic_operand_diagnostic(
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
                    (_malformed_generation_value_arithmetic_diagnostic(query, location),)
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
        return Result.failure((_malformed_generation_predicate_diagnostic(query, location),))
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
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationValue]:
    parsed = _parse_generation_value_call(inner, "type::size_bytes")
    if parsed is None:
        return Result.failure(
            (_unsupported_generation_value_query_diagnostic(query_text, location),)
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
                _unsupported_nested_generation_value_query_diagnostic(
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
    context: GenerationContext,
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
    context: GenerationContext,
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


def _parse_generation_if(
    item: LoweringInput,
    text: str,
) -> Result[_ParsedGenerationIf]:
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_CONDITION_MARKER):
        return Result.failure((_unsupported_generation_condition_diagnostic(item, text),))

    cursor = len(_GENERATION_CONDITION_MARKER)
    cursor = _skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "(":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    condition_end = _matching_delimiter(stripped, cursor, "(", ")")
    if condition_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    condition_text = stripped[cursor + 1:condition_end].strip()

    cursor = _skip_whitespace(stripped, condition_end + 1)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    true_end = _matching_delimiter(stripped, cursor, "{", "}")
    if true_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    true_branch_text = stripped[cursor + 1:true_end].strip()

    cursor = _skip_whitespace(stripped, true_end + 1)
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
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    cursor = _skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    false_end = _matching_delimiter(stripped, cursor, "{", "}")
    if false_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    false_branch_text = stripped[cursor + 1:false_end].strip()

    tail = stripped[false_end + 1:].strip()
    if tail:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    return Result.ok(
        _ParsedGenerationIf(
            condition_text=condition_text,
            true_branch_text=true_branch_text,
            false_branch_text=false_branch_text,
            else_syntax=else_syntax,
        )
    )


def _generation_branch_condition(
    item: LoweringInput,
    request: LoweringRequest,
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
    item: LoweringInput,
    request: LoweringRequest,
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
    item: LoweringInput,
    request: LoweringRequest,
    condition_text: str,
) -> Result[_ResolvedGenerationCondition]:
    value_call = _parse_generation_type_call(condition_text, "value<generation>")
    if value_call is None or len(value_call) != 1:
        return Result.failure(
            (_unsupported_generation_condition_diagnostic(item, condition_text),)
        )
    predicate_call = _parse_generation_type_call(value_call[0], "type::is_signed")
    if predicate_call is None or len(predicate_call) != 1:
        return Result.failure(
            (_unsupported_generation_condition_diagnostic(item, condition_text),)
        )

    type_query = predicate_call[0].strip()
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    type_ref = resolve_generation_type_query(
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
        supported = _supported_generation_type_tag(
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


def _direct_parameter_add_return_statement(
    item: LoweringInput,
    match: re.Match[str],
) -> Result[TsilReturnStatement]:
    left_name, right_name = match.groups()
    unknown = _unknown_parameter_names(item, (left_name, right_name))
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference(left_name),
                right=TsilParameterReference(right_name),
            )
        )
    )


def _intrinsic_compose_return_statement(
    item: LoweringInput,
    text: str,
) -> Result[TsilReturnStatement]:
    match = _INTRIN_COMPOSE_RETURN_RE.fullmatch(text)
    if match is None:
        return Result.failure((_malformed_intrinsic_compose_diagnostic(item),))

    intrinsic_name, arguments_text = match.groups()
    if intrinsic_name != "add":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-UNSUPPORTED",
                    "mini TSIL lowering supports only intrinsic-compose "
                    f"intrinsic 'add'; got {intrinsic_name!r}",
                    location=item.source_location,
                ),
            )
        )

    argument_names = _intrinsic_argument_names(arguments_text)
    invalid_arguments = tuple(
        argument
        for argument in argument_names
        if _TSIL_IDENTIFIER_RE.fullmatch(argument) is None
    )
    if invalid_arguments:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARGUMENT",
                    "mini TSIL lowering supports only primitive parameter "
                    "references as intrin_compose<add> arguments; invalid "
                    f"argument(s): "
                    f"{', '.join(repr(argument) for argument in invalid_arguments)}",
                    location=item.source_location,
                ),
            )
        )

    if len(argument_names) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARITY",
                    "mini TSIL lowering supports only "
                    "intrin_compose<add> with exactly two arguments; got "
                    f"{len(argument_names)}",
                    location=item.source_location,
                ),
            )
        )

    unknown = _unknown_parameter_names(item, argument_names)
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilIntrinsicComposeExpression(
                intrinsic=intrinsic_name,
                arguments=tuple(
                    TsilParameterReference(argument) for argument in argument_names
                ),
            )
        )
    )


def _intrinsic_argument_names(arguments_text: str) -> tuple[str, ...]:
    stripped = arguments_text.strip()
    if not stripped:
        return ()
    return tuple(argument.strip() for argument in arguments_text.split(","))


def _unknown_parameter_names(
    item: LoweringInput,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    parameter_names = tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    return tuple(name for name in names if name not in parameter_names)


def _unknown_parameter_diagnostic(
    item: LoweringInput,
    unknown_names: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
        "mini TSIL lowering can reference only declared primitive "
        f"parameters; unknown name(s): "
        f"{', '.join(repr(name) for name in unknown_names)}",
        location=item.source_location,
    )


def _malformed_intrinsic_compose_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-INTRIN-MALFORMED",
        "mini TSIL lowering supports only intrinsic-compose returns shaped as "
        "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
        location=item.source_location,
    )


def _malformed_generation_if_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-MALFORMED",
        "generation-time branch pruning supports only branches shaped as "
        "'if<generation>(<supported condition>) { ... } else<generation> "
        "{ ... }', plus plain 'else { ... }' for the exact signedness "
        "predicate branch form",
        location=item.source_location,
    )


def _unsupported_generation_condition_diagnostic(
    item: LoweringInput,
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
    item: LoweringInput,
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
    item: LoweringInput,
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


def _unsupported_payload_diagnostic(
    item: LoweringInput,
    *,
    strategy: LoweringStrategy = "mini_tsil",
) -> Diagnostic:
    if item.payload.classification == "tsil":
        code = "TSL-LOWER-TSIL-UNSUPPORTED"
        if strategy == "typed_opaque":
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering is disabled by the typed-opaque strategy"
            )
        else:
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering supports only the mini direct parameter-add return "
                "and intrinsic-compose add return slices"
            )
        if item.payload.has_generation_condition:
            message += (
                " and contains generation-time helpers that must be evaluated "
                "by a future lowering slice"
            )
    else:
        code = "TSL-LOWER-PAYLOAD-UNSUPPORTED"
        message = (
            f"candidate {item.candidate_id!r} has unsupported implementation "
            f"payload kind {item.payload.body_kind!r}"
        )
    return Diagnostic.error(code, message, location=item.source_location)


def _has_generation_helper(text: str) -> bool:
    return any(marker in text for marker in _GENERATION_HELPER_MARKERS)
