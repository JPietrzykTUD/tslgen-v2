"""Cast TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession
from tslc.lower.queries import QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.common import _segment_text, _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody


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

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        args = _split_arg_groups(region.body)
        if len(args) != 2:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported cast: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        # A trailing `*` on the type argument means a pointer reinterpret. This infers
        # intent from raw text; the cleaner-but-corpus-churny design would make it
        # explicit (`cast<reinterpret type=ptr>(...)`, `type=value` default). Deferred to
        # avoid rewriting every cast site for an internal-only gain.
        type_text = _segment_text(args[0])
        if type_text.rstrip().endswith("*"):
            return self._pointer_cast(type_text, region, context, render(args[1]))

        key = f"cast_{region.selector_text.strip()}"
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
        self, type_text: str, region: Region, context: LoweringSession, expr: str
    ) -> str:
        """``cast<reinterpret>(type<…>() [const] *, ptr)`` -> a backend pointer cast."""

        stripped = type_text.rstrip()[:-1].rstrip()  # drop the trailing `*`
        is_const = stripped.endswith("const")
        inner_text = stripped[: -len("const")].rstrip() if is_const else stripped
        inner = self._type_spelling(inner_text, context)
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

    def _type_spelling(self, type_text: str, context: LoweringSession) -> str | None:
        """Resolve a type expression to its backend spelling — a register spelling
        (``vector::register`` -> ``TextValue``) or a base type tag (-> scalar spelling)."""

        value = self._evaluator.evaluate(type_text, context)
        if isinstance(value, TextValue):
            return value.text
        if isinstance(value, TypeValue):
            return context.env.backend.types.scalar_spelling(value.type_tag)
        return None
