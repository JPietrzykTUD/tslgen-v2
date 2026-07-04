"""Declaration and alias TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringSession, VectorValue
from tslc.lower.queries import QueryEvaluator, TypeValue
from tslc.lower.region_handlers.common import _segment_text, _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import (
    RenderField,
    RenderText,
    literal_text,
    render_sequence,
    render_text,
)

class VarLowerer:
    """``var<variant>(...)`` -> the backend's local-declaration template.

    Two shapes: inferred (``var<infer>(name, value)`` / ``var<const_infer>``) fills
    ``var_<variant> = {name}/{value}``; typed (``var<typed>(type, name, value)``)
    additionally carries ``{type}``. An uninitialized array initializer
    (``value(uninit::array)``) routes to the dedicated ``var_array_uninit``
    template instead, which carries ``{type}`` so Rust's MaybeUninit gets it (a value
    region alone cannot supply the array type). The declaration syntax itself is
    backend-neutral, coming from the ``var_*`` translate templates.
    """

    keyword = "var"

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        del region
        return rendered

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        variant = region.selector_text.strip()
        groups = _split_arg_groups(region.body)
        if variant in ("typed", "const_typed"):
            # Both are `(type, name, value)` 3-group forms; `_typed` keys on the variant
            # (`var_typed` / `var_const_typed`), so a const-qualified typed local works too.
            return self._typed(variant, groups, region, context, render)
        if variant == "runtime_array":
            return self._runtime_array(groups, region, context, render)
        if variant in ("init_register", "const_init_register"):
            # A zero-initialized register declaration: `var<init_register>(name)`. The type is
            # the vector's register type (C++ template uses it; the Rust template builds
            # `[BaseType::default(); LANES]` and ignores it).
            key = f"var_{variant}"
            if (
                len(groups) != 1
                or context.env.backend.templates.template(key) is None
            ):
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-VAR",
                    f"unsupported var<{variant}>: {region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
            return context.env.backend.templates.render_template(
                key,
                type=context.env.backend.types.register_type_spelling(),
                name=render_text(render(groups[0])).strip(),
            )
        if len(groups) < 2 or context.env.backend.templates.template(f"var_{variant}") is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<{variant}> declaration: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = render_text(render(groups[0])).strip()
        value = _join_rendered(groups[1:], render)
        return context.env.backend.templates.render_template(
            f"var_{variant}", name=name, value=value
        )

    def _typed(
        self,
        variant: str,
        groups: list[tuple[Segment, ...]],
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> RenderField:
        if len(groups) != 3:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<typed> declaration: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        type_value = render(groups[0])
        name = render_text(render(groups[1])).strip()
        # An uninitialized array uses the type-carrying template (see class docstring).
        key = "var_array_uninit" if "uninit" in _segment_text(groups[2]) else f"var_{variant}"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<typed> declaration: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        if key == "var_array_uninit":
            return context.env.backend.templates.render_template(key, type=type_value, name=name)
        value = render(groups[2])
        return context.env.backend.templates.render_template(
            key, type=type_value, name=name, value=value
        )

    def _runtime_array(
        self,
        groups: list[tuple[Segment, ...]],
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> RenderField:
        if (
            len(groups) != 3
            or context.env.backend.templates.template("var_runtime_array") is None
        ):
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<runtime_array> declaration: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        context.effects.mark_internal_unsafe("raw_memory")
        type_value = render(groups[0])
        name = render_text(render(groups[1])).strip()
        count = render(groups[2])
        return context.env.backend.templates.render_template(
            "var_runtime_array", type=type_value, name=name, count=count
        )


def _join_rendered(groups: list[tuple[Segment, ...]], render: RenderBody) -> RenderText:
    parts: list[RenderField] = []
    for index, group in enumerate(groups):
        if index:
            parts.append(literal_text(", "))
        parts.append(render(group))
    return render_sequence(tuple(parts))


class LetLowerer:
    """``let<type>(Name, type-expr)`` -> a type alias, applied by **substitution**: the
    resolved type spelling is recorded and raw source chunks become literal text plus typed
    alias references during body rendering. A real local alias would be ``using Name = T;`` in
    C++, but Rust rejects a fn-local ``type Name = Self::T;`` (E0401), so inlining is the
    backend-neutral form. The type-expression is resolved via the normal region path (e.g.
    ``type(vector::mask)`` -> the mask-type spelling)."""

    keyword = "let"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        del region
        return rendered

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        variant = region.selector_text.strip()
        groups = _split_arg_groups(region.body)
        if variant != "type" or len(groups) != 2:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-LET",
                f"unsupported let<{variant}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = render_text(render(groups[0])).strip()
        # A vector-valued alias (`let<type>(OutVec, transform_extension(ToBase))`) is captured
        # structurally too, so a later `generic::length(OutVec)` query arg resolves to the vector
        # (the rendered spelling below still drives type-position substitution like `to_array[OutVec]`).
        value = self._evaluator.evaluate(_segment_text(groups[1]), context)
        type_tag: str | None = None
        vector: VectorValue | None = None
        if isinstance(value, VectorValue):
            vector = value
        elif isinstance(value, TypeValue):
            type_tag = value.type_tag
        context.scope.bind_type_alias(
            name,
            render(groups[1]),
            type_tag=type_tag,
            vector=vector,
        )
        return ""
