"""Exact selected-context type and backend type-query lowering."""

import re
from dataclasses import dataclass
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import LowerableDirective
from tslgen.lowering.model import (
    BackendTypeQueryLoweringResult,
    BackendTypeSpellingRequest,
    LoweredBackendTypeReference,
    LoweredBaseTransformType,
    LoweredCurrentScalarType,
    LoweredCurrentVectorType,
    LoweredGenericRegisterType,
    LoweredIntrinsicVectorImaskType,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
    LoweredSpecializationTypeSymbol,
    LoweredTypeIsSamePredicate,
    LoweredTypePredicate,
    LoweredTypeSelectType,
    LoweredTypeAliasBinding,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    LoweredVectorMemberType,
    LoweredVectorTransformType,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    TypeExpressionLoweringResult,
)

_ALIAS_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BARE_SCALAR_TYPE_RE = re.compile(r"(?:si|ui)\d+|f\d+|[su]\d+")
_SCALAR_TYPE_RE = re.compile(r"scalar::((?:si|ui)\d+|f\d+|[su]\d+)")
_BACKEND_TYPE_PREFIX = "type<backend>("
_GENERATION_TYPE_PREFIX = "type<generation>("
_GENERATION_VALUE_PREFIX = "value<generation>("
_CONTEXT_VECTOR_MEMBER_TYPES = {
    "vector::register": "register",
    "vector::mask": "mask",
    "vector::imask": "imask",
    "vector::mask_underlying_t": "mask_underlying",
    "vector::mask_underlying": "mask_underlying",
    "vector::offset_base": "offset_base",
}
_SIGNED_TYPE_COUNTERPARTS = {
    "si8": "si8",
    "ui8": "si8",
    "si16": "si16",
    "ui16": "si16",
    "si32": "si32",
    "ui32": "si32",
    "si64": "si64",
    "ui64": "si64",
    "f32": "si32",
    "f64": "si64",
}
_UNSIGNED_TYPE_COUNTERPARTS = {
    "si8": "ui8",
    "ui8": "ui8",
    "si16": "ui16",
    "ui16": "ui16",
    "si32": "ui32",
    "ui32": "ui32",
    "si64": "ui64",
    "ui64": "ui64",
    "f32": "ui32",
    "f64": "ui64",
}


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


