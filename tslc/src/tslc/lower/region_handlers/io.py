"""I/O TSIL region lowerer."""

from __future__ import annotations

from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, trimmed_text


class IoLowerer:
    """``io<format>(buffer, array, modifier)`` -> a text-stream write, lowered through the
    ``io_format`` translate template (C++ ``::tsl::ostream_write(...)`` / Rust
    ``crate::tsl_core::ostream_write(...)``). The runtime helper owns the per-lane base
    formatting, so the source body stays a single call (the modifier is an int selector)."""

    keyword = "io"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        op = region.selector_text.strip()
        args = [trimmed_text(render(group)) for group in split_arg_groups(region.body)]
        if op == "format" and len(args) == 3:
            key = "io_format"
            fields = {"out": args[0], "array": args[1], "modifier": args[2]}
        else:
            key, fields = "", {}
        if not key or context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-IO",
                f"unsupported io<{op}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.templates.render_template(key, **fields)
