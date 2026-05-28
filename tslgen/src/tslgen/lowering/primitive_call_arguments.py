"""Raw argument binding for already matched primitive calls."""

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import PrimitiveCall
from tslgen.lowering.model import (
    PrimitiveCallArgumentBinding,
    PrimitiveCallArgumentBindingResult,
    PrimitiveCallReference,
    PrimitiveCallTargetMatch,
    build_selected_implementation_lowering_context,
)


def lower_primitive_call_argument_bindings(
    primitive_call: PrimitiveCall,
    target_match: PrimitiveCallTargetMatch,
) -> PrimitiveCallArgumentBindingResult:
    """Bind raw call arguments positionally to the matched primitive parameters."""

    context = build_selected_implementation_lowering_context(target_match.selected)
    parameter_names = context.parameter_names
    arguments = primitive_call.arguments
    if len(arguments) != len(parameter_names):
        return PrimitiveCallArgumentBindingResult(
            reference=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH",
                    message=(
                        "primitive-call target "
                        f"{context.primitive_name!r} expects "
                        f"{len(parameter_names)} argument(s) for parameters "
                        f"{_format_parameter_names(parameter_names)}; got "
                        f"{len(arguments)} argument(s)"
                    ),
                    location=primitive_call.source,
                ),
            ),
        )

    bindings = tuple(
        PrimitiveCallArgumentBinding(parameter_name=name, argument=argument)
        for name, argument in zip(parameter_names, arguments, strict=True)
    )
    return PrimitiveCallArgumentBindingResult(
        reference=PrimitiveCallReference(
            primitive_call=primitive_call,
            target_match=target_match,
            bindings=bindings,
            source=primitive_call.source,
        ),
        diagnostics=(),
    )


def _format_parameter_names(parameter_names: tuple[str, ...]) -> str:
    if not parameter_names:
        return "<none>"
    return "(" + ", ".join(parameter_names) + ")"
