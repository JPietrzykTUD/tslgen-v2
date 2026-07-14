"""Array-element TSIL region lowerer."""

from __future__ import annotations

from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, render_text, trimmed_text


class ArrayLowerer:
    """``array<set>(array, index, value)`` -> backend-owned element assignment."""

    keyword = "array"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        args: list[RenderText] = []
        for group in split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))

        key = (
            "array_set"
            if region.selector_text.strip() == "set" and len(args) == 3
            else ""
        )
        if not key or context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-ARRAY",
                f"unsupported array<{region.selector_text.strip()}>: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.templates.render_template(
            key, array=args[0], index=args[1], value=args[2]
        )
