"""Catalog/profile validation catches source-data shape errors before lowering."""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from tslc.backend.registry import registered_compiler_capabilities
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.target_families import (
    ProfileFamilyCapability,
    TargetFamilyCatalog,
    TargetFeatureCapability,
)
from tslc.catalog.validation import validate_catalog
from tslc.catalog.validation._schema_extensions import known_extension_fields
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import SourceLocation
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _diagnostics(text: str, *, backends: tuple[str, ...] = ("cpp", "rust")):
    _, diagnostics = _catalog_and_diagnostics(text, backends=backends)
    return diagnostics


def _catalog_and_diagnostics(
    text: str,
    *,
    backends: tuple[str, ...] = ("cpp", "rust"),
):
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), text, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(
            result.catalog,
            parsed,
            required_backends=backends,
            compiler_capabilities=registered_compiler_capabilities(),
        ),
    )
    return result.catalog, diagnostics


_OVERLOAD_REGISTRY = (
    "overload_axes:\n"
    "  count_distribution:\n"
    "    values:\n"
    "      uniform:\n"
    "        operand_kinds [s, sImm]\n"
    "      per_lane:\n"
    "        operand_kinds [v]\n"
    "  payload_extent:\n"
    "    values:\n"
    "      vector:\n"
    "        operand_kinds [v]\n"
    "      scalar:\n"
    "        operand_kinds [s]\n"
)


def _target_family_catalog() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar", "generic_like", "x86", "arm", "cuda"}),
        universal_extension_families=frozenset({"scalar", "generic_like"}),
        profile_families={
            "generic": ProfileFamilyCapability("generic"),
            "x86": ProfileFamilyCapability(
                "x86",
                frozenset({"x86"}),
                runner_kinds=frozenset({"sde"}),
            ),
            "aarch64": ProfileFamilyCapability(
                "aarch64",
                frozenset({"arm"}),
                runner_kinds=frozenset({"qemu-aarch64"}),
            ),
        },
    )


def _base_source(extra: str = "") -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        f"{extra}"
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )


def test_valid_tiny_catalog_has_no_validation_diagnostics() -> None:
    assert _diagnostics(_base_source()) == ()


def test_valid_overload_registry_has_no_schema_diagnostics() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "overload_axes:\n"
            "  demo_axis:\n"
            "    values:\n"
            "      first:\n"
            "        operand_kinds [s, sImm]\n"
            "      second:\n"
            "        operand_kinds [v]\n"
        )
    )

    assert not any("OVERLOAD" in diagnostic.code for diagnostic in diagnostics)


def test_overload_registry_rejects_duplicate_axes_values_and_kinds() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "overload_axes:\n"
            "  duplicate:\n"
            "    values:\n"
            "      same:\n"
            "        operand_kinds [s, s]\n"
            "      same:\n"
            "        operand_kinds [v]\n"
            "  duplicate:\n"
            "    values:\n"
            "      other:\n"
            "        operand_kinds [s]\n"
        )
    )

    codes = [diagnostic.code for diagnostic in diagnostics]
    assert "TSL-CATALOG-DUPLICATE-OVERLOAD-AXIS" in codes
    assert "TSL-CATALOG-DUPLICATE-OVERLOAD-VALUE" in codes
    duplicate_kind = next(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code == "TSL-CATALOG-OVERLOAD-DUPLICATE-OPERAND-KIND"
    )
    assert duplicate_kind.related


def test_overload_registry_rejects_duplicate_top_level_declarations() -> None:
    registry = (
        "overload_axes:\n"
        "  demo:\n"
        "    values:\n"
        "      value:\n"
        "        operand_kinds [s]\n"
    )
    diagnostics = _diagnostics(_base_source(registry + registry))

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-DUPLICATE-OVERLOAD-REGISTRY"
    )
    assert diagnostic.related


@pytest.mark.parametrize(
    ("registry", "code"),
    (
        (
            "overload_axes:\n"
            "  demo:\n"
            "    typo:\n"
            "      value:\n"
            "        operand_kinds [s]\n",
            "TSL-CATALOG-UNKNOWN-FIELD",
        ),
        (
            "overload_axes:\n"
            "  demo:\n"
            "    values: {}\n",
            "TSL-CATALOG-OVERLOAD-MISSING-VALUES",
        ),
        (
            "overload_axes:\n"
            "  demo:\n"
            "    values:\n"
            "      value:\n"
            "        operand_kinds [not_a_signature_kind]\n",
            "TSL-CATALOG-OVERLOAD-UNKNOWN-OPERAND-KIND",
        ),
        (
            "overload_axes:\n"
            "  demo:\n"
            "    values:\n"
            "      value:\n"
            "        operand_kinds []\n",
            "TSL-CATALOG-OVERLOAD-MALFORMED-OPERAND-KINDS",
        ),
    ),
)
def test_overload_registry_reports_malformed_schema(
    registry: str,
    code: str,
) -> None:
    diagnostics = _diagnostics(_base_source(registry))

    assert any(diagnostic.code == code for diagnostic in diagnostics)


def test_overload_registry_diagnostics_have_stable_source_order() -> None:
    source = _base_source(
        "overload_axes:\n"
        "  z_axis:\n"
        "    values: {}\n"
        "  a_axis:\n"
        "    values:\n"
        "      value:\n"
        "        operand_kinds [bad]\n"
    )

    diagnostics = tuple(
        (diagnostic.span.line, diagnostic.code, diagnostic.message)
        for diagnostic in _diagnostics(source)
        if "OVERLOAD" in diagnostic.code
    )

    assert diagnostics == tuple(sorted(diagnostics))


@pytest.mark.parametrize(
    ("overload", "code"),
    (
        (
            "  overload:\n"
            "    value uniform\n",
            "TSL-CATALOG-OVERLOAD-MISSING-FIELD",
        ),
        (
            "  overload:\n"
            "    axis count_distribution\n",
            "TSL-CATALOG-OVERLOAD-MISSING-FIELD",
        ),
        (
            "  overload:\n"
            "    axis count_distribution\n"
            "    axis payload_extent\n"
            "    value uniform\n",
            "TSL-CATALOG-DUPLICATE-FIELD",
        ),
        (
            "  overload:\n"
            "    axis count_distribution\n"
            "    value uniform\n"
            "    typo true\n",
            "TSL-CATALOG-UNKNOWN-FIELD",
        ),
        (
            "  overload:\n"
            "    axis count_distribution\n"
            "    value uniform\n"
            "    primary sometimes\n",
            "TSL-CATALOG-OVERLOAD-MALFORMED-PRIMARY",
        ),
        (
            "  overload:\n"
            "    axis [count_distribution]\n"
            "    value uniform\n",
            "TSL-CATALOG-OVERLOAD-MALFORMED-FIELD",
        ),
        (
            "  overload:\n"
            "    axis count_distribution\n"
            "    value {name uniform}\n",
            "TSL-CATALOG-OVERLOAD-MALFORMED-FIELD",
        ),
    ),
)
def test_primitive_overload_block_rejects_malformed_fields(
    overload: str,
    code: str,
) -> None:
    source = _base_source().replace("  impls:\n", overload + "  impls:\n")

    diagnostics = _diagnostics(source)

    assert any(diagnostic.code == code for diagnostic in diagnostics)


