"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringContext` (in ``context.py``) holds the selected extension/type,
  the backend translation, the diagnostics sink, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`Lowerer` is the orchestrator: read the signature kinds, locate the
  return statement, render the body, and assemble a :class:`LoweredSpecialization`
  (a not-yet-lowerable construct skips the specialization rather than failing).

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.context import LoweringContext
from tslc.lower.regions import DEFAULT_REGION_LOWERERS, RegionLowerer
from tslc.select.selector import SelectedImplementation

# The single supported statement keyword for the current slice (v:=(v,v) bodies).
_RETURN_KEYWORD = "emit_return"


@dataclass(frozen=True, slots=True)
class LoweredSpecialization:
    """One `<primitive, extension, type>` body, ready for the backend to wrap in a
    template specialization (C++) / trait impl (Rust). Signature types are *not*
    concrete here — the backend expresses them via the ``simd<>`` member types
    (`Vec::register_type` / `Vec::base_type`); only the body is concrete."""

    backend_id: str
    primitive_name: str
    extension_name: str  # the simd<> extension tag, e.g. "avx2"
    type_tag: str
    base_type_spelling: str  # the simd<> base-type arg, e.g. "int32_t" / "i32"
    result_kind: str  # "v" | "s"
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    body_text: str  # fully framed body, e.g. "return _mm256_add_epi32(left, right);"


@dataclass(frozen=True, slots=True)
class LoweringResult:
    specialization: LoweredSpecialization | None
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
            self._context.skip(
                "TSL-LOWER-UNSUPPORTED-REGION",
                f"region {segment.keyword!r} is not supported yet: {segment.full_text!r}",
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
            type_tag=selected.type_tag,
            translation=translation,
        )

        shape = parse_signature(selected.primitive.signature)
        if shape is None:
            return _error(
                "TSL-LOWER-BAD-SIGNATURE",
                f"could not parse signature {selected.primitive.signature!r}",
            )
        if shape.result_kind not in _SUPPORTED_KINDS or any(
            kind not in _SUPPORTED_KINDS for kind in shape.param_kinds
        ):
            return _error(
                "TSL-LOWER-UNSUPPORTED-KIND",
                f"signature {selected.primitive.signature!r} uses a kind beyond "
                "the supported {v, s} set",
            )
        parameters = selected.primitive.parameters
        if len(parameters) != len(shape.param_kinds):
            return _error(
                "TSL-LOWER-SIGNATURE-ARITY",
                f"primitive {selected.primitive.name!r} has {len(parameters)} parameters "
                f"but signature {selected.primitive.signature!r} has {len(shape.param_kinds)}",
            )

        base_type_spelling = translation.scalar_spelling(context.type_tag)
        if base_type_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {translation.backend_id} base-type spelling for {context.type_tag!r}",
            )

        segments = scan(selected.implementation.body_text)
        if _find_region(segments, _RETURN_KEYWORD) is None:
            # No top-level return statement to model yet — skip, don't fail.
            return LoweringResult(
                specialization=None,
                diagnostics=(
                    Diagnostic(
                        severity="info",
                        code="TSL-LOWER-NO-EMIT-RETURN",
                        message=(
                            f"implementation for {selected.primitive.name!r} has no top-level "
                            "emit_return(...); skipped"
                        ),
                    ),
                ),
            )

        # Render the whole body as a statement stream: var/emit_return are registered
        # handlers, and raw text (assignment LHS, newlines, ";") passes through.
        renderer = ExpressionRenderer(context, self._region_lowerers)
        rendered = renderer.render(segments)
        if context.unsupported or context.has_errors:
            # A not-yet-lowerable construct was hit: skip this specialization.
            return LoweringResult(specialization=None, diagnostics=tuple(context.diagnostics))
        body_text = translation.frame_body(rendered, requires_unsafe=context.requires_unsafe)

        specialization = LoweredSpecialization(
            backend_id=translation.backend_id,
            primitive_name=selected.primitive.name,
            extension_name=context.extension.name,
            type_tag=context.type_tag,
            base_type_spelling=base_type_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body_text=body_text,
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(context.diagnostics),
        )


_SUPPORTED_KINDS = frozenset({"v", "s"})


def _find_region(segments: tuple[Segment, ...], keyword: str) -> Region | None:
    for segment in segments:
        if isinstance(segment, Region) and segment.keyword == keyword:
            return segment
    return None


def _error(code: str, message: str) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(Diagnostic(severity="error", code=code, message=message),),
    )
