"""Region lowerers: one focused class per TSIL keyword island.

A :class:`RegionLowerer` turns one :class:`~tslc.ir.segments.Region` into target
text, using the shared :class:`~tslc.lower.context.LoweringContext` and a
``render`` callback for its (recursively-scanned) argument body. New TSIL
keywords are added by writing a new class and listing it in
:data:`DEFAULT_REGION_LOWERERS` — never by extending a dispatch megafunction.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.context import LoweringContext
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue, TypeValue
from tslc.lower._text import skip_string, split_top_level

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
        # `post=mask` selects the mask-returning intrinsic on native-predicate
        # extensions (`_mm512_cmpeq_epi32` -> `_mm512_cmpeq_epi32_mask`); on
        # lane-bitmask/scalar extensions the compare already yields the mask, so it
        # stays a no-op.
        if (
            modifiers.get("post") == "mask"
            and context.extension.mask_policy.kind == "native_predicate_by_lanes"
        ):
            name = f"{name}_mask"
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

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        args = _split_arg_groups(region.body)
        if len(args) != 2:
            context.skip("TSL-LOWER-UNSUPPORTED-CAST", f"unsupported cast: {region.full_text!r}")
            return region.full_text

        # A trailing `*` on the type argument means a pointer reinterpret. This infers
        # intent from raw text; the cleaner-but-corpus-churny design would make it
        # explicit (`cast<reinterpret type=ptr>(...)`, `type=value` default). Deferred to
        # avoid rewriting every cast site for an internal-only gain.
        type_text = _segment_text(args[0])
        if type_text.rstrip().endswith("*"):
            return self._pointer_cast(type_text, region, context, render(args[1]))

        key = f"cast_{region.selector_text.strip()}"
        if context.translation.template(key) is None:
            context.skip("TSL-LOWER-UNSUPPORTED-CAST", f"unsupported cast: {region.full_text!r}")
            return region.full_text

        spelling = self._type_spelling(type_text, context)
        if spelling is None:
            context.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve cast type in {region.full_text!r}",
            )
            return region.full_text
        return context.translation.render_template(key, type=spelling, expr=render(args[1]))

    def _pointer_cast(
        self, type_text: str, region: Region, context: LoweringContext, expr: str
    ) -> str:
        """``cast<reinterpret>(type<…>() [const] *, ptr)`` -> a backend pointer cast."""

        stripped = type_text.rstrip()[:-1].rstrip()  # drop the trailing `*`
        is_const = stripped.endswith("const")
        inner_text = stripped[: -len("const")].rstrip() if is_const else stripped
        inner = self._type_spelling(inner_text, context)
        if inner is None:
            context.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve pointer cast type in {region.full_text!r}",
            )
            return region.full_text
        return context.translation.render_pointer_cast(inner, is_const=is_const, expr=expr)

    def _type_spelling(self, type_text: str, context: LoweringContext) -> str | None:
        """Resolve a type expression to its backend spelling — a register spelling
        (``vector::register`` -> ``TextValue``) or a base type tag (-> scalar spelling)."""

        value = self._evaluator.evaluate(type_text, context)
        if isinstance(value, TextValue):
            return value.text
        if isinstance(value, TypeValue):
            return context.translation.scalar_spelling(value.type_tag)
        return None


def _split_arg_groups(segments: tuple[Segment, ...]) -> list[tuple[Segment, ...]]:
    """Split a body segment sequence into top-level comma-separated argument groups.

    Regions are atomic (their internal commas/brackets stay inside them); only
    depth-0 commas in raw text separate arguments.
    """

    groups: list[list[Segment]] = [[]]
    depth = 0
    for segment in segments:
        if isinstance(segment, Region):
            groups[-1].append(segment)
            continue
        text = segment.text
        start = 0
        for index, char in enumerate(text):
            if char in "(<[":
                depth += 1
            elif char in ")>]":
                depth -= 1
            elif char == "," and depth == 0:
                piece = text[start:index]
                if piece.strip():
                    groups[-1].append(RawText(piece))
                groups.append([])
                start = index + 1
        tail = text[start:]
        if tail.strip():
            groups[-1].append(RawText(tail))
    return [tuple(group) for group in groups]


def _segment_text(segments: tuple[Segment, ...]) -> str:
    """Reconstruct the source text of a segment group (for query delegation)."""

    return "".join(
        seg.full_text if isinstance(seg, Region) else seg.text for seg in segments
    ).strip()


def _split_top_level_op(text: str, op: str) -> list[str]:
    """Split ``text`` on the two-char operator ``op`` at paren/bracket/string depth
    zero (so an operator inside a nested call is not a split point)."""

    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif depth == 0 and text[i : i + 2] == op:
            parts.append(text[start:i])
            i += 2
            start = i
            continue
        i += 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


class CallLowerer:
    """``call<primitive=NAME[Vec] attrs[aligned=…]>(args)`` -> a call to NAME's wrapper.

    Primitives are generated independently; this only renders the *call* (via
    ``translation.render_call``), it does not inline NAME's body. Only the simple
    ``[Vec]`` / no-type-arg form is handled; multi-type-arg forms (e.g.
    ``[Vec, ToBase]``, ``[OutVec]``) are deferred.

    A callee carrying a boolean-wildcard axis (e.g. ``store``/``load`` with ``aligned``)
    needs that axis passed at the call site: C++ could default it, but Rust const-generics
    can't be inferred when ambiguous. The value comes from the call's ``attrs[...]``
    (default ``false``); which axis keys a callee has comes from ``context.primitive_axes``.
    """

    keyword = "call"
    _NAME = re.compile(r"([A-Za-z_]\w*)")

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        selector = region.selector_text.strip()
        if not selector.startswith("primitive="):
            context.skip("TSL-LOWER-UNSUPPORTED-CALL", f"unsupported call: {region.full_text!r}")
            return region.full_text
        rest = selector[len("primitive=") :].strip()
        match = self._NAME.match(rest)
        if match is None:
            context.skip("TSL-LOWER-UNSUPPORTED-CALL", f"unsupported call: {region.full_text!r}")
            return region.full_text
        name = match.group(1)
        rest = rest[match.end() :].strip()

        type_args, rest = _take_bracket(rest)
        if type_args and type_args != "Vec":
            context.skip(
                "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
                f"call type-args {type_args!r} not supported yet: {region.full_text!r}",
            )
            return region.full_text

        attrs: dict[str, str] = {}
        if rest.startswith("attrs"):
            attr_text, rest = _take_bracket(rest[len("attrs") :].lstrip())
            for term in attr_text.split(","):
                key, sep, value = term.partition("=")
                if sep:
                    attrs[key.strip()] = value.strip()
        if rest:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-CALL",
                f"unsupported call selector tail {rest!r}: {region.full_text!r}",
            )
            return region.full_text

        axis_values = tuple(
            attrs.get(key, "false") for key in context.primitive_axes.get(name, ())
        )
        return context.translation.render_call(
            name,
            render(region.body),
            axis_values,
            context.primitive_arg_generics.get(name, 0),
        )


def _take_bracket(text: str) -> tuple[str, str]:
    """If ``text`` starts with ``[...]``, return ``(inside, remainder)``; else ``("", text)``."""

    text = text.lstrip()
    if not text.startswith("["):
        return "", text
    close = text.find("]")
    if close == -1:
        return "", text
    return text[1:close].strip(), text[close + 1 :].lstrip()


class IfGenerationLowerer:
    """``if<generation>(cond) { ... } else<generation> { ... }`` -> the taken branch.

    A *generation-time* conditional: the condition is evaluated now (against the
    type being generated) and **only the chosen branch's statements** are emitted —
    the output contains no ``if<generation>`` and no dead branch. ``else if`` chains
    nest naturally: the ``else_block`` holds a single nested ``if`` region that
    re-dispatches through this same lowerer.
    """

    keyword = "if"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        if region.selector_text.strip() != "generation":
            context.skip(
                "TSL-LOWER-UNSUPPORTED-IF",
                f"only if<generation> is modeled (runtime if not yet): {region.full_text!r}",
            )
            return region.full_text

        taken = self._evaluate_condition(_segment_text(region.body), context)
        if taken is None:
            context.skip(
                "TSL-LOWER-UNRESOLVED-IF-CONDITION",
                f"could not evaluate generation-time condition in {region.full_text!r}",
            )
            return region.full_text

        if taken:
            return render(region.block)
        if region.else_block is None:
            return ""
        return render(region.else_block)

    def _evaluate_condition(self, text: str, context: LoweringContext) -> bool | None:
        """Evaluate a generation-time boolean condition. Supports ``||`` / ``&&`` of
        query sub-conditions (``&&`` binds tighter), e.g.
        ``is_same(..., si64) || is_same(..., ui64)``. Returns None if unresolvable."""

        ors = _split_top_level_op(text, "||")
        if len(ors) > 1:
            results = [self._evaluate_condition(part, context) for part in ors]
            return None if None in results else any(results)
        ands = _split_top_level_op(text, "&&")
        if len(ands) > 1:
            results = [self._evaluate_condition(part, context) for part in ands]
            return None if None in results else all(results)
        value = self._evaluator.evaluate(text.strip(), context)
        return value.value if isinstance(value, BoolValue) else None


class AssumeAlignedLowerer:
    """``assume_aligned<N>(ptr)`` -> an aligned-pointer hint. C++ forwards to the static
    core's ``::tsl::assume_aligned<N>(ptr)`` (``std::assume_aligned``); Rust has no stable
    equivalent and the aligned intrinsic already assumes alignment, so it drops to ``ptr``.
    The ``<N>`` selector (e.g. ``value<generation>(vector::alignment)``) is query-resolved."""

    keyword = "assume_aligned"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        expr = render(region.body)
        if context.translation.backend_id == "rust":
            return expr
        value = self._evaluator.evaluate(region.selector_text.strip(), context)
        if not isinstance(value, TextValue):
            context.skip(
                "TSL-LOWER-UNRESOLVED-ASSUME-ALIGNED",
                f"could not resolve alignment in {region.full_text!r}",
            )
            return region.full_text
        return f"::tsl::assume_aligned<{value.text}>({expr})"


class LoopLowerer:
    """``loop<range>(var, start, end, step) { body }`` / ``loop<unroll>(count)`` -> the
    backend's **native** loop construct (NOT a generation-time unroll): the `loop_range` /
    `loop_unroll` translate template framing the (recursively-rendered) block. C++
    ``for (std::size_t i = 0; i < N; i += 1) { ... }`` / Rust ``for i in (0..N).step_by(1)
    { ... }``; the bound ``value<generation>(vector::length)`` resolves via the query region.
    """

    keyword = "loop"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        variant = region.selector_text.strip()
        key = f"loop_{variant}"
        if context.translation.template(key) is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-LOOP",
                f"unsupported loop<{variant}>: {region.full_text!r}",
            )
            return region.full_text
        block = render(region.block) if region.block else ""
        if variant == "range":
            groups = _split_arg_groups(region.body)
            if len(groups) != 4:
                context.skip(
                    "TSL-LOWER-UNSUPPORTED-LOOP",
                    f"loop<range> needs (var, start, end, step): {region.full_text!r}",
                )
                return region.full_text
            var, start, end, step = (render(group).strip() for group in groups)
            header = context.translation.render_template(
                key, var=var, start=start, end=end, step=step
            )
            return f"{header} {{\n        {block}\n      }}"
        # unroll: a bare hint (no block of its own; it precedes a loop).
        header = context.translation.render_template(key, count=render(region.body).strip())
        return f"{header} {{\n        {block}\n      }}" if region.block else header


class QueryRegionLowerer:
    """``type<generation>(x)`` / ``value<generation>(x)`` in raw expression position ->
    the evaluated query's rendered text. A type resolves to its backend spelling; a
    text/integer value to its literal. This is how generation-time constants are spliced
    into a body, e.g. ``array_type<type<generation>(base::in), value<generation>(...)>``.
    One instance is registered per keyword (``type``/``value``)."""

    def __init__(self, keyword: str, evaluator: QueryEvaluator | None = None) -> None:
        self.keyword = keyword
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        value = self._evaluator.evaluate(region.full_text, context)
        if isinstance(value, TextValue):
            return value.text
        if isinstance(value, TypeValue):
            spelling = context.translation.scalar_spelling(value.type_tag)
            if spelling is not None:
                return spelling
        context.skip(
            "TSL-LOWER-UNRESOLVED-QUERY-REGION",
            f"could not resolve {region.keyword}<...> region: {region.full_text!r}",
        )
        return region.full_text


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
    CastLowerer(),
    CallLowerer(),
    IfGenerationLowerer(),
    AssumeAlignedLowerer(),
    LoopLowerer(),
    QueryRegionLowerer("type"),
    QueryRegionLowerer("value"),
    EmitReturnLowerer(),
)
