"""Backend protocol: render a lowered function as target-language text."""

from __future__ import annotations

from typing import Protocol

from tslc.lower.lowerer import LoweredFunction


class Backend(Protocol):
    backend_id: str

    def render_function(self, function: LoweredFunction) -> str:
        """Render one lowered function as a complete target-language definition."""