@pytest.mark.parametrize("primary", ("", "    primary false\n", "    primary true\n"))
def test_primitive_overload_primary_boolean_forms_are_locally_valid(primary: str) -> None:
    overload = (
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        f"{primary}"
    )
    source = _base_source().replace("  impls:\n", overload + "  impls:\n")

    diagnostics = _diagnostics(source)

    assert not any(
        diagnostic.code == "TSL-CATALOG-OVERLOAD-MALFORMED-PRIMARY"
        for diagnostic in diagnostics
    )


def test_overload_family_validates_and_promotes_primary_value() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,sImm)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "prim<v:=(m,v,sImm)>[mask=pass_through] family(mask, data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )
    catalog, diagnostics = _catalog_and_diagnostics(
        _base_source(_OVERLOAD_REGISTRY + family)
    )

    assert not any("OVERLOAD" in diagnostic.code for diagnostic in diagnostics)
    resolved = tuple(
        catalog.resolve_primitive_overload(primitive)
        for primitive in catalog.primitives_named("family", unmasked=False)
    )
    assert all(item is not None for item in resolved)
    assert [item.is_primary_value for item in resolved if item is not None] == [
        True,
        True,
        True,
        False,
    ]


@pytest.mark.parametrize(
    ("axis", "value", "code"),
    (
        (
            "count_distribution",
            "scalar",
            "TSL-CATALOG-OVERLOAD-INVALID-VALUE",
        ),
        ("payload_extent", "uniform", "TSL-CATALOG-OVERLOAD-INVALID-VALUE"),
        ("unknown_axis", "uniform", "TSL-CATALOG-OVERLOAD-UNKNOWN-AXIS"),
    ),
)
def test_overload_family_rejects_unregistered_axis_value_pairs(
    axis: str,
    value: str,
    code: str,
) -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        f"    axis {axis}\n"
        f"    value {value}\n"
        "    primary true\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(item for item in diagnostics if item.code == code)
    assert diagnostic.span is not None
    assert diagnostic.help


def test_overload_family_requires_every_same_name_declaration() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  semantics \"missing metadata\"\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-OVERLOAD-MISSING-MEMBER"
    )
    assert diagnostic.related


def test_overload_family_rejects_mixed_axes() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,v)> family(data, payload):\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value vector\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(
        item for item in diagnostics if item.code == "TSL-CATALOG-OVERLOAD-MIXED-AXIS"
    )
    assert diagnostic.related


def test_overload_family_rejects_primary_markers_for_different_values() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
        "    primary true\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-OVERLOAD-DUPLICATE-PRIMARY"
    )
    assert diagnostic.related


def test_overload_family_rejects_multiple_primary_markers_for_same_value() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,sImm)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    assert any(
        item.code == "TSL-CATALOG-OVERLOAD-DUPLICATE-PRIMARY"
        for item in diagnostics
    )


