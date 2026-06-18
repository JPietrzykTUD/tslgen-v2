"""Control-flow TSIL region lowerers."""

from __future__ import annotations

import re

from tslc.ir.segments import Region
from tslc.lower._text import skip_string
from tslc.lower.context import LoweringSession
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue
from tslc.lower.region_handlers.common import _segment_text, _split_arg_groups
from tslc.lower.region_handlers.protocol import RenderBody

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

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        selector = region.selector_text.strip()
        if selector not in self._SPLICE_SELECTORS:
            return self._runtime(region, render)

        condition = _segment_text(region.body)
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
                header = context.env.backend.templates.render_template(
                    "flow_if_static", "if constexpr ({cond})", cond=rendered
                )
                then = render(region.block) if region.block is not None else ""
                out = f"{header} {{\n        {then}\n      }}"
                if region.else_block is not None:
                    out += f" else {{\n        {render(region.else_block)}\n      }}"
                return out

        context.effects.skip(
            "TSL-LOWER-UNRESOLVED-IF-CONDITION",
            f"could not evaluate generation-time condition in {region.full_text!r}",
        )
        return region.full_text

    def _runtime(self, region: Region, render: RenderBody) -> str:
        """A native runtime ``if``: emit the condition + branches verbatim for the target."""

        then = render(region.block) if region.block is not None else ""
        out = f"if ({render(region.body)}) {{\n        {then}\n      }}"
        if region.else_block is not None:
            # A bare nested `if` region in else position is an `else if` (no extra braces);
            # any other else body is a plain block.
            if (
                len(region.else_block) == 1
                and isinstance(region.else_block[0], Region)
                and region.else_block[0].keyword == "if"
            ):
                out += f" else {render(region.else_block)}"
            else:
                out += f" else {{\n        {render(region.else_block)}\n      }}"
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


class AssumeAlignedLowerer:
    """``assume_aligned<N>(ptr)`` -> an aligned-pointer hint. C++ forwards to the static
    core's ``::tsl::assume_aligned<N>(ptr)`` (``std::assume_aligned``); Rust has no stable
    equivalent and the aligned intrinsic already assumes alignment, so it drops to ``ptr``.
    The ``<N>`` selector (e.g. ``value<generation>(vector::alignment)``) is query-resolved."""

    keyword = "assume_aligned"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        expr = render(region.body)
        value = self._evaluator.evaluate(region.selector_text.strip(), context)
        if not isinstance(value, TextValue):
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-ASSUME-ALIGNED",
                f"could not resolve alignment in {region.full_text!r}",
            )
            return region.full_text
        return context.env.backend.syntax.render_assume_aligned(expr, value.text)


class LoopLowerer:
    """``loop<range>(var, start, end, step) { body }`` / ``loop<unroll>(count)`` -> the
    backend's **native** loop construct (NOT a generation-time unroll): the `loop_range` /
    `loop_unroll` translate template framing the (recursively-rendered) block. C++
    ``for (std::size_t i = 0; i < N; i += 1) { ... }`` / Rust ``for i in (0..N).step_by(1)
    { ... }``; the bound ``value<generation>(vector::length)`` resolves via the query region.
    """

    keyword = "loop"

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        variant = region.selector_text.strip()
        key = f"loop_{variant}"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-LOOP",
                f"unsupported loop<{variant}>: {region.full_text!r}",
            )
            return region.full_text
        block = render(region.block) if region.block else ""
        if variant == "range":
            groups = _split_arg_groups(region.body)
            if len(groups) != 4:
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-LOOP",
                    f"loop<range> needs (var, start, end, step): {region.full_text!r}",
                )
                return region.full_text
            var, start, end, step = (render(group).strip() for group in groups)
            header = context.env.backend.templates.render_template(
                key, var=var, start=start, end=end, step=step
            )
            return f"{header} {{\n        {block}\n      }}"
        # unroll: a bare hint (no block of its own; it precedes a loop).
        header = context.env.backend.templates.render_template(
            key, count=render(region.body).strip()
        )
        return f"{header} {{\n        {block}\n      }}" if region.block else header

class SwitchLowerer:
    """``switch<compile>(sel) { label => { body } … _ => { body } }`` -> a compile-time multi-way
    selection over the const selector ``sel`` (gather/scatter's ``scale``). The selected arm folds
    at compile time, so each arm can call an intrinsic that needs a *literal* (the scale const):

    - C++: a cascading ``if constexpr (sel == label) { … } else if constexpr (…) … else { … }``.
    - Rust: a ``match sel { label => { … }, _ => { … } }`` (LLVM folds the const match).

    Each arm body renders like any block — ``emit_return`` inside it becomes the backend's return,
    and every arm returns, so the construct is the function's diverging tail (as with ``if<compile>``).
    The ``_`` arm is the default (the portable fallback loop)."""

    keyword = "switch"

    def lower(self, region: Region, context: LoweringSession, render: RenderBody) -> str:
        if region.arms is None:
            context.effects.skip(
                "TSL-LOWER-SWITCH-NO-ARMS",
                f"switch without arms is not supported: {region.full_text!r}",
            )
            return region.full_text
        selector = render(region.body).strip()
        arms = tuple((label, render(body)) for label, body in region.arms)
        return context.env.backend.syntax.render_compile_switch(selector, arms)
