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
    PrimitiveConversionContract,
    conversion_kind_values,
    lane_count_relation_values,
)
from tslc.catalog.semantics import PrimitiveOperation, PrimitiveSemanticContract
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.access import source_span
from tslc.syntax.ast import ParsedPrimitiveDeclaration


KNOWN_CONVERSION_FIELDS = frozenset({"kind", "lane_count"})


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
    if kind is None or lane_count is None:
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
    return PrimitiveConversionContract(
        kind=kind,
        lane_count=lane_count,
        source=source_span(field.source),
        kind_source=member_value_source(members.get("kind")),
        lane_count_source=member_value_source(members.get("lane_count")),
    )


__all__ = ("KNOWN_CONVERSION_FIELDS", "build_conversion_contract")