def test_overload_family_rejects_duplicate_composite_identity() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,s)> family(other_data, other_count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    assert any(
        item.code == "TSL-CATALOG-OVERLOAD-DUPLICATE-COMPOSITE"
        for item in diagnostics
    )
    assert any(item.code == "TSL-CATALOG-DUPLICATE-PRIMITIVE" for item in diagnostics)


def test_overload_family_requires_one_primary_marker() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    assert any(
        item.code == "TSL-CATALOG-OVERLOAD-MISSING-PRIMARY"
        for item in diagnostics
    )


def test_overload_family_rejects_swapped_operand_kinds() -> None:
    family = (
        "prim<v:=(v,v)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-OVERLOAD-SHAPE-MISMATCH"
    )
    assert "accepted kinds" in diagnostic.message
    assert "observes" in diagnostic.message


def test_overload_family_rejects_result_or_arity_mismatch() -> None:
    family = (
        "prim<v:=(v,s)> family(data, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<s:=(v,v,v)> family(data, other, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    diagnostic = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-OVERLOAD-SHAPE-MISMATCH"
    )
    assert diagnostic.related


def test_ordinary_leading_mask_operand_is_not_policy_normalized() -> None:
    family = (
        "prim<v:=(m,s)> family(active, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value uniform\n"
        "    primary true\n"
        "prim<v:=(m,v)> family(active, count):\n"
        "  overload:\n"
        "    axis count_distribution\n"
        "    value per_lane\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    assert not any("OVERLOAD" in item.code for item in diagnostics)


def test_wildcard_expansion_does_not_duplicate_primary_marker() -> None:
    family = (
        "prim<void:=(ptr,v)>[aligned=*] family(ptr, data):\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value vector\n"
        "    primary true\n"
        "prim<void:=(m,ptr,v)>[aligned=*,mask=pass_through] family(mask, ptr, data):\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value vector\n"
        "prim<void:=(ptr,s)>[aligned=*] family(ptr, data):\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value scalar\n"
    )
    catalog, diagnostics = _catalog_and_diagnostics(
        _base_source(_OVERLOAD_REGISTRY + family)
    )

    assert not any("OVERLOAD" in item.code for item in diagnostics)
    variants = catalog.primitives_named("family", unmasked=False)
    assert len(variants) == 6
    assert sum(
        bool(resolved and resolved.is_primary_value)
        for primitive in variants
        if (resolved := catalog.resolve_primitive_overload(primitive)) is not None
    ) == 4


def test_result_target_dimension_distinguishes_duplicate_headers() -> None:
    family = (
        "prim<void:=(ptr,v)> family(ptr, data):\n"
        "  return_type:\n"
        "    base: ToBase\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value vector\n"
        "    primary true\n"
        "prim<void:=(ptr,v)> family(ptr, data):\n"
        "  return_type:\n"
        "    extension: ToExtension\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value vector\n"
        "prim<void:=(ptr,s)> family(ptr, data):\n"
        "  overload:\n"
        "    axis payload_extent\n"
        "    value scalar\n"
    )

    diagnostics = _diagnostics(_base_source(_OVERLOAD_REGISTRY + family))

    assert not any("OVERLOAD" in item.code for item in diagnostics)
    assert not any(item.code == "TSL-CATALOG-DUPLICATE-PRIMITIVE" for item in diagnostics)


def test_synthetic_overload_axis_is_additive_at_catalog_boundary() -> None:
    registry = (
        "overload_axes:\n"
        "  synthetic_axis:\n"
        "    values:\n"
        "      alpha:\n"
        "        operand_kinds [s]\n"
        "      beta:\n"
        "        operand_kinds [v]\n"
    )
    family = (
        "prim<v:=(v,s)> family(data, payload):\n"
        "  overload:\n"
        "    axis synthetic_axis\n"
        "    value alpha\n"
        "    primary true\n"
        "prim<v:=(v,v)> family(data, payload):\n"
        "  overload:\n"
        "    axis synthetic_axis\n"
        "    value beta\n"
    )
    catalog, diagnostics = _catalog_and_diagnostics(_base_source(registry + family))

    assert not any("OVERLOAD" in item.code for item in diagnostics)
    assert catalog.resolve_primitive_overload(
        catalog.primitives_named("family")[0]
    ).is_primary_value


def test_implementation_selector_rejects_unknown_scalar_metadata() -> None:
    source = _base_source().replace(
        "        implementation:\n",
        '        hello: "test"\n'
        "        implementation:\n",
    )

    diagnostics = _diagnostics(source)

    assert any(
        diagnostic.code == "TSL-CATALOG-UNKNOWN-FIELD"
        and "'hello'" in diagnostic.message
        and "implementation selector 'ints'" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_target_constraint_relations_are_validated() -> None:
    source = _base_source().replace(
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        "prim<v:=v> id(data):\n"
        "  return_type:\n"
        "    extension: ToExtension\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        ToExtension:\n"
        "          where:\n"
        "            family unrelated\n"
        "            width sideways\n"
        "            implementation:\n"
        '              tsil "complete(data);"\n',
    )

    diagnostics = _diagnostics(source)

    assert sum(diagnostic.code == "TSL-CATALOG-INVALID-ENUM" for diagnostic in diagnostics) == 2
    assert any("target constraint family" in diagnostic.message for diagnostic in diagnostics)
    assert any("target constraint width" in diagnostic.message for diagnostic in diagnostics)


def test_exact_double_target_constraint_relation_is_accepted() -> None:
    source = _base_source().replace(
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        "prim<v:=v> id(data):\n"
        "  return_type:\n"
        "    extension: ToExtension\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        ToExtension:\n"
        "          where:\n"
        "            family same_as\n"
        "            width twice_as_wide\n"
        "            implementation:\n"
        '              tsil "complete(data);"\n',
    )

    diagnostics = _diagnostics(source)

    assert not any(
        diagnostic.code == "TSL-CATALOG-INVALID-ENUM" for diagnostic in diagnostics
    )


def test_primitive_documentation_fields_are_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "  impls:\n",
        '  brief_description "Identity operation."\n'
        '  detailed_description "Returns the input unchanged."\n'
        '  semantics """\n'
        "input: register data\n"
        "return data\n"
        '"""\n'
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert primitive.brief_description == "Identity operation."
    assert primitive.detailed_description == "Returns the input unchanged."
    assert "input: register data" in (primitive.semantics or "")
    assert "return data" in (primitive.semantics or "")


def test_benchmark_latency_chain_is_typed_primitive_metadata() -> None:
    source = _base_source().replace(
        "  impls:\n",
        "  benchmarks:\n"
        "    latency_chain data\n"
        "    operand_domains:\n"
        "      data nonzero\n"
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )

    assert diagnostics == ()
    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert primitive.benchmark.latency_chain == "data"
    assert [
        (operand.parameter, operand.domain)
        for operand in primitive.benchmark.operand_domains
    ] == [("data", "nonzero")]


@pytest.mark.parametrize(
    ("benchmarks", "code"),
    (
        ('  benchmarks "latency"\n', "TSL-CATALOG-BENCHMARKS-NOT-MAP"),
        (
            "  benchmarks:\n    latency_chain missing\n",
            "TSL-CATALOG-BENCHMARK-BAD-LATENCY-CHAIN",
        ),
        (
            "  benchmarks:\n    workload arbitrary_cpp\n",
            "TSL-CATALOG-UNKNOWN-FIELD",
        ),
        (
            '  benchmarks:\n    operand_domains "nonzero"\n',
            "TSL-CATALOG-BENCHMARK-OPERAND-DOMAINS-NOT-MAP",
        ),
        (
            "  benchmarks:\n    operand_domains:\n      missing nonzero\n",
            "TSL-CATALOG-BENCHMARK-BAD-OPERAND",
        ),
        (
            "  benchmarks:\n    operand_domains:\n      data arbitrary\n",
            "TSL-CATALOG-BENCHMARK-BAD-OPERAND-DOMAIN",
        ),
    ),
)
def test_benchmark_metadata_rejects_untyped_or_unknown_forms(
    benchmarks: str,
    code: str,
) -> None:
    source = _base_source().replace("  impls:\n", benchmarks + "  impls:\n")

    assert any(diagnostic.code == code for diagnostic in _diagnostics(source))


def test_benchmark_operand_domain_rejects_non_vector_parameter() -> None:
    source = _base_source().replace(
        "prim<v:=v> id(data):\n  impls:\n",
        "prim<v:=(v,s)> id(data, divisor):\n"
        "  benchmarks:\n"
        "    operand_domains:\n"
        "      divisor nonzero\n"
        "  impls:\n",
    )

    assert any(
        diagnostic.code == "TSL-CATALOG-BENCHMARK-BAD-OPERAND"
        for diagnostic in _diagnostics(source)
    )


def test_shift_count_operand_domain_accepts_scalar_parameter() -> None:
    source = _base_source().replace(
        "prim<v:=v> id(data):\n  impls:\n",
        "prim<v:=(v,s)> id(data, count):\n"
        "  benchmarks:\n"
        "    operand_domains:\n"
        "      count shift_count\n"
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None

    assert (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    ) == ()
    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert [
        (operand.parameter, operand.domain)
        for operand in primitive.benchmark.operand_domains
    ] == [("count", "shift_count")]


def test_shift_count_operand_domain_rejects_immediate_parameter() -> None:
    source = _base_source().replace(
        "prim<v:=v> id(data):\n  impls:\n",
        "prim<v:=(v,sImm)> id(data, count):\n"
        "  benchmarks:\n"
        "    operand_domains:\n"
        "      count shift_count\n"
        "  impls:\n",
    )

    assert any(
        diagnostic.code == "TSL-CATALOG-BENCHMARK-BAD-OPERAND"
        for diagnostic in _diagnostics(source)
    )


def test_implementation_variants_are_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        "        implementation:\n"
        '          tsil "complete(data);"\n'
        "        variants:\n"
        "          scalar_loop:\n"
        '            tsil "complete(data);"\n'
        "          intrinsic_composition:\n"
        "            safety:\n"
        "              internal_unsafe true\n"
        "              reasons [intrinsic]\n"
        '            tsil "complete(intrin<identity>(data));"\n',
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    implementation = result.catalog.primitive("id").implementations[0]
    assert tuple(variant.name for variant in implementation.variants) == (
        "scalar_loop",
        "intrinsic_composition",
    )
    assert implementation.variants[0].body_text == "complete(data);"
    assert implementation.variants[1].safety.internal_unsafe is True
    assert implementation.variants[1].safety.caller_unsafe is False
    assert implementation.variants[1].safety.reasons == frozenset({"intrinsic"})


def test_implementation_variants_must_live_on_body_leaf() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      variants:\n"
        "        alt:\n"
        '          tsil "complete(data);"\n'
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-MALFORMED-VARIANT")
    assert "same selector entry as an implementation body" in diagnostic.message


def test_implementation_variant_cannot_change_public_caller_safety() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "        implementation:\n"
            '          tsil "complete(data);"\n',
            "        implementation:\n"
            '          tsil "complete(data);"\n'
            "        variants:\n"
            "          alt:\n"
            "            safety:\n"
            "              caller_unsafe true\n"
            '            tsil "complete(data);"\n',
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "implementation variant 'alt' safety" in diagnostic.message
    assert "caller_unsafe" in diagnostic.message


def test_duplicate_implementation_variant_names_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "        implementation:\n"
            '          tsil "complete(data);"\n',
            "        implementation:\n"
            '          tsil "complete(data);"\n'
            "        variants:\n"
            "          alt:\n"
            '            tsil "complete(data);"\n'
            "          alt:\n"
            '            tsil "complete(data);"\n',
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-DUPLICATE-FIELD")
    assert "implementation variant 'alt'" in diagnostic.message


def test_implementation_variant_bodies_are_validated_like_default_bodies() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "        implementation:\n"
            '          tsil "complete(data);"\n',
            "        implementation:\n"
            '          tsil "complete(data);"\n'
            "        variants:\n"
            "          alt:\n"
            '            tsil "call<primitive=set_zero trailing>(data);"\n',
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-CALL-SELECTOR")
    assert "primitive 'id': malformed call selector" in diagnostic.message


def test_simd_type_base_constraints_are_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "  impls:\n",
        "  generic_params:\n"
        "    IndexVec {kind simd_type, base_types [ints, si32], specialize_base true}\n"
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert primitive.generic_params[0].base_type_constraints == ("ints", "si32")
    assert primitive.generic_params[0].specialize_base is True
    assert primitive.generic_params[0].base_width_constraints == ()


def test_simd_type_nested_constraints_are_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "  impls:\n",
        "  generic_params:\n"
        "    IndexVec:\n"
        "      kind simd_type\n"
        "      specialize_base true\n"
        "      constraints:\n"
        "        base_types [ints, si32]\n"
        "        width(self::base) >= width(base::in)\n"
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    primitive = result.catalog.primitive("id")
    assert primitive is not None
    param = primitive.generic_params[0]
    assert param.base_type_constraints == ("ints", "si32")
    assert param.specialize_base is True
    assert tuple(constraint.relation for constraint in param.base_width_constraints) == (
        ">=",
    )


def test_test_index_type_is_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "  impls:\n",
        "  tests:\n"
        "    - {tags [basic], type \"si32\", index_type \"si32\", case {inputs [[1, 2, 3, 4]], expected [1, 2, 3, 4]}}\n"
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert primitive.tests[0].index_type == "si32"
    assert primitive.tests[0].name == "id_si32_index_si32_basic"


def test_test_index_type_must_be_a_known_scalar_type() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  tests:\n"
            "    - {tags [basic], type \"si32\", index_type \"vec32\", case {inputs [[1, 2, 3, 4]], expected [1, 2, 3, 4]}}\n"
            "  impls:\n",
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-INVALID-ENUM")
    assert "test index_type 'vec32'" in diagnostic.message


def test_simd_type_base_constraints_are_allowed_only_on_simd_type_params() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    PreserveSign {kind bool, base_types [si32]}\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "allowed only for kind 'simd_type'" in diagnostic.message


def test_simd_type_base_specialization_is_allowed_only_on_simd_type_params() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    PreserveSign {kind bool, specialize_base true}\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "specialize_base is allowed only for kind 'simd_type'" in diagnostic.message


def test_simd_type_base_specialization_requires_base_constraints() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec {kind simd_type, specialize_base true}\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "must declare base_types" in diagnostic.message


def test_simd_type_base_specialization_accepts_nested_base_constraints() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec:\n"
            "      kind simd_type\n"
            "      specialize_base true\n"
            "      constraints:\n"
            "        base_types [si32]\n"
            "  impls:\n",
        )
    )

    assert diagnostics == ()


def test_simd_type_base_width_constraint_requires_specialization() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec:\n"
            "      kind simd_type\n"
            "      constraints:\n"
            "        base_types [si32]\n"
            "        width(self::base) >= width(base::in)\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "base-width constraints require specialize_base true" in diagnostic.message


def test_base_width_constraint_unknown_relation_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec:\n"
            "      kind simd_type\n"
            "      specialize_base true\n"
            "      constraints:\n"
            "        base_types [si32]\n"
            "        width(self::base) < width(base::in)\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-BASE-WIDTH-RELATION"
    )
    assert "unknown relation '<'" in diagnostic.message
    assert ">=" in diagnostic.message
    # the mistyped relation is diagnosed as such, not as an unrelated unknown field
    assert not any(
        d.code == "TSL-CATALOG-UNKNOWN-FIELD" and "width(self::base)" in d.message
        for d in diagnostics
    )


def test_base_width_constraint_known_relations_are_accepted() -> None:
    for relation in (">=", ">", "=="):
        diagnostics = _diagnostics(
            _base_source().replace(
                "  impls:\n",
                "  generic_params:\n"
                "    IndexVec:\n"
                "      kind simd_type\n"
                "      specialize_base true\n"
                "      constraints:\n"
                "        base_types [si32]\n"
                f"        width(self::base) {relation} width(base::in)\n"
                "  impls:\n",
            )
        )

        assert diagnostics == (), (relation, diagnostics)


def test_extension_vector_bits_unknown_spelling_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            '  family "scalar"\n',
            '  family "scalar"\n  vector_bits "huge"\n',
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-MALFORMED-VECTOR-BITS"
    )
    assert "'huge'" in diagnostic.message
    assert "scalable" in diagnostic.message
    assert "sized" in diagnostic.message


