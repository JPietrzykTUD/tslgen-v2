"""Classify lowered implementation bodies by how directly they use target support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import TYPE_CHECKING

from tslc.catalog.signatures import parse_signature
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
        "select_expr",
        "switch",
        "var",
    }
)
IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS = (
    _SPECIAL_KEYWORDS | _NEUTRAL_KEYWORDS | _COMPOSITION_KEYWORDS
)
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


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

    facts = ImplementationStateFacts()
    facts.visit(segments, selected)
    return facts.implementation_state(selected)


@dataclass(slots=True)
class ImplementationStateFacts:
    """Facts collected while rendering the body paths that survive lowering."""

    direct: int = 0
    intrinsics: int = 0
    calls: int = 0
    composition_markers: int = 0
    fallback: bool = False
    unknown: bool = False

    def implementation_state(
        self, selected: "SelectedImplementation"
    ) -> ImplementationState:
        if selected.extension.family in {"scalar", "generic_like"}:
            return ImplementationState.FALLBACK
        if self.fallback:
            return ImplementationState.FALLBACK
        if self.unknown:
            return ImplementationState.UNKNOWN
        if (
            self.calls == 0
            and self.composition_markers == 0
            and (
                (self.intrinsics == 1 and self.direct == 0)
                or (self.intrinsics == 0 and self.direct > 0)
            )
        ):
            return ImplementationState.NATIVE
        if (
            self.direct > 0
            or self.intrinsics > 0
            or self.calls > 0
            or self.composition_markers > 0
        ):
            return ImplementationState.COMPOSED
        return ImplementationState.UNKNOWN

    def mark_direct(self) -> None:
        self.direct += 1

    def mark_intrinsic(self) -> None:
        self.intrinsics += 1

    def mark_call(self) -> None:
        self.calls += 1

    def mark_composition(self) -> None:
        self.composition_markers += 1

    def mark_fallback(self) -> None:
        self.fallback = True

    def mark_unknown(self) -> None:
        self.unknown = True

    def visit(
        self,
        segments: tuple[Segment, ...] | None,
        selected: "SelectedImplementation",
    ) -> None:
        if segments is None:
            return
        for segment in segments:
            if isinstance(segment, RawText):
                continue
            self._visit_region(segment, selected)
            self.visit(segment.body, selected)
            self.visit(segment.block, selected)
            self.visit(segment.else_block, selected)
            if segment.arms is not None:
                for _label, arm in segment.arms:
                    self.visit(arm, selected)

    def _visit_region(
        self, region: Region, selected: "SelectedImplementation"
    ) -> None:
        if region.keyword == "complete" and direct_return_is_native(region, selected):
            self.mark_direct()
            return
        if region.keyword == "intrin":
            self.mark_intrinsic()
            return
        if region.keyword == "call":
            self.mark_call()
            return
        if region.keyword == "loop":
            if _loop_is_backend_fallback(region.selector_text):
                self.mark_fallback()
            else:
                self.mark_composition()
            return
        if region.keyword in _COMPOSITION_KEYWORDS:
            self.mark_composition()
            return
        if region.keyword in _NEUTRAL_KEYWORDS:
            return
        self.mark_unknown()


def _loop_is_backend_fallback(selector_text: str) -> bool:
    terms = [term.strip() for term in selector_text.split(",")]
    return bool(terms) and terms[0] == "backend"


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
