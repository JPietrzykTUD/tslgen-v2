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
    TypeQuery,
    TypeSyntax,
    parse_type_syntax,
)


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

    expression = parsed.expression
    if isinstance(expression, TypeIdentifier):
        return _lower_identifier_value(context, parsed, expression, source, catalog)
    if isinstance(expression, TypeCall):
        return _lower_call_value(
            context,
            parsed,
            expression,
            source,
            catalog=catalog,
            environment=environment,
        )

    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(query, source),
        ),
    )


def _lower_identifier_value(
    context: SelectedImplementationLoweringContext,
    query: TypeQuery,
    expression: TypeIdentifier,
    source: SourceLocation,
    catalog: Catalog | None,
) -> GenerationValueQueryLoweringResult:
    if expression.name == "vector::length":
        return _lower_vector_length(context, query.source_text, source, catalog)
    if expression.name == "vector::alignment":
        return _lower_vector_alignment(context, query.source_text, source, catalog)
    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(
                query.source_text,
                source,
            ),
        ),
    )


def _lower_call_value(
    context: SelectedImplementationLoweringContext,
    query: TypeQuery,
    call: TypeCall,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    if call.name == "type::size_bytes":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(query.source_text, source)
        return _lower_type_size_bytes(context, query.source_text, call, source, environment)

    if call.name == "type::is_signed":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(query.source_text, source)
        return _lower_type_is_signed(context, query.source_text, call, source, environment)

    if call.name == "type::is_same":
        if len(call.arguments) != 2:
            return _malformed_generation_value_query_result(query.source_text, source)
        return _lower_type_is_same(context, query.source_text, call, source, environment)

    if call.name == "primitive::attribute":
        if len(call.arguments) != 1:
            return _malformed_generation_value_query_result(query.source_text, source)
        return _lower_primitive_attribute(context, query.source_text, call, source)

    return GenerationValueQueryLoweringResult(
        value=None,
        diagnostics=(
            _unsupported_generation_value_query_diagnostic(
                query.source_text,
                source,
            ),
        ),
    )


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
            "type::is_same(...), or primitive::attribute(...), got "
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
