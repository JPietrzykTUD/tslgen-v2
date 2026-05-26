"""Selected-implementation lowering for the exact tiny clean operation bodies."""

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
    ImplementationBody,
    LowerableOperationFragment,
    SegmentedLine,
)
from tslgen.lowering.binary_operations import (
    BinaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    supported_binary_operation_ids,
)
from tslgen.lowering.comparison_operations import (
    ComparisonOperationDescriptor,
    lookup_comparison_operation_descriptor,
    supported_comparison_operation_ids,
)
from tslgen.lowering.model import (
    INPUT_SCALAR_RESULT_TYPE,
    SCALAR_COMPARISON_RESULT_TYPE,
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredResultType,
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
_SUPPORTED_COMPARISON_TEMPLATE = "compare"
_SUPPORTED_EXTENSION = "scalar"
_SUPPORTED_BINARY_PARAMETERS = ("left", "right")
_SUPPORTED_UNARY_PARAMETERS = ("value",)
_SUPPORTED_COMPARISON_PARAMETERS = ("left", "right")


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
        fragment = _operation_fragment_from_body(body)
        if selected.primitive.template == _SUPPORTED_COMPARISON_TEMPLATE:
            operation = lookup_comparison_operation_descriptor(selected.primitive.name)
            diagnostics = tuple(
                _unsupported_comparison_diagnostics(
                    selected,
                    body,
                    fragment,
                    scalar_type,
                    operation,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)
            return LoweringResult(
                function=_lower_comparison_function(
                    selected,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        if selected.primitive.template == _SUPPORTED_UNARY_TEMPLATE:
            operation = lookup_unary_operation_descriptor(selected.primitive.name)
            diagnostics = tuple(
                _unsupported_unary_diagnostics(
                    selected,
                    body,
                    fragment,
                    scalar_type,
                    operation,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)

            return LoweringResult(
                function=_lower_unary_function(
                    selected,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        if selected.primitive.template == _SUPPORTED_BINARY_TEMPLATE:
            operation = lookup_binary_operation_descriptor(selected.primitive.name)
            diagnostics = tuple(
                _unsupported_binary_diagnostics(
                    selected,
                    body,
                    fragment,
                    scalar_type,
                    operation,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)
            return LoweringResult(
                function=_lower_binary_function(
                    selected,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        diagnostics = (
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected one of: "
                    f"{_SUPPORTED_BINARY_TEMPLATE}, {_SUPPORTED_UNARY_TEMPLATE}, "
                    f"{_SUPPORTED_COMPARISON_TEMPLATE}"
                ),
                location=selected.primitive.source,
            )
        )
        return LoweringResult(function=None, diagnostics=diagnostics)


def _unsupported_binary_diagnostics(
    selected: SelectedImplementation,
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
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

    if fragment is None:
        diagnostics.append(
            _unsupported_body_shape_diagnostic(
                body,
                _SUPPORTED_BINARY_PARAMETERS,
                selected.primitive.name,
            )
        )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_BINARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(left, right)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_comparison_diagnostics(
    selected: SelectedImplementation,
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: ComparisonOperationDescriptor | None,
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
                    f"{', '.join(supported_comparison_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_COMPARISON_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_COMPARISON_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_COMPARISON_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_COMPARISON_PARAMETERS!r}"
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

    if fragment is None:
        diagnostics.append(
            _unsupported_body_shape_diagnostic(
                body,
                _SUPPORTED_COMPARISON_PARAMETERS,
                selected.primitive.name,
            )
        )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_COMPARISON_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(left, right)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_unary_diagnostics(
    selected: SelectedImplementation,
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
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

    if fragment is None:
        diagnostics.append(
            _unsupported_body_shape_diagnostic(
                body,
                _SUPPORTED_UNARY_PARAMETERS,
                selected.primitive.name,
            )
        )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_UNARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(value)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _operation_fragment_from_body(
    body: ImplementationBody,
) -> LowerableOperationFragment | None:
    if len(body.lines) != 1:
        return None
    line = body.lines[0]
    if not isinstance(line, SegmentedLine):
        return None
    if len(line.segments) != 1:
        return None
    segment = line.segments[0]
    if not isinstance(segment, LowerableOperationFragment):
        return None
    return segment


def _unsupported_body_shape_diagnostic(
    body: ImplementationBody,
    expected_arguments: tuple[str, ...],
    operation_id: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-BODY",
        message=(
            "implementation body cannot be lowered; expected exactly one "
            "segmented line containing "
            f"'{operation_id}({', '.join(expected_arguments)})'"
        ),
        location=body.source,
    )


def _lower_binary_function(
    selected: SelectedImplementation,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: BinaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(selected, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=operation,
                    left=LoweredParameterRef(fragment.arguments[0]),
                    right=LoweredParameterRef(fragment.arguments[1]),
                ),
                source=fragment.source,
            ),
        ),
        source=selected.implementation.source,
    )


def _lower_comparison_function(
    selected: SelectedImplementation,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: ComparisonOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(
            selected,
            scalar_type,
            result_type=SCALAR_COMPARISON_RESULT_TYPE,
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredComparisonOperationExpression(
                    operation=operation,
                    left=LoweredParameterRef(fragment.arguments[0]),
                    right=LoweredParameterRef(fragment.arguments[1]),
                ),
                source=fragment.source,
            ),
        ),
        source=selected.implementation.source,
    )


def _lower_unary_function(
    selected: SelectedImplementation,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: UnaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(selected, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredUnaryOperationExpression(
                    operation=operation,
                    value=LoweredParameterRef(fragment.arguments[0]),
                ),
                source=fragment.source,
            ),
        ),
        source=selected.implementation.source,
    )


def _signature(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor,
    *,
    result_type: LoweredResultType = INPUT_SCALAR_RESULT_TYPE,
) -> LoweredFunctionSignature:
    return LoweredFunctionSignature(
        name=_function_name(selected),
        primitive_name=selected.primitive.name,
        parameters=tuple(
            LoweredParameter(name=name) for name in selected.primitive.parameters
        ),
        scalar_type=scalar_type,
        result_type=result_type,
    )


def _function_name(selected: SelectedImplementation) -> str:
    return (
        f"{selected.primitive.name}_"
        f"{selected.implementation.extension}_"
        f"{selected.implementation.type_tag}"
    )
