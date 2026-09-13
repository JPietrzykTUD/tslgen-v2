"""Semantic primitive-provider resolution regressions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.semantics import (
    COMPARE_EQUAL_REQUIREMENT,
    MASK_ALL_FALSE_REQUIREMENT,
    MASK_AND_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_POPULATION_COUNT_REQUIREMENT,
    MASK_SET_LANE_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
    RUNTIME_LANE_EXTRACT_REQUIREMENT,
    VECTOR_ZERO_REQUIREMENT,
    OperandRole,
    PrimitiveOperation,
    PrimitiveProviderRequirement,
)
from tslc.diagnostics import Diagnostic, SourceSpan


_CURRENT_PROVIDERS = (
    (MASK_TO_INTEGRAL_REQUIREMENT, "to_integral"),
    (MASK_FROM_INTEGRAL_REQUIREMENT, "to_mask"),
    (COMPARE_EQUAL_REQUIREMENT, "equal"),
    (MASK_AND_REQUIREMENT, "mask_binary_and"),
    (MASK_ALL_FALSE_REQUIREMENT, "mask_false"),
    (MASK_POPULATION_COUNT_REQUIREMENT, "mask_population_count"),
    (MASK_SET_LANE_REQUIREMENT, "set_mask_lane"),
    (RUNTIME_LANE_EXTRACT_REQUIREMENT, "extract_value_at"),
    (VECTOR_ZERO_REQUIREMENT, "set_zero"),
)


def test_current_corpus_resolves_semantic_primitive_providers(catalog: Catalog) -> None:
    assert tuple(
        _resolved(catalog, requirement).name
        for requirement, _name in _CURRENT_PROVIDERS
    ) == tuple(name for _requirement, name in _CURRENT_PROVIDERS)


def test_renamed_primitive_providers_resolve_without_name_fallback(
    catalog: Catalog,
) -> None:
    providers = tuple(
        _resolved(catalog, requirement)
        for requirement, _name in _CURRENT_PROVIDERS
    )
    names_by_identity = {
        id(provider): f"renamed_provider_{index}"
        for index, provider in enumerate(providers)
    }
    renamed = replace(
        catalog,
        primitives=tuple(
            replace(primitive, name=names_by_identity[id(primitive)])
            if id(primitive) in names_by_identity
            else primitive
            for primitive in catalog.primitives
        ),
    )

    assert tuple(
        _resolved(renamed, requirement).name
        for requirement, _name in _CURRENT_PROVIDERS
    ) == tuple(f"renamed_provider_{index}" for index in range(len(providers)))


def test_runtime_lane_extract_is_distinct_from_immediate_extract(
    catalog: Catalog,
) -> None:
    immediate = PrimitiveProviderRequirement(
        PrimitiveOperation.EXTRACT_LANE,
        "s",
        ("v",),
        (OperandRole.PRIMARY,),
    )

    assert _resolved(catalog, immediate).name == "extract_value"
    assert _resolved(catalog, RUNTIME_LANE_EXTRACT_REQUIREMENT).name == (
        "extract_value_at"
    )


def test_provider_attribute_constraints_disambiguate_mask_forms(
    catalog: Catalog,
) -> None:
    zero = next(
        primitive
        for primitive in catalog.primitives
        if primitive.operation is not None
        and primitive.operation.kind is PrimitiveOperation.COMPARE_EQUAL
        and primitive.signature == "m:=(m,v,v)"
    )
    pass_through = replace(
        zero,
        name="renamed_masked_equal",
        attributes={"mask": "pass_through"},
    )
    synthetic = replace(catalog, primitives=(*catalog.primitives, pass_through))
    requirement = PrimitiveProviderRequirement(
        PrimitiveOperation.COMPARE_EQUAL,
        "m",
        ("m", "v", "v"),
        (OperandRole.CONTROL_MASK, OperandRole.PRIMARY, OperandRole.SECONDARY),
        required_attributes=(("mask", "pass_through"),),
    )

    assert _resolved(synthetic, requirement).name == "renamed_masked_equal"


def test_missing_provider_is_source_aware_and_never_uses_its_name(
    catalog: Catalog,
) -> None:
    provider = _resolved(catalog, MASK_TO_INTEGRAL_REQUIREMENT)
    decoy = replace(provider, name="name_only_decoy", operation=None)
    synthetic = replace(
        catalog,
        primitives=tuple(
            decoy if primitive is provider else primitive
            for primitive in catalog.primitives
        ),
    )
    use_site = _span("use.tsl", 7)

    result = synthetic.resolve_primitive_provider(
        MASK_TO_INTEGRAL_REQUIREMENT,
        source=use_site,
    )

    assert isinstance(result, Diagnostic)
    assert result.code == "TSL-CATALOG-MISSING-PRIMITIVE-PROVIDER"
    assert result.span == use_site
    assert "mask_to_integral" in result.message
    assert decoy.name not in result.message


def test_ambiguous_provider_diagnostic_sorts_and_locates_candidates(
    catalog: Catalog,
) -> None:
    provider = _resolved(catalog, MASK_AND_REQUIREMENT)
    zeta = replace(
        provider,
        name="zeta_provider",
        source=_span("zeta.tsl", 3),
        header_source=_span("zeta.tsl", 3),
    )
    alpha = replace(
        provider,
        name="alpha_provider",
        source=_span("alpha.tsl", 5),
        header_source=_span("alpha.tsl", 5),
    )
    synthetic = replace(
        catalog,
        primitives=(
            *(primitive for primitive in catalog.primitives if primitive is not provider),
            zeta,
            alpha,
        ),
    )
    use_site = _span("use.tsl", 11)

    result = synthetic.resolve_primitive_provider(
        MASK_AND_REQUIREMENT,
        source=use_site,
    )

    assert isinstance(result, Diagnostic)
    assert result.code == "TSL-CATALOG-AMBIGUOUS-PRIMITIVE-PROVIDER"
    assert result.span == use_site
    assert result.message.index("alpha_provider") < result.message.index(
        "zeta_provider"
    )
    assert tuple(item.span.path.name for item in result.related) == (
        "alpha.tsl",
        "zeta.tsl",
    )


def _resolved(
    catalog: Catalog,
    requirement: PrimitiveProviderRequirement,
) -> Primitive:
    result = catalog.resolve_primitive_provider(requirement)
    assert isinstance(result, Primitive), result
    return result


def _span(name: str, line: int) -> SourceSpan:
    return SourceSpan(Path("/synthetic") / name, line, 1, line, 8)
