"""Reusable primitive-call expression lowering for recognized call tokens."""

from tslgen.analysis.selection import SelectedImplementation
from tslgen.domain.catalog import Catalog, PrimitiveCall
from tslgen.lowering.model import (
    LoweredPrimitiveCallExpression,
    PrimitiveCallExpressionLoweringResult,
    SelectedTypeEnvironment,
    build_selected_implementation_lowering_context,
)
from tslgen.lowering.primitive_call_arguments import (
    lower_primitive_call_argument_bindings,
)
from tslgen.lowering.primitive_call_targets import lower_primitive_call_target_match
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.lowering.type_queries import build_selected_type_environment


def lower_primitive_call_expression(
    selected: SelectedImplementation,
    catalog: Catalog,
    primitive_call: PrimitiveCall,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> PrimitiveCallExpressionLoweringResult:
    """Lower one already recognized primitive call into a reusable expression."""

    context = build_selected_implementation_lowering_context(selected)
    selected_environment = (
        environment
        if environment is not None
        else build_selected_type_environment(context)
    )
    selector_result = lower_primitive_call_selector_payload(
        context,
        catalog,
        primitive_call,
        selected_environment,
    )
    if selector_result.payload is None:
        return PrimitiveCallExpressionLoweringResult(
            expression=None,
            diagnostics=selector_result.diagnostics,
        )

    match_result = lower_primitive_call_target_match(
        context,
        catalog,
        selector_result.payload,
    )
    if match_result.match is None:
        return PrimitiveCallExpressionLoweringResult(
            expression=None,
            diagnostics=match_result.diagnostics,
        )

    binding_result = lower_primitive_call_argument_bindings(
        primitive_call,
        match_result.match,
    )
    if binding_result.reference is None:
        return PrimitiveCallExpressionLoweringResult(
            expression=None,
            diagnostics=binding_result.diagnostics,
        )

    return PrimitiveCallExpressionLoweringResult(
        expression=LoweredPrimitiveCallExpression(binding_result.reference),
        diagnostics=(),
    )
