"""Backend-divergent operator region lowerer.

``op<NAME>(args...)`` is the one keyword for lane operators whose spelling differs between
backends (arithmetic that must wrap, bit-negate, …). The per-backend spelling lives in the
corpus translate tables keyed ``op_<NAME>`` with positional fields ``{a0}``, ``{a1}``, … — so a
new divergent operator is two corpus lines, not Python plumbing. (Compare ``mask<…>``, which uses
the same template machinery.) A genuinely portable operator stays raw text (e.g. ``&``, ``==``).
"""

from __future__ import annotations

from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, render_text, trimmed_text


class OpLowerer:
    keyword = "op"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        name = region.selector_text.strip()
        args: list[RenderText] = []
        for group in split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))
        key = f"op_{name}"
        if not name or context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-OP",
                f"unsupported op<{name}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        fields = {f"a{index}": arg for index, arg in enumerate(args)}
        return context.env.backend.templates.render_template(key, **fields)
