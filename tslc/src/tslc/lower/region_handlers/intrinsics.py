"""Intrinsic TSIL region lowerers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.ir.segments import Region
from tslc.lower._text import skip_string
from tslc.lower.context import LoweringSession
from tslc.lower.queries import QueryEvaluator, TextValue
from tslc.lower.region_handlers.common import _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody

def _split_compose_terms(text: str) -> list[str]:
    """Split an ``intrin_compose`` selector into ``base`` + ``key=value`` modifiers on top-level
    commas OR runs of whitespace, respecting ``()``/``<>`` nesting and quoted strings. Handles
    both the comma form (``i32gather, suffix=…, immediate(2)=1``) and the space form
    (``cvt infix=… infix_sep="" suffix=…``); modifier values are parens-wrapped or quoted, so they
    never contain a top-level separator."""

    terms: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch in "(<":
            depth += 1
        elif ch in ")>":
            depth -= 1
        elif depth == 0 and (ch == "," or ch.isspace()):
            if start < i:
                terms.append(text[start:i])
            start = i + 1
        i += 1
    if start < n:
        terms.append(text[start:])
    return [term.strip() for term in terms if term.strip()]


@dataclass(frozen=True, slots=True)
class ComposeModifiers:
    """The parsed selector of ``intrin_compose<base, key=value, ...>``."""

    base: str | None
    modifiers: tuple[tuple[str, str], ...]

    @classmethod
    def parse(cls, selector_text: str) -> "ComposeModifiers":
        terms = _split_compose_terms(selector_text)
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

    def immediate_forward(self) -> tuple[int, str] | None:
        """An ``immediate(N)=V`` modifier as ``(position, value)``: intrinsic-arg position ``N``
        carries the compile-time immediate ``V``. C++ keeps ``V`` as the positional arg the body
        already supplies; Rust forwards it as a turbofish const and drops that positional arg
        (the gather scale: a C++ runtime const arg vs a Rust const generic). None when absent."""

        for name, value in self.modifiers:
            match = re.fullmatch(r"immediate\((\d+)\)", name)
            if match:
                return int(match.group(1)), value
        return None


class IntrinComposeLowerer:
    """``intrin_compose<base, suffix=...>(args)`` -> a composed intrinsic call."""

    keyword = "intrin_compose"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        context.effects.mark_unsafe()
        modifiers = ComposeModifiers.parse(region.selector_text)
        if modifiers.base is None:
            context.effects.skip(
                "TSL-LOWER-EMPTY-INTRIN-COMPOSE", "intrin_compose has no base name"
            )
            return region.full_text

        # An `infix`/`infix_sep` modifier folds into the base: `base + infix_sep + infix`
        # (`cast`+``+`ps` -> `castps`, completed to `_mm256_castps_si256` by the suffix; `cvt`+`epi8`
        # -> `cvtepi8` -> `_mm256_cvtepi8_epi16`). Unresolvable -> skip.
        base = self._compose_base(modifiers, modifiers.base, context)
        if base is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-INFIX",
                f"could not resolve intrin_compose infix in {region.selector_text!r}",
            )
            return region.full_text

        suffix = self._suffix(modifiers, context)
        if context.effects.has_errors:
            return region.full_text

        name = context.env.translation.compose_intrinsic_name(
            context.env.extension, base, suffix
        )
        if name is None:
            context.effects.skip(
                "TSL-LOWER-NO-INTRINSIC-PREFIX",
                f"extension {context.env.extension.name!r} has no "
                f"{context.env.translation.backend_id} "
                f"intrinsic prefix for intrin_compose<{modifiers.base}>",
            )
            return region.full_text
        # `post=mask` selects the mask-returning intrinsic on native-predicate
        # extensions (`_mm512_cmpeq_epi32` -> `_mm512_cmpeq_epi32_mask`); on
        # lane-bitmask/scalar extensions the compare already yields the mask, so it
        # stays a no-op.
        if (
            modifiers.get("post") == "mask"
            and context.env.extension.mask_policy.kind == "native_predicate_by_lanes"
        ):
            name = f"{name}_mask"
        # Const-generic immediate bridge: a Rust immediate intrinsic takes the count as a
        # const generic whose type differs across ISAs (avx2 `i32` vs avx512 `u32`), and a
        # single shared const can't satisfy both. When the immediate declares the `literal_match`
        # strategy, forward it through a literal match — each arm calls the intrinsic with a
        # *literal* const, which re-types to whatever that intrinsic wants (folds to one arm at
        # compile time). Otherwise the immediate stays a positional const arg (C++ always;
        # Rust when no strategy is declared — a compile-time-constant arg works directly).
        match_call = self._literal_match(name, region, context, render)
        if match_call is not None:
            return match_call
        forward = modifiers.immediate_forward()
        if forward is not None:
            return self._immediate_forward(name, forward, region, context, render)
        return f"{name}({render(region.body)})"

    def _immediate_forward(
        self,
        name: str,
        forward: tuple[int, str],
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> str:
        """Emit an intrinsic whose arg at position ``N`` is a compile-time immediate ``V``
        (``immediate(N)=V``). Rust forwards ``V`` as a turbofish const and drops that positional
        arg (`name::<V>(rest)`); C++ leaves ``V`` as the positional arg the body already supplies
        (`name(all args)`) — the same intrinsic shape differs between backends (gather's scale)."""

        position, value = forward
        args = tuple(render(group).strip() for group in _split_arg_groups(region.body))
        return context.env.translation.render_immediate_intrinsic_call(
            name, value, position, args
        )

    def _literal_match(
        self, name: str, region: Region, context: LoweringSession, render: RenderBody
    ) -> str | None:
        """A Rust `literal_match` immediate intrinsic -> a literal match over the immediate's
        legal range: `match shift { 0 => name::<0>(rest), … hi-1 => …, _ => name::<lo>(rest) }`.
        Returns None when not applicable (wrong backend, no strategy, no range, or the
        immediate isn't among the args)."""

        if (
            context.env.immediate_dispatch != "literal_match"
            or context.env.immediate_name is None
            or context.env.immediate_range is None
        ):
            return None
        args = tuple(render(group).strip() for group in _split_arg_groups(region.body))
        return context.env.translation.render_literal_match_intrinsic_call(
            name, context.env.immediate_name, context.env.immediate_range, args
        )

    def _compose_base(
        self, modifiers: ComposeModifiers, base: str, context: LoweringSession
    ) -> str | None:
        """Fold an ``infix``/``infix_sep`` modifier into the intrinsic base: ``base + infix_sep +
        infix`` (both resolved as query values — ``infix`` is typically a type's intrinsic suffix,
        ``infix_sep`` a literal like ``""``). Returns ``base`` unchanged when there is no ``infix``,
        or None when a part doesn't resolve to text."""

        infix_expr = modifiers.get("infix")
        if infix_expr is None:
            return base
        infix = self._evaluator.evaluate(infix_expr, context)
        sep_expr = modifiers.get("infix_sep")
        separator = (
            self._evaluator.evaluate(sep_expr, context)
            if sep_expr is not None
            else TextValue("")
        )
        if not isinstance(infix, TextValue) or not isinstance(separator, TextValue):
            return None
        return f"{base}{separator.text}{infix.text}"

    def _suffix(self, modifiers: ComposeModifiers, context: LoweringSession) -> str | None:
        explicit = modifiers.get("suffix")
        if explicit is None:
            # No explicit modifier: use the extension's default suffix for the selected type.
            return context.env.translation.default_suffix(
                context.env.extension, context.env.type_tag
            )
        value = self._evaluator.evaluate(explicit, context)
        if isinstance(value, TextValue):
            return value.text
        context.effects.skip(
            "TSL-LOWER-UNRESOLVED-SUFFIX",
            f"could not resolve intrinsic suffix from {explicit!r}",
        )
        return None


class IntrinLowerer:
    """``intrin<name>(args)`` -> a direct intrinsic call.

    The name is qualified for the backend (Rust needs the ``core::arch`` path).
    """

    keyword = "intrin"

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        context.effects.mark_unsafe()
        name = context.env.translation.qualify_intrinsic(
            context.env.extension, region.selector_text.strip()
        )
        return f"{name}({render(region.body)})"
