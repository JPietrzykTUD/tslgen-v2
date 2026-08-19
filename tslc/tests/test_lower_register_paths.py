"""Masked, SVE, and register-only lowering regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
)


@pytest.mark.parametrize("primitive", ["hadd", "hand", "hor"])
@pytest.mark.parametrize("type_tag", ["ui8", "ui16"])
def test_knl_masked_small_reductions_use_sse_quarter_composition(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["knl"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert lowered.body_text.count("extract") == 4
        assert "_mm512_" not in lowered.body_text
        assert "to_mask" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text

@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui8", "si32", "f32", "f64"])
def test_clang_masked_extrema_unroll_direct_lane_access(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.signature == "s:=(m,v)"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "vec[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "for " not in lowered.body_text

@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui8", "si32", "f32", "f64"])
def test_neon_masked_extrema_unroll_semantic_lane_extracts(
    catalog: Catalog, machine_profiles, primitive: str, type_tag: str
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["neon"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "neon"
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "vgetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text

@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_sve_masked_extrema_use_semantic_empty_mask_test(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["sve128"], primitive, (type_tag,)
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.signature == "s:=(m,v)"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "mask_population_count" in lowered.body_text
    assert "to_integral" not in lowered.body_text

@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("profile", ["sse2", "avx2", "knl"])
@pytest.mark.parametrize("type_tag", ["si8", "ui16", "si32", "ui64"])
def test_x86_masked_integer_extrema_avoid_array_fallback(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    type_tag: str,
) -> None:
    extension = {"sse2": "sse", "avx2": "avx2", "knl": "avx512"}[profile]
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text
        if profile == "knl" and type_tag in {"si32", "ui64"}:
            assert "mask_reduce" in lowered.body_text
        else:
            assert "select" in lowered.body_text

@pytest.mark.parametrize("primitive", ["hmax", "hmin"])
@pytest.mark.parametrize("profile", ["sse2", "avx2"])
@pytest.mark.parametrize("type_tag", ["f32", "f64"])
def test_x86_masked_float_extrema_unroll_native_lane_extracts(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    profile: str,
    type_tag: str,
) -> None:
    extension = "sse" if profile == "sse2" else "avx2"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and selected.primitive.signature == "s:=(m,v)"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "shuffle" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "for " not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["si8", "ui16", "si32", "ui64", "f32", "f64"])
def test_sve_extract_value_uses_semantic_singleton_lane_mask(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "extract_value", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::set1<" in lowered.body_text
    assert "svlastb_" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text

def test_sve_runtime_lane_counts_use_typed_query(catalog: Catalog) -> None:
    offenders: list[str] = []
    typed_query_bodies = 0
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            bodies = [implementation.body_text]
            bodies.extend(variant.body_text for variant in implementation.variants)
            for body in bodies:
                if "value(generic::runtime_length(" in body:
                    typed_query_bodies += 1
                if "intrin<svcntb>" in body:
                    offenders.append(
                        f"{primitive.name}:{'/'.join(implementation.selector_path)}"
                    )

    assert typed_query_bodies > 0
    assert offenders == []

def test_sve_plain_load_store_intrinsics_stay_in_owning_primitives(
    catalog: Catalog,
) -> None:
    offenders: list[str] = []
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            bodies = [implementation.body_text]
            bodies.extend(variant.body_text for variant in implementation.variants)
            for body in bodies:
                has_plain_load = any(
                    token in body for token in ("intrin<svld1>", "intrin<svld1,")
                )
                has_plain_store = any(
                    token in body for token in ("intrin<svst1>", "intrin<svst1,")
                )
                if (has_plain_load and primitive.name != "load") or (
                    has_plain_store and primitive.name != "store"
                ):
                    offenders.append(
                        f"{primitive.name}:{'/'.join(implementation.selector_path)}"
                    )

    assert offenders == []

def test_clang_unpacked_mask_load_uses_vector_comparison(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "load_mask_repr", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.primitive.attributes["packed"] == "false"
        and selected.primitive.attributes["aligned"] == "false"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::load<" in lowered.body_text
    assert "::tsl::nequal<" in lowered.body_text
    assert "for " not in lowered.body_text
    assert "mask<set>" not in lowered.body_text

@pytest.mark.parametrize(
    ("packed", "semantic"),
    [("false", "nequal"), ("true", "mask_false")],
)
def test_sve_mask_load_uses_semantic_mask_operations(
    catalog: Catalog,
    machine_profiles,
    packed: str,
    semantic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "load_mask_repr",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.attributes["packed"] == packed
        and selected.primitive.attributes["aligned"] == "false"
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert semantic in lowered.body_text
    assert "svcmpne_n" not in lowered.body_text
    assert "svpfalse_b" not in lowered.body_text

def test_sve_packed_mask_store_uses_semantic_any_test(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["sve128"],
            "store_mask_repr",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "sve128"
        and selected.primitive.attributes["packed"] == "true"
        and selected.primitive.attributes["aligned"] == "false"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "mask_population_count" in lowered.body_text
    assert "mask_binary_and" in lowered.body_text
    assert "svptest_any" not in lowered.body_text

@pytest.mark.parametrize("primitive", ["compress", "expand"])
def test_clang_compress_expand_use_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["compress", "expand"])
@pytest.mark.parametrize(
    ("extension", "fixed_isa", "width"),
    [
        ("clang_v128", "sse", 128),
        ("clang_v256", "avx2", 256),
        ("clang_v512", "avx512", 512),
    ],
)
@pytest.mark.parametrize(
    ("profile", "type_tag", "lane_bits"),
    [
        ("skylake", "ui32", 32),
        ("skylake", "f32", 32),
        ("icelake_rockerlake", "ui8", 8),
    ],
)
def test_clang_compress_expand_delegate_to_fixed_native_avx512_leaf(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
    fixed_isa: str,
    width: int,
    profile: str,
    type_tag: str,
    lane_bits: int,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            primitive,
            (type_tag,),
            backend_id="cpp",
        )
        .selected
        if selected.extension.name == extension
    )

    assert slot.implementation.type_group == "[idqword, bword, f?]"
    assert slot.fixed_fallback_extension is not None
    assert slot.fixed_fallback_extension.isa_name == fixed_isa
    assert "avx512f" in slot.required_features
    assert ("avx512_vbmi2" in slot.required_features) == (type_tag == "ui8")

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert f"fixed<{width // lane_bits}>" in lowered.body_text
    assert "::tsl::to_integral<Vec>(mask)" in lowered.body_text
    assert "::tsl::to_mask<" in lowered.body_text
    assert f"::tsl::{primitive}<" in lowered.body_text
    assert "::tsl::bit_cast<" in lowered.body_text
    assert "[0]" not in lowered.body_text
    dependencies = {
        (origin.dependency.primitive, origin.dependency.source.extension_isa)
        for origin in lowered.call_dependency_origins
    }
    assert dependencies == {
        (primitive, fixed_isa),
        ("to_integral", extension),
        ("to_mask", fixed_isa),
    }


@pytest.mark.parametrize("primitive", ["compress", "expand"])
@pytest.mark.parametrize("extension", ["clang_v128", "clang_v256", "clang_v512"])
def test_clang_compress_expand_keep_direct_lane_fallback_without_vbmi2(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            primitive,
            ("ui8",),
            backend_id="cpp",
        )
        .selected
        if selected.extension.name == extension
    )

    assert slot.implementation.type_group == "arith"
    assert slot.required_features == frozenset()
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "[0]" in lowered.body_text
    assert "fixed<" not in lowered.body_text
    assert "for " not in lowered.body_text


def test_clang_conflict_unrolls_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "conflict", ("ui32",))
        .selected
        if selected.extension.name == "clang_v256"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "data[1]" in lowered.body_text
    assert "data[0]" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize("backend_id", ["cpp", "rust"])
def test_x86_conflict_generation_expands_fixed_nested_loops(
    catalog: Catalog,
    machine_profiles,
    backend_id: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "conflict", ("ui32",))
        .selected
        if selected.extension.name == "avx2"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, backend_id)
    ).specialization

    assert lowered is not None
    assert "values[1]" in lowered.body_text
    assert "values[7]" in lowered.body_text
    assert "result[1]" in lowered.body_text
    assert "result[7]" in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "extension"),
    [
        ("wasm32-simd128", "wasm128"),
        ("neon", "neon"),
    ],
)
@pytest.mark.parametrize("type_tag", ["ui8", "si16", "ui32", "si64"])
def test_conflict_unrolls_semantic_lane_primitives(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "conflict", (type_tag,))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "extract_value" in lowered.body_text
        assert "insert_value" in lowered.body_text
        assert "extract_lane" not in lowered.body_text
        assert "replace_lane" not in lowered.body_text
        assert "vgetq_lane" not in lowered.body_text
        assert "vsetq_lane" not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["ui8", "si16", "ui32", "si64"])
def test_sve_conflict_accumulates_vector_matches_without_memory(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "conflict", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svlastb_" in lowered.body_text
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::greater_than<" in lowered.body_text
    assert "::tsl::mask_binary_and<" in lowered.body_text
    assert "::tsl::binary_or_mask<" in lowered.body_text
    assert "::tsl::set1<" in lowered.body_text
    assert "svindex_" not in lowered.body_text
    assert "svcmpeq_n_" not in lowered.body_text
    assert "svcmpgt_n_" not in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svand_b_z" not in lowered.body_text
    assert "svorr_n_" not in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text

def test_sve_insert_value_uses_semantic_singleton_lane_mask(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog, machine_profiles["sve128"], "insert_value", ("ui32",)
        )
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "::tsl::mov_mask<" in lowered.body_text
    assert "imask_type" not in lowered.body_text

@pytest.mark.parametrize(
    ("primitive", "type_tag", "evidence"),
    [
        ("compress", "ui8", "svlastb_u8"),
        ("expand", "si16", "svlastb_s16"),
        ("expand", "f64", "svlastb_f64"),
        ("compress_store", "ui8", "svlastb_u8"),
        ("expand_load", "f32", "::tsl::masked_set1<"),
    ],
)
def test_sve_pack_expand_paths_stay_register_only(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
    evidence: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert evidence in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "std::free" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text
    assert "mask_population_count" in lowered.body_text
    assert "mask_binary_and" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svptest_any" not in lowered.body_text

@pytest.mark.parametrize("type_tag", ["si16", "ui32", "si64", "f64"])
def test_sve_convert_down_stays_register_only(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve128"], "convert_down", (type_tag,))
        .selected
        if selected.extension.name == "sve128"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "svlastb_" in lowered.body_text
    assert "masked_set1" in lowered.body_text
    assert "::tsl::sequence<" in lowered.body_text
    assert "::tsl::equal<" in lowered.body_text
    assert "svwhilelt_b" not in lowered.body_text
    assert "svdup_n_" not in lowered.body_text
    assert "saturating_cast" in lowered.body_text
    assert "malloc" not in lowered.body_text
    assert "svst1" not in lowered.body_text
    assert "svld1" not in lowered.body_text

@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
@pytest.mark.parametrize("extension", ["clang_v128", "clang_v256", "clang_v512"])
def test_clang_width_conversion_uses_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, ("si16",))
        .selected
        if selected.extension.name == extension
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "data[" in lowered.body_text
    assert "result[" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text

@pytest.mark.parametrize(
    ("primitive", "extension", "to_extension"),
    [
        ("extract", "clang_v512", "clang_v128"),
        ("insert", "clang_v128", "clang_v512"),
    ],
)
def test_clang_repr_chunk_operations_use_direct_vector_lanes(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    extension: str,
    to_extension: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            primitive,
            ("si32",),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == to_extension
    )
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "result[" in cpp.body_text
    assert "data[" in cpp.body_text
    assert "memcpy" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text
    assert "for " not in cpp.body_text
