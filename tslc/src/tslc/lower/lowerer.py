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
from tslc.catalog.model import BOOLEAN_WILDCARD_ATTRIBUTES, Catalog
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
    # Boolean-wildcard attribute axis (name, concrete value), e.g. (("aligned","false"),).
    # Each becomes a `bool` template parameter (C++) / const generic (Rust) so the
    # `[aligned=*]`-expanded variants coexist as distinct callables.
    axis: tuple[tuple[str, str], ...] = ()
    # True when register_type == base_type for this extension (scalar/generic). Lets the
    # backend dedup overload `apply`s that collapse to the same type (a `v` and an `s`
    # parameter are distinct on SIMD but identical here).
    register_is_base: bool = False


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
            attributes=dict(selected.primitive.attributes),
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
            # A not-yet-supported signature kind (e.g. s[], ptr) is a coverage gap,
            # not a failure — skip the specialization (info), don't fail generation.
            return _skip(
                "TSL-LOWER-UNSUPPORTED-KIND",
                f"signature {selected.primitive.signature!r} uses an unsupported kind "
                f"(supported: {', '.join(sorted(_SUPPORTED_KINDS))})",
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

        # Dereferencing a raw pointer is `unsafe` in Rust, so a `ptr`-taking body needs
        # the unsafe frame even when it uses no intrinsics (e.g. scalar `*ptr = data;`).
        if "ptr" in shape.param_kinds:
            context.mark_unsafe()

        segments = scan(selected.implementation.body_text)
        # A `void` primitive (e.g. `store`) has no return value, so it carries no
        # top-level `emit_return`; only value-returning bodies require one.
        if shape.result_kind != "void" and _find_region(segments, _RETURN_KEYWORD) is None:
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
            # Emit the ISA name (avx2), not the internal block name (avx2_vl):
            # the `_vl` distinction only steers selection, never the generated type.
            extension_name=context.extension.isa_name,
            type_tag=context.type_tag,
            base_type_spelling=base_type_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body_text=body_text,
            axis=tuple(
                (key, selected.primitive.attributes[key])
                for key in sorted(selected.primitive.attributes)
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            ),
            register_is_base=context.extension.vector_bits == 0,
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(context.diagnostics),
        )


_SUPPORTED_KINDS = frozenset({"v", "s", "m", "ptr", "void"})


def _find_region(segments: tuple[Segment, ...], keyword: str) -> Region | None:
    """Find a region by keyword, descending into ``if`` branch blocks so an
    ``emit_return`` guarded by ``if<generation>`` still counts as present."""

    for segment in segments:
        if isinstance(segment, Region):
            if segment.keyword == keyword:
                return segment
            if segment.keyword == "if":
                nested = _find_region(segment.block, keyword)
                if nested is None and segment.else_block is not None:
                    nested = _find_region(segment.else_block, keyword)
                if nested is not None:
                    return nested
    return None


def _error(code: str, message: str) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(Diagnostic(severity="error", code=code, message=message),),
    )


def _skip(code: str, message: str) -> LoweringResult:
    """A not-yet-lowerable specialization: recorded as a coverage gap, not a failure."""

    return LoweringResult(
        specialization=None,
        diagnostics=(Diagnostic(severity="info", code=code, message=message),),
    )
