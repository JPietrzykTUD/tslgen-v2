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
        # Const-generic intrinsic forward: a Rust immediate intrinsic takes the count as a
        # const generic (`_mm256_slli_epi32::<SHIFT>(a)`), not a runtime arg. When the
        # primitive's immediate uses `rust_const_match`, lift the arg that names the
        # immediate out of the call and into the turbofish. (C++ takes it as a normal arg —
        # a compile-time-constant template param converts implicitly.)
        forwarded = self._forward_immediate(region, context, render)
        if forwarded is not None:
            turbofish, rest = forwarded
            return f"{name}::<{turbofish}>({rest})"
        return f"{name}({render(region.body)})"

    def _forward_immediate(
        self, region: Region, context: LoweringContext, render: RenderBody
    ) -> tuple[str, str] | None:
        """If this is a Rust `rust_const_match` immediate intrinsic, split the rendered
        args into (immediate-for-turbofish, remaining-args). Returns None otherwise."""

        if (
            context.translation.backend_id != "rust"
            or context.immediate_dispatch != "rust_const_match"
            or context.immediate_name is None
        ):
            return None
        groups = _split_arg_groups(region.body)
        imm: str | None = None
        rest: list[str] = []
        for group in groups:
            rendered = render(group).strip()
            if rendered == context.immediate_name:
                imm = rendered
            else:
                rest.append(rendered)
        if imm is None:
            return None
        return (imm, ", ".join(rest))

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

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        variant = region.selector_text.strip()
        groups = _split_arg_groups(region.body)
        if variant != "type" or len(groups) != 2:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-LET",
                f"unsupported let<{variant}>: {region.full_text!r}",
            )
            return region.full_text
        context.type_aliases[render(groups[0]).strip()] = render(groups[1]).strip()
        return ""


class MaskLowerer:
    """``mask<zero>() / mask<set:1|0>(m,i) / mask<set>(m,i,v) / mask<test>(m,i)`` -> mask-bit
    ops, lowered per the extension's mask **representation** via a backend translate template
    keyed by `mask_<op>_<repr>` (so literal/`&mut` differences stay in the translate layer).
    Currently the integer-bitset repr (`lane_bitmask`, used by the generic vector's emulated
    masks) is templated; native `__mmask`/register reprs register their own keys later. (Only
    the emulated/generic bodies use `mask<…>` — native bodies use intrinsics — so the bitset
    templates are reached only for the generic vector.)"""

    keyword = "mask"

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
        op, _, bit = region.selector_text.strip().partition(":")
        repr_kind = context.extension.mask_policy.kind
        args = [render(group).strip() for group in _split_arg_groups(region.body) if render(group).strip()]
        if op == "zero":
            key, fields = f"mask_zero_{repr_kind}", {}
        elif op == "test" and len(args) == 2:
            key, fields = f"mask_test_{repr_kind}", {"mask": args[0], "index": args[1]}
        elif op == "set" and bit == "1" and len(args) == 2:
            key, fields = f"mask_set_{repr_kind}", {"name": args[0], "index": args[1]}
        elif op == "set" and bit == "0" and len(args) == 2:
            key, fields = f"mask_clear_{repr_kind}", {"name": args[0], "index": args[1]}
        elif op == "set" and not bit and len(args) == 3:
            key = f"mask_set_to_{repr_kind}"
            fields = {"name": args[0], "index": args[1], "value": args[2]}
        else:
            key, fields = "", {}
        if not key or context.translation.template(key) is None:
            context.skip(
                "TSL-LOWER-UNSUPPORTED-MASK",
                f"unsupported mask<{region.selector_text.strip()}> for {repr_kind!r}: "
                f"{region.full_text!r}",
            )
            return region.full_text
        return context.translation.render_template(key, **fields)


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
    _NAME = re.compile(r"(@?[A-Za-z_]\w*)")

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

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
        # `@self` is a recursive call into the primitive currently being lowered.
        if name == "@self":
            name = context.current_primitive

        type_args, rest = _take_bracket(rest)
        # The bracket is a comma-separated list: entry 0 is the target vector (the plain `[Vec]` /
        # no-arg form targets the current vector; any other type-expression — e.g.
        # `vector::as_extension(scalar)` — names the vector to call), and entries 1.. are extra
        # template/const-generic args forwarded into the callee's wrapper (e.g.
        # `@self[GenericVec, shift, PreserveSign]` delegating with the in-scope immediate + param).
        entries = split_top_level(type_args, ",") if type_args else []
        vec_override: str | None = None
        if entries and entries[0] != "Vec":
            value = self._evaluator.evaluate(entries[0], context)
            if not isinstance(value, TextValue):
                context.skip(
                    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
                    f"call type-args {type_args!r} not supported yet: {region.full_text!r}",
                )
                return region.full_text
            vec_override = value.text
        extra_args: list[str] = []
        for entry in entries[1:]:
            rendered = self._render_call_arg(entry, context)
            if rendered is None:
                context.skip(
                    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
                    f"call type-args {type_args!r} not supported yet: {region.full_text!r}",
                )
                return region.full_text
            extra_args.append(rendered)

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
            vec_override,
            tuple(extra_args),
        )

    def _render_call_arg(self, entry: str, context: LoweringContext) -> str | None:
        """A forwarded call-bracket arg (entries 1..) as a target template/const-generic arg:
        a query that resolves to a `TextValue` spelling, or a bare `generic_params` name (e.g.
        `PreserveSign`) passed through verbatim. Returns None when it is neither (so the caller
        skips).

        Forwarding the *immediate* itself (`@self[…, shift, …]`) is deferred: it would target the
        callee's `_imm` split (not the current `@self` name) and cross the per-ISA immediate type
        (e.g. avx2 `i32` into a generic/scalar `u32` slot). Such an entry returns None → skip.

        In-scope param names are matched *before* query evaluation (the evaluator passes a bare
        token through as a `TextValue`, which would otherwise mask the immediate-skip)."""

        if entry == context.immediate_name:
            return None
        if any(
            re.search(rf"\b{re.escape(name)}\b", entry) for name in context.generic_param_names
        ):
            return entry
        value = self._evaluator.evaluate(entry, context)
        if isinstance(value, TextValue):
            return value.text
        return None


def _take_bracket(text: str) -> tuple[str, str]:
    """If ``text`` starts with ``[...]``, return ``(inside, remainder)``; else ``("", text)``."""

    text = text.lstrip()
    if not text.startswith("["):
        return "", text
    close = text.find("]")
    if close == -1:
        return "", text
    return text[1:close].strip(), text[close + 1 :].lstrip()


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

    def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str:
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
                header = context.translation.render_template(
                    "flow_if_static", "if constexpr ({cond})", cond=rendered
                )
                then = render(region.block) if region.block is not None else ""
                out = f"{header} {{\n        {then}\n      }}"
                if region.else_block is not None:
                    out += f" else {{\n        {render(region.else_block)}\n      }}"
                return out

        context.skip(
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

    def _evaluate_condition(self, text: str, context: LoweringContext) -> bool | None:
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

    def _render_condition(self, text: str, context: LoweringContext) -> str | None:
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
            for name in context.generic_param_names
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
    LetLowerer(),
    MaskLowerer(),
    CastLowerer(),
    CallLowerer(),
    IfLowerer(),
    AssumeAlignedLowerer(),
    LoopLowerer(),
    QueryRegionLowerer("type"),
    QueryRegionLowerer("value"),
    EmitReturnLowerer(),
)
