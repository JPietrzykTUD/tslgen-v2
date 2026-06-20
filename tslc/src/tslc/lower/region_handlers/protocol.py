"""Protocol shared by TSIL region lowerers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringSession
from tslc.render.model import RenderText

RenderBody = Callable[[tuple[Segment, ...]], str]


class RegionLowerer(Protocol):
    keyword: str

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> str | RenderText:
        """Render one region to target text (recursing into its body via ``render``)."""
