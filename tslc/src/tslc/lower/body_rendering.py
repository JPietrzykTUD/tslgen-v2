"""Render recursive TSIL segment streams into backend-ready text."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import ImplementationSafety
from tslc.catalog.signatures import SignatureShape
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower._diagnostics import (
    implementation_body_source as _implementation_body_source,
)
from tslc.lower.context import (
    LoweringEffects,
    LoweringEnv,
    LoweringScope,
    LoweringSession,
)
from tslc.lower.implementation_state import (
    ImplementationState,
    record_rendered_region_state,
)
from tslc.lower.raw_text import render_raw_text
from tslc.lower.region_safety import direct_region_safety
from tslc.lower.region_handlers import (
    DEFAULT_REGION_LOWERERS,
    RegionLowerer,
    StatementFinalizer,
)
from tslc.target_text import (
    RenderContext,
    RenderSequence,
    RenderText,
    as_render_text,
    literal_text,
    render_sequence,
    trimmed_text,
)
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import SupportPolicy


@dataclass(frozen=True, slots=True)
class RenderedBodyResult:
    rendered: RenderText | None
    safety: ImplementationSafety
    implementation_state: ImplementationState
    diagnostics: tuple[Diagnostic, ...] = ()


def body_context(
    env: LoweringEnv,
    scope: LoweringScope,
    shape: SignatureShape,
    support: SupportPolicy,
) -> LoweringSession:
    context = LoweringSession(
        env=env,
        scope=_clone_scope(scope),
        effects=LoweringEffects(),
    )
    # Dereferencing a raw pointer is `unsafe` in Rust, so a pointer-taking body needs
    # the unsafe frame even when it uses no intrinsics (e.g. scalar `*ptr = data;`).
    # Raw-pointer APIs also require callers to uphold pointer validity.
    if support.requires_unsafe_frame(shape):
        context.effects.mark_caller_unsafe("raw_pointer")
    return context


def render_body(
    *,
    selected: SelectedImplementation,
    shape: SignatureShape,
    context: LoweringSession,
    segments: tuple[Segment, ...],
    region_lowerers: tuple[RegionLowerer, ...],
    variant_name: str | None = None,
    variant_source: SourceSpan | None = None,
) -> RenderedBodyResult:
    if shape.result_kind != "void" and _find_region(segments, "complete") is None:
        if variant_name is not None:
            return RenderedBodyResult(
                rendered=None,
                safety=context.effects.safety,
                implementation_state=context.effects.implementation_state(selected),
                diagnostics=(
                    diagnostic_at(
                        severity="error",
                        code="TSL-LOWER-VARIANT-NO-COMPLETE",
                        message=(
                            f"implementation variant {variant_name!r} for "
                            f"{selected.primitive.name!r} has no top-level "
                            "complete(...)"
                        ),
                        source=variant_source,
                    ),
                ),
            )
        return RenderedBodyResult(
            rendered=None,
            safety=context.effects.safety,
            implementation_state=context.effects.implementation_state(selected),
            diagnostics=(
                diagnostic_at(
                    severity="info",
                    code="TSL-LOWER-NO-COMPLETE",
                    message=(
                        f"implementation for {selected.primitive.name!r} has no "
                        "top-level complete(...); skipped"
                    ),
                    source=_implementation_body_source(selected),
                ),
            ),
        )

    renderer = ExpressionRenderer(context, selected, region_lowerers)
    rendered = renderer.render(segments)
    diagnostics = tuple(context.effects.diagnostics)
    if variant_name is not None:
        diagnostics = _variant_diagnostics(
            diagnostics,
            selected.primitive.name,
            variant_name,
        )
    if context.effects.unsupported or context.effects.has_errors:
        return RenderedBodyResult(
            rendered=None,
            safety=context.effects.safety,
            implementation_state=context.effects.implementation_state(selected),
            diagnostics=diagnostics,
        )
    return RenderedBodyResult(
        rendered=rendered,
        safety=context.effects.safety,
        implementation_state=context.effects.implementation_state(selected),
        diagnostics=diagnostics,
    )


class ExpressionRenderer:
    """Render a TSIL expression or statement stream to target text."""

    def __init__(
        self,
        context: LoweringSession,
        selected: SelectedImplementation,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
    ) -> None:
        self._context = context
        self._selected = selected
        self._lowerers = {lowerer.keyword: lowerer for lowerer in region_lowerers}

    def render(self, segments: tuple[Segment, ...]) -> RenderText:
        parts = [self._render_segment(segment) for segment in segments]
        return trimmed_text(RenderSequence(tuple(parts)))

    def render_text(self, segments: tuple[Segment, ...]) -> str:
        return self.render(segments).render(
            RenderContext(
                unsafe_block_renderer=(
                    self._context.env.backend.syntax.render_unsafe_block
                )
            )
        )

    def _render_segment(self, segment: Segment) -> RenderText:
        if isinstance(segment, RawText):
            return render_raw_text(segment.text)
        lowerer = self._lowerers.get(segment.keyword)
        if lowerer is None:
            self._context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-REGION",
                f"region {segment.keyword!r} is not supported yet: {segment.full_text!r}",
                source=segment.source,
            )
            self._context.effects.mark_unknown()
            return literal_text(segment.full_text)
        self._context.effects.merge_safety(direct_region_safety(segment))
        record_rendered_region_state(
            self._context.effects,
            segment,
            self._selected,
        )
        rendered = as_render_text(lowerer.lower(segment, self._context, self.render))
        return _finish_consumed_statement_terminator(segment, lowerer, rendered)


def _finish_consumed_statement_terminator(
    region: Region,
    lowerer: RegionLowerer,
    rendered: RenderText,
) -> RenderText:
    if not region.has_statement_terminator:
        return rendered
    if region.block or region.else_block is not None or region.arms is not None:
        return rendered
    if isinstance(lowerer, StatementFinalizer):
        return as_render_text(lowerer.finish_statement(rendered, region))
    return render_sequence((rendered, literal_text(";")))


def _clone_scope(scope: LoweringScope) -> LoweringScope:
    return LoweringScope(
        type_aliases=dict(scope.type_aliases),
        target_type_symbols=dict(scope.target_type_symbols),
        type_symbols=dict(scope.type_symbols),
        extension_symbols=dict(scope.extension_symbols),
        vector_aliases=dict(scope.vector_aliases),
        generation_ints=dict(scope.generation_ints),
    )


def _find_region(segments: tuple[Segment, ...] | None, keyword: str) -> Region | None:
    """Find a region by keyword in statement position: top level or any statement block.

    Deliberately does not descend into ``(...)`` payloads — an argument-position
    region is not a statement.
    """

    if segments is None:
        return None
    for segment in segments:
        if isinstance(segment, Region):
            if segment.keyword == keyword:
                return segment
            for block in segment.statement_blocks():
                nested = _find_region(block, keyword)
                if nested is not None:
                    return nested
    return None


def _variant_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    primitive_name: str,
    variant_name: str,
) -> tuple[Diagnostic, ...]:
    return tuple(
        Diagnostic(
            severity=diagnostic.severity,
            code=diagnostic.code,
            message=(
                f"implementation variant {variant_name!r} for "
                f"{primitive_name!r}: {diagnostic.message}"
            ),
            span=diagnostic.span,
        )
        for diagnostic in diagnostics
    )
