"""Cast TSIL region lowerers."""

from __future__ import annotations

from tslc.backend.translation import PointerCastOperand
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.ir.region_syntax import parse_cast_selector, segments_text, split_arg_groups
from tslc.ir.segments import RawText, Region, Segment
from tslc.lane_count import LaneCount
from tslc.lower.context import LoweringSession
from tslc.lower.region_safety import direct_region_safety
from tslc.lower.object_representation import register_object_size
from tslc.lower.queries import QueryEvaluator, TextValue, TypeValue
from tslc.lower.region_handlers.common import _resolve_type_expression
from tslc.lower.region_handlers.protocol import RenderBody
from tslc.target_text import RenderField


class AddressLowerer:
    """``address<of|borrow_mut>(expr)`` -> a backend address expression."""

    keyword = "address"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        args = split_arg_groups(region.body)
        selector = region.selector_text.strip()
        if selector not in {"of", "borrow_mut"} or len(args) != 1:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-ADDRESS",
                f"unsupported address form: {region.full_text!r}",
                source=region.source,
            )
            return region.full_text
        return context.env.backend.syntax.render_address(
            render(args[0]), mutable=selector == "borrow_mut"
        )


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
        context.effects.merge_safety(direct_region_safety(region))
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
                "use a pointer-valued expression or address<of|borrow_mut>(target)",
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
    """Classify pointer operands only from typed TSIL structure."""

    significant = tuple(
        segment
        for segment in group
        if not (isinstance(segment, RawText) and not segment.text.strip())
    )
    if not significant:
        return None
    if (
        len(significant) == 1
        and isinstance(significant[0], Region)
        and significant[0].keyword == "address"
    ):
        address = significant[0]
        args = split_arg_groups(address.body)
        selector = address.selector_text.strip()
        if selector not in {"of", "borrow_mut"} or len(args) != 1:
            return None
        return PointerCastOperand(
            kind="address_of",
            target=render(args[0]),
            mutable_borrow=selector == "borrow_mut",
        )
    return PointerCastOperand(kind="pointer", target=render(group))
