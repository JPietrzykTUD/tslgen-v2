"""Validation and promotion for primitive conversion contracts."""

from __future__ import annotations

from tslc.catalog._semantic_promotion_common import (
    closed_members,
    enum_member,
    member_value_source,
)
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
    PrimitiveConversionContract,
    conversion_kind_values,
    lane_count_relation_values,
    numeric_conversion_mode_values,
)
from tslc.catalog.semantics import PrimitiveOperation, PrimitiveSemanticContract
from tslc.catalog.model import RESULT_DIM_VECTOR
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.access import source_span
from tslc.syntax.ast import ParsedPrimitiveDeclaration


KNOWN_CONVERSION_FIELDS = frozenset({"kind", "lane_count", "numeric_mode"})


def build_conversion_contract(
    declaration: ParsedPrimitiveDeclaration,
    semantic: PrimitiveSemanticContract | None,
    result_target: tuple[str, str] | None,
    diagnostics: list[Diagnostic],
) -> PrimitiveConversionContract | None:
    fields = declaration.fields_by_name("conversion")
    conversion_operations = {
        PrimitiveOperation.CONVERT,
        PrimitiveOperation.REINTERPRET,
    }
    if not fields:
        if semantic is not None and semantic.kind in conversion_operations:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OPERATION-MISSING-CONVERSION",
                    message=(
                        f"operation {semantic.kind.value!r} on primitive "
                        f"{declaration.name!r} requires a conversion contract"
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
        KNOWN_CONVERSION_FIELDS,
        "conversion",
        diagnostics,
        required=frozenset({"kind", "lane_count"}),
    )
    kind = enum_member(
        declaration,
        members.get("kind"),
        ConversionKind,
        conversion_kind_values(),
        "conversion kind",
        "TSL-CATALOG-CONVERSION-KIND",
        diagnostics,
    )
    lane_count = enum_member(
        declaration,
        members.get("lane_count"),
        LaneCountRelation,
        lane_count_relation_values(),
        "lane-count relation",
        "TSL-CATALOG-CONVERSION-LANE-COUNT",
        diagnostics,
    )
    numeric_mode = enum_member(
        declaration,
        members.get("numeric_mode"),
        NumericConversionMode,
        numeric_conversion_mode_values(),
        "numeric conversion mode",
        "TSL-CATALOG-CONVERSION-NUMERIC-MODE",
        diagnostics,
    )
    if kind is None or lane_count is None:
        return None
    if numeric_mode is not None and kind is not ConversionKind.NUMERIC:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-CONVERSION-NUMERIC-MODE-KIND",
                message=(
                    f"numeric_mode on primitive {declaration.name!r} requires "
                    "conversion kind 'numeric'"
                ),
                source=member_value_source(members.get("numeric_mode")),
            )
        )
        return None
    expected = {
        ConversionKind.NUMERIC: PrimitiveOperation.CONVERT,
        ConversionKind.BIT_PATTERN: PrimitiveOperation.REINTERPRET,
    }[kind]
    if semantic is None or semantic.kind is not expected:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-CONVERSION-OPERATION",
                message=(
                    f"conversion kind {kind.value!r} on primitive "
                    f"{declaration.name!r} requires operation {expected.value!r}"
                ),
                source=(
                    member_value_source(members.get("kind"))
                    or source_span(field.source)
                ),
            )
        )
        return None
    if result_target is None:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-CONVERSION-MISSING-TARGET",
                message=(
                    f"conversion contract on primitive {declaration.name!r} requires "
                    "an explicit result target"
                ),
                source=source_span(field.source),
            )
        )
        return None
    if (
        lane_count is LaneCountRelation.PRESERVE_LANE_COUNT
        and result_target[0] != RESULT_DIM_VECTOR
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-CONVERSION-LANE-TARGET",
                message=(
                    f"lane-preserving conversion on primitive {declaration.name!r} "
                    "requires an explicit target SIMD type"
                ),
                source=member_value_source(members.get("lane_count")),
            )
        )
        return None
    return PrimitiveConversionContract(
        kind=kind,
        lane_count=lane_count,
        numeric_mode=numeric_mode,
        source=source_span(field.source),
        kind_source=member_value_source(members.get("kind")),
        lane_count_source=member_value_source(members.get("lane_count")),
        numeric_mode_source=member_value_source(members.get("numeric_mode")),
    )


__all__ = ("KNOWN_CONVERSION_FIELDS", "build_conversion_contract")