def lower_generation_type_query(
    context: SelectedImplementationLoweringContext,
    query: str,
    source: SourceLocation,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> TypeExpressionLoweringResult:
    expression = _extract_query_payload(
        query,
        _GENERATION_TYPE_PREFIX,
    )
    if expression is None:
        return TypeExpressionLoweringResult(
            value=None,
            diagnostics=(_malformed_generation_type_query_diagnostic(query, source),),
        )

    return lower_type_expression(
        context,
        expression,
        source,
        environment=environment,
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
    *,
    allow_specialization_symbol: bool = False,
) -> LoweredTypeValue | Diagnostic:
    if expression != expression.strip():
        return _unsupported_type_expression_diagnostic(expression, source)

    if expression == context.current_vector_keyword:
        return LoweredCurrentVectorType(
            extension=context.extension,
            type_tag=context.type_tag,
        )

    if expression == context.current_scalar_keyword:
        return LoweredCurrentScalarType(type_tag=context.type_tag)

    if expression == "base::in":
        return LoweredCurrentScalarType(type_tag=context.type_tag)

    if expression in _CONTEXT_VECTOR_MEMBER_TYPES:
        return LoweredVectorMemberType(
            member=_CONTEXT_VECTOR_MEMBER_TYPES[expression],
            extension=context.extension,
            type_tag=context.type_tag,
        )

    if expression == "size_t":
        return LoweredSizeType()

    if expression == "intrin::vector::imask":
        return LoweredIntrinsicVectorImaskType()

    scalar_match = _SCALAR_TYPE_RE.fullmatch(expression)
    if scalar_match is not None:
        return LoweredScalarTypeIdentity(type_tag=scalar_match.group(1))

    if _BARE_SCALAR_TYPE_RE.fullmatch(expression) is not None:
        return LoweredScalarTypeIdentity(type_tag=expression)

    generation_payload = _extract_query_payload(expression, _GENERATION_TYPE_PREFIX)
    if generation_payload is not None:
        return _lower_type_expression_value(
            context,
            generation_payload,
            source,
            alias_bindings,
            allow_specialization_symbol=allow_specialization_symbol,
        )

    backend_payload = _extract_query_payload(expression, _BACKEND_TYPE_PREFIX)
    if backend_payload is not None:
        backend_value = _lower_type_expression_value(
            context,
            backend_payload,
            source,
            alias_bindings,
            allow_specialization_symbol=allow_specialization_symbol,
        )
        if isinstance(backend_value, Diagnostic):
            return backend_value
        return LoweredBackendTypeReference(
            request=BackendTypeSpellingRequest(
                backend=context.backend,
                value=backend_value,
                source_text=expression,
                source=source,
            )
        )

    parsed_call = _parse_type_call(expression)
    if parsed_call is not None:
        return _lower_type_call(
            context,
            expression,
            parsed_call[0],
            parsed_call[1],
            source,
            alias_bindings,
        )

    if _ALIAS_NAME_RE.fullmatch(expression) is not None:
        binding = _find_alias_binding(alias_bindings, expression)
        if binding is not None:
            return binding.value
        if allow_specialization_symbol:
            return LoweredSpecializationTypeSymbol(name=expression)
        return _unbound_type_alias_diagnostic(expression, source)

    return _unsupported_type_expression_diagnostic(expression, source)


def _lower_type_call(
    context: SelectedImplementationLoweringContext,
    expression: str,
    name: str,
    arguments: tuple[str, ...],
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    if name in {"base::signed_of", "base::unsigned_of"} and len(arguments) == 1:
        value = _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(value, Diagnostic):
            return value
        return _lower_signedness_transform(
            "signed_of" if name == "base::signed_of" else "unsigned_of",
            value,
        )

    if name == "base::generic" and len(arguments) == 1:
        value = _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(value, Diagnostic):
            return value
        return LoweredBaseTransformType(transform="generic", value=value)

    if name == "base::id" and len(arguments) == 1:
        return _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )

    if name == "register::generic" and len(arguments) == 1:
        value = _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(value, Diagnostic):
            return value
        return LoweredGenericRegisterType(vector_type=value)

    if name in {"vector::transform", "vector::transform_extension"} and len(
        arguments
    ) == 1:
        value = _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(value, Diagnostic):
            return value
        return LoweredVectorTransformType(
            transform="transform"
            if name == "vector::transform"
            else "transform_extension",
            base_type=value,
            extension=context.extension,
        )

    if name == "vector::as_extension" and len(arguments) in {1, 2}:
        extension_name = arguments[0].strip()
        if _ALIAS_NAME_RE.fullmatch(extension_name) is None:
            return _unsupported_type_expression_diagnostic(expression, source)
        if len(arguments) == 1:
            base_type: LoweredTypeValue = LoweredCurrentScalarType(
                type_tag=context.type_tag
            )
        else:
            value = _lower_type_expression_value(
                context,
                arguments[1],
                source,
                alias_bindings,
                allow_specialization_symbol=True,
            )
            if isinstance(value, Diagnostic):
                return value
            base_type = value
        return LoweredVectorAsExtensionType(
            base_type=base_type,
            extension=extension_name,
        )

    if name == "select" and len(arguments) == 3:
        condition = _lower_generation_value_predicate(
            context,
            arguments[0],
            source,
            alias_bindings,
        )
        if isinstance(condition, Diagnostic):
            return condition
        then_type = _lower_type_expression_value(
            context,
            arguments[1],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(then_type, Diagnostic):
            return then_type
        else_type = _lower_type_expression_value(
            context,
            arguments[2],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )
        if isinstance(else_type, Diagnostic):
            return else_type
        return LoweredTypeSelectType(
            condition=condition,
            then_type=then_type,
            else_type=else_type,
        )

    return _unsupported_type_expression_diagnostic(expression, source)


def _lower_generation_value_predicate(
    context: SelectedImplementationLoweringContext,
    expression: str,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypePredicate | Diagnostic:
    payload = _extract_query_payload(expression, _GENERATION_VALUE_PREFIX)
    if payload is None:
        return _unsupported_type_expression_diagnostic(expression, source)

    parsed_call = _parse_type_call(payload)
    if parsed_call is None:
        return _unsupported_type_expression_diagnostic(expression, source)

    name, arguments = parsed_call
    if name != "type::is_same" or len(arguments) != 2:
        return _unsupported_type_expression_diagnostic(expression, source)

    left = _lower_type_expression_value(
        context,
        arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(left, Diagnostic):
        return left
    right = _lower_type_expression_value(
        context,
        arguments[1],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(right, Diagnostic):
        return right
    return LoweredTypeIsSamePredicate(left=left, right=right)


def _lower_signedness_transform(
    transform: Literal["signed_of", "unsigned_of"],
    value: LoweredTypeValue,
) -> LoweredTypeValue:
    type_tag = _scalar_type_tag(value)
    counterparts = (
        _SIGNED_TYPE_COUNTERPARTS
        if transform == "signed_of"
        else _UNSIGNED_TYPE_COUNTERPARTS
    )
    if type_tag in counterparts:
        return LoweredScalarTypeIdentity(type_tag=counterparts[type_tag])
    return LoweredBaseTransformType(transform=transform, value=value)


def _scalar_type_tag(value: LoweredTypeValue) -> str | None:
    if isinstance(value, LoweredCurrentScalarType | LoweredScalarTypeIdentity):
        return value.type_tag
    return None


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


def _extract_query_payload(query: str, prefix: str) -> str | None:
    if query != query.strip() or not query.startswith(prefix):
        return None

    open_index = len(prefix) - 1
    close_index = _matching_close_paren(query, open_index)
    if close_index is None or close_index != len(query) - 1:
        return None

    expression = query[len(prefix) : close_index]
    if not expression or expression != expression.strip():
        return None
    return expression


def _parse_type_call(expression: str) -> tuple[str, tuple[str, ...]] | None:
    open_index = expression.find("(")
    if open_index == -1 or not expression.endswith(")"):
        return None

    close_index = _matching_close_paren(expression, open_index)
    if close_index is None or close_index != len(expression) - 1:
        return None

    name = expression[:open_index].strip()
    if not name:
        return None
    arguments = _split_top_level_arguments(expression[open_index + 1 : close_index])
    if arguments is None:
        return None
    return name, arguments


def _split_top_level_arguments(payload: str) -> tuple[str, ...] | None:
    if not payload.strip():
        return ()

    arguments: list[str] = []
    start = 0
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
            argument = payload[start:index].strip()
            if not argument:
                return None
            arguments.append(argument)
            start = index + 1

    if paren_depth != 0 or bracket_depth != 0:
        return None

    argument = payload[start:].strip()
    if not argument:
        return None
    arguments.append(argument)
    return tuple(arguments)


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
            "type expression cannot be lowered by the observed M143 type "
            "boundary; expected an observed context type, type transform, "
            "backend/scalar type identity, type query, or a previously "
            f"bound alias, got {expression!r}"
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


def _malformed_generation_type_query_diagnostic(
    query: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-TYPE-QUERY",
        message=(
            "generation type query cannot be lowered; expected exactly "
            f"type<generation>(TypeExpr), got {query!r}"
        ),
        location=source,
    )
