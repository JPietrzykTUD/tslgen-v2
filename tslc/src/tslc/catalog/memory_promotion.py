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
    MemoryPayloadExtent,
    PrimitiveMemoryContract,
    memory_access_values,
    memory_addressing_values,
    memory_operation,
)
from tslc.catalog.semantics import (
    OperandRole,
    PrimitiveOperation,
    PrimitiveSemanticContract,
)
from tslc.catalog.signatures import parse_signature
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
    if not _validate_addressing_roles(
        declaration, semantic, addressing, diagnostics
    ):
        return None
    payload_extent = _payload_extent(
        declaration, semantic, access, addressing, diagnostics
    )
    if payload_extent is None:
        return None
    return PrimitiveMemoryContract(
        access=access,
        addressing=addressing,
        payload_extent=payload_extent,
        source=source_span(field.source),
        access_source=member_value_source(members.get("access")),
        addressing_source=member_value_source(members.get("addressing")),
    )


def _payload_extent(
    declaration: ParsedPrimitiveDeclaration,
    semantic: PrimitiveSemanticContract,
    access: MemoryAccess,
    addressing: MemoryAddressing,
    diagnostics: list[Diagnostic],
) -> MemoryPayloadExtent | None:
    if addressing is MemoryAddressing.COMPACTED:
        return MemoryPayloadExtent.ACTIVE_LANES
    signature = parse_signature(declaration.signature)
    kind: str | None
    if signature is None:
        kind = None
    elif access is MemoryAccess.READ:
        kind = signature.result_kind
    else:
        value = semantic.binding(OperandRole.VALUE)
        kind = None if value is None else value.parameter_kind
    payload_extent = (
        None
        if kind is None
        else {
            "s": MemoryPayloadExtent.SCALAR,
            "v": MemoryPayloadExtent.VECTOR,
        }.get(kind)
    )
    if payload_extent is not None:
        return payload_extent
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-MEMORY-PAYLOAD-EXTENT",
            message=(
                f"memory access {access.value!r} on primitive "
                f"{declaration.name!r} requires a scalar or vector payload"
            ),
            source=source_span(declaration.signature_source),
        )
    )
    return None


def _validate_addressing_roles(
    declaration: ParsedPrimitiveDeclaration,
    semantic: PrimitiveSemanticContract,
    addressing: MemoryAddressing,
    diagnostics: list[Diagnostic],
) -> bool:
    roles = frozenset(binding.role for binding in semantic.operand_bindings)
    required = {
        MemoryAddressing.CONTIGUOUS: frozenset(),
        MemoryAddressing.INDEXED: frozenset(
            {OperandRole.INDEX, OperandRole.SCALE}
        ),
        MemoryAddressing.COMPACTED: frozenset({OperandRole.CONTROL_MASK}),
    }[addressing]
    forbidden = {
        MemoryAddressing.CONTIGUOUS: frozenset(
            {OperandRole.INDEX, OperandRole.SCALE}
        ),
        MemoryAddressing.INDEXED: frozenset(),
        MemoryAddressing.COMPACTED: frozenset(
            {OperandRole.INDEX, OperandRole.SCALE}
        ),
    }[addressing]
    missing = required - roles
    unexpected = forbidden.intersection(roles)
    if not missing and not unexpected:
        return True
    details: list[str] = []
    if missing:
        details.append(
            "requires " + ", ".join(repr(role.value) for role in sorted(missing))
        )
    if unexpected:
        details.append(
            "forbids "
            + ", ".join(repr(role.value) for role in sorted(unexpected))
        )
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-MEMORY-ADDRESSING-ROLES",
            message=(
                f"memory addressing {addressing.value!r} on primitive "
                f"{declaration.name!r} " + "; ".join(details)
            ),
            source=semantic.operand_roles_source or semantic.source,
        )
    )
    return False


__all__ = ("KNOWN_MEMORY_FIELDS", "build_memory_contract")
