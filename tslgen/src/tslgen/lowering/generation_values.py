"""Selected-context generation value query lowering."""

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, Extension, PrimitiveAttribute
from tslgen.lowering.model import (
    GenerationValueQueryLoweringResult,
    LoweredCurrentScalarType,
    LoweredGenerationValue,
    LoweredScalarTypeIdentity,
    LoweredTypeValue,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.scalar_types import (
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
)
from tslgen.lowering.type_queries import lower_type_expression
from tslgen.lowering.type_syntax import (
    TypeCall,
    TypeIdentifier,
    TypeIntegerLiteral,
    TypeQuery,
    TypeSyntax,
    parse_type_syntax,
)

_GENERATION_ARITHMETIC_PREFIX = "arith<generation>::"
_GENERATION_ARITHMETIC_OPERATIONS = frozenset(("add", "sub", "mul", "div", "rem"))


def lower_generation_value_query(
    context: SelectedImplementationLoweringContext,
    query: str,
    source: SourceLocation,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationValueQueryLoweringResult:
    parsed = parse_type_syntax(query)
    if not isinstance(parsed, TypeQuery) or parsed.kind != "generation_value":
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(_malformed_generation_value_query_diagnostic(query, source),),
        )

    return _lower_generation_value_expression(
        context,
        parsed.expression,
        parsed.source_text,
        source,
        catalog=catalog,
        environment=environment,
        allow_integer_literal=False,
    )


def _lower_generation_value_expression(
    context: SelectedImplementationLoweringContext,
    expression: TypeSyntax,
    source_text: str,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
    allow_integer_literal: bool,
) -> GenerationValueQueryLoweringResult:
    if isinstance(expression, TypeIntegerLiteral):
        if not allow_integer_literal:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _unsupported_generation_value_query_diagnostic(
                        source_text,
                        source,
                    ),
                ),
            )
        return GenerationValueQueryLoweringResult(
            value=LoweredGenerationValue(
                kind="generation.integer_literal",
                value=expression.value,
                source_text=source_text,
                source=source,
            ),
            diagnostics=(),
        )
    if isinstance(expression, TypeIdentifier):
        return _lower_identifier_value(
            context,
            source_text,
            expression,
            source,
            catalog,
        )
    if isinstance(expression, TypeCall):
        return _lower_call_value(
            context,
            source_text,
            expression,
            source,
            catalog=catalog,
            environment=environment,
            allow_integer_literal=allow_integer_literal,
        )

    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(source_text, source),
        ),
    )


def _lower_identifier_value(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    expression: TypeIdentifier,
    source: SourceLocation,
    catalog: Catalog | None,
) -> GenerationValueQueryLoweringResult:
    if expression.name == "vector::length":
        return _lower_vector_length(context, source_text, source, catalog)
    if expression.name == "vector::alignment":
        return _lower_vector_alignment(context, source_text, source, catalog)
    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(
                source_text,
                source,
            ),
        ),
    )


def _lower_call_value(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    call: TypeCall,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
    allow_integer_literal: bool,
) -> GenerationValueQueryLoweringResult:
    arithmetic_operation = _generation_arithmetic_operation(call.name)
    if arithmetic_operation is not None:
        return _lower_generation_arithmetic_value(
            context,
            source_text,
            arithmetic_operation,
            call,
            source,
            catalog=catalog,
            environment=environment,
        )

    if call.name.startswith(_GENERATION_ARITHMETIC_PREFIX):
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _unsupported_generation_arithmetic_diagnostic(
                    call.name.removeprefix(_GENERATION_ARITHMETIC_PREFIX),
                    source,
                ),
            ),
        )

    if call.name == "type::size_bytes":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(source_text, source)
        return _lower_type_size_bytes(context, source_text, call, source, environment)

    if call.name == "type::is_signed":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(source_text, source)
        return _lower_type_is_signed(context, source_text, call, source, environment)

    if call.name == "type::is_same":
        if len(call.arguments) != 2:
            return _malformed_generation_value_query_result(source_text, source)
        return _lower_type_is_same(context, source_text, call, source, environment)

    if call.name == "primitive::attribute":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(source_text, source)
        return _lower_primitive_attribute(context, source_text, call, source)

    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(
                source_text,
                source,
            ),
        ),
    )


