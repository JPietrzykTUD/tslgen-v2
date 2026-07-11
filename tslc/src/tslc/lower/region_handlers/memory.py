"""Memory TSIL region lowerer."""

from __future__ import annotations

from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, render_text, trimmed_text


class MemLowerer:
    """``mem<copy>(dst, src, count) / mem<set>(ptr, value, count) / mem<alloc>(count) /
    mem<alloc_aligned>(align, count) / mem<free>(ptr)`` -> a raw memory operation, lowered
    through a backend translate template keyed by ``mem_<op>`` (C++ ``std::memcpy`` etc.;
    Rust ``crate::tsl_core::mem_copy`` etc.). Like the intrinsics, raw pointer access is
    ``unsafe`` in Rust, so the body is marked unsafe (a no-op for C++)."""

    keyword = "mem"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        context.effects.mark_internal_unsafe("raw_memory")
        op = region.selector_text.strip()
        args: list[RenderText] = []
        for group in split_arg_groups(region.body):
            rendered = render(group)
            if render_text(rendered).strip():
                args.append(trimmed_text(rendered))
        if op == "copy" and len(args) == 3:
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