def test_extension_vector_bits_accepts_numeric_sized_and_scalable() -> None:
    for value in ("128", '"sized"', '"scalable"'):
        diagnostics = _diagnostics(
            _base_source().replace(
                '  family "scalar"\n',
                f'  family "scalar"\n  vector_bits {value}\n',
            )
        )

        assert not any(
            d.code == "TSL-CATALOG-MALFORMED-VECTOR-BITS" for d in diagnostics
        ), (value, diagnostics)


def test_simd_type_base_constraints_cannot_duplicate_base_types_location() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec:\n"
            "      kind simd_type\n"
            "      base_types [si32]\n"
            "      specialize_base true\n"
            "      constraints:\n"
            "        base_types [si64]\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "declares base_types both directly and inside constraints" in diagnostic.message


def test_simd_type_base_constraints_must_resolve_to_scalar_types() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "  impls:\n",
            "  generic_params:\n"
            "    IndexVec {kind simd_type, base_types [ui128]}\n"
            "  impls:\n",
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-SIMD-TYPE-CONSTRAINT"
    )
    assert "invalid base_types entry 'ui128'" in diagnostic.message


def test_duplicate_keys_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "language cpp:\n"
            '  s32 {type "int"}\n'
        )
    )

    assert "TSL-CATALOG-DUPLICATE-BLOCK" in {d.code for d in diagnostics}


def test_duplicate_primitive_declarations_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "prim<v:=v> id(data):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
        )
    )

    duplicate = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-DUPLICATE-PRIMITIVE"
    )
    assert "id" in duplicate.message
    assert duplicate.related
    assert duplicate.related[0].message == "first declaration is here"


