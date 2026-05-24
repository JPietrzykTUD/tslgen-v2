"""Selected-implementation lowering for the exact tiny clean operation bodies."""

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import BinaryOperationBody, UnaryOperationBody
from tslgen.lowering.binary_operations import (
    BinaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    supported_binary_operation_ids,
)
from tslgen.lowering.model import (
    LoweredBinaryOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredUnaryOperationExpression,
)
from tslgen.lowering.operation_type_compatibility import (
    binary_operation_supports_scalar_type,
    supported_scalar_type_tags_for_binary_operation,
    supported_scalar_type_tags_for_unary_operation,
    unary_operation_supports_scalar_type,
)
from tslgen.lowering.scalar_types import (
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)
from tslgen.lowering.unary_operations import (
    UnaryOperationDescriptor,
    lookup_unary_operation_descriptor,
    supported_unary_operation_ids,
)

_SUPPORTED_BINARY_TEMPLATE = "binary"
_SUPPORTED_UNARY_TEMPLATE = "unary"
_SUPPORTED_EXTENSION = "scalar"
_SUPPORTED_BINARY_PARAMETERS = ("left", "right")
_SUPPORTED_UNARY_PARAMETERS = ("value",)


@dataclass(frozen=True, slots=True)
class LoweringResult:
    function: LoweredFunction | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweringStageResult:
    lowered_functions: LoweredFunctionSet
    diagnostics: tuple[Diagnostic, ...]


class Lowerer:
    """Lower only the selected scalar operation implementation shapes."""

    def lower_all(
        self,
        selected: Iterable[SelectedImplementation],
    ) -> LoweringStageResult:
        functions: list[LoweredFunction] = []
        diagnostics: list[Diagnostic] = []

        for item in selected:
            result = self.lower(item)
            diagnostics.extend(result.diagnostics)
            if result.function is not None:
                functions.append(result.function)

        return LoweringStageResult(
            lowered_functions=LoweredFunctionSet(tuple(functions)),
            diagnostics=tuple(diagnostics),
        )

    def lower(self, selected: SelectedImplementation) -> LoweringResult:
        scalar_type = lookup_scalar_type_descriptor(selected.implementation.type_tag)
        body = selected.implementation.body
        if isinstance(body, BinaryOperationBody):
            operation = lookup_binary_operation_descriptor(selected.primitive.name)
            diagnostics = tuple(
                _unsupported_binary_diagnostics(
                    selected,
                    body,
                    scalar_type,
                    operation,
                )
            )
            if diagnostics or scalar_type is None or operation is None:
                return LoweringResult(function=None, diagnostics=diagnostics)
            return LoweringResult(
                function=_lower_binary_function(selected, body, scalar_type, operation),
                diagnostics=(),
            )

        operation = lookup_unary_operation_descriptor(selected.primitive.name)
        diagnostics = tuple(
            _unsupported_unary_diagnostics(
                selected,
                body,
                scalar_type,
                operation,
            )
        )
        if diagnostics or scalar_type is None or operation is None:
            return LoweringResult(function=None, diagnostics=diagnostics)

        return LoweringResult(
            function=_lower_unary_function(selected, body, scalar_type, operation),
            diagnostics=(),
        )


