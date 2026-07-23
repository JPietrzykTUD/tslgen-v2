"""Generic, scalar, and compiler-vector lowering regressions."""

from __future__ import annotations

from _select_lower_core_support import (
    Catalog,
    create_backend_dialect,
    Lowerer,
    pytest,
    Selector,
    _by_key,
)
from tslc.backend.cpp_documentation import cpp_doc
from tslc.backend.rust_documentation import rust_doc


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin"])
@pytest.mark.parametrize("masked", [False, True])
def test_generic_like_horizontal_reductions_index_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "vec[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_generic_like_bitwise_reductions_index_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
    type_tag: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "vec[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_scalar_bitwise_reductions_do_not_materialize_single_lane_arrays(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    masked: bool,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "scalar"
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hadd", "hmax", "hmin"])
@pytest.mark.parametrize("masked", [False, True])
def test_scalar_arithmetic_reductions_do_not_materialize_single_lane_arrays(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    masked: bool,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, ("ui32",))
        .selected
        if selected.extension.name == "scalar"
        and (len(selected.primitive.parameters) == 2) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
def test_scalar_width_conversions_are_direct_scalar_casts(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, ("si16",))
        .selected
        if selected.extension.name == "scalar"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text
        assert "for " not in lowered.body_text


def test_lane_preserving_conversion_keeps_explicit_target_vector_typed(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = tuple(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "convert_lanes",
            ("si32",),
        )
        .selected
        if selected.extension.name == "avx2"
    )

    assert {
        binding.base_tag
        for selected in slots
        for binding in selected.simd_type_base_bindings
        if binding.param_name == "ToVec"
    } == {"si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"}

    selected = next(
        item
        for item in slots
        if item.simd_type_base_bindings[0].base_tag == "f64"
    )
    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            selected,
            catalog,
            create_backend_dialect(catalog, backend_id),
        ).specialization

        assert lowered is not None
        assert lowered.result_vector_param == "ToVec"
        target = next(param for param in lowered.type_params if param.name == "ToVec")
        assert target.base_type_binding == "f64"
        assert "require_same_lanes" in lowered.body_text
        assert "scalar_as_cast" in lowered.body_text
        rendered_doc = (
            cpp_doc(lowered, context="implementation")
            if backend_id == "cpp"
            else rust_doc(lowered, context="implementation")
        )
        assert "ToVec" in rendered_doc.split("Returns", 1)[1].splitlines()[0]


def test_scalar_lzc_and_cast_are_direct_scalar_operations(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = (
        next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["scalar"], "lzc", ("ui32",))
            .selected
            if selected.extension.name == "scalar"
        ),
        next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["scalar"], "cast", ("si32",))
            .selected
            if selected.extension.name == "scalar" and selected.to_target == "f64"
        ),
    )

    for slot in slots:
        for backend_id in ("cpp", "rust"):
            lowered = Lowerer().lower(
                slot, catalog, create_backend_dialect(catalog, backend_id)
            ).specialization

            assert lowered is not None
            assert "to_array" not in lowered.body_text
            assert "from_array" not in lowered.body_text
            assert "for " not in lowered.body_text


@pytest.mark.parametrize("primitive", ["hand", "hor"])
@pytest.mark.parametrize("type_tag", ["ui32", "f32"])
def test_clang_masked_bitwise_reductions_stay_in_vector_or_typed_composition(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if selected.extension.name == "clang_v128"
        and len(selected.primitive.parameters) == 2
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert primitive in lowered.body_text
    assert "binary_" in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["popcnt", "lzc"])
