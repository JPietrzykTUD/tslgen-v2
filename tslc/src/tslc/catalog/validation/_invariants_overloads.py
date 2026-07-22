"""Cross-declaration invariants for semantic primitive overloads."""

from __future__ import annotations

from collections.abc import Hashable

from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.overloads import OverloadAxisSpec
from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at


def validate_overload_families(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    families: dict[str, list[Primitive]] = {}
    for primitive in catalog.primitives:
        families.setdefault(primitive.name, []).append(primitive)

    for name in sorted(families):
        expanded = families[name]
        declarations = _unique_source_declarations(expanded)
        if not any(primitive.overload is not None for primitive in declarations):
            continue
        if not _validate_registry_membership(catalog, name, declarations, diagnostics):
            continue
        axis_spec = _validate_family_completeness(
            catalog,
            name,
            declarations,
            diagnostics,
        )
        if axis_spec is None:
            continue
        if not _validate_primary_marker(name, declarations, diagnostics):
            continue
        if not _validate_signature_alignment(name, axis_spec, declarations, diagnostics):
            continue
        _validate_composite_uniqueness(name, expanded, diagnostics)


def _unique_source_declarations(primitives: list[Primitive]) -> tuple[Primitive, ...]:
    unique: dict[Hashable, Primitive] = {}
    for index, primitive in enumerate(primitives):
        overload = primitive.overload
        key: Hashable
        if primitive.source is not None:
            key = primitive.source
        elif overload is not None:
            key = id(overload)
        else:
            key = ("declaration", index)
        unique.setdefault(key, primitive)
    return tuple(unique.values())


def _validate_registry_membership(
    catalog: Catalog,
    name: str,
    declarations: tuple[Primitive, ...],
    diagnostics: list[Diagnostic],
) -> bool:
    valid = True
    for primitive in declarations:
        overload = primitive.overload
        if overload is None or not overload.axis or not overload.value:
            continue
        axis_spec = catalog.overload_registry.axis(overload.axis)
        if axis_spec is None:
            valid = False
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OVERLOAD-UNKNOWN-AXIS",
                    message=(
                        f"primitive {name!r} declares unknown overload axis "
                        f"{overload.axis!r}"
                    ),
                    source=overload.axis_source or overload.source or primitive.source,
                    help=(
                        "registered overload axes: "
                        + ", ".join(catalog.overload_registry.axes)
                    ),
                )
            )
            continue
        if overload.value not in axis_spec.values:
            valid = False
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-OVERLOAD-INVALID-VALUE",
                    message=(
                        f"primitive {name!r} declares invalid overload value "
                        f"{overload.value!r} for axis {overload.axis!r}"
                    ),
                    source=overload.value_source or overload.source or primitive.source,
                    help="allowed values: " + ", ".join(axis_spec.values),
                )
            )
    return valid


def _validate_family_completeness(
    catalog: Catalog,
    name: str,
    declarations: tuple[Primitive, ...],
    diagnostics: list[Diagnostic],
) -> OverloadAxisSpec | None:
    annotated = tuple(
        primitive for primitive in declarations if primitive.overload is not None
    )
    first = annotated[0]
    assert first.overload is not None
    complete = True
    for primitive in declarations:
        if primitive.overload is not None:
            continue
        complete = False
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-MISSING-MEMBER",
                message=(
                    f"primitive family {name!r} uses overload axis "
                    f"{first.overload.axis!r}, but this declaration has no overload block"
                ),
                source=primitive.header_source or primitive.source,
                related=_related(
                    "annotated family member is here",
                    first.overload.source or first.source,
                ),
            )
        )
    for primitive in annotated[1:]:
        assert primitive.overload is not None
        if primitive.overload.axis == first.overload.axis:
            continue
        complete = False
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-MIXED-AXIS",
                message=(
                    f"primitive family {name!r} mixes overload axes "
                    f"{first.overload.axis!r} and {primitive.overload.axis!r}"
                ),
                source=(
                    primitive.overload.axis_source
                    or primitive.overload.source
                    or primitive.source
                ),
                related=_related(
                    f"first family axis {first.overload.axis!r} is declared here",
                    first.overload.axis_source or first.overload.source or first.source,
                ),
            )
        )
    if not complete:
        return None
    return catalog.overload_registry.axis(first.overload.axis)


def _validate_primary_marker(
    name: str,
    declarations: tuple[Primitive, ...],
    diagnostics: list[Diagnostic],
) -> bool:
    markers = tuple(
        primitive
        for primitive in declarations
        if primitive.overload is not None and primitive.overload.declares_primary
    )
    if not markers:
        first = declarations[0]
        overload = first.overload
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-MISSING-PRIMARY",
                message=(
                    f"primitive family {name!r} must have exactly one source "
                    "declaration with overload primary true"
                ),
                source=(
                    first.source
                    if overload is None
                    else overload.source or first.source
                ),
            )
        )
        return False
    if len(markers) == 1:
        return True
    first = markers[0]
    first_overload = first.overload
    assert first_overload is not None
    duplicate = markers[1]
    duplicate_overload = duplicate.overload
    assert duplicate_overload is not None
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-OVERLOAD-DUPLICATE-PRIMARY",
            message=(
                f"primitive family {name!r} has multiple source declarations with "
                f"overload primary true ({first_overload.value!r} and "
                f"{duplicate_overload.value!r})"
            ),
            source=(
                duplicate_overload.primary_source
                or duplicate_overload.source
                or duplicate.source
            ),
            related=tuple(
                RelatedLocation(
                    message=f"other primary marker for value {item.overload.value!r}",
                    span=span,
                )
                for item in markers
                if item is not duplicate
                if item.overload is not None
                if (
                    span := item.overload.primary_source
                    or item.overload.source
                    or item.source
                )
                is not None
            ),
        )
    )
    return False


