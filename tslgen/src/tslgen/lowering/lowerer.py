"""Selected-implementation lowering for the exact M107 add body."""

from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.lowering.model import (
    LoweredBinaryAddExpression,
    LoweredFunction,
    LoweredParameter,
    LoweredParameterRef,
)

_SUPPORTED_PRIMITIVE = "add"
_SUPPORTED_TEMPLATE = "binary"
_SUPPORTED_EXTENSION = "scalar"
_SUPPORTED_TYPE_TAG = "si32"
_SUPPORTED_PARAMETERS = ("left", "right")


@dataclass(frozen=True, slots=True)
class LoweringResult:
    function: LoweredFunction | None
    diagnostics: tuple[Diagnostic, ...]


class Lowerer:
    """Lower only the selected M107 scalar si32 add implementation."""

    def lower(self, selected: SelectedImplementation) -> LoweringResult:
        diagnostics = tuple(_unsupported_diagnostics(selected))
        if diagnostics:
            return LoweringResult(function=None, diagnostics=diagnostics)

        body = selected.implementation.body
        function = LoweredFunction(
            name=_function_name(selected),
            primitive_name=selected.primitive.name,
            parameters=tuple(
                LoweredParameter(name=name) for name in selected.primitive.parameters
            ),
            scalar_type_tag=selected.implementation.type_tag,
            expression=LoweredBinaryAddExpression(
                left=LoweredParameterRef(body.left_parameter),
                right=LoweredParameterRef(body.right_parameter),
            ),
            source=selected.implementation.source,
        )
        return LoweringResult(function=function, diagnostics=())


def _unsupported_diagnostics(
    selected: SelectedImplementation,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    body = selected.implementation.body

    if selected.primitive.name != _SUPPORTED_PRIMITIVE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PRIMITIVE",
                message=(
                    f"primitive {selected.primitive.name!r} cannot be lowered by "
                    f"M108; expected {_SUPPORTED_PRIMITIVE!r}"
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
                    f"M108; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if selected.implementation.type_tag != _SUPPORTED_TYPE_TAG:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    f"cannot be lowered by M108; expected "
                    f"{_SUPPORTED_TYPE_TAG!r}"
                ),
                location=selected.implementation.source,
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
                    "implementation body cannot be lowered by M108; expected "
                    "exactly 'add(left, right)'"
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
