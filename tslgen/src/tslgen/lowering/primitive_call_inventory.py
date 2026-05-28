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
from tslgen.lowering.primitive_call_arguments import (
    lower_primitive_call_argument_bindings,
)
from tslgen.lowering.primitive_call_targets import lower_primitive_call_target_match
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
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
        selector_result = lower_primitive_call_selector_payload(
            context,
            catalog,
            primitive_call,
            environment,
        )
        if selector_result.payload is None:
            diagnostics.extend(selector_result.diagnostics)
            continue

        match_result = lower_primitive_call_target_match(
            context,
            catalog,
            selector_result.payload,
        )
        if match_result.match is None:
            diagnostics.extend(match_result.diagnostics)
            continue

        binding_result = lower_primitive_call_argument_bindings(
            primitive_call,
            match_result.match,
        )
        if binding_result.reference is None:
            diagnostics.extend(binding_result.diagnostics)
            continue

        references.append(binding_result.reference)

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
