"""Cross-declaration and type-domain invariants for arithmetic contracts."""

from __future__ import annotations

from collections.abc import Hashable

from tslc.catalog.arithmetic import (
    ARITHMETIC_GUARANTEE_SPECS,
    ArithmeticGuarantee,
    ArithmeticNumericDomain,
    ArithmeticOperandRole,
)
from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS, ScalarTypeInfo
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at


def validate_arithmetic_contracts(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    families: dict[str, list[Primitive]] = {}
    for primitive in catalog.primitives:
        families.setdefault(primitive.name, []).append(primitive)

    for name in sorted(families):
        declarations = _unique_source_declarations(families[name])
        for primitive in declarations:
            _validate_failure_cases(primitive, diagnostics)
        annotated = tuple(
            primitive for primitive in declarations if primitive.arithmetic is not None
        )
        if not annotated:
            continue
        first = annotated[0]
        first_contract = first.arithmetic
        assert first_contract is not None
        for primitive in declarations:
            contract = primitive.arithmetic
            if contract is None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-ARITHMETIC-MISSING-MEMBER",
                        message=(
                            f"primitive family {name!r} mixes declarations with and "
                            "without an arithmetic contract"
                        ),
                        source=primitive.header_source or primitive.source,
                        related=_related(
                            "annotated family member is here",
                            first_contract.source or first.source,
                        ),
                    )
                )
                continue
            if contract.operations != first_contract.operations:
                diagnostics.append(
                    _family_mismatch(
                        name,
                        "operation sets",
                        primitive,
                        contract.operations_source or contract.source,
                        first,
                        first_contract.operations_source or first_contract.source,
                    )
                )
            if contract.family_operand_identity != first_contract.family_operand_identity:
                binding_source = next(
                    (
                        binding.parameter_source or binding.source
                        for binding in contract.operand_bindings
                    ),
                    contract.source,
                )
                first_binding_source = next(
                    (
                        binding.parameter_source or binding.source
                        for binding in first_contract.operand_bindings
                    ),
                    first_contract.source,
                )
                diagnostics.append(
                    _family_mismatch(
                        name,
                        "operand-role bindings",
                        primitive,
                        binding_source,
                        first,
                        first_binding_source,
                    )
                )
            if contract.non_mask_guarantees != first_contract.non_mask_guarantees:
                diagnostics.append(
                    _family_mismatch(
                        name,
                        "non-mask guarantee sets",
                        primitive,
                        contract.guarantees_source or contract.source,
                        first,
                        first_contract.guarantees_source or first_contract.source,
                    )
                )
            _validate_domains(catalog, primitive, diagnostics)


def _validate_failure_cases(
    primitive: Primitive,
    diagnostics: list[Diagnostic],
) -> None:
    for case in primitive.tests:
        if case.role not in {"runtime_failure", "compile_failure"}:
            continue
        contract = primitive.arithmetic
        source = case.failure_source or case.source or primitive.source
        if contract is None or not contract.has_guarantee(
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-FAILURE-CONTRACT",
                    message=(
                        f"primitive {primitive.name!r} test {case.name!r}: "
                        "integer-zero-divisor failure requires arithmetic guarantee "
                        f"{ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS.value!r}"
                    ),
                    source=source,
                )
            )
            continue
        binding = contract.binding(ArithmeticOperandRole.DIVISOR)
        if binding is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-FAILURE-DIVISOR",
                    message=(
                        f"primitive {primitive.name!r} test {case.name!r}: "
                        "integer-zero-divisor failure requires a resolved divisor role"
                    ),
                    source=source,
                )
            )
            continue
        info = SCALAR_TYPE_INFOS.get(case.type_tag)
        if info is not None and info.floating:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-FAILURE-DOMAIN",
                    message=(
                        f"primitive {primitive.name!r} test {case.name!r}: "
                        "integer-zero-divisor failure requires an integer lane type"
                    ),
                    source=source,
                )
            )
        expected_kind = "sImm" if case.role == "compile_failure" else None
        phase_matches = (
            binding.parameter_kind == expected_kind
            if expected_kind is not None
            else binding.parameter_kind != "sImm"
        )
        if not phase_matches:
            phase = "compile-time sImm" if case.role == "compile_failure" else "runtime"
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-FAILURE-PHASE",
                    message=(
                        f"primitive {primitive.name!r} test {case.name!r}: role "
                        f"{case.role!r} requires a {phase} divisor binding, got "
                        f"{binding.parameter_kind!r}"
                    ),
                    source=source,
                )
            )


def _validate_domains(
    catalog: Catalog,
    primitive: Primitive,
    diagnostics: list[Diagnostic],
) -> None:
    contract = primitive.arithmetic
    assert contract is not None
    infos = tuple(
        SCALAR_TYPE_INFOS[tag]
        for tag in sorted(
            {
                member
                for implementation in primitive.implementations
                for member in catalog.type_group_members(implementation.type_group)
            }
        )
        if tag in SCALAR_TYPE_INFOS
    )
    # No concrete source type evidence means the ordinary selector validators
    # own the malformed or unsupported type-group diagnostic.
    if not infos:
        return
    for guarantee in contract.ordered_guarantees:
        domain = ARITHMETIC_GUARANTEE_SPECS[guarantee].numeric_domain
        if domain is None or any(_matches_domain(info, domain) for info in infos):
            continue
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-ARITHMETIC-GUARANTEE-DOMAIN",
                message=(
                    f"arithmetic guarantee {guarantee.value!r} on primitive "
                    f"{primitive.name!r} has no declared {domain.value} type domain"
                ),
                source=contract.guarantees_source or contract.source or primitive.source,
            )
        )


def _matches_domain(info: ScalarTypeInfo, domain: ArithmeticNumericDomain) -> bool:
    if domain is ArithmeticNumericDomain.FLOATING:
        return info.floating
    if domain is ArithmeticNumericDomain.SIGNED_INTEGER:
        return info.signed and not info.floating
    return not info.floating


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


def _family_mismatch(
    name: str,
    fact: str,
    primitive: Primitive,
    source: SourceSpan | None,
    first: Primitive,
    first_source: SourceSpan | None,
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code="TSL-CATALOG-ARITHMETIC-FAMILY-MISMATCH",
        message=f"primitive family {name!r} has inconsistent arithmetic {fact}",
        source=source or primitive.source,
        related=_related(
            "family arithmetic contract starts here",
            first_source or first.source,
        ),
    )


def _related(message: str, span: SourceSpan | None) -> tuple[RelatedLocation, ...]:
    return () if span is None else (RelatedLocation(message=message, span=span),)


__all__ = ("validate_arithmetic_contracts",)
