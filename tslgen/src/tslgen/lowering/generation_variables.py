"""Exact generation variable declaration directive discovery."""

from __future__ import annotations

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    ImplementationBody,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.model import (
    GenerationVariableDeclarationDiscovery,
    GenerationVariableDeclarationDiscoveryLoweringResult,
    GenerationVariableDeclarationOpaqueSegment,
    GenerationVariableDeclarationRequest,
    GenerationVariableDeclarationRequestSegment,
    GenerationVariableDeclarationSelector,
    GenerationVariableDeclarationText,
    SelectedImplementationLoweringContext,
)
from tslgen.syntax.tsil_lexical import (
    LexicalPart,
    raw_brace_depth_after,
)

_SUPPORTED_SELECTORS = frozenset(("init_register", "infer", "const_infer", "typed"))
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def discover_generation_variable_declarations(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> GenerationVariableDeclarationDiscoveryLoweringResult:
    """Discover top-level unresolved generation variable declarations."""

    del context

    tokens = body.tokens
    segments: list[
        GenerationVariableDeclarationOpaqueSegment
        | GenerationVariableDeclarationRequestSegment
    ] = []
    pending_opaque_start = 0
    raw_brace_depth = 0

    for index, token in enumerate(tokens):
        if raw_brace_depth != 0:
            raw_brace_depth = _updated_raw_brace_depth(raw_brace_depth, token)
            continue

        if not _is_var_directive(token):
            raw_brace_depth = _updated_raw_brace_depth(raw_brace_depth, token)
            continue

        assert isinstance(token, LowerableDirective)
        declaration = _lower_var_directive(token)
        if isinstance(declaration, Diagnostic):
            return GenerationVariableDeclarationDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(declaration,),
            )

        opaque_tokens = tokens[pending_opaque_start:index]
        if opaque_tokens:
            segments.append(
                GenerationVariableDeclarationOpaqueSegment(
                    tokens=opaque_tokens,
                    source=_token_source(opaque_tokens[0]),
                )
            )
        segments.append(
            GenerationVariableDeclarationRequestSegment(
                declaration=declaration,
                source=declaration.source,
            )
        )
        pending_opaque_start = index + 1

    if not segments:
        return GenerationVariableDeclarationDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_declaration_diagnostic(body.source),),
        )

    trailing_tokens = tokens[pending_opaque_start:]
    if trailing_tokens:
        segments.append(
            GenerationVariableDeclarationOpaqueSegment(
                tokens=trailing_tokens,
                source=_token_source(trailing_tokens[0]),
            )
        )

    return GenerationVariableDeclarationDiscoveryLoweringResult(
        discovery=GenerationVariableDeclarationDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def _lower_var_directive(
    directive: LowerableDirective,
) -> GenerationVariableDeclarationRequest | Diagnostic:
    if len(directive.arguments) != 2:
        return _malformed_declaration_diagnostic(
            directive,
            "expected var directive with selector and payload",
        )

    selector, payload = directive.arguments
    if selector not in _SUPPORTED_SELECTORS:
        return _unsupported_selector_diagnostic(directive, selector)

    payload_source = _payload_source(directive, selector)
    parts = _split_declaration_payload(payload)
    if parts is None:
        return _malformed_declaration_diagnostic(
            directive,
            "payload must split on top-level commas with balanced delimiters",
        )

    if selector == "init_register":
        if len(parts) != 1:
            return _malformed_arity_diagnostic(directive, selector, len(parts), 1)
        name_part = parts[0]
        initializer_part = None
        type_part = None
    elif selector in {"infer", "const_infer"}:
        if len(parts) != 2:
            return _malformed_arity_diagnostic(directive, selector, len(parts), 2)
        name_part = parts[0]
        initializer_part = parts[1]
        type_part = None
    else:
        if len(parts) != 3:
            return _malformed_arity_diagnostic(directive, selector, len(parts), 3)
        type_part = parts[0]
        name_part = parts[1]
        initializer_part = parts[2]

    if _IDENTIFIER_RE.fullmatch(name_part.text) is None:
        return _invalid_name_diagnostic(
            name_part.text,
            _source_at_offset(payload_source, payload, name_part.start),
        )

    return GenerationVariableDeclarationRequest(
        selector=_typed_selector(selector),
        name=name_part.text,
        name_source=_source_at_offset(payload_source, payload, name_part.start),
        payload_text=payload,
        source=directive.source,
        explicit_type=(
            _declaration_text(payload_source, payload, type_part)
            if type_part is not None
            else None
        ),
        initializer=(
            _declaration_text(payload_source, payload, initializer_part)
            if initializer_part is not None
            else None
        ),
    )


def _declaration_text(
    payload_source: SourceLocation,
    payload: str,
    part: LexicalPart,
) -> GenerationVariableDeclarationText:
    return GenerationVariableDeclarationText(
        text=part.text,
        source=_source_at_offset(payload_source, payload, part.start),
    )


def _split_declaration_payload(payload: str) -> tuple[LexicalPart, ...] | None:
    """Split var payload fields without treating raw shifts as angle syntax."""

    if not payload.strip():
        return None

    parts: list[LexicalPart] = []
    part_start = 0
    paren_depth = 0
    bracket_depth = 0
    angle_depth = 0

    for index, char in enumerate(payload):
        if char == "(":
            paren_depth += 1
            continue
        if char == ")":
            if paren_depth == 0:
                return None
            paren_depth -= 1
            continue
        if char == "[":
            bracket_depth += 1
            continue
        if char == "]":
            if bracket_depth == 0:
                return None
            bracket_depth -= 1
            continue
        if char == "<" and _is_angle_opener(payload, index):
            angle_depth += 1
            continue
        if char == ">":
            if angle_depth > 0:
                angle_depth -= 1
            continue
        if (
            char == ","
            and paren_depth == 0
            and bracket_depth == 0
            and angle_depth == 0
        ):
            part = _trimmed_part(payload, part_start, index)
            if part is None:
                return None
            parts.append(part)
            part_start = index + 1

    if paren_depth != 0 or bracket_depth != 0 or angle_depth != 0:
        return None

    part = _trimmed_part(payload, part_start, len(payload))
    if part is None:
        return None
    parts.append(part)
    return tuple(parts)


def _is_angle_opener(text: str, index: int) -> bool:
    if index + 1 >= len(text) or text[index + 1] in "<=":
        return False
    if text[index + 1].isspace():
        return False
    if index == 0 or text[index - 1].isspace():
        return False
    return text[index - 1].isalnum() or text[index - 1] in "_]:)"


def _trimmed_part(payload: str, start: int, end: int) -> LexicalPart | None:
    while start < end and payload[start].isspace():
        start += 1
    while end > start and payload[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    return LexicalPart(text=payload[start:end], start=start, end=end)


def _is_var_directive(token: BodyToken) -> bool:
    return isinstance(token, LowerableDirective) and token.name == "var"


def _typed_selector(selector: str) -> GenerationVariableDeclarationSelector:
    if selector == "init_register":
        return "init_register"
    if selector == "infer":
        return "infer"
    if selector == "const_infer":
        return "const_infer"
    if selector == "typed":
        return "typed"
    raise AssertionError(f"unsupported selector {selector!r}")


def _updated_raw_brace_depth(depth: int, token: BodyToken) -> int:
    if not isinstance(token, RawStringToken):
        return depth
    return raw_brace_depth_after(depth, token.text, clamp_underflow=True)


def _payload_source(directive: LowerableDirective, selector: str) -> SourceLocation:
    return SourceLocation(
        directive.source.path,
        directive.source.line,
        directive.source.column + len(f"var<{selector}>("),
    )


def _source_at_offset(
    source: SourceLocation,
    text: str,
    offset: int,
) -> SourceLocation:
    line = source.line
    column = source.column
    for char in text[:offset]:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return SourceLocation(source.path, line, column)


def _token_source(token: BodyToken) -> SourceLocation:
    return token.source


def _malformed_declaration_diagnostic(
    directive: LowerableDirective,
    reason: str,
) -> Diagnostic:
    payload = directive.arguments[1] if len(directive.arguments) > 1 else ""
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-VARIABLE-DECLARATION",
        message=(
            "generation variable declaration cannot be lowered by M163; "
            f"{reason}; got {payload!r}"
        ),
        location=directive.source,
    )


def _malformed_arity_diagnostic(
    directive: LowerableDirective,
    selector: str,
    actual: int,
    expected: int,
) -> Diagnostic:
    return _malformed_declaration_diagnostic(
        directive,
        (
            f"var<{selector}> expected exactly {expected} top-level "
            f"payload argument(s), got {actual}"
        ),
    )


def _unsupported_selector_diagnostic(
    directive: LowerableDirective,
    selector: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-VARIABLE-SELECTOR",
        message=(
            "generation variable declaration selector is not supported by "
            "M163; expected one of const_infer, infer, init_register, or "
            f"typed, got {selector!r}"
        ),
        location=directive.source,
    )


def _invalid_name_diagnostic(name: str, source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-INVALID-GENERATION-VARIABLE-NAME",
        message=(
            "generation variable declaration name must be an identifier; "
            f"got {name!r}"
        ),
        location=source,
    )


def _no_declaration_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-GENERATION-VARIABLE-DECLARATION",
        message=(
            "generation variable declaration discovery found no exact "
            "top-level var<...>(...) declaration"
        ),
        location=source,
    )
