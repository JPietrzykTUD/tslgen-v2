"""Validation and promotion for primitive ``preconditions`` declarations."""

from __future__ import annotations

from collections import Counter

from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionKind,
    PrimitivePrecondition,
    precondition_values,
)
from tslc.catalog.semantics import PrimitiveSemanticContract
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

    if operation is None and kinds:
        invalid = True
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-PRECONDITION-MISSING-OPERATION",
                message=(
                    f"primitive {declaration.name!r} preconditions require an "
                    "operation and operand_roles contract"
                ),
                source=source_span(field.source),
            )
        )
    if invalid or operation is None:
        return ()

    bindings_by_role = {binding.role: binding for binding in operation.operand_bindings}
    promoted: list[PrimitivePrecondition] = []
    for kind, item in kinds:
        descriptor = PRECONDITION_DESCRIPTORS[kind]
        if operation.kind not in descriptor.compatible_operations:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-INCOMPATIBLE-PRECONDITION-OPERATION",
                    message=(
                        f"precondition {kind.value!r} is incompatible with operation "
                        f"{operation.kind.value!r} on primitive {declaration.name!r}"
                    ),
                    source=_item_source(item),
                )
            )
            continue
        missing = descriptor.required_roles - bindings_by_role.keys()
        if missing:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-PRECONDITION-MISSING-ROLE",
                    message=(
                        f"precondition {kind.value!r} on primitive "
                        f"{declaration.name!r} requires operand roles "
                        + ", ".join(repr(role.value) for role in sorted(missing))
                    ),
                    source=_item_source(item),
                )
            )
            continue
        promoted.append(
            PrimitivePrecondition(
                kind=kind,
                operand_bindings=tuple(
                    bindings_by_role[role]
                    for role in sorted(
                        descriptor.required_roles, key=lambda role: role.value
                    )
                ),
                source=_item_source(item),
            )
        )
    return tuple(promoted)


def _item_source(item: ParsedTslScalarValue) -> SourceSpan | None:
    return source_span(item.payload_source or item.source)


__all__ = ("build_preconditions",)
