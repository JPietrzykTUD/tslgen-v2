"""Catalog/profile validation catches source-data shape errors before lowering."""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.target_families import ProfileFamilyCapability, TargetFamilyCatalog
from tslc.catalog.validation import validate_catalog
from tslc.catalog.validation._schema_extensions import known_extension_fields
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import SourceLocation
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _diagnostics(text: str, *, backends: tuple[str, ...] = ("cpp", "rust")):
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), text, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return (*result.diagnostics, *validate_catalog(result.catalog, parsed, required_backends=backends))


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


def test_extension_backend_compile_guards_are_validated() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension guarded:\n"
            '  extension_name "guarded"\n'
            '  family "x86"\n'
            "  active_when:\n"
            "    target_features [sse]\n"
            "    compile_modes [demo_mode]\n"
            "  cpp:\n"
            "    supported true\n"
            "    compile_guards:\n"
            "      demo:\n"
            '        macro "TSL_DEMO"\n'
            "        typo true\n"
            "      broken:\n"
            "        equals 1\n"
        )
    )

    codes = {diagnostic.code for diagnostic in diagnostics}
    assert "TSL-CATALOG-UNKNOWN-FIELD" in codes
    assert "TSL-CATALOG-MALFORMED-COMPILE-GUARD" in codes


def test_extension_backend_dataparallel_inference_is_boolean() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension overlay:\n"
            '  extension_name "overlay"\n'
            '  family "x86"\n'
            "  cpp:\n"
            "    supported true\n"
            '    header_group "clang"\n'
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

    assert result.profiles["avx2"].runner is not None
    assert result.profiles["avx2"].runner.kind == "sde"
    assert result.profiles["avx2"].runner.profile == "hsw"
    assert "TSL-PROFILE-MALFORMED-RUNNER" in {d.code for d in result.diagnostics}


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
