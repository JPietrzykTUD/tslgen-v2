"""Semantic handoff for discovered backend intrinsic request islands."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering._source_islands import SourceMappedText, source_text_from_text
from tslgen.lowering.backend_value_queries import (
    discover_backend_value_queries_in_text,
    lower_backend_value_query_discovery,
)
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicDiscovery,
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffLoweringResult,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicHandoffSegment,
    BackendIntrinsicModifierBackendValueOperand,
    BackendIntrinsicModifierDestinationTypeSuffixOperand,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierIntegerOperand,
    BackendIntrinsicModifierName,
    BackendIntrinsicModifierOperand,
    BackendIntrinsicModifierStringOperand,
    BackendIntrinsicModifierSymbolOperand,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
    BackendIntrinsicRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendValueTypeOperand,
    LoweredScalarTypeIdentity,
    BackendValueQueryDiscovery,
    BackendValueQueryHandoffRequestSegment,
    BackendValueQueryRequestSegment,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.selected_specializations import (
    selected_specialization_binding_kind_diagnostic,
    selected_specialization_type_value,
    unbound_selected_specialization_binding_diagnostic,
)

_BACKEND_VALUE_QUERY_PREFIX = "value<backend>("
_TO_TYPE_SUFFIX_SYMBOL = "to_type_suffix"
_NORMAL_MODIFIER_NAMES: tuple[BackendIntrinsicModifierName, ...] = (
    "infix_sep",
    "suffix",
    "prefix",
    "post",
    "infix",
)
_SYMBOL_OPERAND_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_?]*(?:::[A-Za-z_][A-Za-z0-9_?]*)*"
)
_INTEGER_OPERAND_RE = re.compile(r"[0-9]+")


def lower_backend_intrinsic_discovery(
    context: SelectedImplementationLoweringContext,
    discovery: BackendIntrinsicDiscovery,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> BackendIntrinsicHandoffLoweringResult:
    """Lower discovered backend intrinsic islands to typed handoff requests."""

    segments: list[BackendIntrinsicHandoffSegment] = []
    diagnostics: list[Diagnostic] = []

    for segment in discovery.segments:
        if isinstance(
            segment,
            BackendIntrinsicOpaqueTextSegment | BackendIntrinsicOpaqueTokenSegment,
        ):
            segments.append(segment)
            continue

        result = _lower_backend_intrinsic_request(
            context,
            segment.request,
            environment=environment,
        )
        diagnostics.extend(result.diagnostics)
        if result.request is None:
            continue
        segments.append(
            BackendIntrinsicHandoffRequestSegment(
                request=result.request,
                island=segment.request,
                source=segment.source,
            )
        )

    if diagnostics:
        return BackendIntrinsicHandoffLoweringResult(
            handoff=None,
            diagnostics=tuple(diagnostics),
        )

    return BackendIntrinsicHandoffLoweringResult(
        handoff=BackendIntrinsicHandoff(
            segments=tuple(segments),
            source=discovery.source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _BackendIntrinsicRequestLoweringResult:
    request: BackendIntrinsicHandoffRequest | None
    diagnostics: tuple[Diagnostic, ...]


def _lower_backend_intrinsic_request(
    context: SelectedImplementationLoweringContext,
    request: BackendIntrinsicRequest,
    *,
    environment: SelectedTypeEnvironment | None,
) -> _BackendIntrinsicRequestLoweringResult:
    if request.intrinsic_kind == "intrin":
        return _BackendIntrinsicRequestLoweringResult(
            request=BackendDirectIntrinsicHandoffRequest(
                angle_payload_text=request.angle_payload_text,
                angle_payload_source=request.angle_payload_source,
                argument_text=request.argument_text,
                argument_source=request.argument_source,
                source_text=request.source_text,
                source=request.source,
            ),
            diagnostics=(),
        )

    if request.intrinsic_kind == "intrin_compose":
        return _lower_intrin_compose_request(
            context,
            request,
            environment=environment,
        )

    return _BackendIntrinsicRequestLoweringResult(
        request=None,
        diagnostics=(
            _unsupported_modifier_diagnostic(
                request.source,
                request.source_text,
                "expected intrin<...>(...) or intrin_compose<...>(...)",
            ),
        ),
    )


def _lower_intrin_compose_request(
    context: SelectedImplementationLoweringContext,
    request: BackendIntrinsicRequest,
    *,
    environment: SelectedTypeEnvironment | None,
) -> _BackendIntrinsicRequestLoweringResult:
    parse_result = _parse_intrin_compose_payload(
        context,
        source_text_from_text(request.angle_payload_text, request.angle_payload_source),
        environment=environment,
    )
    if parse_result.diagnostics:
        return _BackendIntrinsicRequestLoweringResult(
            request=None,
            diagnostics=parse_result.diagnostics,
        )
    assert parse_result.base is not None

    return _BackendIntrinsicRequestLoweringResult(
        request=BackendIntrinsicComposeHandoffRequest(
            base_text=parse_result.base.text,
            base_source=parse_result.base.source,
            modifiers=parse_result.modifiers,
            angle_payload_text=request.angle_payload_text,
            angle_payload_source=request.angle_payload_source,
            argument_text=request.argument_text,
            argument_source=request.argument_source,
            source_text=request.source_text,
            source=request.source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _ComposeBase:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class _ComposePayloadParseResult:
    base: _ComposeBase | None
    modifiers: tuple[BackendIntrinsicModifierField, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _ModifierKey:
    name: BackendIntrinsicModifierName
    key_text: str
    source_text: str
    source: SourceLocation
    immediate_index: int | None = None
    immediate_index_text: str | None = None


@dataclass(frozen=True, slots=True)
class _ModifierValue:
    text: str
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class _ModifierKeyScan:
    key: _ModifierKey | None
    equals_index: int | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _DelimiterScanResult:
    end_index: int
    diagnostics: tuple[Diagnostic, ...]


def _parse_intrin_compose_payload(
    context: SelectedImplementationLoweringContext,
    source_text: SourceMappedText,
    *,
    environment: SelectedTypeEnvironment | None,
) -> _ComposePayloadParseResult:
    text = source_text.text
    index = _skip_whitespace(text, 0)
    if index >= len(text):
        return _compose_payload_diagnostics(
            _malformed_modifier_diagnostic(
                source_text.source,
                text,
                "expected a non-empty intrin_compose base token",
            )
        )

    base_start = index
    while (
        index < len(text)
        and text[index] not in {",", "="}
        and not text[index].isspace()
    ):
        index += 1
    base_text = text[base_start:index]
    if not base_text:
        return _compose_payload_diagnostics(
            _malformed_modifier_diagnostic(
                source_text.source_at(base_start),
                text,
                "expected an intrin_compose base token before modifiers",
            )
        )

    base = _ComposeBase(text=base_text, source=source_text.source_at(base_start))
    modifiers: list[BackendIntrinsicModifierField] = []
    diagnostics: list[Diagnostic] = []
    seen_fields: set[tuple[BackendIntrinsicModifierName, int | None]] = set()

    while True:
        separator_start = index
        index = _skip_separators_before_modifier(text, index)
        if index >= len(text):
            break
        if index == separator_start:
            diagnostics.append(
                _malformed_modifier_diagnostic(
                    source_text.source_at(index),
                    text[index:],
                    "expected a comma or whitespace before the next modifier field",
                )
            )
            break

        key_scan = _scan_modifier_key(source_text, index)
        diagnostics.extend(key_scan.diagnostics)
        if key_scan.key is None or key_scan.equals_index is None:
            break

        value_start = key_scan.equals_index + 1
        value_end_scan = _find_modifier_value_end(source_text, value_start)
        diagnostics.extend(value_end_scan.diagnostics)
        if value_end_scan.diagnostics:
            break

        value_span = source_text.span(value_start, value_end_scan.end_index)
        value_text = value_span.text.strip()
        value_offset = len(value_span.text) - len(value_span.text.lstrip())
        if not value_text:
            diagnostics.append(
                _malformed_modifier_diagnostic(
                    value_span.source,
                    value_span.text,
                    "expected a non-empty modifier value",
                )
            )
            break

        duplicate_key = (key_scan.key.name, key_scan.key.immediate_index)
        if duplicate_key in seen_fields:
            diagnostics.append(
                _malformed_modifier_diagnostic(
                    key_scan.key.source,
                    key_scan.key.source_text,
                    "duplicate backend intrinsic modifier field",
                )
            )
            break
        seen_fields.add(duplicate_key)

        value_source = source_text.source_at(value_start + value_offset)
        operand = _lower_modifier_operand(
            context,
            key_scan.key,
            _ModifierValue(
                text=value_text,
                source_text=value_text,
                source=value_source,
            ),
            environment=environment,
        )
        if isinstance(operand, Diagnostic):
            diagnostics.append(operand)
            break
        modifiers.append(
            BackendIntrinsicModifierField(
                name=key_scan.key.name,
                key_text=key_scan.key.key_text,
                value=operand,
                source_text=text[index:value_end_scan.end_index],
                source=source_text.source_at(index),
                key_source=key_scan.key.source,
                value_source=value_source,
                immediate_index=key_scan.key.immediate_index,
                immediate_index_text=key_scan.key.immediate_index_text,
            )
        )
        index = value_end_scan.end_index

    if diagnostics:
        return _ComposePayloadParseResult(
            base=None,
            modifiers=(),
            diagnostics=tuple(diagnostics),
        )

    return _ComposePayloadParseResult(
        base=base,
        modifiers=tuple(modifiers),
        diagnostics=(),
    )


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _skip_separators_before_modifier(text: str, index: int) -> int:
    saw_separator = False
    while index < len(text):
        if text[index] == "," or text[index].isspace():
            saw_separator = True
            index += 1
            continue
        break
    if not saw_separator:
        return index
    return index


def _scan_modifier_key(
    source_text: SourceMappedText,
    index: int,
) -> _ModifierKeyScan:
    text = source_text.text
    for name in _NORMAL_MODIFIER_NAMES:
        prefix = f"{name}="
        if text.startswith(prefix, index):
            return _ModifierKeyScan(
                key=_ModifierKey(
                    name=name,
                    key_text=name,
                    source_text=name,
                    source=source_text.source_at(index),
                ),
                equals_index=index + len(name),
                diagnostics=(),
            )

    immediate_prefix = "immediate("
    if text.startswith(immediate_prefix, index):
        return _scan_immediate_key(source_text, index)

    next_separator = _next_top_level_separator(text, index)
    return _ModifierKeyScan(
        key=None,
        equals_index=None,
        diagnostics=(
            _malformed_modifier_diagnostic(
                source_text.source_at(index),
                text[index:next_separator],
                "expected suffix=, prefix=, post=, infix=, infix_sep=, "
                "or immediate(N)= modifier field",
            ),
        ),
    )


def _scan_immediate_key(
    source_text: SourceMappedText,
    index: int,
) -> _ModifierKeyScan:
    text = source_text.text
    immediate_prefix = "immediate("
    argument_start = index + len(immediate_prefix)
    close_index = text.find(")", argument_start)
    if close_index == -1:
        return _ModifierKeyScan(
            key=None,
            equals_index=None,
            diagnostics=(
                _malformed_modifier_diagnostic(
                    source_text.source_at(index),
                    text[index:],
                    "expected immediate(N)=... with a closing ')' in the key",
                ),
            ),
        )
    if close_index + 1 >= len(text) or text[close_index + 1] != "=":
        return _ModifierKeyScan(
            key=None,
            equals_index=None,
            diagnostics=(
                _malformed_modifier_diagnostic(
                    source_text.source_at(index),
                    text[index : close_index + 1],
                    "expected immediate(N)=... with '=' after the key",
                ),
            ),
        )

    immediate_index_text = text[argument_start:close_index]
    if _INTEGER_OPERAND_RE.fullmatch(immediate_index_text) is None:
        return _ModifierKeyScan(
            key=None,
            equals_index=None,
            diagnostics=(
                _malformed_modifier_diagnostic(
                    source_text.source_at(argument_start),
                    immediate_index_text,
                    "expected immediate(N) where N is a decimal integer",
                ),
            ),
        )

    key_text = text[index : close_index + 1]
    return _ModifierKeyScan(
        key=_ModifierKey(
            name="immediate",
            key_text=key_text,
            source_text=key_text,
            source=source_text.source_at(index),
            immediate_index=int(immediate_index_text),
            immediate_index_text=immediate_index_text,
        ),
        equals_index=close_index + 1,
        diagnostics=(),
    )


def _find_modifier_value_end(
    source_text: SourceMappedText,
    start: int,
) -> _DelimiterScanResult:
    text = source_text.text
    depths = {"(": 0, "[": 0, "<": 0}
    quote: str | None = None
    escaped = False
    index = start

    while index < len(text):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
            index += 1
            continue

        delimiter_result = _advance_delimiter_depths(source_text, start, index, depths)
        if delimiter_result is not None:
            if isinstance(delimiter_result, _DelimiterScanResult):
                return delimiter_result
            index = delimiter_result
            continue

        if _at_top_level(depths):
            if char == ",":
                break
            if char.isspace() and _modifier_key_starts_after_whitespace(text, index):
                break
        index += 1

    if quote is not None or any(depths.values()):
        return _DelimiterScanResult(
            end_index=index,
            diagnostics=(
                _malformed_modifier_diagnostic(
                    source_text.source_at(start),
                    text[start:index],
                    "unbalanced delimiter or quote in modifier value",
                ),
            ),
        )
    return _DelimiterScanResult(end_index=index, diagnostics=())


def _advance_delimiter_depths(
    source_text: SourceMappedText,
    start: int,
    index: int,
    depths: dict[str, int],
) -> int | _DelimiterScanResult | None:
    text = source_text.text
    char = text[index]
    if char in {"(", "[", "<"}:
        depths[char] += 1
        return index + 1
    if char == ")":
        return _advance_closing_delimiter(
            source_text,
            start,
            index,
            depths,
            open_char="(",
            close_char=")",
        )
    if char == "]":
        return _advance_closing_delimiter(
            source_text,
            start,
            index,
            depths,
            open_char="[",
            close_char="]",
        )
    if char == ">":
        return _advance_closing_delimiter(
            source_text,
            start,
            index,
            depths,
            open_char="<",
            close_char=">",
        )
    return None


def _advance_closing_delimiter(
    source_text: SourceMappedText,
    start: int,
    index: int,
    depths: dict[str, int],
    *,
    open_char: str,
    close_char: str,
) -> int | _DelimiterScanResult:
    if depths[open_char] == 0:
        return _DelimiterScanResult(
            end_index=index,
            diagnostics=(
                _malformed_modifier_diagnostic(
                    source_text.source_at(index),
                    source_text.text[start : index + 1],
                    f"unbalanced {close_char!r} in modifier value",
                ),
            ),
        )
    depths[open_char] -= 1
    return index + 1


def _at_top_level(depths: dict[str, int]) -> bool:
    return all(depth == 0 for depth in depths.values())


def _modifier_key_starts_after_whitespace(text: str, whitespace_index: int) -> bool:
    index = _skip_whitespace(text, whitespace_index)
    if index >= len(text):
        return False
    return _recognised_modifier_key_start(text, index)


def _recognised_modifier_key_start(text: str, index: int) -> bool:
    for name in _NORMAL_MODIFIER_NAMES:
        if text.startswith(f"{name}=", index):
            return True
    return text.startswith("immediate(", index)


def _next_top_level_separator(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index] != "," and not text[index].isspace():
        index += 1
    return index


def _lower_modifier_operand(
    context: SelectedImplementationLoweringContext,
    key: _ModifierKey,
    value: _ModifierValue,
    *,
    environment: SelectedTypeEnvironment | None,
) -> BackendIntrinsicModifierOperand | Diagnostic:
    if key.name == "infix" and value.text == _TO_TYPE_SUFFIX_SYMBOL:
        destination_suffix = _lower_to_type_suffix_operand(
            context,
            value,
            environment=environment,
        )
        if destination_suffix is not None:
            return destination_suffix

    if value.text.startswith(_BACKEND_VALUE_QUERY_PREFIX):
        return _lower_backend_value_operand(
            context,
            value,
            environment=environment,
        )

    string_operand = _string_modifier_operand(value)
    if isinstance(string_operand, BackendIntrinsicModifierStringOperand | Diagnostic):
        return string_operand

    if _INTEGER_OPERAND_RE.fullmatch(value.text) is not None:
        return BackendIntrinsicModifierIntegerOperand(
            value=int(value.text),
            source_text=value.source_text,
            source=value.source,
        )

    if _SYMBOL_OPERAND_RE.fullmatch(value.text) is not None:
        return BackendIntrinsicModifierSymbolOperand(
            text=value.text,
            source=value.source,
        )

    return _unsupported_modifier_diagnostic(
        value.source,
        value.text,
        "expected a backend value island, symbol, integer, or quoted string",
    )


def _lower_to_type_suffix_operand(
    context: SelectedImplementationLoweringContext,
    value: _ModifierValue,
    *,
    environment: SelectedTypeEnvironment | None,
) -> BackendIntrinsicModifierDestinationTypeSuffixOperand | Diagnostic | None:
    declaration = context.primitive.return_type_binding
    if declaration is None:
        diagnostic = _first_selected_binding_diagnostic(environment)
        if diagnostic is not None:
            return diagnostic
        return None

    if declaration.kind != "base":
        selected_value = selected_specialization_type_value(
            context,
            declaration.name,
            value.source,
        )
        if isinstance(selected_value, Diagnostic):
            return selected_value
        if selected_value is None:
            return unbound_selected_specialization_binding_diagnostic(
                declaration.name,
                value.source,
            )
        return selected_specialization_binding_kind_diagnostic(
            declaration.name,
            "return_type.base",
            type(selected_value).__name__,
            value.source,
        )

    selected_value = selected_specialization_type_value(
        context,
        declaration.name,
        value.source,
    )
    if isinstance(selected_value, Diagnostic):
        return selected_value
    if selected_value is None:
        diagnostic = _first_selected_binding_diagnostic(environment)
        if diagnostic is not None:
            return diagnostic
        return unbound_selected_specialization_binding_diagnostic(
            declaration.name,
            value.source,
        )
    if not isinstance(selected_value, LoweredScalarTypeIdentity):
        return selected_specialization_binding_kind_diagnostic(
            declaration.name,
            "return_type.base",
            type(selected_value).__name__,
            value.source,
        )

    return BackendIntrinsicModifierDestinationTypeSuffixOperand(
        request=BackendIntrinsicSuffixValueRequest(
            backend=context.backend,
            argument=BackendValueTypeOperand(
                value=selected_value,
                source_text=declaration.name,
                source=value.source,
            ),
            source_text=value.source_text,
            source=value.source,
        ),
        source_text=value.source_text,
        source=value.source,
    )


def _first_selected_binding_diagnostic(
    environment: SelectedTypeEnvironment | None,
) -> Diagnostic | None:
    if environment is None:
        return None
    for diagnostic in environment.diagnostics:
        if "SELECTED-SPECIALIZATION-BINDING" in diagnostic.code:
            return diagnostic
    return None


def _lower_backend_value_operand(
    context: SelectedImplementationLoweringContext,
    value: _ModifierValue,
    *,
    environment: SelectedTypeEnvironment | None,
) -> BackendIntrinsicModifierBackendValueOperand | Diagnostic:
    discovery_result = discover_backend_value_queries_in_text(value.text, value.source)
    if discovery_result.diagnostics:
        return _malformed_modifier_diagnostic(
            value.source,
            value.text,
            "expected exactly one balanced value<backend>(...) island",
        )
    if discovery_result.discovery is None or not _is_single_backend_value_query_island(
        discovery_result.discovery
    ):
        return _unsupported_modifier_diagnostic(
            value.source,
            value.text,
            "expected the modifier value to be exactly one value<backend>(...) island",
        )

    handoff_result = lower_backend_value_query_discovery(
        context,
        discovery_result.discovery,
        environment=environment,
    )
    if handoff_result.diagnostics:
        return handoff_result.diagnostics[0]
    assert handoff_result.handoff is not None
    handoff_segment = handoff_result.handoff.segments[0]
    assert isinstance(handoff_segment, BackendValueQueryHandoffRequestSegment)
    return BackendIntrinsicModifierBackendValueOperand(
        request=handoff_segment.request,
        island=handoff_segment.island,
        source_text=value.source_text,
        source=value.source,
    )


def _is_single_backend_value_query_island(
    discovery: BackendValueQueryDiscovery,
) -> bool:
    return (
        len(discovery.segments) == 1
        and isinstance(discovery.segments[0], BackendValueQueryRequestSegment)
    )


def _string_modifier_operand(
    value: _ModifierValue,
) -> BackendIntrinsicModifierStringOperand | Diagnostic | None:
    if not (value.text.startswith('"') or value.text.endswith('"')):
        return None
    if not (value.text.startswith('"') and value.text.endswith('"')):
        return _malformed_modifier_diagnostic(
            value.source,
            value.text,
            "expected a complete quoted string literal",
        )

    try:
        literal_value = ast.literal_eval(value.text)
    except (SyntaxError, ValueError):
        return _malformed_modifier_diagnostic(
            value.source,
            value.text,
            "expected a valid quoted string literal",
        )
    if not isinstance(literal_value, str):
        return _malformed_modifier_diagnostic(
            value.source,
            value.text,
            "expected a quoted string literal",
        )
    return BackendIntrinsicModifierStringOperand(
        value=literal_value,
        source_text=value.source_text,
        source=value.source,
    )


def _compose_payload_diagnostics(
    diagnostic: Diagnostic,
) -> _ComposePayloadParseResult:
    return _ComposePayloadParseResult(
        base=None,
        modifiers=(),
        diagnostics=(diagnostic,),
    )


def _malformed_modifier_diagnostic(
    source: SourceLocation,
    payload: str,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-INTRINSIC-MODIFIER",
        message=f"malformed backend intrinsic modifier {payload!r}: {reason}",
        location=source,
    )


def _unsupported_modifier_diagnostic(
    source: SourceLocation,
    payload: str,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-BACKEND-INTRINSIC-MODIFIER",
        message=f"unsupported backend intrinsic modifier {payload!r}: {reason}",
        location=source,
    )
