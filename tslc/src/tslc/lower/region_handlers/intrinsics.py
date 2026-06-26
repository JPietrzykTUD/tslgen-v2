"""Intrinsic TSIL region lowerers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.ir.segments import Region
from tslc.lower._text import split_selector_terms
from tslc.lower.context import LoweringSession
from tslc.lower.queries import QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.common import _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.render.model import RenderField, literal_text, render_sequence, render_text


def _parse_modifier_terms(text: str) -> tuple[tuple[str, str], ...]:
    modifiers: list[tuple[str, str]] = []
    for term in split_selector_terms(text):
        key, sep, value = term.partition("=")
        if sep:
            modifiers.append((key.strip(), value.strip()))
    return tuple(modifiers)


@dataclass(frozen=True, slots=True)
class IntrinsicSelector:
    """The parsed selector of ``intrin<name[, build[...]]>``."""

    name: str | None
    build: bool
    modifiers: tuple[tuple[str, str], ...]
    unsupported_terms: tuple[str, ...] = ()

    @classmethod
    def parse(cls, selector_text: str) -> "IntrinsicSelector":
        terms = split_selector_terms(selector_text)
        if not terms:
            return cls(name=None, build=False, modifiers=())
        if _has_top_level_whitespace(terms[0]):
            return cls(
                name=terms[0],
                build=False,
                modifiers=(),
                unsupported_terms=(terms[0],),
            )
        modifiers: list[tuple[str, str]] = []
        unsupported_terms: list[str] = []
        build = False
        for term in terms[1:]:
            if term == "build":
                build = True
                continue
            if term.startswith("build[") and term.endswith("]"):
                build = True
                modifiers.extend(_parse_modifier_terms(term[len("build[") : -1]))
                continue
            unsupported_terms.append(term)
        return cls(
            name=terms[0],
            build=build,
            modifiers=tuple(modifiers),
            unsupported_terms=tuple(unsupported_terms),
        )

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


def _has_top_level_whitespace(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "(<[":
            depth += 1
        elif char in ")>]" and depth:
            depth -= 1
        elif depth == 0 and char.isspace():
            return True
    return False


class IntrinLowerer:
    """``intrin<name>(args)`` or ``intrin<base, build[...]>(args)``."""

    keyword = "intrin"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        context.effects.mark_internal_unsafe("intrinsic")
        selector = IntrinsicSelector.parse(region.selector_text)
        if selector.name is None:
            context.effects.skip(
                "TSL-LOWER-EMPTY-INTRIN",
                "intrin has no name",
                source=region.source,
            )
            return region.full_text
        if selector.unsupported_terms:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-INTRIN-SELECTOR",
                "intrin selector terms require build[...]: "
                + ", ".join(repr(term) for term in selector.unsupported_terms),
                source=region.source,
            )
            return region.full_text
        if not selector.build:
            name = context.env.backend.intrinsics.qualify_intrinsic(
                context.env.extension, selector.name
            )
            return render_sequence(
                (literal_text(f"{name}("), render(region.body), literal_text(")"))
            )
        return self._lower_build(selector, region, context, render)

    def _lower_build(
        self,
        selector: IntrinsicSelector,
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> RenderField:
        # An `infix`/`infix_sep` modifier folds into the base: `base + infix_sep + infix`
        # (`cast`+``+`ps` -> `castps`, completed to `_mm256_castps_si256` by the suffix; `cvt`+`epi8`
        # -> `cvtepi8` -> `_mm256_cvtepi8_epi16`). Unresolvable -> skip.
        assert selector.name is not None
        base = self._compose_base(selector, selector.name, context)
        if base is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-INFIX",
                f"could not resolve intrin build infix in {region.selector_text!r}",
                source=region.source,
            )
            return region.full_text

        prefix = self._prefix(selector, region, context)
        suffix = self._suffix(selector, region, context)
        if context.effects.unsupported or context.effects.has_errors:
            return region.full_text

        name = context.env.backend.intrinsics.compose_intrinsic_name(
            context.env.extension, base, suffix, prefix=prefix
        )
        if name is None:
            context.effects.skip(
                "TSL-LOWER-NO-INTRINSIC-PREFIX",
                f"extension {context.env.extension.name!r} has no "
                f"{context.env.backend.backend_id} "
                f"intrinsic prefix for intrin<{selector.name}, build>",
                source=region.source,
            )
            return region.full_text
        # `post=mask` selects the mask-returning intrinsic on native-predicate
        # extensions (`_mm512_cmpeq_epi32` -> `_mm512_cmpeq_epi32_mask`); on
        # lane-bitmask/scalar extensions the compare already yields the mask, so it
        # stays a no-op.
        if (
            selector.get("post") == "mask"
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
        forward = selector.immediate_forward()
        if forward is not None:
            return self._immediate_forward(name, forward, region, context, render)
        return render_sequence((literal_text(f"{name}("), render(region.body), literal_text(")")))

    def _immediate_forward(
        self,
        name: str,
        forward: tuple[int, str],
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> RenderField:
        """Emit an intrinsic whose arg at position ``N`` is a compile-time immediate ``V``
        (``immediate(N)=V``). Rust forwards ``V`` as a turbofish const and drops that positional
        arg (`name::<V>(rest)`); C++ leaves ``V`` as the positional arg the body already supplies
        (`name(all args)`) — the same intrinsic shape differs between backends (gather's scale)."""

        position, value = forward
        args = tuple(
            render_text(render(group)).strip() for group in _split_arg_groups(region.body)
        )
        return context.env.backend.intrinsics.render_immediate_intrinsic_call(
            name, value, position, args
        )

    def _literal_match(
        self, name: str, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField | None:
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
        args = tuple(
            render_text(render(group)).strip() for group in _split_arg_groups(region.body)
        )
        return context.env.backend.intrinsics.render_literal_match_intrinsic_call(
            name, context.env.immediate_name, context.env.immediate_range, args
        )

    def _compose_base(
        self, selector: IntrinsicSelector, base: str, context: LoweringSession
    ) -> str | None:
        """Fold an ``infix``/``infix_sep`` modifier into the intrinsic base: ``base + infix_sep +
        infix`` (both resolved as query values — ``infix`` is typically a type's intrinsic suffix,
        ``infix_sep`` a literal like ``""``). Returns ``base`` unchanged when there is no ``infix``,
        or None when a part doesn't resolve to a text or type-backed suffix."""

        infix_expr = selector.get("infix")
        if infix_expr is None:
            return base
        if infix_expr == "to_type_suffix":
            target_type = context.scope.resolve_target_type_symbol("ToType")
            separator = self._infix_separator(selector, context)
            suffix = (
                context.env.backend.intrinsics.default_suffix(
                    context.env.extension, target_type
                )
                if target_type is not None
                else None
            )
            if separator is None or suffix is None:
                return None
            return f"{base}{separator}{suffix}"
        infix = self._evaluator.evaluate(infix_expr, context)
        separator = self._infix_separator(selector, context)
        if separator is None:
            return None
        infix_text = self._text_or_type_suffix(infix, context)
        if infix_text is None:
            return None
        return f"{base}{separator}{infix_text}"

    def _infix_separator(
        self, selector: IntrinsicSelector, context: LoweringSession
    ) -> str | None:
        sep_expr = selector.get("infix_sep")
        separator = (
            self._evaluator.evaluate(sep_expr, context)
            if sep_expr is not None
            else TextValue("")
        )
        if not isinstance(separator, TextValue):
            return None
        return separator.as_text()

    def _prefix(
        self,
        selector: IntrinsicSelector,
        region: Region,
        context: LoweringSession,
    ) -> str | None:
        explicit = selector.get("prefix")
        if explicit is None:
            return None
        value = self._evaluator.evaluate(explicit, context)
        if isinstance(value, TextValue):
            return value.as_text()
        context.effects.skip(
            "TSL-LOWER-UNRESOLVED-PREFIX",
            f"could not resolve intrinsic prefix from {explicit!r}; expected text",
            source=region.source,
        )
        return None

    def _suffix(
        self,
        selector: IntrinsicSelector,
        region: Region,
        context: LoweringSession,
    ) -> str | None:
        explicit = selector.get("suffix")
        if explicit is None:
            # No explicit modifier: use the extension's default suffix for the selected type.
            return context.env.backend.intrinsics.default_suffix(
                context.env.extension, context.env.type_tag
            )
        value = self._evaluator.evaluate(explicit, context)
        suffix = self._text_or_type_suffix(value, context)
        if suffix is not None:
            return suffix
        context.effects.skip(
            "TSL-LOWER-UNRESOLVED-SUFFIX",
            f"could not resolve intrinsic suffix from {explicit!r}; "
            "expected text or type",
            source=region.source,
        )
        return None

    def _text_or_type_suffix(
        self, value: object, context: LoweringSession
    ) -> str | None:
        if isinstance(value, TextValue):
            return value.as_text()
        if isinstance(value, TypeValue):
            return context.env.backend.intrinsics.default_suffix(
                context.env.extension, value.type_tag
            )
        return None