def _generation_arithmetic_operation(call_name: str) -> str | None:
    if not call_name.startswith(_GENERATION_ARITHMETIC_PREFIX):
        return None
    operation = call_name.removeprefix(_GENERATION_ARITHMETIC_PREFIX)
    if operation in _GENERATION_ARITHMETIC_OPERATIONS:
        return operation
    return None


def _lower_generation_arithmetic_value(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    operation: str,
    call: TypeCall,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    if len(call.arguments) != 2:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _malformed_generation_arithmetic_diagnostic(
                    call.source_text,
                    source,
                    "expected exactly two arguments",
                ),
            ),
        )

    left_result = _lower_generation_value_expression(
        context,
        call.arguments[0],
        call.arguments[0].source_text,
        source,
        catalog=catalog,
        environment=environment,
        allow_integer_literal=True,
    )
    if left_result.value is None:
        return left_result
    right_result = _lower_generation_value_expression(
        context,
        call.arguments[1],
        call.arguments[1].source_text,
        source,
        catalog=catalog,
        environment=environment,
        allow_integer_literal=True,
    )
    if right_result.value is None:
        return right_result

    left = left_result.value
    right = right_result.value
    if type(left.value) is not int:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _noninteger_generation_arithmetic_operand_diagnostic(
                    left.source_text,
                    source,
                ),
            ),
        )
    if type(right.value) is not int:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _noninteger_generation_arithmetic_operand_diagnostic(
                    right.source_text,
                    source,
                ),
            ),
        )
    if operation in {"div", "rem"} and right.value == 0:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _zero_divisor_generation_arithmetic_diagnostic(
                    call.source_text,
                    source,
                    operation,
                ),
            ),
        )

    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind=f"generation.arithmetic.{operation}",
            value=_evaluate_generation_arithmetic(
                operation,
                left.value,
                right.value,
            ),
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _evaluate_generation_arithmetic(
    operation: str,
    left: int,
    right: int,
) -> int:
    if operation == "add":
        return left + right
    if operation == "sub":
        return left - right
    if operation == "mul":
        return left * right
    if operation == "div":
        return _truncating_integer_division(left, right)
    if operation == "rem":
        return left - (_truncating_integer_division(left, right) * right)
    raise AssertionError(f"unsupported generation arithmetic operation {operation!r}")


def _truncating_integer_division(left: int, right: int) -> int:
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        return -quotient
    return quotient


