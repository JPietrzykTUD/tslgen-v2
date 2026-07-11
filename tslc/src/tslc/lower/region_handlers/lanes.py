"""Lane-list TSIL region lowerer."""

from __future__ import annotations

from tslc.ir.region_syntax import segments_text, split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.generation import evaluate_generation_int_segments
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, literal_text, render_sequence


class LanesLowerer:
    """``lanes<at>(values, N)`` -> one scalar element of a ``lanes<s>`` parameter."""

    keyword = "lanes"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        selector = region.selector_text.strip()
        if selector != "at":
            context.effects.skip(
                "TSL-LOWER-LANES-UNSUPPORTED",
                f"unsupported lanes<{selector}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        groups = split_arg_groups(region.body)
        if len(groups) != 2:
            context.effects.skip(
                "TSL-LOWER-LANES-ARITY",
                f"lanes<at> needs (name, index): {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        name = segments_text(groups[0])
        param = context.env.lane_list_params.get(name)
        if param is None:
            context.effects.skip(
                "TSL-LOWER-LANES-UNKNOWN",
                f"unknown lane-list parameter {name!r}: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        index = evaluate_generation_int_segments(groups[1], context, render)
        if index is None:
            context.effects.skip(
                "TSL-LOWER-LANES-NON-GENERATION-INDEX",
                f"lanes<at> index must be known at generation time: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        if index < 0:
            context.effects.error(
                "TSL-LOWER-LANES-NEGATIVE-INDEX",
                f"lanes<at> index {index} is negative",
                source=region.source,
            )
            return region.full_text
        if param.lane_count is not None and index >= param.lane_count:
            context.effects.error(
                "TSL-LOWER-LANES-INDEX-OUT-OF-RANGE",
                f"lanes<at> index {index} is outside {name!r} lane count "
                f"{param.lane_count}",
                source=region.source,
            )
            return region.full_text

        return render_sequence((literal_text(name), literal_text(f"[{index}]")))
