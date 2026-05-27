"""Exact selected-context type and backend type-query lowering."""

import re
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import LowerableDirective
from tslgen.lowering.model import (
    BackendTypeQueryLoweringResult,
    BackendTypeSpellingRequest,
    LoweredCurrentScalarType,
    LoweredCurrentVectorType,
    LoweredTypeAliasBinding,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    TypeExpressionLoweringResult,
)

_ALIAS_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKEND_TYPE_PREFIX = "type<backend>("
_VECTOR_AS_EXTENSION_EXPRESSION = "vector::as_extension(scalar)"


def build_selected_type_environment(
    context: SelectedImplementationLoweringContext,
) -> SelectedTypeEnvironment:
    """Build ordered source-defined type aliases for one selected body."""

    alias_bindings: list[LoweredTypeAliasBinding] = []
    diagnostics: list[Diagnostic] = []

    for token in context.implementation.body.tokens:
        if not isinstance(token, LowerableDirective):
            continue
        if token.name != "let" or token.arguments[:1] != ("type",):
            continue

        alias_result = _lower_type_alias_binding(
            context,
            token,
            tuple(alias_bindings),
        )
        diagnostics.extend(alias_result.diagnostics)
        if alias_result.binding is not None:
            alias_bindings.append(alias_result.binding)

    return SelectedTypeEnvironment(
        context=context,
        context_symbols=(
            context.current_vector_keyword,
            context.current_scalar_keyword,
        ),
        alias_bindings=tuple(alias_bindings),
        diagnostics=tuple(diagnostics),
    )