def _lower_vector_length(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    source: SourceLocation,
    catalog: Catalog | None,
) -> GenerationValueQueryLoweringResult:
    metadata = _fixed_vector_metadata(context, catalog, source)
    if isinstance(metadata, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(metadata,))
    _, descriptor, vector_bits = metadata

    if str(context.extension) == "scalar" and vector_bits == 0:
        lane_count = 1
    else:
        if vector_bits <= 0 or vector_bits % descriptor.bit_width != 0:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _missing_vector_metadata_diagnostic(
                        context,
                        source,
                        "fixed positive vector_bits divisible by scalar bit width",
                    ),
                ),
            )
        lane_count = vector_bits // descriptor.bit_width

    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="vector.length",
            value=lane_count,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _lower_vector_alignment(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    source: SourceLocation,
    catalog: Catalog | None,
) -> GenerationValueQueryLoweringResult:
    metadata = _fixed_vector_metadata(context, catalog, source)
    if isinstance(metadata, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(metadata,))
    _, descriptor, vector_bits = metadata

    if str(context.extension) == "scalar" and vector_bits == 0:
        alignment = descriptor.bit_width // 8
    else:
        if vector_bits <= 0 or vector_bits % 8 != 0:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _missing_vector_metadata_diagnostic(
                        context,
                        source,
                        "fixed positive byte-aligned vector_bits",
                    ),
                ),
            )
        alignment = vector_bits // 8

    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="vector.alignment",
            value=alignment,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _lower_type_size_bytes(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    call: TypeCall,
    source: SourceLocation,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    descriptor = _lower_scalar_type_argument(
        context,
        call.arguments[0],
        source,
        environment,
    )
    if isinstance(descriptor, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(descriptor,))
    if descriptor.bit_width % 8 != 0:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _missing_scalar_fact_diagnostic(
                    str(descriptor.tag),
                    source,
                    "byte size",
                ),
            ),
        )
    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="type.size_bytes",
            value=descriptor.bit_width // 8,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _lower_type_is_signed(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    call: TypeCall,
    source: SourceLocation,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    descriptor = _lower_scalar_type_argument(
        context,
        call.arguments[0],
        source,
        environment,
    )
    if isinstance(descriptor, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(descriptor,))
    if descriptor.signedness == "not_applicable":
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _missing_scalar_fact_diagnostic(
                    str(descriptor.tag),
                    source,
                    "integer signedness",
                ),
            ),
        )
    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="type.is_signed",
            value=descriptor.signedness == "signed",
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _lower_type_is_same(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    call: TypeCall,
    source: SourceLocation,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    left = _lower_scalar_type_argument(
        context,
        call.arguments[0],
        source,
        environment,
    )
    if isinstance(left, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(left,))
    right = _lower_scalar_type_argument(
        context,
        call.arguments[1],
        source,
        environment,
    )
    if isinstance(right, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(right,))
    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="type.is_same",
            value=left.tag == right.tag,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _lower_primitive_attribute(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    call: TypeCall,
    source: SourceLocation,
) -> GenerationValueQueryLoweringResult:
    attribute_key = _attribute_key(call.arguments[0])
    if attribute_key is None:
        return _malformed_generation_value_query_result(source_text, source)

    attributes = tuple(
        attribute
        for attribute in context.primitive_attributes
        if attribute.key == attribute_key and attribute.key_argument is None
    )
    if not attributes:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _unknown_primitive_attribute_diagnostic(attribute_key, source),
            ),
        )
    if len(attributes) > 1:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _nonconcrete_primitive_attribute_diagnostic(
                    attribute_key,
                    tuple(attribute.value for attribute in attributes),
                    source,
                ),
            ),
        )

    attribute = attributes[0]
    if attribute.value == "true":
        value = True
    elif attribute.value == "false":
        value = False
    else:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                _nonconcrete_primitive_attribute_diagnostic(
                    attribute_key,
                    (attribute.value,),
                    source,
                ),
            ),
        )

    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind="primitive.attribute",
            value=value,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def _fixed_vector_metadata(
    context: SelectedImplementationLoweringContext,
    catalog: Catalog | None,
    source: SourceLocation,
) -> tuple[Extension, ScalarTypeDescriptor, int] | Diagnostic:
    descriptor = lookup_scalar_type_descriptor(context.type_tag)
    if descriptor is None:
        return _missing_scalar_fact_diagnostic(
            str(context.type_tag),
            source,
            "scalar bit width",
        )

    if catalog is None:
        return _missing_vector_metadata_diagnostic(
            context,
            source,
            "catalog extension metadata",
        )

    extension = catalog.extensions.get(str(context.extension))
    if extension is None:
        return _missing_vector_metadata_diagnostic(
            context,
            source,
            "known selected extension",
        )

    if not isinstance(extension.vector_bits, int):
        return _missing_vector_metadata_diagnostic(
            context,
            source,
            "fixed integer vector_bits",
        )

    return extension, descriptor, extension.vector_bits


def _lower_scalar_type_argument(
    context: SelectedImplementationLoweringContext,
    syntax: TypeSyntax,
    source: SourceLocation,
    environment: SelectedTypeEnvironment | None,
) -> ScalarTypeDescriptor | Diagnostic:
    result = lower_type_expression(
        context,
        syntax.source_text,
        source,
        environment=environment,
    )
    if result.value is None:
        return result.diagnostics[0]
    type_tag = _scalar_type_tag(result.value)
    if type_tag is None:
        return _unsupported_generation_value_type_diagnostic(
            syntax.source_text,
            source,
        )
    descriptor = lookup_scalar_type_descriptor(type_tag)
    if descriptor is None:
        return _missing_scalar_fact_diagnostic(
            type_tag,
            source,
            "scalar size or signedness",
        )
    return descriptor