def _validate_signature_alignment(
    name: str,
    axis_spec: OverloadAxisSpec,
    declarations: tuple[Primitive, ...],
    diagnostics: list[Diagnostic],
) -> bool:
    shaped = tuple(
        (primitive, _normalized_shape(primitive)) for primitive in declarations
    )
    if any(shape is None for _, shape in shaped):
        return False
    first_primitive, first_shape_value = shaped[0]
    assert first_shape_value is not None
    first_shape = first_shape_value
    aligned = True
    for primitive, shape_value in shaped[1:]:
        assert shape_value is not None
        shape = shape_value
        if (
            shape.result_kind == first_shape.result_kind
            and len(shape.param_kinds) == len(first_shape.param_kinds)
        ):
            continue
        aligned = False
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-SHAPE-MISMATCH",
                message=(
                    f"primitive family {name!r} overload members must align in result "
                    f"and arity after explicit policy-mask normalization; observed "
                    f"{primitive.signature!r}"
                ),
                source=primitive.signature_source or primitive.source,
                related=_related(
                    f"family shape starts with {first_primitive.signature!r}",
                    first_primitive.signature_source or first_primitive.source,
                ),
            )
        )
    if not aligned:
        return False

    candidates = tuple(
        position
        for position in range(len(first_shape.param_kinds))
        if all(
            _accepted_at(axis_spec, primitive, shape, position)
            for primitive, shape in shaped
            if shape is not None
        )
    )
    if len(candidates) != 1:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-SHAPE-MISMATCH",
                message=(
                    f"primitive family {name!r} overload axis {axis_spec.name!r} "
                    "must have exactly one discriminating operand position; "
                    f"found {len(candidates)}. {_observed_compatibility(axis_spec, shaped)}"
                ),
                source=first_primitive.signature_source or first_primitive.source,
            )
        )
        return False
    discriminating = candidates[0]
    for position in range(len(first_shape.param_kinds)):
        if position == discriminating:
            continue
        kinds = {
            shape.param_kinds[position]
            for _, shape in shaped
            if shape is not None
        }
        if len(kinds) == 1:
            continue
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-SHAPE-MISMATCH",
                message=(
                    f"primitive family {name!r} changes non-overload operand "
                    f"position {position + 1}: observed {', '.join(sorted(kinds))}"
                ),
                source=first_primitive.signature_source or first_primitive.source,
            )
        )
        return False
    return True


def _normalized_shape(primitive: Primitive) -> SignatureShape | None:
    shape = parse_signature(primitive.signature)
    if shape is None or not shape.param_terms or "mask" not in primitive.attributes:
        return shape
    if not DEFAULT_SIGNATURE_KINDS.is_test_mask_argument(shape.param_kinds[0]):
        return shape
    return SignatureShape(shape.result_term, shape.param_terms[1:])


def _accepted_at(
    axis_spec: OverloadAxisSpec,
    primitive: Primitive,
    shape: SignatureShape,
    position: int,
) -> bool:
    overload = primitive.overload
    if overload is None:
        return False
    value_spec = axis_spec.values.get(overload.value)
    return (
        value_spec is not None
        and shape.param_kinds[position] in value_spec.operand_kinds
    )


def _observed_compatibility(
    axis_spec: OverloadAxisSpec,
    shaped: tuple[tuple[Primitive, SignatureShape | None], ...],
) -> str:
    facts: list[str] = []
    for primitive, shape in shaped:
        overload = primitive.overload
        if overload is None or shape is None:
            continue
        value_spec = axis_spec.values[overload.value]
        facts.append(
            f"value {overload.value!r} observes {shape.param_kinds!r} "
            f"(accepted kinds: {', '.join(value_spec.operand_kinds)})"
        )
    return "; ".join(facts)


def _validate_composite_uniqueness(
    name: str,
    primitives: list[Primitive],
    diagnostics: list[Diagnostic],
) -> None:
    seen: dict[Hashable, Primitive] = {}
    for primitive in primitives:
        identity = _composite_identity(primitive)
        first = seen.get(identity)
        if first is None:
            seen[identity] = primitive
            continue
        if first.source is not None and first.source == primitive.source:
            continue
        overload = primitive.overload
        assert overload is not None
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-OVERLOAD-DUPLICATE-COMPOSITE",
                message=(
                    f"primitive family {name!r} has duplicate composite overload "
                    f"identity for {overload.axis}={overload.value}"
                ),
                source=primitive.header_source or primitive.source,
                related=_related(
                    "first composite overload declaration is here",
                    first.header_source or first.source,
                ),
            )
        )


def _composite_identity(primitive: Primitive) -> Hashable:
    shape = _normalized_shape(primitive)
    signature: Hashable = (
        primitive.signature.replace(" ", "")
        if shape is None
        else (shape.result_kind, shape.param_kinds)
    )
    overload = primitive.overload
    assert overload is not None
    return (
        overload.value,
        signature,
        tuple(sorted(primitive.attributes.items())),
        tuple(
            (
                item.name,
                item.kind,
                item.default,
                item.base_type_constraints,
                item.specialize_base,
                tuple(constraint.relation for constraint in item.base_width_constraints),
            )
            for item in primitive.generic_params
        ),
        primitive.result_target,
    )


def _related(message: str, span: SourceSpan | None) -> tuple[RelatedLocation, ...]:
    return () if span is None else (RelatedLocation(message=message, span=span),)


__all__ = ("validate_overload_families",)
