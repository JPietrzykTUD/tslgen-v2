"""Direct safety effects derived from typed TSIL regions."""

from __future__ import annotations

from tslc.catalog.model import ImplementationSafety
from tslc.ir.region_syntax import (
    parse_cast_selector,
    parse_var_selector,
    split_arg_groups,
)
from tslc.ir.segments import Region, Segment


def direct_region_safety(region: Region) -> ImplementationSafety:
    """Return the context-free unsafe operations represented by one region."""

    reason: str | None = None
    if region.keyword == "intrin":
        reason = "intrinsic"
    elif region.keyword == "mem":
        reason = "raw_memory"
    elif region.keyword == "var":
        var_selector = parse_var_selector(
            region.selector_text,
            len(split_arg_groups(region.body)),
        )
        if var_selector is not None and var_selector.kind == "runtime_array":
            reason = "raw_memory"
    elif region.keyword == "cast":
        cast_selector = parse_cast_selector(region.selector_text)
        if (
            cast_selector.is_valid
            and cast_selector.variant == "reinterpret"
            and cast_selector.type_kind == "value"
        ):
            reason = "value_reinterpretation"
    if reason is None:
        return ImplementationSafety()
    return ImplementationSafety(
        internal_unsafe=True,
        reasons=frozenset({reason}),
    )


def direct_implementation_safety(
    segments: tuple[Segment, ...],
) -> ImplementationSafety:
    """Collect direct safety effects from a recursive typed segment sequence."""

    safety = ImplementationSafety()
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        safety = safety.merge(direct_region_safety(segment))
        for children in segment.child_sequences():
            safety = safety.merge(direct_implementation_safety(children))
    return safety


__all__ = ("direct_implementation_safety", "direct_region_safety")