def _scalar_type_tag(value: LoweredTypeValue) -> str | None:
    if isinstance(value, LoweredCurrentScalarType | LoweredScalarTypeIdentity):
        return str(value.type_tag)
    return None


def _attribute_key(syntax: TypeSyntax) -> str | None:
    if isinstance(syntax, TypeIdentifier):
        return syntax.name
    return None


def _malformed_generation_value_query_result(
    query: str,
    source: SourceLocation,
) -> GenerationValueQueryLoweringResult:
    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(_malformed_generation_value_query_diagnostic(query, source),),
    )


def _malformed_generation_value_query_diagnostic(
    query: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-VALUE-QUERY",
        message=(
            "generation value query cannot be lowered; expected exactly "
            "value<generation>(GenerationValueExpr), got "
            f"{query!r}"
        ),
        location=source,
    )


def _unsupported_generation_value_query_diagnostic(
    query: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-QUERY",
        message=(
            "generation value query family is not supported by the M155 "
            "isolated value-query boundary; expected vector::length, "
            "vector::alignment, type::size_bytes(...), type::is_signed(...), "
            "type::is_same(...), primitive::attribute(...), or an M159 "
            "arith<generation>::add/sub/mul/div/rem(...) call, got "
            f"{query!r}"
        ),
        location=source,
    )


def _unsupported_generation_value_type_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-VALUE-TYPE",
        message=(
            "generation value query type argument lowered to an unsupported "
            "type value; M155 evaluates only scalar type values, got "
            f"{expression!r}"
        ),
        location=source,
    )


def _malformed_generation_arithmetic_diagnostic(
    expression: str,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-ARITHMETIC",
        message=(
            "generation arithmetic value call cannot be lowered; "
            f"{reason}; got {expression!r}"
        ),
        location=source,
    )


def _unsupported_generation_arithmetic_diagnostic(
    operation: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-ARITHMETIC",
        message=(
            "generation arithmetic operation is not supported by M159; "
            "expected one of add, sub, mul, div, or rem, got "
            f"{operation!r}"
        ),
        location=source,
    )


def _noninteger_generation_arithmetic_operand_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONINTEGER-GENERATION-ARITHMETIC-OPERAND",
        message=(
            "generation arithmetic operands must lower to integer generation "
            f"values; got {expression!r}"
        ),
        location=source,
    )


def _zero_divisor_generation_arithmetic_diagnostic(
    expression: str,
    source: SourceLocation,
    operation: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-ZERO-DIVISOR-GENERATION-ARITHMETIC",
        message=(
            "generation arithmetic division and remainder require a non-zero "
            f"right operand; operation {operation!r} got {expression!r}"
        ),
        location=source,
    )


def _missing_vector_metadata_diagnostic(
    context: SelectedImplementationLoweringContext,
    source: SourceLocation,
    expected: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MISSING-VECTOR-METADATA",
        message=(
            "generation value query requires selected extension vector "
            f"metadata for extension {str(context.extension)!r} and type "
            f"{str(context.type_tag)!r}; expected {expected}"
        ),
        location=source,
    )


def _missing_scalar_fact_diagnostic(
    type_tag: str,
    source: SourceLocation,
    expected: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MISSING-SCALAR-FACT",
        message=(
            f"generation value query requires {expected} for scalar type "
            f"{type_tag!r}"
        ),
        location=source,
    )


def _unknown_primitive_attribute_diagnostic(
    attribute_key: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNKNOWN-PRIMITIVE-ATTRIBUTE",
        message=(
            "generation value query references primitive attribute "
            f"{attribute_key!r}, but the selected primitive has no concrete "
            "attribute with that key"
        ),
        location=source,
    )


def _nonconcrete_primitive_attribute_diagnostic(
    attribute_key: str,
    values: tuple[str, ...],
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONCONCRETE-PRIMITIVE-ATTRIBUTE",
        message=(
            "generation value query can only evaluate concrete boolean "
            f"primitive attributes; attribute {attribute_key!r} has value(s) "
            f"{values!r}"
        ),
        location=source,
    )
