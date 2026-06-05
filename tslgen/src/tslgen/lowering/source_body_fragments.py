"""Recursive TSIL keyword-region fragments over M230 lexical regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
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
from tslgen.syntax.source_body_regions import (
    SourceBodyDelimitedSpan,
    SourceBodyKeyword,
    SourceBodyLexicalRegionCandidate,
    SourceBodyLexicalScanResult,
    SourceBodyRawSegment,
    SourceBodySpan,
    SourceBodyText,
    scan_source_body_text,
)


@dataclass(frozen=True, slots=True)
class RawSourceFragment:
    source_order: int
    span: SourceBodySpan


@dataclass(frozen=True, slots=True)
class KeywordRegionFragment:
    source_order: int
    source_region: SourceBodyLexicalRegionCandidate
    selector_fragments: SourceBodyFragmentSequence | None = None
    payload_fragments: SourceBodyFragmentSequence | None = None
    body_fragments: SourceBodyFragmentSequence | None = None

    @property
    def keyword(self) -> SourceBodyKeyword:
        return self.source_region.head.keyword


SourceBodyFragment: TypeAlias = RawSourceFragment | KeywordRegionFragment


@dataclass(frozen=True, slots=True)
class SourceBodyFragmentSequence:
    source_text: SourceBodyText
    fragments: tuple[SourceBodyFragment, ...]

    @property
    def raw_fragments(self) -> tuple[RawSourceFragment, ...]:
        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, RawSourceFragment)
        )

    @property
    def keyword_fragments(self) -> tuple[KeywordRegionFragment, ...]:
        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, KeywordRegionFragment)
        )


@dataclass(frozen=True, slots=True)
class SourceBodyFragmentLoweringResult:
    sequence: SourceBodyFragmentSequence
    diagnostics: tuple[Diagnostic, ...]


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


def lower_source_body_fragments(
    source: SourceBodyText | SourceBodyLexicalScanResult,
) -> SourceBodyFragmentLoweringResult:
    scan_result = (
        source if isinstance(source, SourceBodyLexicalScanResult) else scan_source_body_text(source)
    )
    sequence, diagnostics = _fragment_sequence_from_scan(scan_result)
    return SourceBodyFragmentLoweringResult(
        sequence=sequence,
        diagnostics=diagnostics,
    )


def payload_tokens_from_fragment_sequence(
    sequence: SourceBodyFragmentSequence,
) -> tuple[RawStringToken | LowerableDirective, ...]:
    tokens: list[RawStringToken | LowerableDirective] = []
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

        tokens.append(
            RawStringToken(
                text=fragment.source_region.full_span.text,
                source=fragment.source_region.full_span.start,
            )
        )
    return tuple(tokens)


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


def _fragment_sequence_from_scan(
    scan_result: SourceBodyLexicalScanResult,
) -> tuple[SourceBodyFragmentSequence, tuple[Diagnostic, ...]]:
    fragments: list[SourceBodyFragment] = []
    diagnostics: list[Diagnostic] = list(scan_result.diagnostics)

    for item in scan_result.items:
        if isinstance(item, SourceBodyRawSegment):
            fragments.append(
                RawSourceFragment(
                    source_order=item.source_order,
                    span=item.span,
                )
            )
            continue

        selector_fragments, selector_diagnostics = _child_fragments(item.selector)
        diagnostics.extend(selector_diagnostics)
        payload_fragments, payload_diagnostics = _child_fragments(item.payload)
        diagnostics.extend(payload_diagnostics)
        body_fragments, body_diagnostics = _child_fragments(item.body)
        diagnostics.extend(body_diagnostics)

        fragments.append(
            KeywordRegionFragment(
                source_order=item.source_order,
                source_region=item,
                selector_fragments=selector_fragments,
                payload_fragments=payload_fragments,
                body_fragments=body_fragments,
            )
        )

    return (
        SourceBodyFragmentSequence(
            source_text=scan_result.source_text,
            fragments=tuple(fragments),
        ),
        tuple(diagnostics),
    )


def _child_fragments(
    span: SourceBodyDelimitedSpan | None,
) -> tuple[SourceBodyFragmentSequence | None, tuple[Diagnostic, ...]]:
    if span is None:
        return None, ()
    child_scan = scan_source_body_text(SourceBodyText.from_span(span.payload_span))
    return _fragment_sequence_from_scan(child_scan)


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
