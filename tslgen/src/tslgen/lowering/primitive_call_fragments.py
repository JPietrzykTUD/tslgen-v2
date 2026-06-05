"""Shared exact primitive-call fragment adaptation."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    LowerableDirective,
    NamedPrimitiveReference,
    PrimitiveCall,
    PrimitiveCallArgument,
    PrimitiveCallSelector,
    SelfPrimitiveReference,
)
from tslgen.syntax.tsil_lexical import (
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    matching_close,
    split_top_level_parts,
)

_PRIMITIVE_SELECTOR_PREFIX = "primitive="
_SELF_SELECTOR = "@self"


@dataclass(frozen=True, slots=True)
class PrimitiveCallFragmentText:
    text: str
    source_locations: tuple[SourceLocation, ...]

    @classmethod
    def from_source(
        cls,
        text: str,
        source: SourceLocation,
    ) -> "PrimitiveCallFragmentText":
        return cls(
            text=text,
            source_locations=_source_locations_for_text(source, text),
        )

    def source_at(self, offset: int) -> SourceLocation:
        if offset < 0 or offset > len(self.text):
            raise ValueError("offset is outside primitive-call fragment text")
        return self.source_locations[offset]


@dataclass(frozen=True, slots=True)
class ExactPrimitiveCallFragment:
    source: SourceLocation
    selector_payload: PrimitiveCallFragmentText
    argument_payload: PrimitiveCallFragmentText


@dataclass(frozen=True, slots=True)
class PrimitiveCallFragmentAdaptationResult:
    directive: LowerableDirective | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _PrimitiveCallSelectorParts:
    target_kind: str
    target_name: str | None
    specialization: str | None
    attrs: str | None


def adapt_exact_primitive_call_fragment(
    fragment: ExactPrimitiveCallFragment,
) -> PrimitiveCallFragmentAdaptationResult:
    selector = _selector_without_primitive_prefix(fragment.selector_payload)
    if isinstance(selector, Diagnostic):
        return PrimitiveCallFragmentAdaptationResult(
            directive=None,
            diagnostics=(selector,),
        )

    primitive_call = _primitive_call_from_fragment(fragment, selector)
    if isinstance(primitive_call, Diagnostic):
        return PrimitiveCallFragmentAdaptationResult(
            directive=None,
            diagnostics=(primitive_call,),
        )

    return PrimitiveCallFragmentAdaptationResult(
        directive=LowerableDirective(
            name="call",
            arguments=(
                "primitive",
                selector,
                fragment.argument_payload.text,
            ),
            source=fragment.source,
            primitive_call=primitive_call,
        ),
        diagnostics=(),
    )


def _primitive_call_from_fragment(
    fragment: ExactPrimitiveCallFragment,
    selector_text: str,
) -> PrimitiveCall | Diagnostic:
    selector = _primitive_call_selector(fragment.selector_payload, selector_text)
    if isinstance(selector, Diagnostic):
        return selector

    argument_parts = split_top_level_parts(
        fragment.argument_payload.text,
        delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER),
        allow_empty_payload=True,
    )
    if argument_parts is None:
        return _malformed_primitive_call_fragment_diagnostic(
            fragment.source,
            "argument payload cannot be split at top-level comma boundaries",
        )

    return PrimitiveCall(
        selector=selector,
        payload=fragment.argument_payload.text,
        source=fragment.source,
        arguments=tuple(
            PrimitiveCallArgument(
                text=argument.text,
                source=fragment.argument_payload.source_at(argument.start),
            )
            for argument in argument_parts
        ),
    )


def _selector_without_primitive_prefix(
    selector_payload: PrimitiveCallFragmentText,
) -> str | Diagnostic:
    selector_text = selector_payload.text
    if not selector_text.startswith(_PRIMITIVE_SELECTOR_PREFIX):
        return _malformed_primitive_call_fragment_diagnostic(
            selector_payload.source_at(0),
            "expected selector to start with 'primitive='",
        )

    value = selector_text[len(_PRIMITIVE_SELECTOR_PREFIX) :]
    if not value:
        return _malformed_primitive_call_fragment_diagnostic(
            selector_payload.source_at(len(_PRIMITIVE_SELECTOR_PREFIX)),
            "expected a primitive selector after 'primitive='",
        )
    return value


def _primitive_call_selector(
    selector_payload: PrimitiveCallFragmentText,
    selector_text: str,
) -> PrimitiveCallSelector | Diagnostic:
    source = selector_payload.source_at(len(_PRIMITIVE_SELECTOR_PREFIX))
    parts = _parse_primitive_call_selector(selector_text)
    if parts is None:
        return _malformed_primitive_call_fragment_diagnostic(
            source,
            f"unsupported selector {selector_text!r}",
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


def _malformed_primitive_call_fragment_diagnostic(
    location: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED",
        message=(
            "call keyword fragment cannot be adapted to a primitive-call "
            f"directive: {reason}"
        ),
        location=location,
    )


def _source_locations_for_text(
    source: SourceLocation,
    text: str,
) -> tuple[SourceLocation, ...]:
    locations: list[SourceLocation] = []
    line = source.line
    column = source.column
    for char in text:
        locations.append(SourceLocation(source.path, line, column))
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    locations.append(SourceLocation(source.path, line, column))
    return tuple(locations)
