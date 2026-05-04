from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", FrozenMap(self.values.items()))
        if self.primitive_attributes is not None:
            object.__setattr__(
                self,
                "primitive_attributes",
                FrozenMap(self.primitive_attributes.items()),
            )


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
class PrunedGenerationBranch:
    condition: TsilPrimitiveAttributeCondition
    selected_branch: GenerationBranchChoice
    statement_text: str
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
            location_key,
        )


@dataclass(frozen=True, slots=True)
class LoweredImplementation:
    candidate_id: str
    status: LoweringStatus
    statements: tuple[TsilStatement, ...] = ()
    generation_branches: tuple[PrunedGenerationBranch, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowered implementation candidate id must be non-empty")
        object.__setattr__(self, "statements", tuple(self.statements))
        object.__setattr__(
            self,
            "generation_branches",
            tuple(self.generation_branches),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate_id,
            self.status,
            tuple(statement.key for statement in self.statements),
            tuple(branch.key for branch in self.generation_branches),
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


def _prune_generation_branch(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[PrunedGenerationBranch]:
    parsed = _parse_generation_if(item, text)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    parsed_branch = parsed.unwrap()

    condition = _primitive_attribute_condition(item, parsed_branch.condition_text)
    if not condition.is_ok:
        return Result.failure(condition.diagnostics)
    attribute_condition = condition.unwrap()

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

    selected_branch: GenerationBranchChoice = "true" if value else "false"
    statement_text = (
        parsed_branch.true_branch_text if value else parsed_branch.false_branch_text
    ).strip()
    return Result.ok(
        PrunedGenerationBranch(
            condition=attribute_condition,
            selected_branch=selected_branch,
            statement_text=statement_text,
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
    else_marker = "else<generation>"
    if not stripped.startswith(else_marker, cursor):
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    cursor = _skip_whitespace(stripped, cursor + len(else_marker))
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
        )
    )


def _primitive_attribute_condition(
    item: LoweringInput,
    condition_text: str,
) -> Result[TsilPrimitiveAttributeCondition]:
    match = _PRIMITIVE_ATTRIBUTE_CONDITION_RE.fullmatch(condition_text)
    if match is None:
        return Result.failure((_unsupported_generation_condition_diagnostic(item, condition_text),))
    return Result.ok(TsilPrimitiveAttributeCondition(match.group(1)))


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
        "'if<generation>(value<generation>(primitive::attribute(aligned))) "
        "{ ... } else<generation> { ... }'",
        location=item.source_location,
    )


def _unsupported_generation_condition_diagnostic(
    item: LoweringInput,
    condition_text: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-UNSUPPORTED",
        "generation-time branch pruning supports only condition "
        "'value<generation>(primitive::attribute(aligned))'; got "
        f"{condition_text!r}",
        location=item.source_location,
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
                " and contains generation-time conditions that must be evaluated "
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
