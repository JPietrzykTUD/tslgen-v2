"""Exact selected-context type and backend type-query lowering."""

import re
from dataclasses import dataclass
from typing import Literal

from tslgen.analysis.selection import (
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
    TargetVectorTypeBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import ExtensionName, TypeTag
from tslgen.domain.catalog import LowerableDirective
from tslgen.lowering.model import (
    BackendTypeQueryLoweringResult,
    BackendTypeSpellingRequest,
    CurrentVector,
    LoweredBackendTypeReference,
    LoweredBaseTransformType,
    LoweredCurrentScalarType,
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
from tslgen.lowering.type_syntax import (
    TypeCall,
    TypeIdentifier,
    TypeQuery,
    TypeSyntax,
    parse_type_syntax,
    split_top_level_arguments,
)

_ALIAS_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BARE_SCALAR_TYPE_RE = re.compile(r"(?:si|ui)\d+|f\d+|[su]\d+")
_SCALAR_TYPE_RE = re.compile(r"scalar::((?:si|ui)\d+|f\d+|[su]\d+)")
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
    diagnostics: list[Diagnostic] = list(
        _selected_specialization_binding_diagnostics(context)
    )

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
    parsed = parse_type_syntax(expression)
    if parsed is None:
        return TypeExpressionLoweringResult(
            value=None,
            diagnostics=(_unsupported_type_expression_diagnostic(expression, source),),
        )
    return _lower_type_syntax_result(
        context,
        parsed,
        source,
        environment=environment,
    )


def _lower_type_syntax_result(
    context: SelectedImplementationLoweringContext,
    syntax: TypeSyntax,
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
        syntax,
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
    parsed = parse_type_syntax(query)
    if not isinstance(parsed, TypeQuery) or parsed.kind != "backend":
        return BackendTypeQueryLoweringResult(
            request=None,
            diagnostics=(_malformed_backend_type_query_diagnostic(query, source),),
        )

    expression_result = _lower_type_syntax_result(
        context,
        parsed.expression,
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
    parsed = parse_type_syntax(query)
    if not isinstance(parsed, TypeQuery) or parsed.kind != "generation":
        return TypeExpressionLoweringResult(
            value=None,
            diagnostics=(_malformed_generation_type_query_diagnostic(query, source),),
        )

    return _lower_type_syntax_result(
        context,
        parsed.expression,
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

    parsed_expression = parse_type_syntax(expression)
    if parsed_expression is None:
        return _TypeAliasBindingResult(
            None,
            (_unsupported_type_expression_diagnostic(expression, directive.source),),
        )

    type_value = _lower_type_expression_value(
        context,
        parsed_expression,
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
    syntax: TypeSyntax,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
    *,
    allow_specialization_symbol: bool = False,
) -> LoweredTypeValue | Diagnostic:
    if isinstance(syntax, TypeQuery):
        if syntax.kind == "generation":
            return _lower_type_expression_value(
                context,
                syntax.expression,
                source,
                alias_bindings,
                allow_specialization_symbol=allow_specialization_symbol,
            )
        if syntax.kind == "backend":
            backend_value = _lower_type_expression_value(
                context,
                syntax.expression,
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
                    source_text=syntax.source_text,
                    source=source,
                )
            )
        return _unsupported_type_expression_diagnostic(syntax.source_text, source)

    if isinstance(syntax, TypeCall):
        return _lower_type_call(
            context,
            syntax,
            source,
            alias_bindings,
        )

    expression = syntax.source_text

    if expression == context.current_vector_keyword:
        return CurrentVector(
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
        return LoweredScalarTypeIdentity(type_tag=TypeTag(scalar_match.group(1)))

    if _BARE_SCALAR_TYPE_RE.fullmatch(expression) is not None:
        return LoweredScalarTypeIdentity(type_tag=TypeTag(expression))

    if _ALIAS_NAME_RE.fullmatch(expression) is not None:
        binding = _find_alias_binding(alias_bindings, expression)
        if binding is not None:
            return binding.value
        selected_binding = _selected_specialization_binding_value(
            context,
            expression,
            source,
        )
        if selected_binding is not None:
            return selected_binding
        if allow_specialization_symbol:
            return LoweredSpecializationTypeSymbol(name=expression)
        return _unbound_type_alias_diagnostic(expression, source)

    return _unsupported_type_expression_diagnostic(expression, source)


def _lower_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    name = syntax.name
    arguments = syntax.arguments

    if name in {"base::signed_of", "base::unsigned_of"} and len(arguments) == 1:
        return _lower_signedness_type_call(context, syntax, source, alias_bindings)

    if name == "base::generic" and len(arguments) == 1:
        return _lower_base_generic_type_call(context, syntax, source, alias_bindings)

    if name == "base::id" and len(arguments) == 1:
        return _lower_type_expression_value(
            context,
            arguments[0],
            source,
            alias_bindings,
            allow_specialization_symbol=True,
        )

    if name == "register::generic" and len(arguments) == 1:
        return _lower_register_generic_type_call(
            context,
            syntax,
            source,
            alias_bindings,
        )

    if name in {"vector::transform", "vector::transform_extension"} and len(
        arguments
    ) == 1:
        return _lower_vector_transform_type_call(
            context,
            syntax,
            source,
            alias_bindings,
        )

    if name == "vector::as_extension" and len(arguments) in {1, 2}:
        return _lower_vector_as_extension_type_call(
            context,
            syntax,
            source,
            alias_bindings,
        )

    if name == "select" and len(arguments) == 3:
        return _lower_select_type_call(context, syntax, source, alias_bindings)

    return _unsupported_type_expression_diagnostic(syntax.source_text, source)


def _lower_signedness_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    value = _lower_type_expression_value(
        context,
        syntax.arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(value, Diagnostic):
        return value
    return _lower_signedness_transform(
        "signed_of" if syntax.name == "base::signed_of" else "unsigned_of",
        value,
    )


def _lower_base_generic_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    value = _lower_type_expression_value(
        context,
        syntax.arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(value, Diagnostic):
        return value
    return LoweredBaseTransformType(transform="generic", value=value)


def _lower_register_generic_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    value = _lower_type_expression_value(
        context,
        syntax.arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(value, Diagnostic):
        return value
    return LoweredGenericRegisterType(vector_type=value)


def _lower_vector_transform_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    value = _lower_type_expression_value(
        context,
        syntax.arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(value, Diagnostic):
        return value
    return LoweredVectorTransformType(
        transform="transform"
        if syntax.name == "vector::transform"
        else "transform_extension",
        base_type=value,
        extension=context.extension,
    )


def _lower_vector_as_extension_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    extension_name = _lower_extension_operand(
        context,
        syntax.arguments[0],
        source,
    )
    if isinstance(extension_name, Diagnostic):
        return extension_name
    if len(syntax.arguments) == 1:
        base_type: LoweredTypeValue = LoweredCurrentScalarType(
            type_tag=context.type_tag
        )
    else:
        value = _lower_type_expression_value(
            context,
            syntax.arguments[1],
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


def _lower_select_type_call(
    context: SelectedImplementationLoweringContext,
    syntax: TypeCall,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypeValue | Diagnostic:
    condition = _lower_generation_value_predicate(
        context,
        syntax.arguments[0],
        source,
        alias_bindings,
    )
    if isinstance(condition, Diagnostic):
        return condition
    then_type = _lower_type_expression_value(
        context,
        syntax.arguments[1],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(then_type, Diagnostic):
        return then_type
    else_type = _lower_type_expression_value(
        context,
        syntax.arguments[2],
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


def _lower_generation_value_predicate(
    context: SelectedImplementationLoweringContext,
    syntax: TypeSyntax,
    source: SourceLocation,
    alias_bindings: tuple[LoweredTypeAliasBinding, ...],
) -> LoweredTypePredicate | Diagnostic:
    if (
        not isinstance(syntax, TypeQuery)
        or syntax.kind != "generation_value"
        or not isinstance(syntax.expression, TypeCall)
    ):
        return _unsupported_type_expression_diagnostic(syntax.source_text, source)

    call = syntax.expression
    if call.name != "type::is_same" or len(call.arguments) != 2:
        return _unsupported_type_expression_diagnostic(syntax.source_text, source)

    left = _lower_type_expression_value(
        context,
        call.arguments[0],
        source,
        alias_bindings,
        allow_specialization_symbol=True,
    )
    if isinstance(left, Diagnostic):
        return left
    right = _lower_type_expression_value(
        context,
        call.arguments[1],
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
        return LoweredScalarTypeIdentity(type_tag=TypeTag(counterparts[type_tag]))
    return LoweredBaseTransformType(transform=transform, value=value)


def _scalar_type_tag(value: LoweredTypeValue) -> str | None:
    if isinstance(value, LoweredCurrentScalarType | LoweredScalarTypeIdentity):
        return value.type_tag
    return None


def _lower_extension_operand(
    context: SelectedImplementationLoweringContext,
    syntax: TypeSyntax,
    source: SourceLocation,
) -> ExtensionName | Diagnostic:
    if not isinstance(syntax, TypeIdentifier):
        return _unsupported_type_expression_diagnostic(syntax.source_text, source)

    binding = _find_selected_specialization_binding(context, syntax.name)
    if isinstance(binding, Diagnostic):
        return binding
    if binding is None:
        declaration = context.primitive.return_type_binding
        if (
            declaration is not None
            and declaration.kind == "extension"
            and declaration.name == syntax.name
        ):
            return _unbound_selected_specialization_binding_diagnostic(
                syntax.name,
                source,
            )
        return ExtensionName(syntax.name)
    diagnostic = _selected_specialization_binding_validation_diagnostic(
        context,
        binding,
        source,
    )
    if diagnostic is not None:
        return diagnostic
    if isinstance(binding, TargetReturnTypeExtensionBinding):
        return binding.extension
    return _selected_specialization_binding_kind_diagnostic(
        binding.name,
        "return_type.extension",
        _selected_specialization_binding_kind(binding),
        source,
    )


def _selected_specialization_binding_value(
    context: SelectedImplementationLoweringContext,
    name: str,
    source: SourceLocation,
) -> LoweredTypeValue | Diagnostic | None:
    binding = _find_selected_specialization_binding(context, name)
    if isinstance(binding, Diagnostic) or binding is None:
        return binding

    diagnostic = _selected_specialization_binding_validation_diagnostic(
        context,
        binding,
        source,
    )
    if diagnostic is not None:
        return diagnostic

    if isinstance(binding, TargetReturnTypeBaseBinding):
        return LoweredScalarTypeIdentity(type_tag=binding.type_tag)
    if isinstance(binding, TargetVectorTypeBinding):
        return CurrentVector(
            extension=binding.extension,
            type_tag=binding.type_tag,
        )
    return _selected_specialization_binding_kind_diagnostic(
        name,
        "return_type.base or type.vector",
        _selected_specialization_binding_kind(binding),
        source,
    )


def _find_selected_specialization_binding(
    context: SelectedImplementationLoweringContext,
    name: str,
) -> TargetSpecializationBinding | Diagnostic | None:
    bindings = tuple(
        binding
        for binding in context.selected_specialization_bindings
        if binding.name == name
    )
    if not bindings:
        return None
    if len(bindings) > 1:
        return _duplicate_selected_specialization_binding_diagnostic(
            name,
            context.primitive_source,
        )
    return bindings[0]


def _selected_specialization_binding_diagnostics(
    context: SelectedImplementationLoweringContext,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_names: set[str] = set()
    duplicate_names: set[str] = set()
    for binding in context.selected_specialization_bindings:
        if _ALIAS_NAME_RE.fullmatch(binding.name) is None:
            diagnostics.append(
                _malformed_selected_specialization_binding_diagnostic(
                    binding.name,
                    context.primitive_source,
                )
            )
        if binding.name in seen_names and binding.name not in duplicate_names:
            diagnostics.append(
                _duplicate_selected_specialization_binding_diagnostic(
                    binding.name,
                    context.primitive_source,
                )
            )
            duplicate_names.add(binding.name)
        seen_names.add(binding.name)
        validation = _selected_specialization_binding_validation_diagnostic(
            context,
            binding,
            context.primitive_source,
        )
        if validation is not None:
            diagnostics.append(validation)
    return tuple(diagnostics)


def _selected_specialization_binding_validation_diagnostic(
    context: SelectedImplementationLoweringContext,
    binding: TargetSpecializationBinding,
    source: SourceLocation,
) -> Diagnostic | None:
    if not isinstance(
        binding,
        TargetReturnTypeBaseBinding | TargetReturnTypeExtensionBinding,
    ):
        return None

    declaration = context.primitive.return_type_binding
    if declaration is None:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNDECLARED-SELECTED-SPECIALIZATION-BINDING",
            message=(
                "selected return-type specialization binding "
                f"{binding.name!r} has no primitive-local return_type "
                "declaration to validate against"
            ),
            location=source,
        )

    expected_kind = (
        "base"
        if isinstance(binding, TargetReturnTypeBaseBinding)
        else "extension"
    )
    if declaration.name != binding.name or declaration.kind != expected_kind:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
            message=(
                "selected return-type specialization binding does not match "
                "the primitive-local return_type declaration; expected "
                f"{declaration.kind} binding {declaration.name!r}, got "
                f"{expected_kind} binding {binding.name!r}"
            ),
            location=source,
        )

    return None


def _selected_specialization_binding_kind(
    binding: TargetSpecializationBinding,
) -> str:
    if isinstance(binding, TargetReturnTypeBaseBinding):
        return "return_type.base"
    if isinstance(binding, TargetReturnTypeExtensionBinding):
        return "return_type.extension"
    if isinstance(binding, TargetVectorTypeBinding):
        return "type.vector"
    raise AssertionError(f"unsupported specialization binding: {binding!r}")


def _selected_specialization_binding_kind_diagnostic(
    name: str,
    expected: str,
    actual: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-KIND-MISMATCH",
        message=(
            "selected specialization binding has the wrong kind for this "
            f"type expression; symbol {name!r} expected {expected}, got {actual}"
        ),
        location=source,
    )


def _malformed_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization binding name is malformed; expected an "
            f"identifier, got {name!r}"
        ),
        location=source,
    )


def _duplicate_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-DUPLICATE-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization binding names must be unique; duplicate "
            f"binding for {name!r}"
        ),
        location=source,
    )


def _unbound_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNBOUND-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization symbol has a primitive-local "
            f"declaration but no selected binding was supplied for {name!r}"
        ),
        location=source,
    )


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
    parts = split_top_level_arguments(payload)
    if parts is None or len(parts) != 2:
        return None
    return (parts[0], parts[1])


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