def test_repeated_wildcard_primitive_declaration_is_a_duplicate() -> None:
    block = (
        "prim<v:=v>[aligned=*] dup(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )
    diagnostics = _diagnostics(_base_source(block + block))

    assert "TSL-CATALOG-DUPLICATE-PRIMITIVE" in {d.code for d in diagnostics}


def test_primitive_overloads_and_attribute_variants_are_not_duplicates() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "prim<v:=(v,v)> combine(left, right):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(left);"\n'
            "prim<v:=(v,s)> combine(left, scalar):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(left);"\n'
            "prim<v:=v>[aligned=true] tagged(data):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
            "prim<v:=v>[aligned=false] tagged(data):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
        )
    )

    assert "TSL-CATALOG-DUPLICATE-PRIMITIVE" not in {d.code for d in diagnostics}


def test_base_and_extension_target_declarations_share_one_callable_name() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "prim<im:=(imt,im,usize)> resize_mask(orig, data, position):\n"
            "  return_type:\n"
            "    base: ToBase\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        ToBase:\n"
            "          ints:\n"
            "            implementation:\n"
            '              tsil "complete(orig);"\n'
            "prim<im:=(imt,im,usize)> resize_mask(orig, data, position):\n"
            "  return_type:\n"
            "    extension: ToExtension\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        ToExtension:\n"
            "          scalar:\n"
            "            implementation:\n"
            '              tsil "complete(orig);"\n'
        )
    )

    assert "TSL-CATALOG-DUPLICATE-PRIMITIVE" not in {d.code for d in diagnostics}


@pytest.mark.parametrize("dimension", ("base", "extension"))
@pytest.mark.parametrize("ordinary_first", (True, False))
def test_ordinary_and_target_declarations_cannot_share_one_callable(
    dimension: str,
    ordinary_first: bool,
) -> None:
    ordinary = (
        "prim<im:=(im,usize)> resize_mask(data, position):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )
    targeted = (
        "prim<im:=(im,usize)> resize_mask(data, position):\n"
        "  return_type:\n"
        f"    {dimension}: ToTarget\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        ToTarget:\n"
        "          ints:\n"
        "            implementation:\n"
        '              tsil "complete(data);"\n'
    )
    diagnostics = _diagnostics(
        _base_source(ordinary + targeted if ordinary_first else targeted + ordinary)
    )

    duplicate = next(
        item
        for item in diagnostics
        if item.code == "TSL-CATALOG-DUPLICATE-PRIMITIVE"
    )
    assert "ordinary and target-axis forms" in duplicate.message
    assert duplicate.related


def test_target_owned_signature_parameter_requires_return_type_axis() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "prim<im:=(imt,im,usize)> resize_mask(orig, data, position):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(orig);"\n'
        )
    )

    assert "TSL-CATALOG-TARGET-PARAM-RETURN-TYPE" in {
        diagnostic.code for diagnostic in diagnostics
    }


def test_type_group_without_member_list_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "types:\n"
            '  broken:\n'
            '    types "notalist"\n'
        )
    )

    malformed = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-TYPE-GROUP-MALFORMED"
    )
    assert "broken" in malformed.message


def test_type_group_with_empty_member_list_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "types:\n"
            "  hollow {types []}\n"
        )
    )

    assert "TSL-CATALOG-TYPE-GROUP-MALFORMED" in {d.code for d in diagnostics}


def test_type_group_missing_types_field_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "types:\n"
            "  nameless {}\n"
        )
    )

    assert "TSL-CATALOG-TYPE-GROUP-MALFORMED" in {d.code for d in diagnostics}


def test_unknown_fields_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension generic:\n"
            '  extension_name "generic"\n'
            '  family "generic_like"\n'
            "  familly typo\n"
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "familly" in diagnostic.message
    assert diagnostic.location == SourceLocation(Path("catalog_validation_fixture.tsl"), 13, 3)


def test_lscpu_flags_is_no_longer_an_extension_field() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension legacy:\n"
            '  extension_name "legacy"\n'
            '  family "scalar"\n'
            "  lscpu_flags []\n"
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "lscpu_flags" in diagnostic.message


def test_unknown_extension_backend_metadata_fields_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension generic:\n"
            '  extension_name "generic"\n'
            '  family "generic_like"\n'
            "  cpp:\n"
            "    supported true\n"
            '    test_suit_name "typo"\n'
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "test_suit_name" in diagnostic.message
    assert "extension backend cpp" in diagnostic.message


def test_extension_backend_field_names_follow_supported_backends() -> None:
    assert {"cpp", "rust"} <= known_extension_fields(("cpp", "rust"))
    assert {"active_when", "supersedes"} <= known_extension_fields()
    assert "lscpu_flags" not in known_extension_fields()
    assert "zig" in known_extension_fields(("zig",))
    assert "zig" not in known_extension_fields()
    assert "vendor" not in known_extension_fields()


@pytest.mark.parametrize(
    ("fields", "field_name"),
    (
        ('  vendor "intel"\n', "vendor"),
        ("  test_sizes_bits [128]\n", "test_sizes_bits"),
        ("  signature_support:\n    exclude []\n", "signature_support"),
        (
            '  mask_type_policy:\n    kind "lane_bitmask"\n    width "lanes"\n',
            "width",
        ),
        (
            '  integral_mask_type_policy:\n    kind "unsigned_scalar"\n'
            '    cpp "std::uint64_t"\n',
            "cpp",
        ),
        ("  size_parameter:\n    kind \"lanes\"\n    name \"LANES\"\n", "kind"),
        (
            '  vector_register_type_policy:\n    kind "fixed_array"\n'
            '    element "base_type"\n',
            "element",
        ),
        (
            "  cpp:\n    supported true\n"
            '    test_suite_name "LegacySuite"\n',
            "test_suite_name",
        ),
    ),
)
def test_inert_extension_fields_are_rejected(fields: str, field_name: str) -> None:
    source = _base_source().replace("language cpp:\n", fields + "language cpp:\n")

    diagnostics = _diagnostics(source)

    unknown = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code == "TSL-CATALOG-UNKNOWN-FIELD"
    ]
    assert any(field_name in diagnostic.message for diagnostic in unknown)


def test_extension_backend_compiler_capabilities_are_validated() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension guarded:\n"
            '  extension_name "guarded"\n'
            '  family "x86"\n'
            "  cpp:\n"
            "    supported true\n"
            "    compiler_capabilities [missing_capability]\n"
        )
    )

    assert any(
        diagnostic.code == "TSL-CATALOG-UNKNOWN-COMPILER-CAPABILITY"
        and "missing_capability" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_extension_backend_dataparallel_inference_is_boolean() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension overlay:\n"
            '  extension_name "overlay"\n'
            '  family "x86"\n'
            "  cpp:\n"
            "    supported true\n"
            '    dataparallel_inference "sometimes"\n'
        )
    )

    assert any(
        diagnostic.code == "TSL-CATALOG-MALFORMED-DATAPARALLEL-INFERENCE"
        for diagnostic in diagnostics
    )


