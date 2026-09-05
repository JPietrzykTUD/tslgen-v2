"""Catalog promotion: type groups, extensions, type spellings."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.backend.cpp_compiler_capabilities import (
    cpp_extension_compiler_ids,
    cpp_extension_header_group,
)
from tslc.catalog import builder as builder_module
from tslc.catalog._builder_extensions import _build_extension
from tslc.catalog._builder_implementations import _implementations_from_entries
from tslc.catalog._builder_primitives import _build_primitives
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    PrimitiveValueMode,
    TargetConstraint,
)
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def test_catalog_builder_keeps_domain_promotion_boundaries() -> None:
    assert builder_module.CatalogBuilder.__module__ == "tslc.catalog.builder"
    assert _build_extension.__module__ == "tslc.catalog._builder_extensions"
    assert (
        _implementations_from_entries.__module__
        == "tslc.catalog._builder_implementations"
    )
    assert _build_primitives.__module__ == "tslc.catalog._builder_primitives"


def test_type_groups_expand(catalog: Catalog) -> None:
    assert catalog.type_groups["?i?"] == (
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    )
    assert catalog.type_groups["f?"] == ("f32", "f64")
    assert catalog.type_group_contains("?i?", "ui32")
    assert not catalog.type_group_contains("f?", "si8")


def test_avx2_and_avx2_vl_are_distinct_extensions(catalog: Catalog) -> None:
    avx2 = catalog.extensions["avx2"]
    avx2_vl = catalog.extensions["avx2_vl"]
    # Distinct identities (keyed by block name), even though they share an ISA name.
    assert avx2.name == "avx2"
    assert avx2_vl.name == "avx2_vl"
    # The real avx2 compose metadata must not be clobbered by avx2_vl.
    assert avx2.compose_prefix["cpp"] == "_mm256_"
    assert avx2.compose_suffix_by_type["si32"] == "epi32"


def test_scalar_extension_has_no_intrinsic_compose(catalog: Catalog) -> None:
    scalar = catalog.extensions["scalar"]
    assert scalar.family == "scalar"
    assert scalar.compose_prefix == {}  # scalar has no intrinsic prefix


def test_target_constraint_matches_exact_double_width(catalog: Catalog) -> None:
    constraint = TargetConstraint(family="same_as", width="twice_as_wide")

    assert constraint.matches(catalog.extensions["sse"], catalog.extensions["avx2"])
    assert constraint.matches(catalog.extensions["avx2"], catalog.extensions["avx512"])
    assert not constraint.matches(
        catalog.extensions["sse"], catalog.extensions["avx512"]
    )
    assert not constraint.matches(
        catalog.extensions["neon"], catalog.extensions["avx2"]
    )


@pytest.mark.parametrize(("name", "operation"), (("mul_imm", "mul"), ("mod_imm", "mod")))
def test_immediate_arithmetic_composes_semantic_primitives(
    catalog: Catalog, name: str, operation: str
) -> None:
    variants = catalog.primitives_named(name, unmasked=False)
    assert variants
    for primitive in variants:
        for implementation in primitive.implementations:
            assert f"call<primitive={operation}" in implementation.body_text
            assert "call<primitive=set1" in implementation.body_text
            assert "intrin<" not in implementation.body_text
            assert "helper<arith_" not in implementation.body_text


def test_insert_value_has_semantic_index_contract(catalog: Catalog) -> None:
    primitive = catalog.primitive("insert_value")
    assert primitive is not None
    assert primitive.signature == "v:=(v,s)"
    params = tuple(
        (param.name, param.kind, param.default) for param in primitive.generic_params
    )
    assert params == (
        ("Index", "int", "0"),
    )


def test_native_extension_register_metadata_promoted(catalog: Catalog) -> None:
    neon = catalog.extensions["neon"]
    assert neon.direct_vector_register_type("cpp", "si32") == "int32x4_t"
    assert (
        neon.direct_vector_register_type("rust", "si32")
        == "core::arch::aarch64::int32x4_t"
    )
    assert neon.headers_for_backend("cpp") == ("arm_neon.h",)


def test_type_spellings_normalized(catalog: Catalog) -> None:
    assert catalog.type_spellings["cpp"]["s32"] == "int32_t"
    assert catalog.type_spellings["cpp"]["f32"] == "float"
    assert catalog.type_spellings["rust"]["s32"] == "i32"
    assert catalog.type_spellings["rust"]["u64"] == "u64"


def test_rust_runtime_has_one_asset_owned_source(catalog: Catalog) -> None:
    assert "preamble" not in catalog.translations["rust"]


def test_to_integral_tests_default_to_unqualified_baseline(catalog: Catalog) -> None:
    primitive = catalog.primitive("to_integral")
    assert primitive is not None

    baseline_types = {
        case.type_tag
        for case in primitive.tests
        if case.extension is None and case.tags == ("basic",)
    }
    assert baseline_types == {
        "ui8",
        "ui16",
        "ui32",
        "ui64",
        "si8",
        "si16",
        "si32",
        "si64",
        "f32",
        "f64",
    }
    assert any(
        case.extension is None and case.type_tag == "ui32" and case.tags == ("zero",)
        for case in primitive.tests
    )
    assert all(
        "wide" in case.tags
        for case in primitive.tests
        if case.extension == "avx512"
    )
    assert all(
        "scalable" in case.tags
        for case in primitive.tests
        if case.extension == "sve"
    )


def test_bracketed_type_group_membership(catalog: Catalog) -> None:
    # hadd uses explicit type-list selectors like [si32, ui32].
    assert catalog.type_group_contains("[si32, ui32]", "si32")
    assert not catalog.type_group_contains("[si32, ui32]", "f32")
    assert catalog.type_group_specificity("[si32, ui32]") == 2
    assert catalog.type_group_specificity("f64") == 1  # bare concrete tag
    assert catalog.type_group_specificity("arith") == 10


def _flat_flags(impl):
    assert len(impl.requirements) == 1 and impl.requirements[0].type_group is None
    return impl.requirements[0].flags


def test_requirements_promoted_flat(catalog: Catalog) -> None:
    add = catalog.primitive("add")
    by_path = {(i.extension, i.type_group): i for i in add.implementations}
    assert _flat_flags(by_path[("avx2", "?i?")]) == frozenset({"avx", "avx2"})
    assert _flat_flags(by_path[("avx2", "f?")]) == frozenset({"avx"})
    assert _flat_flags(by_path[("sse", "?i?")]) == frozenset({"sse2"})
    assert _flat_flags(by_path[("scalar", "arith")]) == frozenset()


def test_nested_requires_promoted_per_type_group(catalog: Catalog) -> None:
    # avx512 add's ?i? body has a nested `requires:` map: idqword needs avx512f,
    # bword needs avx512f + avx512bw.
    add = catalog.primitive("add")
    nested = next(
        i for i in add.implementations if i.extension == "avx512" and i.type_group == "?i?"
    )
    clauses = {c.type_group: c.flags for c in nested.requirements}
    assert clauses["idqword"] == frozenset({"avx512f"})
    assert clauses["bword"] == frozenset({"avx512f", "avx512bw"})


def test_extension_inheritance_activation_and_supersession(catalog: Catalog) -> None:
    avx2_vl = catalog.extensions["avx2_vl"]
    assert avx2_vl.inherits == "avx2"
    assert avx2_vl.isa_name == "avx2"  # emitted as avx2; _vl is internal only
    assert avx2_vl.active_when.target_features == frozenset(
        {"avx2", "avx512f", "avx512vl"}
    )
    assert avx2_vl.supersedes == frozenset({"avx2"})
    # compose metadata is inherited (flattened) from avx2.
    assert avx2_vl.compose_prefix["cpp"] == "_mm256_"
    assert avx2_vl.family == "x86"
    assert avx2_vl.metadata.backend["rust"].arch_module == "x86_64"
    assert catalog.extension_chain("avx2_vl") == ("avx2_vl", "avx2")

    sve512 = catalog.extensions["sve512"]
    assert sve512.inherits == "sve"
    assert sve512.isa_name == "sve512"
    assert sve512.family == "arm"
    assert sve512.vector_bits == 512
    assert sve512.vector_bits_kind == "fixed"
    assert sve512.active_when.target_features == frozenset({"sve"})
    assert sve512.active_when.compile_modes == frozenset({"sve_vector_bits_512"})
    assert sve512.supersedes == frozenset({"sve"})
    assert catalog.extension_chain("sve512") == ("sve512", "sve")
    assert sve512.metadata.backend["cpp"].compiler_capabilities == (
        "sve_vector_bits_512",
    )

    oneapi = catalog.extensions["oneapi_fpga"]
    assert oneapi.active_when.target_features == frozenset()
    assert oneapi.active_when.compile_modes == frozenset({"oneapi_fpga"})
    assert oneapi.mask_policy.kind == "exact_lane_bitmask"
    assert oneapi.mask_policy.spelling("cpp") == "ac_int<LANES, false>"
    assert oneapi.imask_policy.kind == "same_as_mask_type"
    assert oneapi.headers_for_backend("cpp") == (
        "sycl/ext/intel/ac_types/ac_int.hpp",
    )
    assert (
        sve512.direct_vector_register_type("cpp", "si32")
        == "svint32_t __attribute__((arm_sve_vector_bits(512)))"
    )
    assert (
        sve512.mask_policy.spelling("cpp")
        == "svbool_t __attribute__((arm_sve_vector_bits(512)))"
    )


def test_extension_backend_support_is_explicit_and_inherited(catalog: Catalog) -> None:
    avx2_vl = catalog.extensions["avx2_vl"]
    sve = catalog.extensions["sve"]
    rtl = catalog.extensions["oneapi_fpga_rtl"]

    assert avx2_vl.supports_backend("cpp")
    assert avx2_vl.supports_backend("rust")
    assert not avx2_vl.supports_backend("zig")
    assert sve.supports_backend("cpp")
    assert not sve.supports_backend("rust")
    assert not rtl.supports_backend("cpp")


def test_extension_compiler_metadata_is_promoted(catalog: Catalog) -> None:
    avx2 = catalog.extensions["avx2"]
    neon = catalog.extensions["neon"]
    sve = catalog.extensions["sve"]

    assert avx2.metadata.native_sort_order == 300
    assert avx2.headers_for_backend("cpp") == ("immintrin.h",)
    assert avx2.metadata.backend["rust"].type_name == "Avx2"
    assert avx2.metadata.backend["rust"].arch_module == "x86_64"
    assert neon.metadata.backend["rust"].arch_module == "aarch64"
    assert sve.runtime_lane_count["cpp"] == "svcntb() / sizeof({base_type})"


def test_boolean_wildcard_attributes_expand_to_concrete_variants() -> None:
    source = SourceDocument(
        Path("wildcard_fixture.tsl"),
        (
            "types:\n"
            "  ints {types [si32]}\n"
            "extension scalar:\n"
            '  extension_name "scalar"\n'
            '  family "scalar"\n'
            "prim<v:=v>[aligned=*, packed=*, value=zero] wtest(data):\n"
            "  impls:\n"
            "    scalar:\n"
            "      ints:\n"
            "        implementation:\n"
            '          tsil "complete(data);"\n'
        ),
        "d",
        "tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((source,))
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None

    variants = result.catalog.primitives_named("wtest")
    combos = {
        (p.attributes["aligned"], p.attributes["packed"]) for p in variants
    }
    assert combos == {
        ("true", "true"),
        ("true", "false"),
        ("false", "true"),
        ("false", "false"),
    }
    assert len(variants) == 4
    assert all(p.attributes["value"] == "zero" for p in variants)
    assert all(p.value_mode is PrimitiveValueMode.ZERO for p in variants)
    bodies = {
        tuple(impl.body_text for impl in p.implementations) for p in variants
    }
    assert len(bodies) == 1


@pytest.mark.parametrize(
    ("primary_line", "declares_primary"),
    (("", False), ("    primary false\n", False), ("    primary true\n", True)),
)
def test_primitive_overload_is_promoted_with_source_spans(
    primary_line: str,
    declares_primary: bool,
) -> None:
    source = SourceDocument(
        Path("primitive_overload_fixture.tsl"),
        (
            "prim<v:=(v,s)> demo(data, count):\n"
            "  overload:\n"
            "    axis count_distribution\n"
            "    value uniform\n"
            f"{primary_line}"
        ),
        "d",
        "tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((source,))
    assert parsed.diagnostics == ()
    assert parsed.documents[0].primitives[0].fields_by_name("overload")[0].kind == (
        "overload"
    )
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None

    primitive = result.catalog.primitive("demo")
    assert primitive is not None and primitive.overload is not None
    assert primitive.overload.axis == "count_distribution"
    assert primitive.overload.value == "uniform"
    assert primitive.overload.declares_primary is declares_primary
    assert primitive.overload.source is not None
    assert primitive.overload.axis_source is not None
    assert primitive.overload.value_source is not None
    assert (primitive.overload.primary_source is not None) is bool(primary_line)


def test_extension_inheritance_respects_explicit_false_and_empty_overrides() -> None:
    source = SourceDocument(
        Path("extension_inheritance_fixture.tsl"),
        """extension parent:
  extension_name "parent"
  family "generic_like"
  vector_bits "sized"
  cpp:
    supported true
  rust:
    supported true
  size_bits [128, 256]
  unroll_variants true
  mask_type_policy:
    kind "native_predicate"
    cpp "parent_mask"
  integral_mask_type_policy:
    kind "same_as_mask_type"

