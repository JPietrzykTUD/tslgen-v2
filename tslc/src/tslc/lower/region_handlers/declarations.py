"""Declaration and alias TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.region_syntax import parse_var_selector, segments_text, split_arg_groups
from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringSession, VectorValue
from tslc.lower.queries import QueryEvaluator, TypeValue
from tslc.lower.region_handlers.common import _resolve_type_expression
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import (
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

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def finish_statement(self, rendered: RenderText, region: Region) -> RenderField:
        del region
        return rendered

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        groups = split_arg_groups(region.body)
        selector = parse_var_selector(region.selector_text, len(groups))
        if selector is not None and selector.kind == "typed":
            # Both are `(type, name, value)` 3-group forms; `_typed` keys on the variant
            # (`var_typed` / `var_const_typed`), so a const-qualified typed local works too.
            return self._typed(selector.variant, groups, region, context, render)
        if selector is not None and selector.kind == "runtime_array":
            return self._runtime_array(groups, region, context, render)
        if selector is not None and selector.kind == "init_register":
            # A zero-initialized register declaration: `var<init_register>(name)`. The type is
            # the vector's register type (C++ template uses it; the Rust template builds
            # `[BaseType::default(); LANES]` and ignores it).
            key = f"var_{selector.variant}"
            if context.env.backend.templates.template(key) is None:
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-VAR",
                    f"unsupported var<{selector.variant}>: {region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
            return context.env.backend.templates.render_template(
                key,
                type=context.env.backend.types.register_type_spelling(),
                name=render_text(render(groups[0])).strip(),
            )
        if (
            selector is None
            or context.env.backend.templates.template(f"var_{selector.variant}") is None
        ):
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<{region.selector_text.strip()}> declaration: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = render_text(render(groups[0])).strip()
        value = _join_rendered(groups[1:], render)
        return context.env.backend.templates.render_template(
            f"var_{selector.variant}", name=name, value=value
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
        resolved_type = _resolve_type_expression(
            segments_text(groups[0]),
            context,
            self._evaluator,
            fallback=render(groups[0]),
        )
        if resolved_type is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-VAR-TYPE",
                f"could not resolve var<{variant}> type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        type_value = resolved_type[1]
        name = render_text(render(groups[1])).strip()
        # An uninitialized array uses the type-carrying template (see class docstring).
        key = "var_array_uninit" if "uninit" in segments_text(groups[2]) else f"var_{variant}"
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
        resolved_type = _resolve_type_expression(
            segments_text(groups[0]),
            context,
            self._evaluator,
            fallback=render(groups[0]),
        )
        if resolved_type is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-VAR-TYPE",
                f"could not resolve var<runtime_array> type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        type_value = resolved_type[1]
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
    """``let<type>(Name, type-expr)`` binds a type alias for later TSIL use.

    Type-owned positions such as ``cast<static>(Name, value)`` and
    ``var<typed>(Name, value, init)`` resolve the alias directly. ``type(Name)`` is
    reserved for explicitly inserting its spelling into otherwise raw target text.
    Raw target text remains opaque and is never searched for alias identifiers.
    """

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
        groups = split_arg_groups(region.body)
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
        # (the rendered spelling below still drives direct type-position substitution).
        resolved_type = _resolve_type_expression(
            segments_text(groups[1]),
            context,
            self._evaluator,
            fallback=render(groups[1]),
        )
        if resolved_type is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-LET-TYPE",
                f"could not resolve let<type> value in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        value, spelling = resolved_type
        type_tag: str | None = None
        vector: VectorValue | None = None
        if isinstance(value, VectorValue):
            vector = value
        elif isinstance(value, TypeValue):
            type_tag = value.type_tag
        context.scope.bind_type_alias(
            name,
            spelling,
            type_tag=type_tag,
            vector=vector,
        )
        return ""
