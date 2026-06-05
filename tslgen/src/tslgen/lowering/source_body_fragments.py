"""Recursive TSIL keyword-region fragments over M230 lexical regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    LowerableDirective,
    NamedPrimitiveReference,
    PrimitiveCall,
    PrimitiveCallArgument,
    PrimitiveCallSelector,
    RawStringToken,
    SelfPrimitiveReference,
)
from tslgen.lowering.model import BackendIntrinsicRequest
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
from tslgen.syntax.tsil_lexical import (
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    LexicalPart,
    matching_close,
    split_top_level_parts,
)

_PRIMITIVE_SELECTOR_PREFIX = "primitive="
_SELF_SELECTOR = "@self"


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
            directive = _primitive_call_directive(fragment)
            if not isinstance(directive, Diagnostic):
                tokens.append(directive)
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
            directive = _primitive_call_directive(fragment)
            if isinstance(directive, Diagnostic):
                diagnostics.append(directive)
            else:
                directives.append(
                    PrimitiveCallKeywordDirective(
                        fragment=fragment,
                        directive=directive,
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
) -> LowerableDirective | Diagnostic:
    region = fragment.source_region
    if region.selector is None:
        return _malformed_primitive_call_fragment_diagnostic(
            fragment,
            "a balanced angle selector is required",
        )
    if region.payload is None:
        return _malformed_primitive_call_fragment_diagnostic(
            fragment,
            "a balanced parenthesized argument payload is required",
        )

    selector_text = region.selector.payload_span.text
    selector = _selector_without_primitive_prefix(region.selector)
    if isinstance(selector, Diagnostic):
        return selector

    primitive_call = _primitive_call_from_region(fragment, selector)
    if isinstance(primitive_call, Diagnostic):
        return primitive_call

    return LowerableDirective(
        name="call",
        arguments=("primitive", selector_text[len(_PRIMITIVE_SELECTOR_PREFIX) :], region.payload.payload_span.text),
        source=region.full_span.start,
        primitive_call=primitive_call,
    )


def _primitive_call_from_region(
    fragment: KeywordRegionFragment,
    selector_text: str,
) -> PrimitiveCall | Diagnostic:
    region = fragment.source_region
    assert region.selector is not None
    assert region.payload is not None

    selector = _primitive_call_selector(region.selector, selector_text)
    if isinstance(selector, Diagnostic):
        return selector

    argument_parts = _primitive_call_argument_parts(region.payload)
    if argument_parts is None:
        return _malformed_primitive_call_fragment_diagnostic(
            fragment,
            "argument payload cannot be split at top-level comma boundaries",
        )

    payload_source = SourceBodyText.from_span(region.payload.payload_span)
    return PrimitiveCall(
        selector=selector,
        payload=region.payload.payload_span.text,
        source=region.full_span.start,
        arguments=tuple(
            PrimitiveCallArgument(
                text=argument.text,
                source=payload_source.source_at(argument.start),
            )
            for argument in argument_parts
        ),
    )


def _selector_without_primitive_prefix(
    selector: SourceBodyDelimitedSpan,
) -> str | Diagnostic:
    selector_text = selector.payload_span.text
    if not selector_text.startswith(_PRIMITIVE_SELECTOR_PREFIX):
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED",
            message=(
                "call keyword fragment cannot be adapted to a primitive-call "
                "directive: expected selector to start with 'primitive='"
            ),
            location=selector.payload_span.start,
        )
    value = selector_text[len(_PRIMITIVE_SELECTOR_PREFIX) :]
    if not value:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED",
            message=(
                "call keyword fragment cannot be adapted to a primitive-call "
                "directive: expected a primitive selector after 'primitive='"
            ),
            location=_selector_source_after_prefix(selector),
        )
    return value


def _primitive_call_selector(
    selector: SourceBodyDelimitedSpan,
    selector_text: str,
) -> PrimitiveCallSelector | Diagnostic:
    source = _selector_source_after_prefix(selector)
    parts = _parse_primitive_call_selector(selector_text)
    if parts is None:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED",
            message=(
                "call keyword fragment cannot be adapted to a primitive-call "
                f"directive: unsupported selector {selector_text!r}"
            ),
            location=source,
        )

    if parts.target_kind == "self":
        target = SelfPrimitiveReference(source=source)
    else:
        assert parts.target_name is not None
        target = NamedPrimitiveReference(name=parts.target_name, source=source)

    return PrimitiveCallSelector(
        target=target,
        specialization=parts.specialization,
        attrs=parts.attrs,
        source_text=selector_text,
        source=source,
    )


@dataclass(frozen=True, slots=True)
class _PrimitiveCallSelectorParts:
    target_kind: str
    target_name: str | None
    specialization: str | None
    attrs: str | None


def _parse_primitive_call_selector(
    selector: str,
) -> _PrimitiveCallSelectorParts | None:
    if selector != selector.strip():
        return None

    index = 0
    if selector.startswith(_SELF_SELECTOR):
        target_kind = "self"
        target_name = None
        index = len(_SELF_SELECTOR)
    else:
        target_name, index = _parse_identifier(selector, index)
        if target_name is None:
            return None
        target_kind = "named"

    specialization: str | None = None
    if index < len(selector) and selector[index] == "[":
        close_index = matching_close(selector, index, BRACKET_DELIMITER)
        if close_index is None:
            return None
        specialization = selector[index + 1 : close_index]
        index = close_index + 1

    attrs: str | None = None
    if index < len(selector):
        whitespace_start = index
        while index < len(selector) and selector[index].isspace():
            index += 1
        if index == whitespace_start:
            return None
        if not selector.startswith("attrs[", index):
            return None
        attrs_open_index = index + len("attrs")
        close_index = matching_close(selector, attrs_open_index, BRACKET_DELIMITER)
        if close_index is None:
            return None
        attrs = selector[attrs_open_index + 1 : close_index]
        index = close_index + 1

    if index != len(selector):
        return None

    return _PrimitiveCallSelectorParts(
        target_kind=target_kind,
        target_name=target_name,
        specialization=specialization,
        attrs=attrs,
    )


def _parse_identifier(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text):
        return None, start
    first = text[start]
    if not (first.isalpha() or first == "_"):
        return None, start

    index = start + 1
    while index < len(text) and (text[index].isalnum() or text[index] == "_"):
        index += 1
    return text[start:index], index


def _primitive_call_argument_parts(
    payload: SourceBodyDelimitedSpan,
) -> tuple[LexicalPart, ...] | None:
    return split_top_level_parts(
        payload.payload_span.text,
        delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER),
        allow_empty_payload=True,
    )


def _selector_source_after_prefix(selector: SourceBodyDelimitedSpan) -> SourceLocation:
    source_text = SourceBodyText.from_span(selector.payload_span)
    return source_text.source_at(len(_PRIMITIVE_SELECTOR_PREFIX))


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
