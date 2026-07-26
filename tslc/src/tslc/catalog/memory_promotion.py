"""Validation and promotion for primitive memory contracts."""

from __future__ import annotations

from tslc.catalog._semantic_promotion_common import (
    closed_members,
    enum_member,
    member_value_source,
)
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    PrimitiveMemoryContract,
    memory_access_values,
    memory_addressing_values,
    memory_operation,
)
from tslc.catalog.semantics import PrimitiveOperation, PrimitiveSemanticContract
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.access import source_span
from tslc.syntax.ast import ParsedPrimitiveDeclaration


KNOWN_MEMORY_FIELDS = frozenset({"access", "addressing"})


def build_memory_contract(
    declaration: ParsedPrimitiveDeclaration,
    semantic: PrimitiveSemanticContract | None,
    diagnostics: list[Diagnostic],
) -> PrimitiveMemoryContract | None:
    fields = declaration.fields_by_name("memory")
    if not fields:
        if semantic is not None and semantic.kind in {
            PrimitiveOperation.LOAD,
            PrimitiveOperation.STORE,
        }:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OPERATION-MISSING-MEMORY",
                    message=(
                        f"operation {semantic.kind.value!r} on primitive "
                        f"{declaration.name!r} requires a memory contract"
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
        KNOWN_MEMORY_FIELDS,
        "memory",
        diagnostics,
    )
    access = enum_member(
        declaration,
        members.get("access"),
        MemoryAccess,
        memory_access_values(),
        "memory access",
        "TSL-CATALOG-MEMORY-ACCESS",
        diagnostics,
    )
    addressing = enum_member(
        declaration,
        members.get("addressing"),
        MemoryAddressing,
        memory_addressing_values(),
        "memory addressing",
        "TSL-CATALOG-MEMORY-ADDRESSING",
        diagnostics,
    )
    if access is None or addressing is None:
        return None
    expected_operation = memory_operation(access)
    if semantic is None or semantic.kind is not expected_operation:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MEMORY-OPERATION",
                message=(
                    f"memory access {access.value!r} on primitive {declaration.name!r} "
                    f"requires operation {expected_operation.value!r}"
                ),
                source=(
                    member_value_source(members.get("access"))
                    or source_span(field.source)
                ),
            )
        )
        return None
    return PrimitiveMemoryContract(
        access=access,
        addressing=addressing,
        source=source_span(field.source),
        access_source=member_value_source(members.get("access")),
        addressing_source=member_value_source(members.get("addressing")),
    )


__all__ = ("KNOWN_MEMORY_FIELDS", "build_memory_contract")
