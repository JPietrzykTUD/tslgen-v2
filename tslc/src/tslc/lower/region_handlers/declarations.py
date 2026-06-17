"""Declaration and alias TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringContext, VectorValue
from tslc.lower.queries import QueryEvaluator, TypeValue
from tslc.lower.region_handlers.common import _segment_text, _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody

class VarLowerer:
    """``var<variant>(...)`` -> the backend's local-declaration template.

    Two shapes: inferred (``var<infer>(name, value)`` / ``var<const_infer>``) fills
    ``var_<variant> = {name}/{value}``; typed (``var<typed>(type, name, value)``)
    additionally carries ``{type}``. An uninitialized array initializer
    (``value<backend>(uninit::array)``) routes to the dedicated ``var_array_uninit``
    template instead, which carries ``{type}`` so Rust's MaybeUninit gets it (a value
    region alone cannot supply the array type). The declaration syntax itself is
    backend-neutral, coming from the ``var_*`` translate templates.
    """

    keyword = "var"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        variant = region.selector_text.strip()
        groups = _split_arg_groups(region.body)
        if variant == "typed":
            return self._typed(variant, groups, region, context, render)
        if variant == "init_register":
            # A zero-initialized register declaration: `var<init_register>(name)`. The type is
            # the vector's register type (C++ template uses it; the Rust template builds
            # `[BaseType::default(); LANES]` and ignores it).
            if len(groups) != 1 or context.translation.template("var_init_register") is None:
                context.skip(
                    "TSL-LOWER-UNSUPPORTED-VAR",
                    f"unsupported var<init_register>: {region.full_text!r}",
                )
                return region.full_text
            return context.translation.render_template(
                "var_init_register",
                type=context.translation.register_type_spelling(),
                name=render(groups[0]).strip(),
            )
        if len(groups) < 2 or context.translation.template(f"var_{variant}") is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<{variant}> declaration: {region.full_text!r}",
            )
            return region.full_text
        name = render(groups[0]).strip()
        value = ", ".join(render(group) for group in groups[1:])
        return context.translation.render_template(f"var_{variant}", name=name, value=value)

    def _typed(
        self,
        variant: str,
        groups: list[tuple[Segment, ...]],
        region: Region,
        context: LoweringContext,
        render: RenderBody,
    ) -> str:
        if len(groups) != 3:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<typed> declaration: {region.full_text!r}",
            )
            return region.full_text
        type_text = render(groups[0]).strip()
        name = render(groups[1]).strip()
        # An uninitialized array uses the type-carrying template (see class docstring).
        key = "var_array_uninit" if "uninit" in _segment_text(groups[2]) else f"var_{variant}"
        if context.translation.template(key) is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<typed> declaration: {region.full_text!r}",
            )
            return region.full_text
        if key == "var_array_uninit":
            return context.translation.render_template(key, type=type_text, name=name)
        value = render(groups[2])
        return context.translation.render_template(key, type=type_text, name=name, value=value)


class LetLowerer:
    """``let<type>(Name, type-expr)`` -> a type alias, applied by **substitution**: the
    resolved type spelling is recorded and inlined at every later use of ``Name`` in the body
    (the lowerer substitutes after rendering). A real local alias would be ``using Name = T;``
    in C++, but Rust rejects a fn-local ``type Name = Self::T;`` (E0401), so inlining is the
    backend-neutral form. The type-expression is resolved via the normal region path (e.g.
    ``type<generation>(vector::mask)`` -> the mask-type spelling)."""

    keyword = "let"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        variant = region.selector_text.strip()
        groups = _split_arg_groups(region.body)
        if variant != "type" or len(groups) != 2:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-LET",
                f"unsupported let<{variant}>: {region.full_text!r}",
            )
            return region.full_text
        name = render(groups[0]).strip()
        # A vector-valued alias (`let<type>(OutVec, transform_extension(ToBase))`) is captured
        # structurally too, so a later `generic::length(OutVec)` query arg resolves to the vector
        # (the rendered spelling below still drives type-position substitution like `to_array[OutVec]`).
        value = self._evaluator.evaluate(_segment_text(groups[1]), context)
        if isinstance(value, VectorValue):
            context.vector_aliases[name] = value
        elif isinstance(value, TypeValue):
            context.type_value_aliases[name] = value.type_tag
        context.type_aliases[name] = render(groups[1]).strip()
        return ""
