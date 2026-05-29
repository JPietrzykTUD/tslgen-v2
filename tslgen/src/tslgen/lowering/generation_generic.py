"""Exact generic namespace generation-expression lowering."""

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog
from tslgen.lowering.model import (
    CurrentVector,
    GenerationValueQueryLoweringResult,
    LoweredBackendTypeReference,
    LoweredCurrentScalarType,
    LoweredGenerationValue,
    LoweredScalarTypeIdentity,
    LoweredSpecializationTypeSymbol,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    LoweredVectorTransformType,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.scalar_types import lookup_scalar_type_descriptor
from tslgen.lowering.type_queries import lower_type_expression
from tslgen.lowering.type_syntax import TypeCall, TypeSyntax

GENERIC_GENERATION_PREFIX = "generic::"
_GENERIC_GENERATION_OPERATIONS = frozenset(("length", "runtime_length"))


def generic_generation_operation(call_name: str) -> str | None:
    if not call_name.startswith(GENERIC_GENERATION_PREFIX):
        return None
    operation = call_name.removeprefix(GENERIC_GENERATION_PREFIX)
    if operation in _GENERIC_GENERATION_OPERATIONS:
        return operation
    return None


def lower_generic_generation_value(
    context: SelectedImplementationLoweringContext,
    source_text: str,
    operation: str,
    call: TypeCall,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> GenerationValueQueryLoweringResult:
    if len(call.arguments) != 1:
        return GenerationValueQueryLoweringResult(
            value=None,
            diagnostics=(
                malformed_generic_generation_expression_diagnostic(
                    call.source_text,
                    source,
                    "expected exactly one type argument",
                ),
            ),
        )

    vector_type = _lower_generic_vector_argument(
        context,
        call.arguments[0],
        source,
        environment,
    )
    if isinstance(vector_type, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(vector_type,))

    extension_name, type_tag = vector_type
    lane_count = _fixed_lane_count_for_generic_vector(
        extension_name,
        type_tag,
        catalog,
        source,
    )
    if isinstance(lane_count, Diagnostic):
        return GenerationValueQueryLoweringResult(value=None, diagnostics=(lane_count,))

    return GenerationValueQueryLoweringResult(
        value=LoweredGenerationValue(
            kind=f"generic.{operation}",
            value=lane_count,
            source_text=source_text,
            source=source,
        ),
        diagnostics=(),
    )


def unsupported_generic_generation_expression_diagnostic(
    operation: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERIC-GENERATION-EXPRESSION",
        message=(
            "generic generation expression operation is not supported by "
            "M168; expected length or runtime_length, got "
            f"{operation!r}"
        ),
        location=source,
    )


def malformed_generic_generation_expression_diagnostic(
    expression: str,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERIC-GENERATION-EXPRESSION",
        message=(
            "generic generation expression cannot be lowered; "
            f"{reason}; got {expression!r}"
        ),
        location=source,
    )


def _lower_generic_vector_argument(
    context: SelectedImplementationLoweringContext,
    syntax: TypeSyntax,
    source: SourceLocation,
    environment: SelectedTypeEnvironment | None,
) -> tuple[str, str] | Diagnostic:
    result = lower_type_expression(
        context,
        syntax.source_text,
        source,
        environment=environment,
    )
    if result.value is None:
        return result.diagnostics[0]
    return _concrete_generic_vector_type(syntax.source_text, result.value, source)


def _concrete_generic_vector_type(
    expression: str,
    value: LoweredTypeValue,
    source: SourceLocation,
) -> tuple[str, str] | Diagnostic:
    if isinstance(value, CurrentVector):
        return (str(value.extension), str(value.type_tag))

    if isinstance(value, LoweredVectorTransformType):
        type_tag = _generic_vector_scalar_type_tag(value.base_type)
        if type_tag is not None:
            return (str(value.extension), type_tag)
        if _contains_unresolved_specialization(value.base_type):
            return _unresolved_generic_vector_type_diagnostic(expression, source)
        return _unsupported_generic_vector_type_diagnostic(expression, source)

    if isinstance(value, LoweredVectorAsExtensionType):
        type_tag = _generic_vector_scalar_type_tag(value.base_type)
        if type_tag is not None:
            return (str(value.extension), type_tag)
        if _contains_unresolved_specialization(value.base_type):
            return _unresolved_generic_vector_type_diagnostic(expression, source)
        return _unsupported_generic_vector_type_diagnostic(expression, source)

    if _contains_unresolved_specialization(value):
        return _unresolved_generic_vector_type_diagnostic(expression, source)
    return _unsupported_generic_vector_type_diagnostic(expression, source)


def _generic_vector_scalar_type_tag(value: LoweredTypeValue) -> str | None:
    if isinstance(value, LoweredCurrentScalarType | LoweredScalarTypeIdentity):
        return str(value.type_tag)
    if isinstance(value, LoweredBackendTypeReference):
        return _generic_vector_scalar_type_tag(value.request.value)
    return None


def _contains_unresolved_specialization(value: LoweredTypeValue) -> bool:
    if isinstance(value, LoweredSpecializationTypeSymbol):
        return True
    if isinstance(value, LoweredBackendTypeReference):
        return _contains_unresolved_specialization(value.request.value)
    if isinstance(value, LoweredVectorTransformType | LoweredVectorAsExtensionType):
        return _contains_unresolved_specialization(value.base_type)
    return False


def _fixed_lane_count_for_generic_vector(
    extension_name: str,
    type_tag: str,
    catalog: Catalog | None,
    source: SourceLocation,
) -> int | Diagnostic:
    descriptor = lookup_scalar_type_descriptor(type_tag)
    if descriptor is None:
        return _missing_scalar_fact_diagnostic(
            type_tag,
            source,
            "scalar bit width",
        )

    if catalog is None:
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "catalog extension metadata",
        )

    extension = catalog.extensions.get(extension_name)
    if extension is None:
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "known vector extension",
        )

    if extension.runtime_lanes:
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "non-runtime fixed vector lanes",
        )

    if extension.size_parameter is not None:
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "fixed vector_bits independent of size parameters",
        )

    if not isinstance(extension.vector_bits, int):
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "fixed integer vector_bits",
        )

    if extension_name == "scalar" and extension.vector_bits == 0:
        return 1

    if extension.vector_bits <= 0 or extension.vector_bits % descriptor.bit_width != 0:
        return _missing_generic_vector_metadata_diagnostic(
            extension_name,
            type_tag,
            source,
            "fixed positive vector_bits divisible by scalar bit width",
        )

    return extension.vector_bits // descriptor.bit_width


def _unsupported_generic_vector_type_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERIC-VECTOR-TYPE",
        message=(
            "generic generation expression requires a lowered concrete "
            "vector type value; expected Vec, vector::transform_extension(...), "
            "vector::as_extension(...), or an alias to one of those values, "
            f"got {expression!r}"
        ),
        location=source,
    )


def _unresolved_generic_vector_type_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNRESOLVED-GENERIC-VECTOR-TYPE",
        message=(
            "generic generation expression requires a concrete vector type, "
            "but the lowered type still contains an unresolved specialization "
            f"symbol; got {expression!r}"
        ),
        location=source,
    )


def _missing_generic_vector_metadata_diagnostic(
    extension_name: str,
    type_tag: str,
    source: SourceLocation,
    expected: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MISSING-GENERIC-VECTOR-METADATA",
        message=(
            "generic generation expression requires fixed vector lane "
            f"metadata for extension {extension_name!r} and scalar type "
            f"{type_tag!r}; expected {expected}"
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