def test_scalable_cpp_extension_requires_runtime_lane_count() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension sve_demo:\n"
            '  extension_name "sve_demo"\n'
            '  family "arm"\n'
            '  vector_bits "scalable"\n'
            "  cpp:\n"
            "    supported true\n"
        ),
        backends=("cpp",),
    )

    diagnostic = next(
        d
        for d in diagnostics
        if d.code == "TSL-CATALOG-MISSING-RUNTIME-LANE-COUNT"
    )
    assert "runtime_lane_count entry for backend 'cpp'" in diagnostic.message


def test_invalid_enum_like_values_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  universal_extension_families [scalar]\n"
        "  extension_family_capabilities:\n"
        "    scalar:\n"
        "      implementation_fallback sometimes\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      native_without_runner sometimes\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "nonsense"\n'
        "  mask_type_policy:\n"
        "    kind strange\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    messages = [d.message for d in diagnostics if d.code == "TSL-CATALOG-INVALID-ENUM"]
    assert any("family" in message for message in messages)
    assert any("mask_type_policy" in message for message in messages)
    assert any("implementation_fallback" in message for message in messages)
    assert any("native_without_runner" in message for message in messages)


def test_target_family_data_makes_new_extension_family_additive() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar, rvv]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "    riscv:\n"
        "      extension_families [rvv]\n"
        "      sort_order 30\n"
        "      backends:\n"
        "        cpp:\n"
        "          feature_flags false\n"
        '          target "riscv64-linux-gnu"\n'
        "        rust:\n"
        "          feature_flags false\n"
        '          target "riscv64gc-unknown-linux-gnu"\n'
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "extension rvv:\n"
        '  extension_name "rvv"\n'
        '  family "rvv"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    assert "TSL-CATALOG-INVALID-ENUM" not in {d.code for d in diagnostics}


def test_empty_backend_target_arch_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      backends:\n"
        "        rust:\n"
        '          target_arch ""\n'
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    assert "TSL-CATALOG-TARGET-FAMILIES-MALFORMED-TARGET-ARCH" in {
        diagnostic.code for diagnostic in diagnostics
    }


def test_target_family_typos_are_still_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar, rvv]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "extension typo:\n"
        '  extension_name "typo"\n'
        '  family "risc-v"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-INVALID-ENUM")
    assert "extension family 'risc-v'" in diagnostic.message
    assert "rvv" in diagnostic.message


def test_unknown_target_feature_spellings_and_uses_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  known_target_features [known]\n"
        "  target_feature_spellings:\n"
        '    typo "compiler-typo"\n'
        "  universal_extension_families [scalar]\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "  active_when:\n"
        "    target_features [active_typo]\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        requires [requires_typo]\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    messages = [diagnostic.message for diagnostic in diagnostics]
    assert any("target feature spelling 'typo'" in message for message in messages)
    assert any("active_when uses unknown target feature 'active_typo'" in message for message in messages)
    assert any("requires uses unknown target feature 'requires_typo'" in message for message in messages)


def test_missing_backend_spellings_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  f32 {type "float"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        backends=("cpp",),
    )

    assert [d.code for d in diagnostics] == ["TSL-CATALOG-MISSING-TYPE-SPELLING"]
    assert "si32" in diagnostics[0].message


def test_bad_extension_inheritance_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension child:\n"
            '  extension_name "child"\n'
            '  family "scalar"\n'
            "  inherits missing\n"
        )
    )

    assert "TSL-CATALOG-UNKNOWN-INHERITS" in {d.code for d in diagnostics}


def test_bad_extension_supersedes_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension child:\n"
            '  extension_name "child"\n'
            '  family "scalar"\n'
            "  supersedes [missing]\n"
        )
    )

    diagnostic = next(
        d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-SUPERSEDES"
    )
    assert "extension 'child' supersedes unknown extension 'missing'" in diagnostic.message


def test_extension_inheritance_cycles_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension a:\n"
        '  extension_name "a"\n'
        "  inherits b\n"
        "extension b:\n"
        '  extension_name "b"\n'
        "  inherits a\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    a:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    assert "TSL-CATALOG-INHERITS-CYCLE" in {d.code for d in diagnostics}


def test_malformed_requires_shape_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        requires:\n"
        "          scalar:\n"
        "            default nope\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-MALFORMED-REQUIRES")
    assert "flag list" in diagnostic.message

def test_compiler_capability_requires_are_promoted_separately_from_target_features() -> None:
    catalog, diagnostics = _catalog_and_diagnostics(
        _base_source().replace(
            "        implementation:\n",
            "        requires:\n"
            "          target_features []\n"
            "          compiler:\n"
            "            cpp:\n"
            "              capabilities [elementwise_clzg]\n"
            "        implementation:\n",
        )
    )

    assert diagnostics == ()
    implementation = catalog.primitive("id").implementations[0]
    compiler_clause = next(
        clause for clause in implementation.requirements if clause.compiler
    )
    assert compiler_clause.flags == frozenset()
    assert compiler_clause.compiler[0].backend_id == "cpp"
    assert compiler_clause.compiler[0].capabilities == frozenset(
        {"elementwise_clzg"}
    )


@pytest.mark.parametrize(
    ("backend", "capability", "code"),
    [
        ("cpp", "missing_capability", "TSL-CATALOG-UNKNOWN-COMPILER-CAPABILITY"),
        ("missing_backend", "elementwise_clzg", "TSL-CATALOG-UNKNOWN-COMPILER-BACKEND"),
    ],
)
def test_unknown_compiler_requirement_is_diagnosed(
    backend: str,
    capability: str,
    code: str,
) -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            "        implementation:\n",
            "        requires:\n"
            "          compiler:\n"
            f"            {backend}:\n"
            f"              capabilities [{capability}]\n"
            "        implementation:\n",
        )
    )

    assert code in {diagnostic.code for diagnostic in diagnostics}

def test_malformed_call_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "call<primitive=set_zero trailing>(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-CALL-SELECTOR")
    assert "malformed call selector" in diagnostic.message


def test_malformed_let_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "let<type>(AliasOnly); complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-LET")
    assert "let<type>(Name, type-expression)" in diagnostic.message


def test_runtime_array_var_body_region_is_accepted() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            'tsil "complete(data);"',
            (
                'tsil "var<runtime_array>('
                'type(base::in), tmp, value(vector::runtime_length)'
                '); complete(data);"'
            ),
        )
    )

    assert diagnostics == ()


@pytest.mark.parametrize(
    "body",
    [
        "var<runtime_array>(type(base::in), tmp); complete(data);",
        (
            "var<runtime_array>("
            "type(base::in), tmp[0], value(vector::runtime_length)"
            "); complete(data);"
        ),
        "var<unknown>(tmp, data); complete(data);",
    ],
)
def test_malformed_var_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        _base_source().replace('tsil "complete(data);"', f'tsil "{body}"')
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-VAR")
    assert "malformed var declaration" in diagnostic.message


def test_malformed_intrin_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(intrin<add, suffix=epi32>(data));"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-INTRIN-SELECTOR")
    assert "build" in diagnostic.message


def test_query_region_selectors_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(cast<static>(type<generation>(base::in), value<backend>(uninit::array)));"\n'
    )

    messages = [
        diagnostic.message
        for diagnostic in diagnostics
        if diagnostic.code == "TSL-BODY-BAD-QUERY-SELECTOR"
    ]
    assert len(messages) == 2
    assert any("use `type(query)`" in message for message in messages)
    assert any("use `value(query)`" in message for message in messages)


