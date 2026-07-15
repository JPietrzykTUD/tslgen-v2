"""Query TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.queries import QueryEvaluator
from tslc.lower.region_handlers.common import _type_value_spelling
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField


class QueryRegionLowerer:
    """``type(x)`` / ``value(x)`` in raw expression position -> the evaluated
    query's rendered text. A type resolves to its backend spelling; a text/integer
    value to its literal. This is how generated constants are spliced into a
    body, e.g. ``array_type<type(base::in), value(vector::length)>``.
    One instance is registered per keyword (``type``/``value``)."""

    def __init__(self, keyword: str, evaluator: QueryEvaluator | None = None) -> None:
        self.keyword = keyword
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        del render
        value = self._evaluator.evaluate(region.full_text, context)
        if value is not None:
            spelling = _type_value_spelling(value, context)
            if spelling is not None:
                return spelling
        context.effects.skip(
            (
                "TSL-LOWER-UNRESOLVED-TYPE-QUERY"
                if region.keyword == "type"
                else "TSL-LOWER-UNRESOLVED-VALUE-QUERY"
            ),
            f"could not resolve {region.keyword}<...> region: {region.full_text!r}",
            source=region.source,
        )
        return region.full_text