def _unsupported_binary_diagnostics(
    selected: SelectedImplementation,
    body: BinaryOperationBody,
    scalar_type: ScalarTypeDescriptor | None,
    operation: BinaryOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if operation is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION",
                message=(
                    f"operation {selected.primitive.name!r} cannot be lowered; "
                    "expected one of: "
                    f"{', '.join(supported_binary_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_BINARY_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_BINARY_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_BINARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_BINARY_PARAMETERS!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.implementation.extension != _SUPPORTED_EXTENSION:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-EXTENSION",
                message=(
                    f"implementation extension "
                    f"{selected.implementation.extension!r} cannot be lowered by "
                    f"the tiny clean lowerer; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if scalar_type is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    "cannot be lowered; expected one of: "
                    f"{', '.join(supported_scalar_type_tags())}"
                ),
                location=selected.implementation.source,
            )
        )

    if (
        operation is not None
        and scalar_type is not None
        and not binary_operation_supports_scalar_type(operation, scalar_type)
    ):
        supported_type_tags = supported_scalar_type_tags_for_binary_operation(operation)
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION-TYPE",
                message=(
                    f"operation {operation.operation_id!r} cannot be lowered for "
                    f"scalar type {scalar_type.tag!r}; expected one of: "
                    f"{', '.join(supported_type_tags)}"
                ),
                location=selected.implementation.source,
            )
        )

    if operation is not None and body.operation != operation.source_body_operation:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{body.operation!r}"
                ),
                location=body.source,
            )
        )

    if (
        body.left_parameter != _SUPPORTED_BINARY_PARAMETERS[0]
        or body.right_parameter != _SUPPORTED_BINARY_PARAMETERS[1]
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{body.operation}(left, right)'"
                ),
                location=body.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_unary_diagnostics(
    selected: SelectedImplementation,
    body: UnaryOperationBody,
    scalar_type: ScalarTypeDescriptor | None,
    operation: UnaryOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if operation is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION",
                message=(
                    f"operation {selected.primitive.name!r} cannot be lowered; "
                    "expected one of: "
                    f"{', '.join(supported_unary_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_UNARY_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_UNARY_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_UNARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_UNARY_PARAMETERS!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.implementation.extension != _SUPPORTED_EXTENSION:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-EXTENSION",
                message=(
                    f"implementation extension "
                    f"{selected.implementation.extension!r} cannot be lowered by "
                    f"the tiny clean lowerer; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if scalar_type is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    "cannot be lowered; expected one of: "
                    f"{', '.join(supported_scalar_type_tags())}"
                ),
                location=selected.implementation.source,
            )
        )

    if (
        operation is not None
        and scalar_type is not None
        and not unary_operation_supports_scalar_type(operation, scalar_type)
    ):
        supported_type_tags = supported_scalar_type_tags_for_unary_operation(operation)
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION-TYPE",
                message=(
                    f"operation {operation.operation_id!r} cannot be lowered for "
                    f"scalar type {scalar_type.tag!r}; expected one of: "
                    f"{', '.join(supported_type_tags)}"
                ),
                location=selected.implementation.source,
            )
        )

    if operation is not None and body.operation != operation.source_body_operation:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{body.operation!r}"
                ),
                location=body.source,
            )
        )

    if body.value_parameter != _SUPPORTED_UNARY_PARAMETERS[0]:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{body.operation}(value)'"
                ),
                location=body.source,
            )
        )

    return tuple(diagnostics)


def _lower_binary_function(
    selected: SelectedImplementation,
    body: BinaryOperationBody,
    scalar_type: ScalarTypeDescriptor,
    operation: BinaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(selected, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=operation,
                    left=LoweredParameterRef(body.left_parameter),
                    right=LoweredParameterRef(body.right_parameter),
                ),
                source=body.source,
            ),
        ),
        source=selected.implementation.source,
    )


def _lower_unary_function(
    selected: SelectedImplementation,
    body: UnaryOperationBody,
    scalar_type: ScalarTypeDescriptor,
    operation: UnaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(selected, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredUnaryOperationExpression(
                    operation=operation,
                    value=LoweredParameterRef(body.value_parameter),
                ),
                source=body.source,
            ),
        ),
        source=selected.implementation.source,
    )


def _signature(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor,
) -> LoweredFunctionSignature:
    return LoweredFunctionSignature(
        name=_function_name(selected),
        primitive_name=selected.primitive.name,
        parameters=tuple(
            LoweredParameter(name=name) for name in selected.primitive.parameters
        ),
        scalar_type=scalar_type,
    )


def _function_name(selected: SelectedImplementation) -> str:
    return (
        f"{selected.primitive.name}_"
        f"{selected.implementation.extension}_"
        f"{selected.implementation.type_tag}"
    )