@pytest.mark.parametrize(
    "body",
    [
        "complete(select_expr<generation>(a, b, c));",
        "complete(select_expr(a, b));",
        "complete(select_expr(a, b, c, d));",
    ],
)
def test_malformed_select_expr_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        _base_source().replace('tsil "complete(data);"', f'tsil "{body}"')
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-SELECT-EXPR")
    assert "select_expr(condition, if_true, if_false)" in diagnostic.message


@pytest.mark.parametrize(
    "body",
    [
        "complete(mask<set:1>(data, 0));",
        "complete(mask<set>(data, 0, true));",
        "complete(mask<lane_true>(data));",
        "complete(mask<all>(data));",
        "complete(mask<test, integral>(data, 0));",
        "complete(mask<test, imask>(data));",
    ],
)
def test_malformed_mask_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        f'          tsil "{body}"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-MASK-SELECTOR")
    assert "malformed mask selector" in diagnostic.message


def test_array_set_body_region_is_accepted_with_nested_index() -> None:
    diagnostics = _diagnostics(
        _base_source().replace(
            'tsil "complete(data);"',
            (
                'tsil "array<set>(lanes, '
                'cast<static>(type(scalar::size), 0), data); complete(data);"'
            ),
        )
    )

    assert diagnostics == ()


@pytest.mark.parametrize(
    "body",
    [
        "array<get>(lanes, 0, data); complete(data);",
        "array<set>(lanes, 0); complete(data);",
        "array<set>(lanes, 0, data, extra); complete(data);",
        "array(lanes, 0, data); complete(data);",
    ],
)
def test_malformed_array_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        _base_source().replace('tsil "complete(data);"', f'tsil "{body}"')
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-ARRAY")
    assert "array<set>(array, index, value)" in diagnostic.message


@pytest.mark.parametrize(
    ("body", "keyword", "reason"),
    [
        ("call<primitive=set_zero(data);", "call", "unterminated selector"),
        ("call<primitive=set_zero>;", "call", "missing argument payload"),
        ("call<primitive=set_zero>(data;", "call", "unterminated argument payload"),
        (
            "if<generation>(value(type::is_integral)) complete(data);",
            "if",
            "missing block",
        ),
        (
            "switch<compile>(scale) { 1 { complete(data); } }",
            "switch",
            "malformed switch arms",
        ),
    ],
)
def test_malformed_tsil_region_shells_are_diagnosed(
    body: str, keyword: str, reason: str
) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        f'          tsil "{body}"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-MALFORMED-REGION")
    assert f"malformed TSIL region '{keyword}'" in diagnostic.message
    assert reason in diagnostic.message
    assert diagnostic.location is not None


@pytest.mark.parametrize(
    "body",
    [
        "complete(address<unknown>(data));",
        "complete(address<of>());",
        "complete(address<borrow_mut>(data, data));",
    ],
)
def test_malformed_address_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        _base_source().replace('tsil "complete(data);"', f'tsil "{body}"')
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-ADDRESS")
    assert "address<of|borrow_mut>(expr)" in diagnostic.message


def test_legacy_pointer_cast_shell_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(cast<reinterpret>(type(base::in) const *, data));"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-CAST")
    assert "cast<reinterpret, type=ptr|const_ptr>" in diagnostic.message


def test_primitive_source_uses_explicit_pointer_cast_selectors() -> None:
    legacy_pointer_cast = re.compile(r"cast<reinterpret>\(\s*[^,]*\*,", re.S)
    offenders = [
        str(path)
        for path in Path("tsldata/primitives").rglob("*.tsl")
        if legacy_pointer_cast.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


@pytest.mark.parametrize(
    ("signature", "code"),
    [
        ("lanes<s>:=v", "TSL-CATALOG-LANE-LIST-RESULT"),
        ("v:=(lanes<>)", "TSL-CATALOG-LANE-LIST-EMPTY"),
        ("v:=(lanes<v>)", "TSL-CATALOG-LANE-LIST-ELEMENT"),
        ("v:=(lanes<lanes<s>>)", "TSL-CATALOG-LANE-LIST-NESTED"),
    ],
)
def test_lane_list_signature_validation_reports_rejected_shapes(
    signature: str, code: str
) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        f"prim<{signature}> id(values):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(values);"\n'
    )

    assert code in {diagnostic.code for diagnostic in diagnostics}


def test_machine_profile_validation_reports_shape_errors(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "dup", "target_features": "sse", "extra": true},\n'
        '    {"name": "dup", "target_features": "avx"}\n'
        '  ],\n'
        '  "strange": [],\n'
        '  "generic": [{"name": "scalar", "target_features": "NOSIMD-INVALID", "alternatives": []}]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert {
        "TSL-PROFILE-DUPLICATE-NAME",
        "TSL-PROFILE-INVALID-FAMILY",
        "TSL-PROFILE-MALFORMED-ALTERNATIVES",
        "TSL-PROFILE-UNKNOWN-FIELD",
    } <= codes


