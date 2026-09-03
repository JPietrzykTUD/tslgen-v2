"""Validation and promotion for primitive ``preconditions`` declarations."""

from __future__ import annotations

from collections import Counter

from tslc.catalog.arithmetic import ArithmeticContract, ArithmeticOperandBinding
from tslc.catalog.memory import MemoryAccess, PrimitiveMemoryContract
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionKind,
    PrimitivePrecondition,
    precondition_values,
)
from tslc.catalog.semantics import (
    OperandBinding,
    OperandRole,
    PrimitiveSemanticContract,
)
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at
from tslc.syntax.access import source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslListValue,
    ParsedTslScalarValue,
)


def build_preconditions(
    declaration: ParsedPrimitiveDeclaration,
    operation: PrimitiveSemanticContract | None,
    arithmetic: ArithmeticContract | None,
    memory: PrimitiveMemoryContract | None,
    diagnostics: list[Diagnostic],
) -> tuple[PrimitivePrecondition, ...]:
    fields = declaration.fields_by_name("preconditions")
    if not fields or len(fields) != 1:
        return ()
    field = fields[0].field
    value = field.value
    if not isinstance(value, ParsedTslListValue) or any(
        not isinstance(item, ParsedTslScalarValue) for item in value.items
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-PRECONDITIONS-MALFORMED-LIST",
                message=(
                    f"primitive {declaration.name!r} preconditions must be a "
                    "scalar list"
                ),
                source=source_span(field.source),
            )
        )
        return ()
    items = tuple(
        item for item in value.items if isinstance(item, ParsedTslScalarValue)
    )
    counts = Counter(item.text for item in items)
    first_by_value: dict[str, ParsedTslScalarValue] = {}
    invalid = False
    for item in items:
        if counts[item.text] < 2:
            continue
        first = first_by_value.get(item.text)
        if first is None:
            first_by_value[item.text] = item
            continue
        invalid = True
        first_source = _item_source(first)
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-DUPLICATE-PRECONDITION",
                message=(
                    f"duplicate precondition {item.text!r} on primitive "
                    f"{declaration.name!r}"
                ),
                source=_item_source(item),
                related=(
                    ()
                    if first_source is None
                    else (
                        RelatedLocation(
                            message="first precondition is here",
                            span=first_source,
                        ),
                    )
                ),
            )
        )

    kinds: list[tuple[PreconditionKind, ParsedTslScalarValue]] = []
    for item in items:
        try:
            kinds.append((PreconditionKind(item.text), item))
        except ValueError:
            invalid = True
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-PRECONDITION",
                    message=(
                        f"unknown precondition {item.text!r} on primitive "
                        f"{declaration.name!r}; expected "
                        + ", ".join(repr(item) for item in precondition_values())
                    ),
                    source=_item_source(item),
                )
            )

    if operation is None and arithmetic is None and memory is None and kinds:
        invalid = True
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-PRECONDITION-MISSING-OPERATION",
                message=(
                    f"primitive {declaration.name!r} preconditions require an "
                    "operation, arithmetic, or memory contract with operand roles"
                ),
                source=source_span(field.source),
            )
        )
    if invalid or (operation is None and arithmetic is None and memory is None):
        return ()

    promoted: list[PrimitivePrecondition] = []
    for kind, item in kinds:
        descriptor = PRECONDITION_DESCRIPTORS[kind]
        semantic_compatible = (
            operation is not None
            and operation.kind in descriptor.compatible_operations
        )
        arithmetic_compatible = (
            arithmetic is not None
            and bool(
                arithmetic.operations.intersection(
                    descriptor.compatible_arithmetic_operations
                )
            )
        )
        memory_compatible = (
            memory is not None
            and memory.access in descriptor.compatible_memory_accesses
            and memory.addressing in descriptor.compatible_memory_addressings
        )
        compatible = (
            semantic_compatible and memory_compatible
            if descriptor.binds_memory_operand
            else semantic_compatible or arithmetic_compatible or memory_compatible
        )
        if not compatible:
            actual = (
                repr(operation.kind.value)
                if operation is not None
                else ", ".join(
                    repr(value.value) for value in arithmetic.ordered_operations
                )
                if arithmetic is not None
                else "none"
            )
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-INCOMPATIBLE-PRECONDITION-OPERATION",
                    message=(
                        f"precondition {kind.value!r} is incompatible with operation "
                        f"{actual} on primitive {declaration.name!r}"
                    ),
                    source=_item_source(item),
                )
            )
            continue
        bindings: list[OperandBinding | ArithmeticOperandBinding] = []
        missing_names: list[str] = []
        if semantic_compatible:
            assert operation is not None
            by_role = {binding.role: binding for binding in operation.operand_bindings}
            missing = descriptor.required_roles - by_role.keys()
            missing_names.extend(role.value for role in missing)
            bindings.extend(
                by_role[role]
                for role in sorted(descriptor.required_roles, key=lambda role: role.value)
                if role in by_role
            )
        if arithmetic_compatible:
            assert arithmetic is not None
            by_arithmetic_role = {
                binding.role: binding for binding in arithmetic.operand_bindings
            }
            missing_arithmetic = (
                descriptor.required_arithmetic_roles - by_arithmetic_role.keys()
            )
            missing_names.extend(role.value for role in missing_arithmetic)
            bindings.extend(
                by_arithmetic_role[role]
                for role in sorted(
                    descriptor.required_arithmetic_roles,
                    key=lambda role: role.value,
                )
                if role in by_arithmetic_role
            )
        if memory_compatible and descriptor.binds_memory_operand:
            assert memory is not None
            if operation is None:
                missing_names.append("memory_source_or_destination")
            else:
                memory_role = (
                    OperandRole.MEMORY_SOURCE
                    if memory.access is MemoryAccess.READ
                    else OperandRole.MEMORY_DESTINATION
                )
                memory_binding = operation.binding(memory_role)
                if memory_binding is None:
                    missing_names.append(memory_role.value)
                else:
                    bindings.append(memory_binding)
        if missing_names:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-PRECONDITION-MISSING-ROLE",
                    message=(
                        f"precondition {kind.value!r} on primitive "
                        f"{declaration.name!r} requires operand roles "
                        + ", ".join(repr(role) for role in sorted(missing_names))
                    ),
                    source=_item_source(item),
                )
            )
            continue
        if descriptor.checkable_arithmetic_binding_kinds:
            incompatible_bindings = tuple(
                binding
                for binding in bindings
                if isinstance(binding, ArithmeticOperandBinding)
                and binding.parameter_kind
                not in descriptor.checkable_arithmetic_binding_kinds
            )
            if incompatible_bindings:
                static_only = all(
                    binding.parameter_kind == "sImm"
                    for binding in incompatible_bindings
                )
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code=(
                            "TSL-CATALOG-PRECONDITION-STATIC-OPERAND"
                            if static_only
                            else "TSL-CATALOG-PRECONDITION-UNCHECKABLE-OPERAND"
                        ),
                        message=(
                            f"precondition {kind.value!r} on primitive "
                            f"{declaration.name!r} cannot be checked for operand kind(s) "
                            + ", ".join(
                                repr(binding.parameter_kind)
                                for binding in incompatible_bindings
                            )
                            + "; supported checkable kinds are "
                            + ", ".join(
                                repr(value)
                                for value in sorted(
                                    descriptor.checkable_arithmetic_binding_kinds
                                )
                            )
                        ),
                        source=_item_source(item),
                    )
                )
                continue
        promoted.append(
            PrimitivePrecondition(
                kind=kind,
                operand_bindings=tuple(bindings),
                source=_item_source(item),
            )
        )
    return tuple(promoted)


def _item_source(item: ParsedTslScalarValue) -> SourceSpan | None:
    return source_span(item.payload_source or item.source)


__all__ = ("build_preconditions",)
