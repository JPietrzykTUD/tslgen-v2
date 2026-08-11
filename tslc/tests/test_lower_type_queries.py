"""Typed TSIL query and generated-expression lowering regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    create_backend_dialect,
    Extension,
    GenericParam,
    Implementation,
    ImplementationState,
    Lowerer,
    Primitive,
    pytest,
    replace,
    SelectedImplementation,
    Selector,
    SimdTypeBaseBinding,
    _by_key,
)


def test_lower_scalar_add_has_no_unsafe(catalog: Catalog, machine_profiles) -> None:
    slot = _by_key(catalog, machine_profiles["scalar"], "add")[("si32", "scalar")]
    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp.base_type_spelling == "int32_t"
    # `op<add>` lowers per backend: C++ keeps wrapping `+`, Rust uses the wrapping lane op.
    assert cpp.body_text == "return (left + right);"
    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust.base_type_spelling == "i32"
    assert rust.body_text == "return left.tsl_add(right);"


def test_lower_to_vector_lane_bitmask_identity_is_native(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "to_vector", ("si64",))
        .selected
    }
    slot = slots[("si64", "avx2")]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return mask;"
    assert cpp.implementation_state is ImplementationState.NATIVE


def test_oneapi_exact_lane_mask_policy_lowers_lane_bitmask_operations(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = {
        (s.type_tag, s.extension.name): s
        for s in Selector()
        .select_profile(catalog, machine_profiles["skylake-oneapi"], "less_than", ("si32",))
        .selected
        if s.primitive.attributes.get("mask") is None
    }
    slot = slots[("si32", "oneapi_fpga")]

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert "typename Vec::mask_type result = 0;" in cpp.body_text
    assert "result |= (1ull << (i));" in cpp.body_text
    assert "typename Vec::register_type result" not in cpp.body_text


def test_rust_sse_float_nequal_uses_sse_cmpneq_intrinsic(
    catalog: Catalog,
    machine_profiles,
) -> None:
    slots = _by_key(catalog, machine_profiles["sse"], "nequal")
    slot = slots[("f32", "sse")]

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization

    assert rust is not None
    assert "core::arch::x86_64::_mm_cmpneq_ps(left, right)" in rust.body_text
    assert "core::arch::x86_64::_mm_cmp_ps" not in rust.body_text


@pytest.mark.parametrize("backend_id", ("cpp", "rust"))
def test_fixed_non_x86_extension_requires_register_metadata(backend_id: str) -> None:
    ext = Extension(
        name="tiny_arm",
        isa_name="tiny_arm",
        family="arm",
        backend_supported={"cpp": True, "rust": True},
        vector_bits=128,
    )
    impl = Implementation(
        ("tiny_arm", "ints"),
        "tiny_arm",
        "ints",
        "complete(data);",
        source_order=0,
    )
    prim = Primitive(
        name="metadata_guard",
        signature="v:=v",
        parameters=("data",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"tiny_arm": ext},
        type_spellings={
            "cpp": {"s32": "int32_t"},
            "rust": {"s32": "i32"},
        },
        translations={
            "cpp": {"complete": "return {value}"},
            "rust": {"complete": "return {value}"},
        },
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    unsupported_slot = replace(
        slot,
        extension=replace(ext, backend_supported={}),
    )
    unsupported = Lowerer().lower(
        unsupported_slot,
        catalog,
        create_backend_dialect(catalog, backend_id),
    )

    assert unsupported.specialization is None
    assert [diagnostic.code for diagnostic in unsupported.diagnostics] == [
        "TSL-LOWER-BACKEND-UNSUPPORTED"
    ]

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.specialization is None
    assert [diagnostic.code for diagnostic in lowered.diagnostics] == [
        "TSL-LOWER-NO-REGISTER-TYPE"
    ]
    assert "tiny_arm" in lowered.diagnostics[0].message


def test_avx_truncating_cast_uses_exact_conversion_intrinsic(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "cast", ("f32",))
        .selected
        if s.extension.name == "avx2" and s.to_target == "si32"
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    assert cpp is not None
    assert "_mm256_cvttps_epi32" in cpp.body_text
    assert "_MM_FROUND_TO_ZERO" not in cpp.body_text

    rust = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert rust is not None
    assert "core::arch::x86_64::_mm256_cvttps_epi32" in rust.body_text
    assert "_MM_FROUND_TO_ZERO" not in rust.body_text


@pytest.mark.parametrize(
    ("backend_id", "expected"),
    (
        ("cpp", "return IndexVec::lane_count_v;"),
        ("rust", "return IndexVec::ELEMENT_COUNT;"),
    ),
)
def test_simd_type_generic_param_queries_lower_from_authored_name(
    catalog: Catalog,
    backend_id: str,
    expected: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        "complete(value(generic::length(IndexVec)));",
        source_order=0,
    )
    primitive = Primitive(
        name="index_lane_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert tuple(
        (param.name, param.bounds, param.base_type_constraints)
        for param in lowered.specialization.type_params
    ) == (("IndexVec", (), ("?i32",)),)
    assert lowered.specialization.body_text == expected


@pytest.mark.parametrize("backend_id", ("cpp", "rust"))
def test_bound_simd_type_generic_base_folds_generation_condition(
    catalog: Catalog,
    backend_id: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        (
            "complete(value(select("
            "value(type::same_size(type(base::in), type(base::generic(IndexVec)))), "
            "\"1\", \"0\")));"
        ),
        source_order=0,
    )
    primitive = Primitive(
        name="index_base_width_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
                specialize_base=True,
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
        simd_type_base_bindings=(SimdTypeBaseBinding("IndexVec", "ui32"),),
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert lowered.specialization.body_text == "return 1;"
    expected_spelling = "uint32_t" if backend_id == "cpp" else "u32"
    assert tuple(
        (
            param.name,
            param.specialize_base,
            param.base_type_binding,
            param.base_type_binding_spelling,
        )
        for param in lowered.specialization.type_params
    ) == (("IndexVec", True, "ui32", expected_spelling),)


@pytest.mark.parametrize(
    ("backend_id", "expected"),
    (
        (
            "cpp",
            "return ((left == right) ? (static_cast<int32_t>(0)) : (left));",
        ),
        (
            "rust",
            "return if left == right { (0) as i32 } else { left };",
        ),
    ),
)
def test_select_expr_lowers_to_backend_conditional_expression(
    catalog: Catalog,
    backend_id: str,
    expected: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        (
            "complete(select_expr("
            "left == right, "
            "cast<static>(base::in, 0), "
            "left"
            "));"
        ),
        source_order=0,
    )
    primitive = Primitive(
        name="select_expr_probe",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        attribute_keys=(),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert lowered.specialization.body_text == expected


@pytest.mark.parametrize(
    ("backend_id", "expected_call"),
    (
        ("cpp", "to_array<IndexVec>(index)"),
        ("rust", "to_array::<IndexVec>(index)"),
    ),
)
def test_simd_type_generic_param_can_target_primitive_call(
    catalog: Catalog,
    backend_id: str,
    expected_call: str,
) -> None:
    impl = Implementation(
        ("avx2", "all"),
        "avx2",
        "all",
        """
        var<infer>(idx_array, call<primitive=to_array[IndexVec]>(index));
        complete(idx_array[0]);
        """,
        source_order=0,
    )
    primitive = Primitive(
        name="index_array_probe",
        signature="usize:=vidx",
        parameters=("index",),
        attribute_keys=(),
        generic_params=(
            GenericParam(
                "IndexVec",
                "simd_type",
                "",
                base_type_constraints=("?i32",),
            ),
        ),
        implementations=(impl,),
    )
    slot = SelectedImplementation(
        primitive=primitive,
        implementation=impl,
        extension=catalog.extensions["avx2"],
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))

    assert lowered.diagnostics == ()
    assert lowered.specialization is not None
    assert expected_call in lowered.specialization.body_text
    assert tuple(param.name for param in lowered.specialization.type_params) == ("IndexVec",)
