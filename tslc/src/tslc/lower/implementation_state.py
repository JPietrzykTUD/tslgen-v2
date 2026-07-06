"""Classify lowered implementation bodies by how directly they use target support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from tslc.ir.segments import RawText, Region, Segment

if TYPE_CHECKING:
    from tslc.select.selector import SelectedImplementation


class ImplementationState(Enum):
    """Public implementation-state lattice for a selected specialization."""

    NATIVE = "native"
    COMPOSED = "composed"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


_STATE_RANK = {
    ImplementationState.NATIVE: 0,
    ImplementationState.COMPOSED: 1,
    ImplementationState.UNKNOWN: 2,
    ImplementationState.FALLBACK: 3,
}

_SPECIAL_KEYWORDS = frozenset({"intrin", "call", "loop"})
_NEUTRAL_KEYWORDS = frozenset({"complete", "let", "type", "value"})
_COMPOSITION_KEYWORDS = frozenset(
    {
        "assume_aligned",
        "cast",
        "helper",
        "if",
        "io",
        "lanes",
        "mask",
        "mem",
        "op",
        "switch",
        "var",
    }
)
IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS = (
    _SPECIAL_KEYWORDS | _NEUTRAL_KEYWORDS | _COMPOSITION_KEYWORDS
)


def combine_implementation_states(
    states: tuple[ImplementationState, ...] | list[ImplementationState],
) -> ImplementationState:
    """Join states conservatively: fallback dominates, then unknown, composed, native."""

    if not states:
        return ImplementationState.UNKNOWN
    return max(states, key=lambda state: _STATE_RANK[state])


def infer_direct_implementation_state(
    selected: "SelectedImplementation",
    segments: tuple[Segment, ...],
) -> ImplementationState:
    """Infer the direct state of one source body before call-graph propagation."""

    if selected.extension.family in {"scalar", "generic_like"}:
        return ImplementationState.FALLBACK

    facts = _BodyStateFacts()
    facts.visit(segments)
    if facts.fallback:
        return ImplementationState.FALLBACK
    if facts.unknown:
        return ImplementationState.UNKNOWN
    if facts.intrinsics == 1 and facts.calls == 0 and facts.composition_markers == 0:
        return ImplementationState.NATIVE
    if facts.intrinsics > 0 or facts.calls > 0 or facts.composition_markers > 0:
        return ImplementationState.COMPOSED
    return ImplementationState.UNKNOWN


@dataclass(slots=True)
class _BodyStateFacts:
    intrinsics: int = 0
    calls: int = 0
    composition_markers: int = 0
    fallback: bool = False
    unknown: bool = False

    def visit(self, segments: tuple[Segment, ...] | None) -> None:
        if segments is None:
            return
        for segment in segments:
            if isinstance(segment, RawText):
                continue
            self._visit_region(segment)
            self.visit(segment.body)
            self.visit(segment.block)
            self.visit(segment.else_block)
            if segment.arms is not None:
                for _label, arm in segment.arms:
                    self.visit(arm)

    def _visit_region(self, region: Region) -> None:
        if region.keyword == "intrin":
            self.intrinsics += 1
            return
        if region.keyword == "call":
            self.calls += 1
            return
        if region.keyword == "loop":
            if _loop_is_backend_fallback(region.selector_text):
                self.fallback = True
            else:
                self.composition_markers += 1
            return
        if region.keyword in _COMPOSITION_KEYWORDS:
            self.composition_markers += 1
            return
        if region.keyword in _NEUTRAL_KEYWORDS:
            return
        self.unknown = True


def _loop_is_backend_fallback(selector_text: str) -> bool:
    terms = [term.strip() for term in selector_text.split(",")]
    return bool(terms) and terms[0] == "backend"
