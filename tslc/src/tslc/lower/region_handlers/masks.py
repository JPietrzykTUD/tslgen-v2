"""Mask TSIL region lowerers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower._text import split_selector_terms
from tslc.lower.region_handlers.common import _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField, RenderText, render_text, trimmed_text

MaskSelectorKind = Literal[
    "lane_true",
    "lane_false",
    "zero",
    "all",
    "test",
    "test_imask",
    "set",
    "clear",
    "set_to",
]


@dataclass(frozen=True, slots=True)
class MaskSelector:
    kind: MaskSelectorKind
    op: str


def parse_mask_selector(selector_text: str, arity: int) -> MaskSelector | None:
    selector_terms = tuple(split_selector_terms(selector_text))
    kind_by_shape: dict[tuple[tuple[str, ...], int], MaskSelectorKind] = {
        (("lane_true",), 0): "lane_true",
        (("lane_false",), 0): "lane_false",
        (("zero",), 0): "zero",
        (("all",), 0): "all",
        (("test",), 2): "test",
        (("test", "imask"), 2): "test_imask",
        (("set",), 2): "set",
        (("clear",), 2): "clear",
        (("set_to",), 3): "set_to",
    }
    kind = kind_by_shape.get((selector_terms, arity))
    if kind is None:
        return None
    return MaskSelector(kind=kind, op=selector_terms[0])


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
        selector = parse_mask_selector(region.selector_text, len(args))
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
