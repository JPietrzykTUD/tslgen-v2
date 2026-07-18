"""Convert captured lowering streams into immutable PIVOT body values."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.diagnostics import SourceSpan
from tslc.target_text import (
    LiteralText,
    LoweredBody,
    RenderPlaceholder,
    RenderSequence,
    RenderText,
    TemplateApplication,
    TemplateRenderError,
    TrimmedText,
    UnsafeBlockText,
)
from tslc_pivot.body_ir import (
    PivotBinding,
    PivotBindingId,
    PivotBody,
    PivotBodyBuildResult,
    PivotCall,
    PivotExpression,
    PivotExpressionPiece,
    PivotFinalResult,
    PivotFixedCall,
    PivotLocal,
    PivotResidualStatementSequence,
    PivotResidualText,
    PivotUnsupported,
)
from tslc_pivot.model import PivotLanguage
from tslc_pivot.lowering_capture import (
    CAPTURE_CLOSE,
    CAPTURE_OPEN,
    PivotCapturedCall,
    PivotBodyCapture,
    PivotCapturedResult,
    PivotCapturedLocal,
    PivotCaptureNode,
    parse_capture_token,
)


type _DecodedPiece = str | PivotCaptureNode


class _BodyBuildError(ValueError):
    def __init__(self, unsupported: PivotUnsupported) -> None:
        super().__init__(unsupported.message)
        self.unsupported = unsupported


def build_pivot_body(
    language: PivotLanguage,
    lowered: LoweredBody,
    capture: PivotBodyCapture,
    source: SourceSpan | None,
    *,
    alternative_sources: tuple[SourceSpan, ...] = (),
) -> PivotBodyBuildResult:
    """Build a body body without rendering compiler-added unsafe framing."""

    try:
        nodes = _capture_nodes(capture, source, alternative_sources)
        seen: set[str] = set()
        pieces = _decode_render_text(lowered.content, nodes, seen, source)
        statements: list[PivotLocal | PivotResidualStatementSequence] = []
        residual: list[_DecodedPiece] = []
        result: PivotFinalResult | None = None

        for piece in pieces:
            if result is not None:
                if isinstance(piece, str) and not piece.strip():
                    continue
                if isinstance(piece, PivotCapturedResult):
                    raise _failure(
                        "TSL-PIVOT-BODY-DUPLICATE-COMPLETE",
                        "PIVOT body body contains more than one complete(...) result",
                        piece.source or source,
                    )
                raise _failure(
                    "TSL-PIVOT-BODY-NONFINAL-COMPLETE",
                    "PIVOT complete(...) must be the final body item",
                    source,
                )
            if isinstance(piece, PivotCapturedLocal):
                _flush_residual(statements, residual, nodes, seen, source)
                initializer = _expression_from_render_text(
                    piece.initializer,
                    nodes,
                    seen,
                    piece.source or source,
                )
                statements.append(
                    PivotLocal(
                        binding=piece.binding,
                        initializer=initializer,
                        mutable=piece.mutable,
                        source=piece.source,
                    )
                )
                continue
            if isinstance(piece, PivotCapturedResult):
                _flush_residual(statements, residual, nodes, seen, source)
                result = PivotFinalResult(
                    _expression_from_render_text(
                        piece.value,
                        nodes,
                        seen,
                        piece.source or source,
                    ),
                    piece.source,
                )
                continue
            residual.append(piece)

        _flush_residual(statements, residual, nodes, seen, source)
        if result is None:
            raise _failure(
                "TSL-PIVOT-BODY-NO-COMPLETE",
                "PIVOT body body has no typed final complete(...) result",
                source,
            )
        _ensure_all_captures_consumed(nodes, seen, source)
        return PivotBodyBuildResult(
            body=PivotBody(
                language=language,
                parameters=capture.parameters,
                statements=tuple(statements),
                result=result,
                requires_unsafe=(
                    lowered.requires_unsafe
                    or _contains_unsafe(lowered.content)
                    or result.value.requires_unsafe
                    or any(
                        (
                            statement.initializer
                            if isinstance(statement, PivotLocal)
                            else statement.expression
                        ).requires_unsafe
                        for statement in statements
                    )
                ),
                source=source,
            )
        )
    except _BodyBuildError as exc:
        return PivotBodyBuildResult(unsupported=(exc.unsupported,))


def synthetic_pivot_body(
    language: PivotLanguage,
    parameter_names: tuple[str, ...],
    callable_name: str,
    vector_type: str,
    source: SourceSpan | None,
) -> PivotBodyBuildResult:
    parameters = tuple(
        PivotBinding(PivotBindingId(index), name, source)
        for index, name in enumerate(parameter_names)
    )
    try:
        arguments = tuple(
            _normalize_expression((name,), source) for name in parameter_names
        )
        expression = PivotExpression(
            (
                PivotFixedCall(
                    callable_name=callable_name,
                    vector_type=vector_type,
                    arguments=arguments,
                    source=source,
                ),
            ),
            source,
        )
    except _BodyBuildError as exc:
        return PivotBodyBuildResult(unsupported=(exc.unsupported,))
    return PivotBodyBuildResult(
        body=PivotBody(
            language=language,
            parameters=parameters,
            statements=(),
            result=PivotFinalResult(expression, source),
            requires_unsafe=False,
            source=source,
        )
    )


def _flush_residual(
    statements: list[PivotLocal | PivotResidualStatementSequence],
    residual: list[_DecodedPiece],
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> None:
    if not residual:
        return
    if all(isinstance(piece, str) and not piece.strip() for piece in residual):
        residual.clear()
        return
    expression = _expression_from_decoded(residual, nodes, seen, source)
    statements.append(PivotResidualStatementSequence(expression, source))
    residual.clear()


def _expression_from_render_text(
    value: RenderText,
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> PivotExpression:
    return _expression_from_decoded(
        _decode_render_text(value, nodes, seen, source),
        nodes,
        seen,
        source,
    )


def _expression_from_decoded(
    decoded: Iterable[_DecodedPiece],
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> PivotExpression:
    pieces: list[PivotExpressionPiece | str] = []
    for piece in decoded:
        if isinstance(piece, str):
            pieces.append(piece)
            continue
        if isinstance(piece, PivotCapturedCall):
            arguments = tuple(
                _expression_from_render_text(
                    argument,
                    nodes,
                    seen,
                    piece.source or source,
                )
                for argument in piece.arguments
            )
            pieces.append(
                PivotCall(
                    dependency=piece.dependency,
                    attrs=piece.attrs,
                    arguments=arguments,
                    source=piece.source,
                    requires_unsafe=piece.requires_unsafe,
                )
            )
            continue
        kind = (
            "local declaration"
            if isinstance(piece, PivotCapturedLocal)
            else "complete"
        )
        raise _failure(
            "TSL-PIVOT-BODY-NESTED-STATEMENT",
            f"PIVOT found a typed {kind} in expression position",
            piece.source or source,
        )
    return _normalize_expression(pieces, source)


def _normalize_expression(
    pieces: Iterable[PivotExpressionPiece | str],
    source: SourceSpan | None,
) -> PivotExpression:
    normalized: list[PivotExpressionPiece] = []
    pending_text = ""
    for piece in pieces:
        if isinstance(piece, str):
            pending_text += piece
            continue
        if pending_text:
            normalized.append(PivotResidualText(pending_text, source))
            pending_text = ""
        normalized.append(piece)
    if pending_text:
        normalized.append(PivotResidualText(pending_text, source))

    if normalized and isinstance(normalized[0], PivotResidualText):
        text = normalized[0].text.lstrip()
        if text:
            normalized[0] = PivotResidualText(text, normalized[0].source)
        else:
            normalized.pop(0)
    if normalized and isinstance(normalized[-1], PivotResidualText):
        text = normalized[-1].text.rstrip()
        if text:
            normalized[-1] = PivotResidualText(text, normalized[-1].source)
        else:
            normalized.pop()
    if not normalized:
        raise _failure(
            "TSL-PIVOT-BODY-EMPTY-EXPRESSION",
            "PIVOT captured an empty expression",
            source,
        )
    return PivotExpression(tuple(normalized), source)


def _capture_nodes(
    capture: PivotBodyCapture,
    source: SourceSpan | None,
    alternative_sources: tuple[SourceSpan, ...],
) -> dict[str, PivotCaptureNode]:
    nodes: dict[str, PivotCaptureNode] = {}
    tokens: set[str] = set()
    ordinals: set[int] = set()
    for node in capture.nodes:
        token = node.token
        kind = (
            "call"
            if isinstance(node, PivotCapturedCall)
            else "local"
            if isinstance(node, PivotCapturedLocal)
            else "complete"
        )
        parsed = parse_capture_token(token)
        if (
            parsed is None
            or parsed[:2] != (capture.namespace, kind)
            or parsed[2] in ordinals
        ):
            raise _failure(
                "TSL-PIVOT-BODY-MALFORMED-CAPTURE",
                "PIVOT lowering produced a malformed reserved capture token",
                node.source or source,
            )
        ordinal = parsed[2]
        ordinals.add(ordinal)
        if token in tokens:
            raise _failure(
                "TSL-PIVOT-BODY-DUPLICATE-CAPTURE",
                "PIVOT lowering produced duplicate reserved capture tokens",
                node.source or source,
            )
        tokens.add(token)
        if (
            source is not None
            and node.source is not None
            and not _span_contains(source, node.source)
        ):
            if any(_span_contains(span, node.source) for span in alternative_sources):
                # Lowerer also lowers implementation variants, while this
                # adapter consumes the default ``LoweredSpecialization.body``.
                continue
            raise _failure(
                "TSL-PIVOT-BODY-OUT-OF-BODY-CAPTURE",
                "PIVOT lowering captured a typed node outside the selected body",
                node.source,
            )
        nodes[token] = node
    if ordinals != set(range(len(capture.nodes))):
        raise _failure(
            "TSL-PIVOT-BODY-MALFORMED-CAPTURE",
            "PIVOT lowering produced a non-contiguous capture ordinal set",
            source,
        )
    return nodes


def _span_contains(container: SourceSpan, child: SourceSpan) -> bool:
    if container.path != child.path:
        return False
    start = (container.line, container.column)
    end = (container.end_line, container.end_column)
    child_start = (child.line, child.column)
    child_end = (child.end_line, child.end_column)
    return start <= child_start and child_end <= end


def _decode_render_text(
    value: RenderText,
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> tuple[_DecodedPiece, ...]:
    """Walk the lockstep compiler render family without flattening PIVOT nodes."""

    if isinstance(
        value,
        (PivotCapturedCall, PivotCapturedLocal, PivotCapturedResult),
    ):
        _consume_node(value, nodes, seen, source)
        return (value,)
    if isinstance(value, LiteralText):
        return _decode(value.text, nodes, seen, source)
    if isinstance(value, RenderPlaceholder):
        return _decode(value.render(), nodes, seen, source)
    if isinstance(value, RenderSequence):
        return tuple(
            piece
            for part in value.parts
            for piece in _decode_render_text(part, nodes, seen, source)
        )
    if isinstance(value, TrimmedText):
        return _trim_decoded(
            _decode_render_text(value.content, nodes, seen, source)
        )
    if isinstance(value, UnsafeBlockText):
        return _decode_render_text(value.content, nodes, seen, source)
    if isinstance(value, TemplateApplication):
        pieces: list[_DecodedPiece] = []
        for segment in value.segments:
            if isinstance(segment, str):
                pieces.extend(_decode(segment, nodes, seen, source))
                continue
            name = getattr(segment, "name", None)
            if not isinstance(name, str) or name not in value.fields:
                raise _failure(
                    "TSL-PIVOT-BODY-MALFORMED-TEMPLATE",
                    f"PIVOT cannot adapt unresolved template {value.key!r}",
                    source,
                )
            field = value.fields[name]
            pieces.extend(
                _decode(field, nodes, seen, source)
                if isinstance(field, str)
                else _decode_render_text(field, nodes, seen, source)
            )
        try:
            value.render()
        except TemplateRenderError as exc:
            raise _failure(
                "TSL-PIVOT-BODY-MALFORMED-TEMPLATE",
                str(exc),
                source,
            ) from exc
        return tuple(pieces)
    raise _failure(
        "TSL-PIVOT-BODY-UNKNOWN-RENDER-TEXT",
        "PIVOT body contains an unsupported compiler render value",
        source,
    )


def _contains_unsafe(value: RenderText) -> bool:
    if isinstance(value, UnsafeBlockText):
        return True
    if isinstance(value, RenderSequence):
        return any(_contains_unsafe(part) for part in value.parts)
    if isinstance(value, TrimmedText):
        return _contains_unsafe(value.content)
    if isinstance(value, TemplateApplication):
        return any(
            not isinstance(field, str) and _contains_unsafe(field)
            for segment in value.segments
            if not isinstance(segment, str)
            if isinstance((name := getattr(segment, "name", None)), str)
            if (field := value.fields.get(name)) is not None
        )
    if isinstance(value, PivotCapturedCall):
        return value.requires_unsafe or any(
            _contains_unsafe(argument) for argument in value.arguments
        )
    if isinstance(value, PivotCapturedLocal):
        return _contains_unsafe(value.initializer)
    if isinstance(value, PivotCapturedResult):
        return _contains_unsafe(value.value)
    return False


def _consume_node(
    node: PivotCaptureNode,
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> None:
    if nodes.get(node.token) is not node:
        raise _failure(
            "TSL-PIVOT-BODY-FOREIGN-CAPTURE",
            "PIVOT render node belongs to a different lowering capture",
            node.source or source,
        )
    if node.token in seen:
        raise _failure(
            "TSL-PIVOT-BODY-REPEATED-CAPTURE",
            "PIVOT render stream repeats a capture token",
            node.source or source,
        )
    seen.add(node.token)


def _ensure_all_captures_consumed(
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> None:
    missing = next((token for token in nodes if token not in seen), None)
    if missing is None:
        return
    node = nodes[missing]
    raise _failure(
        "TSL-PIVOT-BODY-UNCONSUMED-CAPTURE",
        "PIVOT lowering captured a typed node that was lost from the render stream",
        node.source or source,
    )


def _trim_decoded(pieces: tuple[_DecodedPiece, ...]) -> tuple[_DecodedPiece, ...]:
    result = list(pieces)
    while result and isinstance(result[0], str):
        text = result[0].lstrip()
        if text:
            result[0] = text
            break
        result.pop(0)
    while result and isinstance(result[-1], str):
        text = result[-1].rstrip()
        if text:
            result[-1] = text
            break
        result.pop()
    return tuple(result)


def _decode(
    text: str,
    nodes: dict[str, PivotCaptureNode],
    seen: set[str],
    source: SourceSpan | None,
) -> tuple[_DecodedPiece, ...]:
    pieces: list[_DecodedPiece] = []
    cursor = 0
    while cursor < len(text):
        opening = text.find(CAPTURE_OPEN, cursor)
        stray_sentinel = text.find(CAPTURE_CLOSE, cursor)
        if stray_sentinel != -1 and stray_sentinel != opening:
            raise _failure(
                "TSL-PIVOT-BODY-MALFORMED-CAPTURE",
                "PIVOT render stream contains an unexpected capture sentinel",
                source,
            )
        if opening == -1:
            tail = text[cursor:]
            if CAPTURE_CLOSE in tail:
                raise _failure(
                    "TSL-PIVOT-BODY-MALFORMED-CAPTURE",
                    "PIVOT render stream contains a malformed capture delimiter",
                    source,
                )
            if tail:
                pieces.append(tail)
            break
        if opening > cursor:
            pieces.append(text[cursor:opening])
        closing = text.find(CAPTURE_CLOSE, opening + len(CAPTURE_OPEN))
        if closing == -1:
            raise _failure(
                "TSL-PIVOT-BODY-MALFORMED-CAPTURE",
                "PIVOT render stream contains an unterminated capture token",
                source,
            )
        token = text[opening : closing + len(CAPTURE_CLOSE)]
        node = nodes.get(token)
        if node is None:
            raise _failure(
                "TSL-PIVOT-BODY-UNKNOWN-CAPTURE",
                "PIVOT render stream refers to an unknown capture token",
                source,
            )
        _consume_node(node, nodes, seen, source)
        pieces.append(node)
        cursor = closing + len(CAPTURE_CLOSE)
    return tuple(pieces)


def _failure(code: str, message: str, source: SourceSpan | None) -> _BodyBuildError:
    return _BodyBuildError(PivotUnsupported(code, message, source))


__all__ = ("build_pivot_body", "synthetic_pivot_body")
