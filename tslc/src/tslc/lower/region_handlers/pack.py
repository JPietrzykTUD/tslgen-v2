"""Variadic-pack TSIL region lowerer."""

from __future__ import annotations

from tslc.backend.translation_common import signed_of
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField


class PackLowerer:
    """``pack<expand>(name) / pack<first>(name)`` -> the variadic scalar pack of a `set`-like
    primitive. ``expand`` produces the lane-count argument list for an intrinsic (C++ ``name...``
    pack expansion; Rust ``name[0], …, name[N-1]`` over the array param). ``first`` produces the
    first element (the scalar/1-lane case). The lane count comes from ``env.variadic_lanes``."""

    keyword = "pack"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        op = region.selector_text.strip()
        lanes = context.env.variadic_lanes
        if lanes is None or op not in ("expand", "first"):
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-PACK",
                f"unsupported pack<{op}> (variadic_lanes={lanes}): {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = render(region.body)
        syntax = context.env.backend.syntax
        if op == "expand":
            # The x86 set intrinsics take signed integers; an integer base's elements are cast to
            # the signed-of-width type (Rust needs this explicitly; C++ ignores it). Float bases
            # pass through (the float intrinsics take the float type).
            type_tag = context.env.type_tag
            cast_to = (
                None
                if type_tag.startswith("f")
                else context.env.backend.types.scalar_spelling(signed_of(type_tag))
            )
            return syntax.render_pack_expand(name, lanes, cast_to)
        return syntax.render_pack_first(name, lanes)
