from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue


type LoweringStrategy = Literal["typed_opaque"]
type PayloadClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]
type LoweringStatus = Literal["unsupported"]

_GENERATION_CONDITION_MARKER = "if<generation>"


@dataclass(frozen=True, slots=True)
class GenerationContext:
    values: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)


@dataclass(frozen=True, slots=True)
class LoweringRequest:
    strategy: LoweringStrategy = "typed_opaque"
    backend_id: str | None = None
    generation_context: GenerationContext = field(default_factory=GenerationContext)

    def __post_init__(self) -> None:
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
class LoweredImplementation:
    candidate_id: str
    status: LoweringStatus
    statements: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowered implementation candidate id must be non-empty")
        object.__setattr__(self, "statements", tuple(self.statements))


@dataclass(frozen=True, slots=True)
class LoweringPlan:
    request: LoweringRequest
    input_set: LoweringInputSet
    implementations: tuple[LoweredImplementation, ...]
    implementations_by_candidate_id: FrozenMap[str, LoweredImplementation] = field(
        init=False
    )

    def __post_init__(self) -> None:
        implementations = tuple(
            sorted(self.implementations, key=lambda item: item.candidate_id)
        )
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
    diagnostics = tuple(
        _unsupported_payload_diagnostic(item)
        for item in lowering_inputs.inputs
    )
    ordered = sort_diagnostics(diagnostics)
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


def _classify_payload(candidate: ImplementationCandidate) -> Result[ClassifiedPayload]:
    body = candidate.implementation.body
    classification = _classification_for_body_kind(body.kind)
    if body.kind == "tsil" and not isinstance(body.payload, str):
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

    text = body.payload if isinstance(body.payload, str) else None
    return Result.ok(
        ClassifiedPayload(
            body_kind=body.kind,
            classification=classification,
            raw_payload=body.payload,
            text=text,
            has_generation_condition=(
                isinstance(body.payload, str)
                and _GENERATION_CONDITION_MARKER in body.payload
            ),
        )
    )


def _classification_for_body_kind(body_kind: str) -> PayloadClassification:
    if body_kind == "tsil":
        return "tsil"
    if body_kind in {"intrin", "intrinsic", "intrin_compose"}:
        return "intrinsic"
    if body_kind in {"c", "c17", "cpp", "rust"}:
        return "backend_specific"
    return "opaque"


def _unsupported_payload_diagnostic(item: LoweringInput) -> Diagnostic:
    if item.payload.classification == "tsil":
        code = "TSL-LOWER-TSIL-UNSUPPORTED"
        message = (
            f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
            "TSIL lowering is deferred by the typed-opaque strategy"
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
