"""Cast TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.region_syntax import parse_cast_selector, segments_text, split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.queries import QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField


class CastLowerer:
    """``cast<variant>(type<...>(...), expr)`` -> the backend's cast template.

    The type argument is resolved by delegating to the query evaluator (so query
    semantics live in one place, not duplicated here); the value argument is
    rendered normally. The cast syntax itself comes from the ``cast_<variant>``
    translate template (C++ ``static_cast<T>(e)`` / Rust ``(e as T)``).
    """

    keyword = "cast"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        args = split_arg_groups(region.body)
        if len(args) != 2:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported cast: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        selector = parse_cast_selector(region.selector_text)
        if not selector.is_valid:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported cast: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        type_text = segments_text(args[0])
        if selector.type_kind in {"ptr", "const_ptr"}:
            if selector.variant != "reinterpret":
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-CAST",
                    f"unsupported pointer cast: {region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
            return self._pointer_cast(
                type_text,
                is_const=selector.type_kind == "const_ptr",
                region=region,
                context=context,
                expr=render(args[1]),
            )

        if type_text.rstrip().endswith("*"):
            return self._legacy_pointer_cast(type_text, region, context, render(args[1]))

        key = f"cast_{selector.variant}"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported cast: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        spelling = self._type_spelling(type_text, context)
        if spelling is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve cast type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.templates.render_template(
            key, type=spelling, expr=render(args[1])
        )

    def _pointer_cast(
        self,
        type_text: str,
        *,
        is_const: bool,
        region: Region,
        context: LoweringSession,
        expr: RenderField,
    ) -> RenderField:
        """``cast<reinterpret, type=ptr|const_ptr>(type<...>(), ptr)`` -> pointer cast."""

        inner = self._type_spelling(type_text, context)
        if inner is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve pointer cast type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.syntax.render_pointer_cast(
            inner, is_const=is_const, expr=expr
        )

    def _legacy_pointer_cast(
        self,
        type_text: str,
        region: Region,
        context: LoweringSession,
        expr: RenderField,
    ) -> RenderField:
        stripped = type_text.rstrip()[:-1].rstrip()  # drop the trailing `*`
        is_const = stripped.endswith("const")
        inner_text = stripped[: -len("const")].rstrip() if is_const else stripped
        return self._pointer_cast(
            inner_text,
            is_const=is_const,
            region=region,
            context=context,
            expr=expr,
        )

    def _type_spelling(
        self, type_text: str, context: LoweringSession
    ) -> RenderField | None:
        """Resolve a type expression to its backend spelling — a register spelling
        (``vector::register`` -> ``TextValue``) or a base type tag (-> scalar spelling)."""

        value = self._evaluator.evaluate(type_text, context)
        if isinstance(value, TextValue):
            return value.text
        if isinstance(value, TypeValue):
            return context.env.backend.types.scalar_spelling(value.type_tag)
        return None
