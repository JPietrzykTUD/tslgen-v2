"""PIVOT call capture layered over the standard TSIL lowering configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.diagnostics import SourceSpan
from tslc.ir.region_syntax import parse_call_selector, parse_var_selector, split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    resolve_lowered_call_dependency,
)
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue
from tslc.lower.region_handlers import DEFAULT_REGION_LOWERERS, RegionLowerer
from tslc.lower.region_handlers.declarations import VarLowerer
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, RenderText, literal_text, render_sequence, render_text

@dataclass(frozen=True, slots=True)
class PivotCallSite:
    marker_id: int
    dependency: CallDependency
    attrs: tuple[tuple[str, str], ...]
    source: SourceSpan | None

    @property
    def marker(self) -> str:
        return f"__tslc_pivot_call_{self.marker_id}"


@dataclass(slots=True)
class PivotCallCapture:
    sites: list[PivotCallSite] = field(default_factory=list)

    def add(
        self,
        dependency: CallDependency,
        attrs: tuple[tuple[str, str], ...],
        source: SourceSpan | None,
    ) -> PivotCallSite:
        site = PivotCallSite(len(self.sites), dependency, attrs, source)
        self.sites.append(site)
        return site


class PivotCallLowerer:
    """Capture a typed call edge while leaving a private marker in target text."""

    keyword = "call"

    def __init__(
        self,
        capture: PivotCallCapture,
        evaluator: QueryEvaluator | None = None,
    ) -> None:
        self._capture = capture
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        parsed = parse_call_selector(region.selector_text)
        if parsed is None:
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-CALL",
                f"PIVOT cannot resolve call selector {region.selector_text!r}",
                source=region.source,
            )
            return region.full_text
        if len(parsed.type_args) > 1:
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-CALL-TYPEARGS",
                "PIVOT call inlining does not support forwarded immediate or generic "
                f"arguments: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        attrs = tuple(
            (key, self._resolve_attr(value, context)) for key, value in parsed.attrs
        )
        dependency = resolve_lowered_call_dependency(
            parsed,
            context,
            self._evaluator,
            mask_policy=dict(attrs).get("mask"),
        )
        context.effects.record_call_dependency(
            CallDependencyOrigin(dependency, context.env.dependency_origin)
        )
        arguments = render(region.body)
        site = self._capture.add(dependency, attrs, region.source)
        return render_sequence(
            (literal_text(f"{site.marker}("), arguments, literal_text(")"))
        )

    def _resolve_attr(self, value: str, context: LoweringSession) -> str:
        if "<" not in value and "::" not in value:
            return value
        resolved = self._evaluator.evaluate(value, context)
        if isinstance(resolved, TextValue):
            return resolved.as_text()
        if isinstance(resolved, BoolValue):
            return "true" if resolved.value else "false"
        return value


class PivotVarLowerer:
    """Admit only inferred locals, which remain plain dataflow assignments."""

    keyword = "var"

    def __init__(self) -> None:
        self._delegate = VarLowerer()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        groups = split_arg_groups(region.body)
        selector = parse_var_selector(region.selector_text, len(groups))
        if selector is None or selector.kind != "inferred":
            context.effects.skip(
                "TSL-PIVOT-UNSUPPORTED-VAR",
                "PIVOT supports only var<infer> and var<const_infer> locals: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return self._delegate.lower(region, context, render)

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        return self._delegate.finish_statement(rendered, region)


def pivot_region_lowerers(capture: PivotCallCapture) -> tuple[RegionLowerer, ...]:
    """Reuse normal TSIL semantics, replacing only handlers PIVOT must constrain.

    In particular, the normal control lowerers get the opportunity to splice
    generation-time branches and expand generation-time loops. The planner
    validates their final target text and rejects control flow that survives.
    Calls remain a PIVOT override because their typed call-site identity must be
    retained for recursive inlining. Variables remain limited to inferred locals
    so the inliner can alpha-rename every admitted declaration without parsing C++.
    """

    lowerers: list[RegionLowerer] = []
    for lowerer in DEFAULT_REGION_LOWERERS:
        if lowerer.keyword == "call":
            lowerers.append(PivotCallLowerer(capture))
        elif lowerer.keyword == "var":
            lowerers.append(PivotVarLowerer())
        else:
            lowerers.append(lowerer)
    return tuple(lowerers)


__all__ = (
    "PivotCallCapture",
    "PivotCallSite",
    "pivot_region_lowerers",
)
