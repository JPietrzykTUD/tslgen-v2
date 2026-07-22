"""Cast TSIL region lowerers."""

from __future__ import annotations

from tslc.backend.translation import PointerCastOperand
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.ir.region_syntax import parse_cast_selector, segments_text, split_arg_groups
from tslc.ir.segments import RawText, Region, Segment
from tslc.lane_count import LaneCount
from tslc.lower.context import LoweringSession
from tslc.lower.object_representation import register_object_size
from tslc.lower.queries import QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.common import _resolve_type_expression
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField


class CastLowerer:
    """``cast<variant>(type-expr, expr)`` -> the backend's cast template.

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
                value_group=args[1],
                render=render,
            )

        if type_text.rstrip().endswith("*"):
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                (
                    "legacy pointer cast syntax is unsupported; use "
                    "cast<reinterpret, type=ptr|const_ptr>"
                ),
                source=region.source,
            )
            return region.full_text

        key = f"cast_{selector.variant}"
        if context.env.backend.templates.template(key) is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported cast: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text

        resolved = _resolve_type_expression(type_text, context, self._evaluator)
        if resolved is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve cast type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        if selector.variant == "bitcast" and not _valid_bitcast_target(
            resolved[0], context, region
        ):
            return region.full_text
        if selector.variant == "reinterpret":
            # Value reinterpretation is deliberately distinct from a pointer
            # cast and from the checked bitcast path. The implementation leaf
            # owns the concrete pair; lowering records its unsafe boundary so
            # Rust frames the generated call even if source safety metadata is
            # accidentally incomplete.
            context.effects.mark_internal_unsafe("value_reinterpretation")
        return context.env.backend.templates.render_template(
            key, type=resolved[1], expr=render(args[1])
        )

    def _pointer_cast(
        self,
        type_text: str,
        *,
        is_const: bool,
        region: Region,
        context: LoweringSession,
        value_group: tuple[Segment, ...],
        render: RenderBody,
    ) -> RenderField:
        """``cast<reinterpret, type=ptr|const_ptr>(type-expr, ptr)`` -> pointer cast."""

        resolved = _resolve_type_expression(type_text, context, self._evaluator)
        if resolved is None:
            context.effects.skip(
                "TSL-LOWER-UNRESOLVED-CAST-TYPE",
                f"could not resolve pointer cast type in {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        operand = _classify_pointer_operand(value_group, render)
        if operand is None:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-CAST",
                f"unsupported pointer-cast operand form in {region.full_text!r}; "
                "use a pointer-valued expression, &target, or &mut target",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.syntax.render_pointer_cast(
            resolved[1], is_const=is_const, operand=operand
        )


def _valid_bitcast_target(
    target: object,
    context: LoweringSession,
    region: Region,
) -> bool:
    """Validate the safe bitcast destination from typed query facts.

    The source expression language is intentionally not a target-language AST.
    Its expected size is therefore the selected scalar width for scalar targets
    and the selected register width for register targets. Rust additionally
    constrains the concrete destination with its generated ``ValidBitPattern``
    marker before the local unsafe copy can compile.
    """

    if isinstance(target, TypeValue):
        source_bits = scalar_bit_width(context.env.type_tag)
        target_bits = scalar_bit_width(target.type_tag)
        valid = source_bits is not None and source_bits == target_bits
    elif isinstance(target, TextValue):
        uses_sized_vector = context.env.support.uses_sized_vector(
            context.env.extension
        )
        lane_count = (
            LaneCount.fixed(context.env.concrete_lanes)
            if context.env.concrete_lanes is not None
            else LaneCount.symbolic(context.env.lane_symbol())
        )
        source_size = register_object_size(
            context.env.type_tag,
            context.env.extension,
            uses_sized_vector=uses_sized_vector,
            lane_count=lane_count,
        )
        valid = (
            target.all_bit_patterns_valid
            and target.object_size is not None
            and source_size is not None
            and target.object_size.same_size_as(source_size)
        )
    else:
        valid = False
    if valid:
        return True
    context.effects.error(
        "TSL-LOWER-INVALID-BITCAST",
        "safe bitcast requires a compiler-known, same-sized destination whose "
        "bit patterns are all valid",
        source=region.source,
    )
    return False


def _classify_pointer_operand(
    group: tuple[Segment, ...], render: RenderBody
) -> PointerCastOperand | None:
    """Classify the exact source form of a pointer-cast value operand.

    A leading ``&`` / ``&mut`` in raw text is an address-of whose target is the
    remainder of the operand; anything else is an already-pointer-valued
    expression. Returns ``None`` for unsupported address forms (``&&x``, a bare
    ``&``) so the caller diagnoses instead of guessing.
    """

    segments = list(group)
    index = 0
    while index < len(segments):
        candidate = segments[index]
        if not (isinstance(candidate, RawText) and not candidate.text.strip()):
            break
        index += 1
    if index >= len(segments):
        return None
    first = segments[index]
    if not isinstance(first, RawText) or not first.text.lstrip().startswith("&"):
        return PointerCastOperand(
            kind="pointer", target=render(tuple(segments[index:]))
        )
    text = first.text.lstrip()
    if text.startswith("&&"):
        return None
    rest = text[1:].lstrip()
    mutable = False
    if rest.startswith("mut") and not (
        len(rest) > 3 and (rest[3].isalnum() or rest[3] == "_")
    ):
        mutable = True
        rest = rest[3:].lstrip()
    remainder: tuple[Segment, ...]
    if rest:
        remainder = (RawText(rest, source=first.source), *segments[index + 1 :])
    else:
        remainder = tuple(segments[index + 1 :])
    if not remainder:
        return None
    return PointerCastOperand(
        kind="address_of", target=render(remainder), mutable_borrow=mutable
    )
