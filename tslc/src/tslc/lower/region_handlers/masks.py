"""Mask TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.region_syntax import parse_mask_selector, split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, render_text, trimmed_text

class MaskLowerer:
    """``mask<...>`` lane values and mask-container operations.

    ``lane_true`` / ``lane_false`` produce a scalar lane payload value.
    ``zero`` / ``all`` / ``test`` / ``set`` / ``clear`` / ``set_to`` operate on a mask
    container and lower per the selected extension's mask representation.
    ``test, imask`` tests a packed integral mask bitset.
    """

    keyword = "mask"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        extension = context.env.extension
        repr_kind = extension.mask_policy.kind
        # Lane-bitmask policies lower through the same per-lane bit operations. Fixed-width
        # x86 masks are register-backed, so a real vector width gets its own template key.
        if extension.mask_policy.lowers_as_lane_bitmask():
            repr_kind = "lane_bitmask"
        if extension.mask_policy.kind == "lane_bitmask" and extension.vector_bits > 0:
            repr_kind = "lane_register"
        args: list[RenderText] = []
        for group in split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))
        selector = parse_mask_selector(region.selector_text, len(args))
        key: str
        fields: dict[str, RenderField]
        if selector is not None and selector.kind in ("lane_true", "lane_false"):
            key = "mask_lane_all_true" if selector.op == "lane_true" else "mask_lane_all_false"
            base = context.env.backend.types.scalar_spelling(context.env.type_tag)
            fields = {"base": base} if base is not None else {}
            if base is None:
                key = ""
        elif selector is not None and selector.kind in ("zero", "all"):
            key, fields = f"mask_{selector.op}_{repr_kind}", {}
        elif selector is not None and selector.kind == "test_imask":
            key, fields = "mask_test_imask", {"mask": args[0], "index": args[1]}
        elif selector is not None and selector.kind == "test":
            key, fields = f"mask_test_{repr_kind}", {"mask": args[0], "index": args[1]}
        elif selector is not None and selector.kind == "set":
            key, fields = f"mask_set_{repr_kind}", {"name": args[0], "index": args[1]}
        elif selector is not None and selector.kind == "clear":
            key, fields = f"mask_clear_{repr_kind}", {"name": args[0], "index": args[1]}
        elif selector is not None and selector.kind == "set_to":
            key = f"mask_set_to_{repr_kind}"
            fields = {"name": args[0], "index": args[1], "value": args[2]}
        else:
            key, fields = "", {}
        if not key or context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-MASK",
                f"unsupported mask<{region.selector_text.strip()}> for {repr_kind!r}: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.templates.render_template(key, **fields)