def test_generic_like_bit_counts_mutate_native_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_generic_cast_mutates_native_output_register_directly(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], "cast", ("si32",))
        .selected
        if selected.extension.name == "generic" and selected.to_target == "f64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "data[i]" in lowered.body_text
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["convert_up", "convert_down"])
def test_generic_like_width_conversions_mutate_native_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("si16",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "data[" in lowered.body_text
        assert "result[" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_set_constructs_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "set", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_expand_load_mutates_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "expand_load", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_load_convert_up_mutates_output_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "load_convert_up",
            ("ui32",),
        )
        .selected
        if selected.extension.name == extension and selected.to_target == "ui64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "out[i]" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    ("primitive", "masked", "type_tag", "keeps_index_array"),
    [
        ("gather", False, "ui32", True),
        ("gather", True, "ui32", True),
        ("gather_narrow_partial", False, "ui16", True),
        ("gather_narrow", False, "ui16", False),
    ],
)
def test_generic_like_gathers_write_native_array_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    masked: bool,
    type_tag: str,
    keeps_index_array: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, (type_tag,))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[i]" in lowered.body_text
        assert ("idx_array" in lowered.body_text) is keeps_index_array
        assert "from_array" not in lowered.body_text
        assert not any(
            "result" in line and "to_array" in line
            for line in lowered.body_text.splitlines()
        )


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("masked", [False, True])
def test_generic_like_scatters_read_native_value_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    masked: bool,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "scatter", ("ui32",))
        .selected
        if selected.extension.name == extension
        and ("mask" in selected.primitive.attribute_keys) is masked
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "a[i]" in lowered.body_text
        assert "idx_array" in lowered.body_text
        assert "val_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize("primitive", ["select", "compress", "expand", "conflict"])
def test_generic_like_misc_fallbacks_mutate_native_array_registers_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "result[" in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    ("primitive", "operator"),
    [
        ("mask_binary_and", "&"),
        ("mask_binary_or", "|"),
        ("mask_binary_xor", "^"),
        ("mask_binary_not", None),
    ],
)
def test_generic_like_mask_logic_uses_packed_bitset_operations(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
    operator: str | None,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "valid_lanes" in lowered.body_text
        assert "for " not in lowered.body_text
        assert "mask<" not in lowered.body_text
        if operator is not None:
            assert operator in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
@pytest.mark.parametrize(
    "primitive",
    [
        "equal",
        "nequal",
        "less_than",
        "greater_than",
        "less_than_or_equal",
        "greater_than_or_equal",
    ],
)
def test_generic_like_masked_comparisons_compose_unmasked_compare_and_mask_logic(
    catalog: Catalog,
    machine_profiles,
    extension: str,
    primitive: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], primitive, ("ui32",))
        .selected
        if selected.extension.name == extension
        and len(selected.primitive.parameters) == 3
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "mask_binary_and" in lowered.body_text
        assert primitive in lowered.body_text
        assert "for " not in lowered.body_text


def test_generic_mask_population_count_uses_packed_popcount(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["scalar"],
            "mask_population_count",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "generic"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "popcount" in lowered.body_text
        assert "for " not in lowered.body_text


@pytest.mark.parametrize("extension", ["generic", "oneapi_fpga"])
def test_generic_like_ostream_formats_native_array_register_directly(
    catalog: Catalog,
    machine_profiles,
    extension: str,
) -> None:
    profile = "skylake-oneapi" if extension == "oneapi_fpga" else "scalar"
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_ostream", ("ui32",))
        .selected
        if selected.extension.name == extension
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "ostream_write" in lowered.body_text
        assert "to_array" not in lowered.body_text


def test_sve_ostream_uses_typed_runtime_storage(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["sve"], "to_ostream", ("ui32",))
        .selected
        if selected.extension.name == "sve"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "values_storage" in lowered.body_text
    assert "std::malloc" not in lowered.body_text
    assert "std::free" not in lowered.body_text


def test_scalar_load_convert_up_is_a_direct_scalar_load_and_cast(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["scalar"],
            "load_convert_up",
            ("ui32",),
        )
        .selected
        if selected.extension.name == "scalar" and selected.to_target == "ui64"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "*ptr" in lowered.body_text
        assert "for " not in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


def test_clang_load_convert_up_unrolls_direct_output_lanes(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "load_convert_up", ("si8",))
        .selected
        if selected.extension.name == "clang_v256"
        and selected.to_target == "si16"
    )
    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "out[0]" in lowered.body_text
    assert "ptr" in lowered.body_text
    assert "to_array" not in lowered.body_text
    assert "from_array" not in lowered.body_text
    assert "for " not in lowered.body_text


