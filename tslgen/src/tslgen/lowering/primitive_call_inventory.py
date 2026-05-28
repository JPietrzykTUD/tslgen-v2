"""Source-ordered primitive-call reference inventory for selected bodies."""

from collections.abc import Iterator

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import BodyToken, Catalog, LowerableDirective, PrimitiveCall
from tslgen.lowering.model import (
    PrimitiveCallReference,
    PrimitiveCallReferenceInventory,
    build_selected_implementation_lowering_context,
)
from tslgen.lowering.primitive_call_expression import lower_primitive_call_expression
from tslgen.lowering.type_queries import build_selected_type_environment


def lower_primitive_call_reference_inventory(
    selected: SelectedImplementation,
    catalog: Catalog,
) -> PrimitiveCallReferenceInventory:
    """Compose accepted per-call lowering boundaries over one selected body."""

    context = build_selected_implementation_lowering_context(selected)
    environment = build_selected_type_environment(context)
    references: list[PrimitiveCallReference] = []
    diagnostics: list[Diagnostic] = []

    for primitive_call in _primitive_calls_in_source_order(selected):
        expression_result = lower_primitive_call_expression(
            selected,
            catalog,
            primitive_call,
            environment=environment,
        )
        if expression_result.expression is None:
            diagnostics.extend(expression_result.diagnostics)
            continue

        references.append(expression_result.expression.reference)

    return PrimitiveCallReferenceInventory(
        references=tuple(references),
        diagnostics=tuple(diagnostics),
    )


def _primitive_calls_in_source_order(
    selected: SelectedImplementation,
) -> Iterator[PrimitiveCall]:
    for token in selected.implementation.body.tokens:
        yield from _primitive_calls_from_token(token)


def _primitive_calls_from_token(token: BodyToken) -> Iterator[PrimitiveCall]:
    if not isinstance(token, LowerableDirective):
        return

    if token.primitive_call is not None:
        yield token.primitive_call

    for payload_token in token.payload_tokens:
        yield from _primitive_calls_from_token(payload_token)