def lower_type_expression(
    context: SelectedImplementationLoweringContext,
    expression: str,
    source: SourceLocation,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> TypeExpressionLoweringResult:
    alias_bindings = (
        _visible_alias_bindings(environment.alias_bindings, source)
        if environment is not None
        else ()
    )
    type_value = _lower_type_expression_value(
        context,
        expression,
        source,
        alias_bindings,
    )
    if isinstance(type_value, Diagnostic):
        return TypeExpressionLoweringResult(value=None, diagnostics=(type_value,))
    return TypeExpressionLoweringResult(value=type_value, diagnostics=())


def lower_backend_type_query(
    context: SelectedImplementationLoweringContext,
    query: str,
    source: SourceLocation,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> BackendTypeQueryLoweringResult:
    if query != query.strip() or not query.startswith(_BACKEND_TYPE_PREFIX):
        return BackendTypeQueryLoweringResult(
            request=None,
            diagnostics=(_malformed_backend_type_query_diagnostic(query, source),),
        )

    open_index = len(_BACKEND_TYPE_PREFIX) - 1
    close_index = _matching_close_paren(query, open_index)
    if close_index is None or close_index != len(query) - 1:
        return BackendTypeQueryLoweringResult(
            request=None,
            diagnostics=(_malformed_backend_type_query_diagnostic(query, source),),
        )

    expression = query[len(_BACKEND_TYPE_PREFIX) : close_index]
    if not expression or expression != expression.strip():
        return BackendTypeQueryLoweringResult(
            request=None,
            diagnostics=(_malformed_backend_type_query_diagnostic(query, source),),
        )

    expression_result = lower_type_expression(
        context,
        expression,
        source,
        environment=environment,
    )
    if expression_result.value is None:
        return BackendTypeQueryLoweringResult(
            request=None,
            diagnostics=expression_result.diagnostics,
        )

    return BackendTypeQueryLoweringResult(
        request=BackendTypeSpellingRequest(
            backend=context.backend,
            value=expression_result.value,
            source_text=query,
            source=source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _TypeAliasBindingResult:
    binding: LoweredTypeAliasBinding | None
    diagnostics: tuple[Diagnostic, ...]


def _lower_type_alias_binding(
    context: SelectedImplementationLoweringContext,
    directive: LowerableDirective,
    prior_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> _TypeAliasBindingResult:
    if len(directive.arguments) != 2:
        return _TypeAliasBindingResult(
            None,
            (_malformed_type_alias_diagnostic(directive),),
        )

    parts = _split_top_level_comma(directive.arguments[1])
    if parts is None:
        return _TypeAliasBindingResult(
            None,
            (_malformed_type_alias_diagnostic(directive),),
        )

    alias_name, expression = parts
    if _ALIAS_NAME_RE.fullmatch(alias_name) is None:
        return _TypeAliasBindingResult(
            None,
            (_malformed_type_alias_diagnostic(directive),),
        )

    type_value = _lower_type_expression_value(
        context,
        expression,
        directive.source,
        prior_bindings,
    )
    if isinstance(type_value, Diagnostic):
        return _TypeAliasBindingResult(None, (type_value,))

    return _TypeAliasBindingResult(
        LoweredTypeAliasBinding(
            alias_name=alias_name,
            value=type_value,
            source_text=expression,
            source=directive.source,
        ),
        (),
    )


def _lower_type_expression_value(
    context: SelectedImplementationLoweringContext,
    expression: str,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    if expression == context.current_vector_keyword:
        return LoweredCurrentVectorType(
            extension=context.extension,
            type_tag=context.type_tag,
        )

    if expression == context.current_scalar_keyword:
        return LoweredCurrentScalarType(type_tag=context.type_tag)

    if expression == _VECTOR_AS_EXTENSION_EXPRESSION:
        return LoweredVectorAsExtensionType(
            scalar=LoweredCurrentScalarType(type_tag=context.type_tag),
            extension=context.extension,
        )

    if _ALIAS_NAME_RE.fullmatch(expression) is not None:
        binding = _find_alias_binding(alias_bindings, expression)
        if binding is not None:
            return binding.value
        return _unbound_type_alias_diagnostic(expression, source)

    return _unsupported_type_expression_diagnostic(expression, source)


def _find_alias_binding(
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
    alias_name: str,
) -> LoweredTypeAliasBinding | None:
    for binding in reversed(alias_bindings):
        if binding.alias_name == alias_name:
            return binding
    return None


def _visible_alias_bindings(
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
    source: SourceLocation,
) -> tuple[LoweredTypeAliasBinding, ...]:
    return tuple(
        binding
        for binding in alias_bindings
        if _source_precedes(binding.source, source)
    )


def _source_precedes(left: SourceLocation, right: SourceLocation) -> bool:
    if left.path != right.path:
        return False
    return (left.line, left.column) < (right.line, right.column)


def _split_top_level_comma(payload: str) -> tuple[str, str] | None:
    comma_index: int | None = None
    paren_depth = 0
    bracket_depth = 0
    for index, char in enumerate(payload):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth == 0:
                return None
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            if bracket_depth == 0:
                return None
            bracket_depth -= 1
        elif char == "," and paren_depth == 0 and bracket_depth == 0:
            if comma_index is not None:
                return None
            comma_index = index

    if paren_depth != 0 or bracket_depth != 0 or comma_index is None:
        return None

    alias_name = payload[:comma_index].strip()
    expression = payload[comma_index + 1 :].strip()
    if not alias_name or not expression:
        return None
    return (alias_name, expression)


def _matching_close_paren(text: str, open_index: int) -> int | None:
    if open_index >= len(text) or text[open_index] != "(":
        return None

    depth = 1
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _malformed_type_alias_diagnostic(
    directive: LowerableDirective,
) -> Diagnostic:
    payload = directive.arguments[1] if len(directive.arguments) > 1 else ""
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-TYPE-ALIAS",
        message=(
            "type alias directive cannot be lowered; expected exactly "
            f"let<type>(AliasName, TypeExpr), got {payload!r}"
        ),
        location=directive.source,
    )


def _unbound_type_alias_diagnostic(
    alias_name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNBOUND-TYPE-ALIAS",
        message=(
            f"type alias {alias_name!r} is not bound by an earlier "
            "let<type>(...) directive in the selected body"
        ),
        location=source,
    )


def _unsupported_type_expression_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-TYPE-EXPRESSION",
        message=(
            "type expression cannot be lowered by the exact M142 boundary; "
            "expected Vec, scalar, vector::as_extension(scalar), or a "
            f"previously bound alias, got {expression!r}"
        ),
        location=source,
    )


def _malformed_backend_type_query_diagnostic(
    query: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY",
        message=(
            "backend type query cannot be lowered; expected exactly "
            f"type<backend>(TypeExpr), got {query!r}"
        ),
        location=source,
    )
