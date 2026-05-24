"""Selected-implementation lowering for the exact tiny clean binary body."""

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
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
)
from tslgen.lowering.scalar_types import (
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)

_SUPPORTED_TEMPLATE = "binary"
_SUPPORTED_EXTENSION = "scalar"
_SUPPORTED_PARAMETERS = ("left", "right")


@dataclass(frozen=True, slots=True)
class LoweringResult:
    function: LoweredFunction | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweringStageResult:
    lowered_functions: LoweredFunctionSet
    diagnostics: tuple[Diagnostic, ...]


class Lowerer:
    """Lower only the selected scalar binary implementation shape."""

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
        operation = lookup_binary_operation_descriptor(selected.primitive.name)
        diagnostics = tuple(_unsupported_diagnostics(selected, scalar_type, operation))
        if diagnostics or scalar_type is None or operation is None:
            return LoweringResult(function=None, diagnostics=diagnostics)

        body = selected.implementation.body
        function = LoweredFunction(
            signature=LoweredFunctionSignature(
                name=_function_name(selected),
                primitive_name=selected.primitive.name,
                parameters=tuple(
                    LoweredParameter(name=name) for name in selected.primitive.parameters
                ),
                scalar_type=scalar_type,
            ),
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
        return LoweringResult(function=function, diagnostics=())


def _unsupported_diagnostics(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor | None,
    operation: BinaryOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    body = selected.implementation.body

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

    if selected.primitive.template != _SUPPORTED_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_PARAMETERS!r}"
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
        body.left_parameter != _SUPPORTED_PARAMETERS[0]
        or body.right_parameter != _SUPPORTED_PARAMETERS[1]
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


def _function_name(selected: SelectedImplementation) -> str:
    return (
        f"{selected.primitive.name}_"
        f"{selected.implementation.extension}_"
        f"{selected.implementation.type_tag}"
    )
