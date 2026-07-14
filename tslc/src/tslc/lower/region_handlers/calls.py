"""Primitive-call TSIL region lowerers."""

from __future__ import annotations

import re

from tslc.catalog.model import Extension
from tslc.ir.region_syntax import parse_call_selector, split_arg_groups
from tslc.ir.segments import Region
from tslc.lower.context import LoweringSession, VectorValue
from tslc.lower.dependencies import (
    CallDependencyOrigin,
    VectorIdentity,
    resolve_lowered_call_vector,
    resolve_lowered_call_dependency,
)
from tslc.lower.queries import BoolValue, QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.common import _vector_spelling
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField, as_render_text, literal_text, render_sequence, render_text, unsafe_block

_DECIMAL_INTEGER = re.compile(r"^[0-9]+$")


class CallLowerer:
    """``call<primitive=NAME[Vec], attrs[aligned=…]>(args)`` -> a call to NAME's wrapper.

    Primitives are generated independently; this only renders the *call* (via
    ``backend.syntax.render_call``), it does not inline NAME's body. The selector shape is parsed by
    :func:`tslc.ir.region_syntax.parse_call_selector`; this lowerer owns only rendering decisions.

    A callee carrying a boolean-wildcard axis (e.g. ``store``/``load`` with ``aligned``)
    needs that axis passed at the call site: C++ could default it, but Rust const-generics
    can't be inferred when ambiguous. The value comes from the call's ``attrs[...]``
    (default ``false``); which axis keys a callee has comes from ``context.env.primitive_axes``.
    """

    keyword = "call"

    def __init__(self, evaluator: QueryEvaluator | None = None) -> None:
        self._evaluator = evaluator or QueryEvaluator()

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        parsed = parse_call_selector(region.selector_text)
        if parsed is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CALL",
                f"unsupported call: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        name = parsed.primitive_ref
        # `@self` is a recursive call into the primitive currently being lowered.
        if name == "@self":
            name = context.env.current_primitive

        # The bracket is a comma-separated list: entry 0 is the target vector (the plain `[Vec]` /
        # no-arg form targets the current vector; any other type-expression — e.g.
        # `vector::as_extension(scalar)` — names the vector to call), and entries 1.. are extra
        # template/const-generic args forwarded into the callee's wrapper (e.g.
        # `@self[GenericVec, shift, PreserveSign]` delegating with the in-scope immediate + param).
        entries = list(parsed.type_args)
        source_identity = (
            resolve_lowered_call_vector(entries[0], context, self._evaluator)
            if entries
            else None
        ) or VectorIdentity(
            context.env.type_tag, context.env.extension.isa_name
        )
        immediate_forwarded = (
            context.env.immediate_name is not None
            and context.env.immediate_name in entries[1:]
        )
        vec_override: str | None = None
        if entries and entries[0] != "Vec":
            vec_override = self._resolve_vec_expr(entries[0], context)
            if vec_override is None:
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
                    f"call type-args {parsed.type_args!r} not supported yet: {region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
        extra_args: list[str] = []
        for entry in entries[1:]:
            rendered = self._render_call_arg(entry, context, source_identity)
            if rendered is None:
                context.effects.skip(
                    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS",
                    f"call type-args {parsed.type_args!r} not supported yet: {region.full_text!r}",
                    source=region.source,
                )
                return region.full_text
            extra_args.append(rendered)

        attrs = {
            key: self._resolve_attr_value(value, context) for key, value in parsed.attrs
        }
        context.effects.record_call_dependency(
            CallDependencyOrigin(
                resolve_lowered_call_dependency(
                    parsed,
                    context,
                    self._evaluator,
                    mask_policy=attrs.get("mask"),
                ),
                context.env.dependency_origin,
            )
        )

        # A `attrs[mask=…]` call to a policy-split name targets its `_mask`/`_maskz` split (the
        # render rename); single-form callees (`blend`) aren't in the set and stay bare.
        call_name = name
        if attrs.get("mask") and name in context.env.policy_split_names:
            call_name = f"{name}{context.env.support.mask_suffix(attrs['mask'])}"
        # Forwarding the caller's compile-time immediate targets an `_imm` wrapper only for
        # callees whose emitted callable family actually splits runtime and `sImm` forms. Pure
        # `sImm` callees such as `insert` and `extract` keep their authored name.
        if immediate_forwarded and name in context.env.immediate_split_names:
            call_name = f"{call_name}_imm"
        axis_values = tuple(
            attrs.get(key, "false") for key in context.env.primitive_axes.get(name, ())
        )
        call = context.env.backend.syntax.render_call(
            call_name,
            self._render_call_args(region, context, render, name),
            axis_values,
            context.env.primitive_arg_generics.get(call_name, 0),
            vec_override,
            tuple(extra_args),
        )
        if context.env.primitive_caller_unsafe.get(name, False):
            return unsafe_block(call)
        return call

    def _render_call_args(
        self,
        region: Region,
        context: LoweringSession,
        render: RenderBody,
        primitive_name: str,
    ) -> RenderField:
        borrowed = context.env.primitive_borrowed_arg_positions.get(primitive_name, ())
        prefix = context.env.backend.syntax.borrowed_call_arg_prefix
        if prefix is None or not borrowed:
            return render(region.body)
        groups = split_arg_groups(region.body)
        borrowed_positions = set(borrowed)
        parts: list[RenderField] = []
        for index, group in enumerate(groups):
            if parts:
                parts.append(literal_text(", "))
            value = render(group)
            if index in borrowed_positions:
                value = render_sequence((literal_text(prefix), as_render_text(value)))
            parts.append(value)
        return render_sequence(tuple(as_render_text(part) for part in parts))

    def _resolve_attr_value(self, value: str, context: LoweringSession) -> str:
        """An `attrs[key=value]` value. A literal (`false`) passes through; a generation query
        — `value(primitive::attribute(aligned))`, used by masked `load`/`store` to
        forward the caller's `aligned` to the delegated unmasked op — is evaluated to its literal
        so it doesn't leak unlowered into the emitted call."""

        if "<" not in value and "::" not in value:
            return value
        resolved = self._evaluator.evaluate(value, context)
        if isinstance(resolved, TextValue):
            return resolved.as_text()
        if isinstance(resolved, BoolValue):
            return "true" if resolved.value else "false"
        return value

    def _render_call_arg(
        self,
        entry: str,
        context: LoweringSession,
        source: VectorIdentity,
    ) -> str | None:
        """A forwarded call-bracket arg (entries 1..) as a target template/const-generic arg:
        a query that resolves to a `TextValue` spelling, or a bare `generic_params` name (e.g.
        `PreserveSign`) passed through verbatim. Returns None when it is neither (so the caller
        skips).

        Forwarding the *immediate* (`@self[…, shift, …]`) passes it through verbatim — it is in
        scope as the `_imm` form's template / const-generic param (the caller appends `_imm` to
        the callee; see `lower()`), so it threads straight into the callee's turbofish.

        A `Vec<X>` entry (a representation-change target, e.g. `reinterpret[Vec, Vec<UnsignedT>]`)
        resolves to the target vector spelling. In-scope param names are matched *before* query
        evaluation (the evaluator passes a bare token through as a `TextValue`)."""

        if entry.startswith("Vec<") and entry.endswith(">"):
            return self._resolve_vec_expr(entry, context)
        # A bare `Vec` target (`reinterpret[Vec<UnsignedT>, Vec]`) is the current vector — spell
        # it concretely (Rust has no `Vec` alias, and an arg-trait `Self` is the argument type).
        if entry == "Vec":
            base = context.env.backend.types.scalar_spelling(context.env.type_tag)
            return (
                _vector_type_for_extension(base, context.env.extension, context)
                if base is not None
                else None
            )
        if entry == context.env.immediate_name:
            return entry
        if _DECIMAL_INTEGER.match(entry):
            return entry
        if any(
            re.search(rf"\b{re.escape(name)}\b", entry)
            for name in context.env.generic_param_names
        ):
            return entry
        extension = context.env.catalog.extensions.get(entry)
        if extension is not None:
            base = context.env.backend.types.scalar_spelling(source.base_tag)
            return (
                _vector_type_for_extension(base, extension, context)
                if base is not None
                else None
            )
        value = self._evaluator.evaluate(entry, context)
        if isinstance(value, TextValue):
            return value.as_text()
        # A base tag (`cast[Vec, ToBase]`'s `ToBase`) -> the target vector (`ToVec`) the cast/convert
        # wrapper takes as its second type param: `simd<ToBase, current_ext>`.
        if isinstance(value, TypeValue):
            base = context.env.backend.types.scalar_spelling(value.type_tag)
            extension = next(
                (
                    candidate
                    for candidate in context.env.catalog.extensions.values()
                    if candidate.isa_name == source.extension_isa
                ),
                None,
            )
            return (
                _vector_type_for_extension(base, extension, context)
                if base is not None and extension is not None
                else None
            )
        if isinstance(value, VectorValue):  # an already-vector target -> its spelling
            return _vector_spelling(value, context)
        return None

    def _resolve_vec_expr(self, entry: str, context: LoweringSession) -> str | None:
        """A call-bracket vector expression -> its backend `simd<…>` spelling. `Vec<X>` is the
        current vector with base replaced by the type `X` (`Vec<UnsignedT>` -> the same-extension
        unsigned sibling); any other expression is a query resolving to a vector `TextValue`
        (e.g. `vector::as_extension(scalar)`). None if unresolvable."""

        entry = entry.strip()
        if entry.startswith("Vec<") and entry.endswith(">"):
            inner = entry[len("Vec<") : -1].strip()
            # `inner` is either a `let<type>` alias (its recorded spelling is the base) or a
            # type expression that evaluates to a tag (-> its scalar spelling).
            if inner in context.scope.type_aliases:
                base: str | None = render_text(context.scope.type_aliases[inner])
            else:
                value = self._evaluator.evaluate(inner, context)
                base = (
                    context.env.backend.types.scalar_spelling(value.type_tag)
                    if isinstance(value, TypeValue)
                    else None
                )
            if base is None:
                return None
            return _vector_type_for_extension(base, context.env.extension, context)
        if entry in context.env.simd_type_param_names:
            return entry
        value = self._evaluator.evaluate(entry, context)
        if isinstance(value, TextValue):  # a query resolving to a vector spelling
            return value.as_text()
        if isinstance(value, VectorValue):  # a `let<type>` vector alias (`InVec`) -> its spelling
            return _vector_spelling(value, context)
        return None


def _vector_type_for_extension(
    base_spelling: str,
    extension: Extension,
    context: LoweringSession,
) -> str:
    if context.env.support.uses_sized_vector(extension):
        lanes = (
            context.env.lane_symbol()
            if extension.isa_name == context.env.extension.isa_name
            else context.env.support.size_parameter_name(extension)
        )
        return context.env.backend.types.sized_vector_spelling(
            base_spelling, extension.isa_name, lanes
        )
    return context.env.backend.types.vector_type_spelling(
        base_spelling, extension.isa_name
    )
