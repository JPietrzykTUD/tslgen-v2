"""Memory TSIL region lowerer."""

from __future__ import annotations

from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_safety import direct_region_safety
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, render_text, trimmed_text


class MemLowerer:
    """Lower typed scalar and raw byte-memory operations through backend templates.

    Like intrinsics, direct pointer access is unsafe in Rust, so every operation
    contributes the compiler-owned raw-memory safety fact.
    """

    keyword = "mem"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        context.effects.merge_safety(direct_region_safety(region))
        op = region.selector_text.strip()
        args: list[RenderText] = []
        for group in split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))
        if op == "load_scalar" and len(args) == 1:
            key, fields = "mem_load_scalar", {"ptr": args[0]}
        elif op == "store_scalar" and len(args) == 2:
            key, fields = "mem_store_scalar", {"ptr": args[0], "value": args[1]}
        elif op == "copy" and len(args) == 3:
            key, fields = "mem_copy", {"dst": args[0], "src": args[1], "count": args[2]}
        elif op == "set" and len(args) == 3:
            key, fields = "mem_set", {"ptr": args[0], "value": args[1], "count": args[2]}
        elif op == "alloc" and len(args) == 1:
            key, fields = "mem_alloc", {"count": args[0]}
        elif op == "alloc_aligned" and len(args) == 2:
            # The corpus body passes (count_bytes, alignment); the template orders them per
            # backend (C++ `aligned_alloc(align, count)`).
            key, fields = "mem_alloc_aligned", {"count": args[0], "align": args[1]}
        elif op == "free" and len(args) == 1:
            key, fields = "mem_free", {"ptr": args[0]}
        else:
            key, fields = "", {}
        if not key or context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-MEM",
                f"unsupported mem<{region.selector_text.strip()}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.templates.render_template(key, **fields)
