"""Mask TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringContext
from tslc.lower.region_handlers.common import _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody

class MaskLowerer:
    """``mask<zero>() / mask<set:1|0>(m,i) / mask<set>(m,i,v) / mask<test>(m,i)`` -> mask-bit
    ops, lowered per the extension's mask **representation** via a backend translate template
    keyed by `mask_<op>_<repr>` (so literal/`&mut` differences stay in the translate layer).
    Currently the integer-bitset repr (`lane_bitmask`, used by the generic vector's emulated
    masks) is templated; native `__mmask`/register reprs register their own keys later. (Only
    the emulated/generic bodies use `mask<…>` — native bodies use intrinsics — so the bitset
    templates are reached only for the generic vector.)"""

    keyword = "mask"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        op, _, bit = region.selector_text.strip().partition(":")
        repr_kind = context.extension.mask_policy.kind
        args = [render(group).strip() for group in _split_arg_groups(region.body) if render(group).strip()]
        if op == "zero":
            key, fields = f"mask_zero_{repr_kind}", {}
        elif op == "test" and len(args) == 2:
            key, fields = f"mask_test_{repr_kind}", {"mask": args[0], "index": args[1]}
        elif op == "set" and bit == "1" and len(args) == 2:
            key, fields = f"mask_set_{repr_kind}", {"name": args[0], "index": args[1]}
        elif op == "set" and bit == "0" and len(args) == 2:
            key, fields = f"mask_clear_{repr_kind}", {"name": args[0], "index": args[1]}
        elif op == "set" and not bit and len(args) == 3:
            key = f"mask_set_to_{repr_kind}"
            fields = {"name": args[0], "index": args[1], "value": args[2]}
        else:
            key, fields = "", {}
        if not key or context.translation.template(key) is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-MASK",
                f"unsupported mask<{region.selector_text.strip()}> for {repr_kind!r}: "
                f"{region.full_text!r}",
            )
            return region.full_text
        return context.translation.render_template(key, **fields)
