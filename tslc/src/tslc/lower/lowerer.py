"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringContext` (in ``context.py``) holds the selected extension/type,
  the backend translation, the diagnostics sink, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`Lowerer` is the orchestrator: resolve the signature types, locate the
  return statement, render its expression, and assemble :class:`LoweredFunction`.

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.context import LoweringContext
from tslc.lower.regions import DEFAULT_REGION_LOWERERS, RegionLowerer
from tslc.select.selector import SelectedImplementation

# The single supported statement keyword for the current slice (v:=(v,v) bodies).
_RETURN_KEYWORD = "emit_return"


@dataclass(frozen=True, slots=True)
class LoweredParameter:
    name: str
    type_spelling: str


@dataclass(frozen=True, slots=True)
class LoweredFunction:
    backend_id: str
    name: str
    parameters: tuple[LoweredParameter, ...]
    result_type: str
    body_text: str  # the fully framed body statement(s), e.g. "return left + right;"


@dataclass(frozen=True, slots=True)
class LoweringResult:
    function: LoweredFunction | None
    diagnostics: tuple[Diagnostic, ...]


class ExpressionRenderer:
    """Render a TSIL expression (segment sequence) to target text."""

    def __init__(
        self,
        context: LoweringContext,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
    ) -> None:
        self._context = context
        self._lowerers = {lowerer.keyword: lowerer for lowerer in region_lowerers}

    def render(self, segments: tuple[Segment, ...]) -> str:
        parts = [self._render_segment(segment) for segment in segments]
        return "".join(parts).strip()

    def _render_segment(self, segment: Segment) -> str:
        if isinstance(segment, RawText):
            return segment.text
        lowerer = self._lowerers.get(segment.keyword)
        if lowerer is None:
            self._context.error(
                "TSL-LOWER-UNSUPPORTED-REGION",
                f"region {segment.keyword!r} is not supported in this slice: "
                f"{segment.full_text!r}",
            )
            return segment.full_text
        return lowerer.lower(segment, self._context, self.render)


class Lowerer:
    def __init__(
        self, region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS
    ) -> None:
        self._region_lowerers = region_lowerers

    def lower(
        self,
        selected: SelectedImplementation,
        catalog: Catalog,
        translation: BackendTranslation,
    ) -> LoweringResult:
        context = LoweringContext(
            extension=selected.extension,
            type_tag=selected.target.type_tag,
            translation=translation,
        )

        register_type = translation.register_type(context.extension, context.type_tag)
        if register_type is None:
            return _error(
                "TSL-LOWER-NO-REGISTER-TYPE",
                f"no {translation.backend_id} register type for {context.type_tag!r} "
                f"under extension {context.extension.name!r}",
            )

        segments = scan(selected.implementation.body_text)
        if _find_region(segments, _RETURN_KEYWORD) is None:
            return _error(
                "TSL-LOWER-NO-EMIT-RETURN",
                f"implementation for {selected.primitive.name!r} has no top-level "
                "emit_return(...) (unsupported body shape in this slice)",
            )

        # Render the whole body as a statement stream: emit_return is a registered
        # handler that frames the return, and the source terminator (";") passes
        # through as raw text.
        renderer = ExpressionRenderer(context, self._region_lowerers)
        body_text = renderer.render(segments)
        if context.has_errors:
            return LoweringResult(function=None, diagnostics=tuple(context.diagnostics))

        function = LoweredFunction(
            backend_id=translation.backend_id,
            name=f"{selected.primitive.name}_{context.extension.name}_{context.type_tag}",
            parameters=tuple(
                LoweredParameter(name=name, type_spelling=register_type)
                for name in selected.primitive.parameters
            ),
            result_type=register_type,
            body_text=body_text,
        )
        return LoweringResult(
            function=function,
            diagnostics=sort_diagnostics(context.diagnostics),
        )


def _find_region(segments: tuple[Segment, ...], keyword: str) -> Region | None:
    for segment in segments:
        if isinstance(segment, Region) and segment.keyword == keyword:
            return segment
    return None


def _error(code: str, message: str) -> LoweringResult:
    return LoweringResult(
        function=None,
        diagnostics=(Diagnostic(severity="error", code=code, message=message),),
    )
