"""Validation and promotion for primitive shift contracts."""

from __future__ import annotations

from collections import Counter

from tslc.catalog._semantic_promotion_common import (
    closed_members,
    enum_member,
    member_value_source,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import PrimitiveOperation, PrimitiveSemanticContract
from tslc.catalog.shift import (
    PrimitiveShiftContract,
    ShiftCountRule,
    ShiftLaneRule,
    shift_count_rule_values,
    shift_lane_rule_values,
)
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.access import list_text, source_span
from tslc.syntax.ast import ParsedPrimitiveDeclaration, ParsedTslField


KNOWN_SHIFT_FIELDS = frozenset(
    {"count_rule", "lane_rule", "scalar_count_types"}
)
_WRAPPING_SHIFT_OPERATIONS = frozenset(
    {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }
)
_EXPECTED_LANE_RULE = {
    PrimitiveOperation.SHIFT_LEFT_WRAPPING: ShiftLaneRule.UNSIGNED_BIT_PATTERN_LEFT,
    PrimitiveOperation.SHIFT_RIGHT_WRAPPING: (
        ShiftLaneRule.SIGNED_ARITHMETIC_UNSIGNED_LOGICAL_RIGHT
    ),
}


def build_shift_contract(
    declaration: ParsedPrimitiveDeclaration,
    semantic: PrimitiveSemanticContract | None,
    diagnostics: list[Diagnostic],
) -> PrimitiveShiftContract | None:
    fields = declaration.fields_by_name("shift")
    if not fields:
        if semantic is not None and semantic.kind in _WRAPPING_SHIFT_OPERATIONS:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OPERATION-MISSING-SHIFT",
                    message=(
                        f"operation {semantic.kind.value!r} on primitive "
                        f"{declaration.name!r} requires a shift contract"
                    ),
                    source=semantic.operation_source or semantic.source,
                )
            )
        return None
    if len(fields) != 1:
        return None
    field = fields[0].field
    members = closed_members(
        declaration,
        field,
        KNOWN_SHIFT_FIELDS,
        "shift",
        diagnostics,
    )
    count_rule = enum_member(
        declaration,
        members.get("count_rule"),
        ShiftCountRule,
        shift_count_rule_values(),
        "shift count rule",
        "TSL-CATALOG-SHIFT-COUNT-RULE",
        diagnostics,
    )
    lane_rule = enum_member(
        declaration,
        members.get("lane_rule"),
        ShiftLaneRule,
        shift_lane_rule_values(),
        "shift lane rule",
        "TSL-CATALOG-SHIFT-LANE-RULE",
        diagnostics,
    )
    scalar_types_field = members.get("scalar_count_types")
    scalar_count_types = (
        () if scalar_types_field is None else list_text(scalar_types_field)
    )
    _validate_scalar_count_types(
        declaration,
        scalar_types_field,
        scalar_count_types,
        diagnostics,
    )
    if count_rule is None or lane_rule is None or not scalar_count_types:
        return None
    if semantic is None or semantic.kind not in _WRAPPING_SHIFT_OPERATIONS:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-SHIFT-OPERATION",
                message=(
                    f"shift contract on primitive {declaration.name!r} requires a "
                    "wrapping shift operation"
                ),
                source=source_span(field.source),
            )
        )
        return None
    expected_lane_rule = _EXPECTED_LANE_RULE[semantic.kind]
    if lane_rule is not expected_lane_rule:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-SHIFT-LANE-RULE-OPERATION",
                message=(
                    f"operation {semantic.kind.value!r} on primitive "
                    f"{declaration.name!r} requires lane rule "
                    f"{expected_lane_rule.value!r}"
                ),
                source=(
                    member_value_source(members.get("lane_rule"))
                    or source_span(field.source)
                ),
            )
        )
        return None
    return PrimitiveShiftContract(
        count_rule=count_rule,
        lane_rule=lane_rule,
        scalar_count_types=scalar_count_types,
        source=source_span(field.source),
        count_rule_source=member_value_source(members.get("count_rule")),
        lane_rule_source=member_value_source(members.get("lane_rule")),
        scalar_count_types_source=(
            None
            if scalar_types_field is None
            else source_span(scalar_types_field.source)
        ),
    )


def _validate_scalar_count_types(
    declaration: ParsedPrimitiveDeclaration,
    field: ParsedTslField | None,
    values: tuple[str, ...],
    diagnostics: list[Diagnostic],
) -> None:
    if field is None:
        return
    if not values:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-SHIFT-SCALAR-COUNT-TYPES",
                message=(
                    f"shift contract on primitive {declaration.name!r} requires "
                    "at least one scalar count type"
                ),
                source=source_span(field.source),
            )
        )
        return
    counts = Counter(values)
    for value in values:
        info = SCALAR_TYPE_INFOS.get(value)
        if info is None or info.floating:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-SHIFT-SCALAR-COUNT-TYPE",
                    message=(
                        f"shift contract on primitive {declaration.name!r} has "
                        f"non-integer scalar count type {value!r}"
                    ),
                    source=source_span(field.source),
                )
            )
    duplicates = tuple(sorted(value for value, count in counts.items() if count > 1))
    if duplicates:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-SHIFT-DUPLICATE-SCALAR-COUNT-TYPE",
                message=(
                    f"shift contract on primitive {declaration.name!r} repeats scalar "
                    f"count types {', '.join(repr(value) for value in duplicates)}"
                ),
                source=source_span(field.source),
            )
        )


__all__ = ("KNOWN_SHIFT_FIELDS", "build_shift_contract")