extension child:
  extension_name "child"
  inherits "parent"
  rust:
    supported false
  size_bits []
  unroll_variants false
  mask_type_policy:
    kind "lane_bitmask"
  integral_mask_type_policy:
    kind "lane_bitmask"
""",
        "d",
        "tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((source,))
    assert parsed.diagnostics == ()
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None

    child = result.catalog.extensions["child"]
    assert child.supports_backend("cpp")
    assert not child.supports_backend("rust")
    assert child.size_bits == ()
    assert not child.unroll_variants
    assert child.mask_policy.kind == "lane_bitmask"
    assert child.imask_policy.kind == "lane_bitmask"


def test_machine_profiles_loaded(machine_profiles) -> None:
    assert machine_profiles["scalar"].features == frozenset()
    assert "avx2" in machine_profiles["avx2"].features
    assert "avx2" not in machine_profiles["avx"].features
    assert "avx512f" in machine_profiles["skylake"].features
    assert machine_profiles["avx2"].feature_spelling("sse4_1", "cpp") == "sse4.1"
    assert machine_profiles["avx2"].feature_spelling("rdrand", "cpp") == "rdrnd"
    assert (
        machine_profiles["icelake_rockerlake"].feature_spelling(
            "avx512_vpclmulqdq", "rust"
        )
        == "vpclmulqdq"
    )
    assert machine_profiles["neon"].flags_for_backend("cpp") == ()
    assert machine_profiles["sve"].features == frozenset({"sve"})
    assert machine_profiles["sve"].flags_for_backend("cpp") == ("-mcpu=a64fx",)
    assert machine_profiles["sve128"].runner is not None
    assert (
        machine_profiles["sve128"].runner.profile
        == "max,sve=on,sve128=on,sve256=off,sve512=off"
    )
    assert machine_profiles["sve256"].runner is not None
    assert (
        machine_profiles["sve256"].runner.profile
        == "max,sve=on,sve128=on,sve256=on,sve512=off"
    )
    assert machine_profiles["sve512"].features == frozenset({"sve"})
    assert machine_profiles["sve512"].compile_modes == frozenset(
        {"sve_vector_bits_512"}
    )
    assert machine_profiles["sve512"].auto_detect_gate is None
    assert machine_profiles["sve512"].flags_for_backend("cpp") == (
        "-mcpu=a64fx",
        "-msve-vector-bits=512",
    )
    assert machine_profiles["skylake-oneapi"].compile_modes == frozenset(
        {"oneapi_fpga"}
    )
    assert machine_profiles["skylake-oneapi"].auto_detect_gate == "oneapi_fpga"
    assert (
        machine_profiles["skylake-oneapi"].compiler_role_for_backend("cpp")
        == "oneapi-cpp"
    )
    assert machine_profiles["scalar"].default_build_fallback
    assert machine_profiles["wasm32-simd128"].family == "wasm32"
    assert machine_profiles["wasm32-simd128"].features == frozenset({"simd128"})
    assert machine_profiles["wasm32-simd128"].flags_for_backend("cpp") == ()
    assert machine_profiles["wasm32-simd128"].runner is not None
    assert machine_profiles["wasm32-simd128"].runner.kind == "wasmtime"


def test_target_families_promoted(catalog: Catalog) -> None:
    families = catalog.target_families

    assert families.known_extension_families >= {
        "scalar",
        "generic_like",
        "x86",
        "arm",
        "cuda",
        "wasm",
    }
    assert families.universal_extension_families == frozenset(
        {"scalar", "generic_like", "compiler_builtin"}
    )
    assert families.extension_family("scalar").implementation_fallback
    assert not families.extension_family(
        "scalar"
    ).requires_declared_vector_register
    assert families.extension_family("generic_like").implementation_fallback
    assert not families.extension_family("compiler_builtin").free_function_owner
    assert families.extension_family("x86").index_vector_register
    assert families.extension_family("scalar").documented_sort_order == 0
    assert families.extension_family("generic_like").documented_family == "generic"
    assert families.extension_family("generic_like").documented_sort_order == 1
    assert families.extension_family("arm").documented_family == "aarch64"
    assert families.extension_family("arm").documented_sort_order == 20
    assert families.profile_families["x86"].backend("rust").target_arch == "x86_64"
    assert (
        families.profile_families["aarch64"].backend("rust").target_arch
        == "aarch64"
    )
    assert families.profile_families["wasm32"].backend("rust").target_arch == "wasm32"
    sse4_1 = families.target_feature("sse4_1")
    rdrand = families.target_feature("rdrand")
    assert sse4_1 is not None and sse4_1.spelling("cpp") == "sse4.1"
    assert rdrand is not None and rdrand.spelling("cpp") == "rdrnd"
    assert rdrand.spelling("rust") == "rdrand"
    assert families.profile_families["generic"].native_without_runner
    assert families.profile_families["x86"].extension_families == frozenset({"x86"})
    assert families.profile_families["aarch64"].extension_families == frozenset({"arm"})
    assert families.profile_families["wasm32"].extension_families == frozenset({"wasm"})
    assert families.profile_families["x86"].runner_kinds == frozenset({"sde"})
    assert families.profile_families["aarch64"].runner_kinds == frozenset(
        {"qemu-aarch64"}
    )
    assert families.profile_families["wasm32"].runner_kinds == frozenset({"wasmtime"})
    assert families.profile_families["wasm32"].backend("cpp").target == "wasm32-wasip1"
    assert families.profile_families["wasm32"].backend("rust").target == "wasm32-wasip1"

    assert catalog.extensions["sve"].metadata.documentation_width == "SVE"
    assert catalog.extensions["sve512"].metadata.documentation_width == "SVE"
    assert catalog.extensions["neon"].family_capability.documented_family == "aarch64"


def test_overload_registry_promoted_from_source(catalog: Catalog) -> None:
    registry = catalog.overload_registry

    assert tuple(registry.axes) == ("count_distribution", "payload_extent")
    assert tuple(registry.axes["count_distribution"].values) == (
        "per_lane",
        "uniform",
    )
    assert registry.value("count_distribution", "uniform") is not None
    assert registry.value("count_distribution", "uniform").operand_kinds == (
        "s",
        "sImm",
    )
    assert registry.accepts_operand_kind("count_distribution", "per_lane", "v")
    assert not registry.accepts_operand_kind("payload_extent", "scalar", "v")
    assert registry.axes["payload_extent"].source is not None
    assert registry.axes["payload_extent"].values["vector"].source is not None


def test_overload_annotations_preserve_corpus_inventory(catalog: Catalog) -> None:
    assert len(catalog.primitives) == 185
    authored_sources = {primitive.source for primitive in catalog.primitives}
    assert None not in authored_sources
    assert len(authored_sources) == 173

    annotated = tuple(
        primitive for primitive in catalog.primitives if primitive.overload is not None
    )
    assert {primitive.name for primitive in annotated} == {
        "shift_left",
        "shift_left_wrapping",
        "shift_right",
        "shift_right_wrapping",
        "store",
    }
    assert len({primitive.source for primitive in annotated}) == 14
    assert all(
        primitive.overload is not None
        for primitive in catalog.primitives
        if primitive.name
        in {
            "shift_left",
            "shift_left_wrapping",
            "shift_right",
            "shift_right_wrapping",
            "store",
        }
    )


def test_clang_vector_extensions_are_cpp_opt_in_overlays(catalog: Catalog) -> None:
    for width in (128, 256, 512):
        extension = catalog.extensions[f"clang_v{width}"]
        assert extension.family == "compiler_builtin"
        assert extension.vector_bits == width
        assert extension.supports_backend("cpp")
        assert not extension.supports_backend("rust")
        assert extension.mask_policy.kind == "comparison_lane_vector"
        metadata = extension.metadata.backend["cpp"]
        assert metadata.compiler_capabilities == ("clang_vector_types",)
        assert cpp_extension_header_group(extension) == "clang"
        assert cpp_extension_compiler_ids(extension) == ("AppleClang", "Clang")
        assert not metadata.participates_in_dataparallel_inference

    for width in (128, 256, 512):
        extension = catalog.extensions[f"clang_v{width}_bool"]
        assert extension.family == "compiler_builtin"
        assert extension.vector_bits == width
        assert extension.supports_backend("cpp")
        assert not extension.supports_backend("rust")
        assert extension.mask_policy.kind == "boolean_lane_vector"
        assert extension.imask_policy.kind == "lane_bitmask"
        metadata = extension.metadata.backend["cpp"]
        assert metadata.compiler_capabilities == (
            "clang_vector_types",
            "ext_vector_type_boolean",
        )
        assert cpp_extension_header_group(extension) == "clang"
        assert cpp_extension_compiler_ids(extension) == ("AppleClang", "Clang")
        assert not metadata.participates_in_dataparallel_inference


def test_catalog_mappings_are_read_only(catalog: Catalog) -> None:
    add = catalog.primitive("add")
    assert add is not None
    avx2 = catalog.extensions["avx2"]
    avx512 = catalog.extensions["avx512"]

    with pytest.raises(TypeError):
        catalog.type_groups["new"] = ("si32",)  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.extensions["new"] = avx2  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.type_spellings["cpp"]["s32"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.translations["cpp"]["complete"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        add.attributes["mask"] = "zero"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx2.compose_prefix["cpp"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx2.compose_suffix_by_type["si32"] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx512.mask_policy.backend_spelling_by_lanes["cpp"][16] = "bad"  # type: ignore[index]
    with pytest.raises(TypeError):
        avx2.metadata.backend["new"] = avx2.metadata.backend["rust"]  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.target_families.profile_families["new"] = (  # type: ignore[index]
            catalog.target_families.profile_families["x86"]
        )
    with pytest.raises(TypeError):
        catalog.overload_registry.axes["new"] = (  # type: ignore[index]
            catalog.overload_registry.axes["payload_extent"]
        )
    with pytest.raises(TypeError):
        catalog.overload_registry.axes["payload_extent"].values["new"] = (  # type: ignore[index]
            catalog.overload_registry.axes["payload_extent"].values["scalar"]
        )


def test_machine_profile_mappings_are_read_only(machine_profiles) -> None:
    alternate_feature = "avx512_vpclmulqdq"
    with pytest.raises(TypeError):
        machine_profiles["new"] = MachineProfile(  # type: ignore[index]
            "new", "x86", frozenset(), {}
        )
    with pytest.raises(TypeError):
        machine_profiles["skylake"].alternatives[alternate_feature] = "bad"  # type: ignore[index]
