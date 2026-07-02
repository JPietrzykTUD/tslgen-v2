"""Mask TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower._text import split_selector_terms
from tslc.lower.region_handlers.common import _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField, RenderText, render_text, trimmed_text


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
        selector_terms = split_selector_terms(region.selector_text)
        op = selector_terms[0] if selector_terms else ""
        extension = context.env.extension
        repr_kind = extension.mask_policy.kind
        # `lane_bitmask` covers two physical reprs: the generic vector's integer bitset (one bit
        # per lane) and the sse/avx2 register lane-mask (the mask IS a data register, one
        # all-ones/all-zeros lane per element). They test differently, so a register-backed
        # lane mask (a real vector width) gets its own `*_lane_register` key.
        if repr_kind == "lane_bitmask" and extension.vector_bits > 0:
            repr_kind = "lane_register"
        args: list[RenderText] = []
        for group in _split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))
        if selector_terms in (["lane_true"], ["lane_false"]) and not args:
            key = "mask_lane_all_true" if op == "lane_true" else "mask_lane_all_false"
            base = context.env.backend.types.scalar_spelling(context.env.type_tag)
            fields = {"base": base} if base is not None else {}
            if base is None:
                key = ""
        elif selector_terms in (["zero"], ["all"]) and not args:
            key, fields = f"mask_{op}_{repr_kind}", {}
        elif selector_terms == ["test", "imask"] and len(args) == 2:
            key, fields = "mask_test_imask", {"mask": args[0], "index": args[1]}
        elif selector_terms == ["test"] and len(args) == 2:
            key, fields = f"mask_test_{repr_kind}", {"mask": args[0], "index": args[1]}
        elif selector_terms == ["set"] and len(args) == 2:
            key, fields = f"mask_set_{repr_kind}", {"name": args[0], "index": args[1]}
        elif selector_terms == ["clear"] and len(args) == 2:
            key, fields = f"mask_clear_{repr_kind}", {"name": args[0], "index": args[1]}
        elif selector_terms == ["set_to"] and len(args) == 3:
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
