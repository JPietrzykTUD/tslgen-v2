from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
from tslgen.validation.catalog_validator import ValidatedPrimitive
from tslgen.validation.reference_rules import ReferenceValidatedCatalog


_BOOLEAN_WILDCARD_ATTRIBUTES = frozenset({"aligned", "packed"})
_BOOLEAN_EXPANSION_ORDER = (True, False)


@dataclass(frozen=True, slots=True)
class PrimitiveVariant:
    source: ValidatedPrimitive
    attributes: FrozenMap[str, CatalogValue]
    variant_id: str

    @property
    def primitive_name(self) -> str:
        return self.source.declaration.name

    @property
    def template_name(self) -> str:
        return self.source.template_name


@dataclass(frozen=True, slots=True)
class VariantSet:
    variants: tuple[PrimitiveVariant, ...]
    variants_by_id: FrozenMap[str, PrimitiveVariant] = field(init=False)

    def __post_init__(self) -> None:
        variants = tuple(self.variants)
        object.__setattr__(self, "variants", variants)
        object.__setattr__(
            self,
            "variants_by_id",
            FrozenMap((variant.variant_id, variant) for variant in variants),
        )


def expand_variants(
    reference_catalog: ReferenceValidatedCatalog,
) -> Result[VariantSet]:
    if reference_catalog.validated_catalog is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-EXPAND-MISSING-VALIDATED-CATALOG",
                    "variant expansion requires a reference-validated catalog "
                    "created from a ValidatedCatalog",
                ),
            )
        )

    diagnostics: list[Diagnostic] = []
    variants: list[PrimitiveVariant] = []
    seen_ids: set[str] = set()
    for primitive in reference_catalog.validated_catalog.primitives:
        expanded = _expand_primitive(primitive)
        diagnostics.extend(expanded.diagnostics)
        if not expanded.is_ok:
            continue
        for variant in expanded.unwrap():
            if variant.variant_id in seen_ids:
                diagnostics.append(
                    Diagnostic.error(
                        "TSL-EXPAND-DUPLICATE-VARIANT",
                        f"duplicate primitive variant id {variant.variant_id!r}",
                        location=primitive.declaration.source_span.location,
                    )
                )
                continue
            seen_ids.add(variant.variant_id)
            variants.append(variant)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(VariantSet(tuple(variants)), diagnostics=ordered)


def _expand_primitive(
    primitive: ValidatedPrimitive,
) -> Result[tuple[PrimitiveVariant, ...]]:
    attributes = FrozenMap(
        (attribute.key, attribute.value)
        for attribute in primitive.declaration.attributes
    )
    wildcard_keys = tuple(
        attribute.key
        for attribute in primitive.declaration.attributes
        if attribute.value == "*"
    )
    unsupported = tuple(
        key for key in wildcard_keys if key not in _BOOLEAN_WILDCARD_ATTRIBUTES
    )
    if unsupported:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-EXPAND-UNSUPPORTED-WILDCARD",
                    f"primitive {primitive.declaration.name!r} has unsupported wildcard "
                    f"attribute(s): {', '.join(unsupported)}",
                    location=primitive.declaration.source_span.location,
                ),
            )
        )

    if not wildcard_keys:
        return Result.ok(
            (
                PrimitiveVariant(
                    source=primitive,
                    attributes=attributes,
                    variant_id=_variant_id(primitive, attributes),
                ),
            )
        )

    variants: list[PrimitiveVariant] = []
    for concrete_values in product(
        _BOOLEAN_EXPANSION_ORDER,
        repeat=len(wildcard_keys),
    ):
        concrete = dict(attributes.items())
        concrete.update(zip(wildcard_keys, concrete_values, strict=True))
        concrete_attributes = FrozenMap(concrete)
        variants.append(
            PrimitiveVariant(
                source=primitive,
                attributes=concrete_attributes,
                variant_id=_variant_id(primitive, concrete_attributes),
            )
        )
    return Result.ok(tuple(variants))


def _variant_id(
    primitive: ValidatedPrimitive,
    attributes: FrozenMap[str, CatalogValue],
) -> str:
    parameters = ",".join(
        parameter.name for parameter in primitive.declaration.parameters
    )
    attrs = ",".join(
        f"{key}={_format_value(value)}" for key, value in attributes.items()
    )
    return (
        f"{primitive.declaration.name}<{primitive.signature.normalized}>"
        f"[{attrs}]({parameters})"
    )


def _format_value(value: CatalogValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    if value is None:
        return "none"
    raise TypeError(f"unsupported variant attribute value: {value!r}")
