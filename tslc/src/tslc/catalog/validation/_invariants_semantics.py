"""Cross-declaration invariants for operation, memory, and conversion contracts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable

from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.semantics import OperandRole, PrimitiveSemanticContract
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at


def validate_semantic_contracts(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    by_name: dict[str, list[Primitive]] = defaultdict(list)
    for primitive in catalog.primitives:
        by_name[primitive.name].append(primitive)
    for name, expanded in sorted(by_name.items()):
        declarations = _unique_source_declarations(expanded)
        contracted = tuple(item for item in declarations if item.operation is not None)
        if not contracted:
            continue
        first = contracted[0]
        first_contract = first.operation
        assert first_contract is not None
        for primitive in declarations:
            contract = primitive.operation
            if contract is None:
                diagnostics.append(
                    _mismatch(
                        name,
                        "operation presence",
                        primitive,
                        primitive.source,
                        first,
                        first_contract.source,
                    )
                )
                continue
            if contract.kind is not first_contract.kind:
                diagnostics.append(
                    _mismatch(
                        name,
                        "operation identity",
                        primitive,
                        contract.operation_source or contract.source,
                        first,
                        first_contract.operation_source or first_contract.source,
                    )
                )
                continue
            _validate_operand_roles(
                name,
                primitive,
                contract,
                first,
                first_contract,
                diagnostics,
            )
            _validate_domain_contract(name, primitive, first, "memory", diagnostics)
            _validate_domain_contract(name, primitive, first, "conversion", diagnostics)


def _validate_operand_roles(
    name: str,
    primitive: Primitive,
    contract: PrimitiveSemanticContract,
    first: Primitive,
    first_contract: PrimitiveSemanticContract,
    diagnostics: list[Diagnostic],
) -> None:
    variant_roles = {
        binding.role: binding
        for binding in contract.operand_bindings
        if binding.role not in {OperandRole.CONTROL_MASK, OperandRole.PASS_THROUGH}
    }
    family_roles = {
        binding.role: binding
        for binding in first_contract.operand_bindings
        if binding.role not in {OperandRole.CONTROL_MASK, OperandRole.PASS_THROUGH}
    }
    if variant_roles.keys() != family_roles.keys():
        diagnostics.append(
            _mismatch(
                name,
                "core operand roles",
                primitive,
                contract.operand_roles_source or contract.source,
                first,
                first_contract.operand_roles_source or first_contract.source,
            )
        )
        return
    for role, binding in variant_roles.items():
        first_binding = family_roles[role]
        if _logical_parameter_index(contract, binding.parameter_index) == (
            _logical_parameter_index(first_contract, first_binding.parameter_index)
        ):
            continue
        diagnostics.append(
            _mismatch(
                name,
                f"{role.value!r} operand position",
                primitive,
                binding.source or contract.operand_roles_source,
                first,
                first_binding.source or first_contract.operand_roles_source,
            )
        )


def _logical_parameter_index(
    contract: PrimitiveSemanticContract,
    parameter_index: int,
) -> int:
    control_indexes = {
        binding.parameter_index
        for binding in contract.operand_bindings
        if binding.role is OperandRole.CONTROL_MASK
    }
    return sum(index not in control_indexes for index in range(parameter_index))


def _validate_domain_contract(
    name: str,
    primitive: Primitive,
    first: Primitive,
    field: str,
    diagnostics: list[Diagnostic],
) -> None:
    actual = getattr(primitive, field)
    expected = getattr(first, field)
    if (actual is None) == (expected is None):
        if actual == expected or actual is None:
            return
        # Source spans differ by declaration; compare only semantic enum values.
        if field == "memory" and (
            actual.access,
            actual.addressing,
        ) == (expected.access, expected.addressing):
            return
        if field == "conversion" and (
            actual.kind,
            actual.lane_count,
        ) == (expected.kind, expected.lane_count):
            return
    diagnostics.append(
        _mismatch(
            name,
            f"{field} contract",
            primitive,
            primitive.source if actual is None else actual.source,
            first,
            first.source if expected is None else expected.source,
        )
    )


def _unique_source_declarations(primitives: list[Primitive]) -> tuple[Primitive, ...]:
    unique: dict[Hashable, Primitive] = {}
    for index, primitive in enumerate(primitives):
        key: Hashable = (
            primitive.source
            if primitive.source is not None
            else ("declaration", index)
        )
        unique.setdefault(key, primitive)
    return tuple(unique.values())


def _mismatch(
    name: str,
    fact: str,
    primitive: Primitive,
    source: SourceSpan | None,
    first: Primitive,
    first_source: SourceSpan | None,
) -> Diagnostic:
    related = (
        ()
        if first_source is None
        else (
            RelatedLocation(
                message="family semantic contract starts here",
                span=first_source,
            ),
        )
    )
    return diagnostic_at(
        severity="error",
        code="TSL-CATALOG-INCONSISTENT-OPERATION-FAMILY",
        message=f"primitive family {name!r} has inconsistent {fact}",
        source=source or primitive.source or first.source,
        related=related,
    )


__all__ = ("validate_semantic_contracts",)
