"""Classify lowered implementation bodies by how directly they use target support."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from tslc.catalog.signatures import parse_signature
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.implementation_facts import (
    ImplementationState,
    ImplementationStateFacts,
    RegionImplementationEffect,
    combine_implementation_states,
)
from tslc.lower.region_handlers.registry import (
    IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS,
    region_implementation_effect,
)

if TYPE_CHECKING:
    from tslc.select.selector import SelectedImplementation


class _ImplementationStateRecorder(Protocol):
    def mark_direct(self) -> None: ...
    def mark_intrinsic(self) -> None: ...
    def mark_call(self) -> None: ...
    def mark_composition(self) -> None: ...
    def mark_fallback(self) -> None: ...
    def mark_unknown(self) -> None: ...


_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def infer_direct_implementation_state(
    selected: "SelectedImplementation",
    segments: tuple[Segment, ...],
) -> ImplementationState:
    """Infer the direct state of one source body before call-graph propagation."""

    if selected.extension_family_capability.implementation_fallback:
        return ImplementationState.FALLBACK

    facts = ImplementationStateFacts()
    _visit_regions(facts, segments, selected)
    return facts.implementation_state(selected)


def record_rendered_region_state(
    recorder: _ImplementationStateRecorder,
    region: Region,
    selected: "SelectedImplementation",
) -> None:
    """Record one region that survived generation-time branch lowering."""

    _record_region(recorder, region, selected, rendered=True)


def _visit_regions(
    facts: ImplementationStateFacts,
    segments: tuple[Segment, ...] | None,
    selected: "SelectedImplementation",
) -> None:
    if segments is None:
        return
    for segment in segments:
        if isinstance(segment, RawText):
            continue
        _record_region(facts, segment, selected, rendered=False)
        _visit_regions(facts, segment.body, selected)
        _visit_regions(facts, segment.block, selected)
        _visit_regions(facts, segment.else_block, selected)
        if segment.arms is not None:
            for _label, arm in segment.arms:
                _visit_regions(facts, arm, selected)


def _record_region(
    recorder: _ImplementationStateRecorder,
    region: Region,
    selected: "SelectedImplementation",
    *,
    rendered: bool,
) -> None:
    effect = region_implementation_effect(region.keyword)
    if effect is None:
        recorder.mark_unknown()
    elif effect is RegionImplementationEffect.DIRECT_RETURN:
        if direct_return_is_native(region, selected):
            recorder.mark_direct()
    elif effect is RegionImplementationEffect.INTRINSIC:
        recorder.mark_intrinsic()
    elif effect is RegionImplementationEffect.CALL:
        recorder.mark_call()
    elif effect is RegionImplementationEffect.LOOP:
        selector = region.selector_text.split(",", 1)[0].strip()
        if selector == "backend":
            recorder.mark_fallback()
        elif not rendered or selector != "generation":
            recorder.mark_composition()
    elif effect is RegionImplementationEffect.COMPOSITION:
        recorder.mark_composition()
    elif effect is RegionImplementationEffect.CONTROL:
        if not rendered:
            recorder.mark_composition()
    elif effect is not RegionImplementationEffect.NEUTRAL:
        raise AssertionError(f"unhandled implementation-state effect: {effect}")


def direct_return_is_native(
    region: Region, selected: "SelectedImplementation"
) -> bool:
    """Whether ``complete(symbol)`` returns an already-compatible representation.

    This is intentionally tied to typed source facts: the expression must be a
    bare primitive parameter, and the parameter/result representation must be
    compatible for the selected extension. Opaque target expressions remain
    unknown.
    """

    if region.keyword != "complete":
        return False
    symbol = _bare_return_symbol(region)
    if symbol is None:
        return False
    shape = parse_signature(selected.primitive.signature)
    if shape is None:
        return False
    try:
        param_index = selected.primitive.parameters.index(symbol)
    except ValueError:
        return False
    if param_index >= len(shape.param_terms):
        return False
    param_kind = shape.param_terms[param_index].kind
    return _representations_match(shape.result_kind, param_kind, selected)


def _bare_return_symbol(region: Region) -> str | None:
    if len(region.body) != 1 or not isinstance(region.body[0], RawText):
        return None
    text = region.body[0].text.strip()
    if not _IDENTIFIER.fullmatch(text):
        return None
    return text


def _representations_match(
    result_kind: str,
    param_kind: str,
    selected: "SelectedImplementation",
) -> bool:
    if result_kind == param_kind:
        return True
    extension = selected.extension
    if result_kind == "v" and param_kind == "m":
        return extension.mask_policy.kind == "lane_bitmask"
    if {result_kind, param_kind} == {"m", "im"}:
        return extension.imask_policy.kind == "same_as_mask_type"
    return False