def test_machine_profile_duplicate_json_keys_are_diagnosed(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{"x86": [{"name": "first", "name": "second", "target_features": "sse"}]}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert "TSL-PROFILE-DUPLICATE-KEY" in {d.code for d in result.diagnostics}


def test_machine_profile_target_features_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{"x86": [{"name": "bad", "target_features": ["sse"]}]}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert "TSL-PROFILE-MALFORMED-TARGET-FEATURES" in {
        d.code for d in result.diagnostics
    }


def test_machine_profile_features_and_overrides_use_target_feature_catalog(
    tmp_path: Path,
) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{"x86": [{"name": "demo", "target_features": "known typo", '
        '"alternatives": {"known": "profile-known", "unused": "profile-unused"}}]}\n',
        encoding="utf-8",
    )
    families = TargetFamilyCatalog(
        profile_families={"x86": ProfileFamilyCapability("x86")},
        target_features={
            "known": TargetFeatureCapability(
                "known",
                default_spelling="source-known",
                backend_spellings={"cpp": "cpp-known"},
            )
        },
    )

    result = load_machine_profiles_checked(path, families)

    assert {diagnostic.code for diagnostic in result.diagnostics} >= {
        "TSL-PROFILE-UNKNOWN-ALTERNATIVE",
        "TSL-PROFILE-UNKNOWN-TARGET-FEATURE",
    }
    profile = result.profiles["demo"]
    assert profile.feature_spelling("known", "cpp") == "profile-known"


def test_machine_profile_compile_modes_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{"x86": [{"name": "bad", "target_features": "sse", "compile_modes": ["mode"]}]}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert "TSL-PROFILE-MALFORMED-COMPILE-MODES" in {
        d.code for d in result.diagnostics
    }


def test_machine_profile_backend_flags_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "aarch64": [\n'
        '    {"name": "neon", "target_features": "neon", "backend_flags": {"cpp": []}},\n'
        '    {"name": "bad", "target_features": "sve", "backend_flags": {"cpp": "-march=armv8-a+sve"}}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path)

    assert result.profiles["neon"].flags_for_backend("cpp") == ()
    assert "TSL-PROFILE-MALFORMED-FIELD" in {d.code for d in result.diagnostics}


def test_machine_profile_compiler_roles_and_build_fallback_are_typed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        "{\n"
        '  "x86": [\n'
        '    {"name": "first", "target_features": "sse", '
        '"backend_compiler_roles": {"cpp": "oneapi-cpp"}, '
        '"default_build_fallback": true},\n'
        '    {"name": "second", "target_features": "sse", '
        '"default_build_fallback": true, "auto_detect_gate": "fpga"}\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path)

    assert result.profiles["first"].compiler_role_for_backend("cpp") == "oneapi-cpp"
    assert result.profiles["first"].default_build_fallback
    assert "TSL-PROFILE-MULTIPLE-BUILD-FALLBACKS" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "TSL-PROFILE-GATED-BUILD-FALLBACK" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


def test_machine_profile_auto_detect_gate_is_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "good", "target_features": "sse", "auto_detect_gate": "fpga"},\n'
        '    {"name": "bad", "target_features": "sse", "auto_detect_gate": "two tokens"}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path)

    assert result.profiles["good"].auto_detect_gate == "fpga"
    assert "TSL-PROFILE-MALFORMED-FIELD" in {d.code for d in result.diagnostics}


def test_machine_profile_runner_metadata_is_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "avx2", "target_features": "avx avx2", '
        '"runner": {"kind": "sde", "profile": "-hsw"}},\n'
        '    {"name": "bad", "target_features": "avx", "runner": []}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    leading_dash = next(
        d
        for d in result.diagnostics
        if d.code == "TSL-PROFILE-MALFORMED-RUNNER" and "'-hsw'" in d.message
    )
    assert "avx2" in leading_dash.message
    assert result.profiles["avx2"].runner is None
    runner_errors = [
        d for d in result.diagnostics if d.code == "TSL-PROFILE-MALFORMED-RUNNER"
    ]
    assert len(runner_errors) == 2


def test_machine_profile_valid_runners_are_preserved_verbatim(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "avx2", "target_features": "avx avx2", '
        '"runner": {"kind": "sde", "profile": "hsw"}}\n'
        '  ],\n'
        '  "aarch64": [\n'
        '    {"name": "neon", "target_features": "neon", '
        '"runner": {"kind": "qemu-aarch64", "profile": "cortex-a76", '
        '"args": ["-cpu"]}}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert result.diagnostics == ()
    sde = result.profiles["avx2"].runner
    assert sde is not None and (sde.kind, sde.profile) == ("sde", "hsw")
    qemu = result.profiles["neon"].runner
    assert qemu is not None and (qemu.kind, qemu.profile, qemu.args) == (
        "qemu-aarch64",
        "cortex-a76",
        ("-cpu",),
    )


def test_machine_profile_runner_kinds_come_from_target_families(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "bad", "target_features": "sse", '
        '"runner": {"kind": "qemu-aarch64", "profile": "cortex-a76"}}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    diagnostic = next(
        d for d in result.diagnostics if d.code == "TSL-PROFILE-UNSUPPORTED-RUNNER"
    )
    assert "declared for family 'x86'" in diagnostic.message
    assert "sde" in diagnostic.message


def _param_types_catalog_and_diagnostics(condition_key: str):
    text = (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v>[aligned=*] id(data):\n"
        "  param_types:\n"
        "    data:\n"
        f'      {condition_key} "type(base::in)"\n'
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), text, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return result.catalog, (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )


@pytest.mark.parametrize(
    ("condition_key", "accepted"),
    (
        # Accepted grammar: the unconditional default rule (bare or quoted) and
        # quoted `if attribute=value` conditions.
        ("default", True),
        ('"default"', True),
        ('"if aligned=true"', True),
        ('"if aligned=false"', True),
        ('"if  aligned=true"', True),
        # Rejected grammar: anything else must be diagnosed by validation and
        # dropped by promotion — through the same shared parser.
        ("defaults", False),
        ('"if aligned = true"', False),
        ('"if aligned=*"', False),
        ('"if aligned="', False),
        ('"if =true"', False),
        ('"iff aligned=true"', False),
        ('"if 1aligned=true"', False),
        ('"if aligned=true "', False),
    ),
)
def test_param_type_condition_acceptance_and_promotion_agree(
    condition_key: str, accepted: bool
) -> None:
    """Validator acceptance and builder promotion share one condition grammar."""

    catalog, diagnostics = _param_types_catalog_and_diagnostics(condition_key)

    rejected = any(
        diagnostic.code == "TSL-CATALOG-PARAM-TYPES-BAD-CONDITION"
        for diagnostic in diagnostics
    )
    variants = catalog.primitives_named("id", unmasked=False)
    assert variants
    promoted_rule_counts = {len(variant.param_type_rules) for variant in variants}

    assert rejected == (not accepted)
    assert promoted_rule_counts == ({1} if accepted else {0})


def test_validator_kind_sets_derive_from_typed_catalog_kinds() -> None:
    from typing import get_args

    from tslc.catalog import model
    from tslc.catalog.validation import _schema_primitives, _schema_tests
    from tslc.catalog.validation import _schema_extensions as schema_extensions

    assert _schema_primitives.KNOWN_GENERIC_PARAM_KINDS == frozenset(
        get_args(model.GenericParamKind)
    ) == {"bool", "int", "simd_type"}
    assert _schema_tests.KNOWN_TEST_ROLES == frozenset(
        get_args(model.TestCaseRole)
    ) == {"value", "compile", "runtime_failure", "compile_failure"}
    assert schema_extensions.KNOWN_MASK_POLICY_KINDS == frozenset(
        get_args(model.MaskPolicyKind)
    ) == {
        "bool",
        "boolean_lane_vector",
        "comparison_lane_vector",
        "exact_lane_bitmask",
        "lane_bitmask",
        "native_predicate",
        "native_predicate_by_type",
        "native_predicate_by_lanes",
    }
    assert schema_extensions.KNOWN_IMASK_POLICY_KINDS == frozenset(
        get_args(model.ImaskPolicyKind)
    ) == {"lane_bitmask", "same_as_mask_type", "unsigned_scalar"}
    assert frozenset(get_args(model.TestArgKind)) == {"vector", "mask", "scalar"}


def test_mask_spelling_by_type_rejects_unknown_scalar_tags() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      backends:\n"
        "        cpp:\n"
        "          feature_flags false\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        "  extension_name \"scalar\"\n"
        "  family \"scalar\"\n"
        "  cpp:\n"
        "    supported true\n"
        "  mask_type_policy:\n"
        "    kind \"native_predicate_by_type\"\n"
        "    backend_spelling_by_type:\n"
        "      cpp:\n"
        "        typo \"bad_mask_t\"\n"
        "language cpp:\n"
        "  s32 {type \"int32_t\"}\n"
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        "          tsil \"complete(data);\"\n"
    )

    assert "TSL-CATALOG-INVALID-ENUM" in {
        diagnostic.code for diagnostic in diagnostics
    }