@pytest.mark.parametrize(
    (
        "profile",
        "extension",
        "source_type",
        "target_type",
        "copy_expression",
        "conversion",
    ),
    [
        ("sse2", "sse", "si8", "si64", "2 * 1", "convert_up"),
        ("sse2", "sse", "f32", "f64", "2 * 4", "convert_up"),
        ("avx2", "avx2", "si8", "si64", "4 * 1", "convert_up"),
        ("knl", "avx512", "si8", "si64", "8 * 1", "_mm512_cvtepi8_epi64"),
        ("neon", "neon", "si8", "si64", "2 * 1", "convert_up"),
        ("wasm32-simd128", "wasm128", "ui16", "ui64", "2 * 2", "convert_up"),
    ],
)
def test_fixed_width_load_convert_up_copies_only_consumed_bytes(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    extension: str,
    source_type: str,
    target_type: str,
    copy_expression: str,
    conversion: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile],
            "load_convert_up",
            (source_type,),
        )
        .selected
        if selected.extension.name == extension
        and selected.to_target == target_type
    )

    for backend_id, copy_spelling in (
        ("cpp", "memcpy"),
        ("rust", "mem_copy"),
    ):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert copy_spelling in lowered.body_text
        assert copy_expression in lowered.body_text
        assert conversion in lowered.body_text
        assert "to_array" not in lowered.body_text
        assert "from_array" not in lowered.body_text


@pytest.mark.parametrize(
    ("profile", "type_tag", "intrinsic"),
    [
        ("sse2", "ui8", "_mm_set_epi8"),
        ("sse2", "ui16", "_mm_set_epi16"),
        ("sse2", "ui32", "_mm_set_epi32"),
        ("sse2", "ui64", "_mm_set_epi64x"),
        ("sse2", "f64", "_mm_set_epi64x"),
        ("avx2", "ui64", "_mm_set_epi64x"),
    ],
)
def test_sse_to_mask_builds_lane_bit_constants_without_memory(
    catalog: Catalog,
    machine_profiles,
    profile: str,
    type_tag: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles[profile], "to_mask", (type_tag,))
        .selected
        if selected.extension.name == "sse"
    )

    for backend_id in ("cpp", "rust"):
        lowered = Lowerer().lower(
            slot, catalog, create_backend_dialect(catalog, backend_id)
        ).specialization

        assert lowered is not None
        assert "and_values" not in lowered.body_text
        assert "::tsl::load" not in lowered.body_text
        assert intrinsic in lowered.body_text


def test_clang_mask_kernels_use_their_declared_representation_and_integral_bridge(
    catalog: Catalog, machine_profiles
) -> None:
    profile = machine_profiles["avx2"]

    equal_slot = _by_key(catalog, profile, "equal")[("f32", "clang_v256")]
    equal = Lowerer().lower(
        equal_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert equal is not None
    assert "return left == right;" in equal.body_text

    to_integral_slot = _by_key(catalog, profile, "to_integral")[
        ("f32", "clang_v256")
    ]
    to_integral = Lowerer().lower(
        to_integral_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert to_integral is not None
    assert "if (mask[0] != 0)" in to_integral.body_text
    assert (
        "result |= (static_cast<typename Vec::imask_type>(1)) << 0;"
        in to_integral.body_text
    )

    to_mask_slot = _by_key(catalog, profile, "to_mask")[("f32", "clang_v256")]
    to_mask = Lowerer().lower(
        to_mask_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert to_mask is not None
    assert "typename Vec::mask_type result = static_cast<typename Vec::mask_type>(0);" in (
        to_mask.body_text
    )
    assert "result[0] = -1;" in to_mask.body_text

    bool_equal_slot = _by_key(catalog, profile, "equal")[("f32", "clang_v256_bool")]
    bool_equal = Lowerer().lower(
        bool_equal_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_equal is not None
    assert "return left == right;" in bool_equal.body_text

    bool_to_integral_slot = _by_key(catalog, profile, "to_integral")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_integral = Lowerer().lower(
        bool_to_integral_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_integral is not None
    assert "if (mask[0])" in bool_to_integral.body_text

    bool_to_mask_slot = _by_key(catalog, profile, "to_mask")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_mask = Lowerer().lower(
        bool_to_mask_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_mask is not None
    assert "static_cast<typename Vec::mask_type>(false)" in bool_to_mask.body_text
    assert "result[0] = true;" in bool_to_mask.body_text

    bool_to_vector_slot = _by_key(catalog, profile, "to_vector")[
        ("f32", "clang_v256_bool")
    ]
    bool_to_vector = Lowerer().lower(
        bool_to_vector_slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert bool_to_vector is not None
    assert "::tsl::select<Vec>" in bool_to_vector.body_text
    assert "::tsl::set_zero<Vec>()" in bool_to_vector.body_text
    assert "::tsl::set1<Vec>" in bool_to_vector.body_text
    assert "::tsl::bit_cast" not in bool_to_vector.body_text
