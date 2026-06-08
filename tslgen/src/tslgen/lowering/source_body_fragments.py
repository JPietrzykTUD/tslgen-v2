"""Semantic adapters over recursive TSIL source-body fragments."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
    BodyToken,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.model import BackendIntrinsicRequest
from tslgen.lowering.primitive_call_fragments import (
    ExactPrimitiveCallFragment,
    PrimitiveCallFragmentAdaptationResult,
    PrimitiveCallFragmentText,
    adapt_exact_primitive_call_fragment,
)
from tslgen.syntax.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    SourceBodyFragmentScanResult,
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import (
    SourceBodyKeyword,
    SourceBodyLexicalScanResult,
    SourceBodyText,
)


SourceBodyFragmentLoweringResult = SourceBodyFragmentScanResult


@dataclass(frozen=True, slots=True)
class BackendIntrinsicKeywordRequest:
    fragment: KeywordRegionFragment
    request: BackendIntrinsicRequest


@dataclass(frozen=True, slots=True)
class BackendIntrinsicKeywordRequestExtractionResult:
    requests: tuple[BackendIntrinsicKeywordRequest, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveCallKeywordDirective:
    fragment: KeywordRegionFragment
    directive: LowerableDirective


@dataclass(frozen=True, slots=True)
class PrimitiveCallKeywordDirectiveExtractionResult:
    directives: tuple[PrimitiveCallKeywordDirective, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class PayloadTokenFragmentSequenceResult:
    tokens: tuple[RawStringToken | LowerableDirective, ...]
    diagnostics: tuple[Diagnostic, ...]


def lower_source_body_fragments(
    source: SourceBodyText | SourceBodyLexicalScanResult,
) -> SourceBodyFragmentLoweringResult:
    return fragment_source_body_text(source)


def payload_tokens_from_fragment_sequence(
    sequence: SourceBodyFragmentSequence,
) -> tuple[RawStringToken | LowerableDirective, ...]:
    return payload_token_result_from_fragment_sequence(sequence).tokens


def payload_token_result_from_fragment_sequence(
    sequence: SourceBodyFragmentSequence,
) -> PayloadTokenFragmentSequenceResult:
    tokens: list[RawStringToken | LowerableDirective] = []
    diagnostics: list[Diagnostic] = []
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            tokens.append(
                RawStringToken(text=fragment.span.text, source=fragment.span.start)
            )
            continue

        if fragment.keyword is SourceBodyKeyword.CALL:
            result = _primitive_call_directive(fragment)
            if result.directive is not None:
                tokens.append(result.directive)
                continue
            diagnostics.extend(result.diagnostics)

        tokens.append(
            RawStringToken(
                text=fragment.source_region.full_span.text,
                source=fragment.source_region.full_span.start,
            )
        )
    return PayloadTokenFragmentSequenceResult(
        tokens=tuple(tokens),
        diagnostics=tuple(diagnostics),
    )


def compatibility_body_token_result_from_fragment_sequence(
    sequence: SourceBodyFragmentSequence,
) -> PayloadTokenFragmentSequenceResult:
    """Build temporary body tokens for pre-fragment generation-region models.

    This adapter is retirement debt for result models that still carry
    ``BodyToken`` tuples. Production discovery should prefer recursive
    fragments; this function only preserves already accepted token consumers
    while M254.x removes ``ImplementationBody`` dependencies.
    """

    tokens: list[BodyToken] = []
    diagnostics: list[Diagnostic] = []
    _append_compatibility_body_tokens(sequence, tokens, diagnostics)
    return PayloadTokenFragmentSequenceResult(
        tokens=tuple(
            token
            for token in tokens
            if isinstance(token, RawStringToken | LowerableDirective)
        ),
        diagnostics=tuple(diagnostics),
    )


def extract_primitive_call_directives(
    sequence: SourceBodyFragmentSequence,
) -> PrimitiveCallKeywordDirectiveExtractionResult:
    directives: list[PrimitiveCallKeywordDirective] = []
    diagnostics: list[Diagnostic] = []
    _collect_primitive_call_directives(sequence, directives, diagnostics)
    return PrimitiveCallKeywordDirectiveExtractionResult(
        directives=tuple(directives),
        diagnostics=tuple(diagnostics),
    )


def _append_compatibility_body_tokens(
    sequence: SourceBodyFragmentSequence,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            tokens.append(
                RawStringToken(text=fragment.span.text, source=fragment.span.start)
            )
            continue

        _append_keyword_compatibility_tokens(fragment, tokens, diagnostics)


def _append_keyword_compatibility_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    if fragment.keyword is SourceBodyKeyword.CALL:
        result = _primitive_call_directive(fragment)
        if result.directive is None:
            diagnostics.extend(result.diagnostics)
            _append_raw_keyword_fragment(fragment, tokens)
        else:
            tokens.append(result.directive)
        return

    if fragment.keyword is SourceBodyKeyword.EMIT_RETURN:
        _append_emit_return_compatibility_tokens(fragment, tokens, diagnostics)
        return

    if fragment.keyword is SourceBodyKeyword.IF:
        _append_if_compatibility_tokens(fragment, tokens, diagnostics)
        return

    if fragment.keyword is SourceBodyKeyword.ELSE:
        _append_else_compatibility_tokens(fragment, tokens, diagnostics)
        return

    if fragment.keyword is SourceBodyKeyword.LOOP:
        _append_loop_compatibility_tokens(fragment, tokens, diagnostics)
        return

    _append_raw_keyword_fragment(fragment, tokens)


def _append_emit_return_compatibility_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    region = fragment.source_region
    if region.payload is None:
        _append_raw_keyword_fragment(fragment, tokens)
        return

    payload_result = (
        compatibility_body_token_result_from_fragment_sequence(fragment.payload_fragments)
        if fragment.payload_fragments is not None
        else PayloadTokenFragmentSequenceResult(tokens=(), diagnostics=())
    )
    diagnostics.extend(payload_result.diagnostics)
    tokens.append(
        LowerableDirective(
            name="emit_return",
            arguments=(region.payload.payload_span.text,),
            source=region.full_span.start,
            payload_tokens=payload_result.tokens,
        )
    )


def _append_if_compatibility_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    region = fragment.source_region
    if region.selector is None or region.payload is None or region.body is None:
        _append_raw_keyword_fragment(fragment, tokens)
        return

    tokens.append(
        LowerableDirective(
            name="if",
            arguments=(
                region.selector.payload_span.text.strip(),
                region.payload.payload_span.text,
            ),
            source=region.full_span.start,
        )
    )
    _append_braced_body_tokens(fragment, tokens, diagnostics)


def _append_else_compatibility_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    region = fragment.source_region
    if region.selector is None or region.body is None:
        _append_raw_keyword_fragment(fragment, tokens)
        return

    tokens.append(
        LowerableDirective(
            name="else",
            arguments=(region.selector.payload_span.text.strip(),),
            source=region.full_span.start,
        )
    )
    _append_braced_body_tokens(fragment, tokens, diagnostics)


def _append_loop_compatibility_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    region = fragment.source_region
    if region.selector is None or region.payload is None:
        _append_raw_keyword_fragment(fragment, tokens)
        return

    selector = region.selector.payload_span.text.strip()
    tokens.append(
        LowerableDirective(
            name="loop",
            arguments=(selector, region.payload.payload_span.text),
            source=region.full_span.start,
        )
    )
    if region.body is not None:
        _append_braced_body_tokens(fragment, tokens, diagnostics)


def _append_braced_body_tokens(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
    diagnostics: list[Diagnostic],
) -> None:
    body = fragment.source_region.body
    if body is None:
        _append_raw_keyword_fragment(fragment, tokens)
        return

    tokens.append(RawStringToken(text="{", source=body.full_span.start))
    if fragment.body_fragments is not None:
        _append_compatibility_body_tokens(fragment.body_fragments, tokens, diagnostics)
    tokens.append(
        RawStringToken(
            text="}",
            source=_span_location_at(body.full_span, len(body.full_span.text) - 1),
        )
    )


def _append_raw_keyword_fragment(
    fragment: KeywordRegionFragment,
    tokens: list[BodyToken],
) -> None:
    region = fragment.source_region
    tokens.append(
        RawStringToken(
            text=region.full_span.text,
            source=region.full_span.start,
        )
    )


def _span_location_at(span, offset: int):
    return SourceBodyText.from_span(span).source_at(offset)


def extract_intrin_compose_requests(
    sequence: SourceBodyFragmentSequence,
) -> BackendIntrinsicKeywordRequestExtractionResult:
    requests: list[BackendIntrinsicKeywordRequest] = []
    diagnostics: list[Diagnostic] = []
    _collect_intrin_compose_requests(sequence, requests, diagnostics)
    return BackendIntrinsicKeywordRequestExtractionResult(
        requests=tuple(requests),
        diagnostics=tuple(diagnostics),
    )


def _collect_intrin_compose_requests(
    sequence: SourceBodyFragmentSequence,
    requests: list[BackendIntrinsicKeywordRequest],
    diagnostics: list[Diagnostic],
) -> None:
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            continue

        if fragment.keyword is SourceBodyKeyword.INTRIN_COMPOSE:
            request = _intrin_compose_request(fragment)
            if isinstance(request, Diagnostic):
                diagnostics.append(request)
            else:
                requests.append(
                    BackendIntrinsicKeywordRequest(
                        fragment=fragment,
                        request=request,
                    )
                )

        for child_sequence in (
            fragment.selector_fragments,
            fragment.payload_fragments,
            fragment.body_fragments,
        ):
            if child_sequence is not None:
                _collect_intrin_compose_requests(
                    child_sequence,
                    requests,
                    diagnostics,
                )


def _collect_primitive_call_directives(
    sequence: SourceBodyFragmentSequence,
    directives: list[PrimitiveCallKeywordDirective],
    diagnostics: list[Diagnostic],
) -> None:
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            continue

        if fragment.keyword is SourceBodyKeyword.CALL:
            result = _primitive_call_directive(fragment)
            if result.directive is None:
                diagnostics.extend(result.diagnostics)
            else:
                directives.append(
                    PrimitiveCallKeywordDirective(
                        fragment=fragment,
                        directive=result.directive,
                    )
                )

        for child_sequence in (
            fragment.selector_fragments,
            fragment.payload_fragments,
            fragment.body_fragments,
        ):
            if child_sequence is not None:
                _collect_primitive_call_directives(
                    child_sequence,
                    directives,
                    diagnostics,
                )


def _intrin_compose_request(
    fragment: KeywordRegionFragment,
) -> BackendIntrinsicRequest | Diagnostic:
    region = fragment.source_region
    if region.selector is None:
        return _malformed_intrin_compose_fragment_diagnostic(
            fragment,
            "a balanced angle selector is required",
        )
    if region.payload is None:
        return _malformed_intrin_compose_fragment_diagnostic(
            fragment,
            "a balanced parenthesized argument payload is required",
        )

    return BackendIntrinsicRequest(
        intrinsic_kind="intrin_compose",
        angle_payload_text=region.selector.payload_span.text,
        angle_payload_source=region.selector.payload_span.start,
        argument_text=region.payload.payload_span.text,
        argument_source=region.payload.payload_span.start,
        source_text=region.full_span.text,
        source=region.full_span.start,
    )


def _malformed_intrin_compose_fragment_diagnostic(
    fragment: KeywordRegionFragment,
    reason: str,
) -> Diagnostic:
    region = fragment.source_region
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-INTRIN-COMPOSE-FRAGMENT-MALFORMED",
        message=(
            "intrin_compose keyword fragment cannot be adapted to a backend "
            f"intrinsic request: {reason}"
        ),
        location=region.head_span.start,
    )


def _primitive_call_directive(
    fragment: KeywordRegionFragment,
) -> PrimitiveCallFragmentAdaptationResult:
    region = fragment.source_region
    if region.selector is None:
        return PrimitiveCallFragmentAdaptationResult(
            directive=None,
            diagnostics=(
                _malformed_primitive_call_fragment_diagnostic(
                    fragment,
                    "a balanced angle selector is required",
                ),
            ),
        )
    if region.payload is None:
        return PrimitiveCallFragmentAdaptationResult(
            directive=None,
            diagnostics=(
                _malformed_primitive_call_fragment_diagnostic(
                    fragment,
                    "a balanced parenthesized argument payload is required",
                ),
            ),
        )

    return adapt_exact_primitive_call_fragment(
        ExactPrimitiveCallFragment(
            source=region.full_span.start,
            selector_payload=PrimitiveCallFragmentText.from_source(
                region.selector.payload_span.text,
                region.selector.payload_span.start,
            ),
            argument_payload=PrimitiveCallFragmentText.from_source(
                region.payload.payload_span.text,
                region.payload.payload_span.start,
            ),
        )
    )


def _malformed_primitive_call_fragment_diagnostic(
    fragment: KeywordRegionFragment,
    reason: str,
) -> Diagnostic:
    region = fragment.source_region
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED",
        message=(
            "call keyword fragment cannot be adapted to a primitive-call "
            f"directive: {reason}"
        ),
        location=region.head_span.start,
    )
