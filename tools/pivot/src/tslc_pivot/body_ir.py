"""Immutable PIVOT-owned body and evidence values."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc.lower.dependencies import (
    CallDependency,
    CallVectorReference,
    GenericVectorReference,
    VectorIdentity,
)
from tslc_pivot.model import PivotDefinition, PivotLanguage


@dataclass(frozen=True, slots=True, order=True)
class PivotBindingId:
    ordinal: int

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("a PIVOT binding ordinal cannot be negative")


@dataclass(frozen=True, slots=True)
class PivotBinding:
    identity: PivotBindingId
    authored_name: str
    source: SourceSpan | None

    def __post_init__(self) -> None:
        if not self.authored_name:
            raise ValueError("a PIVOT binding requires an authored name")


@dataclass(frozen=True, slots=True)
class PivotResidualText:
    """Target-language expression text whose syntax is deferred to slice 27C."""

    text: str
    source: SourceSpan | None

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("a residual PIVOT text piece cannot be empty")


@dataclass(frozen=True, slots=True)
class PivotCall:
    dependency: CallDependency
    attrs: tuple[tuple[str, str], ...]
    arguments: tuple[PivotExpression, ...]
    source: SourceSpan | None
    requires_unsafe: bool = False


@dataclass(frozen=True, slots=True)
class PivotFixedCall:
    """One synthetic fixed-vector wrapper call owned by PIVOT export."""

    callable_name: str
    vector_type: str
    arguments: tuple[PivotExpression, ...]
    source: SourceSpan | None


type PivotExpressionPiece = PivotResidualText | PivotCall | PivotFixedCall


@dataclass(frozen=True, slots=True)
class PivotExpression:
    pieces: tuple[PivotExpressionPiece, ...]
    source: SourceSpan | None

    def __post_init__(self) -> None:
        if not self.pieces:
            raise ValueError("a PIVOT expression requires at least one piece")

    @property
    def requires_unsafe(self) -> bool:
        return any(
            (
                piece.requires_unsafe
                if isinstance(piece, PivotCall)
                else False
            )
            or (
                isinstance(piece, (PivotCall, PivotFixedCall))
                and any(argument.requires_unsafe for argument in piece.arguments)
            )
            for piece in self.pieces
        )


@dataclass(frozen=True, slots=True)
class PivotLocal:
    binding: PivotBinding
    initializer: PivotExpression
    mutable: bool
    source: SourceSpan | None


@dataclass(frozen=True, slots=True)
class PivotResidualStatementSequence:
    """An opaque run of one or more target statements, not a parsed assignment."""

    expression: PivotExpression
    source: SourceSpan | None


type PivotStatement = PivotLocal | PivotResidualStatementSequence


@dataclass(frozen=True, slots=True)
class PivotFinalResult:
    value: PivotExpression
    source: SourceSpan | None


@dataclass(frozen=True, slots=True)
class PivotBody:
    language: PivotLanguage
    parameters: tuple[PivotBinding, ...]
    statements: tuple[PivotStatement, ...]
    result: PivotFinalResult
    requires_unsafe: bool
    source: SourceSpan | None

    def __post_init__(self) -> None:
        identities = tuple(binding.identity for binding in self.parameters)
        identities += tuple(
            statement.binding.identity
            for statement in self.statements
            if isinstance(statement, PivotLocal)
        )
        if len(identities) != len(set(identities)):
            raise ValueError("PIVOT binding identities must be unique within a body")

    @property
    def call_count(self) -> int:
        return sum(_call_count(expression) for expression in _expressions(self))

    @property
    def call_depth(self) -> int:
        return max(
            (_call_depth(expression) for expression in _expressions(self)),
            default=0,
        )

    @property
    def local_count(self) -> int:
        return sum(isinstance(statement, PivotLocal) for statement in self.statements)

    @property
    def residual_statement_sequence_count(self) -> int:
        return sum(
            isinstance(statement, PivotResidualStatementSequence)
            for statement in self.statements
        )


@dataclass(frozen=True, slots=True)
class PivotUnsupported:
    code: str
    message: str
    source: SourceSpan | None
    phase: str = "body_construction"

    def __post_init__(self) -> None:
        if not self.code.startswith("TSL-PIVOT-"):
            raise ValueError("a PIVOT unsupported code must start with 'TSL-PIVOT-'")
        if not self.message:
            raise ValueError("a PIVOT unsupported reason requires a message")
        if not self.phase:
            raise ValueError("a PIVOT unsupported reason requires a phase")


@dataclass(frozen=True, slots=True)
class PivotBodyBuildResult:
    body: PivotBody | None = None
    unsupported: tuple[PivotUnsupported, ...] = ()

    def __post_init__(self) -> None:
        if (self.body is None) == (not self.unsupported):
            raise ValueError(
                "a PIVOT body build result requires exactly one of body or unsupported"
            )


class PivotBodyCategory(str, Enum):
    SYNTHETIC_FIXED = "synthetic_fixed"
    NATIVE_LEAF = "native_leaf"
    CALL_ONLY = "call_only"
    LOCAL_ONLY = "local_only"
    CALL_AND_LOCAL = "call_and_local"


class PivotBodyOrigin(str, Enum):
    LOWERED_SOURCE = "lowered_source"
    FIXED_WRAPPER = "fixed_wrapper"


@dataclass(frozen=True, slots=True)
class PivotBodyEntry:
    document: str
    definition: PivotDefinition
    occurrence: int
    origin: PivotBodyOrigin
    category: PivotBodyCategory | None
    body: PivotBodyBuildResult
    inlined_bodies: tuple[PivotBodyBuildResult, ...] = ()

    def __post_init__(self) -> None:
        if self.occurrence < 0:
            raise ValueError("a body occurrence cannot be negative")
        failed = any(
            result.body is None for result in (self.body, *self.inlined_bodies)
        )
        if failed == (self.category is not None):
            raise ValueError("a body failure must not have a category, and vice versa")
        fixed_category = self.category is PivotBodyCategory.SYNTHETIC_FIXED
        fixed_origin = self.origin is PivotBodyOrigin.FIXED_WRAPPER
        if not failed and fixed_category != fixed_origin:
            raise ValueError("a successful fixed-wrapper body needs its fixed category")

    @property
    def features(self) -> tuple[str, ...]:
        root = self.body.body
        if root is None or any(item.body is None for item in self.inlined_bodies):
            return ("body_failure",)
        bodies = (
            root,
            *(item.body for item in self.inlined_bodies if item.body is not None),
        )
        features: set[str] = set()
        if self.origin is PivotBodyOrigin.FIXED_WRAPPER:
            features.add("synthetic_fixed")
        if len(self.definition.direct) > 1:
            features.add("multi_statement")
        if root.call_count:
            features.add("typed_call")
        if root.call_depth > 1 or any(body.call_count for body in bodies[1:]):
            features.add("nested_typed_call")
        local_count = sum(body.local_count for body in bodies)
        if local_count:
            features.add("typed_local")
        if local_count > 1:
            features.add("multiple_locals")
        if root.call_count and local_count:
            features.add("call_and_local")
        if any(body.residual_statement_sequence_count for body in bodies):
            features.add("residual_top_level_text")
        if any(_has_residual_text(body) for body in bodies):
            features.add("residual_expression")
        if root.language is PivotLanguage.RUST and any(
            body.requires_unsafe for body in bodies
        ):
            features.add("rust_unsafe_frame")
        if not root.statements:
            features.add("result_only")
        return tuple(sorted(features))


@dataclass(frozen=True, slots=True)
class PivotBodyCensus:
    language: PivotLanguage
    entries: tuple[PivotBodyEntry, ...]

    @property
    def failures(self) -> tuple[PivotUnsupported, ...]:
        return tuple(
            reason
            for entry in self.entries
            for result in (entry.body, *entry.inlined_bodies)
            for reason in result.unsupported
        )

    @property
    def category_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(
            entry.category.value
            for entry in self.entries
            if entry.category is not None
        )
        return tuple(sorted(counts.items()))

    @property
    def origin_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            sorted(Counter(entry.origin.value for entry in self.entries).items())
        )

    @property
    def feature_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(feature for entry in self.entries for feature in entry.features)
        return tuple(sorted(counts.items()))

    @property
    def feature_combination_counts(self) -> tuple[tuple[tuple[str, ...], int], ...]:
        return tuple(sorted(Counter(entry.features for entry in self.entries).items()))

    @property
    def multi_statement_count(self) -> int:
        return sum(len(entry.definition.direct) > 1 for entry in self.entries)


def classify_body_trace(
    body: PivotBody,
    inlined_bodies: tuple[PivotBodyBuildResult, ...],
) -> PivotBodyCategory:
    has_calls = body.call_count > 0
    has_locals = body.local_count > 0 or any(
        result.body is not None and result.body.local_count > 0
        for result in inlined_bodies
    )
    if has_calls and has_locals:
        return PivotBodyCategory.CALL_AND_LOCAL
    if has_calls:
        return PivotBodyCategory.CALL_ONLY
    if has_locals:
        return PivotBodyCategory.LOCAL_ONLY
    return PivotBodyCategory.NATIVE_LEAF


def pivot_body_trace_semantic_digest(
    body: PivotBodyBuildResult,
    inlined_bodies: tuple[PivotBodyBuildResult, ...],
) -> str:
    return _digest(
        [_build_record(result, spans=False) for result in (body, *inlined_bodies)]
    )


def pivot_body_census_digest(
    censuses: tuple[PivotBodyCensus, ...],
) -> str:
    """Hash exact typed-body semantics independently of source locations."""

    return _pivot_body_census_digest(censuses, spans=False)


def pivot_body_census_location_digest(
    censuses: tuple[PivotBodyCensus, ...],
    *,
    source_root: Path,
) -> str:
    """Hash typed-body facts and normalized source locations."""

    normalized_root = source_root.resolve()
    return _pivot_body_census_digest(
        censuses,
        spans=True,
        source_root=normalized_root,
    )


def _pivot_body_census_digest(
    censuses: tuple[PivotBodyCensus, ...],
    *,
    spans: bool,
    source_root: Path | None = None,
) -> str:
    return _digest(
        [
            {
                "language": census.language.value,
                "entries": [
                    {
                        "document": entry.document,
                        "definition": (
                            entry.definition.isa,
                            entry.definition.dtype,
                            entry.definition.signature,
                            entry.definition.direct,
                        ),
                        "occurrence": entry.occurrence,
                        "category": (
                            None if entry.category is None else entry.category.value
                        ),
                        "origin": entry.origin.value,
                        "features": entry.features,
                        "body": _build_record(
                            entry.body,
                            spans=spans,
                            source_root=source_root,
                        ),
                        "inlined": [
                            _build_record(
                                result,
                                spans=spans,
                                source_root=source_root,
                            )
                            for result in entry.inlined_bodies
                        ],
                    }
                    for entry in census.entries
                ],
            }
            for census in censuses
        ]
    )


def _expressions(body: PivotBody) -> tuple[PivotExpression, ...]:
    return (
        *(
            statement.initializer
            if isinstance(statement, PivotLocal)
            else statement.expression
            for statement in body.statements
        ),
        body.result.value,
    )


def _call_count(expression: PivotExpression) -> int:
    return sum(
        1 + sum(_call_count(argument) for argument in piece.arguments)
        for piece in expression.pieces
        if isinstance(piece, (PivotCall, PivotFixedCall))
    )


def _call_depth(expression: PivotExpression) -> int:
    return max(
        (
            1
            + max(
                (_call_depth(argument) for argument in piece.arguments),
                default=0,
            )
            for piece in expression.pieces
            if isinstance(piece, (PivotCall, PivotFixedCall))
        ),
        default=0,
    )


def _has_residual_text(body: PivotBody) -> bool:
    return any(
        _expression_has_residual_text(expression) for expression in _expressions(body)
    )


def _expression_has_residual_text(expression: PivotExpression) -> bool:
    return any(
        isinstance(piece, PivotResidualText)
        or (
            isinstance(piece, (PivotCall, PivotFixedCall))
            and any(
                _expression_has_residual_text(argument) for argument in piece.arguments
            )
        )
        for piece in expression.pieces
    )


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _build_record(
    result: PivotBodyBuildResult,
    *,
    spans: bool,
    source_root: Path | None = None,
) -> object:
    if result.body is None:
        return {
            "unsupported": [
                (
                    reason.code,
                    reason.message,
                    reason.phase,
                    _span(reason.source, source_root) if spans else None,
                )
                for reason in result.unsupported
            ]
        }
    body = result.body
    return {
        "language": body.language.value,
        "parameters": [
            _binding(item, spans=spans, source_root=source_root)
            for item in body.parameters
        ],
        "statements": [
            (
                {
                    "local": _binding(
                        statement.binding,
                        spans=spans,
                        source_root=source_root,
                    ),
                    "mutable": statement.mutable,
                    "value": _expression(
                        statement.initializer,
                        spans=spans,
                        source_root=source_root,
                    ),
                    "source": (
                        _span(statement.source, source_root) if spans else None
                    ),
                }
                if isinstance(statement, PivotLocal)
                else {
                    "residual": _expression(
                        statement.expression,
                        spans=spans,
                        source_root=source_root,
                    ),
                    "source": (
                        _span(statement.source, source_root) if spans else None
                    ),
                }
            )
            for statement in body.statements
        ],
        "result": _expression(
            body.result.value,
            spans=spans,
            source_root=source_root,
        ),
        "result_source": _span(body.result.source, source_root) if spans else None,
        "requires_unsafe": body.requires_unsafe,
        "source": _span(body.source, source_root) if spans else None,
    }


def _binding(
    value: PivotBinding,
    *,
    spans: bool,
    source_root: Path | None,
) -> object:
    return (
        value.identity.ordinal,
        value.authored_name,
        _span(value.source, source_root) if spans else None,
    )


def _expression(
    value: PivotExpression,
    *,
    spans: bool,
    source_root: Path | None,
) -> object:
    pieces: list[object] = []
    for piece in value.pieces:
        if isinstance(piece, PivotResidualText):
            pieces.append(
                (
                    "text",
                    piece.text,
                    _span(piece.source, source_root) if spans else None,
                )
            )
            continue
        if isinstance(piece, PivotFixedCall):
            pieces.append(
                {
                    "fixed_call": (piece.callable_name, piece.vector_type),
                    "arguments": [
                        _expression(
                            argument,
                            spans=spans,
                            source_root=source_root,
                        )
                        for argument in piece.arguments
                    ],
                    "source": _span(piece.source, source_root) if spans else None,
                }
            )
            continue
        target = piece.dependency.target
        pieces.append(
            {
                "call": (
                    piece.dependency.primitive,
                    piece.dependency.mask_policy,
                    _call_vector_reference(piece.dependency.source),
                    None
                    if target is None
                    else _call_vector_reference(target),
                ),
                "attrs": piece.attrs,
                "requires_unsafe": piece.requires_unsafe,
                "arguments": [
                    _expression(
                        argument,
                        spans=spans,
                        source_root=source_root,
                    )
                    for argument in piece.arguments
                ],
                "source": _span(piece.source, source_root) if spans else None,
            }
        )
    return {
        "pieces": pieces,
        "source": _span(value.source, source_root) if spans else None,
    }


def _call_vector_reference(
    reference: CallVectorReference,
) -> tuple[object, ...]:
    if isinstance(reference, VectorIdentity):
        return (reference.base_tag, reference.extension_isa)
    if isinstance(reference, GenericVectorReference):
        return ("generic", reference.parameter_name, reference.base_tag)
    raise TypeError("unknown compiler call-vector reference")


def _span(value: SourceSpan | None, source_root: Path | None) -> object:
    if value is None:
        return None
    path = value.path
    if source_root is not None and path.is_absolute():
        try:
            path = path.resolve().relative_to(source_root)
        except ValueError as exc:
            raise ValueError(
                f"PIVOT body source {path} is outside digest root {source_root}"
            ) from exc
    return (
        path.as_posix(),
        value.line,
        value.column,
        value.end_line,
        value.end_column,
    )


__all__ = (
    "PivotBinding",
    "PivotBindingId",
    "PivotBody",
    "PivotBodyBuildResult",
    "PivotCall",
    "PivotExpression",
    "PivotFinalResult",
    "PivotFixedCall",
    "PivotLocal",
    "PivotResidualStatementSequence",
    "PivotResidualText",
    "PivotBodyCategory",
    "PivotBodyCensus",
    "PivotBodyEntry",
    "PivotBodyOrigin",
    "PivotUnsupported",
    "classify_body_trace",
    "pivot_body_census_digest",
    "pivot_body_census_location_digest",
    "pivot_body_trace_semantic_digest",
)
