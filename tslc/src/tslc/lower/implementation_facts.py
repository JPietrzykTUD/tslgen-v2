"""Implementation-state values and facts accumulated during lowering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tslc.select.selector import SelectedImplementation


class ImplementationState(Enum):
    """Public implementation-state lattice for a selected specialization."""

    NATIVE = "native"
    COMPOSED = "composed"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class RegionImplementationEffect(Enum):
    """How a registered TSIL region contributes implementation-state facts."""

    DIRECT_RETURN = "direct_return"
    INTRINSIC = "intrinsic"
    CALL = "call"
    LOOP = "loop"
    COMPOSITION = "composition"
    CONTROL = "control"
    NEUTRAL = "neutral"


_STATE_RANK = {
    ImplementationState.NATIVE: 0,
    ImplementationState.COMPOSED: 1,
    ImplementationState.UNKNOWN: 2,
    ImplementationState.FALLBACK: 3,
}


def combine_implementation_states(
    states: tuple[ImplementationState, ...] | list[ImplementationState],
) -> ImplementationState:
    """Join states conservatively: fallback dominates, then unknown, composed, native."""

    if not states:
        return ImplementationState.UNKNOWN
    return max(states, key=lambda state: _STATE_RANK[state])


@dataclass(slots=True)
class ImplementationStateFacts:
    """Facts collected while classifying an implementation body."""

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


__all__ = (
    "ImplementationState",
    "ImplementationStateFacts",
    "RegionImplementationEffect",
    "combine_implementation_states",
)
