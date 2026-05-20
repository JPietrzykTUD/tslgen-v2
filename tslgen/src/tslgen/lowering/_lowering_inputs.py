from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslgen.analysis.candidates import ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue


type LoweringStrategy = Literal["mini_tsil", "typed_opaque"]
type PayloadClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]

_GENERATION_HELPER_MARKERS = (
    "if<generation>",
    "type<generation>",
    "value<generation>",
)


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
                and any(marker in text for marker in _GENERATION_HELPER_MARKERS)
            ),
        )
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
