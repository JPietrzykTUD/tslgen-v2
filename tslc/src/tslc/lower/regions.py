"""Region lowerers: one focused class per TSIL keyword island.

A :class:`RegionLowerer` turns one :class:`~tslc.ir.segments.Region` into target
text, using the shared :class:`~tslc.lower.context.LoweringContext` and a
``render`` callback for its (recursively-scanned) argument body. New TSIL
keywords are added by writing a new class and listing it in
:data:`DEFAULT_REGION_LOWERERS` — never by extending a dispatch megafunction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from tslc.ir.segments import Region, Segment
from tslc.lower.context import LoweringContext
from tslc.lower.queries import QueryEvaluator, TextValue
from tslc.lower._text import split_top_level

RenderBody = Callable[[tuple[Segment, ...]], str]


class RegionLowerer(Protocol):
    keyword: str

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        """Render one region to target text (recursing into its body via ``render``)."""


@dataclass(frozen=True, slots=True)
class ComposeModifiers:
    """The parsed selector of ``intrin_compose<base, key=value, ...>``."""

    base: str | None
    modifiers: tuple[tuple[str, str], ...]

    @classmethod
    def parse(cls, selector_text: str) -> "ComposeModifiers":
        terms = split_top_level(selector_text)
        if not terms:
            return cls(base=None, modifiers=())
        modifiers: list[tuple[str, str]] = []
        for term in terms[1:]:
            key, sep, value = term.partition("=")
            if sep:
                modifiers.append((key.strip(), value.strip()))
        return cls(base=terms[0], modifiers=tuple(modifiers))

    def get(self, key: str) -> str | None:
        for name, value in self.modifiers:
            if name == key:
                return value
        return None


class IntrinComposeLowerer:
    """``intrin_compose<base, suffix=...>(args)`` -> a composed intrinsic call."""

    keyword = "intrin_compose"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        context.mark_unsafe()
        modifiers = ComposeModifiers.parse(region.selector_text)
        if modifiers.base is None:
            context.skip("TSL-LOWER-EMPTY-INTRIN-COMPOSE", "intrin_compose has no base name")
            return region.full_text

        suffix = self._suffix(modifiers, context)
        if context.has_errors:
            return region.full_text

        name = context.translation.compose_intrinsic_name(
            context.extension, modifiers.base, suffix
        )
        if name is None:
            context.skip(
                "TSL-LOWER-NO-INTRINSIC-PREFIX",
                f"extension {context.extension.name!r} has no {context.translation.backend_id} "
                f"intrinsic prefix for intrin_compose<{modifiers.base}>",
            )
            return region.full_text
        return f"{name}({render(region.body)})"

    def _suffix(self, modifiers: ComposeModifiers, context: LoweringContext) -> str | None:
        explicit = modifiers.get("suffix")
        if explicit is None:
            # No explicit modifier: use the extension's default suffix for the selected type.
            return context.translation.default_suffix(context.extension, context.type_tag)
        value = self._evaluator.evaluate(explicit, context)
        if isinstance(value, TextValue):
            return value.text
        context.skip(
            "TSL-LOWER-UNRESOLVED-SUFFIX",
            f"could not resolve intrinsic suffix from {explicit!r}",
        )
        return None


class IntrinLowerer:
    """``intrin<name>(args)`` -> a direct intrinsic call.

    The name is qualified for the backend (Rust needs the ``core::arch`` path).
    """

    keyword = "intrin"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        context.mark_unsafe()
        name = context.translation.qualify_intrinsic(
            context.extension, region.selector_text.strip()
        )
        return f"{name}({render(region.body)})"


class VarLowerer:
    """``var<variant>(name, value)`` -> the backend's local-declaration template.

    Backend-neutral: the declaration syntax (``auto const {name} = {value};`` /
    ``let {name} = {value};``) comes from the backend's ``var_<variant>`` template.
    """

    keyword = "var"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        terms = split_top_level(render(region.body))
        variant = region.selector_text.strip()
        key = f"var_{variant}"
        if len(terms) < 2 or context.translation.template(key) is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-VAR",
                f"unsupported var<{variant}> declaration: {region.full_text!r}",
            )
            return region.full_text
        name = terms[0]
        value = ", ".join(terms[1:])
        return context.translation.render_template(key, name=name, value=value)


class EmitReturnLowerer:
    """``emit_return(expr)`` -> the backend's return framing around the value.

    Backend-neutral: the ``return`` spelling comes from the backend's
    ``emit_return`` translate template. Any required ``unsafe`` framing is applied
    once to the whole body by ``translation.frame_body`` in the lowerer.
    """

    keyword = "emit_return"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        return context.translation.frame_return(render(region.body))


DEFAULT_REGION_LOWERERS: tuple[RegionLowerer, ...] = (
    IntrinComposeLowerer(),
    IntrinLowerer(),
    VarLowerer(),
    EmitReturnLowerer(),
)
