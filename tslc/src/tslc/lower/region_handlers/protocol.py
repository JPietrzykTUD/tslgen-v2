"""Protocol shared by TSIL region lowerers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringSession
from tslc.target_text import RenderField, RenderText

RenderBody = Callable[[tuple[Segment, ...]], RenderText]


class RegionLowerer(Protocol):
    keyword: str

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        """Render one region to target text (recursing into its body via ``render``)."""


@runtime_checkable
class StatementFinalizer(Protocol):
    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        """Adjust rendered text after the scanner consumed a source terminator."""
