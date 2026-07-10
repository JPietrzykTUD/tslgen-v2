"""Control-flow TSIL region lowerers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from tslc.ir.region_syntax import segments_text, split_arg_groups
from tslc.ir.segments import Region, Segment
from tslc.ir.text import skip_string, split_top_level
from tslc.lower.context import LoweringSession
from tslc.lower.generation import evaluate_generation_int_segments
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, literal_text, render_sequence, render_text


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


def _strip_outer_parens(text: str) -> str:
    """Remove balanced parentheses that wrap the *whole* expression, e.g.
    ``( A && B )`` -> ``A && B``. A leading ``(`` that closes before the end
    (``( A ) && B``) is left intact — it isn't wrapping the whole text."""

    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        wraps = True
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(text) - 1:
                    wraps = False
                    break
        if not wraps:
            break
        text = text[1:-1].strip()
    return text


@dataclass(frozen=True, slots=True)
class _RuntimeCondition:
    """Render a runtime condition in statement position.

    Expression atoms stay precedence-safe, but a backend-owned ``if`` wrapper
    does not need the atom's outer guard parentheses around the whole condition.
    """

    content: RenderField

    def render(self, context=None) -> str:
        text = (
            self.content
            if isinstance(self.content, str)
            else self.content.render(context)
        )
        return _strip_outer_parens(text)


class IfLowerer:
    """``if(cond) { ... } [else ...]`` in two modes, by selector:

    - ``if<generation>(cond)`` / ``if<compile>(cond)``: a *generation-time* conditional —
      the condition is evaluated now (against the type being generated) and **only the taken
      branch's statements** are emitted; the output has no ``if<…>`` and no dead branch. The
      two selectors are equivalent (``compile`` reads as a C++ ``if constexpr``); each spec is
      monomorphized per base type, so the predicate is known and splicing is valid in both
      backends — no runtime/constexpr branch is emitted.
    - bare ``if(cond)`` (no selector): a **runtime** conditional, emitted natively as
      ``if (cond) { then } [else { ... } | else if ...]`` — valid verbatim in C++ and
      Rust. The condition/branches are rendered, not evaluated.

    Either way ``else if`` chains nest naturally: ``else_block`` holds a single nested
    ``if`` region that re-dispatches through this same lowerer.
    """

    keyword = "if"
    _SPLICE_SELECTORS = ("generation", "compile")

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        selector = region.selector_text.strip()
        if selector not in self._SPLICE_SELECTORS:
            return self._runtime(region, context, render)

        condition = segments_text(region.body)
        taken = self._evaluate_condition(condition, context)
        if taken is not None:
            # Fully generation-resolvable: splice only the taken branch (no surviving `if`).
            if taken:
                return render(region.block)
            return render(region.else_block) if region.else_block is not None else ""

        # `if<compile>` second half: the predicate has a *symbolic* term (a `generic_params`
        # template param like `!PreserveSign`) that isn't generation-known. Emit a real
        # compile-time branch keeping BOTH arms — C++ `if constexpr` / Rust `if` — with the
        # gen-evaluable leaves folded to literals. (`if<generation>` has no such fallback: an
        # unresolvable generation condition there is still a skip.)
        if selector == "compile":
            rendered = self._render_condition(condition, context)
            if rendered is not None:
                context.effects.mark_composition()
                header = context.env.backend.templates.render_template(
                    "flow_if_static", "if constexpr ({cond})", cond=rendered
                )
                then = render(region.block) if region.block is not None else ""
                out: RenderField = render_sequence(
                    (header, literal_text(" {\n        "), then, literal_text("\n      }"))
                )
                if region.else_block is not None:
                    out = render_sequence(
                        (
                            out,
                            literal_text(" else {\n        "),
                            render(region.else_block),
                            literal_text("\n      }"),
                        )
                    )
                return out

        context.effects.skip(
            "TSL-LOWER-UNRESOLVED-IF-CONDITION",
            f"could not evaluate generation-time condition in {region.full_text!r}",
            source=region.source,
        )
        return region.full_text

    def _runtime(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        """A native runtime ``if``: emit the condition + branches verbatim for the target."""

        context.effects.mark_composition()
        then = render(region.block) if region.block is not None else ""
        header = render_sequence(
            (
                context.env.backend.templates.render_template(
                    "flow_if_runtime",
                    "if ({cond})",
                    cond=_RuntimeCondition(render(region.body)),
                ),
                literal_text(" {\n        "),
            )
        )
        out: RenderField = render_sequence(
            (
                header,
                then,
                literal_text("\n      }"),
            )
        )
        if region.else_block is not None:
            # A bare nested `if` region in else position is an `else if` (no extra braces);
            # any other else body is a plain block.
            if (
                len(region.else_block) == 1
                and isinstance(region.else_block[0], Region)
                and region.else_block[0].keyword == "if"
            ):
                out = render_sequence((out, literal_text(" else "), render(region.else_block)))
            else:
                out = render_sequence(
                    (
                        out,
                        literal_text(" else {\n        "),
                        render(region.else_block),
                        literal_text("\n      }"),
                    )
                )
        return out

    def _evaluate_condition(self, text: str, context: LoweringSession) -> bool | None:
        """Evaluate a generation-time boolean condition. Supports ``||`` / ``&&`` of
        query sub-conditions (``&&`` binds tighter), e.g.
        ``is_same(..., si64) || is_same(..., ui64)``. Returns None if unresolvable."""

        text = _strip_outer_parens(text)
        ors = _split_top_level_op(text, "||")
        if len(ors) > 1:
            results = [self._evaluate_condition(part, context) for part in ors]
            if any(r is True for r in results):  # short-circuit: True dominates ||
                return True
            return None if None in results else False
        ands = _split_top_level_op(text, "&&")
        if len(ands) > 1:
            results = [self._evaluate_condition(part, context) for part in ands]
            if any(r is False for r in results):  # short-circuit: False dominates &&
                return False
            return None if None in results else True
        value = self._evaluator.evaluate(text.strip(), context)
        return value.value if isinstance(value, BoolValue) else None

    def _render_condition(self, text: str, context: LoweringSession) -> str | None:
        """Render a partially-symbolic `if<compile>` predicate as a target expression: each
        leaf is either a generation-time query (folded to ``true``/``false``) or a symbolic
        ``generic_params`` reference (`!PreserveSign`) passed through verbatim. Returns None
        if a leaf is neither (so the caller skips rather than emitting an undefined name)."""

        text = _strip_outer_parens(text)
        ors = _split_top_level_op(text, "||")
        if len(ors) > 1:
            parts = [self._render_condition(part, context) for part in ors]
            return None if None in parts else " || ".join(parts)
        ands = _split_top_level_op(text, "&&")
        if len(ands) > 1:
            parts = [self._render_condition(part, context) for part in ands]
            return None if None in parts else " && ".join(parts)
        leaf = text.strip()
        value = self._evaluator.evaluate(leaf, context)
        if isinstance(value, BoolValue):
            return "true" if value.value else "false"
        if any(
            re.search(rf"\b{re.escape(name)}\b", leaf)
            for name in context.env.generic_param_names
        ):
            return leaf  # a symbolic generic_params predicate; the param is in scope
        return None


class SelectExprLowerer:
    """``select_expr(cond, if_true, if_false)`` -> backend conditional expression."""

    keyword = "select_expr"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        groups = split_arg_groups(region.body)
        if region.selector_text.strip() or len(groups) != 3:
            context.effects.skip(
                "TSL-LOWER-BAD-SELECT-EXPR",
                f"select_expr needs exactly three arguments and no selector: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        condition, if_true, if_false = (render(group) for group in groups)
        return context.env.backend.syntax.render_select_expr(
            condition, if_true, if_false
        )


class AssumeAlignedLowerer:
    """``assume_aligned<N>(ptr)`` -> an aligned-pointer hint. C++ forwards to the static
    core's ``::tsl::assume_aligned<N>(ptr)`` (``std::assume_aligned``); Rust has no stable
    equivalent and the aligned intrinsic already assumes alignment, so it drops to ``ptr``.
    The ``<N>`` selector (e.g. ``value(vector::alignment)``) is query-resolved."""

    keyword = "assume_aligned"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        expr = render(region.body)
        value = self._evaluator.evaluate(region.selector_text.strip(), context)
        if not isinstance(value, TextValue):
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-ASSUME-ALIGNED",
                f"could not resolve alignment in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.syntax.render_assume_aligned(expr, value.as_text())


class LoopLowerer:
    """``loop<backend>`` emits a native target loop; ``loop<generation>`` expands here.

    ``loop<backend>(var, start, end, step) { body }`` renders a target loop.
    ``loop<backend, unroll>(...)`` adds an explicit unroll hint when the backend
    declares one and the trip count is generation-known. ``loop<generation>``
    evaluates integer bounds now, binds ``var`` as a generation-time integer,
    and renders the block once per iteration.
    """

    keyword = "loop"
    _VAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        terms = split_top_level(region.selector_text.strip())
        variant = terms[0] if terms else ""
        if variant == "generation":
            if len(terms) != 1:
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-LOOP",
                    f"unsupported loop selector {region.selector_text!r}: "
                    f"{region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
            return self._generation(region, context, render)

        unroll = "unroll" in terms[1:]
        if variant != "backend" or any(term != "unroll" for term in terms[1:]):
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-LOOP",
                f"unsupported loop selector {region.selector_text!r}: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        key = "loop_backend"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-LOOP",
                f"unsupported loop<{variant}>: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        groups = split_arg_groups(region.body)
        if len(groups) != 4 or region.block is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-LOOP",
                f"loop<backend> needs (var, start, end, step) and a block: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        var, start, end, step = (
            render_text(render(group)).strip() for group in groups
        )
        header = context.env.backend.templates.render_template(
            key, var=var, start=start, end=end, step=step
        )
        block = render(region.block)
        loop = render_sequence(
            (header, literal_text(" {\n        "), block, literal_text("\n      }"))
        )
        if not unroll:
            return loop

        unroll_key = "loop_backend_unroll"
        if context.env.backend.templates.template(unroll_key) is None:
            return loop
        count = self._backend_trip_count(groups, region, context, render)
        if count is None:
            return loop
        hint = context.env.backend.templates.render_template(
            unroll_key, count=str(count)
        )
        return render_sequence((hint, literal_text("\n      "), loop))

    def _backend_trip_count(
        self,
        groups: list[tuple[Segment, ...]],
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> int | None:
        values = tuple(
            evaluate_generation_int_segments(group, context, render)
            for group in groups[1:]
        )
        if any(value is None for value in values):
            return None
        start, end, step = (int(value) for value in values if value is not None)
        if step == 0:
            context.effects.error(
                "TSL-LOWER-BACKEND-LOOP-UNROLL-ZERO-STEP",
                f"loop<backend, unroll> step must not be zero: {region.full_text!r}",
                source=region.source,
            )
            return None
        return len(range(start, end, step))

    def _generation(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        groups = split_arg_groups(region.body)
        if len(groups) != 4 or region.block is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-GENERATION-LOOP",
                f"loop<generation> needs (var, start, end, step) and a block: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        var = segments_text(groups[0])
        if self._VAR.fullmatch(var) is None:
            context.effects.skip(
                "TSL-LOWER-GENERATION-LOOP-BAD-VAR",
                f"loop<generation> variable must be an identifier: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        values = tuple(
            evaluate_generation_int_segments(group, context, render)
            for group in groups[1:]
        )
        if any(value is None for value in values):
            context.effects.skip(
                "TSL-LOWER-GENERATION-LOOP-NON-INTEGER",
                f"loop<generation> bounds must be generation-time integers: "
                f"{region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        start, end, step = (int(value) for value in values if value is not None)
        if step == 0:
            context.effects.error(
                "TSL-LOWER-GENERATION-LOOP-ZERO-STEP",
                f"loop<generation> step must not be zero: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        had_previous = var in context.scope.generation_ints
        previous = context.scope.resolve_generation_int(var)
        parts: list[RenderField] = []
        try:
            for value in range(start, end, step):
                context.scope.bind_generation_int(var, value)
                parts.append(render(region.block))
        finally:
            if had_previous and previous is not None:
                context.scope.bind_generation_int(var, previous)
            else:
                context.scope.unbind_generation_int(var)
        return render_sequence(tuple(parts))

class SwitchLowerer:
    """``switch<compile>(sel) { label => { body } … _ => { body } }`` -> a compile-time multi-way
    selection over the const selector ``sel`` (gather/scatter's ``scale``). The selected arm folds
    at compile time, so each arm can call an intrinsic that needs a *literal* (the scale const):

    - C++: a cascading ``if constexpr (sel == label) { … } else if constexpr (…) … else { … }``.
    - Rust: a ``match sel { label => { … }, _ => { … } }`` (LLVM folds the const match).

    Each arm body renders like any block — ``complete`` inside it becomes the backend's return,
    and every arm returns, so the construct is the function's diverging tail (as with ``if<compile>``).
    The ``_`` arm is the default (the portable fallback loop)."""

    keyword = "switch"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        if region.arms is None:
            context.effects.skip(
                "TSL-LOWER-SWITCH-NO-ARMS",
                f"switch without arms is not supported: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        selector = render_text(render(region.body)).strip()
        selected_label = _selected_switch_label(selector, region.arms)
        if selected_label is None:
            context.effects.mark_composition()
        arms = tuple(
            (
                label,
                (
                    render(body)
                    if selected_label is None or label == selected_label
                    else _render_without_state(context, render, body)
                ),
            )
            for label, body in region.arms
        )
        return context.env.backend.syntax.render_compile_switch(selector, arms)


def _selected_switch_label(
    selector: str, arms: tuple[tuple[str, tuple[Segment, ...]], ...]
) -> str | None:
    labels = tuple(label for label, _body in arms)
    if selector in labels:
        return selector
    return "_" if "_" in labels else None


def _render_without_state(
    context: LoweringSession, render: RenderBody, body: tuple[Segment, ...]
):
    with context.effects.suppress_implementation_state():
        return render(body)
