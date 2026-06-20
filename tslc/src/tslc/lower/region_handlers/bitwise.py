"""Bitwise TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField


class BitNegateLowerer:
    """``bit_negate(expr)`` -> backend bitwise-not expression.

    The source keyword carries the semantic operation. Backend syntax owns the
    target spelling (`~` in C++, `!` in Rust).
    """

    keyword = "bit_negate"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        if region.selector_text.strip():
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-BIT-NEGATE",
                f"unsupported bit_negate selector: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.syntax.render_bit_negate(render(region.body))
