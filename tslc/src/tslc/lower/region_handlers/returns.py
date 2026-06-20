"""Return TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody

class EmitReturnLowerer:
    """``emit_return(expr)`` -> the backend's return framing around the value.

    Backend-neutral: the ``return`` spelling comes from the backend's
    ``emit_return`` translate template. Any required ``unsafe`` framing is carried
    by the typed lowered body, not inferred by backend renderers.
    """

    keyword = "emit_return"

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        return context.env.backend.syntax.frame_return(render(region.body))
