"""Return TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField

class CompleteLowerer:
    """``complete(expr)`` -> the backend's return framing around the value.

    Backend-neutral: the target return spelling comes from the backend's
    ``complete`` translate template. Any required ``unsafe`` framing is carried
    by the typed lowered body, not inferred by backend renderers.
    """

    keyword = "complete"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        return context.env.backend.syntax.frame_return(render(region.body))
